"""Tests for Forms module validators"""

import pytest
from rest_framework import serializers

from quickscale_modules_forms.validators import make_field_validator


@pytest.mark.django_db
class TestMakeFieldValidator:
    """Tests for the make_field_validator factory function"""

    def test_passes_when_no_rules(self, form_field):
        """Validator with empty validation_rules passes any value"""
        form_field.validation_rules = {}
        form_field.save()
        validator = make_field_validator(form_field)
        # Should not raise
        validator("any value")

    def test_min_length_raises_when_too_short(self, form_field):
        """Validator raises when value is shorter than min_length"""
        form_field.validation_rules = {"min_length": 10}
        form_field.save()
        validator = make_field_validator(form_field)
        with pytest.raises(serializers.ValidationError) as exc:
            validator("short")
        assert "10" in str(exc.value.detail[0])

    def test_min_length_passes_when_long_enough(self, form_field):
        """Validator passes when value meets min_length"""
        form_field.validation_rules = {"min_length": 3}
        form_field.save()
        validator = make_field_validator(form_field)
        # Should not raise
        validator("abc")

    def test_max_length_raises_when_too_long(self, form_field):
        """Validator raises when value exceeds max_length"""
        form_field.validation_rules = {"max_length": 5}
        form_field.save()
        validator = make_field_validator(form_field)
        with pytest.raises(serializers.ValidationError) as exc:
            validator("this value is way too long")
        assert "5" in str(exc.value.detail[0])

    def test_max_length_passes_at_boundary(self, form_field):
        """Validator passes when value is exactly max_length characters"""
        form_field.validation_rules = {"max_length": 5}
        form_field.save()
        validator = make_field_validator(form_field)
        # Should not raise
        validator("hello")

    def test_regex_raises_when_no_match(self, form_field):
        """Validator raises when value does not match regex pattern"""
        form_field.validation_rules = {"regex": r"^\d+$"}
        form_field.save()
        validator = make_field_validator(form_field)
        with pytest.raises(serializers.ValidationError):
            validator("not-a-number")

    def test_regex_passes_when_matches(self, form_field):
        """Validator passes when value matches regex pattern"""
        form_field.validation_rules = {"regex": r"^\d+$"}
        form_field.save()
        validator = make_field_validator(form_field)
        # Should not raise
        validator("12345")

    def test_combined_rules_all_must_pass(self, form_field):
        """Validator enforces all rules together"""
        form_field.validation_rules = {"min_length": 5, "max_length": 10}
        form_field.save()
        validator = make_field_validator(form_field)
        # Too short
        with pytest.raises(serializers.ValidationError):
            validator("ab")
        # Too long
        with pytest.raises(serializers.ValidationError):
            validator("this value is too long")
        # Just right
        validator("hello")
