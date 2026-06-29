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
* Ownership/count map always includes ``OrganizationInvitation`` rows.
* Tombstone is created in the same transaction as the purge.
* Cross-module owned rows (social, forms, listings, blog, crm, billing) are
  deleted in FK-safe order.  Modules not installed in the current environment
  are skipped gracefully.
* The shared ``set_current_org_for_context()`` helper establishes consistent
  ContextVar + ``SET LOCAL app.current_org_id`` before touching RLS-protected
  tables.
"""

from __future__ import annotations

import uuid

from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

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
from quickscale_modules_orgs.operator_access import operator_access

# ---------------------------------------------------------------------------
# Cross-module delete registry
#
# Each entry is a dict:
#   app_label  - Django app label
#   model_name - Model class name
#   filter     - Query filter kwargs (e.g. {"organization": org} or
#                {"form__organization": org} for descendant models)
#   label      - Human-readable label for output
#
# Models that PROTECT the org FK must be deleted before the org row.
# Models that PROTECT a parent FK (e.g. FormSubmission → Form) must be
# deleted before their parent.
#
# Priority within a module is determined by entry order: models listed
# first are deleted first.
# ---------------------------------------------------------------------------

_DELETE_SPECS: list[dict[str, object]] = [
    # -- social (all have direct organization FK, PROTECT) --
    {
        "app_label": "quickscale_modules_social",
        "model_name": "SocialLink",
        "filter_key": "organization",
        "label": "Social links",
    },
    {
        "app_label": "quickscale_modules_social",
        "model_name": "SocialEmbed",
        "filter_key": "organization",
        "label": "Social embeds",
    },
    # -- forms --
    # FormFieldValue has org FK (PROTECT) and submission FK (CASCADE);
    # must delete before FormSubmission.
    {
        "app_label": "quickscale_modules_forms",
        "model_name": "FormFieldValue",
        "filter_key": "organization",
        "label": "Form field values",
    },
    # FormField has org FK (PROTECT); must delete before Form.
    {
        "app_label": "quickscale_modules_forms",
        "model_name": "FormField",
        "filter_key": "organization",
        "label": "Form fields",
    },
    # FormSubmission has org FK (PROTECT) and form FK (PROTECT);
    # must delete before Form.
    {
        "app_label": "quickscale_modules_forms",
        "model_name": "FormSubmission",
        "filter_key": "organization",
        "label": "Form submissions",
    },
    # Form has org FK (PROTECT).
    {
        "app_label": "quickscale_modules_forms",
        "model_name": "Form",
        "filter_key": "organization",
        "label": "Forms",
    },
    # -- listings (direct org FK, PROTECT) --
    {
        "app_label": "quickscale_modules_listings",
        "model_name": "Listing",
        "filter_key": "organization",
        "label": "Listings",
    },
    # -- blog (all direct org FK, PROTECT) --
    {
        "app_label": "quickscale_modules_blog",
        "model_name": "Post",
        "filter_key": "organization",
        "label": "Blog posts",
    },
    {
        "app_label": "quickscale_modules_blog",
        "model_name": "Category",
        "filter_key": "organization",
        "label": "Blog categories",
    },
    {
        "app_label": "quickscale_modules_blog",
        "model_name": "Tag",
        "filter_key": "organization",
        "label": "Blog tags",
    },
    {
        "app_label": "quickscale_modules_blog",
        "model_name": "BlogMediaAsset",
        "filter_key": "organization",
        "label": "Blog media assets",
    },
    # -- crm --
    # DealNote has direct org FK (PROTECT); delete before Deal because
    # Deal CASCADE would also remove DealNote.
    {
        "app_label": "quickscale_modules_crm",
        "model_name": "DealNote",
        "filter_key": "organization",
        "label": "CRM deal notes",
    },
    # ContactNote has direct org FK (PROTECT); delete before Contact because
    # Contact CASCADE would also remove ContactNote.
    {
        "app_label": "quickscale_modules_crm",
        "model_name": "ContactNote",
        "filter_key": "organization",
        "label": "CRM contact notes",
    },
    # Deal has org FK (PROTECT); must delete before Stage (PROTECT on deal FK).
    {
        "app_label": "quickscale_modules_crm",
        "model_name": "Deal",
        "filter_key": "organization",
        "label": "CRM deals",
    },
    # Contact has org FK (PROTECT) and company FK (CASCADE).
    {
        "app_label": "quickscale_modules_crm",
        "model_name": "Contact",
        "filter_key": "organization",
        "label": "CRM contacts",
    },
    # Company has org FK (PROTECT).
    {
        "app_label": "quickscale_modules_crm",
        "model_name": "Company",
        "filter_key": "organization",
        "label": "CRM companies",
    },
    # Stage has org FK (PROTECT); no remaining deals reference it.
    {
        "app_label": "quickscale_modules_crm",
        "model_name": "Stage",
        "filter_key": "organization",
        "label": "CRM stages",
    },
    # Tag has org FK (PROTECT).
    {
        "app_label": "quickscale_modules_crm",
        "model_name": "Tag",
        "filter_key": "organization",
        "label": "CRM tags",
    },
    # -- billing (all have direct org FK via tenant_org_fk, PROTECT) --
    {
        "app_label": "quickscale_modules_billing",
        "model_name": "CreditTransaction",
        "filter_key": "organization",
        "label": "Credit transactions",
    },
    {
        "app_label": "quickscale_modules_billing",
        "model_name": "Subscription",
        "filter_key": "organization",
        "label": "Subscriptions",
    },
    {
        "app_label": "quickscale_modules_billing",
        "model_name": "CreditBalance",
        "filter_key": "organization",
        "label": "Credit balances",
    },
]


def _resolve_models() -> list[dict[str, object]]:
    """Resolve cross-module model classes, skipping uninstalled apps.

    Returns a list of dicts with keys ``model`` (the resolved model class
    or ``None``), ``filter_key``, and ``label``.
    """
    resolved: list[dict[str, object]] = []
    for spec in _DELETE_SPECS:
        try:
            model = apps.get_model(
                str(spec["app_label"]),
                str(spec["model_name"]),
            )
        except LookupError:
            model = None
        resolved.append(
            {
                "model": model,
                "filter_key": spec["filter_key"],
                "label": spec["label"],
            }
        )
    return resolved


def _get_filter_for_org(
    filter_key: str, organization: Organization
) -> dict[str, object]:
    """Build a filter dict for a given filter_key and organization."""
    return {filter_key: organization}


def _get_qs(model: object, filter_kwargs: dict[str, object]) -> object:
    """Get a QuerySet for *model* filtered by *filter_kwargs*.

    The caller MUST have established org context (via
    ``set_current_org_for_context`` or ``org_scope``) before calling this
    function.  The default ``objects`` manager (``TenantManager``) scopes
    to that org automatically — no direct ``all_objects`` bypass is needed.

    Fails closed if the model does not expose a standard ``objects``
    manager — a bare ``AttributeError`` means the model cannot participate
    in org-scoped queries through this path.
    """
    try:
        return model.objects.filter(**filter_kwargs)  # type: ignore[union-attr]
    except AttributeError:
        raise TypeError(
            f"Model {model!r} does not expose a standard 'objects' manager. "
            "All delete-spec models must support operator-scoped queries "
            "through the default manager."
        ) from None


class Command(BaseCommand):
    help = (
        "Purge an organization and all owned rows across all modules. "
        "Use --organization-id <uuid> for destructive execution; "
        "--slug <slug> for non-destructive preflight only."
    )

    def add_arguments(self, parser) -> None:
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

    def handle(self, *args: object, **options: object) -> str | None:
        del args
        raw_org_id: str | None = options.get("organization_id")
        slug: str | None = options.get("slug")
        dry_run: bool = options.get("dry_run", False)
        self._force: bool = options.get("force", False)

        # ------------------------------------------------------------------
        # Resolve targeting mode
        # ------------------------------------------------------------------
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

        # ------------------------------------------------------------------
        # Slug mode — non-destructive preflight only
        # ------------------------------------------------------------------
        if slug:
            return self._preflight_by_slug(slug.strip())

        # ------------------------------------------------------------------
        # Organization ID mode — parse UUID and dispatch
        # ------------------------------------------------------------------
        assert raw_org_id is not None
        try:
            org_id = uuid.UUID(raw_org_id.strip())
        except (ValueError, AttributeError):
            raise CommandError(
                f"Invalid --organization-id value: {raw_org_id!r}. "
                "Must be a valid UUID."
            )

        if dry_run:
            return self._dry_run_by_uuid(org_id)
        return self._purge_by_uuid(org_id)

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

    # ------------------------------------------------------------------
    # Dry run by UUID
    # ------------------------------------------------------------------

    def _dry_run_by_uuid(self, org_id: uuid.UUID) -> str | None:
        """Show ownership counts for an organization without deleting."""
        try:
            organization = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist:
            self._check_tombstone(org_id)
            raise CommandError(
                f"No organization found with UUID {org_id}. "
                "No tombstone exists for this UUID either."
            )

        self._guard_reserved_org(organization)
        self._print_ownership_summary(
            organization, self._build_ownership_map_guarded(organization)
        )
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

    def _purge_by_uuid(self, org_id: uuid.UUID) -> str | None:
        """Irrevocably delete the organization and all owned rows."""
        try:
            organization = Organization.objects.get(pk=org_id)
        except Organization.DoesNotExist:
            self._check_tombstone(org_id)
            raise CommandError(
                f"No organization found with UUID {org_id}. "
                "No tombstone exists for this UUID either."
            )

        self._guard_reserved_org(organization)

        ownership_map: dict[str, int] = {}
        with operator_access(reason="purge_organization destructive purge") as ctx:
            # Set audit fields early so failure-path tests can assert
            # them even when the operation fails.
            ctx.command = "purge_organization"
            ctx.target_scope = "single_org"
            ctx.target_org_ids = [str(org_id)]
            ctx.touched_org_ids = [str(org_id)]
            ctx.actor_identifier = "cli:purge_organization"

            with transaction.atomic():
                # Establish consistent org context for RLS-protected tables
                # BEFORE counting or deleting.  Under PostgreSQL FORCE-RLS
                # the runtime role cannot see rows without app.current_org_id
                # set.
                set_current_org_for_context(org_id=organization.pk)
                try:
                    # Build the map inside the atomic block so counts match
                    # the pre-delete snapshot with org context already active.
                    ownership_map = self._build_ownership_map(organization)

                    # Cross-module owned rows (FK-safe delete order).
                    self._delete_owned_rows(organization)

                    # Org-level rows.
                    OrganizationInvitation.objects.filter(
                        organization=organization
                    ).delete()
                    OrganizationMembership.objects.filter(
                        organization=organization
                    ).delete()

                    # Org row — use _raw_delete to bypass Django's cascade
                    # collector, which queries all FK-referencing model tables
                    # (including test-only models whose backing tables may not
                    # exist).  All known FK-referencing rows are already deleted.
                    Organization.objects.filter(pk=organization.pk)._raw_delete(
                        Organization.objects.db
                    )

                    OrganizationTombstone.objects.create(
                        organization_id=org_id,
                    )
                finally:
                    reset_current_org_id()

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
            if model is None:
                continue
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

        Uses the priority-ordered ``_resolve_models()`` list.  Models whose
        app is not installed are skipped.  Complex cascades (forms, crm) are
        handled by deleting parent rows before children that PROTECT them.
        """
        for entry in _resolve_models():
            model = entry["model"]
            label = str(entry["label"])
            if model is None:
                continue
            filter_kwargs = _get_filter_for_org(str(entry["filter_key"]), organization)
            qs = _get_qs(model, filter_kwargs)
            deleted_count, _ = qs.delete()
            if deleted_count:
                self.stdout.write(f"  Deleted {deleted_count} {label.lower()}.")

        # Clear social cache entries for the purged org.  QuerySet.delete()
        # bypasses BaseSocialItem.delete() which normally invalidates
        # org-partitioned cache keys (CR-T117-R2).
        if apps.is_installed("quickscale_modules_social"):
            self._clear_social_cache(organization.pk)

    def _clear_social_cache(self, org_id: uuid.UUID) -> None:
        """Invalidate social cache keys for a purged organization.

        Called after social rows are deleted via queryset.  The queryset
        delete bypasses ``BaseSocialItem.delete()`` which would normally
        clear ``SOCIAL_LINKS_CACHE_KEY`` and ``SOCIAL_EMBEDS_CACHE_KEY``
        plus their ``:org:{org_id}`` variants.
        """
        from django.core.cache import cache

        from quickscale_modules_social.contracts import (
            SOCIAL_EMBEDS_CACHE_KEY,
            SOCIAL_LINKS_CACHE_KEY,
        )

        cache.delete_many(
            [
                SOCIAL_LINKS_CACHE_KEY,
                f"{SOCIAL_LINKS_CACHE_KEY}:org:{org_id}",
                SOCIAL_EMBEDS_CACHE_KEY,
                f"{SOCIAL_EMBEDS_CACHE_KEY}:org:{org_id}",
            ]
        )

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _check_tombstone(self, org_id: uuid.UUID) -> None:
        """Check for a tombstone when the org does not exist."""
        try:
            tombstone = OrganizationTombstone.objects.get(organization_id=org_id)
        except OrganizationTombstone.DoesNotExist:
            return

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
