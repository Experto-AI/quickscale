"""Dynamic field-level validator factory for Forms module"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from rest_framework import serializers

if TYPE_CHECKING:
    from quickscale_modules_forms.models import FormField


def make_field_validator(field: "FormField") -> Any:
    """Return a callable that validates a submitted value against the field's validation_rules"""

    rules: dict = field.validation_rules or {}

    def validate(value: str) -> None:
        min_length = rules.get("min_length")
        max_length = rules.get("max_length")
        pattern = rules.get("regex")

        if min_length is not None and len(value) < int(min_length):
            raise serializers.ValidationError(
                f"This field must be at least {min_length} characters long."
            )

        if max_length is not None and len(value) > int(max_length):
            raise serializers.ValidationError(
                f"This field must be no more than {max_length} characters long."
            )

        if pattern is not None and not re.match(pattern, value):
            raise serializers.ValidationError(
                "This field does not match the required format."
            )

    return validate
