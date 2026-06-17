"""Unit tests for CRM module admin configuration"""

import pytest
from django.contrib import admin
from django.test import RequestFactory

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

    def test_stage_form_hides_terminal_semantic_and_keeps_name_order_editable(self):
        """Stage admin form should expose only the public editable fields."""
        request = RequestFactory().get("/admin/")
        stage_admin = StageAdmin(Stage, admin.site)
        form_class = stage_admin.get_form(request)

        assert list(form_class.base_fields) == ["name", "order"]
        assert "terminal_semantic" not in form_class.base_fields


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


@pytest.mark.django_db
class TestOrganizationFieldExcludedFromAdmin:
    """Phase 11.1d: organization must be excluded from all five affected admin forms.

    The nullable organization groundwork must not leak into the Django admin
    surface.  Each of the five admin classes that own an organization FK
    (Tag, Company, Contact, Stage, Deal) must explicitly exclude it from
    both the ``exclude`` tuple and the generated form fields.
    """

    def test_tag_admin_excludes_organization(self):
        """TagAdmin must exclude organization from its form."""
        from quickscale_modules_crm.admin import TagAdmin

        tag_admin = TagAdmin(Tag, admin.site)
        assert "organization" in tag_admin.exclude
        request = RequestFactory().get("/admin/")
        form_class = tag_admin.get_form(request)
        assert "organization" not in form_class.base_fields

    def test_company_admin_excludes_organization(self):
        """CompanyAdmin must exclude organization from its form."""
        company_admin = CompanyAdmin(Company, admin.site)
        assert "organization" in company_admin.exclude
        request = RequestFactory().get("/admin/")
        form_class = company_admin.get_form(request)
        assert "organization" not in form_class.base_fields

    def test_contact_admin_excludes_organization(self, staff_user):
        """ContactAdmin must exclude organization from its form and fieldsets."""
        from quickscale_modules_crm.admin import ContactAdmin

        contact_admin = ContactAdmin(Contact, admin.site)
        assert "organization" in contact_admin.exclude
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        form_class = contact_admin.get_form(request)
        assert "organization" not in form_class.base_fields
        # Also verify fieldsets do not reference organization.
        fieldset_fields = [
            field
            for _, options in contact_admin.fieldsets
            for field in options.get("fields", ())
        ]
        assert "organization" not in fieldset_fields

    def test_stage_admin_excludes_organization(self):
        """StageAdmin must exclude organization from its form."""
        stage_admin = StageAdmin(Stage, admin.site)
        assert "organization" in stage_admin.exclude
        request = RequestFactory().get("/admin/")
        form_class = stage_admin.get_form(request)
        assert "organization" not in form_class.base_fields

    def test_deal_admin_excludes_organization(self, staff_user):
        """DealAdmin must exclude organization from its form and fieldsets."""
        from quickscale_modules_crm.admin import DealAdmin

        deal_admin = DealAdmin(Deal, admin.site)
        assert "organization" in deal_admin.exclude
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        form_class = deal_admin.get_form(request)
        assert "organization" not in form_class.base_fields
        # Also verify fieldsets do not reference organization.
        fieldset_fields = [
            field
            for _, options in deal_admin.fieldsets
            for field in options.get("fields", ())
        ]
        assert "organization" not in fieldset_fields
