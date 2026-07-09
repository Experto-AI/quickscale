"""Tests for the social module manager re-export contract.

T1.9 — ``TenantManager`` is re-exported from the shared orgs module
rather than defined locally.
"""

from __future__ import annotations

from quickscale_modules_social.managers import TenantManager, __all__


class TestTenantManagerReExport:
    """TenantManager re-export contract."""

    def test_tenant_manager_is_importable_from_social_managers(self) -> None:
        """TenantManager must be accessible via quickscale_modules_social.managers."""
        from quickscale_modules_orgs.managers import (
            TenantManager as OrgTenantManager,
        )

        assert TenantManager is OrgTenantManager

    def test_tenant_manager_in_all(self) -> None:
        """TenantManager must appear in the module's __all__."""
        assert "TenantManager" in __all__

    def test_all_length_is_exactly_one(self) -> None:
        """The only public name in managers is TenantManager."""
        assert __all__ == ["TenantManager"]

    def test_tenant_manager_is_callable(self) -> None:
        """TenantManager must be a class (callable)."""
        assert callable(TenantManager)
