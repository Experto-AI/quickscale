"""Django admin configuration for QuickScale Forms module"""

from typing import Any

from django.contrib import admin
from django.db.models import Count, QuerySet
from django.http import HttpRequest

from quickscale_modules_orgs.admin import TenantModelAdmin

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
)


class FormFieldInline(admin.TabularInline):
    """Inline editor for form fields within the Form admin"""

    model = FormField
    extra = 1
    fields = ["field_type", "label", "name", "required", "order", "is_active"]


@admin.register(Form)
class FormAdmin(TenantModelAdmin):
    """Admin interface for managing form definitions"""

    list_display = [
        "title",
        "slug",
        "organization",
        "is_active",
        "submission_count",
        "created_at",
    ]
    list_filter = ["organization", "is_active", "created_at"]
    search_fields = ["title", "slug"]
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ["created_at", "updated_at", "created_by"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: object | None = None
    ) -> list[str] | tuple[str, ...]:
        """Make organization read-only on change to prevent parent/child desync."""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and "organization" not in readonly:
            readonly.append("organization")
        return readonly

    fieldsets = [
        ("General", {"fields": ["title", "slug", "organization", "description"]}),
        ("Behaviour", {"fields": ["is_active", "spam_protection_enabled"]}),
        ("Notifications", {"fields": ["notify_emails"]}),
        (
            "Data Retention",
            {"fields": ["data_retention_days", "success_message", "redirect_url"]},
        ),
        (
            "Metadata",
            {
                "fields": ["created_by", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]
    inlines = [FormFieldInline]
    actions = ["mark_inactive", "mark_active"]

    def save_formset(
        self,
        request: HttpRequest,
        form: object,
        formset: Any,
        change: bool,
    ) -> None:
        """Stamp organization on new inline FormField instances from the parent Form."""
        instances = formset.save(commit=False)
        for obj in formset.new_objects:
            obj.organization = formset.instance.organization
        for obj in instances:
            obj.save()
        for obj in formset.deleted_objects:
            obj.delete()
        formset.save_m2m()

    def save_model(
        self, request: HttpRequest, obj: Form, form: object, change: bool
    ) -> None:
        # Track which admin user created this form
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def get_queryset(self, request: HttpRequest) -> QuerySet:
        """Org-scoped queryset with submission count annotation."""
        qs = super().get_queryset(request)
        return qs.annotate(  # type: ignore[no-any-return]
            _submission_count=Count("submissions")
        )

    @admin.display(description="Submissions", ordering="_submission_count")
    def submission_count(self, obj: Form) -> int:
        return obj._submission_count  # type: ignore[no-any-return]

    @admin.action(description="Mark selected forms as inactive")
    def mark_inactive(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(is_active=False)

    @admin.action(description="Mark selected forms as active")
    def mark_active(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(is_active=True)


class FormFieldValueInline(admin.TabularInline):
    """Read-only inline for viewing submitted field values within a submission"""

    model = FormFieldValue
    readonly_fields = ["field_name", "field_label", "value", "field"]
    extra = 0
    can_delete = False


@admin.register(FormSubmission)
class FormSubmissionAdmin(TenantModelAdmin):
    """Admin interface for reviewing and managing form submissions"""

    list_display = ["form", "status", "is_spam", "submitted_at", "ip_address"]
    list_filter = ["status", "is_spam", "form", "submitted_at"]
    search_fields = ["values__value", "ip_address"]
    readonly_fields = ["form", "ip_address", "user_agent", "submitted_at"]

    def get_readonly_fields(
        self, request: HttpRequest, obj: object | None = None
    ) -> list[str] | tuple[str, ...]:
        """Make organization read-only on change to prevent parent/child desync."""
        readonly = list(super().get_readonly_fields(request, obj))
        if obj is not None and "organization" not in readonly:
            readonly.append("organization")
        return readonly

    inlines = [FormFieldValueInline]
    actions = ["mark_as_spam", "mark_as_read", "mark_as_replied", "mark_as_archived"]

    @admin.action(description="Mark selected submissions as spam")
    def mark_as_spam(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(is_spam=True)

    @admin.action(description="Mark selected submissions as read")
    def mark_as_read(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(status=FormSubmission.STATUS_READ)

    @admin.action(description="Mark selected submissions as replied")
    def mark_as_replied(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(status=FormSubmission.STATUS_REPLIED)

    @admin.action(description="Mark selected submissions as archived")
    def mark_as_archived(self, request: HttpRequest, queryset: QuerySet) -> None:
        queryset.update(status=FormSubmission.STATUS_ARCHIVED)
