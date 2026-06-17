"""CRM module manifest-driven configuration adapter.

Replaces the legacy ``crm_contract.py`` by sourcing defaults from the CRM
``module.yml`` manifest and routing normalization, validation, and resolution
through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

The public API is a drop-in replacement for the old contract file so that
callers in ``apply_command.py`` and ``module_config.py`` can use it without
rewriting their logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
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
# Defaults are sourced from the CRM module.yml manifest.  They are
# re-declared here as module-level constants so that callers that reference
# them by name continue to work without changes.
# ---------------------------------------------------------------------------

LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION = "default_pipeline_stages"

# ---------------------------------------------------------------------------
# Manifest + derivation schema
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_CRM_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "crm" / "module.yml"


def _load_crm_manifest() -> Any:
    """Load the CRM module manifest from ``module.yml``."""
    return load_manifest_from_path(_CRM_MANIFEST_PATH)


def _build_crm_derivation_schema() -> ModuleDerivationSchema:
    """Build the derivation schema for the CRM module.

    Captures the normalization and validation rules that the generic
    resolver can execute.  CRM-specific rules that the resolver does
    not support natively (integer range checks, boolean type checks)
    are applied as post-resolution steps in the adapter functions below.
    """
    return ModuleDerivationSchema(
        module_name="crm",
        version="1",
        option_derivations={
            "enable_api": OptionDerivation(
                option_key="enable_api",
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_ENABLE_API",
                        source_options=["enable_api"],
                        derivation_type="direct",
                        expression={"option": "enable_api"},
                    ),
                ],
            ),
            "deals_per_page": OptionDerivation(
                option_key="deals_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="deals_per_page",
                        target_key="deals_per_page",
                        rule_type="strip",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="deals_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description=(
                            "modules.crm.deals_per_page must be a positive integer"
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_DEALS_PER_PAGE",
                        source_options=["deals_per_page"],
                        derivation_type="direct",
                        expression={"option": "deals_per_page"},
                    ),
                ],
            ),
            "contacts_per_page": OptionDerivation(
                option_key="contacts_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="contacts_per_page",
                        target_key="contacts_per_page",
                        rule_type="strip",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="contacts_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description=(
                            "modules.crm.contacts_per_page must be a positive integer"
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="CRM_CONTACTS_PER_PAGE",
                        source_options=["contacts_per_page"],
                        derivation_type="direct",
                        expression={"option": "contacts_per_page"},
                    ),
                ],
            ),
        },
    )


# ---------------------------------------------------------------------------
# Public API — drop-in replacement for crm_contract.py
# ---------------------------------------------------------------------------


def default_crm_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for CRM.

    Defaults are sourced from the CRM ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.
    """
    manifest = _load_crm_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_crm_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return CRM options with retired legacy keys removed."""
    normalized = dict(options or {})
    normalized.pop(LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION, None)
    return normalized


def resolve_crm_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge CRM options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction
    and core normalization, then applies CRM-specific post-resolution
    type coercion that the generic resolver does not cover.
    """
    manifest = _load_crm_manifest()
    schema = _build_crm_derivation_schema()

    # Strip legacy keys before passing to the resolver.
    cleaned = normalize_crm_module_options(options)

    result = resolve_module_config(manifest, schema, overrides=cleaned)
    resolved = dict(result.resolved)

    # Coerce integer fields to int for downstream consumers.
    resolved["deals_per_page"] = int(resolved.get("deals_per_page", 25))
    resolved["contacts_per_page"] = int(resolved.get("contacts_per_page", 50))

    # Coerce boolean fields to bool for downstream consumers.
    resolved["enable_api"] = bool(resolved.get("enable_api", True))

    return resolved


def validate_crm_module_options(
    options: Mapping[str, Any] | None,
) -> list[str]:
    """Return validation issues for CRM module options.

    Uses the manifest-driven resolver for core normalization, then adds
    CRM-specific checks for integer ranges and boolean types.
    """
    resolved = resolve_crm_module_options(options)
    issues: list[str] = []

    # deals_per_page must be a positive integer.
    # resolve_crm_module_options already coerces this to int.
    deals_per_page = int(resolved["deals_per_page"])
    if deals_per_page < 1:
        issues.append("modules.crm.deals_per_page must be at least 1")

    # contacts_per_page must be a positive integer.
    # resolve_crm_module_options already coerces this to int.
    contacts_per_page = int(resolved["contacts_per_page"])
    if contacts_per_page < 1:
        issues.append("modules.crm.contacts_per_page must be at least 1")

    # Boolean type checks.
    if not isinstance(resolved.get("enable_api"), bool):
        issues.append("modules.crm.enable_api must be a boolean")

    return issues


__all__ = [
    "LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION",
    "default_crm_module_options",
    "normalize_crm_module_options",
    "resolve_crm_module_options",
    "validate_crm_module_options",
]
