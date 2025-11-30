"""Tests for listing filters"""

from decimal import Decimal

import pytest

from quickscale_modules_listings.filters import ListingFilter, get_listing_filter
from tests.models import ConcreteListing


@pytest.mark.django_db
class TestListingFilter:
    """Tests for ListingFilter class"""

    def test_listing_filter_class_exists(self):
        """Test ListingFilter class is defined"""
        assert ListingFilter is not None

    def test_listing_filter_has_price_min_field(self):
        """Test ListingFilter has price_min field"""
        assert "price_min" in ListingFilter.declared_filters

    def test_listing_filter_has_price_max_field(self):
        """Test ListingFilter has price_max field"""
        assert "price_max" in ListingFilter.declared_filters

    def test_listing_filter_has_location_field(self):
        """Test ListingFilter has location field"""
        assert "location" in ListingFilter.declared_filters

    def test_listing_filter_has_status_field(self):
        """Test ListingFilter has status field"""
        assert "status" in ListingFilter.declared_filters


@pytest.mark.django_db
class TestGetListingFilterFactory:
    """Tests for get_listing_filter factory function"""

    def test_factory_creates_filter_class(self):
        """Test factory function creates a filter class"""
        filter_class = get_listing_filter(ConcreteListing)
        assert filter_class is not None
        assert issubclass(filter_class, ListingFilter)

    def test_factory_filter_has_model(self):
        """Test factory-created filter has model set"""
        filter_class = get_listing_filter(ConcreteListing)
        assert filter_class.Meta.model == ConcreteListing

    def test_factory_filter_inherits_fields(self):
        """Test factory-created filter inherits all fields"""
        filter_class = get_listing_filter(ConcreteListing)
        assert "price_min" in filter_class.declared_filters
        assert "price_max" in filter_class.declared_filters
        assert "location" in filter_class.declared_filters
        assert "status" in filter_class.declared_filters


@pytest.mark.django_db
class TestFilterFunctionality:
    """Tests for actual filter functionality"""

    def test_price_min_filter(self, listing_factory):
        """Test price_min filter works correctly"""
        cheap = listing_factory(
            title="Cheap", status="published", price=Decimal("50.00")
        )
        expensive = listing_factory(
            title="Expensive", status="published", price=Decimal("200.00")
        )

        filter_class = get_listing_filter(ConcreteListing)
        f = filter_class(
            data={"price_min": "100"},
            queryset=ConcreteListing.objects.all(),
        )

        results = f.qs
        assert expensive in results
        assert cheap not in results

    def test_price_max_filter(self, listing_factory):
        """Test price_max filter works correctly"""
        cheap = listing_factory(
            title="Cheap", status="published", price=Decimal("50.00")
        )
        expensive = listing_factory(
            title="Expensive", status="published", price=Decimal("200.00")
        )

        filter_class = get_listing_filter(ConcreteListing)
        f = filter_class(
            data={"price_max": "100"},
            queryset=ConcreteListing.objects.all(),
        )

        results = f.qs
        assert cheap in results
        assert expensive not in results

    def test_location_filter_case_insensitive(self, listing_factory):
        """Test location filter is case-insensitive"""
        ny = listing_factory(title="NYC", status="published", location="New York City")
        la = listing_factory(title="LA", status="published", location="Los Angeles")

        filter_class = get_listing_filter(ConcreteListing)
        f = filter_class(
            data={"location": "new york"},
            queryset=ConcreteListing.objects.all(),
        )

        results = f.qs
        assert ny in results
        assert la not in results

    def test_status_filter(self, listing_factory):
        """Test status filter works correctly"""
        published = listing_factory(title="Published", status="published")
        draft = listing_factory(title="Draft", status="draft")

        filter_class = get_listing_filter(ConcreteListing)
        f = filter_class(
            data={"status": "published"},
            queryset=ConcreteListing.objects.all(),
        )

        results = f.qs
        assert published in results
        assert draft not in results

    def test_combined_filters(self, listing_factory):
        """Test multiple filters work together"""
        match = listing_factory(
            title="Match",
            status="published",
            price=Decimal("150.00"),
            location="New York",
        )
        wrong_price = listing_factory(
            title="Wrong Price",
            status="published",
            price=Decimal("500.00"),
            location="New York",
        )
        wrong_location = listing_factory(
            title="Wrong Location",
            status="published",
            price=Decimal("150.00"),
            location="Los Angeles",
        )

        filter_class = get_listing_filter(ConcreteListing)
        f = filter_class(
            data={
                "price_min": "100",
                "price_max": "200",
                "location": "New York",
            },
            queryset=ConcreteListing.objects.all(),
        )

        results = f.qs
        assert match in results
        assert wrong_price not in results
        assert wrong_location not in results
