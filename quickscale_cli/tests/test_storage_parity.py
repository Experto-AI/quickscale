"""Contract tests for the storage module's manifest-owned configuration.

The storage option defaults, normalization, validation, and retired keys are
declared in ``quickscale_modules/storage/module.yml`` and enforced through the
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

_ACCESS_KEY_OPTION = "access_key_id_env_var"
_SECRET_KEY_OPTION = "secret_access_key_env_var"
_RETIRED_OPTIONS = ("access_key_id", "secret_access_key")

_EXPECTED_DEFAULTS: dict[str, object] = {
    "enabled": True,
    "backend": "local",
    "media_url": "/media/",
    "public_base_url": "",
    "bucket_name": "",
    "endpoint_url": "",
    "region_name": "",
    _ACCESS_KEY_OPTION: "AWS_ACCESS_KEY_ID",
    _SECRET_KEY_OPTION: "AWS_SECRET_ACCESS_KEY",
    "default_acl": "",
    "querystring_auth": False,
    "private_media_enabled": False,
}

_CLOUD_OPTIONS: dict[str, object] = {
    "backend": "s3",
    "bucket_name": "bucket",
    "region_name": "us-east-1",
}


def _manifest():
    return load_module_manifest_with_fallback("storage")


def _cloud(**overrides: object) -> dict[str, object]:
    options = dict(_CLOUD_OPTIONS)
    options.update(overrides)
    return options


# ===========================================================================
# 1. Manifest declarations
# ===========================================================================


class TestManifestDeclaration:
    """The manifest owns the option set, defaults, and declared rules."""

    def test_defaults_match_the_manifest(self) -> None:
        assert resolve_manifest_module_options("storage") == _EXPECTED_DEFAULTS

    def test_immutable_private_media_default_is_declared(self) -> None:
        assert _EXPECTED_DEFAULTS["private_media_enabled"] is False
        assert (
            resolve_manifest_module_options("storage")["private_media_enabled"] is False
        )

    def test_backend_choices_are_declared(self) -> None:
        option = _manifest().get_option("backend")
        assert option is not None
        assert option.validation.get("choices") == ["local", "s3", "r2"]

    def test_credential_requiredness_is_declared_for_cloud_backends(self) -> None:
        for option_name in (_ACCESS_KEY_OPTION, _SECRET_KEY_OPTION):
            option = _manifest().get_option(option_name)
            assert option is not None
            assert option.validation.get("required_when") == {"backend": ["s3", "r2"]}

    def test_env_var_patterns_are_declared(self) -> None:
        access_option = _manifest().get_option(_ACCESS_KEY_OPTION)
        secret_option = _manifest().get_option(_SECRET_KEY_OPTION)
        assert access_option is not None
        assert secret_option is not None
        access_pattern = access_option.validation.get("pattern", "")
        # The access-key option keeps the literal-AWS-key guard in its pattern.
        assert "AKIA" in access_pattern and "ASIA" in access_pattern
        assert secret_option.validation.get("pattern") == "^(?:[A-Z][A-Z0-9_]*)?$"

    def test_retired_raw_credential_and_domain_keys_are_declared(self) -> None:
        retired = _manifest().retired_options
        assert set(retired) == {*_RETIRED_OPTIONS, "custom_domain"}
        assert "access_key_id_env_var" in retired["access_key_id"]
        assert "secret_access_key_env_var" in retired["secret_access_key"]
        assert "public_base_url" in retired["custom_domain"]

    def test_normalization_rules_are_declared(self) -> None:
        derivations = _manifest().option_derivations
        backend_rules = [
            rule["rule_type"] for rule in derivations["backend"]["normalization_rules"]
        ]
        assert backend_rules == ["strip", "lowercase"]
        for option_name in (
            "media_url",
            "public_base_url",
            "bucket_name",
            "endpoint_url",
            "region_name",
            "default_acl",
            _ACCESS_KEY_OPTION,
            _SECRET_KEY_OPTION,
        ):
            rules = [
                rule["rule_type"]
                for rule in derivations[option_name]["normalization_rules"]
            ]
            assert rules == ["strip"], option_name


# ===========================================================================
# 2. Resolution through the generic resolver
# ===========================================================================


class TestStorageResolution:
    """The generic resolver merges defaults with canonicalized overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        assert resolve_manifest_module_options("storage") == _EXPECTED_DEFAULTS

    def test_resolved_keys_match_the_manifest(self) -> None:
        resolved = resolve_manifest_module_options("storage", {"backend": "s3"})
        assert set(resolved.keys()) == set(_EXPECTED_DEFAULTS.keys())

    def test_backend_is_stripped_and_lowercased(self) -> None:
        resolved = resolve_manifest_module_options("storage", {"backend": "  S3  "})
        assert resolved["backend"] == "s3"

    def test_free_text_values_are_stripped(self) -> None:
        resolved = resolve_manifest_module_options(
            "storage",
            {
                "bucket_name": "  my-bucket  ",
                "endpoint_url": "  https://s3.example.com  ",
                "region_name": "  us-east-1  ",
                "default_acl": "  public-read  ",
                _ACCESS_KEY_OPTION: "  AWS_MY_ACCESS_KEY_ID  ",
                _SECRET_KEY_OPTION: "  AWS_MY_SECRET_ACCESS_KEY  ",
            },
        )
        assert resolved["bucket_name"] == "my-bucket"
        assert resolved["endpoint_url"] == "https://s3.example.com"
        assert resolved["region_name"] == "us-east-1"
        assert resolved["default_acl"] == "public-read"
        assert resolved[_ACCESS_KEY_OPTION] == "AWS_MY_ACCESS_KEY_ID"
        assert resolved[_SECRET_KEY_OPTION] == "AWS_MY_SECRET_ACCESS_KEY"

    def test_invalid_backend_passes_through_resolution(self) -> None:
        """Resolution does not coerce invalid values; validation refuses them."""
        resolved = resolve_manifest_module_options("storage", {"backend": "gcs"})
        assert resolved["backend"] == "gcs"

    def test_media_url_keeps_the_authored_form_at_config_layer(self) -> None:
        """The canonical slashes are applied by the adapter's projection."""
        resolved = resolve_manifest_module_options("storage", {"media_url": " media "})
        assert resolved["media_url"] == "media"

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_manifest_module_options(
            "storage", {"backend": "s3", "media_url": "/uploads/"}
        )
        assert resolve_manifest_module_options("storage", resolved) == resolved


# ===========================================================================
# 3. Validation through the shared engine
# ===========================================================================


class TestStorageValidation:
    """The engine enforces the manifest's single- and cross-option rules."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), _EXPECTED_DEFAULTS) == []

    def test_cloud_backend_with_bucket_and_region_passes(self) -> None:
        assert validate_module_options(_manifest(), _cloud()) == []

    @pytest.mark.parametrize("backend", ["local", "s3", "r2"])
    def test_every_declared_backend_passes(self, backend: str) -> None:
        assert validate_module_options(_manifest(), {"backend": backend}) == []

    @pytest.mark.parametrize("backend", ["S3", "R2", "Local"])
    def test_case_insensitive_backend_passes_validation(self, backend: str) -> None:
        """Mixed-case valid backends are canonicalized before validation."""
        assert validate_module_options(_manifest(), {"backend": backend}) == []

    @pytest.mark.parametrize("backend", ["gcs", "azure", "ftp", "S3GCS"])
    def test_invalid_backend_fails(self, backend: str) -> None:
        issues = validate_module_options(_manifest(), {"backend": backend})
        assert any("backend" in issue for issue in issues)
        assert any(
            "local" in issue and "s3" in issue and "r2" in issue for issue in issues
        )

    def test_cloud_backend_requires_credential_env_var_names(self) -> None:
        options = _cloud(**{_ACCESS_KEY_OPTION: "", _SECRET_KEY_OPTION: ""})
        issues = validate_module_options(_manifest(), options)
        assert any(_ACCESS_KEY_OPTION in issue for issue in issues)
        assert any(_SECRET_KEY_OPTION in issue for issue in issues)

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
    def test_retired_raw_credential_keys_are_refused(self, retired_key: str) -> None:
        issues = validate_module_options(_manifest(), {retired_key: "raw-secret"})
        assert len(issues) == 1
        assert "no longer supported" in issues[0]
        assert f"'{retired_key}'" in issues[0]

    def test_retired_key_is_reported_before_other_issues(self) -> None:
        options = {"access_key_id": "raw", "backend": "elsewhere"}
        issues = validate_module_options(_manifest(), options)
        assert "no longer supported" in issues[0]


# ===========================================================================
# 4. CLI configurator behaviour
# ===========================================================================


class TestStorageConfigurator:
    """The CLI configurator's defaults and prompts come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["storage"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["storage"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_canonicalized(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["storage"]
        config = entry.configure(
            non_interactive=True,
            existing_config={"backend": " S3 ", "bucket_name": "  bucket  "},
        )
        assert config["backend"] == "s3"
        assert config["bucket_name"] == "bucket"

    def test_existing_retired_key_aborts(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["storage"]
        with pytest.raises(click.Abort):
            entry.configure(
                non_interactive=True,
                existing_config={"custom_domain": "cdn.example.com"},
            )

    @patch("quickscale_cli.commands.module_config.click.confirm")
    @patch("quickscale_cli.commands.module_config.click.prompt")
    def test_interactive_prompts_read_the_manifest(
        self, mock_prompt, mock_confirm
    ) -> None:
        def _answer(message: str, **kwargs: object) -> object:
            prompt_type = kwargs.get("type")
            choices = getattr(prompt_type, "choices", [])
            if "s3" in choices:
                return "s3"
            return kwargs.get("default")

        mock_prompt.side_effect = _answer
        mock_confirm.return_value = False

        entry = MODULE_CONFIGURATOR_REGISTRY["storage"]
        config = entry.configure(non_interactive=False)

        assert config["backend"] == "s3"

        choice_types = [
            call.kwargs["type"]
            for call in mock_prompt.call_args_list
            if hasattr(call.kwargs.get("type"), "choices")
        ]
        assert len(choice_types) == 1
        assert list(choice_types[0].choices) == ["local", "s3", "r2"]

    @patch("quickscale_cli.commands.module_config.click.confirm")
    @patch("quickscale_cli.commands.module_config.click.prompt")
    def test_local_to_cloud_prompts_offer_the_manifest_credential_defaults(
        self, mock_prompt, mock_confirm
    ) -> None:
        """Blank stored credential names fall back to the manifest's defaults."""

        def _answer(message: str, **kwargs: object) -> object:
            prompt_type = kwargs.get("type")
            choices = getattr(prompt_type, "choices", [])
            if "s3" in choices:
                return "s3"
            return kwargs.get("default")

        mock_prompt.side_effect = _answer
        mock_confirm.return_value = False

        entry = MODULE_CONFIGURATOR_REGISTRY["storage"]
        config = entry.configure(
            non_interactive=False,
            existing_config={
                "backend": "local",
                _ACCESS_KEY_OPTION: "",
                _SECRET_KEY_OPTION: "",
            },
        )

        assert config["backend"] == "s3"
        assert config[_ACCESS_KEY_OPTION] == "AWS_ACCESS_KEY_ID"
        assert config[_SECRET_KEY_OPTION] == "AWS_SECRET_ACCESS_KEY"

    @patch("quickscale_cli.commands.module_config.click.confirm")
    @patch("quickscale_cli.commands.module_config.click.prompt")
    def test_cloud_to_local_reconfiguration_retains_cloud_options(
        self, mock_prompt, mock_confirm
    ) -> None:
        """Switching to local keeps cloud option values for a later switch.

        The manifest owns one option set; the adapter projects the cloud
        settings only while the backend is s3 or r2, so retained values stay
        inert until the operator selects a cloud backend again.  This is the
        declared transition contract (see the module README).
        """

        def _answer(message: str, **kwargs: object) -> object:
            prompt_type = kwargs.get("type")
            choices = getattr(prompt_type, "choices", [])
            if "local" in choices:
                return "local"
            return kwargs.get("default")

        mock_prompt.side_effect = _answer
        mock_confirm.return_value = False

        entry = MODULE_CONFIGURATOR_REGISTRY["storage"]
        config = entry.configure(
            non_interactive=False,
            existing_config={
                "backend": "s3",
                "bucket_name": "production-bucket",
                "endpoint_url": "https://s3.example.com",
                "access_key_id_env_var": "OLD_ACCESS",
                "secret_access_key_env_var": "OLD_SECRET",
            },
        )

        assert config["backend"] == "local"
        assert config["bucket_name"] == "production-bucket"
        assert config["endpoint_url"] == "https://s3.example.com"
        assert config[_ACCESS_KEY_OPTION] == "OLD_ACCESS"
        assert config[_SECRET_KEY_OPTION] == "OLD_SECRET"
