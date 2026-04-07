"""Shared CRM-module configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION = "default_pipeline_stages"


def default_crm_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for CRM."""
    return {
        "enable_api": True,
        "deals_per_page": 25,
        "contacts_per_page": 50,
    }


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
    """Merge CRM options with defaults and normalized overrides."""
    resolved = default_crm_module_options()
    resolved.update(normalize_crm_module_options(options))
    return resolved


__all__ = [
    "LEGACY_CRM_DEFAULT_PIPELINE_STAGES_OPTION",
    "default_crm_module_options",
    "normalize_crm_module_options",
    "resolve_crm_module_options",
]
