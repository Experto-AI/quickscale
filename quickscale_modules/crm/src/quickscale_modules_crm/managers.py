"""CRM module dual-manager contract.

Phase 2 of F11.10: explicit tenant-scoped seam for CRM owned models.

Dual-manager contract:
- ``objects`` (TenantScopedManager): default manager. Returns ``CrmQuerySet``
  with an explicit ``.for_org(org_id)`` method for tenant-scoped queries.
  Callers must use ``.for_org()`` for tenant-facing paths.
- ``all_objects`` (OperatorManager): operator escape hatch. Returns unfiltered
  ``QuerySet`` for admin/operator paths that need cross-tenant visibility.

ContactNote and DealNote are parent-derived (no direct organization FK) and
do not use these managers — they retain the default Django manager.
"""

from __future__ import annotations

from django.db import models


class CrmQuerySet(models.QuerySet):
    """Base queryset for CRM owned models with explicit tenant-scoping."""

    def for_org(self, organization_id: int | str | None) -> "CrmQuerySet":
        """Return rows belonging to the specified organization.

        When ``organization_id`` is ``None``, returns an empty queryset
        (fail-closed: no org context means no visible rows).
        """
        if organization_id is None:
            return self.none()
        return self.filter(organization_id=organization_id)


class TenantScopedManager(models.Manager):
    """Default manager for CRM owned models.

    Returns ``CrmQuerySet`` with explicit ``.for_org()`` method.
    Callers must use ``.for_org(org_id)`` for tenant-scoped queries.
    Using ``.all()`` without ``.for_org()`` returns all rows but signals
    that the caller should review whether tenant scoping is needed.
    """

    def get_queryset(self) -> CrmQuerySet:
        return CrmQuerySet(self.model, using=self._db)

    def for_org(self, organization_id: int | str | None) -> CrmQuerySet:
        """Convenience: scope to the specified organization."""
        return self.get_queryset().for_org(organization_id)


class OperatorManager(models.Manager):
    """Operator escape hatch manager for CRM owned models.

    Returns unfiltered ``QuerySet`` for admin/operator paths that need
    cross-tenant visibility. Use only for explicit operator paths —
    tenant-facing code should use ``objects.for_org()`` instead.
    """

    def get_queryset(self) -> models.QuerySet:
        return models.QuerySet(self.model, using=self._db)
