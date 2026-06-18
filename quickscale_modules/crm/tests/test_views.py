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
        self, authenticated_client, tag
    ):
        """Renaming a tag to a duplicate via the org-scoped route returns a controlled 4xx."""
        from quickscale_modules_crm.models import Tag

        Tag.objects.create(name="Hot Lead")
        response = authenticated_client.patch(
            f"/orgs/acme-corp/crm/api/tags/{tag.id}/",
            {"name": "Hot Lead"},
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "name" in response.data

    def test_update_tag_same_name_via_org_scoped_route_is_valid(
        self, authenticated_client, tag
    ):
        """Updating a tag without changing its name via the org-scoped route succeeds."""
        response = authenticated_client.patch(
            f"/orgs/acme-corp/crm/api/tags/{tag.id}/",
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
        self, authenticated_client, contact, user
    ):
        """Mark-won should target the semantic stage even when names drift."""
        Stage.objects.all().delete()
        exact_name_stage = Stage.objects.create(name="Closed-Won", order=3)
        semantic_stage = Stage.objects.create(
            name="Deal Signed",
            order=9,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
        )
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=exact_name_stage,
            probability=75,
            owner=user,
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
        self, authenticated_client, contact, user
    ):
        """Mark-lost should target the semantic stage even when names drift."""
        Stage.objects.all().delete()
        Stage.objects.create(name="Closed-Lost", order=4)
        semantic_stage = Stage.objects.create(
            name="No Decision",
            order=10,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_LOST,
        )
        open_stage = Stage.objects.create(name="Prospecting", order=1)
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=open_stage,
            probability=75,
            owner=user,
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
        self, authenticated_client, contact, user
    ):
        """Missing semantic rows should self-heal by creating the canonical won stage."""
        Stage.objects.all().delete()
        renamed_stage = Stage.objects.create(name="Deal Signed", order=9)
        open_stage = Stage.objects.create(name="Prospecting", order=1)
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=open_stage,
            probability=75,
            owner=user,
        )

        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-won"),
            {"deal_ids": [deal.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        deal.refresh_from_db()
        renamed_stage.refresh_from_db()
        healed_stage = Stage.objects.get(terminal_semantic=Stage.TERMINAL_SEMANTIC_WON)

        assert renamed_stage.terminal_semantic is None
        assert healed_stage.name == "Closed-Won"
        assert healed_stage.order == 3
        assert deal.stage == healed_stage
        assert deal.probability == 100

    def test_mark_lost_self_heals_missing_terminal_semantic_with_canonical_stage(
        self, authenticated_client, contact, user
    ):
        """Missing semantic rows should self-heal by creating the canonical lost stage."""
        Stage.objects.all().delete()
        renamed_stage = Stage.objects.create(name="No Decision", order=10)
        open_stage = Stage.objects.create(name="Prospecting", order=1)
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount="50000.00",
            stage=open_stage,
            probability=75,
            owner=user,
        )

        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-lost"),
            {"deal_ids": [deal.id]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        deal.refresh_from_db()
        renamed_stage.refresh_from_db()
        healed_stage = Stage.objects.get(terminal_semantic=Stage.TERMINAL_SEMANTIC_LOST)

        assert renamed_stage.terminal_semantic is None
        assert healed_stage.name == "Closed-Lost"
        assert healed_stage.order == 4
        assert deal.stage == healed_stage
        assert deal.probability == 0


@pytest.mark.django_db
class TestCRMPageSizeSettings:
    """Tests for CRM module-owned page size settings."""

    @override_settings(CRM_CONTACTS_PER_PAGE=1, REST_FRAMEWORK={})
    def test_contact_list_respects_contacts_per_page_setting(
        self, authenticated_client, company
    ):
        """Contact pagination should use the module setting instead of global DRF config."""
        from quickscale_modules_crm.models import Contact

        Contact.objects.create(
            first_name="Alice",
            last_name="Able",
            email="alice@example.com",
            company=company,
        )
        Contact.objects.create(
            first_name="Bob",
            last_name="Baker",
            email="bob@example.com",
            company=company,
        )

        response = authenticated_client.get(reverse("quickscale_crm:contact-list"))

        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    @override_settings(CRM_DEALS_PER_PAGE=1, REST_FRAMEWORK={})
    def test_deal_list_respects_deals_per_page_setting(
        self, authenticated_client, contact, stage, user
    ):
        """Deal pagination should use the module setting instead of global DRF config."""
        from quickscale_modules_crm.models import Deal

        Deal.objects.create(
            title="First Deal",
            contact=contact,
            amount="1000.00",
            stage=stage,
            owner=user,
        )
        Deal.objects.create(
            title="Second Deal",
            contact=contact,
            amount="2000.00",
            stage=stage,
            owner=user,
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
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_saas_dashboard_path_resolves(self, client, user):
        """The SaaS CRM dashboard should be reachable at /orgs/<slug>/crm/."""
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get("/orgs/acme-corp/crm/")

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

    def test_saas_api_tags_path_resolves(self, authenticated_client, tag):
        """The SaaS CRM tags API should be reachable at /orgs/<slug>/crm/api/tags/."""
        response = authenticated_client.get("/orgs/acme-corp/crm/api/tags/")

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
        MIDDLEWARE=DASHBOARD_TEST_MIDDLEWARE,
        TEMPLATES=DASHBOARD_TEST_TEMPLATES,
    )
    def test_saas_dashboard_renders_org_scoped_urls(self, client, user):
        """The SaaS CRM dashboard should render org-scoped URLs in links and examples."""
        user.is_staff = True
        user.save(update_fields=["is_staff"])
        client.force_login(user)

        response = client.get("/orgs/acme-corp/crm/")

        assert response.status_code == status.HTTP_200_OK
        content = response.content.decode("utf-8")
        # Verify org-scoped URLs are present
        assert 'href="/orgs/acme-corp/crm/"' in content
        assert 'href="/orgs/acme-corp/crm/api/"' in content
        assert "/orgs/acme-corp/crm/api/contacts/" in content
        assert "/orgs/acme-corp/crm/api/companies/" in content
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
    def test_solo_route_create_does_not_stamp_organization(self, client, staff_user):
        """Solo-route creates must NOT stamp organization_id.

        In solo mode the TenantMiddleware attaches a personal org to
        ``request.org``, but stamping is scoped to ``/orgs/`` routes only.
        A solo ``/crm/api/tags/`` create must leave ``organization_id`` NULL.
        """
        from quickscale_modules_crm.models import Tag

        client.force_login(staff_user)

        response = client.post(
            "/crm/api/tags/",
            data={"name": "Solo Tag"},
            content_type="application/json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        created = Tag.objects.get(pk=response.data["id"])
        assert created.organization_id is None
