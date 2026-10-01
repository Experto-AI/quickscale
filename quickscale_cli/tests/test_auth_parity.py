"""Contract tests for the auth module's manifest-owned configuration.

The auth option defaults, validation, and retired-key refusals are declared in
``quickscale_modules/auth/module.yml`` and enforced through the shared manifest
engine; its CLI configurator is the one generic manifest-driven configurator.
These tests pin that contract and the operator-facing behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import click
import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_core.contracts.module_options import sanitize_module_options
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)
from quickscale_core.manifest.option_validation import (
    collect_option_validation_issues,
    validate_module_options,
)
from quickscale_core.schema.config_schema import ConfigValidationError

_EXPECTED_DEFAULTS: dict[str, object] = {
    "enabled": True,
    "registration_enabled": True,
    "email_verification": "none",
    "authentication_method": "email",
    "session_cookie_age": 1209600,
}

_EMAIL_VERIFICATION_VALUES = ["none", "optional", "mandatory"]
_AUTHENTICATION_METHOD_VALUES = ["email", "username", "both"]
_RETIRED_KEYS = {"allow_registration", "social_providers"}


def _manifest():
    return load_module_manifest_with_fallback("auth")


# ===========================================================================
# 1. Manifest declarations
# ===========================================================================


class TestManifestDeclaration:
    """The manifest owns the option set, choices, bounds, and retirements."""

    def test_defaults_match_the_manifest(self) -> None:
        assert resolve_manifest_module_options("auth") == _EXPECTED_DEFAULTS

    def test_email_verification_choices_are_declared(self) -> None:
        option = _manifest().get_option("email_verification")
        assert option is not None
        assert option.validation.get("choices") == _EMAIL_VERIFICATION_VALUES

    def test_authentication_method_choices_are_declared(self) -> None:
        option = _manifest().get_option("authentication_method")
        assert option is not None
        assert option.validation.get("choices") == _AUTHENTICATION_METHOD_VALUES

    def test_session_cookie_age_minimum_is_declared(self) -> None:
        option = _manifest().get_option("session_cookie_age")
        assert option is not None
        assert option.validation.get("min") == 1

    def test_legacy_keys_are_declared_retired(self) -> None:
        retired = _manifest().retired_options
        assert set(retired) == _RETIRED_KEYS
        assert "registration_enabled" in retired["allow_registration"]
        assert "social_providers" in retired["social_providers"]


# ===========================================================================
# 2. Validation through the shared engine
# ===========================================================================


class TestAuthValidation:
    """The engine refuses a wrong type or a value outside the declared set."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), _EXPECTED_DEFAULTS) == []

    def test_non_boolean_registration_is_refused(self) -> None:
        issues = validate_module_options(_manifest(), {"registration_enabled": "yes"})
        assert any(
            "registration_enabled" in issue and "boolean" in issue for issue in issues
        )

    def test_invalid_email_verification_is_refused(self) -> None:
        issues = validate_module_options(
            _manifest(), {"email_verification": "sometimes"}
        )
        assert any("email_verification" in issue for issue in issues)

    def test_invalid_authentication_method_is_refused(self) -> None:
        issues = validate_module_options(
            _manifest(), {"authentication_method": "magic"}
        )
        assert any("authentication_method" in issue for issue in issues)

    def test_non_integer_session_cookie_age_is_refused(self) -> None:
        issues = validate_module_options(_manifest(), {"session_cookie_age": "forever"})
        assert any("session_cookie_age" in issue for issue in issues)

    def test_zero_session_cookie_age_is_refused(self) -> None:
        issues = validate_module_options(_manifest(), {"session_cookie_age": 0})
        assert any("session_cookie_age" in issue for issue in issues)

    @pytest.mark.parametrize("key", sorted(_RETIRED_KEYS))
    def test_retired_keys_are_reported_with_the_manifest_message(
        self, key: str
    ) -> None:
        issues = collect_option_validation_issues(_manifest(), {key: True})
        assert issues
        assert issues[0].option_name == key
        assert "no longer supported" in issues[0].message

    def test_sanitize_refuses_retired_keys(self) -> None:
        with pytest.raises(ConfigValidationError, match="allow_registration"):
            sanitize_module_options("auth", {"allow_registration": False})
        with pytest.raises(ConfigValidationError, match="social_providers"):
            sanitize_module_options("auth", {"social_providers": ["google"]})


# ===========================================================================
# 3. Resolution through the generic resolver
# ===========================================================================


class TestAuthResolution:
    """The generic resolver merges defaults with supplied overrides."""

    def test_partial_override_preserves_other_defaults(self) -> None:
        resolved = resolve_manifest_module_options(
            "auth", {"registration_enabled": False}
        )
        expected = dict(_EXPECTED_DEFAULTS)
        expected["registration_enabled"] = False
        assert resolved == expected

    def test_all_options_override(self) -> None:
        resolved = resolve_manifest_module_options(
            "auth",
            {
                "registration_enabled": False,
                "email_verification": "mandatory",
                "authentication_method": "username",
                "session_cookie_age": 86400,
            },
        )
        assert resolved == {
            "enabled": True,
            "registration_enabled": False,
            "email_verification": "mandatory",
            "authentication_method": "username",
            "session_cookie_age": 86400,
        }

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_manifest_module_options(
            "auth", {"registration_enabled": False, "session_cookie_age": 86400}
        )
        assert resolve_manifest_module_options("auth", resolved) == resolved


# ===========================================================================
# 4. CLI configurator behaviour
# ===========================================================================


class TestAuthConfigurator:
    """The CLI configurator's prompts and defaults come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["auth"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["auth"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_kept(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["auth"]
        config = entry.configure(
            non_interactive=True,
            existing_config={
                "registration_enabled": False,
                "session_cookie_age": 86400,
            },
        )
        assert config["registration_enabled"] is False
        assert config["session_cookie_age"] == 86400
        assert config["email_verification"] == "none"

    def test_retired_existing_keys_abort_instead_of_being_dropped(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["auth"]
        with pytest.raises(click.Abort):
            entry.configure(
                non_interactive=True,
                existing_config={"allow_registration": False},
            )

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_interactive_prompts_read_the_manifest(
        self, mock_confirm, mock_prompt
    ) -> None:
        """Every manifest option is prompted once, in declaration order."""
        mock_confirm.side_effect = [False, False]
        mock_prompt.side_effect = ["optional", 3600, "username"]

        entry = MODULE_CONFIGURATOR_REGISTRY["auth"]
        config = entry.configure(non_interactive=False)

        assert config == {
            "enabled": False,
            "registration_enabled": False,
            "email_verification": "optional",
            "session_cookie_age": 3600,
            "authentication_method": "username",
        }
