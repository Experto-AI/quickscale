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
"""

from __future__ import annotations

import uuid
from collections import Counter
from contextlib import nullcontext
from heapq import heappop, heappush

from django.apps import apps
from django.core.exceptions import FieldDoesNotExist
from django.core.management.base import BaseCommand, CommandError
from django.db import models, transaction

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
    BILLING_PROVIDER_STATE,
    OWNED_TENANT_ROWS,
    PURGE_TOMBSTONE,
    SOCIAL_CACHE_STATE,
    RemovalAction,
    RemovalBoundary,
    declared_provider_backed_fields,
    require_removal_action,
)
from quickscale_modules_orgs.tenancy import (
    get_tenant_models,
    has_organization_id_field,
)

# Additional child-before-parent constraints belong here only when installed FK
# metadata cannot represent them. Each pair is ``(before_label, after_label)``.
_PURGE_ORDER_OVERRIDES: tuple[tuple[str, str], ...] = ()

_LABEL_PREFIXES = {
    "quickscale_modules_blog": "Blog",
    "quickscale_modules_crm": "CRM",
}


def _model_key(model: type[models.Model]) -> str:
    return model._meta.label_lower


def _self_blocking_foreign_keys(
    model: type[models.Model],
) -> tuple[models.ForeignKey, ...]:
    """Return self-FKs that Django's collector would treat as blockers."""
    return tuple(
        field
        for field in model._meta.fields
        if isinstance(field, models.ForeignKey)
        and field.remote_field.model is model
        and field.remote_field.on_delete
        in {
            models.DO_NOTHING,
            models.PROTECT,
            models.RESTRICT,
        }
    )


def _topologically_order_models(
    tenant_models: list[type[models.Model]],
    order_overrides: tuple[tuple[str, str], ...] = _PURGE_ORDER_OVERRIDES,
) -> list[type[models.Model]]:
    """Order models before every deletion that could collect or block them."""
    models_by_key = {_model_key(model): model for model in tenant_models}
    outgoing: dict[str, set[str]] = {key: set() for key in models_by_key}
    incoming_count = dict.fromkeys(models_by_key, 0)
    hard_orderings: set[tuple[str, str]] = set()

    def add_ordering(before: str, after: str) -> None:
        if before == after:
            return
        if before not in models_by_key or after not in models_by_key:
            raise CommandError(
                "Organization purge order references an unknown model: "
                f"{before} -> {after}."
            )
        if after not in outgoing[before]:
            outgoing[before].add(after)
            incoming_count[after] += 1

    for model in tenant_models:
        child_key = _model_key(model)
        for field in model._meta.fields:
            if not isinstance(field, models.ForeignKey):
                continue
            parent_key = _model_key(field.remote_field.model)
            if parent_key not in models_by_key or parent_key == child_key:
                continue
            if field.remote_field.on_delete is models.CASCADE:
                hard_orderings.add((child_key, parent_key))
            elif field.remote_field.on_delete in {
                models.DO_NOTHING,
                models.PROTECT,
                models.RESTRICT,
            }:
                hard_orderings.add((child_key, parent_key))

    for before, after in order_overrides:
        normalized_ordering = (before.lower(), after.lower())
        if any(key not in models_by_key for key in normalized_ordering):
            raise CommandError(
                "Organization purge order override references an unknown model: "
                f"{normalized_ordering[0]} -> {normalized_ordering[1]}."
            )
        hard_orderings.add(normalized_ordering)

    for before, after in sorted(hard_orderings):
        add_ordering(before, after)

    ready: list[str] = []
    for key, count in incoming_count.items():
        if count == 0:
            heappush(ready, key)

    ordered_keys: list[str] = []
    while ready:
        key = heappop(ready)
        ordered_keys.append(key)
        for dependent in sorted(outgoing[key]):
            incoming_count[dependent] -= 1
            if incoming_count[dependent] == 0:
                heappush(ready, dependent)

    if len(ordered_keys) != len(models_by_key):
        cyclic = sorted(key for key, count in incoming_count.items() if count)
        raise CommandError(
            "Cannot derive an FK-safe organization purge order; resolve the "
            f"blocking cycle involving: {', '.join(cyclic)}"
        )
    return [models_by_key[key] for key in ordered_keys]


def _model_label(model: type[models.Model]) -> str:
    plural = str(model._meta.verbose_name_plural)
    prefix = _LABEL_PREFIXES.get(model._meta.app_label)
    if prefix:
        return f"{prefix} {plural[:1].lower()}{plural[1:]}"
    return f"{plural[:1].upper()}{plural[1:]}"


def _disambiguated_model_labels(
    tenant_models: list[type[models.Model]],
) -> list[str]:
    """Keep legacy labels when unique and qualify project label collisions."""
    base_labels = [_model_label(model) for model in tenant_models]
    label_counts = Counter(base_labels)
    return [
        label if label_counts[label] == 1 else f"{label} ({_model_key(model)})"
        for model, label in zip(tenant_models, base_labels, strict=True)
    ]


def _resolve_models() -> list[dict[str, object]]:
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


def _get_filter_for_org(
    filter_key: str, organization: Organization
) -> dict[str, object]:
    """Build a filter dict for a given filter_key and organization."""
    value: object = organization.pk if filter_key.endswith("_id") else organization
    return {filter_key: value}


def _get_qs(model: object, filter_kwargs: dict[str, object]) -> object:
    """Get a QuerySet for *model* filtered by *filter_kwargs*.

    Tries ``all_objects`` first (TenantManager super-scope bypass), then
    falls back to the default ``objects`` manager.
    """
    try:
        return model.all_objects.filter(**filter_kwargs)  # type: ignore[union-attr]
    except AttributeError:
        return model.objects.filter(**filter_kwargs)  # type: ignore[union-attr]


def _carries_provider_value(field: models.Field, value: object) -> bool:
    """Return whether *value* is set rather than an empty provider slot."""
    if value is None:
        return False
    if isinstance(field, (models.CharField, models.TextField)) and value == "":
        return False
    return True


class Command(BaseCommand):
    help = (
        "Purge an organization and all owned rows across all modules. "
        "Current Stripe-backed subscriptions must be cancelled and pending "
        "hosted checkouts must be completed or expired first. "
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
        assert raw_org_id is not None  # noqa: S101 - internal invariant guaranteed by the caller
        try:
            org_id = uuid.UUID(raw_org_id.strip())
        except ValueError, AttributeError:
            raise CommandError(
                f"Invalid --organization-id value: {raw_org_id!r}. "
                "Must be a valid UUID."
            )

        self._guard_provider_reconciliation_target(org_id)
        with self._billing_provider_mutation_lock(org_id):
            if dry_run:
                provider_expired_checkout_id = self._reconcile_billing_provider_state(
                    org_id,
                    persist=False,
                )
                return self._dry_run_by_uuid(
                    org_id,
                    provider_expired_checkout_id=provider_expired_checkout_id,
                )
            self._reconcile_billing_provider_state(org_id, persist=True)
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

    def _dry_run_by_uuid(
        self,
        org_id: uuid.UUID,
        *,
        provider_expired_checkout_id: str = "",
    ) -> str | None:
        """Show ownership counts for an organization without deleting."""
        try:
            with transaction.atomic():
                organization = self._lock_organization(org_id)
                self._guard_reserved_org(organization)
                require_removal_action(
                    BILLING_PROVIDER_STATE,
                    boundary=RemovalBoundary.PURGE,
                    action=RemovalAction.REFUSE,
                )
                set_current_org_for_context(org_id=organization.pk)
                try:
                    self._guard_live_stripe_subscriptions(
                        organization,
                        provider_expired_checkout_id=provider_expired_checkout_id,
                    )
                    self._guard_provider_backed_fields(organization)
                    ownership_map = self._build_ownership_map(organization)
                finally:
                    reset_current_org_id()
        except Organization.DoesNotExist:
            self._check_tombstone(org_id, heal_social_cache=False)
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

    def _purge_by_uuid(self, org_id: uuid.UUID) -> str | None:
        """Irrevocably delete the organization and all owned rows."""
        ownership_map: dict[str, int] = {}
        try:
            with transaction.atomic():
                # This row is the per-organization billing mutation mutex.
                # Lock it before checking provider state and keep the lock
                # through deletion so a concurrent billing writer either
                # commits first and is observed or waits and then fails closed.
                organization = self._lock_organization(org_id)
                self._guard_reserved_org(organization)
                require_removal_action(
                    BILLING_PROVIDER_STATE,
                    boundary=RemovalBoundary.PURGE,
                    action=RemovalAction.REFUSE,
                )

                # Establish consistent org context for RLS-protected tables
                # BEFORE checking, counting, or deleting. Under PostgreSQL
                # FORCE-RLS the runtime role cannot see rows without
                # app.current_org_id set.
                set_current_org_for_context(org_id=organization.pk)
                try:
                    self._guard_live_stripe_subscriptions(organization)
                    self._guard_provider_backed_fields(organization)

                    # Build the map inside the atomic block so counts match
                    # the pre-delete snapshot with org context already active.
                    ownership_map = self._build_ownership_map(organization)

                    # Cross-module owned rows (FK-safe delete order).
                    require_removal_action(
                        OWNED_TENANT_ROWS,
                        boundary=RemovalBoundary.PURGE,
                        action=RemovalAction.DELETE,
                    )
                    self._delete_owned_rows(organization)

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

                    require_removal_action(
                        PURGE_TOMBSTONE,
                        boundary=RemovalBoundary.PURGE,
                        action=RemovalAction.RECORD,
                    )
                    OrganizationTombstone.objects.create(
                        organization_id=org_id,
                    )
                finally:
                    reset_current_org_id()
        except Organization.DoesNotExist:
            self._check_tombstone(org_id, heal_social_cache=True)
            raise CommandError(
                f"No organization found with UUID {org_id}. "
                "No tombstone exists for this UUID either."
            )

        # Cache backends may be remote. Keep this network effect outside the
        # database transaction; a tombstone retry heals any failure here.
        self._invalidate_social_cache(organization.pk)
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

    def _invalidate_social_cache(self, org_id: uuid.UUID) -> None:
        """Run the declared social-cache obligation outside DB transactions."""
        require_removal_action(
            SOCIAL_CACHE_STATE,
            boundary=RemovalBoundary.PURGE,
            action=RemovalAction.INVALIDATE,
        )
        if apps.is_installed("quickscale_modules_social"):
            self._clear_social_cache(org_id)

    # ------------------------------------------------------------------
    # Shared helpers
    # ------------------------------------------------------------------

    def _guard_provider_reconciliation_target(self, org_id: object) -> None:
        """Apply non-mutating command guards before any provider request."""
        _resolve_models()
        organization = Organization.objects.filter(pk=org_id).first()
        if organization is not None:
            self._guard_reserved_org(organization)

    def _reconcile_billing_provider_state(
        self,
        org_id: object,
        *,
        persist: bool,
    ) -> str:
        """Run billing's provider adapter before opening the purge transaction."""
        if not apps.is_installed("quickscale_modules_billing"):
            return ""
        app_config = apps.get_app_config("quickscale_modules_billing")
        reconcile = getattr(
            app_config,
            "reconcile_organization_removal_provider_state",
            None,
        )
        if not callable(reconcile):
            raise CommandError(
                "Billing is installed without its organization-removal provider "
                "adapter; purge was refused."
            )
        try:
            return str(reconcile(org_id, persist=persist) or "").strip()
        except Exception as exc:
            raise CommandError(
                "Could not establish terminal Stripe checkout state before "
                f"organization removal: {exc}"
            ) from exc

    def _billing_provider_mutation_lock(self, org_id: object):
        """Hold billing's provider mutex through reconciliation and purge."""
        if not apps.is_installed("quickscale_modules_billing"):
            return nullcontext()
        app_config = apps.get_app_config("quickscale_modules_billing")
        lock_factory = getattr(
            app_config,
            "organization_removal_provider_mutation_lock",
            None,
        )
        if not callable(lock_factory):
            raise CommandError(
                "Billing is installed without its organization-removal provider "
                "mutex; purge was refused."
            )
        return lock_factory(org_id)

    def _lock_organization(self, org_id: object) -> Organization:
        """Acquire the organization-first mutex shared with billing writers."""
        return Organization.objects.select_for_update().get(pk=org_id)

    def _guard_live_stripe_subscriptions(
        self,
        organization: Organization,
        *,
        provider_expired_checkout_id: str = "",
    ) -> None:
        """Refuse live subscriptions or an in-progress checkout reservation.

        The caller holds the organization row lock and has established the
        RLS context for the surrounding transaction.
        """
        try:
            subscription_model = apps.get_model(
                "quickscale_modules_billing", "Subscription"
            )
        except LookupError:
            return

        current_statuses = subscription_model.current_statuses()  # type: ignore[attr-defined]
        queryset = _get_qs(subscription_model, {"organization": organization})
        stripe_subscription_ids = sorted(
            str(subscription_id)
            for subscription_id in queryset.filter(  # type: ignore[attr-defined]
                status__in=current_statuses,
                stripe_subscription_id__isnull=False,
            )
            .exclude(stripe_subscription_id="")
            .values_list("stripe_subscription_id", flat=True)
        )
        ambiguous_current_subscription = (
            queryset.filter(status__in=current_statuses)
            .exclude(status=subscription_model.Status.INCOMPLETE)  # type: ignore[attr-defined]
            .filter(
                models.Q(stripe_subscription_id__isnull=True)
                | models.Q(stripe_subscription_id="")
            )
            .exists()
        )
        pending_checkout_queryset = queryset.filter(  # type: ignore[attr-defined]
            status=subscription_model.Status.INCOMPLETE,  # type: ignore[attr-defined]
        )
        pending_checkout_queryset = pending_checkout_queryset.filter(
            models.Q(stripe_subscription_id__isnull=True)
            | models.Q(stripe_subscription_id="")
        )
        if provider_expired_checkout_id:
            pending_checkout_queryset = pending_checkout_queryset.exclude(
                stripe_checkout_session_id=provider_expired_checkout_id
            )
        pending_checkout = pending_checkout_queryset.exists()

        if ambiguous_current_subscription:
            raise CommandError(
                f"Cannot purge organization {organization.pk} while it has a current "
                "Stripe subscription with no provider id. Reconcile the subscription "
                "before retrying."
            )

        if stripe_subscription_ids:
            joined_ids = ", ".join(stripe_subscription_ids)
            raise CommandError(
                f"Cannot purge organization {organization.pk} while it has current "
                f"Stripe subscriptions: {joined_ids}. Cancel these subscriptions "
                "in Stripe before retrying."
            )

        if pending_checkout:
            raise CommandError(
                f"Cannot purge organization {organization.pk} while a Stripe "
                "subscription checkout is pending. Complete or expire the "
                "checkout before retrying."
            )

    def _guard_provider_backed_fields(self, organization: Organization) -> None:
        """Refuse a purge while a row carries provider-backed state (SA208).

        Project-owned models classify their non-relational ``*_id`` fields in
        ``provider_id_classification``.  A field classified provider-backed
        that holds a value is provider state the purge cannot reconcile, so
        the purge refuses and names every such field.  The caller holds the
        organization row lock and has established the RLS context for the
        surrounding transaction.

        Every existing row of the organization in each declared model is
        locked for the rest of the purge transaction, so a concurrent update
        cannot add a provider value after this read and before deletion.  A
        row inserted concurrently is not covered by those row locks and is
        deleted with the organization.
        """
        try:
            declared_fields = declared_provider_backed_fields(get_tenant_models())
        except ValueError as exc:
            raise CommandError(
                f"Cannot purge organization {organization.pk}: {exc}"
            ) from exc

        carried_fields: list[str] = []
        for model, field_name in declared_fields:
            if not has_organization_id_field(model):
                continue
            try:
                field = model._meta.get_field(field_name)
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
            if any(
                _carries_provider_value(field, getattr(row, field_name))
                for row in locked_rows
            ):
                carried_fields.append(f"{_model_key(model)}.{field_name}")

        if carried_fields:
            joined_fields = ", ".join(sorted(carried_fields))
            raise CommandError(
                f"Cannot purge organization {organization.pk} while rows carry "
                f"provider-backed values: {joined_fields}. Clear or reconcile "
                "these fields before retrying."
            )

    def _check_tombstone(
        self,
        org_id: uuid.UUID,
        *,
        heal_social_cache: bool,
    ) -> None:
        """Check for a tombstone when the org does not exist."""
        try:
            tombstone = OrganizationTombstone.objects.get(organization_id=org_id)
        except OrganizationTombstone.DoesNotExist:
            return

        if heal_social_cache:
            self._invalidate_social_cache(org_id)

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
