"""Manifest-declared option validation.

One engine for the per-option ``validation`` block declared next to the option
in ``module.yml``.  ``quickscale plan`` and ``quickscale apply`` run it from
``quickscale_core.schema.config_schema`` on the values a project supplies, and
the generated-project startup check consumes the same block once ``apply``
writes the settings schema.

Recognised keys, as Module Conventions rule 12 records them:

* single-value checks — ``choices`` (a closed set), ``min`` / ``max`` (numeric
  bounds), ``pattern`` (a full-match regular expression);
* cross-option checks — ``required_when`` (a single-entry mapping of another
  option to the value, or list of values, that makes this option required) and
  ``any_of`` (a list of sibling option names, at least one of which must be
  set).  ``any_of`` on an option with ``required_when`` applies only while the
  condition holds; alone it applies always.

Messages name the setting a module author or operator must fix — the option's
``django_setting`` with its ``quickscale.yml`` path — including the setting
named in a ``required_when`` condition.

The manifest's top-level ``retired_options`` section names keys that no longer
exist together with the message that must refuse them; a supplied retired key
is reported first, so a retired name is never mistaken for an undeclared one.

Values are canonicalized before the value-level checks: the caller's own
canonicalization runs first, then the manifest's declared normalization rules
through :func:`~quickscale_core.manifest.resolver.normalize_module_option_values`,
so ``GRID`` and ``" 5/hour "`` are judged as the canonical forms the manifest
names.  The declared ``type`` is checked against the values as supplied, before
any lossy coercion.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from dataclasses import dataclass
from typing import Any

from quickscale_core.manifest.resolver import normalize_module_option_values
from quickscale_core.manifest.schema import ConfigOption, ModuleManifest

#: Keys accepted inside a per-option ``validation`` block.
SINGLE_OPTION_VALIDATION_KEYS = frozenset({"choices", "min", "max", "pattern"})
CROSS_OPTION_VALIDATION_KEYS = frozenset({"required_when", "any_of"})
ALLOWED_VALIDATION_KEYS = SINGLE_OPTION_VALIDATION_KEYS | CROSS_OPTION_VALIDATION_KEYS

#: Option types the loader accepts, with their message labels.
OPTION_TYPE_LABELS: dict[str, tuple[str, str]] = {
    "boolean": ("a", "boolean"),
    "integer": ("an", "integer"),
    "list": ("a", "list"),
    "string": ("a", "string"),
}

_PATTERN_KEY = "pattern"


@dataclass(frozen=True)
class OptionValidationIssue:
    """One failed constraint, carrying the option that must be fixed."""

    option_name: str
    message: str


def setting_display_name(module_name: str, option: ConfigOption) -> str:
    """Return the name a failure message should use for *option*.

    A mutable option is named by its ``django_setting`` — the name an operator
    sees in the environment and in ``settings/modules.py`` — with the
    ``quickscale.yml`` key it was authored as in parentheses.  An option with
    no setting falls back to its dotted path under the module.
    """
    path = f"modules.{module_name}.{option.name}"
    if option.django_setting:
        return f"{option.django_setting} ({path})"
    return path


def option_value_is_empty(value: Any) -> bool:
    """Return whether *value* counts as absent for requiredness checks."""
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, Mapping):
        return not value
    if isinstance(value, (list, tuple, set, frozenset)):
        return not value
    return False


def option_type_matches(option_type: str, value: Any) -> bool:
    """Return whether *value* satisfies the option's declared ``type``.

    An unknown declared type matches everything here; the loader rejects
    unknown types before a manifest reaches this engine.
    """
    if option_type == "boolean":
        return isinstance(value, bool)
    if option_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if option_type == "string":
        return isinstance(value, str)
    if option_type == "list":
        return isinstance(value, list)
    return True


def _type_issue(
    manifest: ModuleManifest, option: ConfigOption, option_name: str
) -> OptionValidationIssue:
    article, noun = OPTION_TYPE_LABELS.get(
        option.option_type, ("a", option.option_type)
    )
    label = setting_display_name(manifest.name, option)
    return OptionValidationIssue(option_name, f"{label} must be {article} {noun}")


def _option_label(manifest: ModuleManifest, option_name: str) -> str:
    option = manifest.get_option(option_name)
    if option is None:
        return option_name
    return setting_display_name(manifest.name, option)


def _render_condition_value(value: Any) -> str:
    """Render a condition value the way the manifest spells it."""
    if isinstance(value, bool):
        return "true" if value else "false"
    return repr(value)


def _condition_matches(
    condition: Mapping[str, Any], resolved: Mapping[str, Any]
) -> bool:
    """Return whether a single-pair ``required_when`` condition holds."""
    for condition_option, expected in condition.items():
        if not isinstance(condition_option, str) or condition_option not in resolved:
            return False
        actual = resolved[condition_option]
        if isinstance(expected, list):
            return any(actual == allowed for allowed in expected)
        return bool(actual == expected)
    return False


def _render_condition(
    manifest: ModuleManifest,
    condition: Mapping[str, Any],
) -> str:
    """Render a single-pair ``required_when`` condition for a failure message."""
    for condition_option, expected in condition.items():
        label = _option_label(manifest, str(condition_option))
        if isinstance(expected, list):
            values = ", ".join(str(value) for value in expected)
            return f"{label} is one of: {values}"
        return f"{label} is {_render_condition_value(expected)}"
    return "the condition is met"


def _numeric(value: Any) -> int | float | None:
    """Return *value* as a comparable number without a lossy conversion."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return value
    return None


def _single_value_issues(
    manifest: ModuleManifest,
    option: ConfigOption,
    value: Any,
) -> list[str]:
    """Check the single-value constraints of *option* against *value*."""
    validation = option.validation or {}
    label = setting_display_name(manifest.name, option)
    issues: list[str] = []

    choices = validation.get("choices")
    if isinstance(choices, list) and value not in choices:
        allowed = ", ".join(str(choice) for choice in choices)
        issues.append(f"{label} must be one of: {allowed}")

    minimum = validation.get("min")
    maximum = validation.get("max")
    if minimum is not None or maximum is not None:
        numeric = _numeric(value)
        if numeric is None:
            issues.append(f"{label} must be a number")
        else:
            if isinstance(minimum, (int, float)) and numeric < minimum:
                issues.append(f"{label} must be >= {minimum}")
            if isinstance(maximum, (int, float)) and numeric > maximum:
                issues.append(f"{label} must be <= {maximum}")

    pattern = validation.get(_PATTERN_KEY)
    if isinstance(pattern, str) and pattern:
        if not re.fullmatch(pattern, str(value)):
            issues.append(f"{label} must match pattern {pattern}")

    return issues


def _cross_option_issues(
    manifest: ModuleManifest,
    option: ConfigOption,
    resolved: Mapping[str, Any],
) -> list[str]:
    """Check ``required_when`` / ``any_of`` constraints of *option*."""
    validation = option.validation or {}
    required_when = validation.get("required_when")
    condition: Mapping[str, Any] | None = None
    if isinstance(required_when, Mapping):
        if not _condition_matches(required_when, resolved):
            return []
        condition = required_when

    any_of = validation.get("any_of")
    if isinstance(any_of, list) and any_of:
        siblings = [option.name]
        siblings.extend(str(name) for name in any_of if str(name) != option.name)
        if all(option_value_is_empty(resolved.get(name)) for name in siblings):
            labels = ", ".join(_option_label(manifest, name) for name in siblings)
            suffix = ""
            if condition is not None:
                suffix = f" when {_render_condition(manifest, condition)}"
            return [f"one of {labels} is required{suffix}"]
        return []

    if condition is not None and option_value_is_empty(resolved.get(option.name)):
        label = setting_display_name(manifest.name, option)
        rendered = _render_condition(manifest, condition)
        return [f"{label} is required when {rendered}"]

    return []


def collect_option_validation_issues(
    manifest: ModuleManifest,
    overrides: Mapping[str, Any] | None = None,
    *,
    supplied: Mapping[str, Any] | None = None,
) -> list[OptionValidationIssue]:
    """Validate every declared option against the manifest's own rules.

    Args:
        manifest: The loaded module manifest.
        overrides: Supplied option values, already put through the caller's
            canonicalization (for example the ``quickscale.yml`` options after
            ``sanitize_module_options``).  Only names the manifest declares are
            considered; undeclared keys are another layer's concern.
        supplied: The same values as they were authored, before any lossy
            coercion.  The declared ``type`` is checked against these so a
            value the caller would stringify is still refused as the wrong
            type.  Defaults to *overrides*.

    Returns:
        Every failed constraint, in option-name order, each carrying the
        option that must be fixed.  A supplied key the manifest declares
        retired is reported first, with the manifest's removal message.
    """
    resolved = normalize_module_option_values(manifest, overrides)
    raw_values = dict(overrides or {}) if supplied is None else dict(supplied)

    issues: list[OptionValidationIssue] = []
    for retired_name, message in sorted(manifest.retired_options.items()):
        if retired_name in raw_values:
            issues.append(OptionValidationIssue(retired_name, message))
    for option_name in sorted(resolved):
        option = manifest.get_option(option_name)
        if option is None:
            continue
        if option_name in raw_values:
            checked_value = raw_values[option_name]
        else:
            checked_value = resolved.get(option_name)
        if checked_value is None or not option_type_matches(
            option.option_type, checked_value
        ):
            issues.append(_type_issue(manifest, option, option_name))
            issues.extend(
                OptionValidationIssue(option_name, message)
                for message in _cross_option_issues(manifest, option, resolved)
            )
            continue
        for message in _single_value_issues(
            manifest, option, resolved.get(option_name)
        ):
            issues.append(OptionValidationIssue(option_name, message))
        for message in _cross_option_issues(manifest, option, resolved):
            issues.append(OptionValidationIssue(option_name, message))

    return issues


def validate_module_options(
    manifest: ModuleManifest,
    overrides: Mapping[str, Any] | None = None,
    *,
    supplied: Mapping[str, Any] | None = None,
) -> list[str]:
    """Return failed-constraint messages for a manifest's declared options."""
    return [
        issue.message
        for issue in collect_option_validation_issues(
            manifest, overrides, supplied=supplied
        )
    ]


__all__ = [
    "ALLOWED_VALIDATION_KEYS",
    "CROSS_OPTION_VALIDATION_KEYS",
    "OPTION_TYPE_LABELS",
    "SINGLE_OPTION_VALIDATION_KEYS",
    "OptionValidationIssue",
    "collect_option_validation_issues",
    "option_type_matches",
    "option_value_is_empty",
    "setting_display_name",
    "validate_module_options",
]
