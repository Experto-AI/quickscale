"""Manifest-declared option validation.

One engine for the per-option ``validation`` block declared next to the option
in ``module.yml``.  ``quickscale plan`` and ``quickscale apply`` run it from
``quickscale_core.schema.config_schema`` on the values a project supplies, and
the generated-project startup check consumes the same block once ``apply``
writes the settings schema.

The complete vocabulary, as Module Conventions rule 12 records it:

* single-value checks — ``choices`` (a closed set; on a ``list`` option each
  item is checked), ``min`` / ``max`` (numeric bounds), ``pattern`` (a
  full-match regular expression), and ``not_empty: true`` (a string not blank;
  a list or mapping not empty);
* cross-option checks — ``required_when`` (this option must be set while the
  condition holds), ``any_of`` (at least one sibling is set; a boolean ``false``
  counts as unset inside ``any_of`` only, so a boolean option that must be true
  participates correctly while ``option_value_is_empty`` itself is unchanged),
  ``subset_of`` (every item of this list is in the other list), ``excludes``
  (the value must equal none of the listed values, compared case-insensitively;
  optional ``when``), and ``intersects`` (the list must contain at least one of
  the listed values; optional ``when``);
* the condition grammar shared by ``required_when``, ``excludes.when``, and
  ``intersects.when``: a mapping whose entries must all hold; each entry's
  value is a literal, a list of literals, or ``{not_empty: true}``.  Existing
  single-entry literal/list conditions keep their meaning;
* declared normalization kinds, applied to supplied values before the
  value-level checks — ``identity``, ``strip``, ``lowercase``, ``url``,
  ``choice_map``, ``coerce_int``, ``coerce_bool``, ``slug``, and ``list``.
  ``slug`` lowercases, maps ``_`` and whitespace to ``-``, drops characters
  outside ``[a-z0-9-]``, collapses repeated dashes, trims leading/trailing
  dashes, takes an optional ``max_length``, and applies an optional ``replace``
  mapping first.  ``list`` comma-splits a string or wraps a scalar, applies its
  nested ``item_rules`` to each item, drops empties, and dedupes preserving
  order; a provider alias table is a ``choice_map`` item rule.

A check this vocabulary cannot express needs a decision edit before it is
added.  A runtime predicate that decides module behavior from resolved options
— notifications' production-targeted / live-delivery email-backend selection —
is adapter code, not validation, and is never declared here.

Messages name the setting a module author or operator must fix — the option's
``django_setting`` with its ``quickscale.yml`` path — including the setting
named in a condition.

The manifest's top-level ``retired_options`` section names keys that no longer
exist together with the message that must refuse them; a supplied retired key
is reported first, so a retired name is never mistaken for an undeclared one.

Values are canonicalized before the value-level checks: the caller's own
canonicalization runs first, then the manifest's declared normalization rules
through :func:`~quickscale_core.manifest.resolver.normalize_module_option_values`,
so ``GRID`` and ``" 5/hour "`` are judged as the canonical forms the manifest
names.  The declared ``type`` is checked against the values as supplied — a
string the manifest's own rules turn into the declared type is an accepted
spelling (a ``list`` rule comma-splitting a string), while a value of another
shape is refused as the wrong type.
"""

from __future__ import annotations

from collections.abc import Mapping
import re
from dataclasses import dataclass
from typing import Any

from quickscale_core.manifest.resolver import normalize_module_option_values
from quickscale_core.manifest.schema import ConfigOption, ModuleManifest

#: Single-value keys accepted inside a per-option ``validation`` block.
SINGLE_OPTION_VALIDATION_KEYS = frozenset(
    {"choices", "min", "max", "pattern", "not_empty"}
)
#: Cross-option keys accepted inside a per-option ``validation`` block.
CROSS_OPTION_VALIDATION_KEYS = frozenset(
    {"required_when", "any_of", "subset_of", "excludes", "intersects"}
)
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


def _supplied_type_matches(
    manifest: ModuleManifest, option: ConfigOption, value: Any
) -> bool:
    """Return whether *value* satisfies the option's declared ``type``.

    A *string* the manifest's own normalization rules turn into the declared
    type is an accepted spelling: a ``list`` rule comma-splits a string, so a
    string supplied for a list option is judged as the list it canonicalizes
    to.  A value of another shape is judged as supplied — the rules document no
    mapping or container input — and ``None`` never matches.
    """
    if value is None:
        return False
    if option_type_matches(option.option_type, value):
        return True
    if not isinstance(value, str):
        return False
    canonical = normalize_module_option_values(manifest, {option.name: value}).get(
        option.name
    )
    return canonical is not None and option_type_matches(option.option_type, canonical)


def _unsupported_list_items(value: Any) -> list[Any]:
    """Return the items of a list value that are neither scalars nor empties.

    The ``list`` normalization rule cannot represent a mapping, a non-empty
    container, or an arbitrary object; the engine refuses such an item rather
    than letting a rule stringify it into a plausible-looking value.
    """
    if not isinstance(value, (list, tuple)):
        return []
    unsupported: list[Any] = []
    for item in value:
        if item is None or isinstance(item, (str, int, float, bool)):
            continue
        if isinstance(item, (list, tuple, set, frozenset, Mapping)) and not item:
            continue
        unsupported.append(item)
    return unsupported


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


def _is_not_empty_condition(expected: Any) -> bool:
    """Return whether an entry value is the ``{not_empty: true}`` condition."""
    return isinstance(expected, Mapping) and expected.get("not_empty") is True


def _condition_entry_matches(expected: Any, actual: Any) -> bool:
    """Return whether one condition entry holds against *actual*.

    An entry value is a literal (equality), a list of literals (any of them),
    or ``{not_empty: true}`` (the option counts as set).
    """
    if _is_not_empty_condition(expected):
        return not option_value_is_empty(actual)
    if isinstance(expected, list):
        return any(actual == allowed for allowed in expected)
    return bool(actual == expected)


def _condition_matches(
    condition: Mapping[str, Any] | None, resolved: Mapping[str, Any]
) -> bool:
    """Return whether every entry of a condition mapping holds.

    An entry over an option the resolved mapping does not carry never holds.
    """
    if not isinstance(condition, Mapping) or not condition:
        return False
    for condition_option, expected in condition.items():
        if not isinstance(condition_option, str) or condition_option not in resolved:
            return False
        if not _condition_entry_matches(expected, resolved[condition_option]):
            return False
    return True


def _render_condition_entry(
    manifest: ModuleManifest, condition_option: str, expected: Any
) -> str:
    """Render one condition entry for a failure message."""
    label = _option_label(manifest, condition_option)
    if _is_not_empty_condition(expected):
        return f"{label} is set"
    if isinstance(expected, list):
        values = ", ".join(str(value) for value in expected)
        return f"{label} is one of: {values}"
    return f"{label} is {_render_condition_value(expected)}"


def _render_condition(
    manifest: ModuleManifest,
    condition: Mapping[str, Any],
) -> str:
    """Render a condition mapping for a failure message."""
    return " and ".join(
        _render_condition_entry(manifest, str(condition_option), expected)
        for condition_option, expected in condition.items()
    )


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

    unsupported_items = _unsupported_list_items(value)
    if unsupported_items:
        rendered = ", ".join(str(item) for item in unsupported_items)
        issues.append(f"{label} contains unsupported items: {rendered}")

    choices = validation.get("choices")
    if isinstance(choices, list) and choices:
        if option.option_type == "list" and isinstance(value, list):
            unsupported = [item for item in value if item not in choices]
            if unsupported:
                allowed = ", ".join(str(choice) for choice in choices)
                rendered = ", ".join(sorted(str(item) for item in unsupported))
                issues.append(
                    f"{label} contains unsupported values: {rendered} "
                    f"(allowed: {allowed})"
                )
        elif value not in choices:
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

    if validation.get("not_empty") is True and option_value_is_empty(value):
        issues.append(f"{label} cannot be empty")

    return issues


def _any_of_counts_as_unset(value: Any) -> bool:
    """Return whether *value* counts as unset inside ``any_of``.

    A boolean ``false`` is unset here only: ``any_of`` is how a manifest says
    "at least one of these boolean surfaces must be true", while
    ``option_value_is_empty`` keeps its meaning everywhere else so
    ``required_when`` on a boolean option still reads the option as present.
    """
    if value is False:
        return True
    return option_value_is_empty(value)


def _cross_option_issues(
    manifest: ModuleManifest,
    option: ConfigOption,
    resolved: Mapping[str, Any],
) -> list[str]:
    """Check every cross-option constraint of *option*."""
    validation = option.validation or {}
    label = setting_display_name(manifest.name, option)
    issues: list[str] = []

    required_when = validation.get("required_when")
    required_when_condition = (
        required_when if isinstance(required_when, Mapping) else None
    )
    condition_met = required_when_condition is not None and _condition_matches(
        required_when_condition, resolved
    )
    has_required_when = required_when_condition is not None

    any_of = validation.get("any_of")
    if has_required_when and not condition_met:
        # The option is not required, and a declared ``any_of`` is gated off
        # while the condition is unmet.
        pass
    elif isinstance(any_of, list) and any_of:
        siblings = [option.name]
        siblings.extend(str(name) for name in any_of if str(name) != option.name)
        if all(_any_of_counts_as_unset(resolved.get(name)) for name in siblings):
            labels = ", ".join(_option_label(manifest, name) for name in siblings)
            suffix = ""
            if condition_met and required_when_condition is not None:
                suffix = f" when {_render_condition(manifest, required_when_condition)}"
            issues.append(f"one of {labels} is required{suffix}")
    elif (
        condition_met
        and required_when_condition is not None
        and option_value_is_empty(resolved.get(option.name))
    ):
        rendered = _render_condition(manifest, required_when_condition)
        issues.append(f"{label} is required when {rendered}")

    subset_of = validation.get("subset_of")
    if isinstance(subset_of, str) and subset_of:
        value = resolved.get(option.name)
        superset = resolved.get(subset_of)
        superset_values = superset if isinstance(superset, (list, tuple, set)) else []
        if isinstance(value, (list, tuple, set)):
            missing = [item for item in value if item not in superset_values]
            if missing:
                other_label = _option_label(manifest, subset_of)
                issues.append(f"{label} must be a subset of {other_label}")

    excludes = validation.get("excludes")
    if isinstance(excludes, Mapping):
        when = excludes.get("when")
        when_condition = when if isinstance(when, Mapping) else None
        if when_condition is None or _condition_matches(when_condition, resolved):
            forbidden = excludes.get("values", [])
            value = str(resolved.get(option.name))
            if any(
                value.casefold() == str(candidate).casefold() for candidate in forbidden
            ):
                rendered = ", ".join(str(candidate) for candidate in forbidden)
                suffix = (
                    f" when {_render_condition(manifest, when_condition)}"
                    if when_condition is not None
                    else ""
                )
                issues.append(f"{label} must not be one of: {rendered}{suffix}")

    intersects = validation.get("intersects")
    if isinstance(intersects, Mapping):
        when = intersects.get("when")
        when_condition = when if isinstance(when, Mapping) else None
        if when_condition is None or _condition_matches(when_condition, resolved):
            expected_values = intersects.get("values", [])
            value = resolved.get(option.name)
            items = value if isinstance(value, (list, tuple, set)) else []
            if not any(item in expected_values for item in items):
                rendered = ", ".join(str(candidate) for candidate in expected_values)
                suffix = (
                    f" when {_render_condition(manifest, when_condition)}"
                    if when_condition is not None
                    else ""
                )
                issues.append(f"{label} must include one of: {rendered}{suffix}")

    return issues


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
            coercion.  The declared ``type`` is checked against these, so a
            value the caller would stringify is still refused as the wrong
            type; a value the manifest's own normalization rules turn into the
            declared type is an accepted spelling.  Defaults to *overrides*.

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
        if not _supplied_type_matches(manifest, option, checked_value):
            issues.append(_type_issue(manifest, option, option_name))
            issues.extend(
                OptionValidationIssue(option_name, message)
                for message in _cross_option_issues(manifest, option, resolved)
            )
            continue
        resolved_value = resolved.get(option_name)
        if not option_type_matches(option.option_type, resolved_value):
            # A normalization rule changed the canonical shape; the option
            # must still carry a value of its declared type.
            issues.append(_type_issue(manifest, option, option_name))
            issues.extend(
                OptionValidationIssue(option_name, message)
                for message in _cross_option_issues(manifest, option, resolved)
            )
            continue
        for message in _single_value_issues(manifest, option, resolved_value):
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
