"""DRF serializers for CRM module models"""

from django.db import models
from rest_framework import serializers

from .models import Company, Contact, ContactNote, Deal, DealNote, Stage, Tag


def _request_org_id(serializer: serializers.Serializer) -> int | str | None:
    """Return the current organization ID for org-scoped create stamping.

    Stamping only applies to true org-scoped routes (``/orgs/<slug>/...``).
    In solo mode the TenantMiddleware attaches a personal org to ``request.org``
    for all authenticated requests, but solo routes must NOT be stamped — they
    retain the legacy NULL-org behavior.  The path check ensures stamping is
    limited to the ``/orgs/`` namespace regardless of ``QUICKSCALE_MODE``.

    On org-scoped routes, if the request lacks org context (``request.org``
    is ``None``), a ``ValidationError`` is raised to fail closed rather than
    silently persisting a NULL-owned row.
    """
    request = serializer.context.get("request")
    if request is None:
        return None
    path = getattr(request, "path", "") or ""
    if not path.startswith("/orgs/"):
        return None
    org = getattr(request, "org", None)
    if org is None:
        raise serializers.ValidationError(
            "Organization context is required for this route.",
            code="org_required",
        )
    return org.id


def _read_org_id(serializer: serializers.Serializer) -> int | str | None:
    """Return the current organization ID for org-scoped read filtering.

    Used by serializer helper methods (counts, tag names) to scope related
    queries when serializing on an org-scoped SaaS route.  Returns ``None``
    on solo routes so that legacy unscoped behavior is preserved.
    """
    request = serializer.context.get("request")
    if request is None:
        return None
    path = getattr(request, "path", "") or ""
    if not path.startswith("/orgs/"):
        return None
    org = getattr(request, "org", None)
    return org.id if org is not None else None


def _is_foreign_org_related(
    related_obj: models.Model | None, org_id: int | str | None
) -> bool:
    """Return whether a related object belongs to a different organization.

    Returns ``False`` when org_id is ``None`` (solo route) or when the
    related object has ``organization_id=None`` (legacy/solo compatibility).
    Returns ``True`` only when both the org context and the related object's
    organization are non-NULL and differ.
    """
    if org_id is None or related_obj is None:
        return False
    related_org_id = getattr(related_obj, "organization_id", None)
    return related_org_id is not None and related_org_id != org_id


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model"""

    class Meta:
        model = Tag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_name(self, value: str) -> str:
        """Reject duplicate tag names within the same owner bucket.

        Owner bucket = (name, organization).  On create the bucket uses the
        request's current org (stamped at save time).  On update the bucket
        uses the existing instance's org.  NULL organization is a single
        bucket (legacy NULL-owned duplicates stay blocked).  Same name across
        different organizations is allowed.
        """
        if self.instance is not None:
            organization_id = self.instance.organization_id
        else:
            organization_id = _request_org_id(self)
        qs = Tag.objects.filter(name=value, organization_id=organization_id)
        if self.instance is not None:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A tag with this name already exists.",
                code="unique",
            )
        return value

    def create(self, validated_data: dict) -> Tag:
        """Stamp the current organization on create."""
        org_id = _request_org_id(self)
        if org_id is not None:
            validated_data.setdefault("organization_id", org_id)
        return super().create(validated_data)


class CompanySerializer(serializers.ModelSerializer):
    """Serializer for Company model"""

    contact_count = serializers.SerializerMethodField()

    class Meta:
        model = Company
        fields = [
            "id",
            "name",
            "industry",
            "website",
            "contact_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_contact_count(self, obj: Company) -> int:
        """Return the number of contacts for this company.

        On org-scoped SaaS routes, only contacts belonging to the active
        organization are counted.  On solo routes, all contacts are counted.
        """
        org_id = _read_org_id(self)
        contacts = obj.contacts  # type: ignore
        if org_id is not None:
            contacts = contacts.filter(organization_id=org_id)
        return contacts.count()

    def validate(self, attrs: dict) -> dict:
        """Fail closed on org-scoped routes without org context."""
        _request_org_id(self)
        return attrs

    def create(self, validated_data: dict) -> Company:
        """Stamp the current organization on create."""
        org_id = _request_org_id(self)
        if org_id is not None:
            validated_data.setdefault("organization_id", org_id)
        return super().create(validated_data)


class ContactNoteSerializer(serializers.ModelSerializer):
    """Serializer for ContactNote model"""

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ContactNote
        fields = [
            "id",
            "contact",
            "created_by",
            "created_by_name",
            "text",
            "created_at",
        ]
        read_only_fields = ["id", "created_by", "created_at"]

    def get_created_by_name(self, obj: ContactNote) -> str:
        """Return the name of the user who created the note"""
        if obj.created_by:
            return str(obj.created_by)
        return ""

    def create(self, validated_data: dict) -> ContactNote:
        """Set created_by to the current user"""
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class ContactListSerializer(serializers.ModelSerializer):
    """Serializer for Contact list view (minimal fields)"""

    company_name = serializers.SerializerMethodField()
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "title",
            "status",
            "company",
            "company_name",
            "tag_names",
            "last_contacted_at",
            "created_at",
        ]
        read_only_fields = ["id", "full_name", "created_at"]

    def get_company_name(self, obj: Contact) -> str:
        """Return the company name, omitting foreign-org companies on org-scoped routes.

        On org-scoped SaaS routes, if the contact's company belongs to a
        different organization, an empty string is returned to prevent
        leaking foreign-org metadata.  On solo routes, the company name
        is always returned.
        """
        org_id = _read_org_id(self)
        company = obj.company
        if _is_foreign_org_related(company, org_id):
            return ""
        return company.name if company else ""

    def get_tag_names(self, obj: Contact) -> list[str]:
        """Return list of tag names.

        On org-scoped SaaS routes, only tags belonging to the active
        organization are included.  On solo routes, all tags are included.
        """
        tags_qs = obj.tags.all()
        org_id = _read_org_id(self)
        if org_id is not None:
            tags_qs = tags_qs.filter(organization_id=org_id)
        return list(tags_qs.values_list("name", flat=True))


class ContactDetailSerializer(serializers.ModelSerializer):
    """Serializer for Contact detail view (full fields with nested data)"""

    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.objects.all(),
        source="company",
        write_only=True,
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        source="tags",
        many=True,
        write_only=True,
        required=False,
    )
    notes = ContactNoteSerializer(many=True, read_only=True)
    deal_count = serializers.SerializerMethodField()

    class Meta:
        model = Contact
        fields = [
            "id",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "phone",
            "title",
            "status",
            "last_contacted_at",
            "company",
            "company_id",
            "tags",
            "tag_ids",
            "notes",
            "deal_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "full_name", "created_at", "updated_at"]

    def get_deal_count(self, obj: Contact) -> int:
        """Return the number of deals for this contact.

        On org-scoped SaaS routes, only deals belonging to the active
        organization are counted.  On solo routes, all deals are counted.
        """
        org_id = _read_org_id(self)
        deals = obj.deals  # type: ignore
        if org_id is not None:
            deals = deals.filter(organization_id=org_id)
        return deals.count()

    def to_representation(self, instance: Contact) -> dict:
        """Omit foreign-org related objects on org-scoped reads.

        On org-scoped SaaS routes, the nested ``company`` is set to ``None``
        and ``tags`` are filtered to only include same-org tags when the
        related objects belong to a different organization.  Solo routes
        preserve legacy unscoped behavior.
        """
        data = super().to_representation(instance)
        org_id = _read_org_id(self)
        if org_id is not None:
            if _is_foreign_org_related(instance.company, org_id):
                data["company"] = None
            # Filter tags to only same-org tags on org-scoped routes.
            if instance.tags.exists():
                data["tags"] = [
                    tag_data
                    for tag_data, tag_obj in zip(
                        data["tags"],
                        instance.tags.all(),
                    )
                    if not _is_foreign_org_related(tag_obj, org_id)
                ]
        return data

    def validate(self, attrs: dict) -> dict:
        """Reject foreign-org related IDs on org-scoped create and update.

        When creating or updating via an org-scoped route, the related
        company and tags must belong to the same organization (or have
        NULL organization for legacy/solo compatibility). Foreign-org
        references are rejected.
        """
        org_id = _request_org_id(self)
        if org_id is None:
            # Solo route or no org context — skip foreign-org validation.
            return attrs

        # Validate company_id belongs to the current org.
        company = attrs.get("company")
        if company is not None:
            if (
                company.organization_id is not None
                and company.organization_id != org_id
            ):
                raise serializers.ValidationError(
                    {
                        "company_id": "The specified company does not belong to this organization."
                    }
                )

        # Validate tag_ids belong to the current org.
        tags = attrs.get("tags")
        if tags:
            foreign_tags = [
                tag
                for tag in tags
                if tag.organization_id is not None and tag.organization_id != org_id
            ]
            if foreign_tags:
                raise serializers.ValidationError(
                    {
                        "tag_ids": "One or more specified tags do not belong to this organization."
                    }
                )

        return attrs

    def create(self, validated_data: dict) -> Contact:
        """Stamp the current organization on create."""
        org_id = _request_org_id(self)
        if org_id is not None:
            validated_data.setdefault("organization_id", org_id)
        return super().create(validated_data)


class StageSerializer(serializers.ModelSerializer):
    """Serializer for Stage model"""

    deal_count = serializers.SerializerMethodField()

    class Meta:
        model = Stage
        fields = ["id", "name", "order", "deal_count"]
        read_only_fields = ["id"]

    def get_deal_count(self, obj: Stage) -> int:
        """Return the number of deals in this stage.

        On org-scoped SaaS routes, only deals belonging to the active
        organization are counted.  On solo routes, all deals are counted.
        """
        org_id = _read_org_id(self)
        deals = obj.deals  # type: ignore
        if org_id is not None:
            deals = deals.filter(organization_id=org_id)
        return deals.count()

    def validate(self, attrs: dict) -> dict:
        """Fail closed on org-scoped routes without org context."""
        _request_org_id(self)
        return attrs

    def create(self, validated_data: dict) -> Stage:
        """Stamp the current organization on create."""
        org_id = _request_org_id(self)
        if org_id is not None:
            validated_data.setdefault("organization_id", org_id)
        return super().create(validated_data)


class DealNoteSerializer(serializers.ModelSerializer):
    """Serializer for DealNote model"""

    created_by_name = serializers.SerializerMethodField()

    class Meta:
        model = DealNote
        fields = ["id", "deal", "created_by", "created_by_name", "text", "created_at"]
        read_only_fields = ["id", "created_by", "created_at"]

    def get_created_by_name(self, obj: DealNote) -> str:
        """Return the name of the user who created the note"""
        if obj.created_by:
            return str(obj.created_by)
        return ""

    def create(self, validated_data: dict) -> DealNote:
        """Set created_by to the current user"""
        validated_data["created_by"] = self.context["request"].user
        return super().create(validated_data)


class DealListSerializer(serializers.ModelSerializer):
    """Serializer for Deal list view (minimal fields)"""

    contact_name = serializers.SerializerMethodField()
    company_name = serializers.SerializerMethodField()
    stage_name = serializers.SerializerMethodField()
    owner_name = serializers.SerializerMethodField()
    tag_names = serializers.SerializerMethodField()

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "contact",
            "contact_name",
            "company_name",
            "amount",
            "stage",
            "stage_name",
            "expected_close_date",
            "probability",
            "owner",
            "owner_name",
            "tag_names",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]

    def get_contact_name(self, obj: Deal) -> str:
        """Return the contact name, omitting foreign-org contacts on org-scoped routes."""
        org_id = _read_org_id(self)
        if _is_foreign_org_related(obj.contact, org_id):
            return ""
        return obj.contact.full_name if obj.contact else ""

    def get_company_name(self, obj: Deal) -> str:
        """Return the company name, omitting foreign-org companies on org-scoped routes."""
        org_id = _read_org_id(self)
        contact = obj.contact
        if contact is None:
            return ""
        company = contact.company
        if _is_foreign_org_related(company, org_id):
            return ""
        return company.name if company else ""

    def get_stage_name(self, obj: Deal) -> str:
        """Return the stage name, omitting foreign-org stages on org-scoped routes."""
        org_id = _read_org_id(self)
        if _is_foreign_org_related(obj.stage, org_id):
            return ""
        return obj.stage.name if obj.stage else ""

    def get_owner_name(self, obj: Deal) -> str:
        """Return the name of the deal owner"""
        if obj.owner:
            return str(obj.owner)
        return ""

    def get_tag_names(self, obj: Deal) -> list[str]:
        """Return list of tag names.

        On org-scoped SaaS routes, only tags belonging to the active
        organization are included.  On solo routes, all tags are included.
        """
        tags_qs = obj.tags.all()
        org_id = _read_org_id(self)
        if org_id is not None:
            tags_qs = tags_qs.filter(organization_id=org_id)
        return list(tags_qs.values_list("name", flat=True))


class DealDetailSerializer(serializers.ModelSerializer):
    """Serializer for Deal detail view (full fields with nested data)"""

    contact = ContactListSerializer(read_only=True)
    contact_id = serializers.PrimaryKeyRelatedField(
        queryset=Contact.objects.all(),
        source="contact",
        write_only=True,
    )
    stage = StageSerializer(read_only=True)
    stage_id = serializers.PrimaryKeyRelatedField(
        queryset=Stage.objects.all(),
        source="stage",
        write_only=True,
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        source="tags",
        many=True,
        write_only=True,
        required=False,
    )
    notes = DealNoteSerializer(many=True, read_only=True)

    class Meta:
        model = Deal
        fields = [
            "id",
            "title",
            "contact",
            "contact_id",
            "amount",
            "stage",
            "stage_id",
            "expected_close_date",
            "probability",
            "owner",
            "tags",
            "tag_ids",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def to_representation(self, instance: Deal) -> dict:
        """Omit foreign-org related objects on org-scoped reads.

        On org-scoped SaaS routes, the nested ``contact``, ``stage``, and
        ``tags`` are filtered to prevent leaking foreign-org metadata.
        Solo routes preserve legacy unscoped behavior.
        """
        data = super().to_representation(instance)
        org_id = _read_org_id(self)
        if org_id is not None:
            if _is_foreign_org_related(instance.contact, org_id):
                data["contact"] = None
            if _is_foreign_org_related(instance.stage, org_id):
                data["stage"] = None
            # Filter tags to only same-org tags on org-scoped routes.
            if instance.tags.exists():
                data["tags"] = [
                    tag_data
                    for tag_data, tag_obj in zip(
                        data["tags"],
                        instance.tags.all(),
                    )
                    if not _is_foreign_org_related(tag_obj, org_id)
                ]
        return data

    def validate(self, attrs: dict) -> dict:
        """Reject foreign-org related IDs on org-scoped create and update.

        When creating or updating via an org-scoped route, the related
        contact, stage, and tags must belong to the same organization (or
        have NULL organization for legacy/solo compatibility). Foreign-org
        references are rejected.
        """
        org_id = _request_org_id(self)
        if org_id is None:
            # Solo route or no org context — skip foreign-org validation.
            return attrs

        # Validate contact_id belongs to the current org.
        contact = attrs.get("contact")
        if contact is not None:
            if (
                contact.organization_id is not None
                and contact.organization_id != org_id
            ):
                raise serializers.ValidationError(
                    {
                        "contact_id": "The specified contact does not belong to this organization."
                    }
                )

        # Validate stage_id belongs to the current org.
        stage = attrs.get("stage")
        if stage is not None:
            if stage.organization_id is not None and stage.organization_id != org_id:
                raise serializers.ValidationError(
                    {
                        "stage_id": "The specified stage does not belong to this organization."
                    }
                )

        # Validate tag_ids belong to the current org.
        tags = attrs.get("tags")
        if tags:
            foreign_tags = [
                tag
                for tag in tags
                if tag.organization_id is not None and tag.organization_id != org_id
            ]
            if foreign_tags:
                raise serializers.ValidationError(
                    {
                        "tag_ids": "One or more specified tags do not belong to this organization."
                    }
                )

        return attrs

    def create(self, validated_data: dict) -> Deal:
        """Stamp the current organization on create."""
        org_id = _request_org_id(self)
        if org_id is not None:
            validated_data.setdefault("organization_id", org_id)
        return super().create(validated_data)


class BulkUpdateStageSerializer(serializers.Serializer):
    """Serializer for bulk stage update action"""

    deal_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )
    stage_id = serializers.PrimaryKeyRelatedField(queryset=Stage.objects.all())

    def validate_stage_id(self, value: Stage) -> Stage:
        """Reject foreign-org stages on org-scoped routes.

        On org-scoped SaaS routes, the target stage must belong to the same
        organization (or have NULL organization for legacy/solo compatibility).
        Foreign-org stages are rejected.  Solo routes preserve legacy behavior.
        """
        request = self.context.get("request")
        if request is None:
            return value
        path = getattr(request, "path", "") or ""
        if not path.startswith("/orgs/"):
            # Solo route — no org-scoped validation.
            return value
        org = getattr(request, "org", None)
        if org is None:
            # Org-scoped route without org context — fail closed.
            raise serializers.ValidationError(
                "Organization context is required for this route.",
                code="org_required",
            )
        if value.organization_id is not None and value.organization_id != org.id:
            raise serializers.ValidationError(
                "The specified stage does not belong to this organization.",
                code="foreign_org",
            )
        return value


class BulkMarkSerializer(serializers.Serializer):
    """Serializer for bulk mark as won/lost action"""

    deal_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )
