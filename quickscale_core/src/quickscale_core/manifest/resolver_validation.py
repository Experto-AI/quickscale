"""Option validation engine for the manifest-driven module resolver.

Split out of :mod:`quickscale_core.manifest.resolver`; the resolver facade
re-exports these helpers so existing imports keep working.  This module owns
the validation rules a manifest declares for its option values.
"""

from __future__ import annotations

from collections.abc import Callable
import re
from typing import Any

from quickscale_core.manifest.derivation import ValidationRule


def _check_required_rule(
    value: Any, rule: ValidationRule, option_key: str
) -> str | None:
    """Check the ``required`` rule: the value must not be null or blank."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return rule.description or f"{option_key} is required"
    return None


def _check_choices_rule(
    value: Any, rule: ValidationRule, option_key: str
) -> str | None:
    """Check the ``choices`` rule: the value must be a declared choice."""
    if value is not None and value not in rule.allowed_values:
        allowed = ", ".join(str(v) for v in rule.allowed_values)
        return rule.description or f"{option_key} must be one of: {allowed}"
    return None


def _check_range_rule(value: Any, rule: ValidationRule, option_key: str) -> str | None:
    """Check the ``range`` rule: the value must be numeric and in bounds."""
    if value is None:
        return None
    try:
        numeric = float(value)
    except TypeError, ValueError:
        return rule.description or f"{option_key} must be a numeric value"
    if rule.min_value is not None and numeric < rule.min_value:
        return rule.description or f"{option_key} must be >= {rule.min_value}"
    if rule.max_value is not None and numeric > rule.max_value:
        return rule.description or f"{option_key} must be <= {rule.max_value}"
    return None


def _check_pattern_rule(
    value: Any, rule: ValidationRule, option_key: str
) -> str | None:
    """Check the ``pattern`` rule: the string value must full-match."""
    if value is not None and rule.pattern:
        str_value = str(value)
        if not re.fullmatch(rule.pattern, str_value):
            return rule.description or f"{option_key} must match pattern {rule.pattern}"
    return None


def _check_min_length_rule(
    value: Any, rule: ValidationRule, option_key: str
) -> str | None:
    """Check the ``min_length`` rule on sized values."""
    if value is None:
        return None
    try:
        if len(value) < (rule.min_value or 0):
            return (
                rule.description or f"{option_key} length must be >= {rule.min_value}"
            )
    except TypeError:
        pass
    return None


def _check_max_length_rule(
    value: Any, rule: ValidationRule, option_key: str
) -> str | None:
    """Check the ``max_length`` rule on sized values."""
    if value is None:
        return None
    try:
        if len(value) > (rule.max_value or 0):
            return (
                rule.description or f"{option_key} length must be <= {rule.max_value}"
            )
    except TypeError:
        pass
    return None


def _check_type_rule(value: Any, rule: ValidationRule, option_key: str) -> str | None:
    """Declaration-only rule: the manifest option type is the source of truth.

    Type validation is declared but not enforced at this layer; the manifest
    schema's option_type field is the source of truth for type coercion.  This
    rule type is reserved for future use.
    """
    return None


_VALIDATION_RULE_HANDLERS: dict[
    str, Callable[[Any, ValidationRule, str], str | None]
] = {
    "required": _check_required_rule,
    "choices": _check_choices_rule,
    "range": _check_range_rule,
    "pattern": _check_pattern_rule,
    "min_length": _check_min_length_rule,
    "max_length": _check_max_length_rule,
    "type": _check_type_rule,
}


def _check_validation_rule(
    value: Any, rule: ValidationRule, option_key: str
) -> str | None:
    """Check a single validation rule against a value.

    Args:
        value: The resolved value to validate.
        rule: The validation rule to check.
        option_key: The option key (for error messages).

    Returns:
        An issue description string if the rule fails, or ``None`` if it
        passes.
    """
    handler = _VALIDATION_RULE_HANDLERS.get(rule.rule_type)
    if handler is None:
        # Unknown rule type: no issue is recorded.
        return None
    return handler(value, rule, option_key)


def _validate_value(
    value: Any,
    option_key: str,
    option_derivation: Any | None,
    shared_rules: list[ValidationRule],
) -> list[str]:
    """Run all applicable validation rules against a single option value.

    Args:
        value: The resolved value to validate.
        option_key: The option key being validated.
        option_derivation: The per-option derivation metadata, if any.
        shared_rules: Module-wide validation rules.

    Returns:
        List of issue description strings for failed rules.
    """
    issues: list[str] = []

    # Check shared rules
    for rule in shared_rules:
        if rule.option_key == "*" or rule.option_key == option_key:
            issue = _check_validation_rule(value, rule, option_key)
            if issue:
                issues.append(issue)

    # Check per-option rules
    if option_derivation is not None:
        for rule in option_derivation.validation_rules:
            issue = _check_validation_rule(value, rule, option_key)
            if issue:
                issues.append(issue)

    return issues
