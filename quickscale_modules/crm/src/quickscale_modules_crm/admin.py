"""Django admin configuration for CRM module"""

from django.contrib import admin

from .models import Company, Contact, ContactNote, Deal, DealNote, Stage, Tag


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin configuration for Tag model"""

    list_display = ["name", "created_at"]
    search_fields = ["name"]
    ordering = ["name"]


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    """Admin configuration for Company model"""

    list_display = ["name", "industry", "website", "contact_count", "created_at"]
    list_filter = ["industry", "created_at"]
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
class ContactAdmin(admin.ModelAdmin):
    """Admin configuration for Contact model"""

    list_display = [
        "full_name",
        "email",
        "phone",
        "company",
        "status",
        "last_contacted_at",
        "created_at",
    ]
    list_filter = ["status", "company", "tags", "created_at"]
    search_fields = ["first_name", "last_name", "email", "company__name"]
    filter_horizontal = ["tags"]
    readonly_fields = ["created_at", "updated_at"]
    inlines = [ContactNoteInline]
    fieldsets = (
        (None, {"fields": ("first_name", "last_name", "email", "phone", "title")}),
        ("Organization", {"fields": ("company", "tags")}),
        ("Status", {"fields": ("status", "last_contacted_at")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    """Admin configuration for Stage model"""

    list_display = ["name", "order", "deal_count"]
    list_editable = ["order"]
    ordering = ["order"]

    def deal_count(self, obj: Stage) -> int:
        """Return the number of deals in this stage"""
        return obj.deals.count()  # type: ignore

    deal_count.short_description = "Deals"  # type: ignore


class DealNoteInline(admin.TabularInline):
    """Inline admin for DealNote"""

    model = DealNote
    extra = 1
    readonly_fields = ["created_at", "created_by"]
    fields = ["text", "created_by", "created_at"]


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    """Admin configuration for Deal model"""

    list_display = [
        "title",
        "contact",
        "stage",
        "amount",
        "probability",
        "owner",
        "expected_close_date",
        "created_at",
    ]
    list_filter = ["stage", "owner", "tags", "created_at"]
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
    fieldsets = (
        (None, {"fields": ("title", "contact", "amount")}),
        ("Pipeline", {"fields": ("stage", "probability", "expected_close_date")}),
        ("Assignment", {"fields": ("owner", "tags")}),
        (
            "Metadata",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )


@admin.register(ContactNote)
class ContactNoteAdmin(admin.ModelAdmin):
    """Admin configuration for ContactNote model"""

    list_display = ["contact", "created_by", "short_text", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["contact__first_name", "contact__last_name", "text"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["contact"]

    def short_text(self, obj: ContactNote) -> str:
        """Return truncated note text"""
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    short_text.short_description = "Text"  # type: ignore


@admin.register(DealNote)
class DealNoteAdmin(admin.ModelAdmin):
    """Admin configuration for DealNote model"""

    list_display = ["deal", "created_by", "short_text", "created_at"]
    list_filter = ["created_at"]
    search_fields = ["deal__title", "text"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["deal"]

    def short_text(self, obj: DealNote) -> str:
        """Return truncated note text"""
        return obj.text[:50] + "..." if len(obj.text) > 50 else obj.text

    short_text.short_description = "Text"  # type: ignore
