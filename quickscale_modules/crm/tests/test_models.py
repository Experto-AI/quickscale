"""Unit tests for CRM module models"""

from decimal import Decimal

import pytest
from django.db import IntegrityError

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

    def test_create_tag(self, org_a):
        """Test creating a tag"""
        tag = Tag.all_objects.create(name="VIP", organization=org_a)
        assert tag.name == "VIP"
        assert str(tag) == "VIP"
        assert tag.created_at is not None

    def test_tag_unique_name(self, org_a):
        """Test that tag names are unique within the same owner bucket."""
        Tag.all_objects.create(name="VIP", organization=org_a)
        with pytest.raises(IntegrityError):
            Tag.all_objects.create(name="VIP", organization=org_a)

    def test_tag_unique_name_field_is_no_longer_field_level_unique(self):
        """Tag.name is no longer field-level unique; uniqueness is via constraint."""
        field = Tag._meta.get_field("name")
        assert field.unique is False

    def test_tag_owner_bucket_constraint_exists(self):
        """Tag has two partial UniqueConstraints for owner-bucket uniqueness."""
        constraint_names = [c.name for c in Tag._meta.constraints]
        assert "crm_tag_name_unique_null_org" in constraint_names
        assert "crm_tag_name_organization_unique" in constraint_names

    def test_tag_same_name_different_orgs_allowed(self, org_a, org_b):
        """Same tag name is allowed across different organizations."""
        tag_a = Tag.all_objects.create(name="VIP", organization=org_a)
        tag_b = Tag.all_objects.create(name="VIP", organization=org_b)
        assert tag_a.pk != tag_b.pk

    def test_tag_duplicate_name_same_org_blocked(self, org_a):
        """Duplicate tag name within the same org is blocked at DB level."""
        Tag.all_objects.create(name="VIP", organization=org_a)
        with pytest.raises(IntegrityError):
            Tag.all_objects.create(name="VIP", organization=org_a)


@pytest.mark.django_db
class TestCompanyModel:
    """Tests for Company model"""

    def test_create_company(self, org_a):
        """Test creating a company"""
        company = Company.all_objects.create(
            name="Acme Corp",
            industry="Technology",
            website="https://acme.com",
            organization=org_a,
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
        contact = Contact.all_objects.create(
            first_name="Jane",
            last_name="Smith",
            email="jane@example.com",
            phone="+1234567890",
            company=company,
            organization=company.organization,
        )
        assert contact.full_name == "Jane Smith"
        assert str(contact) == "Jane Smith"

    def test_contact_default_status(self, company):
        """Test contact default status is 'new'"""
        contact = Contact.all_objects.create(
            first_name="Test",
            last_name="User",
            email="test@example.com",
            company=company,
            organization=company.organization,
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

    def test_create_stage(self, org_a):
        """Test creating a stage"""
        stage = Stage.all_objects.create(
            name="Negotiation", order=2, organization=org_a
        )
        assert stage.name == "Negotiation"
        assert stage.order == 2
        assert str(stage) == "Negotiation"

    def test_stage_ordering(self, org_a):
        """Test stages are ordered by order field"""
        Stage.all_objects.filter(organization=org_a).delete()
        stage3 = Stage.all_objects.create(name="C", order=3, organization=org_a)
        stage1 = Stage.all_objects.create(name="A", order=1, organization=org_a)
        stage2 = Stage.all_objects.create(name="B", order=2, organization=org_a)
        stages = list(Stage.all_objects.filter(organization=org_a))
        assert stages == [stage1, stage2, stage3]

    def test_stage_terminal_semantic_defaults_to_null_and_stays_hidden(self, org_a):
        """Stage terminal semantics should stay nullable and non-editable by default."""
        stage = Stage.all_objects.create(name="Qualified", order=2, organization=org_a)
        field = Stage._meta.get_field("terminal_semantic")

        assert stage.terminal_semantic is None
        assert field.null is True
        assert field.blank is True
        assert field.editable is False
        assert field.unique is False
        assert list(field.choices) == Stage.TERMINAL_SEMANTIC_CHOICES

    def test_stage_terminal_semantic_must_be_unique_when_present(self, org_a):
        """Only one stage per terminal semantic should be allowed per org."""
        Stage.all_objects.filter(organization=org_a).delete()

        Stage.all_objects.create(
            name="Closed-Won",
            order=3,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            organization=org_a,
        )
        Stage.all_objects.create(name="Negotiation", order=2, organization=org_a)

        with pytest.raises(IntegrityError):
            Stage.all_objects.create(
                name="Deal Signed",
                order=9,
                terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
                organization=org_a,
            )

    def test_stage_terminal_semantic_constraints_exist(self):
        """Stage has two partial UniqueConstraints for owner-bucket uniqueness."""
        constraint_names = [c.name for c in Stage._meta.constraints]
        assert "crm_stage_terminal_semantic_unique_null_org" in constraint_names
        assert "crm_stage_terminal_semantic_organization_unique" in constraint_names

    def test_stage_same_terminal_semantic_different_orgs_allowed(self, org_a, org_b):
        """Same terminal semantic is allowed across different organizations."""
        Stage.all_objects.filter(organization=org_a).delete()
        Stage.all_objects.filter(organization=org_b).delete()

        stage_a = Stage.all_objects.create(
            name="Closed-Won",
            order=3,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            organization=org_a,
        )
        stage_b = Stage.all_objects.create(
            name="Deal Signed",
            order=9,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            organization=org_b,
        )
        assert stage_a.pk != stage_b.pk


@pytest.mark.django_db
class TestDealModel:
    """Tests for Deal model"""

    def test_create_deal(self, contact, stage, user):
        """Test creating a deal"""
        deal = Deal.all_objects.create(
            title="Enterprise Deal",
            contact=contact,
            amount=Decimal("50000.00"),
            stage=stage,
            probability=75,
            owner=user,
            organization=contact.organization,
        )
        assert deal.title == "Enterprise Deal"
        assert deal.amount == Decimal("50000.00")
        assert str(deal) == "Enterprise Deal"

    def test_deal_company_property(self, deal, company):
        """Test deal company property returns contact's company"""
        assert deal.company == company

    def test_deal_default_probability(self, contact, stage):
        """Test deal default probability is 50"""
        deal = Deal.all_objects.create(
            title="Test Deal",
            contact=contact,
            stage=stage,
            organization=contact.organization,
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
