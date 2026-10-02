"""Shared non-boundary command helpers for the organization purge command.

The command module keeps ``Command.handle``, ``_purge_by_uuid``,
``_dry_run_by_uuid``, ``_resolve_models``, ``_model_label``, and the
provider-state guard methods whose call sites resolve test patch seams through
the command module; the preflight, tombstone, reserved-org guard, ownership
printing, and cache-invalidation helpers live here so the command file stays
inside the file-length contract (Module Conventions rule 28).
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from django.apps import apps
from django.core.management.base import CommandError

from quickscale_modules_orgs.models import Organization, OrganizationTombstone
from quickscale_modules_orgs.removal import RemovalCoordinator


class _PurgeSupportMixin:
    """Non-boundary purge command helpers shared through the command class."""

    _force: bool
    stdout: Any
    style: Any

    if TYPE_CHECKING:

        def _build_ownership_map_guarded(
            self, organization: Organization
        ) -> dict[str, int]: ...

        def _invalidate_organization_caches(
            self,
            org_id: uuid.UUID,
            *,
            coordinator: RemovalCoordinator,
        ) -> None: ...

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
