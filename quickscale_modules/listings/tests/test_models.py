"""Tests for listing models"""

from decimal import Decimal

import pytest
from django.utils import timezone

from quickscale_modules_orgs.models import Organization
from tests.models import ConcreteListing

# ---------------------------------------------------------------------------
# PostgreSQL detection for physical catalog checks
# ---------------------------------------------------------------------------
try:
    from django.db import connection as _listing_db_conn

    _LISTING_IS_POSTGRES = _listing_db_conn.vendor == "postgresql"
except Exception:
    _LISTING_IS_POSTGRES = False


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
        system_org = Organization.objects.get_system_org()
        listing = ConcreteListing.objects.create(
            title="Test Property",
            slug="custom-slug",
            organization=system_org,
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
        """Test get_absolute_url returns flat route pattern (D1)"""
        listing = listing_factory(title="Test Property")
        url = listing.get_absolute_url()
        assert url == "/listings/test-property/"

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

        listings = list(ConcreteListing.all_objects.filter(status="published"))
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
        system_org = Organization.objects.get_system_org()
        listing = ConcreteListing.objects.create(
            title="Contact for Price",
            price=None,
            organization=system_org,
        )
        assert listing.price is None
        assert listing.has_price is False

    def test_blank_location(self, db):
        """Test location can be blank"""
        system_org = Organization.objects.get_system_org()
        listing = ConcreteListing.objects.create(
            title="No Location",
            location="",
            organization=system_org,
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
        system_org = Organization.objects.get_system_org()
        listing = ConcreteListing.objects.create(
            title="No Alt Text",
            featured_image_alt="",
            organization=system_org,
        )
        assert listing.featured_image_alt == ""

    def test_slug_no_longer_globally_unique(self, listing_factory, org):
        """Test slugs are unique per-org but allowed across different orgs.

        T1.8 retains the per-org ``(slug, organization)`` constraint.
        Duplicate slugs are permitted across different organizations but
        not within the same org.
        """
        listing1 = listing_factory(
            title="Same Title",
            organization=org,
        )
        other_org = Organization.objects.create(name="Other Org", slug="other-org")
        listing2 = ConcreteListing.objects.create(
            title="Same Title",
            organization=other_org,
        )
        assert listing1.slug == listing2.slug == "same-title"
        assert listing1.organization == org
        assert listing2.organization == other_org


@pytest.mark.django_db
class TestListingModel:
    """Additional model tests for edge cases"""

    def test_decimal_price_precision(self, db):
        """Test price field handles decimal precision correctly"""
        system_org = Organization.objects.get_system_org()
        listing = ConcreteListing.objects.create(
            title="Precise Price",
            price=Decimal("999999999.99"),
            organization=system_org,
        )
        listing.refresh_from_db()
        assert listing.price == Decimal("999999999.99")

    def test_description_blank(self, db):
        """Test description can be blank"""
        system_org = Organization.objects.get_system_org()
        listing = ConcreteListing.objects.create(
            title="No Description",
            description="",
            organization=system_org,
        )
        assert listing.description == ""

    def test_long_description(self, db):
        """Test description can handle long text"""
        system_org = Organization.objects.get_system_org()
        long_text = "A" * 10000
        listing = ConcreteListing.objects.create(
            title="Long Description",
            description=long_text,
            organization=system_org,
        )
        listing.refresh_from_db()
        assert listing.description == long_text

    @pytest.mark.django_db
    def test_multiple_abstract_subclasses_can_coexist(self, db):
        """CR-001: Multiple AbstractListing subclasses must not collide.

        Each subclass uses a per-subclass ``related_name``
        (``%(class)s_listings``) so the reverse relation from Organization
        is unique per model.
        """
        from tests.models import AlternateListing

        system_org = Organization.objects.get_system_org()
        ConcreteListing.objects.create(
            title="Concrete One", slug="concrete-one", organization=system_org
        )
        AlternateListing.objects.create(
            title="Alternate One", slug="alt-one", organization=system_org
        )

        assert ConcreteListing.all_objects.count() == 1, (
            "ConcreteListing should have 1 row"
        )
        assert AlternateListing.all_objects.count() == 1, (
            "AlternateListing should have 1 row"
        )
        assert (
            ConcreteListing.all_objects.first() is not None
            and AlternateListing.all_objects.first() is not None
        ), "Both subclass instances should exist"

    def test_abstract_listing_index_names_do_not_collide(self):
        """CR-SA90-MSQ-001: Two concrete AbstractListing subclasses must have
        distinct resolved index names that are unique and fit within
        Django's portable 30-character limit.

        Unnamed indexes on abstract models cause Django to auto-generate
        collision-safe names (``%(app_label)s_%(class)s_...``) that are
        unique per concrete subclass and fit within the portable 30-char
        maximum recommended for cross-database compatibility.
        """
        from tests.models import AlternateListing

        concrete_names = {idx.name for idx in ConcreteListing._meta.indexes}
        alternate_names = {idx.name for idx in AlternateListing._meta.indexes}
        collision = concrete_names & alternate_names
        assert not collision, (
            f"ConcreteListing and AlternateListing share resolved index "
            f"names: {collision}"
        )
        for name in concrete_names | alternate_names:
            assert len(name) <= 30, (
                f"Index name {name!r} is {len(name)} chars, expected <=30"
            )

    def test_abstract_listing_indexes_pass_system_checks(self):
        """CR-SA90-MSQ-001: Django system checks pass for two subclasses
        with collision-safe auto-generated index names.

        Asserts zero index-related errors (models.E034, models.E035, etc.)
        across the full system check suite.
        """
        from django.core.checks import run_checks
        from tests.models import AlternateListing

        # Force model-cls resolution for both subclasses by accessing _meta.
        _ = ConcreteListing._meta.indexes  # noqa
        _ = AlternateListing._meta.indexes  # noqa

        errors = run_checks(include_deployment_checks=True)
        # Fail on ANY index-related Django system check error
        # (models.E034 index-name collision, models.E035 index too long,
        # models.W006/W007/W008, etc.) https://docs.djangoproject.com/en/6.0/ref/checks/
        index_errors = [
            e
            for e in (errors or [])
            if e.id is not None
            and e.id.startswith("models.E")
            and ("index" in e.id.lower() or "index" in e.msg.lower())
        ]
        assert not index_errors, (
            f"Django system check flagged index-related errors: "
            f"{[(e.id, e.msg) for e in index_errors]}"
        )

    @pytest.mark.skipif(
        not _LISTING_IS_POSTGRES,
        reason="Physical index name check requires PostgreSQL.",
    )
    def test_listing_physical_index_names(self, db):
        """CR-SA90-MSQ-001: Built-in Listing has exact baseline physical
        index names on the fresh PostgreSQL schema.

        Verifies that ``quickscale__publish_a4cb60_idx``,
        ``quickscale__status_e05f2c_idx``, and ``quickscale__slug_e91f04_idx``
        exist on the ``quickscale_modules_listings_listing`` table so that
        ProjectState and the migration catalog remain unchanged.
        """
        from django.db import connection

        table = "quickscale_modules_listings_listing"
        expected = {
            "quickscale__publish_a4cb60_idx",
            "quickscale__status_e05f2c_idx",
            "quickscale__slug_e91f04_idx",
        }
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE tablename = %s
                  AND indexname = ANY(%s)
                """,
                [table, list(expected)],
            )
            found = {row[0] for row in cursor.fetchall()}
        missing = expected - found
        assert not missing, (
            f"Built-in Listing table {table} is missing physical indexes: "
            f"{missing}.  Listing.Meta must override index names with the "
            f"exact baseline to keep ProjectState unchanged."
        )
