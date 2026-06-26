"""DRF serializers for CRM module models"""

from django.db import models
from rest_framework import serializers

from .models import Company, Contact, ContactNote, Deal, DealNote, Stage, Tag


def _request_org_id(serializer: serializers.Serializer) -> int | str | None:
    """Return the current organization ID for create stamping.

    T1.5 flat-route contract: resolves ``request.org`` (set by
    ``TenantMiddleware``).  Falls back to personal-org lookup for tests
    that bypass middleware.  Raises ``ValidationError`` when no org
    context is available.

    The contextvar is already set by ``TenantMiddleware._call_with_org``
    via ``org_scope()``; this function only reads the org ID for stamping
    purposes and does not re-set the contextvar (T1.19 — unified entry
    point).
    """
    request = serializer.context.get("request")
    if request is None:
        return None

    org = getattr(request, "org", None)
    if org is not None:
        return org.id

    # Fallback: look up the user's personal org (for tests).
    user = getattr(request, "user", None)
    if user is not None and getattr(user, "is_authenticated", False):
        from quickscale_modules_orgs.models import Organization

        personal_org = Organization.objects.filter(
            is_personal=True, memberships__user=user
        ).first()
        if personal_org is not None:
            request.org = personal_org
            return personal_org.id

    raise serializers.ValidationError(
        "Organization context is required for this route.",
        code="org_required",
    )


def _read_org_id(serializer: serializers.Serializer) -> int | str | None:
    """Return the current organization ID for read filtering.

    T1.5 flat-route contract: always returns the active org ID from
    ``request.org``, or ``None`` when no request context is available.

    The contextvar is already set by ``TenantMiddleware._call_with_org``
    via ``org_scope()``; this function only reads the org ID for
    scoping purposes and does not re-set the contextvar (T1.19 —
    unified entry point).
    """
    request = serializer.context.get("request")
    if request is None:
        return None

    org = getattr(request, "org", None)
    if org is not None:
        return org.id

    return None


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
        """Reject duplicate tag names within the same org bucket.

        Uses ``all_objects`` to bypass TenantManager auto-scoping so the
        duplicate check queries against the full table, filtered explicitly
        by ``organization_id``.
        """
        if self.instance is not None:
            organization_id = self.instance.organization_id
        else:
            organization_id = _request_org_id(self)
        qs = Tag.all_objects.filter(name=value, organization_id=organization_id)
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
        """Return the number of contacts for this company, scoped to active org."""
        org_id = _read_org_id(self)
        if org_id is not None:
            return Contact.all_objects.filter(
                company=obj, organization_id=org_id
            ).count()
        return Contact.all_objects.filter(company=obj).count()

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

    def validate(self, attrs: dict) -> dict:
        """Reject foreign-org parent contact on all create routes.

        When creating a ContactNote, the parent contact must belong to the
        caller's active organization (or have NULL organization for legacy/
        solo compatibility).  Foreign-org parent references are rejected.
        """
        org_id = _request_org_id(self)
        if org_id is None:
            # No org context — skip foreign-org validation.
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
                        "contact": "The specified contact does not belong to this organization."
                    }
                )

        return attrs

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

        T1.5: scoped to the active organization.
        """
        org_id = _read_org_id(self)
        if org_id is not None:
            return list(
                Tag.all_objects.filter(
                    contacts=obj, organization_id=org_id
                ).values_list("name", flat=True)
            )
        return list(Tag.all_objects.filter(contacts=obj).values_list("name", flat=True))


class ContactDetailSerializer(serializers.ModelSerializer):
    """Serializer for Contact detail view (full fields with nested data)"""

    company = CompanySerializer(read_only=True)
    company_id = serializers.PrimaryKeyRelatedField(
        queryset=Company.all_objects.all(),
        source="company",
        write_only=True,
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.all_objects.all(),
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
        """Return the number of deals for this contact, scoped to active org."""
        org_id = _read_org_id(self)
        if org_id is not None:
            return Deal.all_objects.filter(contact=obj, organization_id=org_id).count()
        return Deal.all_objects.filter(contact=obj).count()

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
        """Reject foreign-org related IDs on all create and update routes.

        When creating or updating, the related company and tags must belong
        to the same organization (or have NULL organization for legacy/solo
        compatibility). Foreign-org references are rejected.  The active
        organization is resolved from ``request.org`` (set by middleware) or
        the personal-org fallback for solo routes.
        """
        org_id = _request_org_id(self)
        if org_id is None:
            # No org context — skip foreign-org validation.
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
        """Return the number of deals in this stage, scoped to the active org.

        Uses ``all_objects`` to bypass TenantManager auto-scoping; the
        explicit ``organization_id`` filter handles scoping.
        """
        org_id = _read_org_id(self)
        if org_id is not None:
            return Deal.all_objects.filter(stage=obj, organization_id=org_id).count()
        return Deal.all_objects.filter(stage=obj).count()

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

    def validate(self, attrs: dict) -> dict:
        """Reject foreign-org parent deal on all create routes.

        When creating a DealNote, the parent deal must belong to the
        caller's active organization (or have NULL organization for
        legacy/solo compatibility).  Foreign-org parent references
        are rejected.
        """
        org_id = _request_org_id(self)
        if org_id is None:
            # No org context — skip foreign-org validation.
            return attrs

        # Validate deal_id belongs to the current org.
        deal = attrs.get("deal")
        if deal is not None:
            if deal.organization_id is not None and deal.organization_id != org_id:
                raise serializers.ValidationError(
                    {"deal": "The specified deal does not belong to this organization."}
                )

        return attrs

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

        T1.5: scoped to the active organization.
        """
        org_id = _read_org_id(self)
        if org_id is not None:
            return list(
                Tag.all_objects.filter(deals=obj, organization_id=org_id).values_list(
                    "name", flat=True
                )
            )
        return list(Tag.all_objects.filter(deals=obj).values_list("name", flat=True))


class DealDetailSerializer(serializers.ModelSerializer):
    """Serializer for Deal detail view (full fields with nested data)"""

    contact = ContactListSerializer(read_only=True)
    contact_id = serializers.PrimaryKeyRelatedField(
        queryset=Contact.all_objects.all(),
        source="contact",
        write_only=True,
    )
    stage = StageSerializer(read_only=True)
    stage_id = serializers.PrimaryKeyRelatedField(
        queryset=Stage.all_objects.all(),
        source="stage",
        write_only=True,
    )
    tags = TagSerializer(many=True, read_only=True)
    tag_ids = serializers.PrimaryKeyRelatedField(
        queryset=Tag.all_objects.all(),
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
        """Reject foreign-org related IDs on all create and update routes.

        When creating or updating, the related contact, stage, and tags
        must belong to the same organization (or have NULL organization for
        legacy/solo compatibility). Foreign-org references are rejected.
        The active organization is resolved from ``request.org`` (set by
        middleware) or the personal-org fallback for solo routes.
        """
        org_id = _request_org_id(self)
        if org_id is None:
            # No org context — skip foreign-org validation.
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
    stage_id = serializers.PrimaryKeyRelatedField(queryset=Stage.all_objects.all())

    def validate_stage_id(self, value: Stage) -> Stage:
        """Reject non-owned stages.

        T1.5 flat-route contract: the target stage must belong to the active
        organization resolved from ``request.org`` (set by middleware) or the
        personal-org fallback.
        """
        request = self.context.get("request")
        if request is None:
            return value

        org = getattr(request, "org", None)
        if org is None:
            user = getattr(request, "user", None)
            if user is not None and getattr(user, "is_authenticated", False):
                from quickscale_modules_orgs.models import Organization

                personal_org = Organization.objects.filter(
                    is_personal=True, memberships__user=user
                ).first()
                if personal_org is not None:
                    org = personal_org
                    request.org = personal_org  # type: ignore[union-attr]

        if org is None:
            raise serializers.ValidationError(
                "Organization context is required for this route.",
                code="org_required",
            )
        if value.organization_id != org.id:  # type: ignore[attr-defined]
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
