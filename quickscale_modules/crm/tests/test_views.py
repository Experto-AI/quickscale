"""Unit tests for CRM module API views"""

import pytest
from django.test import override_settings
from django.urls import reverse
from rest_framework import status

from quickscale_modules_crm.models import Deal, Stage


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
    def test_contact_list_allows_authenticated_user_without_host_defaults(
        self, authenticated_client, contact
    ):
        """Authenticated CRM access should remain available without global DRF settings."""
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
