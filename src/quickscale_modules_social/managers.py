"""Social module dual-manager contract.

Phase F11.13a: explicit tenant-scoped seam for social owned models.

Dual-manager contract:
- ``objects`` (TenantScopedManager): default manager. Returns ``SocialItemQuerySet``
  with an explicit ``.for_org(org_id)`` method for tenant-scoped queries.
  Callers must use ``.for_org()`` for tenant-facing paths.
- ``all_objects`` (OperatorManager): operator escape hatch. Returns unfiltered
  ``QuerySet`` for admin/operator paths that need cross-tenant visibility.
"""

from __future__ import annotations

from django.db import models


class SocialItemQuerySet(models.QuerySet):
    """Base queryset for social owned models with explicit tenant-scoping."""

    def for_org(self, organization_id: int | str | None) -> "SocialItemQuerySet":
        """Return rows belonging to the specified organization.

        When ``organization_id`` is ``None``, returns an empty queryset
        (fail-closed: no org context means no visible rows).
        """
        if organization_id is None:
            return self.none()
        return self.filter(organization_id=organization_id)


class TenantScopedManager(models.Manager):
    """Default manager for social owned models.

    Returns ``SocialItemQuerySet`` with explicit ``.for_org()`` method.
    Callers must use ``.for_org(org_id)`` for tenant-scoped queries.
    Using ``.all()`` without ``.for_org()`` returns all rows but signals
    that the caller should review whether tenant scoping is needed.
    """

    def get_queryset(self) -> SocialItemQuerySet:
        return SocialItemQuerySet(self.model, using=self._db)

    def for_org(self, organization_id: int | str | None) -> SocialItemQuerySet:
        """Convenience: scope to the specified organization."""
        return self.get_queryset().for_org(organization_id)


class OperatorManager(models.Manager):
    """Operator escape hatch manager for social owned models.

    Returns unfiltered ``QuerySet`` for admin/operator paths that need
    cross-tenant visibility. Use only for explicit operator paths —
    tenant-facing code should use ``objects.for_org()`` instead.
    """

    def get_queryset(self) -> models.QuerySet:
        return models.QuerySet(self.model, using=self._db)
