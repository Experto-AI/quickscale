"""Listings module dual-manager contract.

Phase F11.12b: explicit tenant-scoped seam for the Listing model.

Dual-manager contract:
- ``objects`` (TenantScopedManager): default manager. Returns ``ListingQuerySet``
  with an explicit ``.for_org(org_id)`` method for tenant-scoped queries.
- ``all_objects`` (OperatorManager): operator escape hatch. Returns unfiltered
  ``QuerySet`` for admin/operator paths that need cross-tenant visibility.
"""

from __future__ import annotations

from django.db import models


class ListingQuerySet(models.QuerySet):
    """Base queryset for Listing with explicit tenant-scoping."""

    def for_org(self, organization_id: int | str | None) -> "ListingQuerySet":
        """Return rows belonging to the specified organization.

        When ``organization_id`` is ``None``, returns an empty queryset
        (fail-closed: no org context means no visible rows).
        """
        if organization_id is None:
            return self.none()
        return self.filter(organization_id=organization_id)


class TenantScopedManager(models.Manager):
    """Default manager for Listing.

    Returns ``ListingQuerySet`` with explicit ``.for_org()`` method.
    """

    def get_queryset(self) -> ListingQuerySet:
        return ListingQuerySet(self.model, using=self._db)

    def for_org(self, organization_id: int | str | None) -> ListingQuerySet:
        """Convenience: scope to the specified organization."""
        return self.get_queryset().for_org(organization_id)


class OperatorManager(models.Manager):
    """Operator escape hatch for Listing.

    Returns unfiltered ``QuerySet`` for admin/operator paths that need
    cross-tenant visibility.
    """

    def get_queryset(self) -> models.QuerySet:
        return models.QuerySet(self.model, using=self._db)
