"""Unit tests for CRM module API views"""

import pytest
from rest_framework import status
from django.urls import reverse


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

    def test_mark_won(self, authenticated_client, deal):
        """Test marking deals as won"""
        # Ensure Closed-Won stage exists
        from quickscale_modules_crm.models import Stage

        Stage.objects.get_or_create(name="Closed-Won", defaults={"order": 3})

        data = {"deal_ids": [deal.id]}
        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-won"), data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1

        # Verify deal was marked won
        deal.refresh_from_db()
        assert deal.stage.name == "Closed-Won"
        assert deal.probability == 100

    def test_mark_lost(self, authenticated_client, deal):
        """Test marking deals as lost"""
        # Ensure Closed-Lost stage exists
        from quickscale_modules_crm.models import Stage

        Stage.objects.get_or_create(name="Closed-Lost", defaults={"order": 4})

        data = {"deal_ids": [deal.id]}
        response = authenticated_client.post(
            reverse("quickscale_crm:deal-mark-lost"), data, format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["updated"] == 1

        # Verify deal was marked lost
        deal.refresh_from_db()
        assert deal.stage.name == "Closed-Lost"
        assert deal.probability == 0
