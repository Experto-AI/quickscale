"""Contract tests for the CRM module's manifest-owned configuration.

The CRM module's option defaults, normalization, validation, and its retired
``default_pipeline_stages`` refusal are declared in
``quickscale_modules/crm/module.yml`` and enforced through the shared manifest
engine; the CLI configurator reads the manifest.  These tests pin that
contract and the operator-facing behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import click
import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_core.contracts.resolvers import load_module_manifest_with_fallback
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)
from quickscale_core.schema.config_schema import ConfigValidationError, validate_config

_EXPECTED_DEFAULTS: dict[str, object] = {
    "enabled": True,
    "api_enabled": True,
    "deals_per_page": 25,
    "contacts_per_page": 50,
}

_RETIRED_MESSAGE = (
    "Legacy config key 'default_pipeline_stages' is no longer supported. "
    "Remove it from the CRM module options."
)

_RETIRED_ENABLE_API_MESSAGE = (
    "Legacy config key 'enable_api' is no longer supported. Use 'api_enabled' instead."
)


def _manifest():
    return load_module_manifest_with_fallback("crm")


# ===========================================================================
# 1. Manifest contract
# ===========================================================================


class TestCrmManifestContract:
    """The manifest declares the defaults, settings, and constraints."""

    def test_manifest_declares_exactly_the_contract_options(self) -> None:
        assert set(_manifest().get_defaults()) == set(_EXPECTED_DEFAULTS)

    def test_manifest_defaults_match_contract(self) -> None:
        assert _manifest().get_defaults() == _EXPECTED_DEFAULTS

    def test_django_settings_are_declared(self) -> None:
        manifest = _manifest()
        assert (
            manifest.get_option("api_enabled").django_setting
            == "QUICKSCALE_CRM_API_ENABLED"
        )
        assert (
            manifest.get_option("deals_per_page").django_setting
            == "QUICKSCALE_CRM_DEALS_PER_PAGE"
        )
        assert (
            manifest.get_option("contacts_per_page").django_setting
            == "QUICKSCALE_CRM_CONTACTS_PER_PAGE"
        )

    def test_manifest_declares_the_option_types(self) -> None:
        manifest = _manifest()
        assert manifest.get_option("api_enabled").option_type == "boolean"
        assert manifest.get_option("deals_per_page").option_type == "integer"
        assert manifest.get_option("contacts_per_page").option_type == "integer"


# ===========================================================================
# 2. Validation engine behaviour
# ===========================================================================


class TestCrmValidation:
    """The shared engine enforces the manifest's declared constraints."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), None) == []

    def test_empty_overrides_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), {}) == []

    def test_valid_overrides_pass_validation(self) -> None:
        assert (
            validate_module_options(
                _manifest(),
                {
                    "api_enabled": False,
                    "deals_per_page": 10,
                    "contacts_per_page": 100,
                },
            )
            == []
        )

    @pytest.mark.parametrize("bad_value", [0, -1, -100])
    def test_non_positive_deals_per_page_is_refused(self, bad_value: int) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"deals_per_page": bad_value}
        )
        assert any(
            issue.option_name == "deals_per_page"
            and "QUICKSCALE_CRM_DEALS_PER_PAGE" in issue.message
            for issue in issues
        )

    @pytest.mark.parametrize("bad_value", [0, -1, -100])
    def test_non_positive_contacts_per_page_is_refused(self, bad_value: int) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"contacts_per_page": bad_value}
        )
        assert any(
            issue.option_name == "contacts_per_page"
            and "QUICKSCALE_CRM_CONTACTS_PER_PAGE" in issue.message
            for issue in issues
        )

    def test_non_boolean_enable_api_is_refused(self) -> None:
        issues = collect_option_validation_issues(
            _manifest(),
            {"api_enabled": "yes"},
            supplied={"api_enabled": "yes"},
        )
        assert any(
            issue.option_name == "api_enabled" and "boolean" in issue.message
            for issue in issues
        )


# ===========================================================================
# 3. Retired-option refusal
# ===========================================================================


class TestCrmRetiredOption:
    """``default_pipeline_stages`` is refused from its manifest declaration."""

    def test_manifest_declares_the_retired_key(self) -> None:
        assert _manifest().retired_options == {
            "default_pipeline_stages": _RETIRED_MESSAGE,
            "enable_api": _RETIRED_ENABLE_API_MESSAGE,
        }

    def test_engine_reports_the_retired_enable_api_key(self) -> None:
        issues = collect_option_validation_issues(_manifest(), {"enable_api": True})
        assert [(issue.option_name, issue.message) for issue in issues] == [
            ("enable_api", _RETIRED_ENABLE_API_MESSAGE)
        ]

    def test_config_load_refuses_the_retired_enable_api_key(self) -> None:
        yaml_content = (
            'version: "1"\n'
            "project:\n"
            "  slug: demo\n"
            "  package: demo\n"
            "modules:\n"
            "  crm:\n"
            "    enable_api: true\n"
        )

        with pytest.raises(ConfigValidationError) as excinfo:
            validate_config(yaml_content)

        assert "enable_api" in str(excinfo.value)
        assert "api_enabled" in str(excinfo.value)

    def test_state_sanitization_refuses_the_retired_enable_api_key(self) -> None:
        from quickscale_core.contracts.module_options import sanitize_module_options

        with pytest.raises(ConfigValidationError) as excinfo:
            sanitize_module_options("crm", {"enable_api": True})

        assert _RETIRED_ENABLE_API_MESSAGE in str(excinfo.value)

    def test_engine_reports_the_retired_key_with_the_declared_message(self) -> None:
        issues = collect_option_validation_issues(
            _manifest(), {"default_pipeline_stages": ["lead"]}
        )
        assert [(issue.option_name, issue.message) for issue in issues] == [
            ("default_pipeline_stages", _RETIRED_MESSAGE)
        ]

    def test_config_load_refuses_the_retired_key(self) -> None:
        yaml_content = (
            'version: "1"\n'
            "project:\n"
            "  slug: demo\n"
            "  package: demo\n"
            "modules:\n"
            "  crm:\n"
            "    default_pipeline_stages:\n"
            "      - lead\n"
        )

        with pytest.raises(ConfigValidationError) as excinfo:
            validate_config(yaml_content)

        assert "default_pipeline_stages" in str(excinfo.value)

    def test_state_sanitization_refuses_the_retired_key(self) -> None:
        from quickscale_core.contracts.module_options import sanitize_module_options

        with pytest.raises(ConfigValidationError) as excinfo:
            sanitize_module_options("crm", {"default_pipeline_stages": ["lead"]})

        assert _RETIRED_MESSAGE in str(excinfo.value)


# ===========================================================================
# 4. CLI configurator behaviour
# ===========================================================================


class TestCrmConfigurator:
    """The CLI configurator's prompts and defaults come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["crm"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["crm"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_kept(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["crm"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"deals_per_page": 10, "contacts_per_page": 100},
        )
        assert config["deals_per_page"] == 10
        assert config["contacts_per_page"] == 100
        assert config["api_enabled"] is True

    def test_undeclared_existing_keys_are_dropped(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["crm"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"not_an_option": "value"},
        )
        assert config == _EXPECTED_DEFAULTS

    def test_retired_existing_key_is_refused(self) -> None:
        """A retired key in existing config is refused, never silently dropped."""
        entry = MODULE_CONFIGURATOR_REGISTRY["crm"]

        with pytest.raises(click.Abort):
            entry.configure(
                non_interactive=True,
                existing_config={"default_pipeline_stages": ["lead"]},
            )

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_interactive_values_are_returned_canonical(
        self, mock_confirm, mock_prompt
    ) -> None:
        mock_confirm.return_value = False
        mock_prompt.side_effect = [30, 100]

        entry = MODULE_CONFIGURATOR_REGISTRY["crm"]
        config = entry.configure(non_interactive=False)

        assert config == {
            "enabled": False,
            "api_enabled": False,
            "deals_per_page": 30,
            "contacts_per_page": 100,
        }
