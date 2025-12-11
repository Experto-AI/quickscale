"""Unit tests for CRM module models"""

from decimal import Decimal

import pytest

from quickscale_modules_crm.models import (
    Company,
    Contact,
    ContactNote,
    Deal,
    DealNote,
    Stage,
    Tag,
)


@pytest.mark.django_db
class TestTagModel:
    """Tests for Tag model"""

    def test_create_tag(self):
        """Test creating a tag"""
        tag = Tag.objects.create(name="VIP")
        assert tag.name == "VIP"
        assert str(tag) == "VIP"
        assert tag.created_at is not None

    def test_tag_unique_name(self):
        """Test that tag names are unique"""
        Tag.objects.create(name="VIP")
        with pytest.raises(Exception):
            Tag.objects.create(name="VIP")


@pytest.mark.django_db
class TestCompanyModel:
    """Tests for Company model"""

    def test_create_company(self):
        """Test creating a company"""
        company = Company.objects.create(
            name="Acme Corp",
            industry="Technology",
            website="https://acme.com",
        )
        assert company.name == "Acme Corp"
        assert company.industry == "Technology"
        assert str(company) == "Acme Corp"

    def test_company_contacts_relationship(self, company, contact):
        """Test company has contacts"""
        assert contact in company.contacts.all()
        assert company.contacts.count() == 1


@pytest.mark.django_db
class TestContactModel:
    """Tests for Contact model"""

    def test_create_contact(self, company):
        """Test creating a contact"""
        contact = Contact.objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+1234567890",
            company=company,
        )
        assert contact.full_name == "Jane Smith"
        assert str(contact) == "Jane Smith"

    def test_contact_default_status(self, company):
        """Test contact default status is 'new'"""
        contact = Contact.objects.create(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            company=company,
        )
        assert contact.status == "new"

    def test_contact_tags(self, contact, tag):
        """Test contact can have tags"""
        contact.tags.add(tag)
        assert tag in contact.tags.all()
        assert contact in tag.contacts.all()


@pytest.mark.django_db
class TestStageModel:
    """Tests for Stage model"""

    def test_create_stage(self):
        """Test creating a stage"""
        stage = Stage.objects.create(name="Negotiation", order=2)
        assert stage.name == "Negotiation"
        assert stage.order == 2
        assert str(stage) == "Negotiation"

    def test_stage_ordering(self):
        """Test stages are ordered by order field"""
        # Delete all stages first to ensure clean state
        Stage.objects.all().delete()
        stage3 = Stage.objects.create(name="C", order=3)
        stage1 = Stage.objects.create(name="A", order=1)
        stage2 = Stage.objects.create(name="B", order=2)
        stages = list(Stage.objects.all())
        assert stages == [stage1, stage2, stage3]


@pytest.mark.django_db
class TestDealModel:
    """Tests for Deal model"""

    def test_create_deal(self, contact, stage, user):
        """Test creating a deal"""
        deal = Deal.objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount=Decimal("50000.00"),
            stage=stage,
            probability=75,
            owner=user,
        )
        assert deal.title == "Enterprise Deal"
        assert deal.amount == Decimal("50000.00")
        assert str(deal) == "Enterprise Deal"

    def test_deal_company_property(self, deal, company):
        """Test deal company property returns contact's company"""
        assert deal.company == company

    def test_deal_default_probability(self, contact, stage):
        """Test deal default probability is 50"""
        deal = Deal.objects.create(
            title="Test Deal",
            contact=contact,
            stage=stage,
        )
        assert deal.probability == 50

    def test_deal_tags(self, deal, tag):
        """Test deal can have tags"""
        deal.tags.add(tag)
        assert tag in deal.tags.all()
        assert deal in tag.deals.all()


@pytest.mark.django_db
class TestContactNoteModel:
    """Tests for ContactNote model"""

    def test_create_contact_note(self, contact, user):
        """Test creating a contact note"""
        note = ContactNote.objects.create(
            contact=contact,
            created_by=user,
            text="Discussed pricing",
        )
        assert note.text == "Discussed pricing"
        assert note.contact == contact
        assert note.created_by == user

    def test_contact_notes_relationship(self, contact_note, contact):
        """Test contact has notes"""
        assert contact_note in contact.notes.all()


@pytest.mark.django_db
class TestDealNoteModel:
    """Tests for DealNote model"""

    def test_create_deal_note(self, deal, user):
        """Test creating a deal note"""
        note = DealNote.objects.create(
            deal=deal,
            created_by=user,
            text="Follow up required",
        )
        assert note.text == "Follow up required"
        assert note.deal == deal
        assert note.created_by == user

    def test_deal_notes_relationship(self, deal_note, deal):
        """Test deal has notes"""
        assert deal_note in deal.notes.all()
