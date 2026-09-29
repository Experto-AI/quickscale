"""Contract tests for the analytics module's manifest-owned configuration.

The analytics option defaults, normalization, and validation are declared in
``quickscale_modules/analytics/module.yml`` and enforced through the shared
manifest engine; its CLI configurator is the one generic manifest-driven
configurator.  These tests pin that contract and the operator-facing
behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)

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


def _manifest():
    return load_module_manifest_with_fallback("analytics")


# ===========================================================================
# 1. Validation engine behaviour
# ===========================================================================


class TestAnalyticsValidation:
    """The shared engine enforces the manifest's declared constraints."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), None) == []

    def test_unknown_provider_is_refused(self) -> None:
        issues = collect_option_validation_issues(_manifest(), {"provider": "segment"})
        assert any(
            issue.option_name == "provider" and "posthog" in issue.message
            for issue in issues
        )

    @pytest.mark.parametrize(
        "bad_value", ["ops-posthog-api-key", "1INVALID", "posthog api key"]
    )
    def test_invalid_env_var_names_are_refused(self, bad_value: str) -> None:
        for option_name in ("posthog_api_key_env_var", "posthog_host_env_var"):
            issues = collect_option_validation_issues(
                _manifest(), {option_name: bad_value}
            )
            assert any(
                issue.option_name == option_name
                and "must match pattern" in issue.message
                for issue in issues
            )

    def test_blank_env_var_names_are_accepted(self) -> None:
        assert (
            validate_module_options(
                _manifest(),
                {"posthog_api_key_env_var": "", "posthog_host_env_var": "  "},
            )
            == []
        )

    @pytest.mark.parametrize("bad_value", ["https:///missing-host", "not a url", ""])
    def test_invalid_hosts_are_refused(self, bad_value: str) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"posthog_host": bad_value}
        )
        assert any(
            issue.option_name == "posthog_host"
            and "must match pattern" in issue.message
            for issue in issues
        )

    @pytest.mark.parametrize(
        "good_value",
        [
            "https://posthog.example.com/proxy",
            "http://localhost:8000",
            "eu.i.posthog.com",
            "//eu.i.posthog.com",
        ],
    )
    def test_supported_host_forms_are_accepted(self, good_value: str) -> None:
        assert validate_module_options(_manifest(), {"posthog_host": good_value}) == []

    @pytest.mark.parametrize("bad_value", ["yes", 1, 0])
    def test_non_boolean_flags_are_refused(self, bad_value: object) -> None:
        for option_name in (
            "enabled",
            "exclude_debug",
            "exclude_staff",
            "anonymous_by_default",
        ):
            issues = collect_option_validation_issues(
                _manifest(),
                {option_name: bad_value},
                supplied={option_name: bad_value},
            )
            assert any(
                issue.option_name == option_name and "boolean" in issue.message
                for issue in issues
            )

    def test_multiple_issues_are_collected(self) -> None:
        issues = collect_option_validation_issues(
            _manifest(),
            {
                "provider": "segment",
                "enabled": "yes",
                "posthog_api_key_env_var": "bad-name",
            },
            supplied={
                "provider": "segment",
                "enabled": "yes",
                "posthog_api_key_env_var": "bad-name",
            },
        )
        assert len(issues) >= 3


# ===========================================================================
# 2. Generic resolver behaviour
# ===========================================================================


class TestAnalyticsResolution:
    """The generic manifest resolver returns the manifest's canonical values."""

    def test_defaults_match_the_manifest(self) -> None:
        assert resolve_manifest_module_options("analytics") == _EXPECTED_DEFAULTS

    def test_overrides_replace_defaults(self) -> None:
        resolved = resolve_manifest_module_options("analytics", {"exclude_staff": True})
        expected = dict(_EXPECTED_DEFAULTS)
        expected["exclude_staff"] = True
        assert resolved == expected

    def test_provider_is_canonicalized(self) -> None:
        resolved = resolve_manifest_module_options(
            "analytics", {"provider": " PostHog "}
        )
        assert resolved["provider"] == "posthog"

    def test_env_var_names_are_stripped(self) -> None:
        resolved = resolve_manifest_module_options(
            "analytics",
            {
                "posthog_api_key_env_var": " CUSTOM_KEY ",
                "posthog_host_env_var": " CUSTOM_HOST ",
            },
        )
        assert resolved["posthog_api_key_env_var"] == "CUSTOM_KEY"
        assert resolved["posthog_host_env_var"] == "CUSTOM_HOST"

    def test_host_is_canonicalized(self) -> None:
        """A bare or slashed host resolves to the absolute form."""
        resolved = resolve_manifest_module_options(
            "analytics", {"posthog_host": " eu.i.posthog.com/ "}
        )
        assert resolved["posthog_host"] == "https://eu.i.posthog.com"


# ===========================================================================
# 3. CLI configurator behaviour
# ===========================================================================


class TestAnalyticsConfigurator:
    """The CLI configurator's prompts and defaults come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["analytics"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["analytics"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_kept(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["analytics"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"enabled": False, "exclude_staff": True},
        )
        assert config["enabled"] is False
        assert config["exclude_staff"] is True
        assert config["provider"] == "posthog"

    def test_undeclared_existing_keys_are_dropped(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["analytics"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"retired_key": "value"},
        )
        assert "retired_key" not in config
        assert config == _EXPECTED_DEFAULTS

    def test_existing_values_are_returned_in_canonical_form(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["analytics"]
        config = entry.configure(
            non_interactive=True,
            existing_config={
                "provider": " POSTHOG ",
                "posthog_api_key_env_var": "  CUSTOM_KEY  ",
            },
        )
        assert config["provider"] == "posthog"
        assert config["posthog_api_key_env_var"] == "CUSTOM_KEY"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_interactive_values_are_returned_in_canonical_form(
        self, mock_confirm, mock_prompt
    ) -> None:
        """A padded interactive answer is stored in its canonical form."""
        mock_confirm.side_effect = [True, True, False, True]
        mock_prompt.side_effect = [
            "POSTHOG",
            "  CUSTOM_KEY  ",
            "CUSTOM_HOST",
            " eu.i.posthog.com/ ",
        ]

        entry = MODULE_CONFIGURATOR_REGISTRY["analytics"]
        config = entry.configure(non_interactive=False)

        assert config["provider"] == "posthog"
        assert config["posthog_api_key_env_var"] == "CUSTOM_KEY"
        assert config["posthog_host_env_var"] == "CUSTOM_HOST"
        assert config["posthog_host"] == "https://eu.i.posthog.com"
        assert config["exclude_staff"] is False
