"""Manifest-declaration tests for the analytics module's option contract.

The analytics ``module.yml`` is the single source of the module's option
defaults, Django-setting projections, normalization rules, and validation.
The module-root manifest is loaded directly so the declaration is tested
where module authors write it.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from quickscale_core.contracts.module_options import (
    ANALYTICS_EVENT_PAGEVIEW,
    ANALYTICS_POSTHOG_DEFAULT_HOST,
    ANALYTICS_POSTHOG_EU_HOST,
    ANALYTICS_PROVIDER_POSTHOG,
    ANALYTICS_PROVIDERS,
)
from quickscale_core.manifest.loader import load_manifest_from_path

REPO_ROOT = Path(__file__).resolve().parents[2]
ANALYTICS_MANIFEST_PATH = REPO_ROOT / "quickscale_modules" / "analytics" / "module.yml"

_EXPECTED_DEFAULTS: dict[str, object] = {
    "enabled": True,
    "provider": "posthog",
    "posthog_api_key_env_var": "POSTHOG_API_KEY",
    "posthog_host_env_var": "POSTHOG_HOST",
    "posthog_host": "https://us.i.posthog.com",
    "exclude_debug": True,
    "exclude_staff": False,
    "anonymous_by_default": True,
}

_EXPECTED_SETTINGS: dict[str, str] = {
    "enabled": "QUICKSCALE_ANALYTICS_ENABLED",
    "provider": "QUICKSCALE_ANALYTICS_PROVIDER",
    "posthog_api_key_env_var": "QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR",
    "posthog_host_env_var": "QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR",
    "posthog_host": "QUICKSCALE_ANALYTICS_POSTHOG_HOST",
    "exclude_debug": "QUICKSCALE_ANALYTICS_EXCLUDE_DEBUG",
    "exclude_staff": "QUICKSCALE_ANALYTICS_EXCLUDE_STAFF",
    "anonymous_by_default": "QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT",
}


def _load_analytics_manifest() -> Any:
    return load_manifest_from_path(ANALYTICS_MANIFEST_PATH)


# ===========================================================================
# 1. Manifest declaration
# ===========================================================================


class TestAnalyticsManifestDeclaration:
    """The manifest declares the defaults, settings, and checks."""

    def test_manifest_declares_exactly_the_contract_options(self) -> None:
        manifest = _load_analytics_manifest()
        assert set(manifest.get_defaults()) == set(_EXPECTED_DEFAULTS)

    def test_manifest_defaults_match_contract(self) -> None:
        assert _load_analytics_manifest().get_defaults() == _EXPECTED_DEFAULTS

    def test_manifest_declares_every_django_setting(self) -> None:
        manifest = _load_analytics_manifest()
        for option_name, setting_name in _EXPECTED_SETTINGS.items():
            option = manifest.get_option(option_name)
            assert option is not None
            assert option.django_setting == setting_name

    def test_manifest_declares_the_option_types(self) -> None:
        manifest = _load_analytics_manifest()
        assert manifest.get_option("enabled").option_type == "boolean"
        assert manifest.get_option("provider").option_type == "string"
        for option_name in (
            "posthog_api_key_env_var",
            "posthog_host_env_var",
            "posthog_host",
            "exclude_debug",
            "exclude_staff",
            "anonymous_by_default",
        ):
            option = manifest.get_option(option_name)
            assert option is not None
        assert manifest.get_option("exclude_debug").option_type == "boolean"

    def test_manifest_declares_provider_choices(self) -> None:
        option = _load_analytics_manifest().get_option("provider")
        assert option is not None
        assert option.validation.get("choices") == ["posthog"]

    def test_manifest_declares_env_var_name_patterns(self) -> None:
        manifest = _load_analytics_manifest()
        for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
            option = manifest.get_option(option_name)
            assert option is not None
            assert option.validation.get("pattern") == "^(?:[A-Z][A-Z0-9_]*)?$"

    def test_manifest_declares_the_host_pattern(self) -> None:
        option = _load_analytics_manifest().get_option("posthog_host")
        assert option is not None
        assert option.validation.get("pattern") == (
            "^(?:https?://[^\\s/?#][^\\s]*|"
            "(?![A-Za-z][A-Za-z0-9+.-]*://)[^\\s/?#][^\\s]*)$"
        )

    def test_manifest_declares_normalization_rules(self) -> None:
        manifest = _load_analytics_manifest()
        provider_rules = manifest.option_derivations["provider"]["normalization_rules"]
        assert [rule["rule_type"] for rule in provider_rules] == ["strip", "lowercase"]
        for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
            rules = manifest.option_derivations[option_name]["normalization_rules"]
            assert [rule["rule_type"] for rule in rules] == ["strip"]
        host_rules = manifest.option_derivations["posthog_host"]["normalization_rules"]
        assert [rule["rule_type"] for rule in host_rules] == ["url"]


# ===========================================================================
# 2. Public constants
# ===========================================================================


class TestAnalyticsPublicConstants:
    """Non-option provider metadata stays stable for docs and adapters."""

    def test_provider_constants_are_stable(self) -> None:
        assert ANALYTICS_PROVIDER_POSTHOG == "posthog"
        assert ANALYTICS_PROVIDERS == ("posthog",)

    def test_host_constants_are_stable(self) -> None:
        assert ANALYTICS_POSTHOG_DEFAULT_HOST == "https://us.i.posthog.com"
        assert ANALYTICS_POSTHOG_EU_HOST == "https://eu.i.posthog.com"

    def test_event_name_constants_are_stable(self) -> None:
        assert ANALYTICS_EVENT_PAGEVIEW == "$pageview"

    def test_core_contract_names_no_feature_events(self) -> None:
        """Feature event names belong to their sending modules (rule 22)."""
        from quickscale_core.contracts import module_options

        assert "ANALYTICS_EVENT_FORM_SUBMIT" not in module_options.__all__
        assert "ANALYTICS_EVENT_SOCIAL_LINK_CLICK" not in module_options.__all__
