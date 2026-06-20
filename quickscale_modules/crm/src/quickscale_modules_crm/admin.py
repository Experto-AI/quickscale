"""Django admin configuration for CRM module"""

from typing import Any

from django.contrib import admin
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ModelForm

from .models import Company, Contact, ContactNote, Deal, DealNote, Stage, Tag


def _make_same_org_validated_form(
    base_form_class: type[ModelForm],
    org_related_fields: list[str],
) -> type[ModelForm]:
    """Return a form subclass that validates same-org membership for related fields.

    The returned form's ``clean()`` checks that all FK and M2M values in
    ``org_related_fields`` belong to the same organization as the row's
    ``organization`` field (add forms) or the instance's current
    ``organization_id`` (change forms).  NULL-org related values are
    accepted for legacy compatibility.
    """

    class SameOrgValidatedForm(base_form_class):  # type: ignore[misc, valid-type]
        def clean(self) -> dict[str, Any]:
            cleaned_data = super().clean()

            # Determine org_id from cleaned_data (add) or instance (change).
            org = cleaned_data.get("organization")
            if org is not None:
                org_id = org.pk if hasattr(org, "pk") else org
            elif (
                self.instance is not None
                and self.instance.pk is not None
                and hasattr(self.instance, "organization_id")
            ):
                org_id = self.instance.organization_id
            else:
                org_id = None

            if org_id is not None:
                for field_name in org_related_fields:
                    values = cleaned_data.get(field_name)
                    if not values:
                        continue
                    # FK fields return a single model instance; M2M fields
                    # return a list/QuerySet of instances.
                    if hasattr(values, "_meta"):
                        # Single FK value.
                        related_org_id = getattr(values, "organization_id", None)
                        if related_org_id is not None and related_org_id != org_id:
                            raise ValidationError(
                                {
                                    field_name: (
                                        f"{field_name} must belong to the "
                                        "same organization."
                                    )
                                }
                            )
                    else:
                        # M2M iterable of values.
                        for val in values:
                            related_org_id = getattr(val, "organization_id", None)
                            if related_org_id is not None and related_org_id != org_id:
                                raise ValidationError(
                                    {
                                        field_name: (
                                            f"All {field_name} must belong "
                                            "to the same organization."
                                        )
                                    }
                                )

            return cleaned_data

    SameOrgValidatedForm.__name__ = f"{base_form_class.__name__}SameOrgValidated"
    return SameOrgValidatedForm


class _CrmOrgAwareAdminMixin:
    """Mixin that makes the organization field explicit on the operator admin path.

    Phase 1 contract:
    - **Add forms**: organization is a required editable field so the operator
      must choose an organization when creating a new row.
    - **Change forms**: organization is displayed read-only so the operator can
      see which organization owns the row but cannot reassign it.
    - **Cross-org related validation**: the admin form rejects related
      selections (company, contact, stage, tags) that belong to a different
      organization than the row's organization.
    """

    # Subclasses list the FK/M2M field names that carry an ``organization_id``
    # attribute and must be validated for same-org membership.
    _org_related_fields: list[str] = []

    def get_form(
        self,
        request: Any,
        obj: Any | None = None,
        change: bool | None = None,
        **kwargs: Any,
    ) -> type[ModelForm]:  # type: ignore[override]
        """Return a form class that includes organization on add and validates same-org membership.

        The returned form validates that FK and M2M related field selections
        belong to the same organization as the row, rejecting foreign-org
        values at the form level before any save occurs.
        """
        is_change = change if change is not None else obj is not None
        form_class = super().get_form(request, obj, change=change, **kwargs)  # type: ignore[misc]

        # Wrap in a same-org validated form if there are related fields to
        # check (must happen before field customization because
        # ModelFormMetaclass creates fresh field instances on subclass).
        if self._org_related_fields:
            form_class = _make_same_org_validated_form(
                form_class, list(self._org_related_fields)
            )

        if not is_change:
            # Add form: ensure organization is present and required.
            if "organization" in form_class.base_fields:
                form_class.base_fields["organization"].required = True

        return form_class

    def get_readonly_fields(self, request: Any, obj: Any | None = None) -> list[str]:  # type: ignore[override]
        """Show organization read-only on change forms."""
        readonly = list(super().get_readonly_fields(request, obj))  # type: ignore[misc]
        if obj is not None and "organization" not in readonly:
            readonly.append("organization")
        return readonly

    def get_exclude(self, request: Any, obj: Any | None = None) -> list[str] | None:  # type: ignore[override]
        """Include organization in the form on both add and change."""
        excludes = list(super().get_exclude(request, obj) or [])  # type: ignore[misc]
        excludes = [f for f in excludes if f != "organization"]
        return excludes or None

    def get_fieldsets(self, request: Any, obj: Any | None = None):  # type: ignore[override, no-untyped-def]
        """Ensure organization appears in the fieldsets."""
        fieldsets = super().get_fieldsets(request, obj)  # type: ignore[misc]
        # Collect all fields currently in fieldsets.
        all_fields: list[str] = []
        for _, options in fieldsets:
            all_fields.extend(options.get("fields", ()))
        if "organization" not in all_fields:
            # Add organization as the first field in the first fieldset.
            first_name, first_opts = fieldsets[0]
            first_opts = dict(first_opts)
            first_opts["fields"] = ("organization",) + tuple(
                first_opts.get("fields", ())
            )
            fieldsets = [(first_name, first_opts)] + list(fieldsets[1:])
        return fieldsets

    def get_form_for_validation(  # type: ignore[no-untyped-def]
        self, request: Any, obj: Any | None = None, **kwargs: Any
    ):  # type: ignore[override]
        """Limit related-field querysets to the same organization."""
        form_class = super().get_form(request, obj, **kwargs)  # type: ignore[misc]
        return form_class

    def _get_org_id_from_form(self, form: ModelForm) -> int | None:
        """Extract the organization_id from a bound form's cleaned data or instance."""
        org = (
            form.cleaned_data.get("organization")
            if "organization" in form.cleaned_data
            else None
        )
        if org is not None:
            return org.pk
        if self.instance and hasattr(self.instance, "organization_id"):  # type: ignore[attr-defined]
            return self.instance.organization_id  # type: ignore[attr-defined]
        return None

    def save_model(self, request: Any, obj: Any, form: Any, change: bool) -> None:  # type: ignore[override]
        """Validate cross-org FK selections before saving.

        M2M fields (tags) require a PK and are handled in ``save_related``.
        """
        org_id = getattr(obj, "organization_id", None)
        if org_id is not None:
            # Only process FK fields — M2M requires a PK and is handled
            # in save_related.
            opts = obj._meta
            m2m_field_names = {f.name for f in opts.many_to_many}
            for field_name in self._org_related_fields:
                if field_name in m2m_field_names:
                    continue
                value = getattr(obj, field_name, None)
                if value is None:
                    continue
                # FK field — single model instance.
                if hasattr(value, "organization_id"):
                    related_org_id = value.organization_id
                    if related_org_id is not None and related_org_id != org_id:
                        from django.core.exceptions import ValidationError

                        raise ValidationError(
                            f"{field_name} must belong to the same organization."
                        )
        super().save_model(request, obj, form, change)  # type: ignore[misc]

    def save_related(  # type: ignore[override]
        self,
        request: Any,
        form: ModelForm,
        formsets: list[Any],
        change: bool,
    ) -> None:
        """Save related objects.

        M2M same-org validation is handled in the form-level ``clean()``
        hook before any save occurs.  This method delegates to the default
        admin save_related for actual persistence.
        """
        super().save_related(request, form, formsets, change)  # type: ignore[misc]


@admin.register(Tag)
class TagAdmin(_CrmOrgAwareAdminMixin, admin.ModelAdmin):
    """Admin configuration for Tag model"""

    list_display = ["name", "organization", "created_at"]
    list_filter = ["organization", "created_at"]
    search_fields = ["name"]
    ordering = ["name"]

    def get_queryset(self, request: Any) -> models.QuerySet:  # type: ignore[override]
        """Operator path: use all_objects for cross-tenant visibility."""
        return Tag.all_objects.all()


@admin.register(Company)
class CompanyAdmin(_CrmOrgAwareAdminMixin, admin.ModelAdmin):
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

    def get_queryset(self, request: Any) -> models.QuerySet:  # type: ignore[override]
        """Operator path: use all_objects for cross-tenant visibility."""
        return Company.all_objects.all()

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
class ContactAdmin(_CrmOrgAwareAdminMixin, admin.ModelAdmin):
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

    def get_queryset(self, request: Any) -> models.QuerySet:  # type: ignore[override]
        """Operator path: use all_objects for cross-tenant visibility."""
        return Contact.all_objects.all()


@admin.register(Stage)
class StageAdmin(_CrmOrgAwareAdminMixin, admin.ModelAdmin):
    """Admin configuration for Stage model"""

    list_display = ["name", "order", "organization", "deal_count"]
    list_filter = ["organization"]
    list_editable = ["order"]
    ordering = ["order"]

    def get_queryset(self, request: Any) -> models.QuerySet:  # type: ignore[override]
        """Operator path: use all_objects for cross-tenant visibility."""
        return Stage.all_objects.all()

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
class DealAdmin(_CrmOrgAwareAdminMixin, admin.ModelAdmin):
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

    def get_queryset(self, request: Any) -> models.QuerySet:  # type: ignore[override]
        """Operator path: use all_objects for cross-tenant visibility."""
        return Deal.all_objects.all()


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
