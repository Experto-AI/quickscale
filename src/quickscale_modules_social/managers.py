"""Social module manager imports from the shared orgs tenant-scoping seam.

T1.9 — drop module-local TenantScopedManager/OperatorManager in favor of
orgs.managers.TenantManager.

Dual-manager contract (now via TenantManager):
- ``objects`` (``TenantManager()``): default manager. Auto-scopes every
  query to the current organization via the ContextVar maintained by
  ``quickscale_modules_orgs.current_org``.
- ``all_objects`` (``TenantManager(super_scope=True)``): operator escape
  hatch. Returns unfiltered ``QuerySet`` for admin/operator paths that
  need cross-tenant visibility.
"""

from quickscale_modules_orgs.managers import TenantManager

__all__ = [
    "TenantManager",
]
