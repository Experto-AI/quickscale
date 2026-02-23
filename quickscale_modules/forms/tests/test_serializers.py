"""Tests for Forms module serializers"""

import pytest

from quickscale_modules_forms.models import FormField
from quickscale_modules_forms.serializers import (
    FormSchemaSerializer,
    FormSubmissionCreateSerializer,
)


@pytest.mark.django_db
class TestFormSchemaSerializer:
    """Tests for the FormSchemaSerializer"""

    def test_formschema_serializer_returns_active_fields_only(self, form, form_field):
        """Inactive fields are excluded from the schema"""
        FormField.objects.create(
            form=form,
            field_type="text",
            label="Hidden",
            name="hidden_field",
            order=99,
            is_active=False,
        )
        data = FormSchemaSerializer(form).data
        names = [f["name"] for f in data["fields"]]
        assert "full_name" in names
        assert "hidden_field" not in names

    def test_formschema_serializer_fields_ordered_by_order(self, form):
        """Fields appear in ascending order"""
        FormField.objects.create(
            form=form, field_type="text", label="Last", name="last_field", order=10
        )
        FormField.objects.create(
            form=form, field_type="text", label="First", name="first_field", order=1
        )
        data = FormSchemaSerializer(form).data
        orders = [f["order"] for f in data["fields"]]
        assert orders == sorted(orders)

    def test_formschema_serializer_contains_slug_and_title(self, form):
        """Serialized data includes slug and title"""
        data = FormSchemaSerializer(form).data
        assert data["slug"] == "contact"
        assert data["title"] == "Contact"


@pytest.mark.django_db
class TestFormSubmissionCreateSerializer:
    """Tests for the FormSubmissionCreateSerializer"""

    def test_valid_data_passes_validation(self, form, form_field, email_field):
        """All required fields present and valid — serializer passes"""
        data = {"full_name": "Alice", "email": "alice@example.com"}
        serializer = FormSubmissionCreateSerializer(data=data, context={"form": form})
        assert serializer.is_valid(), serializer.errors

    def test_missing_required_field_raises_field_error(
        self, form, form_field, email_field
    ):
        """Missing required field yields a field-name-keyed error"""
        data = {"full_name": "Alice"}  # missing email
        serializer = FormSubmissionCreateSerializer(data=data, context={"form": form})
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_optional_field_can_be_omitted(
        self, form, form_field, email_field, optional_field
    ):
        """Optional fields (required=False) do not raise errors when absent"""
        data = {"full_name": "Alice", "email": "alice@example.com"}
        serializer = FormSubmissionCreateSerializer(data=data, context={"form": form})
        assert serializer.is_valid(), serializer.errors

    def test_unknown_field_raises_field_error(self, form, form_field, email_field):
        """Submitting an unknown field key raises a field-named error"""
        data = {
            "full_name": "Alice",
            "email": "alice@example.com",
            "unexpected_key": "value",
        }
        serializer = FormSubmissionCreateSerializer(data=data, context={"form": form})
        assert not serializer.is_valid()
        assert "unexpected_key" in serializer.errors

    def test_invalid_email_format_raises_named_error(
        self, form, form_field, email_field
    ):
        """Invalid email format yields an 'email'-keyed error"""
        data = {"full_name": "Alice", "email": "not-an-email"}
        serializer = FormSubmissionCreateSerializer(data=data, context={"form": form})
        assert not serializer.is_valid()
        assert "email" in serializer.errors

    def test_validation_rules_max_length_enforced(self, form, form_field, email_field):
        """max_length validation_rule is enforced"""
        form_field.validation_rules = {"max_length": 5}
        form_field.save()
        data = {"full_name": "This name is too long", "email": "alice@example.com"}
        serializer = FormSubmissionCreateSerializer(data=data, context={"form": form})
        assert not serializer.is_valid()
        assert "full_name" in serializer.errors
