"""Blog module dual-manager contract.

Phase 1 of F11.11: explicit tenant-scoped seam for blog owned models.

Dual-manager contract:
- ``objects`` (TenantScopedManager): default manager. Returns ``BlogQuerySet``
  with an explicit ``.for_org(org_id)`` method for tenant-scoped queries.
  Callers must use ``.for_org()`` for tenant-facing paths.
- ``all_objects`` (OperatorManager): operator escape hatch. Returns unfiltered
  ``QuerySet`` for admin/operator paths that need cross-tenant visibility.

AuthorProfile is a global model (not org-owned) and retains the default
Django manager.
"""

from __future__ import annotations

from django.db import models


class BlogQuerySet(models.QuerySet):
    """Base queryset for blog owned models with explicit tenant-scoping."""

    def for_org(self, organization_id: int | str | None) -> "BlogQuerySet":
        """Return rows belonging to the specified organization.

        When ``organization_id`` is ``None``, returns an empty queryset
        (fail-closed: no org context means no visible rows).
        """
        if organization_id is None:
            return self.none()
        return self.filter(organization_id=organization_id)


class TenantScopedManager(models.Manager):
    """Default manager for blog owned models.

    Returns ``BlogQuerySet`` with explicit ``.for_org()`` method.
    Callers must use ``.for_org(org_id)`` for tenant-scoped queries.
    Using ``.all()`` without ``.for_org()`` returns all rows but signals
    that the caller should review whether tenant scoping is needed.
    """

    def get_queryset(self) -> BlogQuerySet:
        return BlogQuerySet(self.model, using=self._db)

    def for_org(self, organization_id: int | str | None) -> BlogQuerySet:
        """Convenience: scope to the specified organization."""
        return self.get_queryset().for_org(organization_id)


class OperatorManager(models.Manager):
    """Operator escape hatch manager for blog owned models.

    Returns unfiltered ``QuerySet`` for admin/operator paths that need
    cross-tenant visibility. Use only for explicit operator paths —
    tenant-facing code should use ``objects.for_org()`` instead.
    """

    def get_queryset(self) -> models.QuerySet:
        return models.QuerySet(self.model, using=self._db)
