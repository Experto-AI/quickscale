"""DRF serializers for CRM module models"""

from rest_framework import serializers

from .models import Company, Contact, ContactNote, Deal, DealNote, Stage, Tag


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model"""

    class Meta:
        model = Tag
        fields = ["id", "name", "created_at"]
        read_only_fields = ["id", "created_at"]


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
        """Return the number of contacts for this company"""
        return obj.contacts.count()  # type: ignore


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

    company_name = serializers.CharField(source="company.name", read_only=True)
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

    def get_tag_names(self, obj: Contact) -> list[str]:
        """Return list of tag names"""
        return list(obj.tags.values_list("name", flat=True))


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
        """Return the number of deals for this contact"""
        return obj.deals.count()  # type: ignore


class StageSerializer(serializers.ModelSerializer):
    """Serializer for Stage model"""

    deal_count = serializers.SerializerMethodField()

    class Meta:
        model = Stage
        fields = ["id", "name", "order", "deal_count"]
        read_only_fields = ["id"]

    def get_deal_count(self, obj: Stage) -> int:
        """Return the number of deals in this stage"""
        return obj.deals.count()  # type: ignore


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

    contact_name = serializers.CharField(source="contact.full_name", read_only=True)
    company_name = serializers.CharField(source="contact.company.name", read_only=True)
    stage_name = serializers.CharField(source="stage.name", read_only=True)
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

    def get_owner_name(self, obj: Deal) -> str:
        """Return the name of the deal owner"""
        if obj.owner:
            return str(obj.owner)
        return ""

    def get_tag_names(self, obj: Deal) -> list[str]:
        """Return list of tag names"""
        return list(obj.tags.values_list("name", flat=True))


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


class BulkUpdateStageSerializer(serializers.Serializer):
    """Serializer for bulk stage update action"""

    deal_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )
    stage_id = serializers.PrimaryKeyRelatedField(queryset=Stage.objects.all())


class BulkMarkSerializer(serializers.Serializer):
    """Serializer for bulk mark as won/lost action"""

    deal_ids = serializers.ListField(
        child=serializers.IntegerField(),
        min_length=1,
    )
