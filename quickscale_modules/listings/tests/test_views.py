"""Tests for listing views"""

from decimal import Decimal

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test.utils import override_settings
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

    def test_listing_list_uses_runtime_listings_per_page_setting(
        self,
        client,
        listing_factory,
        settings,
    ):
        """Test list pagination reads LISTINGS_PER_PAGE at runtime."""
        settings.LISTINGS_PER_PAGE = 2
        for index in range(3):
            listing_factory(title=f"Listing {index}", status="published")

        response = client.get(reverse("concrete_listing_list"))

        assert response.status_code == 200
        assert response.context["paginator"].per_page == 2
        assert len(response.context["page_obj"].object_list) == 2
        assert response.context["is_paginated"] is True

    def test_listing_list_invalid_listings_per_page_raises_improperly_configured(
        self,
        client,
        listing_factory,
        settings,
    ):
        """SA30: invalid LISTINGS_PER_PAGE raises ImproperlyConfigured instead of falling back."""
        settings.LISTINGS_PER_PAGE = "invalid"

        with pytest.raises(ImproperlyConfigured, match="LISTINGS_PER_PAGE"):
            client.get(reverse("concrete_listing_list"))

    def test_listing_list_bool_listings_per_page_raises_improperly_configured(
        self,
        client,
        listing_factory,
        settings,
    ):
        """SA30: bool LISTINGS_PER_PAGE raises ImproperlyConfigured."""
        settings.LISTINGS_PER_PAGE = False

        with pytest.raises(ImproperlyConfigured, match="LISTINGS_PER_PAGE"):
            client.get(reverse("concrete_listing_list"))

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

    def test_anonymous_list_shows_system_org_listings_only(
        self, client, db, listing_factory, org
    ):
        """Anonymous list must show System-org published listings,
        but hide non-System org published listings (D2)."""
        from quickscale_modules_orgs.current_org import reset_current_org_id

        reset_current_org_id()

        # Create listings — the factory persists them; we only need them to
        # exist in the DB to verify the view's scoping behavior.
        listing_factory(title="System Listing", status="published")
        listing_factory(
            title="Other Org Listing",
            status="published",
            organization=org,
        )

        response = client.get(reverse("concrete_listing_list"))
        assert response.status_code == 200
        assert "System Listing" in str(response.content)
        assert "Other Org Listing" not in str(response.content)

    def test_listing_list_uses_shared_filterset_factory(
        self, client, listing_factory, monkeypatch
    ):
        """The base list view should route filtering through the shared filterset."""
        listing_factory(title="Published Listing", status="published")
        calls: dict[str, bool] = {"used": False}

        class RecordingFilterSet:
            def __init__(self, data=None, queryset=None):
                del data
                calls["used"] = True
                self.qs = queryset.none()

        monkeypatch.setattr(
            "quickscale_modules_listings.views.get_listing_filter",
            lambda model: RecordingFilterSet,
        )

        response = client.get(reverse("concrete_listing_list"))

        assert response.status_code == 200
        assert calls["used"] is True
        assert "Published Listing" not in str(response.content)


@override_settings(LISTINGS_PER_PAGE=None)
def test_listings_page_size_missing_setting_raises_improperly_configured() -> None:
    """SA30: missing LISTINGS_PER_PAGE raises ImproperlyConfigured."""
    with pytest.raises(
        ImproperlyConfigured, match="LISTINGS_PER_PAGE setting is required"
    ):
        # Access through the view's helper
        from quickscale_modules_listings.views import _get_positive_int_setting

        _get_positive_int_setting("LISTINGS_PER_PAGE")


@override_settings(LISTINGS_PER_PAGE="not-a-number")
def test_listings_page_size_non_numeric_setting_raises_improperly_configured() -> None:
    """SA30: non-numeric LISTINGS_PER_PAGE raises ImproperlyConfigured."""
    with pytest.raises(ImproperlyConfigured, match="LISTINGS_PER_PAGE"):
        from quickscale_modules_listings.views import _get_positive_int_setting

        _get_positive_int_setting("LISTINGS_PER_PAGE")


@override_settings(LISTINGS_PER_PAGE=0)
def test_listings_page_size_non_positive_setting_raises_improperly_configured() -> None:
    """SA30: non-positive LISTINGS_PER_PAGE raises ImproperlyConfigured."""
    with pytest.raises(ImproperlyConfigured, match="positive integer"):
        from quickscale_modules_listings.views import _get_positive_int_setting

        _get_positive_int_setting("LISTINGS_PER_PAGE")


@override_settings(LISTINGS_PER_PAGE=-5)
def test_listings_page_size_negative_setting_raises_improperly_configured() -> None:
    """SA30: negative LISTINGS_PER_PAGE raises ImproperlyConfigured."""
    with pytest.raises(ImproperlyConfigured, match="positive integer"):
        from quickscale_modules_listings.views import _get_positive_int_setting

        _get_positive_int_setting("LISTINGS_PER_PAGE")


@override_settings(LISTINGS_PER_PAGE=24)
def test_listings_page_size_valid_setting_passes() -> None:
    """SA30: valid LISTINGS_PER_PAGE returns the value."""
    from quickscale_modules_listings.views import _get_positive_int_setting

    assert _get_positive_int_setting("LISTINGS_PER_PAGE") == 24


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

    def test_listing_detail_styling_hooks_present_when_rendered(
        self, client, listing_factory
    ):
        """Test listing detail includes markdown wrapper"""
        listing = listing_factory(
            title="Styled Listing",
            status="published",
            description="# Heading\n\nStyled content",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'class="listing-markdown-content"' in html
        assert "quickscale_modules_listings/listings.css" in html

    def test_anonymous_detail_shows_system_org_listing(self, client, published_listing):
        """Anonymous detail must show System-org published listings."""
        from quickscale_modules_orgs.current_org import reset_current_org_id

        reset_current_org_id()

        response = client.get(
            reverse("concrete_listing_detail", args=[published_listing.slug])
        )
        assert response.status_code == 200

    def test_anonymous_detail_returns_404_for_non_system_org_listing(
        self, client, db, listing_factory, org
    ):
        """Anonymous detail must return 404 for non-System org listings."""
        from quickscale_modules_orgs.current_org import reset_current_org_id

        reset_current_org_id()

        other_listing = listing_factory(
            title="Other Org Listing",
            status="published",
            organization=org,
        )

        response = client.get(
            reverse("concrete_listing_detail", args=[other_listing.slug])
        )
        assert response.status_code == 404

    def test_listing_detail_escapes_inline_html_in_markdown(
        self, client, listing_factory
    ):
        """Test markdown rendering escapes raw HTML from listing description"""
        listing = listing_factory(
            title="Unsafe Listing",
            status="published",
            description="# Heading\n\n<script>alert('xss')</script>",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert "<script>alert('xss')</script>" not in html
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html

    # ------------------------------------------------------------------
    # SA26 — Markdown URI scheme sanitization
    # ------------------------------------------------------------------

    def test_listing_detail_sanitizes_javascript_markdown_links(
        self, client, listing_factory
    ):
        """Test markdown []() javascript: links are neutralized in rendered output."""
        listing = listing_factory(
            title="JS Link Listing",
            status="published",
            description="[Click](javascript:alert(1))",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        # The href must not contain javascript: — it should be neutralized to ""
        assert 'href="javascript:alert(1)"' not in html
        assert 'href=""' in html
        # Link text should still be present
        assert "Click" in html

    def test_listing_detail_sanitizes_tab_obfuscated_javascript(
        self, client, listing_factory
    ):
        """Test markdown []() links with tab-obfuscated javascript: scheme are neutralized.

        Note: the markdown parser converts control characters in URLs to
        spaces before the sanitizer sees them, so ``java\\tscript:``
        renders as ``java    script:alert(1)`` in the href.  Browsers do
        NOT strip interior spaces from URLs, so this is not an executable
        ``javascript:`` scheme — the tab-obfuscation attack is blocked by
        the markdown parser itself.  The shared sanitizer's control-char
         normalisation handles the general case when a tab reaches the
        sanitizer via a non-markdown path.
        """
        listing = listing_factory(
            title="Tab JS Link Listing",
            status="published",
            description="[Click](java\tscript:alert(1))",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="javascript:' not in html
        assert "javascript:alert(1)" not in html
        assert "Click" in html

    def test_listing_detail_sanitizes_newline_obfuscated_javascript(
        self, client, listing_factory
    ):
        """Test markdown []() links with newline-obfuscated javascript: scheme are neutralized."""
        listing = listing_factory(
            title="NL JS Link Listing",
            status="published",
            description="[Click](java\nscript:alert(1))",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="java' not in html
        assert "javascript:alert(1)" not in html
        assert "Click" in html

    def test_listing_detail_sanitizes_case_variant_javascript(
        self, client, listing_factory
    ):
        """Test markdown []() links with case-variant javascript: scheme are neutralized."""
        listing = listing_factory(
            title="Case JS Link Listing",
            status="published",
            description="[Click](JaVaScRiPt:alert(1))",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="JaVaScRiPt:alert(1)"' not in html
        assert "javascript:alert(1)" not in html
        assert "Click" in html

    def test_listing_detail_sanitizes_data_scheme(self, client, listing_factory):
        """Test markdown []() data: links are neutralized in rendered output."""
        listing = listing_factory(
            title="Data Link Listing",
            status="published",
            description="[Payload](data:text/html,test)",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="data:' not in html
        assert "Payload" in html

    def test_listing_detail_sanitizes_vbscript_scheme(self, client, listing_factory):
        """Test markdown []() vbscript: links are neutralized in rendered output."""
        listing = listing_factory(
            title="VB Link Listing",
            status="published",
            description="[VB](vbscript:msgbox(1))",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="vbscript:' not in html
        assert "VB" in html

    def test_listing_detail_preserves_https_markdown_links(
        self, client, listing_factory
    ):
        """Test legitimate https: markdown links remain clickable."""
        listing = listing_factory(
            title="Safe Link Listing",
            status="published",
            description="[Example](https://example.com/page)",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="https://example.com/page"' in html

    def test_listing_detail_preserves_mailto_markdown_links(
        self, client, listing_factory
    ):
        """Test legitimate mailto: markdown links remain clickable."""
        listing = listing_factory(
            title="Mailto Link Listing",
            status="published",
            description="[Email](mailto:user@example.com)",
        )

        response = client.get(reverse("concrete_listing_detail", args=[listing.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'href="mailto:user@example.com"' in html
