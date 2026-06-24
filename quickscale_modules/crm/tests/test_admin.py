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

    def test_stage_form_hides_terminal_semantic_and_keeps_name_order_editable(
        self, staff_user
    ):
        """Stage admin form should expose public editable fields plus organization."""
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        stage_admin = StageAdmin(Stage, admin.site)
        form_class = stage_admin.get_form(request, obj=None, change=False)

        # Phase 1: organization is required on add, terminal_semantic stays hidden.
        assert "name" in form_class.base_fields
        assert "order" in form_class.base_fields
        assert "organization" in form_class.base_fields
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
    """Phase 11.1d (superseded by F11.10 Phase 1): organization is now explicit.

    The Phase 11.1d groundwork originally excluded organization from all five
    admin forms.  F11.10 Phase 1 makes organization explicit: required on add,
    read-only on change.  This test class is retained for historical reference
    but the assertions are inverted by the Phase 1 contract.
    """

    def test_tag_admin_includes_organization_on_add(self, staff_user):
        """TagAdmin must include organization as a required field on add forms."""
        from quickscale_modules_crm.admin import TagAdmin

        tag_admin = TagAdmin(Tag, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        form_class = tag_admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required

    def test_company_admin_includes_organization_on_add(self, staff_user):
        """CompanyAdmin must include organization as a required field on add forms."""
        company_admin = CompanyAdmin(Company, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        form_class = company_admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required

    def test_contact_admin_includes_organization_on_add(self, staff_user):
        """ContactAdmin must include organization as a required field on add forms."""
        from quickscale_modules_crm.admin import ContactAdmin

        contact_admin = ContactAdmin(Contact, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        form_class = contact_admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required

    def test_stage_admin_includes_organization_on_add(self, staff_user):
        """StageAdmin must include organization as a required field on add forms."""
        stage_admin = StageAdmin(Stage, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        form_class = stage_admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required

    def test_deal_admin_includes_organization_on_add(self, staff_user):
        """DealAdmin must include organization as a required field on add forms."""
        from quickscale_modules_crm.admin import DealAdmin

        deal_admin = DealAdmin(Deal, admin.site)
        request = RequestFactory().get("/admin/")
        request.user = staff_user
        form_class = deal_admin.get_form(request, obj=None, change=False)
        assert "organization" in form_class.base_fields
        assert form_class.base_fields["organization"].required


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

    def test_superuser_add_form_includes_organization(self, admin_client):
        """Platform operator add forms must expose organization as a required field."""
        response = admin_client.get("/admin/quickscale_modules_crm/tag/add/")
        assert response.status_code == 200
        # The rendered form should contain an organization field.
        content = response.content.decode()
        assert 'name="organization"' in content

    def test_superuser_change_form_shows_organization_readonly(
        self, admin_client, org_a, tag
    ):
        """Platform operator change forms must show organization read-only."""
        tag.organization = org_a
        tag.save(update_fields=["organization"])
        response = admin_client.get(
            f"/admin/quickscale_modules_crm/tag/{tag.pk}/change/"
        )
        assert response.status_code == 200
        # The rendered form should contain the organization value but not as an editable input.
        content = response.content.decode()
        # Organization value should be visible in the page.
        assert org_a.name in content


@pytest.mark.django_db
class TestF1110Phase1AdminReadOnlyOrganizationOnChange:
    """F11.10 Phase 1 — Prove organization is read-only on admin change forms.

    The Phase 1 admin contract requires organization to be displayed read-only
    on change forms so the operator can see which organization owns the row
    but cannot reassign it.
    """

    def test_tag_admin_organization_readonly_on_change(self, org_a, tag):
        """TagAdmin change form includes organization in readonly_fields."""
        from quickscale_modules_crm.admin import TagAdmin

        tag.organization = org_a
        tag.save(update_fields=["organization"])
        tag_admin = TagAdmin(Tag, admin.site)
        request = RequestFactory().get("/admin/")
        readonly = tag_admin.get_readonly_fields(request, obj=tag)
        assert "organization" in readonly

    def test_company_admin_organization_readonly_on_change(self, org_a, company):
        """CompanyAdmin change form includes organization in readonly_fields."""
        company.organization = org_a
        company.save(update_fields=["organization"])
        company_admin = CompanyAdmin(Company, admin.site)
        request = RequestFactory().get("/admin/")
        readonly = company_admin.get_readonly_fields(request, obj=company)
        assert "organization" in readonly

    def test_contact_admin_organization_readonly_on_change(self, org_a, contact):
        """ContactAdmin change form includes organization in readonly_fields."""
        from quickscale_modules_crm.admin import ContactAdmin

        contact.organization = org_a
        contact.save(update_fields=["organization"])
        contact_admin = ContactAdmin(Contact, admin.site)
        request = RequestFactory().get("/admin/")
        readonly = contact_admin.get_readonly_fields(request, obj=contact)
        assert "organization" in readonly

    def test_stage_admin_organization_readonly_on_change(self, org_a, stage):
        """StageAdmin change form includes organization in readonly_fields."""
        stage.organization = org_a
        stage.save(update_fields=["organization"])
        stage_admin = StageAdmin(Stage, admin.site)
        request = RequestFactory().get("/admin/")
        readonly = stage_admin.get_readonly_fields(request, obj=stage)
        assert "organization" in readonly

    def test_deal_admin_organization_readonly_on_change(self, org_a, deal):
        """DealAdmin change form includes organization in readonly_fields."""
        from quickscale_modules_crm.admin import DealAdmin

        deal.organization = org_a
        deal.save(update_fields=["organization"])
        deal_admin = DealAdmin(Deal, admin.site)
        request = RequestFactory().get("/admin/")
        readonly = deal_admin.get_readonly_fields(request, obj=deal)
        assert "organization" in readonly


@pytest.mark.django_db
class TestF1110AdminTagFormLevelValidation:
    """CR-F11.10-ADMIN-002 — Admin tag validation at form-level clean hook.

    These tests verify that the admin form-level ``clean()`` hook rejects
    foreign-org tag selections before any save occurs, for both ContactAdmin
    and DealAdmin add forms.
    """

    # -- ContactAdmin add form: foreign tag rejected --------------------------

    def test_contact_admin_add_form_rejects_foreign_tag(
        self, admin_client, org_a, org_b
    ):
        """ContactAdmin add form rejects a foreign-org tag selection."""
        from quickscale_modules_crm.models import Company, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        foreign_tag = Tag.objects.create(name="Foreign Tag", organization=org_b)

        _inline_mgmt = {
            "notes-TOTAL_FORMS": "0",
            "notes-INITIAL_FORMS": "0",
            "notes-MIN_NUM_FORMS": "0",
            "notes-MAX_NUM_FORMS": "1000",
        }

        response = admin_client.post(
            "/admin/quickscale_modules_crm/contact/add/",
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
                "phone": "+1234567890",
                "title": "Manager",
                "company": company.id,
                "tags": [foreign_tag.id],
                "status": "new",
                "organization": org_a.id,
                **_inline_mgmt,
                "_save": "Save",
            },
        )

        # Form re-rendered with errors (200), not a redirect (302).
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "All tags must belong to the same organization" in content

    # -- ContactAdmin add form: same-org tag accepted -------------------------

    def test_contact_admin_add_form_accepts_same_org_tag(self, admin_client, org_a):
        """ContactAdmin add form accepts a same-org tag selection."""
        from quickscale_modules_crm.models import Company, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        same_org_tag = Tag.objects.create(name="Same-Org Tag", organization=org_a)

        _inline_mgmt = {
            "notes-TOTAL_FORMS": "0",
            "notes-INITIAL_FORMS": "0",
            "notes-MIN_NUM_FORMS": "0",
            "notes-MAX_NUM_FORMS": "1000",
        }

        response = admin_client.post(
            "/admin/quickscale_modules_crm/contact/add/",
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
                "phone": "+1234567890",
                "title": "Manager",
                "company": company.id,
                "tags": [same_org_tag.id],
                "status": "new",
                "organization": org_a.id,
                **_inline_mgmt,
                "_save": "Save",
            },
        )

        # Successful create redirects to changelist.
        assert response.status_code == 302

    # -- ContactAdmin add form: no tags valid ---------------------------------

    def test_contact_admin_add_form_accepts_no_tags(self, admin_client, org_a):
        """ContactAdmin add form accepts a submission with no tags."""
        from quickscale_modules_crm.models import Company

        company = Company.objects.create(name="Org-A Corp", organization=org_a)

        _inline_mgmt = {
            "notes-TOTAL_FORMS": "0",
            "notes-INITIAL_FORMS": "0",
            "notes-MIN_NUM_FORMS": "0",
            "notes-MAX_NUM_FORMS": "1000",
        }

        response = admin_client.post(
            "/admin/quickscale_modules_crm/contact/add/",
            data={
                "first_name": "Test",
                "last_name": "User",
                "email": "test@example.com",
                "phone": "+1234567890",
                "title": "Manager",
                "company": company.id,
                "status": "new",
                "organization": org_a.id,
                **_inline_mgmt,
                "_save": "Save",
            },
        )

        # Successful create redirects to changelist.
        assert response.status_code == 302

    # -- DealAdmin add form: foreign tag rejected -----------------------------

    def test_deal_admin_add_form_rejects_foreign_tag(self, admin_client, org_a, org_b):
        """DealAdmin add form rejects a foreign-org tag selection."""
        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Stage,
            Tag,
        )

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Test",
            last_name="Contact",
            email="deal-test@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        foreign_tag = Tag.objects.create(name="Foreign Tag", organization=org_b)

        _deal_inline_mgmt = {
            "notes-TOTAL_FORMS": "0",
            "notes-INITIAL_FORMS": "0",
            "notes-MIN_NUM_FORMS": "0",
            "notes-MAX_NUM_FORMS": "1000",
        }

        response = admin_client.post(
            "/admin/quickscale_modules_crm/deal/add/",
            data={
                "title": "Test Deal",
                "contact": contact.id,
                "stage": stage.id,
                "amount": "1000.00",
                "probability": 50,
                "tags": [foreign_tag.id],
                "organization": org_a.id,
                **_deal_inline_mgmt,
                "_save": "Save",
            },
        )

        # Form re-rendered with errors (200), not a redirect (302).
        assert response.status_code == 200
        content = response.content.decode("utf-8")
        assert "All tags must belong to the same organization" in content

    # -- DealAdmin add form: same-org tag accepted ----------------------------

    def test_deal_admin_add_form_accepts_same_org_tag(self, admin_client, org_a):
        """DealAdmin add form accepts a same-org tag selection."""
        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Stage,
            Tag,
        )

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Test",
            last_name="Contact",
            email="deal-same-org@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        same_org_tag = Tag.objects.create(name="Same-Org Tag", organization=org_a)

        _deal_inline_mgmt = {
            "notes-TOTAL_FORMS": "0",
            "notes-INITIAL_FORMS": "0",
            "notes-MIN_NUM_FORMS": "0",
            "notes-MAX_NUM_FORMS": "1000",
        }

        response = admin_client.post(
            "/admin/quickscale_modules_crm/deal/add/",
            data={
                "title": "Test Deal",
                "contact": contact.id,
                "stage": stage.id,
                "amount": "1000.00",
                "probability": 50,
                "tags": [same_org_tag.id],
                "organization": org_a.id,
                **_deal_inline_mgmt,
                "_save": "Save",
            },
        )

        # Successful create redirects to changelist.
        assert response.status_code == 302

    # -- DealAdmin add form: no tags valid ------------------------------------

    def test_deal_admin_add_form_accepts_no_tags(self, admin_client, org_a):
        """DealAdmin add form accepts a submission with no tags."""
        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Stage,
        )

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Test",
            last_name="Contact",
            email="deal-no-tags@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)

        _deal_inline_mgmt = {
            "notes-TOTAL_FORMS": "0",
            "notes-INITIAL_FORMS": "0",
            "notes-MIN_NUM_FORMS": "0",
            "notes-MAX_NUM_FORMS": "1000",
        }

        response = admin_client.post(
            "/admin/quickscale_modules_crm/deal/add/",
            data={
                "title": "Test Deal",
                "contact": contact.id,
                "stage": stage.id,
                "amount": "1000.00",
                "probability": 50,
                "organization": org_a.id,
                **_deal_inline_mgmt,
                "_save": "Save",
            },
        )

        # Successful create redirects to changelist.
        assert response.status_code == 302


@pytest.mark.django_db
class TestCRT15001ContactNoteTimestampAdminRegression:
    """CR-T15-001 — Admin/operator ContactNote creation must refresh last_contacted_at
    even when the tenant contextvar is not set."""

    def test_contact_note_save_updates_timestamp_without_contextvar(self, db, company):
        """ContactNote.save() updates Contact.last_contacted_at via all_objects
        bypass even when the tenant contextvar is not set."""
        from django.contrib.auth import get_user_model
        from quickscale_modules_crm.models import Contact, ContactNote
        from quickscale_modules_orgs.current_org import reset_current_org_id

        # Ensure contextvar is explicitly unset (simulating admin/operator path).
        reset_current_org_id()

        user_model = get_user_model()
        operator = user_model.objects.create_superuser(
            username="op-ts-test",
            email="op-ts-test@example.com",
            password="pass",
        )
        contact = Contact.objects.create(
            first_name="Timestamp",
            last_name="Test",
            email="ts-test@example.com",
            company=company,
            organization=company.organization,
        )
        assert contact.last_contacted_at is None

        ContactNote.objects.create(
            contact=contact,
            created_by=operator,
            text="Regression test for CR-T15-001 — no contextvar",
        )

        contact.refresh_from_db()
        assert contact.last_contacted_at is not None, (
            "last_contacted_at must be updated via all_objects bypass"
        )
