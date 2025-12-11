"""Unit tests for CRM module serializers"""

import pytest
from rest_framework.test import APIRequestFactory

from quickscale_modules_crm.serializers import (
    CompanySerializer,
    ContactDetailSerializer,
    ContactListSerializer,
    ContactNoteSerializer,
    DealDetailSerializer,
    DealListSerializer,
    DealNoteSerializer,
    StageSerializer,
    TagSerializer,
)


@pytest.mark.django_db
class TestTagSerializer:
    """Tests for TagSerializer"""

    def test_serialize_tag(self, tag):
        """Test serializing a tag"""
        serializer = TagSerializer(tag)
        assert serializer.data["name"] == "VIP"
        assert "created_at" in serializer.data

    def test_create_tag(self):
        """Test creating a tag via serializer"""
        data = {"name": "Hot Lead"}
        serializer = TagSerializer(data=data)
        assert serializer.is_valid()
        tag = serializer.save()
        assert tag.name == "Hot Lead"


@pytest.mark.django_db
class TestCompanySerializer:
    """Tests for CompanySerializer"""

    def test_serialize_company(self, company):
        """Test serializing a company"""
        serializer = CompanySerializer(company)
        assert serializer.data["name"] == "Acme Corp"
        assert serializer.data["industry"] == "Technology"
        assert serializer.data["contact_count"] == 0

    def test_company_contact_count(self, company, contact):
        """Test company contact count is computed correctly"""
        serializer = CompanySerializer(company)
        assert serializer.data["contact_count"] == 1


@pytest.mark.django_db
class TestContactSerializer:
    """Tests for ContactSerializer"""

    def test_serialize_contact_list(self, contact):
        """Test serializing a contact for list view"""
        serializer = ContactListSerializer(contact)
        assert serializer.data["first_name"] == "John"
        assert serializer.data["last_name"] == "Doe"
        assert serializer.data["full_name"] == "John Doe"
        assert serializer.data["company_name"] == "Acme Corp"

    def test_serialize_contact_detail(self, contact):
        """Test serializing a contact for detail view"""
        serializer = ContactDetailSerializer(contact)
        assert serializer.data["first_name"] == "John"
        assert "company" in serializer.data
        assert serializer.data["company"]["name"] == "Acme Corp"

    def test_contact_tag_names(self, contact, tag):
        """Test contact tag names are serialized"""
        contact.tags.add(tag)
        serializer = ContactListSerializer(contact)
        assert "VIP" in serializer.data["tag_names"]


@pytest.mark.django_db
class TestStageSerializer:
    """Tests for StageSerializer"""

    def test_serialize_stage(self, stage):
        """Test serializing a stage"""
        serializer = StageSerializer(stage)
        assert serializer.data["name"] == "Prospecting"
        assert serializer.data["order"] == 1
        assert serializer.data["deal_count"] == 0

    def test_stage_deal_count(self, stage, deal):
        """Test stage deal count is computed correctly"""
        serializer = StageSerializer(stage)
        assert serializer.data["deal_count"] == 1


@pytest.mark.django_db
class TestDealSerializer:
    """Tests for DealSerializer"""

    def test_serialize_deal_list(self, deal):
        """Test serializing a deal for list view"""
        serializer = DealListSerializer(deal)
        assert serializer.data["title"] == "Enterprise Deal"
        assert serializer.data["contact_name"] == "John Doe"
        assert serializer.data["company_name"] == "Acme Corp"
        assert serializer.data["stage_name"] == "Prospecting"

    def test_serialize_deal_detail(self, deal):
        """Test serializing a deal for detail view"""
        serializer = DealDetailSerializer(deal)
        assert serializer.data["title"] == "Enterprise Deal"
        assert "contact" in serializer.data
        assert "stage" in serializer.data


@pytest.mark.django_db
class TestContactNoteSerializer:
    """Tests for ContactNoteSerializer"""

    def test_serialize_contact_note(self, contact_note):
        """Test serializing a contact note"""
        serializer = ContactNoteSerializer(contact_note)
        assert serializer.data["text"] == "Discussed pricing options"
        assert "created_by_name" in serializer.data

    def test_create_contact_note(self, contact, user):
        """Test creating a contact note via serializer"""
        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = user

        data = {"contact": contact.id, "text": "New note"}
        serializer = ContactNoteSerializer(data=data, context={"request": request})
        assert serializer.is_valid(), serializer.errors
        note = serializer.save()
        assert note.text == "New note"
        assert note.created_by == user


@pytest.mark.django_db
class TestDealNoteSerializer:
    """Tests for DealNoteSerializer"""

    def test_serialize_deal_note(self, deal_note):
        """Test serializing a deal note"""
        serializer = DealNoteSerializer(deal_note)
        assert serializer.data["text"] == "Follow up next week"
        assert "created_by_name" in serializer.data

    def test_create_deal_note(self, deal, user):
        """Test creating a deal note via serializer"""
        factory = APIRequestFactory()
        request = factory.post("/")
        request.user = user

        data = {"deal": deal.id, "text": "New deal note"}
        serializer = DealNoteSerializer(data=data, context={"request": request})
        assert serializer.is_valid(), serializer.errors
        note = serializer.save()
        assert note.text == "New deal note"
        assert note.created_by == user
