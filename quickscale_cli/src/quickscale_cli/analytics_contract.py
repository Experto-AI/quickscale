"""Shared analytics-module configuration helpers."""

from __future__ import annotations

from collections.abc import Mapping
import re
from typing import Any
from urllib.parse import urlsplit

ANALYTICS_PROVIDER_POSTHOG = "posthog"
ANALYTICS_PROVIDERS = (ANALYTICS_PROVIDER_POSTHOG,)

DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR = "POSTHOG_API_KEY"
DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR = "POSTHOG_HOST"

ANALYTICS_POSTHOG_DEFAULT_HOST = "https://us.i.posthog.com"
ANALYTICS_POSTHOG_EU_HOST = "https://eu.i.posthog.com"

ANALYTICS_EVENT_PAGEVIEW = "$pageview"
ANALYTICS_EVENT_FORM_SUBMIT = "form_submit"
ANALYTICS_EVENT_SOCIAL_LINK_CLICK = "social_link_click"

_ANALYTICS_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def default_analytics_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for analytics."""
    return {
        "enabled": True,
        "provider": ANALYTICS_PROVIDER_POSTHOG,
        "posthog_api_key_env_var": DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
        "posthog_host_env_var": DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
        "posthog_host": ANALYTICS_POSTHOG_DEFAULT_HOST,
        "exclude_debug": True,
        "exclude_staff": False,
        "anonymous_by_default": True,
    }


def _normalize_provider(value: Any) -> str:
    return str(value).strip().lower()


def _normalize_posthog_host(value: Any) -> str:
    candidate = str(value).strip()
    if not candidate:
        return ""
    if not candidate.startswith(("http://", "https://")):
        candidate = "https://" + candidate.lstrip("/")
    return candidate.rstrip("/")


def normalize_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return analytics options with normalized provider and host fields."""
    normalized = dict(options or {})

    if "provider" in normalized:
        normalized["provider"] = _normalize_provider(normalized["provider"])

    for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()

    if "posthog_host" in normalized:
        normalized["posthog_host"] = _normalize_posthog_host(normalized["posthog_host"])

    return normalized


def resolve_analytics_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge analytics options with defaults and normalized overrides."""
    resolved = default_analytics_module_options()
    resolved.update(normalize_analytics_module_options(options))
    resolved["provider"] = _normalize_provider(resolved["provider"])
    resolved["posthog_api_key_env_var"] = str(
        resolved["posthog_api_key_env_var"]
    ).strip()
    resolved["posthog_host_env_var"] = str(resolved["posthog_host_env_var"]).strip()
    resolved["posthog_host"] = _normalize_posthog_host(resolved["posthog_host"])
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


def _is_valid_posthog_host(value: str) -> bool:
    candidate = value.strip()
    if not candidate:
        return False

    parsed = urlsplit(candidate)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def validate_analytics_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for analytics module options."""
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
