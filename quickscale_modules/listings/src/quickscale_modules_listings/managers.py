"""Listings module manager contract — delegates to shared orgs TenantManager.

T1.8: Replaced module-local ``TenantScopedManager``/``OperatorManager`` with
the shared ``TenantManager`` from ``quickscale_modules_orgs.managers``.
Scoping is now ambient via the ContextVar set by ``TenantMiddleware``.

Follow-up CR-T18-001: ``OperatorManager`` is now a proper subclass that
passes ``super_scope=True`` so callers who instantiate ``OperatorManager()``
get the correct operator-bypass semantics.
"""

from quickscale_modules_orgs.managers import TenantManager

# Re-export for backward compatibility.
# TenantScopedManager was the default-scoped manager — same as TenantManager().
TenantScopedManager = TenantManager


class OperatorManager(TenantManager):
    """Operator bypass manager — returns all rows (super_scope=True).

    Compatibility wrapper preserved from the module-local implementation.
    Use for admin/operator paths that need to bypass tenant scoping
    (e.g. ``all_objects = OperatorManager()``).
    """

    def __init__(self) -> None:
        super().__init__(super_scope=True)


__all__ = ["TenantManager", "TenantScopedManager", "OperatorManager"]
