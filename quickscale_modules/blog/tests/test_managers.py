"""Tests for blog module managers (Phase 1 / F11.11 dual-manager contract).

Covers the ``BlogQuerySet``, ``TenantScopedManager``, and ``OperatorManager``
implementations to close the managers.py coverage gap reported by the
F11.11 quality-gate pass.
"""

import pytest
from django.db import models

from quickscale_modules_blog.managers import BlogQuerySet
from quickscale_modules_blog.models import Category


class TestBlogQuerySet:
    """Tests for ``BlogQuerySet`` direct behavior."""

    @pytest.mark.django_db
    def test_for_org_filters_by_organization(self, org, org_a):
        """``for_org(org_id)`` must return only rows for that organization.

        Covers line 32 of managers.py (the ``self.filter()`` branch).
        """
        Category.objects.create(name="Org A Cat", organization=org_a)
        Category.objects.create(name="Default Cat", organization=org)

        qs = Category.objects.all()
        result = qs.for_org(org_a.pk)

        names = list(result.values_list("name", flat=True))
        assert names == ["Org A Cat"], f"Expected only Org A Cat, got {names}"

    @pytest.mark.django_db
    def test_for_org_with_none_returns_empty_queryset(self, org):
        """``for_org(None)`` must return an empty queryset (fail-closed).

        Covers lines 30-31 of managers.py (the ``if organization_id is None``
        and ``return self.none()`` branches).
        """
        Category.objects.create(name="Some Cat", organization=org)

        qs = Category.objects.all()
        result = qs.for_org(None)

        assert result.count() == 0, "Expected empty queryset for None org_id"
        assert list(result) == [], "Expected no rows for None org_id"


class TestTenantScopedManager:
    """Tests for ``TenantScopedManager`` convenience methods."""

    @pytest.mark.django_db
    def test_for_org_on_manager(self, org, org_a):
        """``TenantScopedManager.for_org()`` must scope to the given org.

        Covers line 49 of managers.py.
        """
        Category.objects.create(name="Visible Cat", organization=org)
        # Create a second category owned by a different org to make sure
        # the filter actually restricts results.
        Category.objects.create(name="Other Cat", organization=org_a)

        result = Category.objects.for_org(org.pk)

        names = list(result.values_list("name", flat=True))
        assert names == ["Visible Cat"], f"Expected only Visible Cat, got {names}"

    @pytest.mark.django_db
    def test_get_queryset_returns_blog_queryset(self, org):
        """``TenantScopedManager.get_queryset()`` must return ``BlogQuerySet``.

        Covers lines 44-45 of managers.py.
        """
        qs = Category.objects.get_queryset()
        assert isinstance(qs, BlogQuerySet), f"Expected BlogQuerySet, got {type(qs)}"


class TestOperatorManager:
    """Tests for ``OperatorManager`` escape hatch."""

    @pytest.mark.django_db
    def test_get_queryset_returns_standard_queryset(self, org):
        """``OperatorManager.get_queryset()`` must return a plain ``QuerySet``.

        Covers lines 60-61 of managers.py.
        """
        Category.objects.create(name="Operator Cat", organization=org)

        qs = Category.all_objects.get_queryset()

        assert isinstance(qs, models.QuerySet), f"Expected QuerySet, got {type(qs)}"
        # The operator queryset is unfiltered, so it should include everything.
        assert qs.count() >= 1, "Operator queryset should see all rows"

    @pytest.mark.django_db
    def test_operator_manager_all_returns_all_rows(self, org, org_a):
        """``OperatorManager`` (via ``all_objects``) must show all rows
        regardless of organization.

        Covers the integration-level path through OperatorManager.
        """
        Category.objects.create(name="Org A Cat", organization=org_a)
        Category.objects.create(name="Default Cat", organization=org)

        all_cats = list(Category.all_objects.all().values_list("name", flat=True))

        assert "Org A Cat" in all_cats
        assert "Default Cat" in all_cats
        assert len(all_cats) == 2, f"Expected both categories, got {all_cats}"
