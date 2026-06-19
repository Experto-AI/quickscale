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


@pytest.mark.django_db
class TestOperatorPathOrganizationVisibility:
    """Phase 2: CRM admin must expose organization context to the platform operator.

    The Django /admin/ surface is the deliberate cross-tenant operator path
    documented in docs/technical/organizations.md.  The platform owner
    (Django superuser) must see organization context in changelist views
    and be able to filter by organization, while organization remains
    excluded from editable forms.

    These tests use the superuser/operator path explicitly — not generic
    staff semantics — to prove the runtime contract.
    """

    def test_tag_admin_shows_organization_in_changelist(self):
        """TagAdmin list_display must include organization for operator visibility."""
        from quickscale_modules_crm.admin import TagAdmin

        tag_admin = TagAdmin(Tag, admin.site)
        assert "organization" in tag_admin.list_display

    def test_tag_admin_filters_by_organization(self):
        """TagAdmin list_filter must include organization for operator filtering."""
        from quickscale_modules_crm.admin import TagAdmin

        tag_admin = TagAdmin(Tag, admin.site)
        assert "organization" in tag_admin.list_filter

    def test_company_admin_shows_organization_in_changelist(self):
        """CompanyAdmin list_display must include organization for operator visibility."""
        company_admin = CompanyAdmin(Company, admin.site)
        assert "organization" in company_admin.list_display

    def test_company_admin_filters_by_organization(self):
        """CompanyAdmin list_filter must include organization for operator filtering."""
        company_admin = CompanyAdmin(Company, admin.site)
        assert "organization" in company_admin.list_filter

    def test_contact_admin_shows_organization_in_changelist(self):
        """ContactAdmin list_display must include organization for operator visibility."""
        from quickscale_modules_crm.admin import ContactAdmin

        contact_admin = ContactAdmin(Contact, admin.site)
        assert "organization" in contact_admin.list_display

    def test_contact_admin_filters_by_organization(self):
        """ContactAdmin list_filter must include organization for operator filtering."""
        from quickscale_modules_crm.admin import ContactAdmin

        contact_admin = ContactAdmin(Contact, admin.site)
        assert "organization" in contact_admin.list_filter

    def test_stage_admin_shows_organization_in_changelist(self):
        """StageAdmin list_display must include organization for operator visibility."""
        stage_admin = StageAdmin(Stage, admin.site)
        assert "organization" in stage_admin.list_display

    def test_stage_admin_filters_by_organization(self):
        """StageAdmin list_filter must include organization for operator filtering."""
        stage_admin = StageAdmin(Stage, admin.site)
        assert "organization" in stage_admin.list_filter

    def test_deal_admin_shows_organization_in_changelist(self):
        """DealAdmin list_display must include organization for operator visibility."""
        from quickscale_modules_crm.admin import DealAdmin

        deal_admin = DealAdmin(Deal, admin.site)
        assert "organization" in deal_admin.list_display

    def test_deal_admin_filters_by_organization(self):
        """DealAdmin list_filter must include organization for operator filtering."""
        from quickscale_modules_crm.admin import DealAdmin

        deal_admin = DealAdmin(Deal, admin.site)
        assert "organization" in deal_admin.list_filter


@pytest.mark.django_db
class TestOperatorPathHTTPAccess:
    """Phase 2: Prove the superuser/operator /admin/ path with HTTP-level tests.

    These tests use Django's test Client authenticated as a superuser to
    verify that the platform operator can access CRM admin changelist views
    and that organization context is visible in the rendered output.
    """

    def test_superuser_can_access_tag_changelist(self, admin_client):
        """Platform operator (superuser) can access Tag changelist via /admin/."""
        response = admin_client.get("/admin/quickscale_modules_crm/tag/")
        assert response.status_code == 200

    def test_superuser_can_access_company_changelist(self, admin_client):
        """Platform operator (superuser) can access Company changelist via /admin/."""
        response = admin_client.get("/admin/quickscale_modules_crm/company/")
        assert response.status_code == 200

    def test_superuser_can_access_contact_changelist(self, admin_client):
        """Platform operator (superuser) can access Contact changelist via /admin/."""
        response = admin_client.get("/admin/quickscale_modules_crm/contact/")
        assert response.status_code == 200

    def test_superuser_can_access_stage_changelist(self, admin_client):
        """Platform operator (superuser) can access Stage changelist via /admin/."""
        response = admin_client.get("/admin/quickscale_modules_crm/stage/")
        assert response.status_code == 200

    def test_superuser_can_access_deal_changelist(self, admin_client):
        """Platform operator (superuser) can access Deal changelist via /admin/."""
        response = admin_client.get("/admin/quickscale_modules_crm/deal/")
        assert response.status_code == 200

    def test_superuser_can_filter_tag_by_organization(self, admin_client, org_a, tag):
        """Platform operator can filter Tag changelist by organization."""
        tag.organization = org_a
        tag.save(update_fields=["organization"])
        response = admin_client.get(
            f"/admin/quickscale_modules_crm/tag/?organization={org_a.pk}"
        )
        assert response.status_code == 200
        assert tag.name in response.content.decode()

    def test_superuser_can_filter_company_by_organization(
        self, admin_client, org_a, company
    ):
        """Platform operator can filter Company changelist by organization."""
        company.organization = org_a
        company.save(update_fields=["organization"])
        response = admin_client.get(
            f"/admin/quickscale_modules_crm/company/?organization={org_a.pk}"
        )
        assert response.status_code == 200
        assert company.name in response.content.decode()

    def test_superuser_add_form_excludes_organization(self, admin_client):
        """Platform operator add forms must not expose organization as editable."""
        response = admin_client.get("/admin/quickscale_modules_crm/tag/add/")
        assert response.status_code == 200
        # The rendered form should not contain an organization field.
        content = response.content.decode()
        assert 'name="organization"' not in content

    def test_superuser_change_form_excludes_organization(
        self, admin_client, org_a, tag
    ):
        """Platform operator change forms must not expose organization as editable."""
        tag.organization = org_a
        tag.save(update_fields=["organization"])
        response = admin_client.get(
            f"/admin/quickscale_modules_crm/tag/{tag.pk}/change/"
        )
        assert response.status_code == 200
        # The rendered form should not contain an organization field.
        content = response.content.decode()
        assert 'name="organization"' not in content
