"""Tests for listings publish API endpoint"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

from quickscale_modules_listings.models import Listing


@pytest.fixture
def staff_user(db):
    """Create a staff user"""
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="staffpass123",
        is_staff=True,
    )


@pytest.fixture
def regular_user(db):
    """Create a non-staff user"""
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="user",
        email="user@example.com",
        password="userpass123",
        is_staff=False,
    )


@pytest.mark.django_db
class TestPublishListingApi:
    """Tests for publish listing API"""

    def test_publish_listing_api_get_method_not_allowed_returns_405(self, client):
        """Test API rejects non-POST methods"""
        response = client.get(reverse("quickscale_listings:api_publish_listing"))

        assert response.status_code == 405
        assert response.json()["error"] == "Method not allowed"

    def test_publish_listing_api_unauthenticated_returns_401(self, client):
        """Test API requires authentication"""
        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 401
        assert response.json()["error"] == "Authentication required"

    def test_publish_listing_api_non_staff_returns_403(self, client, regular_user):
        """Test API requires staff permissions"""
        client.force_login(regular_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        assert response.json()["error"] == "Staff access required"

    def test_publish_listing_api_missing_csrf_returns_403(self, staff_user):
        """Test API enforces CSRF protection for session-authenticated requests"""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(staff_user)

        response = csrf_client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 403

    def test_publish_listing_api_invalid_json_returns_400(self, client, staff_user):
        """Test API validates JSON format"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data="not-json",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "Invalid JSON payload"

    def test_publish_listing_api_non_object_payload_returns_400(
        self, client, staff_user
    ):
        """Test API requires JSON object payload"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps(["not", "an", "object"]),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "JSON object payload expected"

    def test_publish_listing_api_invalid_utf8_payload_returns_400(
        self, client, staff_user
    ):
        """Test API rejects non-UTF-8 request body payload"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=b"\xff",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "Invalid JSON payload"

    def test_publish_listing_api_missing_required_fields_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates required fields"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "title": "This field is required",
            "description": "This field is required",
        }

    def test_publish_listing_api_non_sluggable_title_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API requires title to generate a usable slug"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "!!!", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "title": "Must include at least one letter or number"
        }

    def test_publish_listing_api_non_string_location_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates location type"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps(
                {
                    "title": "API Listing",
                    "description": "Listing description",
                    "location": 1,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {"location": "Must be a string"}

    def test_publish_listing_api_invalid_price_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates price payload format"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps(
                {
                    "title": "API Listing",
                    "description": "Listing description",
                    "price": "invalid",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "price": "Must be a number or numeric string"
        }

    def test_publish_listing_api_valid_payload_creates_published_listing(
        self,
        client,
        staff_user,
    ):
        """Test API creates published listing and returns metadata"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps(
                {
                    "title": "Automated Listing",
                    "description": "# Markdown description",
                    "location": "New York",
                    "price": "199.99",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["status"] == "published"
        assert payload["slug"] == "automated-listing"
        assert payload["url"] == "/listings/automated-listing/"

        listing = Listing.objects.get(slug="automated-listing")
        assert listing.status == "published"
        assert listing.location == "New York"
        assert listing.description == "# Markdown description"
        assert listing.price == Decimal("199.99")

    def test_publish_listing_api_duplicate_slug_returns_409(
        self,
        client,
        staff_user,
    ):
        """Test API handles duplicate generated slug as conflict"""
        Listing.objects.create(
            title="Duplicate Title",
            description="Existing description",
            status="published",
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Duplicate Title", "description": "New body"}),
            content_type="application/json",
        )

        assert response.status_code == 409
        assert response.json()["error"] == "Listing already exists for generated slug"

    def test_publish_listing_api_unexpected_integrity_error_returns_500(
        self,
        client,
        staff_user,
    ):
        """Test API returns server error for non-conflict integrity failures"""
        client.force_login(staff_user)

        with patch(
            "quickscale_modules_listings.views.create_published_listing_from_payload",
            side_effect=IntegrityError("other integrity error"),
        ):
            response = client.post(
                reverse("quickscale_listings:api_publish_listing"),
                data=json.dumps({"title": "API Listing", "description": "Body"}),
                content_type="application/json",
            )

        assert response.status_code == 500
        assert response.json()["error"] == "Unable to publish listing"

    def test_publish_listing_api_conflict_detected_after_race_returns_409(
        self,
        client,
        staff_user,
    ):
        """Test API maps race-condition slug conflicts to conflict response"""
        client.force_login(staff_user)

        initial_slug_lookup = MagicMock()
        initial_slug_lookup.exists.return_value = False
        race_check_slug_lookup = MagicMock()
        race_check_slug_lookup.exists.return_value = True

        with (
            patch(
                "quickscale_modules_listings.views.Listing.objects.filter",
                side_effect=[initial_slug_lookup, race_check_slug_lookup],
            ),
            patch(
                "quickscale_modules_listings.views.Listing.objects.create",
                side_effect=IntegrityError("slug conflict"),
            ),
        ):
            response = client.post(
                reverse("quickscale_listings:api_publish_listing"),
                data=json.dumps({"title": "API Listing", "description": "Body"}),
                content_type="application/json",
            )

        assert response.status_code == 409
        assert response.json()["error"] == "Listing already exists for generated slug"
