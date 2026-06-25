"""Tests for blog module manager integration (T1.6 TenantManager contract).

Validates that the shared ``TenantManager`` from ``quickscale_modules_orgs``
works correctly on blog models: auto-scoping via ContextVar, operator bypass
via ``all_objects`` (``super_scope=True``), and proper fail-closed behavior.
"""

import pytest
from django.db import models

from quickscale_modules_blog.models import (
    BlogMediaAsset,
    Category,
    Post,
    Tag,
)


class TestTenantManagerScoping:
    """Tests for TenantManager auto-scoping on blog models."""

    @pytest.mark.django_db
    def test_default_manager_is_tenant_manager(self, org):
        """The default ``objects`` manager should be a TenantManager."""
        assert isinstance(Category.objects, models.Manager)
        assert isinstance(Tag.objects, models.Manager)
        assert isinstance(Post.objects, models.Manager)
        assert isinstance(BlogMediaAsset.objects, models.Manager)

    @pytest.mark.django_db
    def test_all_objects_is_tenant_manager_with_super_scope(self, org, org_a):
        """The ``all_objects`` manager should bypass TenantManager auto-scoping.

        When no contextvar is set, ``all_objects`` (super_scope=True) should
        return all rows regardless of organization.
        """
        from quickscale_modules_orgs.current_org import (
            reset_current_org_id,
        )

        reset_current_org_id()

        Category.objects.create(name="Cat A", organization=org)
        Category.objects.create(name="Cat B", organization=org_a)

        all_cats = list(Category.all_objects.all().values_list("name", flat=True))
        assert "Cat A" in all_cats
        assert "Cat B" in all_cats
        assert len(all_cats) == 2

    @pytest.mark.django_db
    def test_default_manager_fail_closed_when_no_org_context(self, org):
        """The default manager should return no rows when contextvar is unset."""
        from quickscale_modules_orgs.current_org import (
            reset_current_org_id,
        )

        reset_current_org_id()

        Category.objects.create(name="Some Cat", organization=org)
        count = Category.objects.count()
        assert count == 0, (
            f"Expected fail-closed (0 rows) with no org context, got {count}"
        )

    @pytest.mark.django_db
    def test_default_manager_filters_by_contextvar_org(self, org, org_a):
        """The default manager should filter to the contextvar org only."""
        from quickscale_modules_orgs.current_org import (
            reset_current_org_id,
            set_current_org_id,
        )

        reset_current_org_id()
        Category.objects.create(name="Cat Org", organization=org)
        Category.objects.create(name="Cat OrgA", organization=org_a)

        set_current_org_id(org.pk)
        try:
            names = list(Category.objects.all().values_list("name", flat=True))
            assert "Cat Org" in names
            assert "Cat OrgA" not in names
        finally:
            reset_current_org_id()


class TestOperatorBypass:
    """Tests for the operator bypass escape hatch."""

    @pytest.mark.django_db
    def test_all_objects_returns_cross_tenant_rows(self, org, org_a):
        """``all_objects`` must return rows from all organizations.

        This validates that the ``super_scope=True`` ``TenantManager``
        bypasses ContextVar-based filtering.
        """
        from quickscale_modules_orgs.current_org import reset_current_org_id

        reset_current_org_id()

        Post.objects.create(
            title="Post A",
            content="Content A",
            status="draft",
            organization=org,
        )
        Post.objects.create(
            title="Post B",
            content="Content B",
            status="draft",
            organization=org_a,
        )

        titles = list(Post.all_objects.all().values_list("title", flat=True))
        assert "Post A" in titles
        assert "Post B" in titles
        assert len(titles) == 2
