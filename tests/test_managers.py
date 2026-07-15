"""Tests for listings module managers (T1.8 TenantManager contract).

T1.8: Replaced module-local ``TenantScopedManager``/``OperatorManager`` with
the shared ``TenantManager`` from ``quickscale_modules_orgs.managers``.
Scoping is ambient via the ContextVar set by ``TenantMiddleware``.
"""

import pytest

from quickscale_modules_listings.managers import (
    OperatorManager,
    TenantScopedManager,
)
from quickscale_modules_listings.models import Listing
from quickscale_modules_orgs.current_org import (
    operator_access,
    org_scope,
    set_current_org_id,
)
from quickscale_modules_orgs.managers import TenantManager
from quickscale_modules_orgs.models import Organization


class TestBackwardCompatibilityAliases:
    """Regression tests for backward-compatible manager aliases (CR-T18-001)."""

    def test_tenant_scoped_manager_is_default_scope(self):
        """``TenantScopedManager()`` must produce an auto-scoping manager."""
        manager = TenantScopedManager()
        assert manager._super_scope is False

    def test_tenant_scoped_manager_is_tenant_manager(self):
        """``TenantScopedManager`` must be the same class as ``TenantManager``."""
        assert TenantScopedManager is TenantManager

    def test_operator_manager_is_super_scope(self):
        """``OperatorManager()`` must produce a super-scope (bypass) manager."""
        manager = OperatorManager()
        assert manager._super_scope is True

    def test_operator_manager_is_tenant_manager_subclass(self):
        """``OperatorManager`` must be a subclass of ``TenantManager``."""
        assert issubclass(OperatorManager, TenantManager)
        assert OperatorManager is not TenantManager


class TestTenantManagerScoping:
    """Tests for ``TenantManager`` auto-scoping via ContextVar."""

    @pytest.mark.django_db
    def test_objects_scopes_to_current_org(self, org, org_a):
        """``Listing.objects.all()`` must scope to the org set in the ContextVar."""
        with org_scope(org_a):
            Listing.objects.create(title="Org A Listing", organization=org_a)
        with org_scope(org):
            Listing.objects.create(title="Default Listing", organization=org)

        set_current_org_id(org_a.pk)
        results = list(Listing.objects.all().values_list("title", flat=True))

        assert results == ["Org A Listing"], (
            f"Expected only Org A Listing, got {results}"
        )

    @pytest.mark.django_db
    def test_objects_returns_none_without_org_context(self, org):
        """``Listing.objects.all()`` returns empty when ContextVar is unset."""
        with org_scope(org):
            Listing.objects.create(title="Some Listing", organization=org)

        # Reset ContextVar to unset state
        from quickscale_modules_orgs.current_org import reset_current_org_id

        reset_current_org_id()
        count = Listing.objects.all().count()

        assert count == 0, "Expected empty queryset without org context"

    @pytest.mark.django_db
    def test_all_objects_returns_all_rows(self, org, org_a):
        """``Listing.all_objects.all()`` must return all rows (operator bypass)."""
        with org_scope(org):
            Listing.objects.create(title="Listing A", organization=org)
        with org_scope(org_a):
            Listing.objects.create(title="Listing B", organization=org_a)

        with operator_access(reason="test_all_objects_returns_all_rows"):
            results = list(Listing.all_objects.all().values_list("title", flat=True))

        assert "Listing A" in results
        assert "Listing B" in results
        assert len(results) == 2

    @pytest.mark.django_db
    def test_create_stamps_correct_org(self, org):
        """Creating a listing via ``objects.create`` requires explicit org."""
        system_org = Organization.objects.get_system_org()
        with org_scope(system_org):
            listing = Listing.objects.create(
                title="New Listing", organization=system_org
            )
        assert listing.organization == system_org
        assert listing.pk is not None
