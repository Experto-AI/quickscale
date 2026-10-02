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
from quickscale_modules_orgs.models import Organization


@pytest.fixture
def staff_user(db):
    """Create a staff user with a personal org."""
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
    """Create a non-staff user with a personal org."""
    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="user",
        email="user@example.com",
        password="userpass123",
        is_staff=False,
    )
    Organization.objects.create_personal_for(user)
    return user


@pytest.fixture
def viewer_user(db):
    """Create a user who is only a viewer in their personal org."""
    from quickscale_modules_orgs.models import (
        OrgRole,
        OrganizationMembership,
    )

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="viewer",
        email="viewer@example.com",
        password="viewerpass123",
    )
    organization = Organization.objects.create_personal_for(user)
    OrganizationMembership.objects.filter(user=user, organization=organization).update(
        role=OrgRole.VIEWER
    )
    return user


@pytest.fixture
def member_user(db):
    """Create a user whose only org role is member."""
    from quickscale_modules_orgs.models import (
        OrgRole,
        OrganizationMembership,
    )

    user_model = get_user_model()
    user = user_model.objects.create_user(
        username="member",
        email="member@example.com",
        password="memberpass123",
    )
    organization = Organization.objects.create_personal_for(user)
    OrganizationMembership.objects.filter(user=user, organization=organization).update(
        role=OrgRole.MEMBER
    )
    return user


def _login_with_org(client, user):
    """Log in *user* and activate their personal org in the session.

    TenantMiddleware in SaaS mode requires ACTIVE_ORG_SESSION_KEY for
    authenticated users; without it the middleware redirects to /orgs/.
    """
    from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY
    from quickscale_modules_orgs.models import OrganizationMembership

    client.force_login(user)
    membership = OrganizationMembership.objects.filter(
        user=user, organization__is_personal=True
    ).first()
    if membership is not None:
        session = client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(membership.organization_id)
        session.save()


def _error(response) -> dict:
    """Return the one QuickScale error body from *response*."""
    body = response.json()
    assert "error" in body, body
    return body["error"]


@pytest.mark.django_db
class TestPublishListingApi:
    """Tests for publish listing API (single flat route contract)"""

    def test_publish_listing_api_get_method_not_allowed_returns_405(
        self, client, staff_user
    ):
        """Test API rejects non-POST methods for an authenticated caller"""
        _login_with_org(client, staff_user)

        response = client.get(reverse("quickscale_listings:api_publish_listing"))

        assert response.status_code == 405
        assert _error(response)["code"] == "method_not_allowed"

    def test_publish_listing_api_unauthenticated_returns_401(self, client):
        """Test API requires authentication"""
        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 401
        assert _error(response)["code"] == "not_authenticated"

    def test_publish_listing_api_viewer_role_returns_403(self, client, viewer_user):
        """Test API requires at least the member org role"""
        _login_with_org(client, viewer_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        assert _error(response)["code"] == "permission_denied"

    def test_publish_listing_api_member_role_creates_published_listing(
        self, client, member_user
    ):
        """Test API admits an org member at the member role"""
        _login_with_org(client, member_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Member Listing", "description": "Body"}),
            content_type="application/json",
        )

        assert response.status_code == 201
        assert response.json()["status"] == "published"

    def test_publish_listing_api_foreign_session_org_is_refused_before_the_view(
        self, client, staff_user, regular_user
    ):
        """Record the API's error-surface boundary: orgs' middleware runs first.

        A session naming an organization the user no longer belongs to is
        refused by ``TenantMiddleware`` before any view runs, so the answer is
        the middleware's empty ``403`` rather than the one QuickScale shape.
        This pre-dates the DRF conversion and belongs to the orgs surface.
        """
        from quickscale_modules_orgs._constants import ACTIVE_ORG_SESSION_KEY

        _login_with_org(client, staff_user)
        foreign_org = Organization.objects.get(
            quickscale_orgs_memberships__user=regular_user, is_personal=True
        )
        session = client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(foreign_org.pk)
        session.save()

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        assert response.content == b""

    def test_publish_listing_api_missing_csrf_returns_403(self, staff_user):
        """Test API enforces CSRF protection for session-authenticated requests"""
        csrf_client = Client(enforce_csrf_checks=True)
        _login_with_org(csrf_client, staff_user)

        response = csrf_client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        assert _error(response)["code"] == "permission_denied"

    def test_publish_listing_api_html_preference_still_answers_the_one_shape(
        self, client, staff_user
    ):
        """An HTML-preferring client gets the QuickScale body, not an HTML page."""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Listing", "description": "Description"}),
            content_type="application/json",
            HTTP_ACCEPT="text/html",
        )

        assert response.status_code == 406
        assert _error(response)["code"] == "not_acceptable"

    def test_publish_listing_api_invalid_json_returns_400(self, client, staff_user):
        """Test API validates JSON format"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data="not-json",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["code"] == "parse_error"

    def test_publish_listing_api_non_object_payload_returns_400(
        self, client, staff_user
    ):
        """Test API requires JSON object payload"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps(["not", "an", "object"]),
            content_type="application/json",
        )

        assert response.status_code == 400
        error = _error(response)
        assert error["code"] == "validation_error"
        assert error["fields"] == {"non_field_errors": ["JSON object payload expected"]}

    def test_publish_listing_api_invalid_utf8_payload_returns_400(
        self, client, staff_user
    ):
        """Test API rejects non-UTF-8 request body payload"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=b"\xff",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["code"] == "parse_error"

    def test_publish_listing_api_missing_required_fields_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates required fields"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )

        assert response.status_code == 400
        error = _error(response)
        assert error["code"] == "validation_error"
        assert error["message"] == "Invalid input."
        assert error["fields"] == {
            "title": ["This field is required"],
            "description": ["This field is required"],
        }

    def test_publish_listing_api_non_sluggable_title_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API requires title to generate a usable slug"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "!!!", "description": "Description"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["fields"] == {
            "title": ["Must include at least one letter or number"]
        }

    def test_publish_listing_api_non_string_location_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates location type"""
        _login_with_org(client, staff_user)

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
        assert _error(response)["fields"] == {"location": ["Must be a string"]}

    def test_publish_listing_api_invalid_price_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates price payload format"""
        _login_with_org(client, staff_user)

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
        assert _error(response)["fields"] == {
            "price": ["Must be a number or numeric string"]
        }

    def test_publish_listing_api_valid_payload_creates_published_listing(
        self,
        client,
        staff_user,
    ):
        """Test API creates published listing and returns metadata"""
        _login_with_org(client, staff_user)

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

        listing = Listing.all_objects.get(slug="automated-listing")
        assert listing.status == "published"
        assert listing.location == "New York"
        assert listing.description == "# Markdown description"
        assert listing.price == Decimal("199.99")
        assert listing.organization is not None

    def test_publish_listing_api_duplicate_slug_returns_409(
        self,
        client,
        staff_user,
    ):
        """Test API handles duplicate generated slug as conflict (same org)"""
        from quickscale_modules_orgs.current_org import org_scope

        # Get the personal org from the staff user so both listings share it.
        personal_org = Organization.objects.get(
            quickscale_orgs_memberships__user=staff_user, is_personal=True
        )
        with org_scope(personal_org):
            Listing.objects.create(
                title="Duplicate Title",
                description="Existing description",
                status="published",
                organization=personal_org,
            )
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_listings:api_publish_listing"),
            data=json.dumps({"title": "Duplicate Title", "description": "New body"}),
            content_type="application/json",
        )

        assert response.status_code == 409
        error = _error(response)
        assert error["code"] == "listing_conflict"
        assert error["message"] == "Listing already exists for generated slug"

    def test_publish_listing_api_unexpected_integrity_error_returns_500(
        self,
        client,
        staff_user,
    ):
        """Test API returns server error for non-conflict integrity failures"""
        _login_with_org(client, staff_user)

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
        error = _error(response)
        assert error["code"] == "publish_failed"
        assert error["message"] == "Unable to publish listing"

    def test_publish_listing_api_conflict_detected_after_race_returns_409(
        self,
        client,
        staff_user,
    ):
        """Test API maps race-condition slug conflicts to conflict response"""
        _login_with_org(client, staff_user)

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
        assert _error(response)["code"] == "listing_conflict"
