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

    @pytest.mark.django_db(transaction=True)
    def test_all_objects_is_tenant_manager_with_super_scope(
        self, org, org_a, blog_org_scope
    ):
        """``all_objects`` (``super_scope=True``) bypasses the ORM-level
        TenantManager auto-scoping but still needs ``operator_access`` to
        authorise the cross-tenant DB-level SELECT under FORCE RLS.

        Writes are scoped to each row's organization so RLS allows the INSERT.
        The entire write+read sequence runs inside a shared
        ``transaction.atomic()`` block (``transaction=True`` so the test
        owns its own transaction, isolated from other tests).  Writes
        complete before ``operator_access()`` — no writes occur inside
        the operator block.
        """
        from quickscale_modules_orgs.current_org import operator_access
        from django.db import transaction

        with transaction.atomic():
            with blog_org_scope(org):
                Category.objects.create(name="Cat A", organization=org)
            with blog_org_scope(org_a):
                Category.objects.create(name="Cat B", organization=org_a)

            with operator_access(
                reason="SA83 blog restricted-role cross-tenant SELECT proof"
            ):
                all_cats = list(
                    Category.all_objects.all().values_list("name", flat=True)
                )
        assert "Cat A" in all_cats
        assert "Cat B" in all_cats
        assert len(all_cats) == 2

    @pytest.mark.django_db
    def test_default_manager_fail_closed_when_no_org_context(self, org, blog_org_scope):
        """The default manager should return no rows when contextvar is unset."""
        with blog_org_scope(org):
            Category.objects.create(name="Some Cat", organization=org)
        with blog_org_scope(None):
            count = Category.objects.count()
        assert count == 0, (
            f"Expected fail-closed (0 rows) with no org context, got {count}"
        )

    @pytest.mark.django_db
    def test_default_manager_filters_by_contextvar_org(
        self, org, org_a, blog_org_scope
    ):
        """The default manager should filter to the contextvar org only."""
        with blog_org_scope(org):
            Category.objects.create(name="Cat Org", organization=org)
        with blog_org_scope(org_a):
            Category.objects.create(name="Cat OrgA", organization=org_a)

        with blog_org_scope(org):
            names = list(Category.objects.all().values_list("name", flat=True))
        assert "Cat Org" in names
        assert "Cat OrgA" not in names


class TestOperatorBypass:
    """Tests for the operator bypass escape hatch.

    ``all_objects`` (``super_scope=True``) bypasses the ORM-level
    ``TenantManager`` filtering but does NOT bypass PostgreSQL
    FORCE RLS.  Cross-tenant SELECTs that need to see rows from
    multiple organizations must be elevated via ``operator_access()``
    inside a ``transaction.atomic()`` block.
    """

    @pytest.mark.django_db(transaction=True)
    def test_all_objects_returns_cross_tenant_rows(self, org, org_a, blog_org_scope):
        """``all_objects`` returns rows from all organisations when the
        cross-tenant SELECT is elevated via ``operator_access()``.

        ``all_objects`` (``super_scope=True``) bypasses the ORM-level
        ``TenantManager`` filtering.  ``operator_access()`` inside
        ``transaction.atomic()`` authorises the DB-level SELECT under
        FORCE RLS so rows from multiple organisations are visible.
        Writes complete before ``operator_access()`` — no writes occur
        inside the operator block.  ``transaction=True`` ensures the
        test owns its own transaction so cross-tenant reads see only
        this test's data.
        """
        from quickscale_modules_orgs.current_org import operator_access
        from django.db import transaction

        with transaction.atomic():
            with blog_org_scope(org):
                Post.objects.create(
                    title="Post A",
                    content="Content A",
                    status="draft",
                    organization=org,
                )
            with blog_org_scope(org_a):
                Post.objects.create(
                    title="Post B",
                    content="Content B",
                    status="draft",
                    organization=org_a,
                )

            with operator_access(
                reason="SA83 blog restricted-role cross-tenant SELECT proof"
            ):
                titles = list(Post.all_objects.all().values_list("title", flat=True))
        assert "Post A" in titles
        assert "Post B" in titles
        assert len(titles) == 2
