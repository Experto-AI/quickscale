"""Purge an organization and all owned rows (T1.17).

Destructive execution is locked to ``--organization-id <uuid>`` only.

* ``--slug <slug>`` — non-destructive preflight/lookup only.
* ``--organization-id <uuid>`` — destructive purge or ``--dry-run`` summary.
* ``--dry-run`` — show ownership counts without deleting.
* ``--force`` — bypass reserved-org guard (System and personal orgs).

Contract rules enforced by this command:

* UUID-only destructive targeting.  Slug-only is preflight-only.
* Missing live UUID and no tombstone → error.
* Missing live UUID with tombstone → no-op success with already-gone message.
* Rerun after successful purge → no-op success with clear message.
* System and personal orgs are guarded by default; ``--force`` overrides.
* Current Stripe-backed subscriptions must be cancelled and hosted checkouts
  must be provider-terminal before any purge.
* A row carrying a value in a ``provider_id_classification`` field declared
  provider-backed refuses the purge, naming the field.
* Ownership/count map always includes ``OrganizationInvitation`` rows.
* Tombstone is created in the same transaction as the purge.
* Every marker-derived tenant model, including project-owned models, is
  deleted in an FK-derived child-before-parent order.
* The shared ``set_current_org_for_context()`` helper establishes consistent
  ContextVar + ``SET LOCAL app.current_org_id`` before touching RLS-protected
  tables.

Module Conventions rule 28: the FK-safe ordering, label disambiguation, and
queryset helpers live in ``_purge_plan`` and are re-exported here.  The
``Command.handle`` entry point the rule 34 boundary check follows stays
physically in this module, as does ``_resolve_models`` and ``_model_label``
because tests patch ``get_tenant_models`` and ``_model_label`` on this module.
"""

from __future__ import annotations

import logging
import uuid
from collections import Counter as Counter
from contextlib import ExitStack, nullcontext
from heapq import heappop as heappop, heappush as heappush
from typing import Any, cast

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

from quickscale_modules_orgs._purge_plan import (
    _PURGE_ORDER_OVERRIDES as _PURGE_ORDER_OVERRIDES,
    _carries_provider_value as _carries_provider_value,
    _disambiguated_model_labels as _plan_disambiguated_model_labels,
    _get_filter_for_org as _get_filter_for_org,
    _get_qs as _get_qs,
    _mapping_carries_value as _mapping_carries_value,
    _model_key as _model_key,
    _removal_label_prefixes as _removal_label_prefixes,
    _self_blocking_foreign_keys as _self_blocking_foreign_keys,
    _topologically_order_models as _topologically_order_models,
)
from quickscale_modules_orgs._purge_support import _PurgeSupportMixin
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
from quickscale_modules_orgs.removal import (
    ORGANIZATION_MODEL_LABEL,
    REMOVAL_LABEL_PREFIX_ATTRIBUTE as REMOVAL_LABEL_PREFIX_ATTRIBUTE,
    DeclaredBoundaryGuard,
    RemovalAction,
    RemovalBoundary,
    RemovalCoordinator,
    declared_boundary_guards,
    declared_provider_backed_fields,
    declared_refusal_fields,
    organization_removal_obligations,
)
from quickscale_modules_orgs.tenancy import (
    get_tenant_models,
    has_organization_id_field,
)

logger = logging.getLogger(__name__)


def _model_label(model: type[models.Model]) -> str:
    plural = str(model._meta.verbose_name_plural)
    prefix = _removal_label_prefixes().get(model._meta.app_label)
    if prefix:
        return f"{prefix} {plural[:1].lower()}{plural[1:]}"
    return f"{plural[:1].upper()}{plural[1:]}"


def _disambiguated_model_labels(
    tenant_models: list[type[models.Model]],
) -> list[str]:
    """Keep legacy labels when unique and qualify project label collisions.

    Resolves ``_model_label`` from this module's globals so the
    ``quickscale_orgs_purge_organization._model_label`` test patch seam keeps
    intercepting every label lookup.
    """
    return _plan_disambiguated_model_labels(tenant_models, model_label=_model_label)


def _resolve_models() -> list[dict[str, Any]]:
    """Derive the installed purge plan from marker-enrolled tenant models."""
    tenant_models = get_tenant_models()
    missing_organization_id = sorted(
        _model_key(model)
        for model in tenant_models
        if not has_organization_id_field(model)
    )
    if missing_organization_id:
        raise CommandError(
            "Marker-enrolled tenant models cannot be purged without an "
            "organization_id field: " + ", ".join(missing_organization_id)
        )
    unsupported_self_fields = sorted(
        f"{_model_key(model)}.{field.name}"
        for model in tenant_models
        for field in _self_blocking_foreign_keys(model)
        if not field.null
    )
    if unsupported_self_fields:
        raise CommandError(
            "Marker-enrolled tenant models cannot be purged with non-nullable "
            "self-blocking fields: " + ", ".join(unsupported_self_fields)
        )
    ordered_models = _topologically_order_models(tenant_models)
    labels = _disambiguated_model_labels(ordered_models)
    return [
        {
            "model": model,
            "filter_key": "organization_id",
            "label": label,
        }
        for model, label in zip(ordered_models, labels, strict=True)
    ]


def _parse_organization_id(raw_org_id: object) -> uuid.UUID:
    """Parse the destructive targeting value or fail with the contract message."""
    try:
        return uuid.UUID(str(raw_org_id).strip())
    except ValueError, AttributeError:
        raise CommandError(
            f"Invalid --organization-id value: {raw_org_id!r}. Must be a valid UUID."
        )


class Command(_PurgeSupportMixin, BaseCommand):
    help = (
        "Purge an organization and all owned rows across all modules. "
        "Current Stripe-backed subscriptions must be cancelled and pending "
        "hosted checkouts must be completed or expired first. "
        "Use --organization-id <uuid> for destructive execution; "
        "--slug <slug> for non-destructive preflight only."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--organization-id",
            dest="organization_id",
            type=str,
            required=False,
            default=None,
            help="UUID of the organization to purge (destructive targeting only).",
        )
        parser.add_argument(
            "--slug",
            type=str,
            required=False,
            default=None,
            help="Slug of the organization for non-destructive preflight/lookup.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show ownership counts without deleting.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Override reserved-org guard (System and personal orgs).",
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

    def handle(self, *args: object, **options: Any) -> str | None:
        del args
        raw_org_id: str | None = options.get("organization_id")
        slug: str | None = options.get("slug")
        dry_run: bool = options.get("dry_run", False)
        self._force: bool = options.get("force", False)

        self._validate_targeting(raw_org_id, slug, dry_run)

        # Slug mode — non-destructive preflight only.
        if slug:
            return self._preflight_by_slug(slug.strip())

        # Organization ID mode — parse UUID and dispatch.
        assert raw_org_id is not None  # noqa: S101 - internal invariant guaranteed by the caller
        org_id = _parse_organization_id(raw_org_id)

        coordinator = RemovalCoordinator(RemovalBoundary.PURGE)
        self._require_dischargeable_obligations(coordinator)
        self._guard_provider_reconciliation_target(org_id)
        with self._provider_mutation_lock(org_id):
            if dry_run:
                provider_expired_checkouts = self._reconcile_provider_states(
                    org_id,
                    persist=False,
                )
                return self._dry_run_by_uuid(
                    org_id,
                    coordinator=coordinator,
                    provider_expired_checkouts=provider_expired_checkouts,
                )
            self._reconcile_provider_states(org_id, persist=True)
            return self._purge_by_uuid(org_id, coordinator=coordinator)

    # ------------------------------------------------------------------
    # Dry run by UUID
    # ------------------------------------------------------------------

    def _dry_run_by_uuid(
        self,
        org_id: uuid.UUID,
        *,
        coordinator: RemovalCoordinator,
        provider_expired_checkouts: dict[str, str] | None = None,
    ) -> str | None:
        """Show ownership counts for an organization without deleting.

        A dry run is not a removal boundary: it rehearses the refusal stage
        and performs no removal, so it discharges the refusal obligations it
        honors without claiming the destructive ones.
        """
        try:
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
                    coordinator.discharge_stage(RemovalAction.REFUSE)
                    ownership_map = self._build_ownership_map(organization)
                finally:
                    reset_current_org_id()
        except Organization.DoesNotExist:
            self._check_tombstone(
                org_id,
                heal_social_cache=False,
                coordinator=coordinator,
            )
            raise CommandError(
                f"No organization found with UUID {org_id}. "
                "No tombstone exists for this UUID either."
            )

        self._print_ownership_summary(organization, ownership_map)
        self.stdout.write(
            self.style.WARNING(
                "Dry run — no changes were made. "
                "Re-run without --dry-run to execute the purge."
            )
        )
        return None

    # ------------------------------------------------------------------
    # Destructive purge by UUID
    # ------------------------------------------------------------------

    def _purge_by_uuid(
        self,
        org_id: uuid.UUID,
        *,
        coordinator: RemovalCoordinator,
    ) -> str | None:
        """Irrevocably delete the organization and all owned rows.

        The boundary discharges every discovered obligation through one
        coordinator and calls ``finish`` after the last one, so an obligation
        this boundary never performed fails the purge instead of passing
        silently.
        """
        ownership_map: dict[str, int] = {}
        try:
            with transaction.atomic():
                # This row is the per-organization billing mutation mutex.
                # Lock it before checking provider state and keep the lock
                # through deletion so a concurrent billing writer either
                # commits first and is observed or waits and then fails closed.
                organization = self._lock_organization(org_id)
                self._guard_reserved_org(organization)

                # Establish consistent org context for RLS-protected tables
                # BEFORE checking, counting, or deleting. Under PostgreSQL
                # FORCE-RLS the runtime role cannot see rows without
                # app.current_org_id set.
                set_current_org_for_context(org_id=organization.pk)
                try:
                    self._guard_boundary_provider_state(organization)
                    self._guard_provider_backed_fields(organization)
                    coordinator.discharge_stage(RemovalAction.REFUSE)

                    # Build the map inside the atomic block so counts match
                    # the pre-delete snapshot with org context already active.
                    ownership_map = self._build_ownership_map(organization)

                    # Cross-module owned rows (FK-safe delete order).
                    self._delete_owned_rows(organization)
                    coordinator.discharge_stage(RemovalAction.DELETE)

                    # Org-level rows — use _raw_delete to bypass model delete()
                    # and signal receivers (notably the SA70 pre_delete backstop
                    # on OrganizationMembership). The purge is intentionally
                    # destroying the org and all its rows; individual row-level
                    # protections are irrelevant here.
                    OrganizationInvitation.objects.filter(
                        organization=organization
                    )._raw_delete(OrganizationInvitation.objects.db)
                    OrganizationMembership.objects.filter(
                        organization=organization
                    )._raw_delete(OrganizationMembership.objects.db)

                    # All known FK-referencing rows are already deleted, so
                    # bypass Django's cascade collector for the org row too.
                    Organization.objects.filter(pk=organization.pk)._raw_delete(
                        Organization.objects.db
                    )

                    OrganizationTombstone.objects.create(
                        organization_id=org_id,
                    )
                    coordinator.discharge_stage(RemovalAction.RECORD)
                finally:
                    reset_current_org_id()
        except Organization.DoesNotExist:
            self._check_tombstone(
                org_id,
                heal_social_cache=True,
                coordinator=coordinator,
            )
            raise CommandError(
                f"No organization found with UUID {org_id}. "
                "No tombstone exists for this UUID either."
            )

        # Cache backends may be remote. Keep this network effect outside the
        # database transaction; a tombstone retry heals any failure here.
        self._invalidate_organization_caches(organization.pk, coordinator=coordinator)
        coordinator.finish()
        self._print_purge_summary(organization, ownership_map)
        return None

    # ------------------------------------------------------------------
    # Shared ownership map (single source of truth for counts)
    # ------------------------------------------------------------------

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

    def _build_ownership_map(self, organization: Organization) -> dict[str, int]:
        """Build a single source-of-truth count map for *organization*.

        Returns a ``{label: count}`` dict.  Both dry-run and destructive
        paths use this so counts cannot drift.
        """
        counts: dict[str, int] = {}

        # Cross-module counts.
        for entry in _resolve_models():
            model = entry["model"]
            label = str(entry["label"])
            filter_kwargs = _get_filter_for_org(str(entry["filter_key"]), organization)
            qs = _get_qs(model, filter_kwargs)
            counts[label] = qs.count()

        # Org-level counts.
        counts["Organization invitations"] = OrganizationInvitation.objects.filter(
            organization=organization
        ).count()
        counts["Organization memberships"] = OrganizationMembership.objects.filter(
            organization=organization
        ).count()

        return counts

    def _delete_owned_rows(self, organization: Organization) -> None:
        """Delete all cross-module owned rows for *organization*.

        Uses the FK-derived ``_resolve_models()`` plan. Complex relationships
        are handled by deleting children before the parents they reference.
        Nullable self-blocking links are detached inside the purge transaction
        so Django's collector cannot reject references that disappear together.
        """
        for entry in _resolve_models():
            model = entry["model"]
            label = str(entry["label"])
            filter_kwargs = _get_filter_for_org(str(entry["filter_key"]), organization)
            qs = _get_qs(model, filter_kwargs)
            self_blocking_fields = _self_blocking_foreign_keys(model)
            non_nullable_fields = [
                field.name for field in self_blocking_fields if not field.null
            ]
            if non_nullable_fields:
                raise CommandError(
                    "Organization purge cannot safely detach non-nullable "
                    f"self-blocking fields on {_model_key(model)}: "
                    f"{', '.join(sorted(non_nullable_fields))}."
                )
            if self_blocking_fields:
                qs.update(**{field.attname: None for field in self_blocking_fields})
            deleted_count, _ = qs.delete()
            if deleted_count:
                self.stdout.write(f"  Deleted {deleted_count} {label.lower()}.")

    def _invalidate_organization_caches(
        self,
        org_id: uuid.UUID,
        *,
        coordinator: RemovalCoordinator,
    ) -> None:
        """Run every installed app's declared cache invalidation hook.

        The ``INVALIDATE`` stage's executor is the declaring app's
        ``invalidate_organization_cache`` hook, so the stage is discharged only
        after each installed app's own invalidation has run.  This method stays
        on the command module so the rule 34 boundary check follows the
        INVALIDATE discharge on ``Command.handle``'s entry path.
        """
        for app_config in sorted(
            apps.get_app_configs(), key=lambda config: config.label
        ):
            hook = getattr(app_config, "invalidate_organization_cache", None)
            if callable(hook):
                hook(org_id)
        coordinator.discharge_stage(RemovalAction.INVALIDATE)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _require_dischargeable_obligations(
        self,
        coordinator: RemovalCoordinator,
    ) -> None:
        """Refuse before any destructive work when a declaration has no stage.

        The completeness guard runs after the purge transaction commits (cache
        invalidation is a post-commit effect), so a declaration the purge has
        no stage for is rejected here instead, before anything is deleted.
        """
        undischargeable = coordinator.undischargeable()
        if undischargeable:
            names = ", ".join(obligation.name for obligation in undischargeable)
            raise CommandError(
                "Organization-removal obligations declare actions the purge "
                f"boundary has no stage for: {names}. Nothing was deleted."
            )

    def _guard_provider_reconciliation_target(self, org_id: object) -> None:
        """Apply non-mutating command guards before any provider request."""
        _resolve_models()
        organization = Organization.objects.filter(pk=org_id).first()
        if organization is not None:
            self._guard_reserved_org(organization)

    def _declared_boundary_guards(self) -> tuple[DeclaredBoundaryGuard, ...]:
        """Return the declared boundary guards, refusing an unreadable declaration."""
        try:
            return declared_boundary_guards()
        except (TypeError, ValueError, RuntimeError) as exc:
            raise CommandError(
                f"Could not read the declared provider-state guards: {exc}. "
                "Purge was refused."
            ) from exc

    def _reconcile_provider_states(
        self,
        org_id: object,
        *,
        persist: bool,
    ) -> dict[str, str]:
        """Run every declared provider-state hook before the purge transaction.

        Each declaring app owns the pre-transaction reconciliation its
        boundary-guarded obligation names.  The returned map carries the
        provider-confirmed expired checkout id per obligation, so the refusal
        guard does not read a checkout the reconciliation certified as pending.
        """
        expired_checkouts: dict[str, str] = {}
        for declared in self._declared_boundary_guards():
            if declared.reconcile is None:
                continue
            try:
                result = declared.reconcile(org_id, persist=persist)
            except Exception as exc:
                raise CommandError(
                    "Could not establish terminal provider state before "
                    f"organization removal: {exc}"
                ) from exc
            expired_checkouts[declared.obligation.name] = str(result or "").strip()
        return expired_checkouts

    def _provider_mutation_lock(self, org_id: object) -> Any:
        """Hold every declared provider mutex through reconciliation and purge.

        Every lock acquired before an acquisition failure is released before
        the error propagates — declared, unexpected, or an interrupt.  If
        releasing an acquired lock also fails, its failure is logged and the
        acquisition failure is the one that propagates.
        """
        lock_factories = [
            declared.mutation_lock
            for declared in self._declared_boundary_guards()
            if declared.mutation_lock is not None
        ]
        if not lock_factories:
            return nullcontext()
        stack = ExitStack()
        try:
            for lock_factory in lock_factories:
                stack.enter_context(lock_factory(org_id))
        except BaseException:
            try:
                stack.close()
            except BaseException:
                logger.exception(
                    "Provider-lock cleanup failed after an acquisition failure; "
                    "re-raising the acquisition failure."
                )
            raise
        return stack

    def _lock_organization(self, org_id: object) -> Organization:
        """Acquire the organization-first mutex shared with billing writers."""
        return Organization.objects.select_for_update().get(pk=org_id)

    def _guard_boundary_provider_state(
        self,
        organization: Organization,
        *,
        provider_expired_checkouts: dict[str, str] | None = None,
    ) -> None:
        """Run every declared boundary guard and refuse with its own reason.

        The caller holds the organization row lock and has established the
        RLS context for the surrounding transaction, so each declaring app's
        guard observes the state the purge is about to remove.
        """
        expired_checkouts = provider_expired_checkouts or {}
        for declared in self._declared_boundary_guards():
            try:
                reason = declared.guard(
                    organization,
                    provider_expired_checkout_id=expired_checkouts.get(
                        declared.obligation.name, ""
                    ),
                )
            except CommandError:
                raise
            except Exception as exc:
                raise CommandError(
                    "Could not verify provider state before organization "
                    f"removal: {exc}"
                ) from exc
            if str(reason or "").strip():
                raise CommandError(str(reason))

    def _model_field_carries_provider_value(
        self,
        model: type[models.Model],
        field_name: str,
        organization: Organization,
    ) -> bool:
        """Return whether one model-classified provider-backed field holds a value."""
        if not has_organization_id_field(model):
            return False
        try:
            field = cast(models.Field, model._meta.get_field(field_name))
        except FieldDoesNotExist as exc:
            raise CommandError(
                f"Cannot purge organization {organization.pk}: "
                f"{_model_key(model)}.{field_name} is declared "
                "provider-backed but is not a model field."
            ) from exc
        queryset = _get_qs(model, {"organization_id": organization.pk})
        locked_rows = list(
            queryset.select_for_update().only(field_name)  # type: ignore[attr-defined]
        )
        return any(
            _carries_provider_value(field, getattr(row, field_name))
            for row in locked_rows
        )

    def _guard_provider_backed_fields(self, organization: Organization) -> None:
        """Refuse a purge while a row carries provider-backed state (SA208/SA213).

        Project-owned models classify their non-relational ``*_id`` fields in
        ``provider_id_classification``.  A field classified provider-backed
        that holds a value is provider state the purge cannot reconcile, so
        the purge refuses and names every such field.  An obligation may also
        declare its own provider fields (SA213); unless the declaring module
        marks a field boundary-guarded, the same refusal applies to it, so a
        project app's declaration is enforced without bespoke boundary code.

        The caller holds the organization row lock and has established the RLS
        context for the surrounding transaction.  Every existing row of the
        organization in each declared model is locked for the rest of the
        purge transaction, so a concurrent update cannot add a provider value
        after this read and before deletion.  A row inserted concurrently is
        not covered by those row locks and is deleted with the organization.
        """
        try:
            declared_fields = declared_provider_backed_fields(get_tenant_models())
            refusal_fields = declared_refusal_fields(RemovalBoundary.PURGE)
            obligations = organization_removal_obligations()
        except (TypeError, ValueError, RuntimeError) as exc:
            raise CommandError(
                f"Cannot purge organization {organization.pk}: {exc}"
            ) from exc

        self._validate_declared_field_labels(obligations, organization)

        carried_fields = [
            f"{_model_key(model)}.{field_name}"
            for model, field_name in declared_fields
            if self._model_field_carries_provider_value(model, field_name, organization)
        ]
        carried_fields.extend(
            self._carried_declared_refusal_fields(organization, refusal_fields)
        )

        if carried_fields:
            joined_fields = ", ".join(sorted(carried_fields))
            raise CommandError(
                f"Cannot purge organization {organization.pk} while rows carry "
                f"provider-backed values: {joined_fields}. Clear or reconcile "
                "these fields before retrying."
            )

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
