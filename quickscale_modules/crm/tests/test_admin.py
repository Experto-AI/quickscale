"""Unit tests for CRM module admin configuration"""

import pytest
from django.contrib import admin

from quickscale_modules_crm.admin import (
    CompanyAdmin,
    ContactNoteAdmin,
    DealNoteAdmin,
    StageAdmin,
)
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
class TestAdminRegistration:
    """Tests for admin model registration"""

    def test_tag_admin_registered(self):
        """Test Tag is registered in admin"""
        assert admin.site.is_registered(Tag)

    def test_company_admin_registered(self):
        """Test Company is registered in admin"""
        assert admin.site.is_registered(Company)

    def test_contact_admin_registered(self):
        """Test Contact is registered in admin"""
        assert admin.site.is_registered(Contact)

    def test_stage_admin_registered(self):
        """Test Stage is registered in admin"""
        assert admin.site.is_registered(Stage)

    def test_deal_admin_registered(self):
        """Test Deal is registered in admin"""
        assert admin.site.is_registered(Deal)

    def test_contact_note_admin_registered(self):
        """Test ContactNote is registered in admin"""
        assert admin.site.is_registered(ContactNote)

    def test_deal_note_admin_registered(self):
        """Test DealNote is registered in admin"""
        assert admin.site.is_registered(DealNote)


@pytest.mark.django_db
class TestCompanyAdmin:
    """Tests for CompanyAdmin"""

    def test_contact_count(self, company, contact):
        """Test contact_count method"""
        company_admin = CompanyAdmin(Company, admin.site)
        assert company_admin.contact_count(company) == 1


@pytest.mark.django_db
class TestStageAdmin:
    """Tests for StageAdmin"""

    def test_deal_count(self, stage, deal):
        """Test deal_count method"""
        stage_admin = StageAdmin(Stage, admin.site)
        assert stage_admin.deal_count(stage) == 1


@pytest.mark.django_db
class TestContactNoteAdmin:
    """Tests for ContactNoteAdmin"""

    def test_short_text_truncation(self, contact_note):
        """Test short_text method truncates long text"""
        note_admin = ContactNoteAdmin(ContactNote, admin.site)
        result = note_admin.short_text(contact_note)
        assert len(result) <= 53  # 50 chars + "..."

    def test_short_text_no_truncation(self, contact, user):
        """Test short_text method doesn't truncate short text"""
        from quickscale_modules_crm.models import ContactNote

        note = ContactNote.objects.create(
            contact=contact,
            created_by=user,
            text="Short",
        )
        note_admin = ContactNoteAdmin(ContactNote, admin.site)
        result = note_admin.short_text(note)
        assert result == "Short"


@pytest.mark.django_db
class TestDealNoteAdmin:
    """Tests for DealNoteAdmin"""

    def test_short_text_truncation(self, deal_note):
        """Test short_text method truncates long text"""
        note_admin = DealNoteAdmin(DealNote, admin.site)
        result = note_admin.short_text(deal_note)
        assert len(result) <= 53  # 50 chars + "..."
