"""Contract tests for the forms module's manifest-owned configuration.

The forms module's option defaults, normalization, and validation are declared
in ``quickscale_modules/forms/module.yml`` and enforced through the shared
manifest engine; the CLI configurator reads the manifest.  These tests pin that
contract — including the legacy hardcoded defaults it replaced — and the
operator-facing behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_cli.commands.plan_command import _configure_selected_modules
from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest.entry_point import build_generic_manifest_spec
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)
from quickscale_core.schema.config_schema import ConfigValidationError, validate_config

_EXPECTED_DEFAULTS: dict[str, object] = {
    "submissions_per_page": 25,
    "spam_protection_enabled": True,
    "rate_limit": "5/hour",
    "retention_days": 365,
    "api_enabled": True,
}

_RETIRED_OPTION_MESSAGES: dict[str, str] = {
    "forms_per_page": (
        "Legacy config key 'forms_per_page' is no longer supported. Use "
        "'submissions_per_page' instead."
    ),
    "data_retention_days": (
        "Legacy config key 'data_retention_days' is no longer supported. Use "
        "'retention_days' instead."
    ),
    "submissions_api_enabled": (
        "Legacy config key 'submissions_api_enabled' is no longer supported. Use "
        "'api_enabled' instead."
    ),
}


def _manifest():
    return load_module_manifest_with_fallback("forms")


# ===========================================================================
# 1. Manifest contract
# ===========================================================================


class TestFormsManifestContract:
    """The manifest declares the defaults, settings, and constraints."""

    def test_manifest_declares_exactly_the_contract_options(self) -> None:
        assert set(_manifest().get_defaults()) == set(_EXPECTED_DEFAULTS)

    def test_manifest_defaults_match_the_legacy_contract(self) -> None:
        assert _manifest().get_defaults() == _EXPECTED_DEFAULTS

    def test_django_settings_are_declared(self) -> None:
        manifest = _manifest()
        assert (
            manifest.get_option("submissions_per_page").django_setting
            == "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE"
        )
        assert (
            manifest.get_option("spam_protection_enabled").django_setting
            == "QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED"
        )
        assert (
            manifest.get_option("rate_limit").django_setting
            == "QUICKSCALE_FORMS_RATE_LIMIT"
        )
        assert (
            manifest.get_option("retention_days").django_setting
            == "QUICKSCALE_FORMS_RETENTION_DAYS"
        )
        assert (
            manifest.get_option("api_enabled").django_setting
            == "QUICKSCALE_FORMS_API_ENABLED"
        )

    def test_manifest_declares_the_option_types(self) -> None:
        manifest = _manifest()
        assert manifest.get_option("submissions_per_page").option_type == "integer"
        assert manifest.get_option("spam_protection_enabled").option_type == "boolean"
        assert manifest.get_option("rate_limit").option_type == "string"
        assert manifest.get_option("retention_days").option_type == "integer"
        assert manifest.get_option("api_enabled").option_type == "boolean"


# ===========================================================================
# 2. Validation engine behaviour
# ===========================================================================


class TestFormsValidation:
    """The shared engine enforces the manifest's declared constraints."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), None) == []

    def test_valid_overrides_pass_validation(self) -> None:
        assert (
            validate_module_options(
                _manifest(),
                {
                    "submissions_per_page": 50,
                    "spam_protection_enabled": False,
                    "rate_limit": "10/minute",
                    "retention_days": 30,
                    "api_enabled": False,
                },
            )
            == []
        )

    @pytest.mark.parametrize("bad_value", [0, -5])
    def test_non_positive_forms_per_page_is_refused(self, bad_value: int) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"submissions_per_page": bad_value}
        )
        assert any(
            issue.option_name == "submissions_per_page"
            and "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE" in issue.message
            for issue in issues
        )

    def test_negative_retention_days_is_refused(self) -> None:
        issues = collect_option_validation_issues(_manifest(), {"retention_days": -1})
        assert any(
            issue.option_name == "retention_days"
            and "QUICKSCALE_FORMS_RETENTION_DAYS" in issue.message
            for issue in issues
        )

    def test_zero_retention_days_is_valid(self) -> None:
        """0 means keep forever, which is a valid value."""
        assert validate_module_options(_manifest(), {"retention_days": 0}) == []

    @pytest.mark.parametrize("bad_value", ["invalid", "5/week", "", "  "])
    def test_invalid_rate_limit_is_refused(self, bad_value: str) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"rate_limit": bad_value}
        )
        assert any(issue.option_name == "rate_limit" for issue in issues)

    @pytest.mark.parametrize("rate", ["1/second", "10/minute", "5/hour", "100/day"])
    def test_valid_rate_limit_formats_pass(self, rate: str) -> None:
        assert validate_module_options(_manifest(), {"rate_limit": rate}) == []

    def test_multiple_issues_collected(self) -> None:
        issues = collect_option_validation_issues(
            _manifest(),
            {
                "submissions_per_page": 0,
                "retention_days": -1,
                "rate_limit": "bad",
            },
        )
        assert {issue.option_name for issue in issues} >= {
            "submissions_per_page",
            "retention_days",
            "rate_limit",
        }


class TestFormsRetiredOptions:
    """The renamed option keys are refused from their manifest declarations."""

    def test_manifest_declares_the_retired_keys(self) -> None:
        assert _manifest().retired_options == _RETIRED_OPTION_MESSAGES

    @pytest.mark.parametrize("retired_key", sorted(_RETIRED_OPTION_MESSAGES))
    def test_engine_reports_the_retired_key_with_the_declared_message(
        self, retired_key: str
    ) -> None:
        issues = collect_option_validation_issues(_manifest(), {retired_key: 1})
        assert [(issue.option_name, issue.message) for issue in issues] == [
            (retired_key, _RETIRED_OPTION_MESSAGES[retired_key])
        ]

    def test_config_load_refuses_the_retired_retention_key(self) -> None:
        yaml_content = (
            'version: "1"\n'
            "project:\n"
            "  slug: demo\n"
            "  package: demo\n"
            "modules:\n"
            "  forms:\n"
            "    data_retention_days: 30\n"
        )

        with pytest.raises(ConfigValidationError) as excinfo:
            validate_config(yaml_content)

        assert "data_retention_days" in str(excinfo.value)
        assert "retention_days" in str(excinfo.value)


# ===========================================================================
# 3. Normalization and settings projection
# ===========================================================================


class TestFormsProjection:
    """Canonical values and their Django-settings projection stay pinned."""

    def test_rate_limit_override_is_stripped(self) -> None:
        from quickscale_core.manifest.resolver import normalize_module_option_values

        normalized = normalize_module_option_values(
            _manifest(), {"rate_limit": " 20/hour "}
        )
        assert normalized["rate_limit"] == "20/hour"

    def test_declared_defaults_project_to_settings(self) -> None:
        assert build_generic_manifest_spec("forms", None).settings == {
            "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE": 25,
            "QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED": True,
            "QUICKSCALE_FORMS_RATE_LIMIT": "5/hour",
            "QUICKSCALE_FORMS_RETENTION_DAYS": 365,
            "QUICKSCALE_FORMS_API_ENABLED": True,
        }

    def test_overrides_project_to_settings(self) -> None:
        assert build_generic_manifest_spec(
            "forms",
            {
                "submissions_per_page": 50,
                "spam_protection_enabled": False,
                "rate_limit": "10/minute",
                "retention_days": 90,
                "api_enabled": False,
            },
        ).settings == {
            "QUICKSCALE_FORMS_SUBMISSIONS_PER_PAGE": 50,
            "QUICKSCALE_FORMS_SPAM_PROTECTION_ENABLED": False,
            "QUICKSCALE_FORMS_RATE_LIMIT": "10/minute",
            "QUICKSCALE_FORMS_RETENTION_DAYS": 90,
            "QUICKSCALE_FORMS_API_ENABLED": False,
        }


# ===========================================================================
# 4. CLI configurator behaviour
# ===========================================================================


class TestFormsConfigurator:
    """The CLI configurator's prompts and defaults come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["forms"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["forms"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_kept(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["forms"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"submissions_per_page": 40, "rate_limit": " 10/minute "},
        )
        assert config["submissions_per_page"] == 40
        assert config["rate_limit"] == "10/minute"
        assert config["retention_days"] == 365

    def test_undeclared_existing_keys_are_dropped(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["forms"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"retired_key": "value"},
        )
        assert config == _EXPECTED_DEFAULTS

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_interactive_values_are_returned_canonical(
        self, mock_confirm, mock_prompt
    ) -> None:
        mock_confirm.side_effect = [False, False]
        mock_prompt.side_effect = [40, "  10/minute  ", 30]

        entry = MODULE_CONFIGURATOR_REGISTRY["forms"]
        config = entry.configure(non_interactive=False)

        assert config == {
            "submissions_per_page": 40,
            "spam_protection_enabled": False,
            "rate_limit": "10/minute",
            "retention_days": 30,
            "api_enabled": False,
        }

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_planner_persists_the_canonical_rate(
        self, mock_confirm, mock_prompt
    ) -> None:
        """The planner's own output carries the canonical rate limit."""
        mock_confirm.side_effect = [True, True]
        mock_prompt.side_effect = [40, "  10/minute  ", 30]

        configured = _configure_selected_modules(
            ["forms"],
            {},
            new_modules=None,
            allow_reconfigure_existing=False,
        )

        assert configured["forms"]["rate_limit"] == "10/minute"
        assert configured["forms"]["submissions_per_page"] == 40
