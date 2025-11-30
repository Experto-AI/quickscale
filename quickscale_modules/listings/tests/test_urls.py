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
