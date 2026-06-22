"""Tests for listings module managers (Phase F11.12b dual-manager contract).

Covers the ``ListingQuerySet`` and ``TenantScopedManager`` implementations to
close the managers.py coverage gap reported by the F11.12b quality-gate pass.
"""

import pytest

from quickscale_modules_listings.models import Listing


class TestListingQuerySet:
    """Tests for ``ListingQuerySet`` direct behavior."""

    @pytest.mark.django_db
    def test_for_org_filters_by_organization(self, org, org_a):
        """``for_org(org_id)`` must return only rows for that organization.

        Covers line 28 of managers.py (the ``self.filter()`` branch).
        """
        Listing.objects.create(title="Org A Listing", organization=org_a)
        Listing.objects.create(title="Default Listing", organization=org)

        qs = Listing.objects.all()
        result = qs.for_org(org_a.pk)

        names = list(result.values_list("title", flat=True))
        assert names == ["Org A Listing"], f"Expected only Org A Listing, got {names}"

    @pytest.mark.django_db
    def test_for_org_with_none_returns_empty_queryset(self, org):
        """``for_org(None)`` must return an empty queryset (fail-closed).

        Covers lines 26-27 of managers.py (the ``if organization_id is None``
        and ``return self.none()`` branches).
        """
        Listing.objects.create(title="Some Listing", organization=org)

        qs = Listing.objects.all()
        result = qs.for_org(None)

        assert result.count() == 0, "Expected empty queryset for None org_id"
        assert list(result) == [], "Expected no rows for None org_id"


class TestTenantScopedManager:
    """Tests for ``TenantScopedManager`` convenience methods."""

    @pytest.mark.django_db
    def test_for_org_on_manager(self, org, org_a):
        """``TenantScopedManager.for_org()`` must scope to the given org.

        Covers line 42 of managers.py.
        """
        Listing.objects.create(title="Visible Listing", organization=org)
        # Create a second listing owned by a different org to make sure
        # the filter actually restricts results.
        Listing.objects.create(title="Other Listing", organization=org_a)

        result = Listing.objects.for_org(org.pk)

        names = list(result.values_list("title", flat=True))
        assert names == ["Visible Listing"], (
            f"Expected only Visible Listing, got {names}"
        )
