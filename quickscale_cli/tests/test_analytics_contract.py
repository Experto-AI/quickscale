"""Tests for the v0.80.0 analytics planner/apply contract."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quickscale_cli.analytics_contract import (
    ANALYTICS_EVENT_FORM_SUBMIT,
    ANALYTICS_EVENT_PAGEVIEW,
    ANALYTICS_EVENT_SOCIAL_LINK_CLICK,
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    ANALYTICS_POSTHOG_EU_HOST,
    ANALYTICS_PROVIDER_POSTHOG,
    ANALYTICS_PROVIDERS,
    DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR,
    DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR,
    analytics_production_targeted,
    default_analytics_module_options,
    normalize_analytics_module_options,
    resolve_analytics_module_options,
    validate_analytics_env_var_reference,
    validate_analytics_module_options,
)
from quickscale_core.manifest.loader import load_manifest_from_path

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_MANIFEST_PATH = REPO_ROOT / "quickscale_modules" / "analytics" / "module.yml"


def _load_analytics_manifest() -> Any:
    return load_manifest_from_path(ANALYTICS_MANIFEST_PATH)


def test_analytics_contract_constants_are_stable() -> None:
    """The v0.80.0 analytics contract should stay explicitly PostHog-only."""
    assert ANALYTICS_PROVIDER_POSTHOG == "posthog"
    assert ANALYTICS_PROVIDERS == ("posthog",)
    assert DEFAULT_ANALYTICS_POSTHOG_API_KEY_ENV_VAR == "POSTHOG_API_KEY"
    assert DEFAULT_ANALYTICS_POSTHOG_HOST_ENV_VAR == "POSTHOG_HOST"
    assert ANALYTICS_POSTHOG_DEFAULT_HOST == "https://us.i.posthog.com"
    assert ANALYTICS_POSTHOG_EU_HOST == "https://eu.i.posthog.com"


def test_analytics_event_constants_are_stable() -> None:
    """First-party analytics event names should remain fixed."""
    assert ANALYTICS_EVENT_PAGEVIEW == "$pageview"
    assert ANALYTICS_EVENT_FORM_SUBMIT == "form_submit"
    assert ANALYTICS_EVENT_SOCIAL_LINK_CLICK == "social_link_click"


def test_default_analytics_module_options_match_manifest_contract() -> None:
    """Default planner/apply config should align with the analytics manifest."""
    manifest = _load_analytics_manifest()
    defaults = default_analytics_module_options()

    assert set(defaults.keys()) == set(manifest.get_all_options().keys())
    assert defaults["enabled"] is True
    assert defaults["provider"] == ANALYTICS_PROVIDER_POSTHOG
    assert defaults["posthog_host"] == ANALYTICS_POSTHOG_DEFAULT_HOST
    assert defaults["exclude_debug"] is True
    assert defaults["exclude_staff"] is False
    assert defaults["anonymous_by_default"] is True


def test_normalize_analytics_module_options_canonicalizes_provider_and_host() -> None:
    """Normalization should collapse provider casing and canonicalize the host URL."""
    normalized = normalize_analytics_module_options(
        {
            "provider": " PostHog ",
            "posthog_api_key_env_var": " OPS_POSTHOG_API_KEY ",
            "posthog_host_env_var": " OPS_POSTHOG_HOST ",
            "posthog_host": "eu.i.posthog.com/",
        }
    )

    assert normalized == {
        "provider": "posthog",
        "posthog_api_key_env_var": "OPS_POSTHOG_API_KEY",
        "posthog_host_env_var": "OPS_POSTHOG_HOST",
        "posthog_host": "https://eu.i.posthog.com",
    }


def test_resolve_analytics_module_options_merges_defaults() -> None:
    """Resolved analytics config should merge defaults with normalized overrides."""
    resolved = resolve_analytics_module_options(
        {
            "posthog_host": "eu.i.posthog.com",
            "exclude_staff": True,
        }
    )

    assert resolved == {
        "enabled": True,
        "provider": "posthog",
        "posthog_api_key_env_var": "POSTHOG_API_KEY",
        "posthog_host_env_var": "POSTHOG_HOST",
        "posthog_host": "https://eu.i.posthog.com",
        "exclude_debug": True,
        "exclude_staff": True,
        "anonymous_by_default": True,
    }


def test_validate_analytics_env_var_reference_rejects_invalid_names() -> None:
    """Analytics env-var references must remain env-var names, not literal secrets."""
    assert (
        validate_analytics_env_var_reference(
            "posthog_api_key_env_var",
            "OPS_POSTHOG_API_KEY",
        )
        is None
    )
    assert (
        validate_analytics_env_var_reference(
            "posthog_api_key_env_var",
            "ops-posthog-api-key",
        )
        == "modules.analytics.posthog_api_key_env_var must be an environment "
        "variable name matching ^[A-Z][A-Z0-9_]*$"
    )


@pytest.mark.parametrize(
    ("options", "expected_issue"),
    [
        (
            {"provider": "segment"},
            "modules.analytics.provider must be one of: posthog",
        ),
        (
            {"posthog_api_key_env_var": "ops-posthog-api-key"},
            "modules.analytics.posthog_api_key_env_var must be an environment "
            "variable name matching ^[A-Z][A-Z0-9_]*$",
        ),
        (
            {"posthog_host": "https:///missing-host"},
            "modules.analytics.posthog_host must be an absolute http(s) URL",
        ),
        (
            {"enabled": "yes"},
            "modules.analytics.enabled must be a boolean",
        ),
    ],
)
def test_validate_analytics_module_options_reports_contract_issues(
    options: dict[str, object],
    expected_issue: str,
) -> None:
    """Validation should surface actionable errors for invalid analytics config."""
    assert expected_issue in validate_analytics_module_options(options)


def test_analytics_production_targeted_requires_enabled_valid_env_reference() -> None:
    """Production-targeted analytics should require an enabled valid env-var ref."""
    assert analytics_production_targeted({"enabled": False}) is False
    assert (
        analytics_production_targeted(
            {"posthog_api_key_env_var": "ops-posthog-api-key"}
        )
        is False
    )
    assert (
        analytics_production_targeted(
            {"posthog_api_key_env_var": "OPS_POSTHOG_API_KEY"}
        )
        is True
    )
