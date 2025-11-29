"""Tests for listing views"""

from decimal import Decimal

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestListingListView:
    """Tests for ListingListView"""

    def test_listing_list_view_displays_published_only(
        self, client, published_listing, draft_listing
    ):
        """Test list view only displays published listings"""
        response = client.get(reverse("concrete_listing_list"))
        assert response.status_code == 200
        assert "Published Listing" in str(response.content)
        assert "Draft Listing" not in str(response.content)

    def test_listing_list_view_empty(self, client, db):
        """Test list view with no listings"""
        response = client.get(reverse("concrete_listing_list"))
        assert response.status_code == 200
        assert "No listings available" in str(response.content)

    def test_filter_by_price_min(self, client, listing_factory):
        """Test filtering by minimum price"""
        listing_factory(title="Cheap", status="published", price=Decimal("50.00"))
        listing_factory(title="Expensive", status="published", price=Decimal("200.00"))

        response = client.get(reverse("concrete_listing_list") + "?price_min=100")
        assert response.status_code == 200
        assert "Expensive" in str(response.content)
        assert "Cheap" not in str(response.content)

    def test_filter_by_price_max(self, client, listing_factory):
        """Test filtering by maximum price"""
        listing_factory(title="Cheap", status="published", price=Decimal("50.00"))
        listing_factory(title="Expensive", status="published", price=Decimal("200.00"))

        response = client.get(reverse("concrete_listing_list") + "?price_max=100")
        assert response.status_code == 200
        assert "Cheap" in str(response.content)
        assert "Expensive" not in str(response.content)

    def test_filter_by_price_range(self, client, listing_factory):
        """Test filtering by price range"""
        listing_factory(title="Cheap", status="published", price=Decimal("50.00"))
        listing_factory(title="Medium", status="published", price=Decimal("150.00"))
        listing_factory(title="Expensive", status="published", price=Decimal("300.00"))

        response = client.get(
            reverse("concrete_listing_list") + "?price_min=100&price_max=200"
        )
        assert response.status_code == 200
        assert "Medium" in str(response.content)
        assert "Cheap" not in str(response.content)
        assert "Expensive" not in str(response.content)

    def test_filter_by_location(self, client, listing_factory):
        """Test filtering by location (case-insensitive)"""
        listing_factory(
            title="NYC Property", status="published", location="New York City"
        )
        listing_factory(title="LA Property", status="published", location="Los Angeles")

        response = client.get(reverse("concrete_listing_list") + "?location=new+york")
        assert response.status_code == 200
        assert "NYC Property" in str(response.content)
        assert "LA Property" not in str(response.content)

    def test_filter_by_status(self, client, listing_factory):
        """Test filtering by status - list view shows only published by default"""
        listing_factory(title="Published Item", status="published")
        listing_factory(title="Sold Item", status="sold")

        response = client.get(reverse("concrete_listing_list") + "?status=published")
        assert response.status_code == 200
        assert "Published Item" in str(response.content)
        # Sold items shouldn't show in listing content (but "Sold" appears in filter dropdown)
        assert "Sold Item" not in str(response.content)

    def test_combined_filters(self, client, listing_factory):
        """Test multiple filters combined"""
        listing_factory(
            title="Match",
            status="published",
            price=Decimal("150.00"),
            location="New York",
        )
        listing_factory(
            title="Wrong Price",
            status="published",
            price=Decimal("500.00"),
            location="New York",
        )
        listing_factory(
            title="Wrong Location",
            status="published",
            price=Decimal("150.00"),
            location="Los Angeles",
        )

        response = client.get(
            reverse("concrete_listing_list")
            + "?price_min=100&price_max=200&location=New+York"
        )
        assert response.status_code == 200
        assert "Match" in str(response.content)
        assert "Wrong Price" not in str(response.content)
        assert "Wrong Location" not in str(response.content)

    def test_filter_params_in_context(self, client, listing_factory):
        """Test filter params are passed to context"""
        listing_factory(title="Test", status="published")
        response = client.get(
            reverse("concrete_listing_list") + "?price_min=100&location=NYC"
        )
        assert response.status_code == 200
        assert response.context["filter_params"]["price_min"] == "100"
        assert response.context["filter_params"]["location"] == "NYC"


@pytest.mark.django_db
class TestListingDetailView:
    """Tests for ListingDetailView"""

    def test_listing_detail_view(self, client, published_listing):
        """Test detail view for published listing"""
        response = client.get(
            reverse("concrete_listing_detail", args=[published_listing.slug])
        )
        assert response.status_code == 200
        assert "Published Listing" in str(response.content)

    def test_listing_detail_draft_returns_404(self, client, draft_listing):
        """Test detail view for draft listing returns 404"""
        response = client.get(
            reverse("concrete_listing_detail", args=[draft_listing.slug])
        )
        assert response.status_code == 404

    def test_listing_detail_displays_price(self, client, published_listing):
        """Test detail view displays price"""
        response = client.get(
            reverse("concrete_listing_detail", args=[published_listing.slug])
        )
        assert response.status_code == 200
        assert "250.00" in str(response.content)

    def test_listing_detail_displays_location(self, client, published_listing):
        """Test detail view displays location"""
        response = client.get(
            reverse("concrete_listing_detail", args=[published_listing.slug])
        )
        assert response.status_code == 200
        assert "New York" in str(response.content)

    def test_listing_detail_nonexistent_returns_404(self, client, db):
        """Test detail view for nonexistent listing returns 404"""
        response = client.get(
            reverse("concrete_listing_detail", args=["nonexistent-slug"])
        )
        assert response.status_code == 404

    def test_listing_detail_contact_for_price(self, client, listing_factory):
        """Test detail view shows 'Contact for price' when price is null"""
        listing = listing_factory(
            title="No Price Listing",
            status="published",
            price=None,
        )
        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))
        assert response.status_code == 200
        assert "Contact for price" in str(response.content)
