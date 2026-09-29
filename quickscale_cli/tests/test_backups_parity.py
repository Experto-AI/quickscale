"""Contract tests for the backups module's manifest-owned configuration.

The backups option defaults, normalization, validation, and retired keys are
declared in ``quickscale_modules/backups/module.yml`` and enforced through the
shared manifest engine; its CLI configurator is the one generic
manifest-driven configurator.  These tests pin that contract and the
operator-facing behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import click
import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)
from quickscale_core.manifest.option_validation import validate_module_options

_EXPECTED_DEFAULTS: dict[str, object] = {
    "retention_days": 14,
    "naming_prefix": "db",
    "target_mode": "local",
    "local_directory": ".quickscale/backups",
    "remote_bucket_name": "",
    "remote_prefix": "backups/private",
    "remote_endpoint_url": "",
    "remote_region_name": "",
    "remote_access_key_id_env_var": "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID",
    "remote_secret_access_key_env_var": "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY",
    "automation_enabled": False,
    "schedule": "0 2 * * *",
}

_ACCESS_KEY_OPTION = "remote_access_key_id_env_var"
_SECRET_KEY_OPTION = "remote_secret_access_key_env_var"
_RETIRED_OPTIONS = ("remote_access_key_id", "remote_secret_access_key")

_PRIVATE_REMOTE_OPTIONS: dict[str, object] = {
    "target_mode": "private_remote",
    "remote_bucket_name": "private-bucket",
    "remote_region_name": "eu-west-1",
}


def _manifest():
    return load_module_manifest_with_fallback("backups")


def _private_remote(**overrides: object) -> dict[str, object]:
    options = dict(_PRIVATE_REMOTE_OPTIONS)
    options.update(overrides)
    return options


# ===========================================================================
# 1. Manifest declarations
# ===========================================================================


class TestManifestDeclaration:
    """The manifest owns the option set, defaults, and declared rules."""

    def test_defaults_match_the_manifest(self) -> None:
        assert resolve_manifest_module_options("backups") == _EXPECTED_DEFAULTS

    def test_env_var_defaults_name_the_conventional_variables(self) -> None:
        defaults = _manifest().get_defaults()
        assert defaults[_ACCESS_KEY_OPTION] == "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
        assert (
            defaults[_SECRET_KEY_OPTION]
            == "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
        )

    def test_target_mode_choices_are_declared(self) -> None:
        option = _manifest().get_option("target_mode")
        assert option is not None
        assert option.validation.get("choices") == ["local", "private_remote"]

    def test_retention_minimum_is_declared(self) -> None:
        option = _manifest().get_option("retention_days")
        assert option is not None
        assert option.validation.get("min") == 1

    def test_remote_bucket_is_required_for_private_remote(self) -> None:
        option = _manifest().get_option("remote_bucket_name")
        assert option is not None
        assert option.validation.get("required_when") == {
            "target_mode": "private_remote"
        }

    def test_endpoint_or_region_is_declared_for_private_remote(self) -> None:
        option = _manifest().get_option("remote_endpoint_url")
        assert option is not None
        assert option.validation.get("required_when") == {
            "target_mode": "private_remote"
        }
        assert option.validation.get("any_of") == ["remote_region_name"]

    def test_schedule_required_when_automation_is_enabled(self) -> None:
        option = _manifest().get_option("schedule")
        assert option is not None
        assert option.validation.get("required_when") == {"automation_enabled": True}

    def test_env_var_patterns_are_declared(self) -> None:
        access_option = _manifest().get_option(_ACCESS_KEY_OPTION)
        secret_option = _manifest().get_option(_SECRET_KEY_OPTION)
        assert access_option is not None
        assert secret_option is not None
        access_pattern = access_option.validation.get("pattern", "")
        # The access-key option keeps the literal-AWS-key guard in its pattern.
        assert "AKIA" in access_pattern and "ASIA" in access_pattern
        assert secret_option.validation.get("pattern") == "^(?:[A-Z][A-Z0-9_]*)?$"

    def test_retired_raw_secret_keys_are_declared(self) -> None:
        retired = _manifest().retired_options
        assert set(retired) == set(_RETIRED_OPTIONS)
        assert "remote_access_key_id_env_var" in retired["remote_access_key_id"]
        assert "remote_secret_access_key_env_var" in retired["remote_secret_access_key"]

    def test_normalization_rules_are_declared(self) -> None:
        derivations = _manifest().option_derivations
        target_rules = [
            rule["rule_type"]
            for rule in derivations["target_mode"]["normalization_rules"]
        ]
        assert target_rules == ["strip", "lowercase"]
        prefix_rules = [
            rule["rule_type"]
            for rule in derivations["naming_prefix"]["normalization_rules"]
        ]
        assert prefix_rules == ["strip"]

    @pytest.mark.parametrize(
        "option_name", ["naming_prefix", "local_directory", "remote_prefix"]
    )
    def test_blank_guards_are_declared(self, option_name: str) -> None:
        option = _manifest().get_option(option_name)
        assert option is not None
        assert option.validation.get("pattern") == "(?s)^.*\\S.*$"


# ===========================================================================
# 2. Resolution through the generic resolver
# ===========================================================================


class TestBackupsResolution:
    """The generic resolver merges defaults with canonicalized overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        assert resolve_manifest_module_options("backups") == _EXPECTED_DEFAULTS

    def test_retention_override_wins(self) -> None:
        resolved = resolve_manifest_module_options("backups", {"retention_days": 30})
        assert resolved["retention_days"] == 30
        assert resolved["naming_prefix"] == "db"

    def test_target_mode_is_stripped_and_lowercased(self) -> None:
        resolved = resolve_manifest_module_options(
            "backups", {"target_mode": " Private_Remote "}
        )
        assert resolved["target_mode"] == "private_remote"

    def test_free_text_values_are_stripped(self) -> None:
        resolved = resolve_manifest_module_options(
            "backups", {"naming_prefix": "  nightlies  ", "remote_prefix": " b/ "}
        )
        assert resolved["naming_prefix"] == "nightlies"
        assert resolved["remote_prefix"] == "b/"

    def test_invalid_values_pass_through_resolution(self) -> None:
        """Resolution does not coerce invalid values; validation refuses them."""
        resolved = resolve_manifest_module_options(
            "backups", {"retention_days": 0, "target_mode": "elsewhere"}
        )
        assert resolved["retention_days"] == 0
        assert resolved["target_mode"] == "elsewhere"

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_manifest_module_options(
            "backups", {"naming_prefix": "  db  "}
        )
        assert resolve_manifest_module_options("backups", resolved) == resolved

    def test_resolved_keys_match_the_manifest(self) -> None:
        resolved = resolve_manifest_module_options("backups", {"retention_days": 7})
        assert set(resolved.keys()) == set(_EXPECTED_DEFAULTS.keys())


# ===========================================================================
# 3. Validation through the shared engine
# ===========================================================================


class TestBackupsValidation:
    """The engine enforces the manifest's single- and cross-option rules."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), _EXPECTED_DEFAULTS) == []

    def test_private_remote_requires_the_remote_credentials(self) -> None:
        issues = validate_module_options(_manifest(), {"target_mode": "private_remote"})
        assert any("remote_bucket_name" in issue for issue in issues)
        assert any("one of" in issue for issue in issues)

    def test_private_remote_with_bucket_and_region_passes(self) -> None:
        assert validate_module_options(_manifest(), _private_remote()) == []

    def test_private_remote_with_bucket_and_endpoint_passes(self) -> None:
        options = {
            "target_mode": "private_remote",
            "remote_bucket_name": "bucket",
            "remote_endpoint_url": "https://s3.example.com",
        }
        assert validate_module_options(_manifest(), options) == []

    def test_private_remote_requires_env_var_references_when_blank(self) -> None:
        options = _private_remote(**{_ACCESS_KEY_OPTION: "", _SECRET_KEY_OPTION: ""})
        issues = validate_module_options(_manifest(), options)
        assert any(_ACCESS_KEY_OPTION in issue for issue in issues)
        assert any(_SECRET_KEY_OPTION in issue for issue in issues)

    def test_retention_below_minimum_fails(self) -> None:
        issues = validate_module_options(_manifest(), {"retention_days": 0})
        assert any("retention_days" in issue for issue in issues)

    def test_invalid_target_mode_fails(self) -> None:
        issues = validate_module_options(_manifest(), {"target_mode": "elsewhere"})
        assert any("target_mode" in issue for issue in issues)

    @pytest.mark.parametrize(
        "option_name", ["naming_prefix", "local_directory", "remote_prefix"]
    )
    def test_blank_free_text_values_fail(self, option_name: str) -> None:
        issues = validate_module_options(_manifest(), {option_name: "   "})
        assert any(option_name in issue for issue in issues)

    def test_schedule_required_when_automation_is_enabled(self) -> None:
        options = {"automation_enabled": True, "schedule": ""}
        issues = validate_module_options(_manifest(), options)
        assert any("schedule" in issue for issue in issues)

    def test_invalid_env_var_name_fails(self) -> None:
        issues = validate_module_options(
            _manifest(), {_ACCESS_KEY_OPTION: "not-valid-env"}
        )
        assert any("must match pattern" in issue for issue in issues)

    def test_literal_aws_access_key_id_is_refused(self) -> None:
        issues = validate_module_options(
            _manifest(), {_ACCESS_KEY_OPTION: "AKIAFAKEACCESSKEY123"}
        )
        assert len(issues) == 1
        assert "must match pattern" in issues[0]

    def test_secret_option_accepts_an_aws_shaped_name(self) -> None:
        """The literal-key guard applies to the access-key option only."""
        assert (
            validate_module_options(
                _manifest(), {_SECRET_KEY_OPTION: "AKIAFAKEACCESSKEY123"}
            )
            == []
        )

    @pytest.mark.parametrize("retired_key", _RETIRED_OPTIONS)
    def test_retired_raw_secret_keys_are_refused(self, retired_key: str) -> None:
        issues = validate_module_options(_manifest(), {retired_key: "raw-secret"})
        assert len(issues) == 1
        assert "no longer supported" in issues[0]
        assert f"'{retired_key}'" in issues[0]

    def test_retired_key_is_reported_before_other_issues(self) -> None:
        options = {"remote_access_key_id": "raw", "retention_days": 0}
        issues = validate_module_options(_manifest(), options)
        assert "no longer supported" in issues[0]


# ===========================================================================
# 4. CLI configurator behaviour
# ===========================================================================


class TestBackupsConfigurator:
    """The CLI configurator's defaults and prompts come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["backups"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["backups"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_canonicalized(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["backups"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"target_mode": " LOCAL ", "retention_days": 7},
        )
        assert config["target_mode"] == "local"
        assert config["retention_days"] == 7
        assert config["naming_prefix"] == "db"

    def test_existing_retired_key_aborts(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["backups"]
        with pytest.raises(click.Abort):
            entry.configure(
                non_interactive=True,
                existing_config={"remote_access_key_id": "raw"},
            )

    @patch("quickscale_cli.commands.module_config.click.confirm")
    @patch("quickscale_cli.commands.module_config.click.prompt")
    def test_interactive_prompts_read_the_manifest(
        self, mock_prompt, mock_confirm
    ) -> None:
        def _answer(message: str, **kwargs: object) -> object:
            prompt_type = kwargs.get("type")
            choices = getattr(prompt_type, "choices", [])
            if "private_remote" in choices:
                return "private_remote"
            if message.startswith("Private S3-compatible bucket"):
                return "private-bucket"
            if message.startswith("Cloud provider region"):
                return "eu-west-1"
            return kwargs.get("default")

        mock_prompt.side_effect = _answer
        mock_confirm.return_value = False

        entry = MODULE_CONFIGURATOR_REGISTRY["backups"]
        config = entry.configure(non_interactive=False)

        assert config["target_mode"] == "private_remote"
        assert config["remote_bucket_name"] == "private-bucket"
        assert config["remote_region_name"] == "eu-west-1"

        choice_types = [
            call.kwargs["type"]
            for call in mock_prompt.call_args_list
            if hasattr(call.kwargs.get("type"), "choices")
        ]
        assert len(choice_types) == 1
        assert list(choice_types[0].choices) == ["local", "private_remote"]
