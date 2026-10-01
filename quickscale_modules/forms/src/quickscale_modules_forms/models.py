"""Data models for QuickScale Forms module"""

from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

from quickscale_modules_orgs.models import TenantModel

HONEYPOT_FIELD_NAME = "_hp_name"


def get_default_form_data_retention_days() -> int:
    """Return the declared retention window for new forms.

    Rule 3: the startup check has validated ``QUICKSCALE_FORMS_RETENTION_DAYS``
    against the manifest schema, so the value is read directly.
    """
    return settings.QUICKSCALE_FORMS_RETENTION_DAYS


def is_form_spam_protection_enabled(form: "Form") -> bool:
    """Return whether honeypot handling is active for the given form.

    Rule 3: the startup check has validated ``QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED`` against
    the manifest schema, so the value is read directly.
    """
    return bool(
        settings.QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED
        and form.spam_protection_enabled
    )


class Form(TenantModel):
    """Top-level form definition — defines structure, metadata, and notification settings"""

    title = models.CharField(max_length=200)
    slug = models.SlugField()
    description = models.TextField(blank=True)
    success_message = models.TextField(default="Thank you, we'll be in touch.")
    redirect_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    spam_protection_enabled = models.BooleanField(default=True)
    # Comma-separated notification recipient email addresses
    notify_emails = models.TextField(
        blank=True,
        help_text="Comma-separated email addresses to notify on every submission.",
    )
    data_retention_days = models.PositiveIntegerField(
        default=get_default_form_data_retention_days,
        help_text="Submissions older than this many days are eligible for anonymization.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="quickscale_forms_created_forms",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    if TYPE_CHECKING:
        # Reverse FK accessor from FormField.form.
        fields: models.Manager["FormField"]

    class Meta(TenantModel.Meta):
        app_label = "quickscale_forms"
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="quickscale_forms_form_slug_organization_unique",
            ),
            models.UniqueConstraint(
                fields=["id", "organization"],
                name="quickscale_forms_form_id_org_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.title


class FormField(TenantModel):
    """An individual field belonging to a form"""

    class FieldType(models.TextChoices):
        TEXT = "text", "Text"
        EMAIL = "email", "Email"
        TEXTAREA = "textarea", "Textarea"
        SELECT = "select", "Select"
        CHECKBOX = "checkbox", "Checkbox"
        RADIO = "radio", "Radio"
        NUMBER = "number", "Number"
        URL = "url", "URL"
        TEL = "tel", "Telephone"
        DATE = "date", "Date"
        HIDDEN = "hidden", "Hidden"

    class LayoutHint(models.TextChoices):
        FULL = "full", "Full width"
        HALF_LEFT = "half_left", "Half width (left)"
        HALF_RIGHT = "half_right", "Half width (right)"

    form = models.ForeignKey(Form, related_name="fields", on_delete=models.CASCADE)
    field_type = models.CharField(max_length=20, choices=FieldType.choices)
    label = models.CharField(max_length=200)
    name = models.SlugField(max_length=100)
    placeholder = models.CharField(max_length=200, blank=True)
    help_text = models.CharField(max_length=500, blank=True)
    required = models.BooleanField(default=True)
    order = models.PositiveIntegerField()
    # List of {value, label} dicts for select/radio/checkbox types
    options = models.JSONField(default=list, blank=True)
    # Validation rules e.g. {"min_length": 10, "max_length": 500, "regex": "^[a-z]+$"}
    validation_rules = models.JSONField(default=dict, blank=True)
    layout_hint = models.CharField(
        max_length=20, choices=LayoutHint.choices, default=LayoutHint.FULL
    )
    is_active = models.BooleanField(default=True)

    class Meta(TenantModel.Meta):
        app_label = "quickscale_forms"
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(
                fields=("form", "name"),
                name="quickscale_forms_formfield_form_name_unique",
            ),
            models.UniqueConstraint(
                fields=["id", "organization"],
                name="quickscale_forms_formfield_id_org_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.form.title} — {self.label}"


class FormSubmission(TenantModel):
    """A single form fill event"""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        READ = "read", "Read"
        REPLIED = "replied", "Replied"
        ARCHIVED = "archived", "Archived"

    form = models.ForeignKey(Form, related_name="submissions", on_delete=models.PROTECT)
    # Anonymized to null when data_retention_days expires
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_spam = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING
    )

    if TYPE_CHECKING:
        # FK attname set by ``form``; unset until the form is assigned.
        form_id: int | None

    class Meta(TenantModel.Meta):
        app_label = "quickscale_forms"
        ordering = ["-submitted_at"]
        constraints = [
            models.UniqueConstraint(
                fields=["id", "organization"],
                name="quickscale_forms_formsubmission_id_org_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"Submission #{self.pk} for {self.form.title} ({self.status})"


class FormFieldValue(TenantModel):
    """The value for a single field in a submission — preserves historical snapshots"""

    submission = models.ForeignKey(
        FormSubmission, related_name="values", on_delete=models.CASCADE
    )
    # SET_NULL so historical values are preserved even when the field definition is deleted
    field = models.ForeignKey(
        FormField,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="values",
    )
    # Snapshot of FormField.name at submission time
    field_name = models.CharField(max_length=100)
    # Snapshot of FormField.label at submission time
    field_label = models.CharField(max_length=200)
    value = models.TextField()

    class Meta(TenantModel.Meta):
        app_label = "quickscale_forms"
        ordering = ["submission_id", "pk"]

    def __str__(self) -> str:
        return f"{self.field_label}: {self.value[:50]}"
