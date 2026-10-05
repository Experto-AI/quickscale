"""Django admin configuration for CRM module"""

from typing import Any

from django.contrib import admin
from django.forms import ModelForm

from quickscale_modules_orgs.admin import OrgAwareAdminMixin, TenantModelAdmin

from .models import Company, Contact, ContactNote, Deal, DealNote, Stage, Tag


class _CrmOrgAwareAdminMixin(OrgAwareAdminMixin):
    """CRM org-aware admin mixin: adds created_by stamping to the shared behavior.

    Same-org validation, organization-required-on-add, and read-only-on-change
    behavior comes from
    :class:`~quickscale_modules_orgs.admin.OrgAwareAdminMixin`; this subclass
    only adds the CRM-specific operator stamp before saving.
    """

    def save_model(self, request: Any, obj: Any, form: Any, change: bool) -> None:
        # Auto-set created_by from the current user for note models
        # (ContactNote, DealNote) when the form excludes the field.
        # NOTE: Use ``created_by_id`` (the FK column attribute) instead of
        # ``created_by`` (the FK descriptor) because the descriptor raises
        # ``RelatedObjectDoesNotExist`` when the FK is NULL, making
        # ``hasattr(obj, "created_by")`` return ``False``.
        if (
            hasattr(obj, "created_by_id")
            and obj.created_by_id is None
            and request.user.is_authenticated
        ):
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(Tag)
class TagAdmin(_CrmOrgAwareAdminMixin, TenantModelAdmin):
    """Admin configuration for Tag model"""

    list_display = ["name", "organization", "created_at"]
    list_filter = ["organization", "created_at"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(Company)
class CompanyAdmin(_CrmOrgAwareAdminMixin, TenantModelAdmin):
    """Admin configuration for Company model"""

    list_display = [
        "name",
        "industry",
        "website",
        "organization",
        "contact_count",
        "created_at",
    ]
    list_filter = ["organization", "industry", "created_at"]
    search_fields = ["name", "industry"]
    ordering = ["name"]

    def contact_count(self, obj: Company) -> int:
        """Return the number of contacts for this company"""
        return obj.contacts.count()  # type: ignore

    contact_count.short_description = "Contacts"  # type: ignore


class ContactNoteInline(admin.TabularInline):
    """Inline admin for ContactNote"""

    model = ContactNote
    extra = 1
    readonly_fields = ["created_at", "created_by"]
    fields = ["text", "created_by", "created_at"]


@admin.register(Contact)
class ContactAdmin(_CrmOrgAwareAdminMixin, TenantModelAdmin):
    """Admin configuration for Contact model"""

    list_display = [
        "full_name",
        "email",
        "phone",
        "company",
        "organization",
        "status",
        "last_contacted_at",
        "created_at",
    ]
    list_filter = ["organization", "status", "company", "tags", "created_at"]
    search_fields = ["first_name", "last_name", "email", "company__name"]
    filter_horizontal = ["tags"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ContactNoteInline]
    _org_related_fields = ["company", "tags"]
    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email", "phone", "title")}),
        ("Organization", {"fields": ("company", "tags")}),
        ("Status", {"fields": ("status", "last_contacted_at")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def save_formset(  # type: ignore[override]
        self,
        request: Any,
        form: Any,
        formset: Any,
        change: bool,
    ) -> None:
        """Stamp organization and created_by from the parent Contact on inline ContactNote creates."""
        instances = formset.save(commit=False)
        parent_org_id = getattr(form.instance, "organization_id", None)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if (
                hasattr(instance, "organization_id")
                and getattr(instance, "organization_id", None) is None
            ):
                instance.organization_id = parent_org_id
            # Auto-set created_by from the current user for note models
            # (ContactNote, DealNote) when the inline form excludes the field.
            if (
                hasattr(instance, "created_by_id")
                and instance.created_by_id is None
                and request.user.is_authenticated
            ):
                instance.created_by = request.user
            instance.save()
        formset.save_m2m()


@admin.register(Stage)
class StageAdmin(_CrmOrgAwareAdminMixin, TenantModelAdmin):
    """Admin configuration for Stage model"""

    list_display = ["name", "order", "organization", "deal_count"]
    list_filter = ["organization"]
    list_editable = ["order"]
    ordering = ["order"]

    def deal_count(self, obj: Stage) -> int:
        """Return the number of deals in this stage"""
        return obj.deals.count()  # type: ignore

    deal_count.short_description = "Deals"  # type: ignore

    def get_form(
        self,
        request: Any,
        obj: Any | None = None,
        change: bool | None = None,
        **kwargs: Any,
    ) -> type[ModelForm]:  # type: ignore[override]
        """Stage form exposes only name and order (terminal_semantic stays hidden)."""
        form_class = super().get_form(request, obj, change=change, **kwargs)
        # Keep terminal_semantic out of the form — it is managed by the system.
        for hidden in ("terminal_semantic",):
            form_class.base_fields.pop(hidden, None)
        return form_class


class DealNoteInline(admin.TabularInline):
    """Inline admin for DealNote"""

    model = DealNote
    extra = 1
    readonly_fields = ["created_at", "created_by"]
    fields = ["text", "created_by", "created_at"]


@admin.register(Deal)
class DealAdmin(_CrmOrgAwareAdminMixin, TenantModelAdmin):
    """Admin configuration for Deal model"""

    list_display = [
        "title",
        "contact",
        "stage",
        "amount",
        "probability",
        "owner",
        "organization",
        "expected_close_date",
        "created_at",
    ]
    list_filter = ["organization", "stage", "owner", "tags", "created_at"]
    search_fields = [
        "title",
        "contact__first_name",
        "contact__last_name",
        "contact__company__name",
    ]
    filter_horizontal = ["tags"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [DealNoteInline]
    raw_id_fields = ["contact"]
    _org_related_fields = ["contact", "stage", "tags"]
    fieldsets = (
        (None, {"fields": ("title", "contact", "amount")}),
        ("Pipeline", {"fields": ("stage", "probability", "expected_close_date")}),
        ("Assignment", {"fields": ("owner", "tags")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    def save_formset(  # type: ignore[override]
        self,
        request: Any,
        form: Any,
        formset: Any,
        change: bool,
    ) -> None:
        """Stamp organization and created_by from the parent Deal on inline DealNote creates."""
        instances = formset.save(commit=False)
        parent_org_id = getattr(form.instance, "organization_id", None)
        for obj in formset.deleted_objects:
            obj.delete()
        for instance in instances:
            if (
                hasattr(instance, "organization_id")
                and getattr(instance, "organization_id", None) is None
            ):
                instance.organization_id = parent_org_id
            # Auto-set created_by from the current user for note models
            # (ContactNote, DealNote) when the inline form excludes the field.
            if (
                hasattr(instance, "created_by_id")
                and instance.created_by_id is None
                and request.user.is_authenticated
            ):
                instance.created_by = request.user
            instance.save()
        formset.save_m2m()


@admin.register(ContactNote)
class ContactNoteAdmin(_CrmOrgAwareAdminMixin, TenantModelAdmin):
    """Admin configuration for ContactNote model"""

    list_display = ["contact", "created_by", "short_text", "organization", "created_at"]
    list_filter = ["organization", "created_at"]
    search_fields = ["contact__first_name", "contact__last_name", "text"]
    readonly_fields = ["created_at", "created_by"]
    raw_id_fields = ["contact"]
    _org_related_fields: list[str] = ["contact"]

    def short_text(self, obj: ContactNote) -> str:
        """Return truncated note text"""
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    short_text.short_description = "Text"  # type: ignore


@admin.register(DealNote)
class DealNoteAdmin(_CrmOrgAwareAdminMixin, TenantModelAdmin):
    """Admin configuration for DealNote model"""

    list_display = ["deal", "created_by", "short_text", "organization", "created_at"]
    list_filter = ["organization", "created_at"]
    search_fields = ["deal__title", "text"]
    readonly_fields = ["created_at", "created_by"]
    raw_id_fields = ["deal"]
    _org_related_fields: list[str] = ["deal"]

    def short_text(self, obj: DealNote) -> str:
        """Return truncated note text"""
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    short_text.short_description = "Text"  # type: ignore
