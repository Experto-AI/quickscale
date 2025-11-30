"""Tests for listing models"""

from decimal import Decimal

import pytest
from django.utils import timezone

from tests.models import ConcreteListing


@pytest.mark.django_db
class TestAbstractListingViaConcreteModel:
    """Tests for AbstractListing via ConcreteListing test model"""

    def test_concrete_model_is_not_abstract(self):
        """Test that ConcreteListing is a concrete model"""
        assert ConcreteListing._meta.abstract is False

    def test_listing_creation(self, listing_factory):
        """Test creating a listing"""
        listing = listing_factory(
            title="Test Property",
            description="A nice property",
            price=Decimal("150000.00"),
            location="San Francisco",
        )
        assert listing.title == "Test Property"
        assert listing.description == "A nice property"
        assert listing.price == Decimal("150000.00")
        assert listing.location == "San Francisco"
        assert listing.status == "draft"
        assert str(listing) == "Test Property"

    def test_auto_slug_generation(self, listing_factory):
        """Test automatic slug generation from title"""
        listing = listing_factory(title="My Amazing Property")
        assert listing.slug == "my-amazing-property"

    def test_manual_slug_preserved(self, db):
        """Test that manually set slug is preserved"""
        listing = ConcreteListing.objects.create(
            title="Test Property",
            slug="custom-slug",
        )
        assert listing.slug == "custom-slug"

    def test_published_date_auto_set(self, listing_factory):
        """Test published_date is set when status changes to published"""
        listing = listing_factory(status="draft")
        assert listing.published_date is None

        listing.status = "published"
        listing.save()
        assert listing.published_date is not None
        assert listing.published_date <= timezone.now()

    def test_published_date_not_overwritten(self, listing_factory):
        """Test published_date is not overwritten on subsequent saves"""
        listing = listing_factory(status="published")
        original_date = listing.published_date

        listing.title = "Updated Title"
        listing.save()
        assert listing.published_date == original_date

    def test_get_absolute_url(self, listing_factory):
        """Test get_absolute_url returns correct pattern"""
        listing = listing_factory(title="Test Property")
        url = listing.get_absolute_url()
        assert "/test-property/" in url
        assert listing.slug in url

    def test_is_published_property(self, listing_factory):
        """Test is_published property"""
        draft = listing_factory(status="draft")
        published = listing_factory(title="Published", status="published")

        assert draft.is_published is False
        assert published.is_published is True

    def test_is_sold_property(self, listing_factory):
        """Test is_sold property"""
        draft = listing_factory(status="draft")
        sold = listing_factory(title="Sold", status="sold")

        assert draft.is_sold is False
        assert sold.is_sold is True

    def test_has_price_property(self, listing_factory):
        """Test has_price property"""
        with_price = listing_factory(price=Decimal("100.00"))
        without_price = listing_factory(title="No Price", price=None)

        assert with_price.has_price is True
        assert without_price.has_price is False

    def test_ordering_by_published_date(self, listing_factory):
        """Test default ordering by -published_date"""
        listing1 = listing_factory(title="First", status="published")
        listing2 = listing_factory(title="Second", status="published")

        listings = list(ConcreteListing.objects.filter(status="published"))
        # Most recently published should be first
        assert listings[0].pk == listing2.pk
        assert listings[1].pk == listing1.pk

    def test_status_choices(self, listing_factory):
        """Test all status choices work"""
        statuses = ["draft", "published", "sold", "archived"]
        for status in statuses:
            listing = listing_factory(
                title=f"Status {status}",
                status=status,
            )
            assert listing.status == status

    def test_nullable_price(self, db):
        """Test price can be null for 'Contact for price'"""
        listing = ConcreteListing.objects.create(
            title="Contact for Price",
            price=None,
        )
        assert listing.price is None
        assert listing.has_price is False

    def test_blank_location(self, db):
        """Test location can be blank"""
        listing = ConcreteListing.objects.create(
            title="No Location",
            location="",
        )
        assert listing.location == ""

    def test_created_at_auto_set(self, listing_factory):
        """Test created_at is automatically set"""
        listing = listing_factory()
        assert listing.created_at is not None
        assert listing.created_at <= timezone.now()

    def test_updated_at_auto_updated(self, listing_factory):
        """Test updated_at is automatically updated on save"""
        listing = listing_factory()
        original_updated = listing.updated_at

        listing.title = "Updated Title"
        listing.save()
        assert listing.updated_at > original_updated

    def test_featured_image_alt_optional(self, db):
        """Test featured_image_alt can be blank"""
        listing = ConcreteListing.objects.create(
            title="No Alt Text",
            featured_image_alt="",
        )
        assert listing.featured_image_alt == ""

    def test_slug_uniqueness(self, listing_factory):
        """Test that slugs are unique"""
        listing_factory(title="Same Title")
        with pytest.raises(Exception):  # IntegrityError
            # Second listing with same title will generate same slug
            ConcreteListing.objects.create(title="Same Title")


@pytest.mark.django_db
class TestListingModel:
    """Additional model tests for edge cases"""

    def test_decimal_price_precision(self, db):
        """Test price field handles decimal precision correctly"""
        listing = ConcreteListing.objects.create(
            title="Precise Price",
            price=Decimal("999999999.99"),
        )
        listing.refresh_from_db()
        assert listing.price == Decimal("999999999.99")

    def test_description_blank(self, db):
        """Test description can be blank"""
        listing = ConcreteListing.objects.create(
            title="No Description",
            description="",
        )
        assert listing.description == ""

    def test_long_description(self, db):
        """Test description can handle long text"""
        long_text = "A" * 10000
        listing = ConcreteListing.objects.create(
            title="Long Description",
            description=long_text,
        )
        listing.refresh_from_db()
        assert listing.description == long_text
