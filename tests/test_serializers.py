"""Unit tests for CRM module serializers"""

import pytest
from django.test import override_settings
from rest_framework.test import APIRequestFactory

from quickscale_modules_crm.models import Stage
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

    def test_create_duplicate_tag_rejected(self, tag):
        """Creating a tag with a duplicate name in the same owner bucket is rejected."""
        serializer = TagSerializer(data={"name": "VIP"})
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_update_tag_same_name_is_valid(self, tag):
        """Updating a tag without changing its name is valid (self-exclusion)."""
        serializer = TagSerializer(tag, data={"name": "VIP"}, partial=True)
        assert serializer.is_valid(), serializer.errors

    def test_update_tag_rename_to_existing_duplicate_rejected(self, tag):
        """Renaming a tag to an existing name in the same bucket is rejected."""
        from quickscale_modules_crm.models import Tag

        Tag.objects.create(name="Hot Lead")
        serializer = TagSerializer(tag, data={"name": "Hot Lead"}, partial=True)
        assert not serializer.is_valid()
        assert "name" in serializer.errors

    def test_create_tag_same_name_different_org_allowed(self, org_a, org_b):
        """Same tag name across different orgs is allowed via serializer."""
        from quickscale_modules_crm.models import Tag

        Tag.objects.create(name="VIP", organization=org_a)
        serializer = TagSerializer(data={"name": "VIP"})
        # Serializer creates with organization_id=None (NULL bucket),
        # which is different from org_a's bucket.
        assert serializer.is_valid(), serializer.errors

    def test_update_tag_rename_to_same_name_different_org_allowed(self, tag, org_a):
        """Renaming a NULL-owned tag to a name that exists only in an org is allowed."""
        from quickscale_modules_crm.models import Tag

        Tag.objects.create(name="Renamed", organization=org_a)
        serializer = TagSerializer(tag, data={"name": "Renamed"}, partial=True)
        assert serializer.is_valid(), serializer.errors


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

    def test_stage_serializer_hides_terminal_semantic(self):
        """Stage serializer output should not expose terminal semantics."""
        stage = Stage.objects.get(terminal_semantic=Stage.TERMINAL_SEMANTIC_WON)

        serializer = StageSerializer(stage)

        assert "terminal_semantic" not in serializer.data

    def test_stage_serializer_does_not_allow_terminal_semantic_input(self):
        """Stage serializer should ignore attempts to set hidden terminal semantics."""
        serializer = StageSerializer(
            data={
                "name": "Closed-Won",
                "order": 3,
                "terminal_semantic": Stage.TERMINAL_SEMANTIC_WON,
            }
        )

        assert serializer.is_valid(), serializer.errors
        stage = serializer.save()

        assert stage.terminal_semantic is None


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


@pytest.mark.django_db
class TestOrganizationFieldNotExposedInSerializers:
    """Phase 11.1d: organization must not appear in serializer output or input.

    The nullable organization groundwork must not leak through the API
    serializer surface.  Every serializer that backs a CRM-owned model
    must exclude organization from its output fields, and attempts to
    supply organization via input must be silently ignored.
    """

    def test_tag_serializer_excludes_organization(self, tag):
        """TagSerializer output must not contain organization."""
        serializer = TagSerializer(tag)
        assert "organization" not in serializer.data

    def test_company_serializer_excludes_organization(self, company):
        """CompanySerializer output must not contain organization."""
        serializer = CompanySerializer(company)
        assert "organization" not in serializer.data

    def test_contact_list_serializer_excludes_organization(self, contact):
        """ContactListSerializer output must not contain organization."""
        serializer = ContactListSerializer(contact)
        assert "organization" not in serializer.data

    def test_contact_detail_serializer_excludes_organization(self, contact):
        """ContactDetailSerializer output must not contain organization."""
        serializer = ContactDetailSerializer(contact)
        assert "organization" not in serializer.data

    def test_stage_serializer_excludes_organization(self, stage):
        """StageSerializer output must not contain organization."""
        serializer = StageSerializer(stage)
        assert "organization" not in serializer.data

    def test_deal_list_serializer_excludes_organization(self, deal):
        """DealListSerializer output must not contain organization."""
        serializer = DealListSerializer(deal)
        assert "organization" not in serializer.data

    def test_deal_detail_serializer_excludes_organization(self, deal):
        """DealDetailSerializer output must not contain organization."""
        serializer = DealDetailSerializer(deal)
        assert "organization" not in serializer.data

    def test_tag_serializer_ignores_organization_input(self):
        """TagSerializer must not accept organization via input."""
        serializer = TagSerializer(data={"name": "OrgInput", "organization": 999})
        assert serializer.is_valid(), serializer.errors
        tag = serializer.save()
        assert tag.organization_id is None

    def test_company_serializer_ignores_organization_input(self):
        """CompanySerializer must not accept organization via input."""
        serializer = CompanySerializer(
            data={"name": "OrgInput Corp", "organization": 999}
        )
        assert serializer.is_valid(), serializer.errors
        company = serializer.save()
        assert company.organization_id is None

    def test_contact_serializer_meta_fields_exclude_organization(self):
        """ContactListSerializer Meta.fields must not list organization."""
        assert "organization" not in ContactListSerializer.Meta.fields

    def test_contact_detail_serializer_meta_fields_exclude_organization(self):
        """ContactDetailSerializer Meta.fields must not list organization."""
        assert "organization" not in ContactDetailSerializer.Meta.fields

    def test_deal_list_serializer_meta_fields_exclude_organization(self):
        """DealListSerializer Meta.fields must not list organization."""
        assert "organization" not in DealListSerializer.Meta.fields

    def test_deal_detail_serializer_meta_fields_exclude_organization(self):
        """DealDetailSerializer Meta.fields must not list organization."""
        assert "organization" not in DealDetailSerializer.Meta.fields


@pytest.mark.django_db
class TestF115Phase2SerializerHelperOrgScoping:
    """F11.5 Phase 2 — Prove serializer helper queries are org-scoped.

    These tests verify that serializer helper methods (counts, tag names)
    scope their related queries to the active organization when serializing
    on an org-scoped SaaS route, while solo routes preserve legacy unscoped
    behavior.

    Coverage matrix:
    - CompanySerializer.get_contact_count() is org-scoped
    - StageSerializer.get_deal_count() is org-scoped
    - ContactDetailSerializer.get_deal_count() is org-scoped
    - ContactListSerializer.get_tag_names() is org-scoped
    - DealListSerializer.get_tag_names() is org-scoped
    """

    def test_company_serializer_contact_count_is_org_scoped(
        self, org_a, org_b, org_a_admin
    ):
        """CompanySerializer.get_contact_count() only counts org-scoped contacts."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact

        company = Company.objects.create(name="Shared Corp", organization=org_a)
        # Create org-A contact
        Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga@example.com",
            company=company,
            organization=org_a,
        )
        # Create org-B contact referencing the same company (cross-org reference)
        Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb@example.com",
            company=company,
            organization=org_b,
        )

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/companies/")
        request.user = org_a_admin
        request.org = org_a  # Simulate TenantMiddleware

        serializer = CompanySerializer(company, context={"request": request})
        # Should only count org-A contacts (1), not org-B contacts
        assert serializer.data["contact_count"] == 1

    def test_stage_serializer_deal_count_is_org_scoped(self, org_a, org_b, org_a_admin):
        """StageSerializer.get_deal_count() only counts org-scoped deals."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        stage = Stage.objects.create(name="Shared Stage", order=1, organization=org_a)
        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-deal@example.com",
            company=company_a,
            organization=org_a,
        )
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-deal@example.com",
            company=company_b,
            organization=org_b,
        )
        # Create org-A deal
        Deal.objects.create(
            title="Org-A Deal",
            contact=contact_a,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=org_a,
        )
        # Create org-B deal referencing the same stage (cross-org reference)
        Deal.objects.create(
            title="Org-B Deal",
            contact=contact_b,
            amount=Decimal("2000.00"),
            stage=stage,
            organization=org_b,
        )

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/stages/")
        request.user = org_a_admin
        request.org = org_a  # Simulate TenantMiddleware

        serializer = StageSerializer(stage, context={"request": request})
        # Should only count org-A deals (1), not org-B deals
        assert serializer.data["deal_count"] == 1

    def test_contact_detail_serializer_deal_count_is_org_scoped(
        self, org_a, org_b, org_a_admin
    ):
        """ContactDetailSerializer.get_deal_count() only counts org-scoped deals."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company = Company.objects.create(name="Shared Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Shared",
            last_name="Contact",
            email="shared@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        # Create org-A deal
        Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )
        # Create org-B deal referencing the same contact (cross-org reference)
        Deal.objects.create(
            title="Org-B Deal",
            contact=contact,
            amount=Decimal("2000.00"),
            stage=stage_b,
            organization=org_b,
        )

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/contacts/")
        request.user = org_a_admin
        request.org = org_a  # Simulate TenantMiddleware

        serializer = ContactDetailSerializer(contact, context={"request": request})
        # Should only count org-A deals (1), not org-B deals
        assert serializer.data["deal_count"] == 1

    def test_contact_list_serializer_tag_names_is_org_scoped(
        self, org_a, org_b, org_a_admin
    ):
        """ContactListSerializer.get_tag_names() only includes org-scoped tags."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-tags@example.com",
            company=company,
            organization=org_a,
        )
        tag_a = Tag.objects.create(name="Org-A-Tag", organization=org_a)
        tag_b = Tag.objects.create(name="Org-B-Tag", organization=org_b)
        contact.tags.add(tag_a, tag_b)

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/contacts/")
        request.user = org_a_admin
        request.org = org_a  # Simulate TenantMiddleware

        serializer = ContactListSerializer(contact, context={"request": request})
        # Should only include org-A tags
        assert "Org-A-Tag" in serializer.data["tag_names"]
        assert "Org-B-Tag" not in serializer.data["tag_names"]

    def test_deal_list_serializer_tag_names_is_org_scoped(
        self, org_a, org_b, org_a_admin
    ):
        """DealListSerializer.get_tag_names() only includes org-scoped tags."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-deal-tags@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=org_a,
        )
        tag_a = Tag.objects.create(name="Org-A-Deal-Tag", organization=org_a)
        tag_b = Tag.objects.create(name="Org-B-Deal-Tag", organization=org_b)
        deal.tags.add(tag_a, tag_b)

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/deals/")
        request.user = org_a_admin
        request.org = org_a  # Simulate TenantMiddleware

        serializer = DealListSerializer(deal, context={"request": request})
        # Should only include org-A tags
        assert "Org-A-Deal-Tag" in serializer.data["tag_names"]
        assert "Org-B-Deal-Tag" not in serializer.data["tag_names"]

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_serializer_helpers_are_unscoped(self, staff_user, org_a, org_b):
        """Solo route serializer helpers return all data (parity preserved)."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage, Tag

        company = Company.objects.create(name="Shared Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Shared",
            last_name="Contact",
            email="shared@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Shared Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Shared Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=org_a,
        )
        tag_a = Tag.objects.create(name="Org-A-Tag", organization=org_a)
        tag_b = Tag.objects.create(name="Org-B-Tag", organization=org_b)
        contact.tags.add(tag_a, tag_b)
        deal.tags.add(tag_a, tag_b)

        # Create cross-org references
        Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb@example.com",
            company=company,
            organization=org_b,
        )
        Deal.objects.create(
            title="Org-B Deal",
            contact=contact,
            amount=Decimal("2000.00"),
            stage=stage,
            organization=org_b,
        )

        factory = APIRequestFactory()
        request = factory.get("/crm/api/contacts/")
        request.user = staff_user
        # No request.org on solo routes

        # CompanySerializer: contact_count should include all contacts
        company_serializer = CompanySerializer(company, context={"request": request})
        assert company_serializer.data["contact_count"] == 2  # org-A + org-B

        # StageSerializer: deal_count should include all deals
        stage_serializer = StageSerializer(stage, context={"request": request})
        assert stage_serializer.data["deal_count"] == 2  # org-A + org-B

        # ContactDetailSerializer: deal_count should include all deals
        contact_serializer = ContactDetailSerializer(
            contact, context={"request": request}
        )
        assert contact_serializer.data["deal_count"] == 2  # org-A + org-B

        # ContactListSerializer: tag_names should include all tags
        contact_list_serializer = ContactListSerializer(
            contact, context={"request": request}
        )
        assert "Org-A-Tag" in contact_list_serializer.data["tag_names"]
        assert "Org-B-Tag" in contact_list_serializer.data["tag_names"]

        # DealListSerializer: tag_names should include all tags
        deal_serializer = DealListSerializer(deal, context={"request": request})
        assert "Org-A-Tag" in deal_serializer.data["tag_names"]
        assert "Org-B-Tag" in deal_serializer.data["tag_names"]


@pytest.mark.django_db
class TestCRMRev001ForeignRelatedObjectIsolation:
    """CRM-REV-001 — Prove org-scoped reads omit foreign related objects.

    These tests verify that org-scoped contact/deal reads do not serialize
    foreign-org related objects (company, contact, stage, tags) in the
    serialized output.  On solo routes, all related objects are serialized
    (legacy parity preserved).

    Coverage matrix:
    - ContactListSerializer.company_name is empty for foreign-org companies
    - ContactDetailSerializer.company is None for foreign-org companies
    - ContactDetailSerializer.tags are filtered to same-org only
    - DealListSerializer contact_name/company_name/stage_name empty for foreign-org
    - DealDetailSerializer contact/stage are None for foreign-org related objects
    - DealDetailSerializer.tags are filtered to same-org only
    - Update path rejects foreign-org related IDs
    """

    def test_contact_list_serializer_hides_foreign_org_company_name(
        self, org_a, org_b, org_a_admin
    ):
        """ContactListSerializer returns empty company_name for foreign-org company."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact

        foreign_company = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga@example.com",
            company=foreign_company,
            organization=org_a,
        )

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/contacts/")
        request.user = org_a_admin
        request.org = org_a

        serializer = ContactListSerializer(contact, context={"request": request})
        assert serializer.data["company_name"] == ""

    def test_contact_detail_serializer_hides_foreign_org_company(
        self, org_a, org_b, org_a_admin
    ):
        """ContactDetailSerializer returns None company for foreign-org company."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact

        foreign_company = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-detail@example.com",
            company=foreign_company,
            organization=org_a,
        )

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/contacts/")
        request.user = org_a_admin
        request.org = org_a

        serializer = ContactDetailSerializer(contact, context={"request": request})
        assert serializer.data["company"] is None

    def test_contact_detail_serializer_filters_foreign_org_tags(
        self, org_a, org_b, org_a_admin
    ):
        """ContactDetailSerializer filters out foreign-org tags on org-scoped reads."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-tags@example.com",
            company=company,
            organization=org_a,
        )
        tag_a = Tag.objects.create(name="Org-A-Tag", organization=org_a)
        tag_b = Tag.objects.create(name="Org-B-Tag", organization=org_b)
        contact.tags.add(tag_a, tag_b)

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/contacts/")
        request.user = org_a_admin
        request.org = org_a

        serializer = ContactDetailSerializer(contact, context={"request": request})
        tag_names = [t["name"] for t in serializer.data["tags"]]
        assert "Org-A-Tag" in tag_names
        assert "Org-B-Tag" not in tag_names

    def test_deal_list_serializer_hides_foreign_org_related_names(
        self, org_a, org_b, org_a_admin
    ):
        """DealListSerializer returns empty names for foreign-org related objects."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        foreign_company = Company.objects.create(name="Org-B Corp", organization=org_b)
        foreign_contact = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb@example.com",
            company=foreign_company,
            organization=org_b,
        )
        foreign_stage = Stage.objects.create(
            name="Org-B Stage", order=1, organization=org_b
        )
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=foreign_contact,
            amount=Decimal("1000.00"),
            stage=foreign_stage,
            organization=org_a,
        )

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/deals/")
        request.user = org_a_admin
        request.org = org_a

        serializer = DealListSerializer(deal, context={"request": request})
        assert serializer.data["contact_name"] == ""
        assert serializer.data["company_name"] == ""
        assert serializer.data["stage_name"] == ""

    def test_deal_detail_serializer_hides_foreign_org_related_objects(
        self, org_a, org_b, org_a_admin
    ):
        """DealDetailSerializer returns None for foreign-org contact/stage."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        foreign_company = Company.objects.create(name="Org-B Corp", organization=org_b)
        foreign_contact = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-detail@example.com",
            company=foreign_company,
            organization=org_b,
        )
        foreign_stage = Stage.objects.create(
            name="Org-B Stage", order=1, organization=org_b
        )
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=foreign_contact,
            amount=Decimal("1000.00"),
            stage=foreign_stage,
            organization=org_a,
        )

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/deals/")
        request.user = org_a_admin
        request.org = org_a

        serializer = DealDetailSerializer(deal, context={"request": request})
        assert serializer.data["contact"] is None
        assert serializer.data["stage"] is None

    def test_deal_detail_serializer_filters_foreign_org_tags(
        self, org_a, org_b, org_a_admin
    ):
        """DealDetailSerializer filters out foreign-org tags on org-scoped reads."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage, Tag

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-deal-tags@example.com",
            company=company,
            organization=org_a,
        )
        stage = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage,
            organization=org_a,
        )
        tag_a = Tag.objects.create(name="Org-A-Deal-Tag", organization=org_a)
        tag_b = Tag.objects.create(name="Org-B-Deal-Tag", organization=org_b)
        deal.tags.add(tag_a, tag_b)

        factory = APIRequestFactory()
        request = factory.get(f"/orgs/{org_a.slug}/crm/api/deals/")
        request.user = org_a_admin
        request.org = org_a

        serializer = DealDetailSerializer(deal, context={"request": request})
        tag_names = [t["name"] for t in serializer.data["tags"]]
        assert "Org-A-Deal-Tag" in tag_names
        assert "Org-B-Deal-Tag" not in tag_names

    def test_contact_update_rejects_foreign_org_company(
        self, org_a, org_b, org_a_admin
    ):
        """ContactDetailSerializer rejects foreign-org company_id on update."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-update@example.com",
            company=company_a,
            organization=org_a,
        )

        factory = APIRequestFactory()
        request = factory.patch(f"/orgs/{org_a.slug}/crm/api/contacts/{contact.id}/")
        request.user = org_a_admin
        request.org = org_a

        serializer = ContactDetailSerializer(
            contact,
            data={"company_id": company_b.id},
            partial=True,
            context={"request": request},
        )
        assert not serializer.is_valid()
        assert "company_id" in serializer.errors

    def test_deal_update_rejects_foreign_org_stage(self, org_a, org_b, org_a_admin):
        """DealDetailSerializer rejects foreign-org stage_id on update."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Deal, Stage

        company = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-deal-update@example.com",
            company=company,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        deal = Deal.objects.create(
            title="Org-A Deal",
            contact=contact,
            amount=Decimal("1000.00"),
            stage=stage_a,
            organization=org_a,
        )

        factory = APIRequestFactory()
        request = factory.patch(f"/orgs/{org_a.slug}/crm/api/deals/{deal.id}/")
        request.user = org_a_admin
        request.org = org_a

        serializer = DealDetailSerializer(
            deal,
            data={"stage_id": stage_b.id},
            partial=True,
            context={"request": request},
        )
        assert not serializer.is_valid()
        assert "stage_id" in serializer.errors


@pytest.mark.django_db
class TestF118SerializerCreatePathRelatedFieldValidation:
    """F11.8 — Prove serializer related-field validation rejects foreign-org IDs on create.

    The serializer ``validate()`` methods on ``ContactDetailSerializer`` and
    ``DealDetailSerializer`` already reject foreign-org related IDs on both
    create and update paths.  These tests prove the create-path rejection
    behaviour and solo-route parity (foreign-org IDs remain allowed on solo
    routes where org context is absent).

    Coverage matrix:
    - ContactDetailSerializer rejects foreign-org company_id on create
    - ContactDetailSerializer rejects foreign-org tag_ids on create
    - DealDetailSerializer rejects foreign-org contact_id on create
    - DealDetailSerializer rejects foreign-org stage_id on create
    - DealDetailSerializer rejects foreign-org tag_ids on create
    - Solo-route parity: foreign-org related IDs are allowed on create
    """

    def test_contact_create_rejects_foreign_org_company(
        self, org_a, org_b, org_a_admin
    ):
        """ContactDetailSerializer rejects foreign-org company_id on create."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)

        factory = APIRequestFactory()
        request = factory.post(f"/orgs/{org_a.slug}/crm/api/contacts/")
        request.user = org_a_admin
        request.org = org_a

        serializer = ContactDetailSerializer(
            data={
                "first_name": "Org-A",
                "last_name": "Contact",
                "email": "orga-create@example.com",
                "company_id": company_b.id,
            },
            context={"request": request},
        )
        assert not serializer.is_valid()
        assert "company_id" in serializer.errors

    def test_contact_create_rejects_foreign_org_tags(self, org_a, org_b, org_a_admin):
        """ContactDetailSerializer rejects foreign-org tag_ids on create."""
        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Tag

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        tag_b = Tag.objects.create(name="Org-B-Tag", organization=org_b)

        factory = APIRequestFactory()
        request = factory.post(f"/orgs/{org_a.slug}/crm/api/contacts/")
        request.user = org_a_admin
        request.org = org_a

        serializer = ContactDetailSerializer(
            data={
                "first_name": "Org-A",
                "last_name": "Contact",
                "email": "orga-tag-create@example.com",
                "company_id": company_a.id,
                "tag_ids": [tag_b.id],
            },
            context={"request": request},
        )
        assert not serializer.is_valid()
        assert "tag_ids" in serializer.errors

    def test_deal_create_rejects_foreign_org_contact(self, org_a, org_b, org_a_admin):
        """DealDetailSerializer rejects foreign-org contact_id on create."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Stage

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-deal-create@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)

        factory = APIRequestFactory()
        request = factory.post(f"/orgs/{org_a.slug}/crm/api/deals/")
        request.user = org_a_admin
        request.org = org_a

        serializer = DealDetailSerializer(
            data={
                "title": "Org-A Deal",
                "contact_id": contact_b.id,
                "amount": str(Decimal("1000.00")),
                "stage_id": stage_a.id,
            },
            context={"request": request},
        )
        assert not serializer.is_valid()
        assert "contact_id" in serializer.errors

    def test_deal_create_rejects_foreign_org_stage(self, org_a, org_b, org_a_admin):
        """DealDetailSerializer rejects foreign-org stage_id on create."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Stage

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-deal-stage-create@example.com",
            company=company_a,
            organization=org_a,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)

        factory = APIRequestFactory()
        request = factory.post(f"/orgs/{org_a.slug}/crm/api/deals/")
        request.user = org_a_admin
        request.org = org_a

        serializer = DealDetailSerializer(
            data={
                "title": "Org-A Deal",
                "contact_id": contact_a.id,
                "amount": str(Decimal("1000.00")),
                "stage_id": stage_b.id,
            },
            context={"request": request},
        )
        assert not serializer.is_valid()
        assert "stage_id" in serializer.errors

    def test_deal_create_rejects_foreign_org_tags(self, org_a, org_b, org_a_admin):
        """DealDetailSerializer rejects foreign-org tag_ids on create."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Stage, Tag

        company_a = Company.objects.create(name="Org-A Corp", organization=org_a)
        contact_a = Contact.objects.create(
            first_name="Org-A",
            last_name="Contact",
            email="orga-deal-tag-create@example.com",
            company=company_a,
            organization=org_a,
        )
        stage_a = Stage.objects.create(name="Org-A Stage", order=1, organization=org_a)
        tag_b = Tag.objects.create(name="Org-B-Deal-Tag", organization=org_b)

        factory = APIRequestFactory()
        request = factory.post(f"/orgs/{org_a.slug}/crm/api/deals/")
        request.user = org_a_admin
        request.org = org_a

        serializer = DealDetailSerializer(
            data={
                "title": "Org-A Deal",
                "contact_id": contact_a.id,
                "amount": str(Decimal("1000.00")),
                "stage_id": stage_a.id,
                "tag_ids": [tag_b.id],
            },
            context={"request": request},
        )
        assert not serializer.is_valid()
        assert "tag_ids" in serializer.errors

    @override_settings(QUICKSCALE_MODE="solo")
    def test_solo_route_allows_foreign_org_related_ids_on_create(
        self, staff_user, org_a, org_b
    ):
        """Solo routes allow foreign-org related IDs on create (parity preserved)."""
        from decimal import Decimal

        from rest_framework.test import APIRequestFactory

        from quickscale_modules_crm.models import Company, Contact, Stage, Tag

        company_b = Company.objects.create(name="Org-B Corp", organization=org_b)
        contact_b = Contact.objects.create(
            first_name="Org-B",
            last_name="Contact",
            email="orgb-solo@example.com",
            company=company_b,
            organization=org_b,
        )
        stage_b = Stage.objects.create(name="Org-B Stage", order=1, organization=org_b)
        tag_b = Tag.objects.create(name="Org-B-Tag", organization=org_b)

        factory = APIRequestFactory()

        # Contact create with foreign-org company and tags on solo route
        contact_request = factory.post("/crm/api/contacts/")
        contact_request.user = staff_user
        # No request.org on solo routes

        contact_serializer = ContactDetailSerializer(
            data={
                "first_name": "Solo",
                "last_name": "Contact",
                "email": "solo-contact@example.com",
                "company_id": company_b.id,
                "tag_ids": [tag_b.id],
            },
            context={"request": contact_request},
        )
        assert contact_serializer.is_valid(), contact_serializer.errors

        # Deal create with foreign-org contact, stage, and tags on solo route
        deal_request = factory.post("/crm/api/deals/")
        deal_request.user = staff_user

        deal_serializer = DealDetailSerializer(
            data={
                "title": "Solo Deal",
                "contact_id": contact_b.id,
                "amount": str(Decimal("1000.00")),
                "stage_id": stage_b.id,
                "tag_ids": [tag_b.id],
            },
            context={"request": deal_request},
        )
        assert deal_serializer.is_valid(), deal_serializer.errors
