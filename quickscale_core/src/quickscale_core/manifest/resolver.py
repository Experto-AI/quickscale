"""Manifest-Driven Module Configuration Resolver

Computes module configuration and wiring inputs from a ``ModuleManifest``
paired with a ``ModuleDerivationSchema`` and optional user-supplied overrides.

This module is the runtime engine that the derivation schema types
(:mod:`quickscale_core.manifest.derivation`) describe but do not execute.
It is **additive** to the existing manifest loader and does not alter,
replace, or migrate any legacy contract-file path.

The resolver is intentionally generic — it operates on the declarative
derivation rules rather than module-specific imperative logic.  Later
roadmap phases will wire concrete modules (starting with ``analytics``)
through this path and eventually retire the per-module contract files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    LegacyKeyAlias,
    ModuleDerivationSchema,
    NormalizationRule,
    ValidationRule,
)
from quickscale_core.manifest.schema import ModuleManifest


@dataclass(frozen=True)
class ResolverResult:
    """Outcome of resolving a module's configuration through the manifest path.

    Attributes:
        module_name: The module this result is for.
        defaults: Default values for every option declared in the manifest.
        resolved: Merged and normalized option values after applying
            overrides on top of defaults.
        validation_issues: Human-readable descriptions of any validation
            constraints that the resolved values violate.  An empty list
            means all validation rules passed.
        derived_settings: Projected Django settings computed from the
            resolved option values via the derivation schema's
            ``DerivedSetting`` declarations.
        legacy_migrations: Key-value pairs that were migrated from legacy
            alias keys to their current canonical keys during resolution.
    """

    module_name: str
    defaults: dict[str, Any]
    resolved: dict[str, Any]
    validation_issues: list[str] = field(default_factory=list)
    derived_settings: dict[str, Any] = field(default_factory=dict)
    legacy_migrations: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Normalization engine
# ---------------------------------------------------------------------------


def _apply_normalization_rule(value: Any, rule: NormalizationRule) -> Any:
    """Apply a single normalization rule to a value.

    Args:
        value: The raw input value.
        rule: The normalization rule to apply.

    Returns:
        The normalized value.
    """
    rule_type = rule.rule_type

    if rule_type == "identity":
        return value

    if rule_type == "strip":
        if isinstance(value, str):
            return value.strip()
        return value

    if rule_type == "lowercase":
        if isinstance(value, str):
            return value.lower()
        return value

    if rule_type == "choice_map":
        str_value = str(value).strip()
        return rule.mapping.get(str_value, value)

    if rule_type == "coerce_int":
        try:
            return int(value)
        except (TypeError, ValueError):
            return value

    if rule_type == "coerce_bool":
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("true", "1", "yes")
        if isinstance(value, (int, float)):
            return bool(value)
        return value

    # Unknown rule type: pass through unchanged
    return value


def _normalize_value(
    value: Any,
    option_key: str,
    option_derivation: Any | None,
    shared_rules: list[NormalizationRule],
) -> Any:
    """Apply all applicable normalization rules to a single option value.

    Shared rules are applied first (in order), then per-option rules.

    Args:
        value: The raw value to normalize.
        option_key: The option key being normalized.
        option_derivation: The per-option derivation metadata, if any.
        shared_rules: Module-wide normalization rules.

    Returns:
        The normalized value.
    """
    result = value

    # Apply shared rules first
    for rule in shared_rules:
        if rule.source_key == "*" or rule.source_key == option_key:
            result = _apply_normalization_rule(result, rule)

    # Apply per-option rules
    if option_derivation is not None:
        for rule in option_derivation.normalization_rules:
            result = _apply_normalization_rule(result, rule)

    return result


# ---------------------------------------------------------------------------
# Validation engine
# ---------------------------------------------------------------------------


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
    rule_type = rule.rule_type

    if rule_type == "required":
        if value is None or (isinstance(value, str) and not value.strip()):
            return rule.description or f"{option_key} is required"

    elif rule_type == "choices":
        if value is not None and value not in rule.allowed_values:
            allowed = ", ".join(str(v) for v in rule.allowed_values)
            return rule.description or f"{option_key} must be one of: {allowed}"

    elif rule_type == "range":
        if value is not None:
            try:
                numeric = float(value)
            except (TypeError, ValueError):
                return rule.description or f"{option_key} must be a numeric value"
            if rule.min_value is not None and numeric < rule.min_value:
                return rule.description or f"{option_key} must be >= {rule.min_value}"
            if rule.max_value is not None and numeric > rule.max_value:
                return rule.description or f"{option_key} must be <= {rule.max_value}"

    elif rule_type == "pattern":
        if value is not None and rule.pattern:
            import re

            str_value = str(value)
            if not re.fullmatch(rule.pattern, str_value):
                return (
                    rule.description
                    or f"{option_key} must match pattern {rule.pattern}"
                )

    elif rule_type == "min_length":
        if value is not None:
            try:
                if len(value) < (rule.min_value or 0):
                    return (
                        rule.description
                        or f"{option_key} length must be >= {rule.min_value}"
                    )
            except TypeError:
                pass

    elif rule_type == "max_length":
        if value is not None:
            try:
                if len(value) > (rule.max_value or 0):
                    return (
                        rule.description
                        or f"{option_key} length must be <= {rule.max_value}"
                    )
            except TypeError:
                pass

    elif rule_type == "type":
        # Type validation is declared but not enforced at this layer;
        # the manifest schema's option_type field is the source of truth
        # for type coercion.  This rule type is reserved for future use.
        pass

    return None


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


# ---------------------------------------------------------------------------
# Legacy alias migration
# ---------------------------------------------------------------------------


def _apply_legacy_transform(value: Any, alias: LegacyKeyAlias) -> Any:
    """Apply the value transform declared on a legacy alias.

    Args:
        value: The raw value from the legacy key.
        alias: The legacy alias declaration.

    Returns:
        The transformed value suitable for the current key.
    """
    transform = alias.transform

    if transform == "identity":
        return value

    if transform == "split_comma_list":
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    if transform == "rename_value":
        str_value = str(value).strip()
        return alias.transform_params.get(str_value, value)

    if transform == "negate_boolean":
        if isinstance(value, bool):
            return not value
        return value

    # Unknown transform: pass through
    return value


def _migrate_legacy_keys(
    overrides: dict[str, Any],
    derivation_schema: ModuleDerivationSchema,
) -> dict[str, Any]:
    """Apply legacy key alias migrations to the overrides dict.

    For each legacy alias declared in the derivation schema, if the
    overrides contain the legacy key, the value is transformed and
    moved to the current key.  The legacy key is removed from the
    overrides.

    Args:
        overrides: Mutable copy of user-supplied overrides.
        derivation_schema: The module's derivation schema.

    Returns:
        A dict of legacy-key -> migrated-value pairs that were applied.
    """
    migrations: dict[str, Any] = {}
    all_aliases = derivation_schema.get_all_legacy_aliases()

    for alias in all_aliases:
        if alias.legacy_key in overrides:
            raw_value = overrides.pop(alias.legacy_key)
            migrated_value = _apply_legacy_transform(raw_value, alias)
            # Only set the current key if it wasn't already provided
            # explicitly (explicit current key wins over legacy alias).
            if alias.current_key not in overrides:
                overrides[alias.current_key] = migrated_value
            migrations[alias.legacy_key] = migrated_value

    return migrations


# ---------------------------------------------------------------------------
# Derived settings projection
# ---------------------------------------------------------------------------


def _project_derived_setting(setting: DerivedSetting, resolved: dict[str, Any]) -> Any:
    """Compute the value for a single derived Django setting.

    Args:
        setting: The derived setting declaration.
        resolved: The fully resolved option values.

    Returns:
        The computed setting value.
    """
    derivation_type = setting.derivation_type

    if derivation_type == "static":
        return setting.expression.get("value", setting.default)

    if derivation_type == "direct":
        option_key = setting.expression.get("option")
        if option_key and option_key in resolved:
            value = resolved[option_key]
            return value if value is not None else setting.default
        return setting.default

    if derivation_type == "conditional":
        branches = setting.expression.get("branches", {})
        # Use the first source option as the branch selector
        for source_key in setting.source_options:
            if source_key in resolved:
                selector = resolved[source_key]
                if selector in branches:
                    return branches[selector]
        return setting.default

    if derivation_type == "computed":
        # Computed derivations use a template string with {option_key}
        # placeholders.  This is a simple format-string substitution;
        # more complex expression evaluation is deferred to a later phase.
        template = setting.expression.get("template", "")
        if template:
            try:
                # Build a safe substitution context from resolved values
                context = {
                    k: str(v) if v is not None else "" for k, v in resolved.items()
                }
                return template.format(**context)
            except (KeyError, IndexError, ValueError):
                return setting.default
        return setting.default

    # Unknown derivation type: return default
    return setting.default


def _project_all_derived_settings(
    derivation_schema: ModuleDerivationSchema,
    resolved: dict[str, Any],
) -> dict[str, Any]:
    """Compute all derived Django settings from resolved option values.

    Args:
        derivation_schema: The module's derivation schema.
        resolved: The fully resolved option values.

    Returns:
        A mapping of Django setting keys to their computed values.
    """
    result: dict[str, Any] = {}
    all_settings = derivation_schema.get_all_derived_settings()

    for setting in all_settings:
        result[setting.setting_key] = _project_derived_setting(setting, resolved)

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_module_config(
    manifest: ModuleManifest,
    derivation_schema: ModuleDerivationSchema,
    overrides: dict[str, Any] | None = None,
) -> ResolverResult:
    """Compute module configuration from manifest + derivation schema + overrides.

    This is the primary entry point for the manifest-driven configuration
    path.  It performs the following steps:

    1. Extract default values from the manifest.
    2. Apply legacy key alias migrations to the overrides.
    3. Merge overrides on top of defaults.
    4. Normalize each resolved value using shared and per-option rules.
    5. Validate each resolved value against shared and per-option rules.
    6. Project derived Django settings from the resolved values.

    The legacy contract-file path is **not** touched.  Callers that still
    use ``analytics_contract.py`` or similar modules are unaffected.

    Args:
        manifest: The loaded module manifest.
        derivation_schema: The module's derivation schema describing how
            options normalize, validate, and project into settings.
        overrides: Optional user-supplied option overrides (e.g. from
            ``quickscale.yml``).  ``None`` is treated as empty.

    Returns:
        A :class:`ResolverResult` containing defaults, resolved values,
        validation issues, derived settings, and any legacy migrations
        that were applied.
    """
    # Step 1: Extract defaults from the manifest
    defaults = manifest.get_defaults()

    # Step 2: Work on a mutable copy of overrides and apply legacy migrations
    working_overrides = dict(overrides or {})
    legacy_migrations = _migrate_legacy_keys(working_overrides, derivation_schema)

    # Step 3: Merge overrides on top of defaults
    resolved = dict(defaults)
    resolved.update(working_overrides)

    # Step 4: Normalize each resolved value
    for option_key in list(resolved.keys()):
        option_derivation = derivation_schema.get_option_derivation(option_key)
        resolved[option_key] = _normalize_value(
            resolved[option_key],
            option_key,
            option_derivation,
            derivation_schema.shared_normalization_rules,
        )

    # Step 5: Validate each resolved value
    validation_issues: list[str] = []
    for option_key in sorted(resolved.keys()):
        option_derivation = derivation_schema.get_option_derivation(option_key)
        issues = _validate_value(
            resolved[option_key],
            option_key,
            option_derivation,
            derivation_schema.shared_validation_rules,
        )
        validation_issues.extend(issues)

    # Step 6: Project derived Django settings
    derived_settings = _project_all_derived_settings(derivation_schema, resolved)

    return ResolverResult(
        module_name=manifest.name,
        defaults=defaults,
        resolved=resolved,
        validation_issues=validation_issues,
        derived_settings=derived_settings,
        legacy_migrations=legacy_migrations,
    )


__all__ = [
    "ResolverResult",
    "resolve_module_config",
]
