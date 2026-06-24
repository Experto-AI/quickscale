"""Unit tests for CRM module API views"""

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.shortcuts import resolve_url
from rest_framework import status

from quickscale_modules_crm.models import Deal, Stage
from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY


DASHBOARD_TEST_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

DASHBOARD_SAAS_TEST_MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "quickscale_modules_orgs.middleware.TenantMiddleware",
]

DASHBOARD_TEST_TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]


def _activate_org_in_session(client, organization):
    """Set the active org in the client session for TenantMiddleware."""
    session = client.session
    session[ACTIVE_ORG_SESSION_KEY] = str(organization.id)
    session.save()


def _perform_api_request(client, method, url, data=None):
    """Dispatch a CRM API request for the given method."""
    if method == "get":
        return client.get(url)
    return getattr(client, method)(url, data or {}, format="json")


def _assert_staff_only_route(
    api_client,
    non_staff_authenticated_client,
    authenticated_client,
    method,
    url,
    expected_staff_status,
    data=None,
):
    """Assert the CRM API route is anonymous-denied, non-staff-denied, and staff-allowed."""
    anonymous_response = _perform_api_request(api_client, method, url, data)
    assert anonymous_response.status_code in (
        status.HTTP_401_UNAUTHORIZED,
        status.HTTP_403_FORBIDDEN,
    )

    non_staff_response = _perform_api_request(
        non_staff_authenticated_client, method, url, data
    )
    assert non_staff_response.status_code == status.HTTP_403_FORBIDDEN

    staff_response = _perform_api_request(authenticated_client, method, url, data)
    assert staff_response.status_code == expected_staff_status


def _assert_api_hidden_for_all_callers(
    api_client,
    non_staff_authenticated_client,
    authenticated_client,
    method,
    url,
    data=None,
):
    """Assert the CRM API route stays hidden when the module API toggle is off."""
    for client in (
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
    ):
        response = _perform_api_request(client, method, url, data)
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestCRMDashboardView:
    """Tests for the CRM HTML dashboard access contract."""

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_dashboard_redirects_anonymous_users_to_login(self, client):
        """Anonymous users should enter the configured auth flow before dashboard access."""
        dashboard_url = reverse("quickscale_crm:dashboard")

        response = client.get(dashboard_url)

        assert response.status_code == status.HTTP_302_FOUND
        assert response["Location"] == (
            f"{resolve_url(settings.LOGIN_URL)}?next={dashboard_url}"
        )

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_dashboard_returns_403_for_authenticated_non_staff_user(self, client, user):
        """Authenticated non-staff users should be blocked from the HTML dashboard."""
        client.force_login(user)

        response = client.get(reverse("quickscale_crm:dashboard"))

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_dashboard_returns_200_for_staff_user(self, client, user, contact, deal):
        """Staff users should be able to render the dashboard."""
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get(reverse("quickscale_crm:dashboard"))

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestCRMAPIPermissions:
    """Permission matrix tests for the staff-only CRM API."""

    def test_api_root_requires_staff(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
    ):
        """The CRM API root should only allow staff users."""
        url = reverse("quickscale_crm:api-root")

        _assert_staff_only_route(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            "get",
            url,
            status.HTTP_200_OK,
        )

    @override_settings(CRM_ENABLE_API=False, REST_FRAMEWORK={})
    def test_api_root_returns_404_when_api_disabled(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
    ):
        """The CRM API root should stay hidden when the API toggle is off."""
        url = reverse("quickscale_crm:api-root")

        _assert_api_hidden_for_all_callers(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            "get",
            url,
        )

    @pytest.mark.parametrize(
        "route_name",
        [
            "tag-list",
            "company-list",
            "contact-list",
            "stage-list",
            "deal-list",
            "contact-note-list",
            "deal-note-list",
        ],
    )
    def test_primary_resource_routes_require_staff(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
        route_name,
    ):
        """Primary CRM resource routes should only allow staff users."""
        url = reverse(f"quickscale_crm:{route_name}")

        _assert_staff_only_route(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            "get",
            url,
            status.HTTP_200_OK,
        )

    @pytest.mark.parametrize(
        ("route_name", "method", "payload", "expected_staff_status"),
        [
            pytest.param(
                "contact-notes",
                "get",
                None,
                status.HTTP_200_OK,
                id="contact-notes-list",
            ),
            pytest.param(
                "contact-notes",
                "post",
                {"text": "Staff contact note"},
                status.HTTP_201_CREATED,
                id="contact-notes-create",
            ),
            pytest.param(
                "deal-notes",
                "get",
                None,
                status.HTTP_200_OK,
                id="deal-notes-list",
            ),
            pytest.param(
                "deal-notes",
                "post",
                {"text": "Staff deal note"},
                status.HTTP_201_CREATED,
                id="deal-notes-create",
            ),
        ],
    )
    def test_nested_note_actions_require_staff(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
        contact,
        deal,
        route_name,
        method,
        payload,
        expected_staff_status,
    ):
        """Nested CRM note actions should only allow staff users."""
        object_id = contact.id if route_name == "contact-notes" else deal.id
        url = reverse(f"quickscale_crm:{route_name}", args=[object_id])

        _assert_staff_only_route(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            method,
            url,
            expected_staff_status,
            payload,
        )

    @pytest.mark.parametrize(
        ("route_name", "payload_factory"),
        [
            pytest.param(
                "deal-bulk-update-stage",
                lambda deal, closed_won_stage: {
                    "deal_ids": [deal.id],
                    "stage_id": closed_won_stage.id,
                },
                id="bulk-update-stage",
            ),
            pytest.param(
                "deal-mark-won",
                lambda deal, closed_won_stage: {"deal_ids": [deal.id]},
                id="mark-won",
            ),
            pytest.param(
                "deal-mark-lost",
                lambda deal, closed_won_stage: {"deal_ids": [deal.id]},
                id="mark-lost",
            ),
        ],
    )
    def test_deal_bulk_actions_require_staff(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
        deal,
        closed_won_stage,
        route_name,
        payload_factory,
    ):
        """Deal bulk actions should only allow staff users."""
        url = reverse(f"quickscale_crm:{route_name}")
        payload = payload_factory(deal, closed_won_stage)

        _assert_staff_only_route(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            "post",
            url,
            status.HTTP_200_OK,
            payload,
        )

    @override_settings(CRM_ENABLE_API=False, REST_FRAMEWORK={})
    @pytest.mark.parametrize(
        "route_name",
        [
            "tag-list",
            "company-list",
            "contact-list",
            "stage-list",
            "deal-list",
            "contact-note-list",
            "deal-note-list",
        ],
    )
    def test_primary_resource_routes_return_404_when_api_disabled(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
        route_name,
    ):
        """Primary CRM resource routes should stay hidden when the API toggle is off."""
        url = reverse(f"quickscale_crm:{route_name}")

        _assert_api_hidden_for_all_callers(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            "get",
            url,
        )

    @override_settings(CRM_ENABLE_API=False, REST_FRAMEWORK={})
    @pytest.mark.parametrize(
        ("route_name", "method", "payload"),
        [
            pytest.param("contact-notes", "get", None, id="contact-notes-list"),
            pytest.param(
                "contact-notes",
                "post",
                {"text": "Hidden contact note"},
                id="contact-notes-create",
            ),
            pytest.param("deal-notes", "get", None, id="deal-notes-list"),
            pytest.param(
                "deal-notes",
                "post",
                {"text": "Hidden deal note"},
                id="deal-notes-create",
            ),
        ],
    )
    def test_nested_note_actions_return_404_when_api_disabled(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
        contact,
        deal,
        route_name,
        method,
        payload,
    ):
        """Nested note actions should stay hidden when the API toggle is off."""
        object_id = contact.id if route_name == "contact-notes" else deal.id
        url = reverse(f"quickscale_crm:{route_name}", args=[object_id])

        _assert_api_hidden_for_all_callers(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            method,
            url,
            payload,
        )

    @override_settings(CRM_ENABLE_API=False, REST_FRAMEWORK={})
    @pytest.mark.parametrize(
        ("route_name", "payload_factory"),
        [
            pytest.param(
                "deal-bulk-update-stage",
                lambda deal, closed_won_stage: {
                    "deal_ids": [deal.id],
                    "stage_id": closed_won_stage.id,
                },
                id="bulk-update-stage",
            ),
            pytest.param(
                "deal-mark-won",
                lambda deal, closed_won_stage: {"deal_ids": [deal.id]},
                id="mark-won",
            ),
            pytest.param(
                "deal-mark-lost",
                lambda deal, closed_won_stage: {"deal_ids": [deal.id]},
                id="mark-lost",
            ),
        ],
    )
    def test_deal_bulk_actions_return_404_when_api_disabled(
        self,
        api_client,
        non_staff_authenticated_client,
        authenticated_client,
        deal,
        closed_won_stage,
        route_name,
        payload_factory,
    ):
        """Deal bulk actions should stay hidden when the API toggle is off."""
        url = reverse(f"quickscale_crm:{route_name}")
        payload = payload_factory(deal, closed_won_stage)

        _assert_api_hidden_for_all_callers(
            api_client,
            non_staff_authenticated_client,
            authenticated_client,
            "post",
            url,
            payload,
        )

    @override_settings(CRM_ENABLE_API=False)
    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_dashboard_stays_available_to_staff_when_api_is_disabled(
        self, client, user, contact, deal
    ):
        """Disabling the API should not disable the separate staff-only HTML dashboard."""
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get(reverse("quickscale_crm:dashboard"))

        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestTagViewSet:
    """Tests for TagViewSet"""

    def test_list_tags(self, authenticated_client, tag):
        """Test listing tags"""
        response = authenticated_client.get(reverse("quickscale_crm:tag-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_tag(self, authenticated_client):
        """Test creating a tag"""
        response = authenticated_client.post(
            reverse("quickscale_crm:tag-list"), {"name": "New Tag"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Tag"

    def test_create_duplicate_tag_returns_4xx(self, authenticated_client, tag):
        """Creating a duplicate tag name returns a controlled 4xx, not a 500."""
        response = authenticated_client.post(
            reverse("quickscale_crm:tag-list"), {"name": "VIP"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_update_tag_rename_to_duplicate_returns_4xx(
        self, authenticated_client, tag, staff_personal_org
    ):
        """Renaming a tag to an existing duplicate name returns a controlled 4xx."""
        from quickscale_modules_crm.models import Tag

        Tag.objects.create(name="Hot Lead", organization=staff_personal_org)
        response = authenticated_client.patch(
            reverse("quickscale_crm:tag-detail", args=[tag.id]),
            {"name": "Hot Lead"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_update_tag_same_name_is_valid(self, authenticated_client, tag):
        """Updating a tag without changing its name succeeds (self-exclusion)."""
        response = authenticated_client.patch(
            reverse("quickscale_crm:tag-detail", args=[tag.id]),
            {"name": "VIP"},
        )
        assert response.status_code == status.HTTP_200_OK

    def test_delete_tag(self, authenticated_client, tag):
        """Test deleting a tag"""
        response = authenticated_client.delete(
            reverse("quickscale_crm:tag-detail", args=[tag.id])
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
class TestCompanyViewSet:
    """Tests for CompanyViewSet"""

    def test_list_companies(self, authenticated_client, company):
        """Test listing companies"""
        response = authenticated_client.get(reverse("quickscale_crm:company-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_company(self, authenticated_client):
        """Test creating a company"""
        data = {
            "name": "New Corp",
            "industry": "Finance",
            "website": "https://newcorp.com",
        }
        response = authenticated_client.post(
            reverse("quickscale_crm:company-list"), data
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "New Corp"

    def test_search_companies(self, authenticated_client, company):
        """Test searching companies by name"""
        response = authenticated_client.get(
            f"{reverse('quickscale_crm:company-list')}?search=Acme"
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1


@pytest.mark.django_db
class TestContactViewSet:
    """Tests for ContactViewSet"""

    def test_list_contacts(self, authenticated_client, contact):
        """Test listing contacts"""
        response = authenticated_client.get(reverse("quickscale_crm:contact-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_contact(self, authenticated_client, company):
        """Test creating a contact"""
        data = {
            "first_name": "Jane",
            "last_name": "Smith",
            "email": "jane@example.com",
            "company_id": company.id,
        }
        response = authenticated_client.post(
            reverse("quickscale_crm:contact-list"), data
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["first_name"] == "Jane"

    def test_retrieve_contact(self, authenticated_client, contact):
        """Test retrieving a contact"""
        response = authenticated_client.get(
            reverse("quickscale_crm:contact-detail", args=[contact.id])
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["first_name"] == "John"

    def test_filter_contacts_by_status(self, authenticated_client, contact):
        """Test filtering contacts by status"""
        response = authenticated_client.get(
            f"{reverse('quickscale_crm:contact-list')}?status=new"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_contact_notes_endpoint(self, authenticated_client, contact):
        """Test listing contact notes"""
        response = authenticated_client.get(
            reverse("quickscale_crm:contact-notes", args=[contact.id])
        )
        assert response.status_code == status.HTTP_200_OK

    def test_create_contact_note_via_nested(self, authenticated_client, contact):
        """Test creating a contact note via nested endpoint"""
        response = authenticated_client.post(
            reverse("quickscale_crm:contact-notes", args=[contact.id]),
            {"text": "New note"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "New note"

    @override_settings(REST_FRAMEWORK={})
    def test_contact_list_requires_authentication_without_host_defaults(
        self, api_client
    ):
        """Explicit module auth should not depend on host DRF defaults."""
        response = api_client.get(reverse("quickscale_crm:contact-list"))

        assert response.status_code in (
            status.HTTP_401_UNAUTHORIZED,
            status.HTTP_403_FORBIDDEN,
        )

    @override_settings(REST_FRAMEWORK={})
    def test_contact_list_returns_403_for_non_staff_user_without_host_defaults(
        self, non_staff_authenticated_client, contact
    ):
        """Explicit CRM auth should still reject non-staff users without global DRF settings."""
        response = non_staff_authenticated_client.get(
            reverse("quickscale_crm:contact-list")
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @override_settings(REST_FRAMEWORK={})
    def test_contact_list_allows_staff_user_without_host_defaults(
        self, authenticated_client, contact
    ):
        """Staff CRM access should remain available without global DRF settings."""
        response = authenticated_client.get(reverse("quickscale_crm:contact-list"))

        assert response.status_code == status.HTTP_200_OK

    @override_settings(CRM_ENABLE_API=False, REST_FRAMEWORK={})
    def test_contact_list_returns_404_when_api_disabled(
        self, authenticated_client, contact
    ):
        """Disabling the CRM API should hide the router endpoints."""
        response = authenticated_client.get(reverse("quickscale_crm:contact-list"))

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_create_contact_note_updates_last_contacted_at(
        self, authenticated_client, contact
    ):
        """Logging a contact note should refresh the contact's last-contacted timestamp."""
        assert contact.last_contacted_at is None

        response = authenticated_client.post(
            reverse("quickscale_crm:contact-notes", args=[contact.id]),
            {"text": "Followed up about the proposal"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED

        contact.refresh_from_db()
        assert contact.last_contacted_at is not None


@pytest.mark.django_db
class TestStageViewSet:
    """Tests for StageViewSet"""

    def test_list_stages(self, authenticated_client, stage):
        """Test listing stages"""
        response = authenticated_client.get(reverse("quickscale_crm:stage-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_stage(self, authenticated_client):
        """Test creating a stage"""
        data = {"name": "Proposal", "order": 2}
        response = authenticated_client.post(reverse("quickscale_crm:stage-list"), data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Proposal"


@pytest.mark.django_db
class TestDealViewSet:
    """Tests for DealViewSet"""

    def test_list_deals(self, authenticated_client, deal):
        """Test listing deals"""
        response = authenticated_client.get(reverse("quickscale_crm:deal-list"))
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_deal(self, authenticated_client, contact, stage):
        """Test creating a deal"""
        data = {
            "title": "New Deal",
            "contact_id": contact.id,
            "stage_id": stage.id,
            "amount": "25000.00",
            "probability": 50,
        }
        response = authenticated_client.post(reverse("quickscale_crm:deal-list"), data)
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "New Deal"

    def test_retrieve_deal(self, authenticated_client, deal):
        """Test retrieving a deal"""
        response = authenticated_client.get(
            reverse("quickscale_crm:deal-detail", args=[deal.id])
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Enterprise Deal"

    def test_filter_deals_by_stage(self, authenticated_client, deal, stage):
        """Test filtering deals by stage"""
        response = authenticated_client.get(
            f"{reverse('quickscale_crm:deal-list')}?stage={stage.id}"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_deal_notes_endpoint(self, authenticated_client, deal):
        """Test listing deal notes"""
        response = authenticated_client.get(
            reverse("quickscale_crm:deal-notes", args=[deal.id])
        )
        assert response.status_code == status.HTTP_200_OK

    def test_create_deal_note_via_nested(self, authenticated_client, deal):
        """Test creating a deal note via nested endpoint"""
        response = authenticated_client.post(
            reverse("quickscale_crm:deal-notes", args=[deal.id]),
            {"text": "New deal note"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "New deal note"

    def test_bulk_update_stage(self, authenticated_client, deal, closed_won_stage):
        """Test bulk updating deal stages"""
        data = {
            "deal_ids": [deal.id],
            "stage_id": closed_won_stage.id,
        }
        response = authenticated_client.post(
            reverse("quickscale_crm:deal-bulk-update-stage"), data
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1

        # Verify stage was updated
        deal.refresh_from_db()
        assert deal.stage == closed_won_stage

    def test_mark_won_prefers_terminal_semantic_over_exact_name(
        self, authenticated_client, contact, user, staff_personal_org
    ):
        """Mark-won should target the semantic stage even when names drift."""
        Stage.objects.all().delete()
        exact_name_stage = Stage.objects.create(
            name="Closed-Won", order=3, organization=staff_personal_org
        )
        semantic_stage = Stage.objects.create(
            name="Deal Signed",
            order=9,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            organization=staff_personal_org,
        )
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=exact_name_stage,
            probability=75,
            owner=user,
            organization=staff_personal_org,
        )

        data = {"deal_ids": [deal.id]}
        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-won"), data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1

        # Verify deal was marked won
        deal.refresh_from_db()
        assert deal.stage == semantic_stage
        assert deal.probability == 100

    def test_mark_lost_prefers_terminal_semantic_over_exact_name(
        self, authenticated_client, contact, user, staff_personal_org
    ):
        """Mark-lost should target the semantic stage even when names drift."""
        Stage.objects.all().delete()
        Stage.objects.create(
            name="Closed-Lost", order=4, organization=staff_personal_org
        )
        semantic_stage = Stage.objects.create(
            name="No Decision",
            order=10,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_LOST,
            organization=staff_personal_org,
        )
        open_stage = Stage.objects.create(
            name="Prospecting", order=1, organization=staff_personal_org
        )
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=open_stage,
            probability=75,
            owner=user,
            organization=staff_personal_org,
        )

        data = {"deal_ids": [deal.id]}
        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-lost"), data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1

        # Verify deal was marked lost
        deal.refresh_from_db()
        assert deal.stage == semantic_stage
        assert deal.probability == 0

    def test_mark_won_self_heals_missing_terminal_semantic_with_canonical_stage(
        self, authenticated_client, contact, user, staff_personal_org
    ):
        """Missing semantic rows should self-heal by finding the canonical won stage name."""
        Stage.objects.all().delete()
        # Create a canonical "Closed-Won" stage without terminal_semantic.
        canonical_stage = Stage.objects.create(
            name="Closed-Won", order=3, organization=staff_personal_org
        )
        open_stage = Stage.objects.create(
            name="Prospecting", order=1, organization=staff_personal_org
        )
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=open_stage,
            probability=75,
            owner=user,
            organization=staff_personal_org,
        )

        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-won"),
            {"deal_ids": [deal.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        deal.refresh_from_db()
        # Phase 2: mark_won finds the canonical "Closed-Won" stage by name.
        assert deal.stage == canonical_stage
        assert deal.probability == 100

    def test_mark_lost_self_heals_missing_terminal_semantic_with_canonical_stage(
        self, authenticated_client, contact, user, staff_personal_org
    ):
        """Missing semantic rows should self-heal by finding the canonical lost stage name."""
        Stage.objects.all().delete()
        # Create a canonical "Closed-Lost" stage without terminal_semantic.
        canonical_stage = Stage.objects.create(
            name="Closed-Lost", order=4, organization=staff_personal_org
        )
        open_stage = Stage.objects.create(
            name="Prospecting", order=1, organization=staff_personal_org
        )
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=open_stage,
            probability=75,
            owner=user,
            organization=staff_personal_org,
        )

        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-lost"),
            {"deal_ids": [deal.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        deal.refresh_from_db()
        # Phase 2: mark_lost finds the canonical "Closed-Lost" stage by name.
        assert deal.stage == canonical_stage
        assert deal.probability == 0


@pytest.mark.django_db
class TestCRMPageSizeSettings:
    """Tests for CRM module-owned page size settings."""

    @override_settings(CRM_CONTACTS_PER_PAGE=1, REST_FRAMEWORK={})
    def test_contact_list_respects_contacts_per_page_setting(
        self, authenticated_client, company, staff_personal_org
    ):
        """Contact pagination should use the module setting instead of global DRF config."""
        from quickscale_modules_crm.models import Contact

        Contact.objects.create(
            first_name="Alice",
            last_name="Able",
            email="alice@example.com",
            company=company,
            organization=staff_personal_org,
        )
        Contact.objects.create(
            first_name="Bob",
            last_name="Baker",
            email="bob@example.com",
            company=company,
            organization=staff_personal_org,
        )

        response = authenticated_client.get(reverse("quickscale_crm:contact-list"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    @override_settings(CRM_DEALS_PER_PAGE=1, REST_FRAMEWORK={})
    def test_deal_list_respects_deals_per_page_setting(
        self, authenticated_client, contact, stage, user, staff_personal_org
    ):
        """Deal pagination should use the module setting instead of global DRF config."""
        from quickscale_modules_crm.models import Deal

        Deal.objects.create(
            title="First Deal",
            contact=contact,
            amount="1000.00",
            stage=stage,
            owner=user,
            organization=staff_personal_org,
        )
        Deal.objects.create(
            title="Second Deal",
            contact=contact,
            amount="2000.00",
            stage=stage,
            owner=user,
            organization=staff_personal_org,
        )

        response = authenticated_client.get(reverse("quickscale_crm:deal-list"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1


@pytest.mark.django_db
class TestFlatRouteCreateStamping:
    """Flat-route create stamps the active organization."""

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_org_member_create_tag_stamps_session_org(self, client, org_a, org_a_admin):
        """An org member POST to /crm/api/tags/ stamps the session org."""
        from quickscale_modules_crm.models import Tag

        client.force_login(org_a_admin)
        _activate_org_in_session(client, org_a)

        before = Tag.objects.count()
        response = client.post(
            "/crm/api/tags/",
            data={"name": "Flat-Route Tag"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Tag.all_objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id
        assert Tag.all_objects.count() == before + 1


@pytest.mark.django_db
class TestF1110SoloDashboardNullOwnedCoverage:
    """Solo dashboard coverage for personal-org data (Phase 3, post-0006).

    These tests verify that the solo CRM dashboard includes only personal-org
    data in its aggregates, stage breakdowns, and recent-item displays.
    Legacy NULL-owned data can no longer exist post-0006.
    """

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_dashboard_deals_by_stage_shows_only_personal_org_deals(
        self, client, staff_user, org_a
    ):
        """Solo dashboard deals_by_stage shows only personal-org deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            Stage,
        )
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        # Personal-org stage.
        stage = Stage.objects.create(
            name="Prospecting", order=1, organization=personal_org
        )

        # Personal-org deal on personal-org stage.
        company_personal = Company.objects.create(
            name="Personal Corp", organization=personal_org
        )
        contact_personal = Contact.objects.create(
            first_name="Personal",
            last_name="Contact",
            email="personal-deal@example.com",
            company=company_personal,
            organization=personal_org,
        )
        Deal.objects.create(
            title="Personal Deal",
            contact=contact_personal,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=personal_org,
        )

        client.force_login(staff_user)
        response = client.get("/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # total_deals should include only the personal deal.
        deals_section = content.split("Total Deals")[0]
        deals_value = deals_section.rsplit("<h3>", 1)[-1].split("</h3>")[0].strip()
        assert deals_value == "1", f"Expected total_deals=1, got {deals_value!r}"

        # total_deal_value should include the personal amount.
        assert "1,000" in content or "1000" in content

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_dashboard_recent_contacts_shows_personal_org_company_name(
        self, client, staff_user
    ):
        """Solo dashboard recent_contacts shows company name for personal-org company."""
        from quickscale_modules_crm.models import Company, Contact
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        # A personal-org contact with personal-org company.
        personal_company = Company.objects.create(
            name="Personal Corp", organization=personal_org
        )
        Contact.objects.create(
            first_name="Personal",
            last_name="Contact",
            email="personal-recent@example.com",
            company=personal_company,
            organization=personal_org,
        )

        client.force_login(staff_user)
        response = client.get("/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # Personal-org company name should appear in the rendered content.
        assert "Personal Corp" in content


@pytest.mark.django_db
class TestF1110Phase1SoloRoutePersonalOrgTerminalStageResolution:
    """F11.10 Phase 1 — Prove solo route personal-org-backed terminal stage resolution.

    When the TenantMiddleware attaches a personal org to ``request.org`` on a
    solo route, terminal stage resolution uses that personal org (same-org
    resolution) instead of legacy global resolution.
    """

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_solo_route_mark_won_uses_personal_org_terminal_stage(
        self, client, staff_user
    ):
        """Solo route mark_won uses the personal org for terminal stage resolution."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            Stage,
        )
        from quickscale_modules_orgs.models import (
            Organization,
        )

        # Clear any terminal_semantic stages.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        # Use the personal org that the staff_user fixture already created
        # (the fixture calls create_personal_for, so there is exactly one).
        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        # Create a personal-org terminal won stage.
        personal_won_stage = Stage.objects.create(
            name="Personal Closed-Won",
            order=3,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            organization=personal_org,
        )

        # Create org-scoped deal data.
        company = Company.objects.create(
            name="Personal Corp", organization=personal_org
        )
        contact = Contact.objects.create(
            first_name="Personal",
            last_name="Contact",
            email="personal@example.com",
            company=company,
            organization=personal_org,
        )
        stage = Stage.objects.create(
            name="Personal Stage", order=1, organization=personal_org
        )
        deal = Deal.objects.create(
            title="Personal Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=personal_org,
        )

        staff_user.is_staff = True
        staff_user.save(update_fields=["is_staff"])
        client.force_login(staff_user)

        # Solo route request — TenantMiddleware attaches personal_org.
        response = client.post(
            "/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage == personal_won_stage
        assert deal.probability == 100


@pytest.mark.django_db
class TestF1110StandaloneNoteSoloParentValidation:
    """CR-F11.10-002 — Solo standalone note POSTs enforce parent org ownership.

    These tests verify that standalone ContactNote and DealNote POSTs on
    solo routes (/crm/api/contact-notes/, /crm/api/deal-notes/) validate
    the parent's organization membership using the caller's personal org:
    - Foreign-org parents are rejected with 400.
    - Same-org parents are accepted with 201.
    """

    # -- ContactNote: foreign-org contact rejected ----------------------------

    def test_solo_contact_note_post_rejects_foreign_contact(
        self, client, staff_user, user
    ):
        """Solo ContactNote POST with a foreign-org contact is rejected with 400."""
        from quickscale_modules_crm.models import Company, Contact, ContactNote
        from quickscale_modules_orgs.models import Organization

        personal_org_user = Organization.objects.get(
            is_personal=True, memberships__user=user
        )

        # Create a contact in the user's personal org (foreign to staff_user).
        company = Company.objects.create(
            name="User Corp", organization=personal_org_user
        )
        foreign_contact = Contact.objects.create(
            first_name="Foreign",
            last_name="SoloContact",
            email="foreign-solo-contact@example.com",
            company=company,
            organization=personal_org_user,
        )

        before = ContactNote.objects.count()
        client.force_login(staff_user)

        response = client.post(
            "/crm/api/contact-notes/",
            data={
                "contact": foreign_contact.id,
                "text": "Foreign contact note attempt on solo route",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "contact" in response.data
        assert ContactNote.objects.count() == before

    # -- ContactNote: same-org contact accepted -------------------------------

    def test_solo_contact_note_post_accepts_same_org_contact(self, client, staff_user):
        """Solo ContactNote POST with a same-org contact succeeds with 201."""
        from quickscale_modules_crm.models import Company, Contact, ContactNote
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        company = Company.objects.create(name="Staff Corp", organization=personal_org)
        contact = Contact.objects.create(
            first_name="Same",
            last_name="SoloOrg",
            email="same-org-solo@example.com",
            company=company,
            organization=personal_org,
        )

        client.force_login(staff_user)

        response = client.post(
            "/crm/api/contact-notes/",
            data={
                "contact": contact.id,
                "text": "Same-org solo note",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "Same-org solo note"
        created = ContactNote.objects.get(pk=response.data["id"])
        assert created.contact_id == contact.id

    # -- DealNote: foreign-org deal rejected ----------------------------------

    def test_solo_deal_note_post_rejects_foreign_deal(self, client, staff_user, user):
        """Solo DealNote POST with a foreign-org deal is rejected with 400."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )
        from quickscale_modules_orgs.models import Organization

        personal_org_user = Organization.objects.get(
            is_personal=True, memberships__user=user
        )

        # Create a deal in the user's personal org (foreign to staff_user).
        company = Company.objects.create(
            name="User Corp", organization=personal_org_user
        )
        contact = Contact.objects.create(
            first_name="User",
            last_name="DealContact",
            email="user-deal-solo@example.com",
            company=company,
            organization=personal_org_user,
        )
        stage = Stage.objects.create(
            name="User Stage", order=1, organization=personal_org_user
        )
        foreign_deal = Deal.objects.create(
            title="User Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=personal_org_user,
        )

        before = DealNote.objects.count()
        client.force_login(staff_user)

        response = client.post(
            "/crm/api/deal-notes/",
            data={
                "deal": foreign_deal.id,
                "text": "Foreign deal note attempt on solo route",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "deal" in response.data
        assert DealNote.objects.count() == before

    # -- DealNote: same-org deal accepted -------------------------------------

    def test_solo_deal_note_post_accepts_same_org_deal(self, client, staff_user):
        """Solo DealNote POST with a same-org deal succeeds with 201."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        company = Company.objects.create(name="Staff Corp", organization=personal_org)
        contact = Contact.objects.create(
            first_name="Staff",
            last_name="DealContact",
            email="staff-deal-solo@example.com",
            company=company,
            organization=personal_org,
        )
        stage = Stage.objects.create(
            name="Staff Stage", order=1, organization=personal_org
        )
        deal = Deal.objects.create(
            title="Staff Deal",
            contact=contact,
            amount=Decimal("5000.00"),
            stage=stage,
            organization=personal_org,
        )

        client.force_login(staff_user)

        response = client.post(
            "/crm/api/deal-notes/",
            data={
                "deal": deal.id,
                "text": "Same-org solo deal note",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "Same-org solo deal note"
        created = DealNote.objects.get(pk=response.data["id"])
        assert created.deal_id == deal.id
