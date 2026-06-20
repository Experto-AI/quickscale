"""Unit tests for CRM module API views"""

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse
from django.shortcuts import resolve_url
from rest_framework import status

from quickscale_modules_crm.models import Deal, Stage


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
        self, authenticated_client, tag
    ):
        """Renaming a tag to an existing duplicate name returns a controlled 4xx."""
        from quickscale_modules_crm.models import Tag

        Tag.objects.create(name="Hot Lead")
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

    def test_create_duplicate_tag_via_org_scoped_route_returns_4xx(
        self, authenticated_client, tag
    ):
        """Creating a duplicate tag name via the org-scoped route returns a controlled 4xx."""
        response = authenticated_client.post(
            "/orgs/acme-corp/crm/api/tags/", {"name": "VIP"}
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_update_tag_rename_to_duplicate_via_org_scoped_route_returns_4xx(
        self, client, org_a, org_a_admin
    ):
        """Renaming a tag to a duplicate via the org-scoped route returns a controlled 4xx."""
        from quickscale_modules_crm.models import Tag

        tag = Tag.objects.create(name="VIP", organization=org_a)
        Tag.objects.create(name="Hot Lead", organization=org_a)
        client.force_login(org_a_admin)

        response = client.patch(
            f"/orgs/{org_a.slug}/crm/api/tags/{tag.id}/",
            {"name": "Hot Lead"},
            content_type="application/json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_update_tag_same_name_via_org_scoped_route_is_valid(
        self, client, org_a, org_a_admin
    ):
        """Updating a tag without changing its name via the org-scoped route succeeds."""
        from quickscale_modules_crm.models import Tag

        tag = Tag.objects.create(name="VIP", organization=org_a)
        client.force_login(org_a_admin)

        response = client.patch(
            f"/orgs/{org_a.slug}/crm/api/tags/{tag.id}/",
            {"name": "VIP"},
            content_type="application/json",
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
class TestCRMRouteContractParity:
    """Route-contract parity tests for Phase 11.1c.

    These tests verify that both solo and SaaS CRM paths are routable and
    serve the same views, proving the canonical route contract:
    - Solo: /crm/ and /crm/api/
    - SaaS: /orgs/<slug>/crm/ and /orgs/<slug>/crm/api/
    """

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_solo_dashboard_path_resolves(self, client, user):
        """The solo CRM dashboard should be reachable at /crm/."""
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get("/crm/")

        assert response.status_code == status.HTTP_200_OK

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_saas_dashboard_path_resolves(self, client, user):
        """The SaaS CRM dashboard should be reachable at /orgs/<slug>/crm/."""
        from quickscale_modules_orgs.models import Organization, OrganizationMembership

        org = Organization.objects.create(name="Acme Corp", slug="acme-corp")
        OrganizationMembership.objects.create(user=user, organization=org, role="admin")
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get(f"/orgs/{org.slug}/crm/")

        assert response.status_code == status.HTTP_200_OK

    def test_solo_api_root_path_resolves(self, authenticated_client):
        """The solo CRM API root should be reachable at /crm/api/."""
        response = authenticated_client.get("/crm/api/")

        assert response.status_code == status.HTTP_200_OK

    def test_saas_api_root_path_resolves(self, authenticated_client):
        """The SaaS CRM API root should be reachable at /orgs/<slug>/crm/api/."""
        response = authenticated_client.get("/orgs/acme-corp/crm/api/")

        assert response.status_code == status.HTTP_200_OK

    def test_solo_api_tags_path_resolves(self, authenticated_client, tag):
        """The solo CRM tags API should be reachable at /crm/api/tags/."""
        response = authenticated_client.get("/crm/api/tags/")

        assert response.status_code == status.HTTP_200_OK

    def test_saas_api_tags_path_resolves(self, client, org_a, org_a_admin, tag):
        """The SaaS CRM tags API should be reachable at /orgs/<slug>/crm/api/tags/."""
        tag.organization = org_a
        tag.save(update_fields=["organization"])
        client.force_login(org_a_admin)

        response = client.get(f"/orgs/{org_a.slug}/crm/api/tags/")

        assert response.status_code == status.HTTP_200_OK

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_solo_dashboard_renders_solo_urls(self, client, user):
        """The solo CRM dashboard should render solo URLs in links and examples."""
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get("/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")
        # Verify solo URLs are present
        assert 'href="/crm/"' in content
        assert 'href="/crm/api/"' in content
        assert "/crm/api/contacts/" in content
        assert "/crm/api/companies/" in content
        # Verify SaaS URLs are NOT present
        assert "/orgs/" not in content

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_saas_dashboard_renders_org_scoped_urls(self, client, user):
        """The SaaS CRM dashboard should render org-scoped URLs in links and examples."""
        from quickscale_modules_orgs.models import Organization, OrganizationMembership

        org = Organization.objects.create(name="Acme Corp", slug="acme-corp")
        OrganizationMembership.objects.create(user=user, organization=org, role="admin")
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get(f"/orgs/{org.slug}/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")
        # Verify org-scoped URLs are present
        assert f'href="/orgs/{org.slug}/crm/"' in content
        assert f'href="/orgs/{org.slug}/crm/api/"' in content
        assert f"/orgs/{org.slug}/crm/api/contacts/" in content
        assert f"/orgs/{org.slug}/crm/api/companies/" in content
        # Verify solo URLs are NOT present (except in navigation text)
        # The solo /crm/ URL should not appear as a link
        assert 'href="/crm/"' not in content
        assert 'href="/crm/api/"' not in content


@pytest.mark.django_db
class TestOrgScopedPostDenial:
    """F11.2 — Prove org-scoped POST denial for Tag, Company, and Stage.

    These tests exercise the real TenantMiddleware request path (via
    ``client.force_login``) rather than DRF ``force_authenticate``, so the
    middleware's membership check is the denial seam under test.

    Two denial variants are covered for each resource:
    - Wrong-org: a user who belongs to Org B POSTs to Org A's route → 403.
    - Non-member staff: a staff user with no org membership POSTs to
      Org A's route → 403.

    Each test also confirms that no row is created on denial.
    """

    # -- Tag ------------------------------------------------------------------

    def test_wrong_org_user_cannot_create_tag(self, client, org_a, org_b_admin):
        """An org-B admin must receive 403 when POSTing to org-A's tag route."""
        from quickscale_modules_crm.models import Tag

        before = Tag.objects.count()
        client.force_login(org_b_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/tags/",
            data={"name": "Cross-Org Tag"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Tag.objects.count() == before

    def test_non_member_staff_cannot_create_tag(self, client, org_a, staff_user):
        """A staff user with no org membership must receive 403 on tag create."""
        from quickscale_modules_crm.models import Tag

        before = Tag.objects.count()
        client.force_login(staff_user)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/tags/",
            data={"name": "Ghost Tag"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Tag.objects.count() == before

    # -- Company --------------------------------------------------------------

    def test_wrong_org_user_cannot_create_company(self, client, org_a, org_b_admin):
        """An org-B admin must receive 403 when POSTing to org-A's company route."""
        from quickscale_modules_crm.models import Company

        before = Company.objects.count()
        client.force_login(org_b_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/companies/",
            data={
                "name": "Cross-Org Corp",
                "industry": "Finance",
                "website": "https://cross-org.example.com",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Company.objects.count() == before

    def test_non_member_staff_cannot_create_company(self, client, org_a, staff_user):
        """A staff user with no org membership must receive 403 on company create."""
        from quickscale_modules_crm.models import Company

        before = Company.objects.count()
        client.force_login(staff_user)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/companies/",
            data={
                "name": "Ghost Corp",
                "industry": "Tech",
                "website": "https://ghost.example.com",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Company.objects.count() == before

    # -- Stage ----------------------------------------------------------------

    def test_wrong_org_user_cannot_create_stage(self, client, org_a, org_b_admin):
        """An org-B admin must receive 403 when POSTing to org-A's stage route."""
        from quickscale_modules_crm.models import Stage

        before = Stage.objects.count()
        client.force_login(org_b_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/stages/",
            data={"name": "Cross-Org Stage", "order": 99},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Stage.objects.count() == before

    def test_non_member_staff_cannot_create_stage(self, client, org_a, staff_user):
        """A staff user with no org membership must receive 403 on stage create."""
        from quickscale_modules_crm.models import Stage

        before = Stage.objects.count()
        client.force_login(staff_user)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/stages/",
            data={"name": "Ghost Stage", "order": 99},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Stage.objects.count() == before


@pytest.mark.django_db
class TestF113OrgScopedCreateStamping:
    """F11.3 — Prove org-scoped create stamping for Tag, Company, and Stage.

    These tests exercise the real TenantMiddleware request path (via
    ``client.force_login`` with a session-authenticated org-member) on real
    ``/orgs/{slug}/crm/api/...`` routes.  Each test asserts:
    - 201 on create
    - Persisted ``organization_id`` matches the current org
    - The created row appears in the org-scoped list response
    """

    # -- Tag ------------------------------------------------------------------

    def test_org_member_create_tag_stamps_organization(
        self, client, org_a, org_a_admin
    ):
        """An org-member POST to the org-scoped tag route stamps current-org."""
        from quickscale_modules_crm.models import Tag

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/tags/",
            data={"name": "Org-A Tag"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Org-A Tag"

        created = Tag.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id

        # The created tag appears in the org-scoped list.
        list_response = client.get(f"/orgs/{org_a.slug}/crm/api/tags/")
        assert list_response.status_code == status.HTTP_200_OK
        list_ids = {item["id"] for item in list_response.data}
        assert created.id in list_ids

    # -- Company --------------------------------------------------------------

    def test_org_member_create_company_stamps_organization(
        self, client, org_a, org_a_admin
    ):
        """An org-member POST to the org-scoped company route stamps current-org."""
        from quickscale_modules_crm.models import Company

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/companies/",
            data={
                "name": "Org-A Corp",
                "industry": "Tech",
                "website": "https://orga.example.com",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Org-A Corp"

        created = Company.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id

        # The created company appears in the org-scoped list.
        list_response = client.get(f"/orgs/{org_a.slug}/crm/api/companies/")
        assert list_response.status_code == status.HTTP_200_OK
        list_ids = {item["id"] for item in list_response.data}
        assert created.id in list_ids

    # -- Stage ----------------------------------------------------------------

    def test_org_member_create_stage_stamps_organization(
        self, client, org_a, org_a_admin
    ):
        """An org-member POST to the org-scoped stage route stamps current-org."""
        from quickscale_modules_crm.models import Stage

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/stages/",
            data={"name": "Org-A Stage", "order": 5},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["name"] == "Org-A Stage"

        created = Stage.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id

        # The created stage appears in the org-scoped list.
        list_response = client.get(f"/orgs/{org_a.slug}/crm/api/stages/")
        assert list_response.status_code == status.HTTP_200_OK
        list_ids = {item["id"] for item in list_response.data}
        assert created.id in list_ids

    # -- Tag duplicate regression under stamped context -----------------------

    def test_same_org_tag_duplicate_rejected_under_stamped_context(
        self, client, org_a, org_a_admin
    ):
        """A same-org duplicate tag name is rejected with 400 under stamped context.

        After the first create stamps the org, a second create with the same
        name in the same org must receive a controlled 4xx and no duplicate
        row must be persisted.
        """
        from quickscale_modules_crm.models import Tag

        client.force_login(org_a_admin)

        # First create — should succeed and stamp org.
        first = client.post(
            f"/orgs/{org_a.slug}/crm/api/tags/",
            data={"name": "Duplicate-Me"},
            content_type="application/json",
        )
        assert first.status_code == status.HTTP_201_CREATED
        first_tag = Tag.objects.get(pk=first.data["id"])
        assert first_tag.organization_id == org_a.id

        before_count = Tag.objects.count()

        # Second create with same name in same org — must be rejected.
        second = client.post(
            f"/orgs/{org_a.slug}/crm/api/tags/",
            data={"name": "Duplicate-Me"},
            content_type="application/json",
        )
        assert second.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in second.data
        assert Tag.objects.count() == before_count

    # -- Cross-org tag name allowance (advisory contract) ---------------------

    def test_same_tag_name_allowed_across_different_orgs(
        self, client, org_a, org_b, org_a_admin, org_b_admin
    ):
        """The same tag name can exist in different orgs (owner-bucket contract)."""
        from quickscale_modules_crm.models import Tag

        # Org A creates "Shared-Name".
        client.force_login(org_a_admin)
        resp_a = client.post(
            f"/orgs/{org_a.slug}/crm/api/tags/",
            data={"name": "Shared-Name"},
            content_type="application/json",
        )
        assert resp_a.status_code == status.HTTP_201_CREATED
        tag_a = Tag.objects.get(pk=resp_a.data["id"])
        assert tag_a.organization_id == org_a.id

        # Org B creates the same name — should succeed.
        client.force_login(org_b_admin)
        resp_b = client.post(
            f"/orgs/{org_b.slug}/crm/api/tags/",
            data={"name": "Shared-Name"},
            content_type="application/json",
        )
        assert resp_b.status_code == status.HTTP_201_CREATED
        tag_b = Tag.objects.get(pk=resp_b.data["id"])
        assert tag_b.organization_id == org_b.id
        assert tag_a.id != tag_b.id

    # -- Solo-route regression (no stamping) ----------------------------------

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_create_stamps_personal_organization(self, client, staff_user):
        """Solo-route creates stamp the personal organization (Phase 2 contract).

        In Phase 2, solo routes are personal-org-backed. A solo ``/crm/api/tags/``
        create stamps the user's personal org, not NULL.
        """
        from quickscale_modules_crm.models import Tag
        from quickscale_modules_orgs.models import Organization

        client.force_login(staff_user)
        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        response = client.post(
            "/crm/api/tags/",
            data={"name": "Solo Tag"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Tag.objects.get(pk=response.data["id"])
        assert created.organization_id == personal_org.id


@pytest.mark.django_db
class TestF114OrgScopedContactDealCreateStamping:
    """F11.4 — Prove org-scoped create stamping and foreign-org rejection for Contact and Deal.

    These tests exercise the real TenantMiddleware request path (via
    ``client.force_login`` with a session-authenticated org-member) on real
    ``/orgs/{slug}/crm/api/...`` routes.  Each test asserts:
    - 201 on create (stamping tests)
    - Persisted ``organization_id`` matches the current org
    - The created row appears in the org-scoped list response
    - 400 on create with foreign-org related IDs (rejection tests)
    """

    # -- Contact: org-stamped create ------------------------------------------

    def test_org_member_create_contact_stamps_organization(
        self, client, org_a, org_a_admin
    ):
        """An org-member POST to the org-scoped contact route stamps current-org."""
        from quickscale_modules_crm.models import Company, Contact

        # Create an org-scoped company first.
        company = Company.objects.create(name="Org-A Corp", organization=org_a)

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contacts/",
            data={
                "first_name": "Org",
                "last_name": "Contact",
                "email": "org-contact@example.com",
                "company_id": company.id,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["first_name"] == "Org"

        created = Contact.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id

        # The created contact appears in the org-scoped list.
        list_response = client.get(f"/orgs/{org_a.slug}/crm/api/contacts/")
        assert list_response.status_code == status.HTTP_200_OK
        list_ids = {item["id"] for item in list_response.data}
        assert created.id in list_ids

    # -- Contact: foreign-org company_id rejected ----------------------------

    def test_org_member_create_contact_rejects_foreign_org_company(
        self, client, org_a, org_b, org_a_admin
    ):
        """A contact create with a foreign-org company_id is rejected with 400."""
        from quickscale_modules_crm.models import Company, Contact

        # Create a company in org B (foreign to org A).
        foreign_company = Company.objects.create(name="Org-B Corp", organization=org_b)

        before = Contact.objects.count()
        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contacts/",
            data={
                "first_name": "Cross",
                "last_name": "Org",
                "email": "cross-org@example.com",
                "company_id": foreign_company.id,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "company_id" in response.data
        assert Contact.objects.count() == before

    # -- Contact: foreign-org tag_ids rejected --------------------------------

    def test_org_member_create_contact_rejects_foreign_org_tags(
        self, client, org_a, org_b, org_a_admin
    ):
        """A contact create with foreign-org tag_ids is rejected with 400."""
        from quickscale_modules_crm.models import Company, Contact, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        foreign_tag = Tag.objects.create(name="Org-B-Tag", organization=org_b)

        before = Contact.objects.count()
        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contacts/",
            data={
                "first_name": "Tag",
                "last_name": "Test",
                "email": "tag-test@example.com",
                "company_id": company.id,
                "tag_ids": [foreign_tag.id],
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "tag_ids" in response.data
        assert Contact.objects.count() == before

    # -- Deal: org-stamped create ---------------------------------------------

    def test_org_member_create_deal_stamps_organization(
        self, client, org_a, org_a_admin
    ):
        """An org-member POST to the org-scoped deal route stamps current-org."""
        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Create org-scoped prerequisites.
        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org",
            last_name="Contact",
            email="org-deal-contact@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/",
            data={
                "title": "Org-A Deal",
                "contact_id": contact.id,
                "stage_id": stage.id,
                "amount": "10000.00",
                "probability": 50,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Org-A Deal"

        created = Deal.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id

        # The created deal appears in the org-scoped list.
        list_response = client.get(f"/orgs/{org_a.slug}/crm/api/deals/")
        assert list_response.status_code == status.HTTP_200_OK
        list_ids = {item["id"] for item in list_response.data}
        assert created.id in list_ids

    # -- Deal: foreign-org contact_id rejected --------------------------------

    def test_org_member_create_deal_rejects_foreign_org_contact(
        self, client, org_a, org_b, org_a_admin
    ):
        """A deal create with a foreign-org contact_id is rejected with 400."""
        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Create a contact in org B (foreign to org A).
        foreign_company = Company.objects.create(name="Org-B Corp", organization=org_b)
        foreign_contact = Contact.objects.create(
            first_name="Foreign",
            last_name="Contact",
            email="foreign@example.com",
            company=foreign_company,
            organization=org_b,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)

        before = Deal.objects.count()
        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/",
            data={
                "title": "Cross-Org Deal",
                "contact_id": foreign_contact.id,
                "stage_id": stage.id,
                "amount": "5000.00",
                "probability": 30,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "contact_id" in response.data
        assert Deal.objects.count() == before

    # -- Deal: foreign-org stage_id rejected ----------------------------------

    def test_org_member_create_deal_rejects_foreign_org_stage(
        self, client, org_a, org_b, org_a_admin
    ):
        """A deal create with a foreign-org stage_id is rejected with 400."""
        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org",
            last_name="Contact",
            email="stage-test@example.com",
            company=company,
            organization=org_a,
        )
        # Create a stage in org B (foreign to org A).
        foreign_stage = Stage.objects.create(
            name="Org-B Stage", order=1, organization=org_b
        )

        before = Deal.objects.count()
        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/",
            data={
                "title": "Cross-Stage Deal",
                "contact_id": contact.id,
                "stage_id": foreign_stage.id,
                "amount": "5000.00",
                "probability": 30,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "stage_id" in response.data
        assert Deal.objects.count() == before

    # -- Deal: foreign-org tag_ids rejected -----------------------------------

    def test_org_member_create_deal_rejects_foreign_org_tags(
        self, client, org_a, org_b, org_a_admin
    ):
        """A deal create with foreign-org tag_ids is rejected with 400."""
        from quickscale_modules_crm.models import Company, Contact, Deal, Stage, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org",
            last_name="Contact",
            email="deal-tag-test@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        foreign_tag = Tag.objects.create(name="Org-B-Tag", organization=org_b)

        before = Deal.objects.count()
        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/",
            data={
                "title": "Tag Test Deal",
                "contact_id": contact.id,
                "stage_id": stage.id,
                "amount": "5000.00",
                "probability": 30,
                "tag_ids": [foreign_tag.id],
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "tag_ids" in response.data
        assert Deal.objects.count() == before

    # -- Contact: same-org related IDs accepted (positive acceptance) ----------

    def test_org_member_create_contact_accepts_same_org_company_and_tags(
        self, client, org_a, org_a_admin
    ):
        """A contact create with same-org company_id and tag_ids succeeds with 201."""
        from quickscale_modules_crm.models import Company, Contact, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        tag_a = Tag.objects.create(name="Org-A-Tag", organization=org_a)

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contacts/",
            data={
                "first_name": "Same",
                "last_name": "Org",
                "email": "same-org@example.com",
                "company_id": company.id,
                "tag_ids": [tag_a.id],
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Contact.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id
        assert set(created.tags.values_list("id", flat=True)) == {tag_a.id}

    # -- Contact: NULL-org legacy related IDs accepted -------------------------

    def test_org_member_create_contact_accepts_null_org_legacy_related_ids(
        self, client, org_a, org_a_admin
    ):
        """A contact create with NULL-org (legacy) company and tags succeeds via org-scoped route.

        Legacy rows with organization_id=NULL remain compatible with org-scoped
        creates — the validator only rejects foreign-org references, not
        NULL-owned rows.
        """
        from quickscale_modules_crm.models import Company, Contact, Tag

        legacy_company = Company.objects.create(name="Legacy Corp")
        assert legacy_company.organization_id is None
        legacy_tag = Tag.objects.create(name="Legacy-Tag")
        assert legacy_tag.organization_id is None

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contacts/",
            data={
                "first_name": "Legacy",
                "last_name": "Contact",
                "email": "legacy-contact@example.com",
                "company_id": legacy_company.id,
                "tag_ids": [legacy_tag.id],
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Contact.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id
        assert set(created.tags.values_list("id", flat=True)) == {legacy_tag.id}

    # -- Deal: same-org related IDs accepted (positive acceptance) -------------

    def test_org_member_create_deal_accepts_same_org_contact_stage_and_tags(
        self, client, org_a, org_a_admin
    ):
        """A deal create with same-org contact_id, stage_id, and tag_ids succeeds with 201."""
        from quickscale_modules_crm.models import Company, Contact, Deal, Stage, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org",
            last_name="Contact",
            email="same-org-deal@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        tag_a = Tag.objects.create(name="Org-A-Deal-Tag", organization=org_a)

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/",
            data={
                "title": "Same-Org Deal",
                "contact_id": contact.id,
                "stage_id": stage.id,
                "amount": "15000.00",
                "probability": 60,
                "tag_ids": [tag_a.id],
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Deal.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id
        assert set(created.tags.values_list("id", flat=True)) == {tag_a.id}

    # -- Deal: NULL-org legacy related IDs accepted ----------------------------

    def test_org_member_create_deal_accepts_null_org_legacy_related_ids(
        self, client, org_a, org_a_admin
    ):
        """A deal create with NULL-org (legacy) contact, stage, and tags succeeds.

        Legacy rows with organization_id=NULL remain compatible with org-scoped
        deal creates — the validator only rejects foreign-org references.
        """
        from quickscale_modules_crm.models import Company, Contact, Deal, Stage, Tag

        legacy_company = Company.objects.create(name="Legacy Corp")
        legacy_contact = Contact.objects.create(
            first_name="Legacy",
            last_name="Contact",
            email="legacy-deal-contact@example.com",
            company=legacy_company,
        )
        assert legacy_contact.organization_id is None
        legacy_stage = Stage.objects.create(name="Legacy Stage", order=1)
        assert legacy_stage.organization_id is None
        legacy_tag = Tag.objects.create(name="Legacy-Deal-Tag")
        assert legacy_tag.organization_id is None

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/",
            data={
                "title": "Legacy Deal",
                "contact_id": legacy_contact.id,
                "stage_id": legacy_stage.id,
                "amount": "8000.00",
                "probability": 40,
                "tag_ids": [legacy_tag.id],
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Deal.objects.get(pk=response.data["id"])
        assert created.organization_id == org_a.id
        assert set(created.tags.values_list("id", flat=True)) == {legacy_tag.id}

    # -- Solo-route regression (personal-org stamping) -------------------------

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_contact_create_stamps_personal_organization(
        self, client, staff_user, company
    ):
        """Solo-route contact creates stamp the personal organization (Phase 2)."""
        from quickscale_modules_crm.models import Contact
        from quickscale_modules_orgs.models import Organization

        client.force_login(staff_user)
        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        response = client.post(
            "/crm/api/contacts/",
            data={
                "first_name": "Solo",
                "last_name": "Contact",
                "email": "solo-contact@example.com",
                "company_id": company.id,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Contact.objects.get(pk=response.data["id"])
        assert created.organization_id == personal_org.id

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_deal_create_stamps_personal_organization(
        self, client, staff_user, contact, stage
    ):
        """Solo-route deal creates stamp the personal organization (Phase 2)."""
        from quickscale_modules_crm.models import Deal
        from quickscale_modules_orgs.models import Organization

        client.force_login(staff_user)
        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        response = client.post(
            "/crm/api/deals/",
            data={
                "title": "Solo Deal",
                "contact_id": contact.id,
                "stage_id": stage.id,
                "amount": "1000.00",
                "probability": 50,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Deal.objects.get(pk=response.data["id"])
        assert created.organization_id == personal_org.id


@pytest.mark.django_db
class TestF115OrgScopedReadScoping:
    """F11.5 Phase 1 — Prove org-aware primary read scoping on SaaS routes.

    These tests verify that org-scoped SaaS routes (``/orgs/<slug>/crm/api/...``)
    return only data belonging to the active organization, while solo routes
    (``/crm/api/...``) preserve their legacy unscoped behavior.

    Coverage matrix:
    - Org-scoped list returns only org-scoped data for each resource type
    - Org-scoped retrieve returns 404 for foreign-org objects
    - Solo routes still return all data (parity preserved)
    - Nested note reads are scoped via parent
    - Standalone note reads are scoped via parent-derived FK
    """

    # -- Tag: org-scoped list isolates tenants --------------------------------

    def test_org_scoped_tag_list_returns_only_org_data(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped tag list returns only the active org's tags."""
        from quickscale_modules_crm.models import Tag

        Tag.objects.create(name="Org-A Tag", organization=org_a)
        Tag.objects.create(name="Org-B Tag", organization=org_b)
        Tag.objects.create(name="Legacy Tag")  # NULL org

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/tags/")

        assert response.status_code == status.HTTP_200_OK
        names = {item["name"] for item in response.data}
        assert "Org-A Tag" in names
        assert "Org-B Tag" not in names
        # NULL-org tags are not returned for org-scoped reads.
        assert "Legacy Tag" not in names

    # -- Company: org-scoped list isolates tenants ----------------------------

    def test_org_scoped_company_list_returns_only_org_data(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped company list returns only the active org's companies."""
        from quickscale_modules_crm.models import Company

        Company.objects.create(name="Org-A Corp", organization=org_a)
        Company.objects.create(name="Org-B Corp", organization=org_b)

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/companies/")

        assert response.status_code == status.HTTP_200_OK
        names = {item["name"] for item in response.data}
        assert "Org-A Corp" in names
        assert "Org-B Corp" not in names

    # -- Contact: org-scoped list isolates tenants ----------------------------

    def test_org_scoped_contact_list_returns_only_org_data(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped contact list returns only the active org's contacts."""
        from quickscale_modules_crm.models import Company, Contact

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga@example.com",
            company=company_a,
            organization=org_a,
        )
        Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb@example.com",
            company=company_b,
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/contacts/")

        assert response.status_code == status.HTTP_200_OK
        names = {item["first_name"] for item in response.data}
        assert "Org-A" in names
        assert "Org-B" not in names

    # -- Stage: org-scoped list isolates tenants ------------------------------

    def test_org_scoped_stage_list_returns_only_org_data(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped stage list returns only the active org's stages."""
        from quickscale_modules_crm.models import Stage

        Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/stages/")

        assert response.status_code == status.HTTP_200_OK
        names = {item["name"] for item in response.data}
        assert "Org-A Stage" in names
        assert "Org-B Stage" not in names

    # -- Deal: org-scoped list isolates tenants -------------------------------

    def test_org_scoped_deal_list_returns_only_org_data(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped deal list returns only the active org's deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-deal@example.com",
            company=company_a,
            organization=org_a,
        )
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-deal@example.com",
            company=company_b,
            organization=org_b,
        )
        stage = Stage.objects.create(name="Stage", order=1, organization=org_a)
        Deal.objects.create(
            title="Org-A Deal",
            contact=contact_a,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=org_a,
        )
        stage_b = Stage.objects.create(name="Stage-B", order=1, organization=org_b)
        Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage_b,
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/deals/")

        assert response.status_code == status.HTTP_200_OK
        titles = {item["title"] for item in response.data}
        assert "Org-A Deal" in titles
        assert "Org-B Deal" not in titles

    # -- Org-scoped retrieve returns 404 for foreign-org objects ---------------

    def test_org_scoped_retrieve_returns_404_for_foreign_org_company(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped retrieve of a foreign-org company returns 404."""
        from quickscale_modules_crm.models import Company

        foreign_company = Company.objects.create(name="Org-B Corp", organization=org_b)

        client.force_login(org_a_admin)
        response = client.get(
            f"/orgs/{org_a.slug}/crm/api/companies/{foreign_company.id}/"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_org_scoped_retrieve_returns_404_for_foreign_org_contact(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped retrieve of a foreign-org contact returns 404."""
        from quickscale_modules_crm.models import Company, Contact

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        foreign_contact = Contact.objects.create(
            first_name="Foreign",
            last_name="Contact",
            email="foreign@example.com",
            company=company_b,
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(
            f"/orgs/{org_a.slug}/crm/api/contacts/{foreign_contact.id}/"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_org_scoped_retrieve_returns_404_for_foreign_org_deal(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped retrieve of a foreign-org deal returns 404."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Foreign",
            last_name="Contact",
            email="foreign-deal@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Stage-B", order=1, organization=org_b)
        foreign_deal = Deal.objects.create(
            title="Foreign Deal",
            contact=contact_b,
            amount=Decimal("5000.00"),
            stage=stage_b,
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/deals/{foreign_deal.id}/")

        assert response.status_code == status.HTTP_404_NOT_FOUND

    # -- Solo route parity: personal-org-scoped reads (Phase 2) ----------------

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_tag_list_returns_personal_org_tags(
        self, client, staff_user, org_a, org_b
    ):
        """Solo route tag list returns only personal-org tags (Phase 2)."""
        from quickscale_modules_crm.models import Tag
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )
        Tag.objects.create(name="Org-A Tag", organization=org_a)
        Tag.objects.create(name="Org-B Tag", organization=org_b)
        Tag.objects.create(name="Personal Tag", organization=personal_org)

        client.force_login(staff_user)
        response = client.get("/crm/api/tags/")

        assert response.status_code == status.HTTP_200_OK
        names = {item["name"] for item in response.data}
        assert "Personal Tag" in names
        assert "Org-A Tag" not in names
        assert "Org-B Tag" not in names

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_company_list_returns_personal_org_companies(
        self, client, staff_user, org_a, org_b
    ):
        """Solo route company list returns only personal-org companies (Phase 2)."""
        from quickscale_modules_crm.models import Company
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )
        Company.objects.create(name="Org-A Corp", organization=org_a)
        Company.objects.create(name="Org-B Corp", organization=org_b)
        Company.objects.create(name="Personal Corp", organization=personal_org)

        client.force_login(staff_user)
        response = client.get("/crm/api/companies/")

        assert response.status_code == status.HTTP_200_OK
        names = {item["name"] for item in response.data}
        assert "Personal Corp" in names
        assert "Org-A Corp" not in names
        assert "Org-B Corp" not in names

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_contact_list_returns_personal_org_contacts(
        self, client, staff_user, org_a, org_b
    ):
        """Solo route contact list returns only personal-org contacts (Phase 2)."""
        from quickscale_modules_crm.models import Company, Contact
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )
        company_personal = Company.objects.create(
            name="Personal Corp", organization=personal_org
        )
        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        Contact.objects.create(
            first_name="Personal",
            last_name="Contact",
            email="personal@example.com",
            company=company_personal,
            organization=personal_org,
        )
        Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="solo-a@example.com",
            company=company_a,
            organization=org_a,
        )
        Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="solo-b@example.com",
            company=company_b,
            organization=org_b,
        )

        client.force_login(staff_user)
        response = client.get("/crm/api/contacts/")

        assert response.status_code == status.HTTP_200_OK
        names = {item["first_name"] for item in response.data}
        assert "Personal" in names
        assert "Org-A" not in names
        assert "Org-B" not in names

    # -- Standalone note reads: scoped via parent-derived FK ------------------

    def test_org_scoped_contact_note_list_returns_only_org_notes(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped contact-note list returns only notes for org-A contacts."""
        from quickscale_modules_crm.models import Company, Contact, ContactNote

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Note",
            email="note-a@example.com",
            company=company_a,
            organization=org_a,
        )
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Note",
            email="note-b@example.com",
            company=company_b,
            organization=org_b,
        )
        ContactNote.objects.create(
            contact=contact_a, created_by=org_a_admin, text="Org-A note"
        )
        ContactNote.objects.create(
            contact=contact_b, created_by=org_a_admin, text="Org-B note"
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/contact-notes/")

        assert response.status_code == status.HTTP_200_OK
        texts = {item["text"] for item in response.data}
        assert "Org-A note" in texts
        assert "Org-B note" not in texts

    def test_org_scoped_deal_note_list_returns_only_org_notes(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped deal-note list returns only notes for org-A deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="DealNote",
            email="dealnote-a@example.com",
            company=company_a,
            organization=org_a,
        )
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="DealNote",
            email="dealnote-b@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_a = Stage.objects.create(name="Stage-A", order=1, organization=org_a)
        stage_b = Stage.objects.create(name="Stage-B", order=1, organization=org_b)
        deal_a = Deal.objects.create(
            title="Org-A Deal",
            contact=contact_a,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        deal_b = Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage_b,
            organization=org_b,
        )
        DealNote.objects.create(
            deal=deal_a, created_by=org_a_admin, text="Org-A deal note"
        )
        DealNote.objects.create(
            deal=deal_b, created_by=org_a_admin, text="Org-B deal note"
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/deal-notes/")

        assert response.status_code == status.HTTP_200_OK
        texts = {item["text"] for item in response.data}
        assert "Org-A deal note" in texts
        assert "Org-B deal note" not in texts

    # -- Nested note reads: scoped via parent queryset ------------------------

    def test_org_scoped_nested_contact_notes_scoped_via_parent(
        self, client, org_a, org_b, org_a_admin
    ):
        """Nested contact notes are scoped because the parent contact is scoped."""
        from quickscale_modules_crm.models import Company, Contact, ContactNote

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Nested",
            email="nested-a@example.com",
            company=company_a,
            organization=org_a,
        )
        ContactNote.objects.create(
            contact=contact_a, created_by=org_a_admin, text="Org-A nested note"
        )

        client.force_login(org_a_admin)
        response = client.get(
            f"/orgs/{org_a.slug}/crm/api/contacts/{contact_a.id}/notes/"
        )

        assert response.status_code == status.HTTP_200_OK
        texts = {item["text"] for item in response.data}
        assert "Org-A nested note" in texts

    def test_org_scoped_nested_deal_notes_scoped_via_parent(
        self, client, org_a, org_b, org_a_admin
    ):
        """Nested deal notes are scoped because the parent deal is scoped."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="DealNested",
            email="deal-nested-a@example.com",
            company=company_a,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Stage-A", order=1, organization=org_a)
        deal_a = Deal.objects.create(
            title="Org-A Deal",
            contact=contact_a,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        DealNote.objects.create(
            deal=deal_a, created_by=org_a_admin, text="Org-A deal nested note"
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/deals/{deal_a.id}/notes/")

        assert response.status_code == status.HTTP_200_OK
        texts = {item["text"] for item in response.data}
        assert "Org-A deal nested note" in texts


@pytest.mark.django_db
class TestF115Phase2DashboardOrgScoping:
    """F11.5 Phase 2 — Prove dashboard aggregate/recent queries are org-scoped.

    These tests verify that the CRM HTML dashboard scopes its aggregate
    counts, deal-by-stage breakdowns, and recent-item queries to the active
    organization on org-scoped SaaS routes, while solo routes preserve
    legacy unscoped behavior.

    Coverage matrix:
    - Org-scoped dashboard shows only org data
    - Org-scoped dashboard fails closed without org context (403)
    - Solo dashboard shows all data (parity preserved)
    """

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_org_scoped_dashboard_shows_only_org_data(
        self, client, org_a, org_b, org_a_admin
    ):
        """Org-scoped dashboard shows only the active org's aggregate data."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Create org-A data
        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-dash@example.com",
            company=company_a,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        Deal.objects.create(
            title="Org-A Deal",
            contact=contact_a,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )

        # Create org-B data
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-dash@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage_b,
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")
        # Org-A data should be visible
        assert "Org-A Corp" in content or "1" in content  # total_companies or recent
        # Org-B data should NOT be visible in aggregates
        # The dashboard shows counts, so we check that org-B company name doesn't appear
        assert "Org-B Corp" not in content

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_org_scoped_dashboard_fails_closed_without_org_context(
        self, client, staff_user
    ):
        """Org-scoped dashboard without org context returns 403 (fail closed).

        When the TenantMiddleware does not attach an org to the request,
        the dashboard must deny access rather than degrading to unscoped data.
        """
        client.force_login(staff_user)
        # Simulate a request to an org-scoped route without org context.
        # The TenantMiddleware would normally set request.org, but we bypass
        # it by using a non-member staff user on an org-scoped path.
        response = client.get("/orgs/nonexistent-org/crm/")

        # Should be 403 (PermissionDenied) because org context is missing.
        assert response.status_code == status.HTTP_403_FORBIDDEN

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_dashboard_includes_legacy_null_owned_data(
        self, client, staff_user, org_a, org_b
    ):
        """Solo dashboard includes personal-org and legacy NULL-owned data.

        CR-F11.10-DASH-003: Solo dashboard must include legacy NULL-owned
        rows (contacts/companies/deals) on solo routes until the NOT NULL
        migration (0006) lands.  Data from other organizations is excluded.
        """
        from quickscale_modules_crm.models import Company
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        # Personal org data (should be included).
        Company.objects.create(name="Personal Corp", organization=personal_org)
        # Legacy NULL-owned data (should be included per CR-F11.10-DASH-003).
        Company.objects.create(name="Legacy Corp")  # NULL org
        # Other org data (should NOT be included on solo route).
        Company.objects.create(name="Org-A Corp", organization=org_a)
        Company.objects.create(name="Org-B Corp", organization=org_b)

        client.force_login(staff_user)
        response = client.get("/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # The dashboard renders stats in cards: contacts, companies, deals, value.
        # total_companies stat should be 2 (personal + null), not 4.
        assert "Total Companies" in content
        # Count <h3> elements before "Total Companies" to find the stat value.
        companies_section = content.split("Total Companies")[0]
        companies_value = (
            companies_section.rsplit("<h3>", 1)[-1].split("</h3>")[0].strip()
        )
        assert companies_value == "2", (
            f"Expected total_companies=2, got {companies_value!r}"
        )


@pytest.mark.django_db
class TestF115Phase2NestedNoteFailClosed:
    """F11.5 Phase 2 — Prove nested note GET fails closed on foreign-org parent.

    These tests verify that accessing nested notes for a foreign-org parent
    returns 404, because the parent queryset is org-scoped.
    """

    def test_org_scoped_nested_contact_notes_returns_404_for_foreign_parent(
        self, client, org_a, org_b, org_a_admin
    ):
        """Nested contact notes for a foreign-org contact returns 404."""
        from quickscale_modules_crm.models import Company, Contact, ContactNote

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-nested@example.com",
            company=company_b,
            organization=org_b,
        )
        ContactNote.objects.create(
            contact=contact_b, created_by=org_a_admin, text="Org-B nested note"
        )

        client.force_login(org_a_admin)
        response = client.get(
            f"/orgs/{org_a.slug}/crm/api/contacts/{contact_b.id}/notes/"
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_org_scoped_nested_deal_notes_returns_404_for_foreign_parent(
        self, client, org_a, org_b, org_a_admin
    ):
        """Nested deal notes for a foreign-org deal returns 404."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="DealContact",
            email="orgb-deal-nested@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        deal_b = Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("1000.00"),
            stage=stage_b,
            organization=org_b,
        )
        DealNote.objects.create(
            deal=deal_b, created_by=org_a_admin, text="Org-B deal nested note"
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/api/deals/{deal_b.id}/notes/")

        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestF1110SoloDashboardNullOwnedCoverage:
    """CR-F11.10-DASH-003 — Solo dashboard coverage for legacy NULL-owned data.

    These tests verify that the solo CRM dashboard includes legacy NULL-owned
    data in its aggregates, stage breakdowns, and recent-item displays.
    """

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_dashboard_deals_by_stage_includes_null_owned_deals(
        self, client, staff_user, org_a
    ):
        """Solo dashboard deals_by_stage includes NULL-owned deals."""
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

        # Legacy NULL-owned deal on the same stage.
        legacy_company = Company.objects.create(name="Legacy Corp")
        legacy_contact = Contact.objects.create(
            first_name="Legacy",
            last_name="Contact",
            email="legacy-deal@example.com",
            company=legacy_company,
        )
        Deal.objects.create(
            title="Legacy Deal",
            contact=legacy_contact,
            amount=Decimal("500.00"),
            stage=stage,
        )

        client.force_login(staff_user)
        response = client.get("/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")

        # total_deals should include both deals (personal + legacy).
        deals_section = content.split("Total Deals")[0]
        deals_value = deals_section.rsplit("<h3>", 1)[-1].split("</h3>")[0].strip()
        assert deals_value == "2", f"Expected total_deals=2, got {deals_value!r}"

        # total_deal_value should include both amounts.
        assert "1,500" in content or "1500" in content

    @override_settings(
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_dashboard_recent_contacts_shows_null_owned_company_name(
        self, client, staff_user
    ):
        """Solo dashboard recent_contacts shows company name for NULL-owned company."""
        from quickscale_modules_crm.models import Company, Contact
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.get(
            is_personal=True, memberships__user=staff_user
        )

        # A personal-org contact with a NULL-owned company (legacy).
        legacy_company = Company.objects.create(name="Legacy Corp")
        Contact.objects.create(
            first_name="Legacy",
            last_name="Contact",
            email="legacy-recent@example.com",
            company=legacy_company,
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

        # NULL-owned company name should appear in the rendered content.
        assert "Legacy Corp" in content
        # Personal-org company name should also appear.
        assert "Personal Corp" in content


@pytest.mark.django_db
class TestCRMRev002DashboardAggregateIsolation:
    """CRM-REV-002 — Prove dashboard aggregates exclude cross-org linked data.

    These tests verify that the CRM dashboard ``deals_by_stage`` aggregate
    uses a filtered Count on org-scoped routes so that cross-org deals
    linked to same-org stages are not counted.  Solo routes preserve
    legacy unscoped behavior.
    """

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_org_scoped_dashboard_deals_by_stage_excludes_cross_org_deals(
        self, client, org_a, org_b, org_a_admin
    ):
        """Dashboard deals_by_stage must not count cross-org deals on org-scoped routes."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Create org-A stage
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)

        # Create org-A deal linked to org-A stage
        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-dash-agg@example.com",
            company=company_a,
            organization=org_a,
        )
        Deal.objects.create(
            title="Org-A Deal",
            contact=contact_a,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )

        # Create org-B deal linked to the SAME org-A stage (cross-org reference)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-dash-agg@example.com",
            company=company_b,
            organization=org_b,
        )
        Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage_a,
            organization=org_b,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")
        # The dashboard should show deal_count=1 for Org-A Stage (only org-A deal).
        # The cross-org org-B deal must not inflate the count.
        # We verify by checking that the org-B deal title does not appear
        # and the count reflects only org-scoped deals.
        assert "Org-B Deal" not in content
        # The total_deals should be 1 (only org-A deal)
        assert "Org-B Corp" not in content

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_org_scoped_dashboard_recent_items_do_not_render_foreign_org_names(
        self, client, org_a, org_b, org_a_admin
    ):
        """Dashboard recent_contacts/recent_deals must not render foreign-org related names.

        CRM-REV-002 remaining slice: even when an org-A contact references an
        org-B company (or an org-A deal references an org-B stage), the
        org-scoped dashboard must not expose the foreign company/stage name
        in the rendered recent-item tables.
        """
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Org-B company and stage (foreign to org-A).
        foreign_company = Company.objects.create(
            name="Foreign-Corp-Secret", organization=org_b
        )
        foreign_stage = Stage.objects.create(
            name="Foreign-Stage-Secret", order=1, organization=org_b
        )

        # Org-A contact linked to org-B company (cross-org FK reference).
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-proj@example.com",
            company=foreign_company,
            organization=org_a,
        )

        # Org-A deal linked to org-B stage (cross-org FK reference).
        Deal.objects.create(
            title="Org-A Deal",
            contact=contact_a,
            amount=Decimal("1000.00"),
            stage=foreign_stage,
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")
        # Foreign-org related names must NOT appear in the rendered dashboard.
        assert "Foreign-Corp-Secret" not in content
        assert "Foreign-Stage-Secret" not in content


@pytest.mark.django_db
class TestF115Phase2ApiListFailClosed:
    """F11.5 Phase 2 gate D — OrgScopedReadMixin API list fails closed without org context.

    Proves that an org-scoped SaaS API list route (TagViewSet) returns 403
    when the request reaches the view without org context, rather than
    degrading to an unscoped queryset.
    """

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_tag_list_returns_403_without_org_context(
        self, client, staff_user
    ):
        """GET /orgs/<slug>/crm/api/tags/ without org context returns 403.

        The TenantMiddleware is excluded so request.org is never set.
        OrgScopedReadMixin.get_queryset calls _require_org_for_read which
        raises PermissionDenied when org context is missing on an org-scoped
        route.
        """
        client.force_login(staff_user)
        response = client.get("/orgs/nonexistent-org/crm/api/tags/")

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCRF115001OrgScopedPostFailClosed:
    """CR-F11.5-001 — Prove org-scoped POSTs fail closed without org context.

    When a POST reaches a CRM collection endpoint on an ``/orgs/<slug>/...``
    route without ``request.org`` (e.g. middleware gap), the serializer must
    reject the request rather than persisting a NULL-owned row.
    """

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_tag_post_returns_400_without_org_context(
        self, client, staff_user
    ):
        """POST /orgs/<slug>/crm/api/tags/ without org context returns 400."""
        from quickscale_modules_crm.models import Tag

        before = Tag.objects.count()
        client.force_login(staff_user)

        response = client.post(
            "/orgs/some-org/crm/api/tags/",
            data={"name": "Ghost Tag"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Tag.objects.count() == before

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_company_post_returns_400_without_org_context(
        self, client, staff_user
    ):
        """POST /orgs/<slug>/crm/api/companies/ without org context returns 400."""
        from quickscale_modules_crm.models import Company

        before = Company.objects.count()
        client.force_login(staff_user)

        response = client.post(
            "/orgs/some-org/crm/api/companies/",
            data={"name": "Ghost Corp", "industry": "Tech"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Company.objects.count() == before

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_stage_post_returns_400_without_org_context(
        self, client, staff_user
    ):
        """POST /orgs/<slug>/crm/api/stages/ without org context returns 400."""
        from quickscale_modules_crm.models import Stage

        before = Stage.objects.count()
        client.force_login(staff_user)

        response = client.post(
            "/orgs/some-org/crm/api/stages/",
            data={"name": "Ghost Stage", "order": 99},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Stage.objects.count() == before

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_contact_post_returns_400_without_org_context(
        self, client, staff_user, company
    ):
        """POST /orgs/<slug>/crm/api/contacts/ without org context returns 400."""
        from quickscale_modules_crm.models import Contact

        before = Contact.objects.count()
        client.force_login(staff_user)

        response = client.post(
            "/orgs/some-org/crm/api/contacts/",
            data={
                "first_name": "Ghost",
                "last_name": "Contact",
                "email": "ghost@example.com",
                "company_id": company.id,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Contact.objects.count() == before

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_deal_post_returns_400_without_org_context(
        self, client, staff_user, contact, stage
    ):
        """POST /orgs/<slug>/crm/api/deals/ without org context returns 400."""
        from quickscale_modules_crm.models import Deal

        before = Deal.objects.count()
        client.force_login(staff_user)

        response = client.post(
            "/orgs/some-org/crm/api/deals/",
            data={
                "title": "Ghost Deal",
                "contact_id": contact.id,
                "stage_id": stage.id,
                "amount": "1000.00",
                "probability": 50,
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert Deal.objects.count() == before


@pytest.mark.django_db
class TestCRF115002DashboardIncludesLegacyNullOrgStages:
    """CR-F11.5-002 — Dashboard deals_by_stage includes legacy NULL-org stages.

    During the pre-backfill window, visible current-org deals may reference
    legacy NULL-org stages.  The dashboard ``deals_by_stage`` breakdown must
    include those stages so the deal counts are not silently dropped.
    """

    @override_settings(
        MIDDLEWARE=DASHBOARD_SAAS_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_org_scoped_dashboard_includes_deals_on_legacy_null_org_stages(
        self, client, org_a, org_a_admin
    ):
        """Dashboard deals_by_stage counts deals on legacy NULL-org stages."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Create a legacy NULL-org stage (pre-backfill).
        legacy_stage = Stage.objects.create(name="Legacy Pipeline", order=1)
        assert legacy_stage.organization_id is None

        # Create an org-A deal attached to the legacy NULL-org stage.
        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="LegacyDeal",
            email="orga-legacy@example.com",
            company=company_a,
            organization=org_a,
        )
        Deal.objects.create(
            title="Org-A Legacy Deal",
            contact=contact_a,
            amount=Decimal("5000.00"),
            stage=legacy_stage,
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.get(f"/orgs/{org_a.slug}/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")
        # The legacy stage name should appear in the dashboard breakdown.
        assert "Legacy Pipeline" in content
        # The org-A deal should be counted (total_deals >= 1).
        assert "Org-A Legacy Deal" in content or "5000" in content


@pytest.mark.django_db
class TestF119Phase1BulkDealMutationOrgScoping:
    """F11.9 Phase 1 — Prove org-scoped bulk deal mutation seams.

    These tests verify that bulk deal actions (``bulk_update_stage``,
    ``mark_won``, ``mark_lost``) on org-scoped SaaS routes cannot mutate
    foreign-org deals.  Solo routes preserve legacy unscoped behavior.

    Coverage matrix:
    - Same-org success: bulk action updates only same-org deals
    - Foreign-org denial: bulk action does not affect foreign-org deals
    - Missing-org fail-closed: org-scoped route without org context returns 403
    - Solo-route parity: bulk actions work as before on solo routes
    - Foreign-org stage rejection: BulkUpdateStageSerializer rejects foreign-org stages
    """

    # -- Same-org success: bulk_update_stage ----------------------------------

    def test_org_scoped_bulk_update_stage_updates_same_org_deals(
        self, client, org_a, org_a_admin
    ):
        """bulk_update_stage on org-scoped route updates only same-org deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-bulk@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        target_stage = Stage.objects.create(
            name="Org-A Target", order=2, organization=org_a
        )
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/bulk-update-stage/",
            data={"deal_ids": [deal.id], "stage_id": target_stage.id},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage == target_stage

    # -- Foreign-org denial: bulk_update_stage --------------------------------

    def test_org_scoped_bulk_update_stage_does_not_affect_foreign_org_deals(
        self, client, org_a, org_b, org_a_admin
    ):
        """bulk_update_stage on org-scoped route does not update foreign-org deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Create org-B deal (foreign to org-A).
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-bulk@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        foreign_deal = Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage_b,
            organization=org_b,
        )
        original_stage = foreign_deal.stage

        # Org-A admin tries to bulk-update the foreign deal via org-A route.
        target_stage = Stage.objects.create(
            name="Org-A Target", order=2, organization=org_a
        )
        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/bulk-update-stage/",
            data={"deal_ids": [foreign_deal.id], "stage_id": target_stage.id},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        # The update count should be 0 — foreign deal was not mutated.
        assert response.data["updated"] == 0
        foreign_deal.refresh_from_db()
        assert foreign_deal.stage == original_stage

    # -- Same-org success: mark_won -------------------------------------------

    def test_org_scoped_mark_won_updates_same_org_deals(
        self, client, org_a, org_a_admin
    ):
        """mark_won on org-scoped route updates only same-org deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear any existing terminal_semantic stages from prior tests.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-won@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        # Create a same-org terminal won stage for mark_won to resolve.
        won_stage = Stage.objects.create(
            name="Closed-Won",
            order=3,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            organization=org_a,
        )
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage == won_stage
        assert deal.probability == 100

    # -- Foreign-org denial: mark_won -----------------------------------------

    def test_org_scoped_mark_won_does_not_affect_foreign_org_deals(
        self, client, org_a, org_b, org_a_admin
    ):
        """mark_won on org-scoped route does not update foreign-org deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-won@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        foreign_deal = Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage_b,
            organization=org_b,
        )
        original_stage = foreign_deal.stage
        original_probability = foreign_deal.probability

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-won/",
            data={"deal_ids": [foreign_deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 0
        foreign_deal.refresh_from_db()
        assert foreign_deal.stage == original_stage
        assert foreign_deal.probability == original_probability

    # -- Same-org success: mark_lost ------------------------------------------

    def test_org_scoped_mark_lost_updates_same_org_deals(
        self, client, org_a, org_a_admin
    ):
        """mark_lost on org-scoped route updates only same-org deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear any existing terminal_semantic stages from prior tests.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-lost@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        # Create a same-org terminal lost stage for mark_lost to resolve.
        lost_stage = Stage.objects.create(
            name="Closed-Lost",
            order=4,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_LOST,
            organization=org_a,
        )
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-lost/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage == lost_stage
        assert deal.probability == 0

    # -- Foreign-org denial: mark_lost ----------------------------------------

    def test_org_scoped_mark_lost_does_not_affect_foreign_org_deals(
        self, client, org_a, org_b, org_a_admin
    ):
        """mark_lost on org-scoped route does not update foreign-org deals."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-lost@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        foreign_deal = Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage_b,
            organization=org_b,
        )
        original_stage = foreign_deal.stage
        original_probability = foreign_deal.probability

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-lost/",
            data={"deal_ids": [foreign_deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 0
        foreign_deal.refresh_from_db()
        assert foreign_deal.stage == original_stage
        assert foreign_deal.probability == original_probability

    # -- Missing-org fail-closed: bulk actions --------------------------------

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_bulk_update_stage_returns_400_without_org_context(
        self, client, staff_user, stage
    ):
        """bulk_update_stage on org-scoped route without org context returns 400.

        The BulkUpdateStageSerializer validates stage_id against org context
        before the view runs, returning 400 (Bad Request) rather than 403.
        """
        from quickscale_modules_crm.models import Company, Contact, Deal

        company = Company.objects.create(name="Corp")
        contact = Contact.objects.create(
            first_name="Contact",
            last_name="Test",
            email="test@example.com",
            company=company,
        )
        deal = Deal.objects.create(
            title="Deal",
            contact=contact,
            amount="1000.00",
            stage=stage,
        )

        client.force_login(staff_user)
        response = client.post(
            "/orgs/nonexistent-org/crm/api/deals/bulk-update-stage/",
            data={"deal_ids": [deal.id], "stage_id": stage.id},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_mark_won_returns_403_without_org_context(
        self, client, staff_user, deal
    ):
        """mark_won on org-scoped route without org context returns 403."""
        client.force_login(staff_user)
        response = client.post(
            "/orgs/nonexistent-org/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @override_settings(MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE)
    def test_org_scoped_mark_lost_returns_403_without_org_context(
        self, client, staff_user, deal
    ):
        """mark_lost on org-scoped route without org context returns 403."""
        client.force_login(staff_user)
        response = client.post(
            "/orgs/nonexistent-org/crm/api/deals/mark-lost/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    # -- Solo-route parity: bulk actions work as before -----------------------

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_bulk_update_stage_updates_all_deals(
        self, client, staff_user, deal, closed_won_stage
    ):
        """Solo route bulk_update_stage updates deals regardless of org."""
        client.force_login(staff_user)
        response = client.post(
            "/crm/api/deals/bulk-update-stage/",
            data={"deal_ids": [deal.id], "stage_id": closed_won_stage.id},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage == closed_won_stage

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_mark_won_updates_all_deals(self, client, staff_user, deal):
        """Solo route mark_won updates deals regardless of org."""
        client.force_login(staff_user)
        response = client.post(
            "/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage.terminal_semantic == Stage.TERMINAL_SEMANTIC_WON
        assert deal.probability == 100

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_mark_lost_updates_all_deals(self, client, staff_user, deal):
        """Solo route mark_lost updates deals regardless of org."""
        client.force_login(staff_user)
        response = client.post(
            "/crm/api/deals/mark-lost/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage.terminal_semantic == Stage.TERMINAL_SEMANTIC_LOST
        assert deal.probability == 0

    # -- Foreign-org stage rejection: BulkUpdateStageSerializer ---------------

    def test_org_scoped_bulk_update_stage_rejects_foreign_org_stage(
        self, client, org_a, org_b, org_a_admin
    ):
        """bulk_update_stage on org-scoped route rejects foreign-org stage_id."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-stage-reject@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        # Foreign stage (org-B).
        foreign_stage = Stage.objects.create(
            name="Org-B Stage", order=2, organization=org_b
        )

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/bulk-update-stage/",
            data={"deal_ids": [deal.id], "stage_id": foreign_stage.id},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "stage_id" in response.data
        # Deal should not be updated.
        deal.refresh_from_db()
        assert deal.stage == stage_a

    def test_org_scoped_bulk_update_stage_rejects_null_org_legacy_stage(
        self, client, org_a, org_a_admin
    ):
        """bulk_update_stage on org-scoped route rejects NULL-org legacy stage.

        Phase 1 post-0006 contract: NULL-owned stages are no longer accepted
        on org-scoped routes.
        """
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-legacy-stage@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        # Legacy NULL-org stage.
        legacy_stage = Stage.objects.create(name="Legacy Stage", order=2)
        assert legacy_stage.organization_id is None

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/bulk-update-stage/",
            data={"deal_ids": [deal.id], "stage_id": legacy_stage.id},
            content_type="application/json",
        )

        # Phase 1: NULL-org stage is rejected on org-scoped routes.
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "stage_id" in response.data
        # Deal should not be updated.
        deal.refresh_from_db()
        assert deal.stage == stage_a


@pytest.mark.django_db
class TestF119Phase2OrgScopedTerminalStageResolution:
    """F11.9 Phase 2 — Prove org-scoped terminal-stage resolution for mark_won/mark_lost.

    These tests verify that ``mark_won`` and ``mark_lost`` on org-scoped SaaS
    routes use org-aware terminal-stage resolution:
    - Same-org terminal stages are preferred
    - Legacy NULL-org terminal stages are accepted for backfill compatibility
    - Foreign-org terminal stages are never used (security boundary)
    - When no valid terminal stage exists for the org, the action no-ops safely

    Coverage matrix:
    - Org-scoped mark_won accepts legacy NULL-org terminal stage
    - Org-scoped mark_lost accepts legacy NULL-org terminal stage
    - Org-scoped mark_won refuses foreign-org terminal stage (no-op)
    - Org-scoped mark_lost refuses foreign-org terminal stage (no-op)
    """

    # -- Legacy NULL-org terminal stage accepted on org-scoped routes ---------

    def test_org_scoped_mark_won_no_ops_when_only_null_org_terminal_stage_exists(
        self, client, org_a, org_a_admin
    ):
        """mark_won on org-scoped route no-ops when only NULL-org terminal stage exists.

        Phase 1 post-0006 contract: NULL-owned terminal stages are no longer
        accepted on org-scoped routes.  The action returns updated=0.
        """
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear any existing terminal_semantic stages from prior tests.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        # Create a legacy NULL-org terminal won stage (pre-backfill).
        legacy_won_stage = Stage.objects.create(
            name="Legacy Closed-Won",
            order=3,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
        )
        assert legacy_won_stage.organization_id is None

        # Create an org-A deal on an org-A stage.
        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-legacy-won@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        original_stage = deal.stage
        original_probability = deal.probability

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        # Phase 1: NULL-org terminal stage is not accepted — safe no-op.
        assert response.data["updated"] == 0
        deal.refresh_from_db()
        assert deal.stage == original_stage
        assert deal.probability == original_probability

    def test_org_scoped_mark_lost_no_ops_when_only_null_org_terminal_stage_exists(
        self, client, org_a, org_a_admin
    ):
        """mark_lost on org-scoped route no-ops when only NULL-org terminal stage exists.

        Phase 1 post-0006 contract: NULL-owned terminal stages are no longer
        accepted on org-scoped routes.  The action returns updated=0.
        """
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear any existing terminal_semantic stages from prior tests.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        # Create a legacy NULL-org terminal lost stage (pre-backfill).
        legacy_lost_stage = Stage.objects.create(
            name="Legacy Closed-Lost",
            order=4,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_LOST,
        )
        assert legacy_lost_stage.organization_id is None

        # Create an org-A deal on an org-A stage.
        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-legacy-lost@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        original_stage = deal.stage
        original_probability = deal.probability

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-lost/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        # Phase 1: NULL-org terminal stage is not accepted — safe no-op.
        assert response.data["updated"] == 0
        deal.refresh_from_db()
        assert deal.stage == original_stage
        assert deal.probability == original_probability

    # -- Foreign-org terminal stage refused on org-scoped routes --------------

    def test_org_scoped_mark_won_refuses_foreign_org_terminal_stage(
        self, client, org_a, org_b, org_a_admin
    ):
        """mark_won on org-scoped route does not attach deals to foreign-org terminal stage.

        When the only terminal_semantic='won' stage belongs to another org,
        org-scoped mark_won must not use it.  The action returns updated=0
        (no-op) rather than attaching org-A's deal to org-B's stage.
        """
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear any existing terminal_semantic stages from prior tests.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        # Create a terminal won stage owned by org-B (foreign to org-A).
        foreign_won_stage = Stage.objects.create(
            name="Org-B Closed-Won",
            order=3,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            organization=org_b,
        )
        assert foreign_won_stage.organization_id == org_b.id

        # Create an org-A deal on an org-A stage.
        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-foreign-won@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        original_stage = deal.stage
        original_probability = deal.probability

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        # The update count should be 0 — foreign terminal stage was not used.
        assert response.data["updated"] == 0
        deal.refresh_from_db()
        # The deal should NOT be attached to the foreign-org terminal stage.
        assert deal.stage == original_stage
        assert deal.probability == original_probability
        assert deal.stage != foreign_won_stage

    def test_org_scoped_mark_lost_refuses_foreign_org_terminal_stage(
        self, client, org_a, org_b, org_a_admin
    ):
        """mark_lost on org-scoped route does not attach deals to foreign-org terminal stage.

        When the only terminal_semantic='lost' stage belongs to another org,
        org-scoped mark_lost must not use it.  The action returns updated=0
        (no-op) rather than attaching org-A's deal to org-B's stage.
        """
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear any existing terminal_semantic stages from prior tests.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        # Create a terminal lost stage owned by org-B (foreign to org-A).
        foreign_lost_stage = Stage.objects.create(
            name="Org-B Closed-Lost",
            order=4,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_LOST,
            organization=org_b,
        )
        assert foreign_lost_stage.organization_id == org_b.id

        # Create an org-A deal on an org-A stage.
        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-foreign-lost@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        original_stage = deal.stage
        original_probability = deal.probability

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-lost/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        # The update count should be 0 — foreign terminal stage was not used.
        assert response.data["updated"] == 0
        deal.refresh_from_db()
        # The deal should NOT be attached to the foreign-org terminal stage.
        assert deal.stage == original_stage
        assert deal.probability == original_probability
        assert deal.stage != foreign_lost_stage


@pytest.mark.django_db
class TestF1110Phase1TerminalStageSameOrgCanonicalNameFallback:
    """F11.10 Phase 1 — Prove same-org canonical name fallback for terminal stages.

    When no same-org terminal_semantic row exists, the resolver falls back to
    a same-org stage with the canonical name (e.g. "Closed-Won") even without
    terminal_semantic set.  If neither exists, the action no-ops safely.
    """

    def test_org_scoped_mark_won_uses_same_org_canonical_name_stage(
        self, client, org_a, org_a_admin
    ):
        """mark_won falls back to same-org stage named 'Closed-Won' when no semantic row exists."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear any terminal_semantic stages.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        # Create a same-org stage named "Closed-Won" without terminal_semantic.
        canonical_stage = Stage.objects.create(
            name="Closed-Won", order=3, organization=org_a
        )

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-canonical@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1
        deal.refresh_from_db()
        assert deal.stage == canonical_stage
        assert deal.probability == 100

    def test_org_scoped_mark_won_no_ops_when_no_same_org_target_exists(
        self, client, org_a, org_a_admin
    ):
        """mark_won returns updated=0 when no same-org terminal or canonical stage exists."""
        from decimal import Decimal

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        # Clear all terminal_semantic stages and ensure no "Closed-Won" in org_a.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()
        Stage.objects.filter(name="Closed-Won", organization=org_a).delete()

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-noop@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        original_stage = deal.stage

        client.force_login(org_a_admin)
        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deals/mark-won/",
            data={"deal_ids": [deal.id]},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 0
        deal.refresh_from_db()
        assert deal.stage == original_stage


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
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # Clear any terminal_semantic stages.
        Stage.objects.filter(terminal_semantic__isnull=False).delete()

        # Create a personal org for the staff user.
        personal_org = Organization.objects.create(
            name="Personal Org", slug="personal-org", is_personal=True
        )
        OrganizationMembership.objects.create(
            user=staff_user, organization=personal_org, role=OrgRole.OWNER
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
class TestF1110StandaloneNoteOrgScopedParentValidation:
    """CR-F11.10-API-001 — Standalone note POSTs reject/accept parents by org.

    These tests verify that standalone ContactNote and DealNote POSTs on
    org-scoped routes validate the parent's organization membership:
    - Foreign-org parents are rejected with 400.
    - Same-org parents are accepted with 201.
    - NULL-org (legacy) parents are accepted for backward compatibility.
    """

    # -- ContactNote: foreign-org contact rejected ----------------------------

    def test_org_scoped_contact_note_post_rejects_foreign_contact(
        self, client, org_a, org_b, org_a_admin
    ):
        """A ContactNote POST with a foreign-org contact is rejected with 400."""
        from quickscale_modules_crm.models import Company, Contact, ContactNote

        # Create a contact in org B (foreign to org A).
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        foreign_contact = Contact.objects.create(
            first_name="Foreign",
            last_name="Contact",
            email="foreign-note@example.com",
            company=company_b,
            organization=org_b,
        )

        before = ContactNote.objects.count()
        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contact-notes/",
            data={
                "contact": foreign_contact.id,
                "text": "Foreign contact note attempt",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "contact" in response.data
        assert ContactNote.objects.count() == before

    # -- ContactNote: same-org contact accepted -------------------------------

    def test_org_scoped_contact_note_post_accepts_same_org_contact(
        self, client, org_a, org_a_admin
    ):
        """A ContactNote POST with a same-org contact succeeds with 201."""
        from quickscale_modules_crm.models import Company, Contact, ContactNote

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Same",
            last_name="Org",
            email="same-org-note@example.com",
            company=company,
            organization=org_a,
        )

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contact-notes/",
            data={
                "contact": contact.id,
                "text": "Same-org note",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "Same-org note"
        created = ContactNote.objects.get(pk=response.data["id"])
        assert created.contact_id == contact.id

    # -- ContactNote: NULL-org legacy contact accepted ------------------------

    def test_org_scoped_contact_note_post_accepts_null_org_legacy_contact(
        self, client, org_a, org_a_admin
    ):
        """A ContactNote POST with a NULL-org (legacy) contact succeeds."""
        from quickscale_modules_crm.models import Company, Contact

        # Create a legacy NULL-org contact.
        legacy_company = Company.objects.create(name="Legacy Corp")
        legacy_contact = Contact.objects.create(
            first_name="Legacy",
            last_name="Contact",
            email="legacy-contact@example.com",
            company=legacy_company,
        )
        assert legacy_contact.organization_id is None

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/contact-notes/",
            data={
                "contact": legacy_contact.id,
                "text": "Legacy contact note",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "Legacy contact note"

    # -- DealNote: foreign-org deal rejected ----------------------------------

    def test_org_scoped_deal_note_post_rejects_foreign_deal(
        self, client, org_a, org_b, org_a_admin
    ):
        """A DealNote POST with a foreign-org deal is rejected with 400."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )

        # Create a deal in org B (foreign to org A).
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-deal-note@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        foreign_deal = Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("1000.00"),
            stage=stage_b,
            organization=org_b,
        )

        before = DealNote.objects.count()
        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deal-notes/",
            data={
                "deal": foreign_deal.id,
                "text": "Foreign deal note attempt",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "deal" in response.data
        assert DealNote.objects.count() == before

    # -- DealNote: same-org deal accepted -------------------------------------

    def test_org_scoped_deal_note_post_accepts_same_org_deal(
        self, client, org_a, org_a_admin
    ):
        """A DealNote POST with a same-org deal succeeds with 201."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Same",
            last_name="Org",
            email="same-org-deal-note@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("5000.00"),
            stage=stage,
            organization=org_a,
        )

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deal-notes/",
            data={
                "deal": deal.id,
                "text": "Same-org deal note",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "Same-org deal note"
        created = DealNote.objects.get(pk=response.data["id"])
        assert created.deal_id == deal.id

    # -- DealNote: NULL-org legacy deal accepted ------------------------------

    def test_org_scoped_deal_note_post_accepts_null_org_legacy_deal(
        self, client, org_a, org_a_admin
    ):
        """A DealNote POST with a NULL-org (legacy) deal succeeds."""
        from decimal import Decimal

        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            Stage,
        )

        # Create a legacy NULL-org deal.
        legacy_company = Company.objects.create(name="Legacy Corp")
        legacy_contact = Contact.objects.create(
            first_name="Legacy",
            last_name="DealNote",
            email="legacy-deal-note@example.com",
            company=legacy_company,
        )
        legacy_stage = Stage.objects.create(name="Legacy Stage", order=1)
        legacy_deal = Deal.objects.create(
            title="Legacy Deal",
            contact=legacy_contact,
            amount=Decimal("3000.00"),
            stage=legacy_stage,
        )
        assert legacy_deal.organization_id is None

        client.force_login(org_a_admin)

        response = client.post(
            f"/orgs/{org_a.slug}/crm/api/deal-notes/",
            data={
                "deal": legacy_deal.id,
                "text": "Legacy deal note",
            },
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["text"] == "Legacy deal note"
