"""Tests for listings publish API endpoint"""

import json
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client
from django.urls import resolve, reverse

from quickscale_modules_listings.models import Listing


@pytest.fixture
def staff_user(db):
    """Create a staff user with a personal org (SaaS mode)."""
    from quickscale_modules_orgs.models import Organization

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="staffpass123",
        is_staff=True,
    )
    Organization.objects.create_personal_for(user)
    return user


@pytest.fixture
def regular_user(db):
    """Create a non-staff user with a personal org (SaaS mode)."""
    from quickscale_modules_orgs.models import Organization

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="user",
        email="user@example.com",
        password="userpass123",
        is_staff=False,
    )
    Organization.objects.create_personal_for(user)
    return user


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
        initial_slug_lookup.filter.return_value.exists.return_value = False
        race_check_slug_lookup = MagicMock()
        race_check_slug_lookup.exists.return_value = True
        race_check_slug_lookup.filter.return_value.exists.return_value = True

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

    # ------------------------------------------------------------------
    # CR-003: Flat publish slug-conflict scoping
    # ------------------------------------------------------------------

    def test_publish_listing_api_flat_route_no_conflict_with_org_listing(
        self,
        client,
        staff_user,
        org,
    ):
        """CR-003: Flat publish does not conflict with org-owned same slug.

        An org-null (flat) listing with slug ``test-item`` must be allowed
        even when an org-owned listing already occupies that slug, because
        the uniqueness scope differs (``organization__isnull=True`` vs.
        ``organization=<pk>``).
        """
        Listing.objects.create(
            title="Test Item",
            description="Org-owned listing",
            status="published",
            organization=org,
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Test Item", "description": "Flat listing"}),
            content_type="application/json",
        )

        assert response.status_code == 201, (
            f"Flat publish should succeed when org listing has same slug, "
            f"got {response.status_code}. Response: {response.content.decode()}"
        )
        payload = response.json()
        assert payload["slug"] == "test-item"
        assert payload["status"] == "published"

    def test_publish_listing_api_flat_route_still_conflicts_with_flat_listing(
        self,
        client,
        staff_user,
    ):
        """CR-003: Flat publish still 409s against another org-null same slug.

        The fix only relaxes cross-org conflicts.  Duplicate org-null slugs
        must still produce a 409 conflict error.
        """
        Listing.objects.create(
            title="Shared Title",
            description="Org-null listing one",
            status="published",
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps(
                {"title": "Shared Title", "description": "Org-null listing two"}
            ),
            content_type="application/json",
        )

        assert response.status_code == 409
        assert response.json()["error"] == "Listing already exists for generated slug"


@pytest.mark.django_db
class TestPublishListingApiOrgScoped:
    """CR-002: Org-scoped publish must fail closed when org context is missing."""

    def test_org_scoped_publish_missing_org_context_returns_403(self, staff_user):
        """View-level: org-scoped publish fails closed without ``request.org``.

        The view calls ``_resolve_active_org`` (fail-closed) for org-scoped
        routes.  When the middleware has not set ``request.org``, the view
        returns a JSON 403 instead of silently stamping ``organization=None``.
        """
        from django.test import RequestFactory

        from quickscale_modules_listings.views import publish_listing_api

        factory = RequestFactory()
        url = reverse("quickscale_listings:org-api_publish_listing", args=["some-org"])
        request = factory.post(
            url,
            data=json.dumps({"title": "Org Listing", "description": "Org description"}),
            content_type="application/json",
        )
        request.user = staff_user
        request.resolver_match = resolve(url)

        response = publish_listing_api(request)

        assert response.status_code == 403, (
            f"Expected 403 when org context missing on org-scoped route, "
            f"got {response.status_code}. Response: {response.content.decode()}"
        )
        payload = json.loads(response.content)
        assert "error" in payload, f"Response should contain error key: {payload}"
        assert "organization" in payload["error"].lower() or (
            "required" in payload["error"].lower()
        ), f"Error should reference missing org context: {payload}"

    def test_org_scoped_publish_flat_route_ignores_org_slug_in_path(
        self, client, staff_user
    ):
        """CR-004: Flat-route publish is unaffected by ``orgs`` in the path.

        When a flat-route slug happens to contain the substring ``orgs``,
        the route must NOT be misidentified as org-scoped.  Publishing via
        the flat API should succeed with ``organization=None``.
        """
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps(
                {
                    "title": "My Orgs Listing",
                    "description": "A listing whose slug contains orgs",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201, (
            f"Expected 201 for flat-route publish with 'orgs' in slug, "
            f"got {response.status_code}. Response: {response.content.decode()}"
        )
        payload = response.json()
        assert payload["status"] == "published"
        assert payload["slug"] == "my-orgs-listing"
        assert payload["url"] == "/listings/my-orgs-listing/", (
            "URL must be flat route, not org-scoped"
        )
