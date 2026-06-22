"""Tests for URL configuration"""

import pytest
from django.urls import resolve, reverse


@pytest.mark.django_db
class TestListingUrls:
    """Tests for listing URL patterns"""

    def test_listing_list_url_resolves(self):
        """Test listing list URL resolves correctly"""
        url = reverse("quickscale_listings:listing_list")
        assert url == "/listings/"

    def test_listing_detail_url_resolves(self):
        """Test listing detail URL resolves correctly"""
        url = reverse("quickscale_listings:listing_detail", args=["test-slug"])
        assert url == "/listings/test-slug/"

    def test_publish_api_url(self):
        """Test publish API URL resolves correctly"""
        url = reverse("quickscale_listings:api_publish_listing")
        assert url == "/listings/api/publish/"

    def test_listing_list_view_name(self):
        """Test listing list URL resolves to correct view name"""
        resolver = resolve("/listings/")
        assert resolver.url_name == "listing_list"

    def test_listing_detail_view_name(self):
        """Test listing detail URL resolves to correct view name"""
        resolver = resolve("/listings/test-slug/")
        assert resolver.url_name == "listing_detail"

    def test_app_name_is_quickscale_listings(self):
        """Test app namespace is correct"""
        resolver = resolve("/listings/")
        assert resolver.namespace == "quickscale_listings"

    def test_concrete_listing_list_url(self):
        """Test concrete listing list URL"""
        url = reverse("concrete_listing_list")
        assert url == "/concrete/"

    def test_concrete_listing_detail_url(self):
        """Test concrete listing detail URL"""
        url = reverse("concrete_listing_detail", args=["test-slug"])
        assert url == "/concrete/test-slug/"

    def test_org_listing_list_url_resolves(self):
        """Test org-scoped listing list URL resolves correctly"""
        url = reverse("quickscale_listings:org-listing_list", args=["test-org"])
        assert url == "/listings/orgs/test-org/"

    def test_org_listing_detail_url_resolves(self):
        """Test org-scoped listing detail URL resolves correctly"""
        url = reverse(
            "quickscale_listings:org-listing_detail", args=["test-org", "test-slug"]
        )
        assert url == "/listings/orgs/test-org/test-slug/"

    def test_org_publish_api_url_resolves(self):
        """Test org-scoped publish API URL resolves correctly"""
        url = reverse("quickscale_listings:org-api_publish_listing", args=["test-org"])
        assert url == "/listings/orgs/test-org/api/publish/"

    def test_flat_slug_named_orgs_resolves_as_flat_route(self):
        """CR-004: Flat slug ``orgs`` must resolve to flat listing_detail.

        A flat route ``/listings/orgs/`` must NOT be misidentified as an
        org-scoped route.  The resolver should return ``listing_detail``
        (with ``slug="orgs"``), not an org-scoped pattern.
        """
        resolver = resolve("/listings/orgs/")
        assert resolver.url_name == "listing_detail", (
            f"Expected listing_detail for /listings/orgs/, got {resolver.url_name}"
        )
        assert resolver.kwargs == {"slug": "orgs"}, (
            f"Expected slug=orgs, got {resolver.kwargs}"
        )
        # Confirm no org_slug in kwargs — route detection relies on this
        assert "org_slug" not in resolver.kwargs, (
            "Flat route must not have org_slug in resolver kwargs"
        )
