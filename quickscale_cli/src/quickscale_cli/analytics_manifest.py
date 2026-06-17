"""Analytics module manifest-driven configuration adapter.

Replaces the legacy ``analytics_contract.py`` by sourcing defaults from the
analytics ``module.yml`` manifest and routing normalization, validation, and
resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

The public API is a drop-in replacement for the old contract file so that
callers in ``apply_command.py`` and ``module_config.py`` can use it without
rewriting their logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any
from urllib.parse import urlsplit

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
# Provider and env-var defaults are sourced from the analytics module.yml
# manifest.  They are re-declared here as module-level constants so that
# callers that reference them by name (apply_command, module_config) continue
# to work without changes.
# ---------------------------------------------------------------------------

ANALYTICS_PROVIDER_POSTHOG = "posthog"
ANALYTICS_PROVIDERS = (ANALYTICS_PROVIDER_POSTHOG,)

DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR = "POSTHOG_API_KEY"
DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR = "POSTHOG_HOST"

ANALYTICS_POSTHOG_DEFAULT_HOST = "https://us.i.posthog.com"
ANALYTICS_POSTHOG_EU_HOST = "https://eu.i.posthog.com"

# Event name constants.  The analytics module also declares these in its own
# ``events.py``; they are re-exported here for backward compatibility with
# callers that imported them from the contract file.
ANALYTICS_EVENT_PAGEVIEW = "$pageview"
ANALYTICS_EVENT_FORM_SUBMIT = "form_submit"
ANALYTICS_EVENT_SOCIAL_LINK_CLICK = "social_link_click"

_ANALYTICS_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# ---------------------------------------------------------------------------
# Manifest + derivation schema
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ANALYTICS_MANIFEST_PATH = (
    _REPO_ROOT / "quickscale_modules" / "analytics" / "module.yml"
)


def _load_analytics_manifest() -> Any:
    """Load the analytics module manifest from ``module.yml``."""
    return load_manifest_from_path(_ANALYTICS_MANIFEST_PATH)


def _build_analytics_derivation_schema() -> ModuleDerivationSchema:
    """Build the derivation schema for the analytics module.

    Captures the normalization and validation rules that the generic
    resolver can execute.  Analytics-specific rules that the resolver
    does not support natively (URL canonicalization, boolean type checks)
    are applied as post-resolution steps in the adapter functions below.
    """
    return ModuleDerivationSchema(
        module_name="analytics",
        version="1",
        option_derivations={
            "provider": OptionDerivation(
                option_key="provider",
                normalization_rules=[
                    NormalizationRule(
                        source_key="provider",
                        target_key="provider",
                        rule_type="strip",
                    ),
                    NormalizationRule(
                        source_key="provider",
                        target_key="provider",
                        rule_type="lowercase",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="provider",
                        rule_type="choices",
                        allowed_values=list(ANALYTICS_PROVIDERS),
                        description=(
                            "modules.analytics.provider must be one of: "
                            + ", ".join(ANALYTICS_PROVIDERS)
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_PROVIDER",
                        source_options=["provider"],
                        derivation_type="direct",
                        expression={"option": "provider"},
                    ),
                ],
            ),
            "posthog_api_key_env_var": OptionDerivation(
                option_key="posthog_api_key_env_var",
                normalization_rules=[
                    NormalizationRule(
                        source_key="posthog_api_key_env_var",
                        target_key="posthog_api_key_env_var",
                        rule_type="strip",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="posthog_api_key_env_var",
                        rule_type="pattern",
                        pattern=r"^[A-Z][A-Z0-9_]*$",
                        description=(
                            "modules.analytics.posthog_api_key_env_var must be "
                            "an environment variable name matching "
                            "^[A-Z][A-Z0-9_]*$"
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
                        source_options=["posthog_api_key_env_var"],
                        derivation_type="direct",
                        expression={"option": "posthog_api_key_env_var"},
                    ),
                ],
            ),
            "posthog_host_env_var": OptionDerivation(
                option_key="posthog_host_env_var",
                normalization_rules=[
                    NormalizationRule(
                        source_key="posthog_host_env_var",
                        target_key="posthog_host_env_var",
                        rule_type="strip",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="posthog_host_env_var",
                        rule_type="pattern",
                        pattern=r"^[A-Z][A-Z0-9_]*$",
                        description=(
                            "modules.analytics.posthog_host_env_var must be "
                            "an environment variable name matching "
                            "^[A-Z][A-Z0-9_]*$"
                        ),
                    ),
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
                        source_options=["posthog_host_env_var"],
                        derivation_type="direct",
                        expression={"option": "posthog_host_env_var"},
                    ),
                ],
            ),
            "posthog_host": OptionDerivation(
                option_key="posthog_host",
                normalization_rules=[],
                validation_rules=[],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_POSTHOG_HOST",
                        source_options=["posthog_host"],
                        derivation_type="direct",
                        expression={"option": "posthog_host"},
                    ),
                ],
            ),
            "enabled": OptionDerivation(
                option_key="enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_ENABLED",
                        source_options=["enabled"],
                        derivation_type="direct",
                        expression={"option": "enabled"},
                    ),
                ],
            ),
            "exclude_debug": OptionDerivation(
                option_key="exclude_debug",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG",
                        source_options=["exclude_debug"],
                        derivation_type="direct",
                        expression={"option": "exclude_debug"},
                    ),
                ],
            ),
            "exclude_staff": OptionDerivation(
                option_key="exclude_staff",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_EXCLUDE_STAFF",
                        source_options=["exclude_staff"],
                        derivation_type="direct",
                        expression={"option": "exclude_staff"},
                    ),
                ],
            ),
            "anonymous_by_default": OptionDerivation(
                option_key="anonymous_by_default",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
                        source_options=["anonymous_by_default"],
                        derivation_type="direct",
                        expression={"option": "anonymous_by_default"},
                    ),
                ],
            ),
        },
    )


# ---------------------------------------------------------------------------
# Analytics-specific post-resolution helpers
# ---------------------------------------------------------------------------


def _normalize_posthog_host(value: Any) -> str:
    """Canonicalize a PostHog host URL.

    Mirrors the legacy contract behaviour: strip whitespace, prepend
    ``https://`` when no scheme is present, and remove trailing slashes.
    """
    candidate = str(value).strip()
    if not candidate:
        return ""
    if not candidate.startswith(("http://", "https://")):
        candidate = "https://" + candidate.lstrip("/")
    return candidate.rstrip("/")


def _is_valid_posthog_host(value: str) -> bool:
    """Return whether *value* is an absolute http(s) URL."""
    candidate = value.strip()
    if not candidate:
        return False
    parsed = urlsplit(candidate)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _apply_analytics_post_normalization(resolved: dict[str, Any]) -> dict[str, Any]:
    """Apply analytics-specific normalization the resolver cannot express.

    The generic resolver handles strip/lowercase/choices/pattern rules.
    URL canonicalization for ``posthog_host`` is analytics-specific domain
    logic applied here after the resolver pipeline.
    """
    if "posthog_host" in resolved:
        resolved["posthog_host"] = _normalize_posthog_host(resolved["posthog_host"])
    return resolved


# ---------------------------------------------------------------------------
# Public API — drop-in replacement for analytics_contract.py
# ---------------------------------------------------------------------------


def default_analytics_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for analytics.

    Defaults are sourced from the analytics ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.
    """
    manifest = _load_analytics_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return analytics options with normalized provider and host fields."""
    normalized = dict(options or {})

    if "provider" in normalized:
        normalized["provider"] = str(normalized["provider"]).strip().lower()

    for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()

    if "posthog_host" in normalized:
        normalized["posthog_host"] = _normalize_posthog_host(normalized["posthog_host"])

    return normalized


def resolve_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge analytics options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction
    and core normalization, then applies the analytics-specific URL
    canonicalization that the generic resolver does not cover.
    """
    manifest = _load_analytics_manifest()
    schema = _build_analytics_derivation_schema()

    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Apply analytics-specific post-resolution normalization.
    _apply_analytics_post_normalization(resolved)

    # Ensure final provider/env-var fields are normalized even after merge.
    resolved["provider"] = str(resolved.get("provider", "")).strip().lower()
    resolved["posthog_api_key_env_var"] = str(
        resolved.get("posthog_api_key_env_var", "")
    ).strip()
    resolved["posthog_host_env_var"] = str(
        resolved.get("posthog_host_env_var", "")
    ).strip()
    resolved["posthog_host"] = _normalize_posthog_host(resolved.get("posthog_host", ""))

    return resolved


def validate_analytics_env_var_reference(option_name: str, value: Any) -> str | None:
    """Validate an analytics env-var reference field."""
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.analytics.{option_name}"
    if not _ANALYTICS_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )
    return None


def validate_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> list[str]:
    """Return validation issues for analytics module options.

    Uses the manifest-driven resolver for provider-choices and env-var
    pattern validation, then adds analytics-specific checks for the
    PostHog host URL and boolean type constraints.
    """
    resolved = resolve_analytics_module_options(options)
    issues: list[str] = []

    provider = str(resolved.get("provider", "")).strip().lower()
    if provider not in ANALYTICS_PROVIDERS:
        issues.append(
            "modules.analytics.provider must be one of: "
            + ", ".join(ANALYTICS_PROVIDERS)
        )

    for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
        issue = validate_analytics_env_var_reference(
            option_name,
            resolved.get(option_name, ""),
        )
        if issue:
            issues.append(issue)

    if not _is_valid_posthog_host(str(resolved.get("posthog_host", ""))):
        issues.append("modules.analytics.posthog_host must be an absolute http(s) URL")

    for option_name in (
        "enabled",
        "exclude_debug",
        "exclude_staff",
        "anonymous_by_default",
    ):
        if not isinstance(resolved.get(option_name), bool):
            issues.append(f"modules.analytics.{option_name} must be a boolean")

    return issues


def analytics_production_targeted(options: Mapping[str, Any] | None) -> bool:
    """Return whether analytics is configured for live runtime capture."""
    resolved = resolve_analytics_module_options(options)
    if not bool(resolved.get("enabled", True)):
        return False

    api_key_env_var = str(resolved.get("posthog_api_key_env_var", "")).strip()
    return not bool(
        validate_analytics_env_var_reference(
            "posthog_api_key_env_var",
            api_key_env_var,
        )
    )


__all__ = [
    "ANALYTICS_EVENT_FORM_SUBMIT",
    "ANALYTICS_EVENT_PAGEVIEW",
    "ANALYTICS_EVENT_SOCIAL_LINK_CLICK",
    "ANALYTICS_POSTHOG_DEFAULT_HOST",
    "ANALYTICS_POSTHOG_EU_HOST",
    "ANALYTICS_PROVIDER_POSTHOG",
    "ANALYTICS_PROVIDERS",
    "DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
    "DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR",
    "analytics_production_targeted",
    "default_analytics_module_options",
    "normalize_analytics_module_options",
    "resolve_analytics_module_options",
    "validate_analytics_env_var_reference",
    "validate_analytics_module_options",
]
