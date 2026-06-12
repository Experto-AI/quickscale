"""Forms module manifest-driven configuration adapter.

Replaces the legacy hardcoded defaults and derivation logic that lived inline
in ``module_config.py`` and ``module_wiring_specs.py`` by sourcing defaults
from the forms ``module.yml`` manifest and routing normalization, validation,
and resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

The public API mirrors the analytics pilot pattern so that callers in
``module_wiring_specs.py``, ``apply_command.py``, and ``module_config.py``
can migrate without rewriting their logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

# ---------------------------------------------------------------------------
# Constants
#
# Defaults are sourced from the forms module.yml manifest.  They are
# re-declared here as module-level constants so that callers that reference
# them by name continue to work without changes.
# ---------------------------------------------------------------------------

DEFAULT_FORMS_PER_PAGE = 25
DEFAULT_FORMS_SPAM_PROTECTION_ENABLED = True
DEFAULT_FORMS_RATE_LIMIT = "5/hour"
DEFAULT_FORMS_DATA_RETENTION_DAYS = 365
DEFAULT_FORMS_SUBMISSIONS_API_ENABLED = True

_FORMS_RATE_LIMIT_PATTERN = re.compile(r"^\d+/(second|minute|hour|day)$")

# ---------------------------------------------------------------------------
# Manifest + derivation schema
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_FORMS_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "forms" / "module.yml"


def _load_forms_manifest() -> Any:
    """Load the forms module manifest from ``module.yml``."""
    return load_manifest_from_path(_FORMS_MANIFEST_PATH)


def _build_forms_derivation_schema() -> ModuleDerivationSchema:
    """Build the derivation schema for the forms module.

    Captures the normalization and validation rules that the generic
    resolver can execute.  Forms-specific rules that the resolver does
    not support natively (rate-limit format, integer range checks) are
    applied as post-resolution steps in the adapter functions below.
    """
    return ModuleDerivationSchema(
        module_name="forms",
        version="1",
        option_derivations={
            "forms_per_page": OptionDerivation(
                option_key="forms_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="forms_per_page",
                        target_key="forms_per_page",
                        rule_type="strip",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="forms_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description=(
                            "modules.forms.forms_per_page must be a positive integer"
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_PER_PAGE",
                        source_options=["forms_per_page"],
                        derivation_type="direct",
                        expression={"option": "forms_per_page"},
                    ),
                ],
            ),
            "spam_protection_enabled": OptionDerivation(
                option_key="spam_protection_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_SPAM_PROTECTION",
                        source_options=["spam_protection_enabled"],
                        derivation_type="direct",
                        expression={"option": "spam_protection_enabled"},
                    ),
                ],
            ),
            "rate_limit": OptionDerivation(
                option_key="rate_limit",
                normalization_rules=[
                    NormalizationRule(
                        source_key="rate_limit",
                        target_key="rate_limit",
                        rule_type="strip",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="rate_limit",
                        rule_type="pattern",
                        pattern=r"^\d+/(second|minute|hour|day)$",
                        description=(
                            "modules.forms.rate_limit must match format "
                            "'<count>/<period>' where period is one of: "
                            "second, minute, hour, day"
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_RATE_LIMIT",
                        source_options=["rate_limit"],
                        derivation_type="direct",
                        expression={"option": "rate_limit"},
                    ),
                ],
            ),
            "data_retention_days": OptionDerivation(
                option_key="data_retention_days",
                normalization_rules=[
                    NormalizationRule(
                        source_key="data_retention_days",
                        target_key="data_retention_days",
                        rule_type="strip",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="data_retention_days",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description=(
                            "modules.forms.data_retention_days must be a "
                            "non-negative integer"
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_DATA_RETENTION_DAYS",
                        source_options=["data_retention_days"],
                        derivation_type="direct",
                        expression={"option": "data_retention_days"},
                    ),
                ],
            ),
            "submissions_api_enabled": OptionDerivation(
                option_key="submissions_api_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="FORMS_SUBMISSIONS_API",
                        source_options=["submissions_api_enabled"],
                        derivation_type="direct",
                        expression={"option": "submissions_api_enabled"},
                    ),
                ],
            ),
        },
    )


# ---------------------------------------------------------------------------
# Public API — drop-in replacement for the legacy hardcoded forms defaults
# ---------------------------------------------------------------------------


def default_forms_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for forms.

    Defaults are sourced from the forms ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.
    """
    manifest = _load_forms_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_forms_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return forms options with normalized string fields."""
    normalized = dict(options or {})

    for option_name in ("rate_limit",):
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()

    return normalized


def resolve_forms_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge forms options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction
    and core normalization, then applies forms-specific post-resolution
    type coercion that the generic resolver does not cover.
    """
    manifest = _load_forms_manifest()
    schema = _build_forms_derivation_schema()

    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Ensure final fields are normalized even after merge.
    resolved["rate_limit"] = str(resolved.get("rate_limit", "")).strip()

    # Coerce integer fields to int for downstream consumers.
    resolved["forms_per_page"] = int(resolved.get("forms_per_page", 25))
    resolved["data_retention_days"] = int(resolved.get("data_retention_days", 365))

    # Coerce boolean fields to bool for downstream consumers.
    resolved["spam_protection_enabled"] = bool(
        resolved.get("spam_protection_enabled", True)
    )
    resolved["submissions_api_enabled"] = bool(
        resolved.get("submissions_api_enabled", True)
    )

    return resolved


def validate_forms_module_options(
    options: Mapping[str, Any] | None,
) -> list[str]:
    """Return validation issues for forms module options.

    Uses the manifest-driven resolver for core normalization, then adds
    forms-specific checks for integer ranges, boolean types, and rate-limit
    format.
    """
    resolved = resolve_forms_module_options(options)
    issues: list[str] = []

    # forms_per_page must be a positive integer.
    try:
        forms_per_page = int(resolved.get("forms_per_page", 0))
        if forms_per_page < 1:
            issues.append("modules.forms.forms_per_page must be at least 1")
    except (TypeError, ValueError):
        issues.append("modules.forms.forms_per_page must be a positive integer")

    # data_retention_days must be a non-negative integer.
    try:
        data_retention_days = int(resolved.get("data_retention_days", -1))
        if data_retention_days < 0:
            issues.append(
                "modules.forms.data_retention_days must be a non-negative integer"
            )
    except (TypeError, ValueError):
        issues.append(
            "modules.forms.data_retention_days must be a non-negative integer"
        )

    # rate_limit must match the expected format.
    rate_limit = str(resolved.get("rate_limit", "")).strip()
    if not _FORMS_RATE_LIMIT_PATTERN.match(rate_limit):
        issues.append(
            "modules.forms.rate_limit must match format '<count>/<period>' "
            "where period is one of: second, minute, hour, day"
        )

    # Boolean type checks.
    for option_name in ("spam_protection_enabled", "submissions_api_enabled"):
        if not isinstance(resolved.get(option_name), bool):
            issues.append(f"modules.forms.{option_name} must be a boolean")

    return issues


__all__ = [
    "DEFAULT_FORMS_DATA_RETENTION_DAYS",
    "DEFAULT_FORMS_PER_PAGE",
    "DEFAULT_FORMS_RATE_LIMIT",
    "DEFAULT_FORMS_SPAM_PROTECTION_ENABLED",
    "DEFAULT_FORMS_SUBMISSIONS_API_ENABLED",
    "default_forms_module_options",
    "normalize_forms_module_options",
    "resolve_forms_module_options",
    "validate_forms_module_options",
]
