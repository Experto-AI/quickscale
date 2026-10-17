"""Shared non-boundary command helpers for the organization purge command.

The command module keeps ``Command.handle``, ``_purge_by_uuid``,
``_dry_run_by_uuid``, ``_resolve_models``, ``_model_label``, and the
provider-state guard methods whose call sites resolve test patch seams through
the command module, and it keeps the ``RemovalCoordinator`` discharge calls the
rule 34 boundary check follows; the targeting validation, confirmation,
preflight, tombstone, reserved-org guard, ownership printing, and
cache-invalidation helpers live here, as do the purge, dry-run, and guarded
ownership-map transactions, so the command module opens no transaction of its
own (Module Conventions rule 17) and stays inside the file-length contract
(rule 28).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import CommandError
from django.db import models, transaction

from quickscale_modules_orgs._purge_plan import (
    _carries_provider_value as _carries_provider_value,
    _get_qs as _get_qs,
    _mapping_carries_value as _mapping_carries_value,
)
from quickscale_modules_orgs._removal_types import ORGANIZATION_MODEL_LABEL
from quickscale_modules_orgs._tenancy_discovery import has_organization_id_field
from quickscale_modules_orgs.current_org import (
    reset_current_org_id,
    set_current_org_for_context,
)
from quickscale_modules_orgs.models import (
    Organization,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationTombstone,
)
from quickscale_modules_orgs.removal import RemovalCoordinator


class _PurgeSupportMixin:
    """Non-boundary purge command helpers shared through the command class."""

    _force: bool
    stdout: Any
    style: Any

    if TYPE_CHECKING:

        def _build_ownership_map(
            self, organization: Organization
        ) -> dict[str, int]: ...

        def _delete_owned_rows(self, organization: Organization) -> None: ...

        def _guard_boundary_provider_state(
            self,
            organization: Organization,
            *,
            provider_expired_checkouts: dict[str, str] | None = None,
        ) -> None: ...

        def _guard_provider_backed_fields(self, organization: Organization) -> None: ...

        def _invalidate_organization_caches(
            self,
            org_id: uuid.UUID,
            *,
            coordinator: RemovalCoordinator,
        ) -> None: ...

        def _lock_organization(self, org_id: object) -> Organization: ...

    # ------------------------------------------------------------------
    # Slug preflight
    # ------------------------------------------------------------------

    def _preflight_by_slug(self, slug: str) -> str | None:
        """Look up an organization by slug and print its state (non-destructive)."""
        try:
            organization = Organization.objects.get(slug=slug)
        except Organization.DoesNotExist:
            raise CommandError(
                f"No organization found with slug {slug!r}. "
                "Use --organization-id <uuid> to search by UUID or check the slug."
            )

        self._guard_reserved_org(organization)
        self._print_ownership_summary(
            organization, self._build_ownership_map_guarded(organization)
        )
        self.stdout.write(
            self.style.WARNING(
                "Preflight only — no changes were made. "
                "Use --organization-id <uuid> for destructive execution."
            )
        )
        return None

    def _check_tombstone(
        self,
        org_id: uuid.UUID,
        *,
        heal_social_cache: bool,
        coordinator: RemovalCoordinator,
    ) -> None:
        """Check for a tombstone when the org does not exist."""
        try:
            tombstone = OrganizationTombstone.objects.get(organization_id=org_id)
        except OrganizationTombstone.DoesNotExist:
            return

        if heal_social_cache:
            self._invalidate_organization_caches(org_id, coordinator=coordinator)

        self.stdout.write(
            f"Organization {org_id} was already purged "
            f"on {tombstone.purged_at:%Y-%m-%d %H:%M:%S} UTC. "
            "No action taken."
        )
        self.stdout.write("  Memberships deleted: 0")
        self.stdout.write("  Invitations deleted: 0")
        raise CommandError(
            "No-op: organization was already purged. See output above.",
            returncode=0,
        )

    # ------------------------------------------------------------------
    # Transactional execution (rule 17)
    #
    # The transaction opens below the command module: the command routes the
    # RemovalCoordinator discharge calls the rule 34 boundary check follows,
    # and these helpers own the database work's transaction.atomic().
    # ------------------------------------------------------------------

    def _execute_purge_transaction(
        self,
        org_id: uuid.UUID,
        *,
        confirm: str | None,
    ) -> tuple[Organization, dict[str, int]]:
        """Irrevocably delete the organization and all owned rows in one transaction.

        Locks the organization row, re-checks the reserved-org guard and the
        confirmation under that lock, establishes the RLS context, runs the
        refusal guards, builds the pre-delete ownership map, deletes the
        tenant plan and the org-level rows, and records the tombstone; a
        failure rolls all of it back together.
        """
        with transaction.atomic():
            # This row is the per-organization billing mutation mutex.
            # Lock it before checking provider state and keep the lock
            # through deletion so a concurrent billing writer either
            # commits first and is observed or waits and then fails closed.
            organization = self._lock_organization(org_id)
            self._guard_reserved_org(organization)
            if confirm is None or confirm not in {
                organization.slug,
                str(organization.pk),
            }:
                raise CommandError(
                    "--confirm must exactly match the organization's slug or "
                    f"UUID ({organization.slug!r} or {organization.pk}) before a "
                    "purge may proceed."
                )

            # Establish consistent org context for RLS-protected tables
            # BEFORE checking, counting, or deleting. Under PostgreSQL
            # FORCE-RLS the runtime role cannot see rows without
            # app.current_org_id set.
            set_current_org_for_context(org_id=organization.pk)
            try:
                self._guard_boundary_provider_state(organization)
                self._guard_provider_backed_fields(organization)

                # Build the map inside the atomic block so counts match
                # the pre-delete snapshot with org context already active.
                ownership_map = self._build_ownership_map(organization)

                # Cross-module owned rows (FK-safe delete order).
                self._delete_owned_rows(organization)

                # Org-level rows — use _raw_delete to bypass model delete()
                # and signal receivers (notably the pre_delete backstop
                # on OrganizationMembership). The purge is intentionally
                # destroying the org and all its rows; individual row-level
                # protections are irrelevant here.
                OrganizationInvitation.objects.filter(
                    organization=organization
                )._raw_delete(OrganizationInvitation.objects.db)
                OrganizationMembership.objects.filter(
                    organization=organization
                )._raw_delete(OrganizationMembership.objects.db)

                # All known FK-referencing rows — the tenant plan, the
                # non-tenant organization children, and the org-owned rows
                # below — are already deleted, so bypass Django's cascade
                # collector for the org row too.
                Organization.objects.filter(pk=organization.pk)._raw_delete(
                    Organization.objects.db
                )

                OrganizationTombstone.objects.create(
                    organization_id=org_id,
                )
            finally:
                reset_current_org_id()
        return organization, ownership_map

    def _execute_dry_run_transaction(
        self,
        org_id: uuid.UUID,
        *,
        provider_expired_checkouts: dict[str, str] | None = None,
    ) -> tuple[Organization, dict[str, int]]:
        """Read one organization's ownership state in one transaction, writing nothing.

        The command module routes the ``REFUSE`` discharge and prints the
        summary; this helper owns the ``transaction.atomic()`` so the
        rehearsal observes the same row-locked state the destructive path
        would.
        """
        with transaction.atomic():
            organization = self._lock_organization(org_id)
            self._guard_reserved_org(organization)
            set_current_org_for_context(org_id=organization.pk)
            try:
                self._guard_boundary_provider_state(
                    organization,
                    provider_expired_checkouts=provider_expired_checkouts or {},
                )
                self._guard_provider_backed_fields(organization)
                ownership_map = self._build_ownership_map(organization)
            finally:
                reset_current_org_id()
        return organization, ownership_map

    def _build_ownership_map_guarded(
        self, organization: Organization
    ) -> dict[str, int]:
        """Build the ownership map with org context established.

        Wraps :meth:`_build_ownership_map` inside ``transaction.atomic()``
        with ``set_current_org_for_context()`` already active.  Under
        PostgreSQL FORCE-RLS the runtime role cannot count rows on
        RLS-protected tables without ``app.current_org_id`` set.

        The ContextVar is always reset in ``finally``; the DB-side
        ``SET LOCAL`` is automatically undone when the atomic block
        commits or rolls back.
        """
        with transaction.atomic():
            set_current_org_for_context(org_id=organization.pk)
            try:
                return self._build_ownership_map(organization)
            finally:
                reset_current_org_id()

    def _guard_reserved_org(self, organization: Organization) -> None:
        """Raise :class:`CommandError` if *organization* is reserved.

        Guards System and personal orgs.  ``--force`` bypasses the guard.
        """
        if self._force:
            return
        reserved_labels: list[str] = []
        if organization.is_system:
            reserved_labels.append("System")
        if organization.is_personal:
            reserved_labels.append("personal")
        if reserved_labels:
            label = " and ".join(reserved_labels)
            raise CommandError(
                f"Cannot purge the {label} organization ({organization.pk}). "
                "Use --force to override."
            )

    def _validate_declared_field_labels(
        self,
        obligations: tuple,
        organization: Organization,
    ) -> None:
        """Refuse when a declared provider field names an uninstalled model."""
        # Every declared label must resolve, guarded or not: a misspelled or
        # uninstalled label would otherwise be read as "no provider state".
        for obligation in obligations:
            for provider_field in obligation.external_provider_fields:
                try:
                    apps.get_model(provider_field.model_label)
                except LookupError as exc:
                    raise CommandError(
                        f"Cannot purge organization {organization.pk}: obligation "
                        f"{obligation.name!r} names "
                        f"{provider_field.model_label}, which is not an installed "
                        "model."
                    ) from exc

    def _print_ownership_summary(
        self,
        organization: Organization,
        ownership_map: dict[str, int],
    ) -> None:
        """Print the ownership summary for *organization*."""
        self.stdout.write(f"Organization: {organization.pk} ({organization.name})")
        if organization.slug:
            self.stdout.write(f"  Slug: {organization.slug}")

        total_owned = 0
        for label, count in sorted(ownership_map.items()):
            if count:
                self.stdout.write(f"  {label}: {count}")
                total_owned += count
        if not total_owned:
            self.stdout.write("  No owned rows found.")

    def _require_confirmation(self, org_id: uuid.UUID, confirm: str | None) -> None:
        """Refuse a destructive purge before any provider write without --confirm."""
        slug = (
            Organization.objects.filter(pk=org_id)
            .values_list("slug", flat=True)
            .first()
        )
        if slug is None:
            # The purge path reports the missing organization itself.
            return
        if confirm is None or confirm not in {slug, str(org_id)}:
            raise CommandError(
                "--confirm must exactly match the organization's slug or "
                f"UUID ({slug!r} or {org_id}) before a purge may proceed."
            )

    def _validate_targeting(
        self,
        raw_org_id: str | None,
        slug: str | None,
        dry_run: bool,
    ) -> None:
        """Reject impossible targeting combinations and warn on ignored flags."""
        if raw_org_id and slug:
            raise CommandError(
                "Cannot combine --organization-id (destructive) with --slug "
                "(non-destructive preflight). Use one targeting flag at a time."
            )

        if not raw_org_id and not slug:
            raise CommandError(
                "Specify --organization-id <uuid> for destructive execution or "
                "--slug <slug> for non-destructive preflight."
            )

        if slug and dry_run:
            self.stdout.write(
                self.style.WARNING(
                    "Warning: --dry-run has no effect with --slug (preflight is "
                    "always non-destructive)."
                )
            )

    def _print_purge_summary(
        self,
        organization: Organization,
        ownership_map: dict[str, int],
    ) -> None:
        """Print the purge completion summary."""
        total_deleted = sum(ownership_map.values())

        self.stdout.write(
            self.style.SUCCESS(
                f"Organization {organization.pk} ({organization.name}) has been purged."
            )
        )
        for label, count in sorted(ownership_map.items()):
            if count:
                self.stdout.write(f"  {label}: {count}")
        self.stdout.write(f"  Total rows deleted: {total_deleted}")
        self.stdout.write(f"  Tombstone recorded for: {organization.pk}")

    def _refusal_field_rows(
        self,
        model: type[models.Model],
        provider_field: Any,
        organization: Organization,
        label: str,
    ) -> list:
        """Return the locked rows a declared refusal field must be read from."""
        if model._meta.label_lower == ORGANIZATION_MODEL_LABEL:
            # The organization row itself carries the declared state.
            return [organization]
        if has_organization_id_field(model):
            queryset = _get_qs(model, {"organization_id": organization.pk})
            return list(
                queryset.select_for_update().only(  # type: ignore[attr-defined]
                    provider_field.field_name
                )
            )
        raise CommandError(
            f"Cannot purge organization {organization.pk}: declared "
            f"refusal field {label} is not organization-scoped, so the "
            "purge cannot inspect it."
        )

    def _carried_refusal_field_messages(
        self,
        organization: Organization,
        provider_field: Any,
    ) -> list[str]:
        """Return one declared refusal field's carried-value labels."""
        try:
            model = apps.get_model(provider_field.model_label)
        except LookupError as exc:
            raise CommandError(
                f"Cannot purge organization {organization.pk}: declared refusal "
                f"field names {provider_field.model_label}, which is not an "
                "installed model."
            ) from exc
        label = f"{provider_field.model_label}.{provider_field.field_name}"
        rows = self._refusal_field_rows(model, provider_field, organization, label)
        try:
            model_field = model._meta.get_field(provider_field.field_name)
        except FieldDoesNotExist as exc:
            raise CommandError(
                f"Cannot purge organization {organization.pk}: "
                f"{label} is declared as a refusal field but is not a model "
                "field."
            ) from exc
        if provider_field.structured_keys:
            return [
                f"{label}[{key}]"
                for row in rows
                for key in provider_field.structured_keys
                if _mapping_carries_value(getattr(row, provider_field.field_name), key)
            ]
        if any(
            _carries_provider_value(
                model_field,
                getattr(row, provider_field.field_name),
            )
            for row in rows
        ):
            return [label]
        return []

    def _carried_declared_refusal_fields(
        self,
        organization: Organization,
        refusal_fields: tuple,
    ) -> list[str]:
        """Return declared refusal fields that carry a value for *organization*.

        Every discovered obligation whose purge action is refuse-or-reconcile
        contributes its non-boundary-guarded provider fields; a populated
        scalar value, or a populated declared structured key, refuses the
        purge exactly like a model-classified provider-backed field.  The
        organization row itself is inspected for a field declared on it, and a
        declared field no organization scope can reach fails closed.  Rows are
        locked for the rest of the purge transaction so a concurrent write
        cannot add a value afterwards.
        """
        carried: list[str] = []
        for provider_field in refusal_fields:
            carried.extend(
                self._carried_refusal_field_messages(organization, provider_field)
            )
        return carried
