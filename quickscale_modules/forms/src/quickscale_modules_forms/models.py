"""Data models for QuickScale Forms module"""

from django.conf import settings
from django.db import models


DEFAULT_FORM_DATA_RETENTION_DAYS = 365
HONEYPOT_FIELD_NAME = "_hp_name"


def get_default_form_data_retention_days() -> int:
    """Return the settings-backed default retention window for new forms."""
    raw_value = getattr(
        settings,
        "FORMS_DATA_RETENTION_DAYS",
        DEFAULT_FORM_DATA_RETENTION_DAYS,
    )
    try:
        retention_days = int(raw_value)
    except TypeError:
        return DEFAULT_FORM_DATA_RETENTION_DAYS
    except ValueError:
        return DEFAULT_FORM_DATA_RETENTION_DAYS
    return retention_days if retention_days >= 0 else DEFAULT_FORM_DATA_RETENTION_DAYS


def is_form_spam_protection_enabled(form: "Form") -> bool:
    """Return whether honeypot handling is active for the given form."""
    return bool(
        getattr(settings, "FORMS_SPAM_PROTECTION", True)
        and form.spam_protection_enabled
    )


class Form(models.Model):
    """Top-level form definition — defines structure, metadata, and notification settings"""

    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
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
        related_name="created_forms",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = "quickscale_modules_forms"
        db_table = "quickscale_modules_forms_form"
        ordering = ["title"]

    def __str__(self) -> str:
        return self.title


class FormField(models.Model):
    """An individual field belonging to a form"""

    FIELD_TYPE_TEXT = "text"
    FIELD_TYPE_EMAIL = "email"
    FIELD_TYPE_TEXTAREA = "textarea"
    FIELD_TYPE_SELECT = "select"
    FIELD_TYPE_CHECKBOX = "checkbox"
    FIELD_TYPE_RADIO = "radio"
    FIELD_TYPE_NUMBER = "number"
    FIELD_TYPE_URL = "url"
    FIELD_TYPE_TEL = "tel"
    FIELD_TYPE_DATE = "date"
    FIELD_TYPE_HIDDEN = "hidden"

    FIELD_TYPE_CHOICES = [
        (FIELD_TYPE_TEXT, "Text"),
        (FIELD_TYPE_EMAIL, "Email"),
        (FIELD_TYPE_TEXTAREA, "Textarea"),
        (FIELD_TYPE_SELECT, "Select"),
        (FIELD_TYPE_CHECKBOX, "Checkbox"),
        (FIELD_TYPE_RADIO, "Radio"),
        (FIELD_TYPE_NUMBER, "Number"),
        (FIELD_TYPE_URL, "URL"),
        (FIELD_TYPE_TEL, "Telephone"),
        (FIELD_TYPE_DATE, "Date"),
        (FIELD_TYPE_HIDDEN, "Hidden"),
    ]

    LAYOUT_FULL = "full"
    LAYOUT_HALF_LEFT = "half_left"
    LAYOUT_HALF_RIGHT = "half_right"

    LAYOUT_HINT_CHOICES = [
        (LAYOUT_FULL, "Full width"),
        (LAYOUT_HALF_LEFT, "Half width (left)"),
        (LAYOUT_HALF_RIGHT, "Half width (right)"),
    ]

    form = models.ForeignKey(Form, related_name="fields", on_delete=models.CASCADE)
    field_type = models.CharField(max_length=20, choices=FIELD_TYPE_CHOICES)
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
        max_length=20, choices=LAYOUT_HINT_CHOICES, default=LAYOUT_FULL
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        app_label = "quickscale_modules_forms"
        db_table = "quickscale_modules_forms_formfield"
        ordering = ["order"]
        unique_together = [["form", "name"]]

    def __str__(self) -> str:
        return f"{self.form.title} — {self.label}"


class FormSubmission(models.Model):
    """A single form fill event"""

    STATUS_PENDING = "pending"
    STATUS_READ = "read"
    STATUS_REPLIED = "replied"
    STATUS_ARCHIVED = "archived"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_READ, "Read"),
        (STATUS_REPLIED, "Replied"),
        (STATUS_ARCHIVED, "Archived"),
    ]

    form = models.ForeignKey(Form, related_name="submissions", on_delete=models.PROTECT)
    # Anonymized to null when data_retention_days expires
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, blank=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_spam = models.BooleanField(default=False)
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING
    )

    class Meta:
        app_label = "quickscale_modules_forms"
        db_table = "quickscale_modules_forms_formsubmission"
        ordering = ["-submitted_at"]

    def __str__(self) -> str:
        return f"Submission #{self.pk} for {self.form.title} ({self.status})"


class FormFieldValue(models.Model):
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

    class Meta:
        app_label = "quickscale_modules_forms"
        db_table = "quickscale_modules_forms_formfieldvalue"

    def __str__(self) -> str:
        return f"{self.field_label}: {self.value[:50]}"
