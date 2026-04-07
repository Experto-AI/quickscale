"""Unit tests for CRM module models"""

from decimal import Decimal
from importlib import import_module

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


stage_terminal_semantic_migration = import_module(
    "quickscale_modules_crm.migrations.0002_stage_terminal_semantic"
)


class _StageMigrationApps:
    @staticmethod
    def get_model(app_label, model_name):
        assert app_label == "quickscale_modules_crm"
        assert model_name == "Stage"
        return Stage


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

    def test_stage_terminal_semantic_defaults_to_null_and_stays_hidden(self):
        """Stage terminal semantics should stay nullable and non-editable by default."""
        stage = Stage.objects.create(name="Qualified", order=2)
        field = Stage._meta.get_field("terminal_semantic")

        assert stage.terminal_semantic is None
        assert field.null is True
        assert field.blank is True
        assert field.editable is False
        assert field.unique is True
        assert list(field.choices) == Stage.TERMINAL_SEMANTIC_CHOICES

    def test_stage_terminal_semantic_must_be_unique_when_present(self):
        """Only one stage per terminal semantic should be allowed."""
        Stage.objects.all().delete()

        Stage.objects.create(
            name="Closed-Won",
            order=3,
            terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
        )
        Stage.objects.create(name="Negotiation", order=2)

        with pytest.raises(IntegrityError):
            Stage.objects.create(
                name="Deal Signed",
                order=9,
                terminal_semantic=Stage.TERMINAL_SEMANTIC_WON,
            )


@pytest.mark.django_db
class TestStageTerminalSemanticBackfill:
    """Tests for the terminal-stage migration backfill helper."""

    def test_backfill_uses_exact_names_and_deterministic_duplicate_selection(
        self, contact
    ):
        """Backfill should tag only canonical exact-name terminal stages."""
        Stage.objects.all().delete()

        won_high_count_high_order = Stage.objects.create(name="Closed-Won", order=99)
        won_high_count_low_order = Stage.objects.create(name="Closed-Won", order=1)
        won_low_count_lowest_order = Stage.objects.create(name="Closed-Won", order=0)
        won_variant = Stage.objects.create(name="closed-won", order=1)
        lost_low_id = Stage.objects.create(name="Closed-Lost", order=5)
        lost_high_id = Stage.objects.create(name="Closed-Lost", order=5)
        lost_variant = Stage.objects.create(name="Closed Lost", order=5)

        for index in range(3):
            Deal.objects.create(
                title=f"Won high order {index}",
                contact=contact,
                stage=won_high_count_high_order,
            )
            Deal.objects.create(
                title=f"Won low order {index}",
                contact=contact,
                stage=won_high_count_low_order,
            )
        for index in range(2):
            Deal.objects.create(
                title=f"Won lower count {index}",
                contact=contact,
                stage=won_low_count_lowest_order,
            )

        stage_terminal_semantic_migration.backfill_terminal_stage_semantics(
            _StageMigrationApps(),
            None,
        )

        won_high_count_high_order.refresh_from_db()
        won_high_count_low_order.refresh_from_db()
        won_low_count_lowest_order.refresh_from_db()
        won_variant.refresh_from_db()
        lost_low_id.refresh_from_db()
        lost_high_id.refresh_from_db()
        lost_variant.refresh_from_db()

        assert won_high_count_low_order.terminal_semantic == Stage.TERMINAL_SEMANTIC_WON
        assert won_high_count_high_order.terminal_semantic is None
        assert won_low_count_lowest_order.terminal_semantic is None
        assert won_variant.terminal_semantic is None
        assert lost_low_id.terminal_semantic == Stage.TERMINAL_SEMANTIC_LOST
        assert lost_high_id.terminal_semantic is None
        assert lost_variant.terminal_semantic is None

        won_high_count_high_order.name = "Closed-Won Duplicate"
        won_high_count_high_order.order = 50
        won_high_count_high_order.save(update_fields=["name", "order"])
        won_high_count_high_order.refresh_from_db()

        assert won_high_count_high_order.name == "Closed-Won Duplicate"
        assert won_high_count_high_order.order == 50


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
