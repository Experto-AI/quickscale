"""Custom managers for the QuickScale organizations module."""

from __future__ import annotations

from itertools import count
from typing import TYPE_CHECKING, Any

from django.db import IntegrityError, models, transaction
from django.utils.text import slugify

if TYPE_CHECKING:
    from .models import Organization


class TenantManager(models.Manager):
    """Manager that auto-scopes querysets to the current organization.

    This is the default manager for :class:`~.models.TenantModel` subclasses.
    It reads the current org ID from the ``ContextVar`` maintained by
    :mod:`~.current_org` and filters all queries to that organization.

    Behaviour
    ---------
    * **Org set** — every ``get_queryset()`` call appends
      ``WHERE organization_id = <current_org_id>``.
    * **No org** — ``get_queryset()`` returns ``.none()`` (fail-closed).
    * **``super_scope=True``** — the manager returns the full unfiltered
      queryset.  Assign this to ``all_objects`` for operator bypass.

    The manager is intentionally model-agnostic and works with any model
    that has an ``organization_id`` foreign-key column.
    """

    def __init__(self, super_scope: bool = False) -> None:
        super().__init__()
        self._super_scope = super_scope

    def get_queryset(self):
        qs = super().get_queryset()
        if self._super_scope:
            return qs
        # Lazy import to avoid circular dependencies at module level.
        from .current_org import get_current_org_id

        org_id = get_current_org_id()
        if org_id is None:
            return qs.none()
        return qs.filter(organization_id=org_id)


class OrganizationManager(models.Manager["Organization"]):
    """Manager helpers for organization creation workflows."""

    def _validate_system_org(self, row: "Organization") -> None:
        """Assert the row meets System org invariants, or raise RuntimeError."""
        from .constants import SYSTEM_ORG_SLUG

        if not row.is_system:
            raise RuntimeError(
                f"Corrupt System org pk={row.pk}: slug='{row.slug}' "
                f"has is_system={row.is_system}. The System org must "
                "have is_system=True."
            )
        if row.is_personal:
            raise RuntimeError(
                f"Corrupt System org pk={row.pk}: slug='{row.slug}' "
                f"has is_personal=True. The System org must have "
                "is_personal=False."
            )
        if row.slug != SYSTEM_ORG_SLUG:
            raise RuntimeError(
                f"Corrupt System org pk={row.pk}: slug='{row.slug}' "
                f"instead of '{SYSTEM_ORG_SLUG}'. The System org "
                "singleton is blocked by a corrupt row."
            )

    def get_system_org(self) -> "Organization":
        """Return the singleton System organization, creating it idempotently.

        The System org is a reserved singleton (slug ``__system__``) that owns
        published-public content (D2).  This method is idempotent — repeated
        calls return the same row.

        The lookup resolves the reserved slug ``__system__`` rather than
        trusting any ``is_system=True`` row.  Model-level ``clean()`` and
        the database partial unique constraint enforce that only the reserved
        slug may carry ``is_system=True``.

        Returns:
            The ``Organization`` instance with ``is_system=True`` and
            slug ``__system__``.
        """
        from .constants import SYSTEM_ORG_NAME, SYSTEM_ORG_SLUG

        # Fast path — the system org already exists.
        try:
            row = self.get(is_system=True, slug=SYSTEM_ORG_SLUG)
            self._validate_system_org(row)
            return row
        except self.model.DoesNotExist:
            pass

        # Creation path — try to create the system org.
        try:
            with transaction.atomic():
                return self.create(
                    name=SYSTEM_ORG_NAME,
                    slug=SYSTEM_ORG_SLUG,
                    is_system=True,
                    is_personal=False,
                )
        except IntegrityError:
            # Another concurrent transaction created the system org, or a
            # corrupt row blocks creation.  Resolve below.
            pass

        # Resolve after a concurrent create or corrupt state.
        # First, check for a row with the reserved slug but wrong flags.
        try:
            row = self.get(slug=SYSTEM_ORG_SLUG)
            self._validate_system_org(row)
            return row
        except self.model.DoesNotExist:
            pass

        # No reserved-slug row exists.  A wrong-slug is_system=True row
        # must have blocked creation via the partial unique constraint.
        row = self.get(is_system=True)
        self._validate_system_org(row)
        return row

    def create_personal_for(self, user: Any) -> "Organization":
        """Return the user's personal organization, creating it if needed."""
        from .models import OrgRole, OrganizationMembership

        existing_membership = (
            OrganizationMembership.objects.select_related("organization")
            .filter(user=user, organization__is_personal=True)
            .first()
        )
        if existing_membership is not None:
            return existing_membership.organization

        username = getattr(user, "username", "") or ""
        fallback_slug = slugify(getattr(user, "email", "")) or f"user-{user.pk}"
        slug = slugify(username) or fallback_slug
        name = username or fallback_slug

        slug_bases = [slug, fallback_slug, f"user-{user.pk}"]
        unique_bases: list[str] = []
        seen_bases: set[str] = set()

        for base in slug_bases:
            if base in seen_bases:
                continue
            seen_bases.add(base)
            unique_bases.append(base)

        slug_candidates = list(unique_bases)
        for suffix in count(2):
            slug_candidates.extend(f"{base}-{suffix}" for base in unique_bases)
            if len(slug_candidates) >= len(unique_bases) * 10:
                break

        seen_slugs: set[str] = set()
        for candidate in slug_candidates:
            if candidate in seen_slugs:
                continue
            seen_slugs.add(candidate)

            try:
                with transaction.atomic():
                    existing_membership = (
                        OrganizationMembership.objects.select_for_update()
                        .select_related("organization")
                        .filter(user=user, organization__is_personal=True)
                        .first()
                    )
                    if existing_membership is not None:
                        return existing_membership.organization

                    organization = self.create(
                        name=name,
                        slug=candidate,
                        is_personal=True,
                    )
                    OrganizationMembership.objects.create(
                        user=user,
                        organization=organization,
                        role=OrgRole.OWNER,
                    )
                    return organization
            except IntegrityError:
                existing_membership = (
                    OrganizationMembership.objects.select_related("organization")
                    .filter(user=user, organization__is_personal=True)
                    .first()
                )
                if existing_membership is not None:
                    return existing_membership.organization

        raise IntegrityError("Unable to create a unique personal organization slug.")
