"""Serializers for QuickScale Forms module"""

from __future__ import annotations

import re
from typing import Any

from rest_framework import serializers

from quickscale_modules_forms.models import (
    Form,
    FormField,
    FormFieldValue,
    FormSubmission,
    HONEYPOT_FIELD_NAME,
    is_form_spam_protection_enabled,
)
from quickscale_modules_forms.validators import make_field_validator


class FormFieldSerializer(serializers.ModelSerializer):
    """Read-only serializer for public form schema — omits server-side-only fields"""

    class Meta:
        model = FormField
        fields = [
            "name",
            "field_type",
            "label",
            "required",
            "order",
            "placeholder",
            "help_text",
            "layout_hint",
            "options",
            "validation_rules",
            "is_active",
        ]
        read_only_fields = fields


class FormSchemaSerializer(serializers.ModelSerializer):
    """Public-facing form schema serializer — includes filtered active fields"""

    class Meta:
        model = Form
        fields = [
            "slug",
            "title",
            "description",
            "success_message",
            "redirect_url",
        ]
        read_only_fields = fields

    def to_representation(self, instance: Form) -> dict:
        """Add filtered active fields to the representation"""
        data = super().to_representation(instance)
        active_fields = instance.fields.filter(is_active=True).order_by("order")
        serialized_fields = FormFieldSerializer(active_fields, many=True).data

        spam_protection_enabled = is_form_spam_protection_enabled(instance)
        has_honeypot_marker = any(
            field_data.get("name") == HONEYPOT_FIELD_NAME
            for field_data in serialized_fields
        )
        if spam_protection_enabled and not has_honeypot_marker:
            max_existing_order = max(
                (int(field_data.get("order", 0)) for field_data in serialized_fields),
                default=0,
            )
            serialized_fields.append(
                {
                    "name": HONEYPOT_FIELD_NAME,
                    "field_type": FormField.FIELD_TYPE_HIDDEN,
                    "label": "",
                    "required": False,
                    "order": max_existing_order + 1,
                    "placeholder": "",
                    "help_text": "",
                    "layout_hint": FormField.LAYOUT_FULL,
                    "options": [],
                    "validation_rules": {},
                    "is_active": True,
                }
            )

        data["fields"] = serialized_fields
        return data


class AdminFormListSerializer(serializers.ModelSerializer):
    """Serializer for staff form list including submission_count"""

    submission_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Form
        fields = [
            "slug",
            "title",
            "description",
            "success_message",
            "redirect_url",
            "submission_count",
        ]
        read_only_fields = fields


class FormFieldValueSerializer(serializers.ModelSerializer):
    """Serializer for field value snapshots in admin submission detail"""

    class Meta:
        model = FormFieldValue
        fields = ["field_name", "field_label", "value"]
        read_only_fields = fields


class FormSubmissionAdminSerializer(serializers.ModelSerializer):
    """Full submission serializer for admin endpoints including nested field values"""

    values = FormFieldValueSerializer(many=True, read_only=True)
    form_title = serializers.CharField(source="form.title", read_only=True)

    class Meta:
        model = FormSubmission
        fields = [
            "id",
            "form",
            "form_title",
            "status",
            "is_spam",
            "ip_address",
            "user_agent",
            "submitted_at",
            "values",
        ]
        read_only_fields = [
            "id",
            "form",
            "form_title",
            "ip_address",
            "user_agent",
            "submitted_at",
            "values",
        ]


class FormSubmissionCreateSerializer(serializers.Serializer):
    """Dynamic write-only serializer — validates submitted data against form field definitions"""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        # form instance is passed via context
        form: Form | None = self.context.get("form")
        if form is not None:
            self._active_fields = list(
                form.fields.filter(is_active=True).order_by("order")
            )
        else:
            self._active_fields = []

    def to_internal_value(self, data: dict) -> dict:
        """Pass all submitted data through — dynamic validation happens in validate()"""
        return dict(data)

    def validate(self, data: dict) -> dict:
        """Validate submitted data against dynamic form field definitions"""
        active_fields: list[FormField] = self._active_fields
        known_names = {f.name for f in active_fields}
        errors: dict[str, list[str]] = {}

        # Reject unknown field names (honeypot already handled in view)
        submitted_keys = {k for k in data if k != HONEYPOT_FIELD_NAME}
        unknown_keys = submitted_keys - known_names
        for key in unknown_keys:
            errors[key] = ["Unknown field."]

        for field in active_fields:
            submitted_value = data.get(field.name, "")

            # Check required fields
            if field.required and not submitted_value:
                errors[field.name] = ["This field is required."]
                continue

            if not submitted_value:
                continue

            # Email type validation
            if field.field_type == "email":
                email_pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
                if not re.match(email_pattern, submitted_value):
                    errors[field.name] = ["Enter a valid email address."]
                    continue

            # Apply validation_rules
            validator = make_field_validator(field)
            try:
                validator(submitted_value)
            except serializers.ValidationError as e:
                errors[field.name] = list(e.detail)

        if errors:
            raise serializers.ValidationError(errors)

        return data
