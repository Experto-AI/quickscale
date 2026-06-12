"""Parity/regression tests for the manifest-driven backups path.

These tests encode the *legacy* ``backups_contract.py`` behaviour as gold
expectations and verify that the manifest-driven replacement
(``backups_manifest.py``) produces identical results for every public
entry point.

The legacy contract file was deleted when the backups module was migrated
to the manifest-driven path (Phase 4, backups migration).  The gold values
below were recovered from the last committed version of
``backups_contract.py``, the core ``module_options.py`` helpers, and the
backups ``module.yml`` manifest.

Design notes
------------
* ``default_backups_module_options()`` sources defaults from ``module.yml``.
  The env-var option defaults are ``""`` in the manifest by design — the
  real fallback env-var *names* are carried by the
  ``DEFAULT_BACKUPS_REMOTE_*`` constants which are re-exported from core.
* ``normalize_backups_module_options``, ``has_legacy_backups_secret_values``,
  and ``validate_backups_env_var_reference`` are thin re-exports from
  ``quickscale_core.contracts.module_options`` — behaviour is unchanged.
* ``sanitize_module_options`` (the cross-module dispatcher) is NOT exported
  from ``backups_manifest``; it lives in ``quickscale_core.contracts.module_options``
  and is tested here via that path to confirm the backups dispatch still works.

Scope
-----
* Constant values (env-var option names, default env-var names)
* Default option values (sourced from module.yml)
* has_legacy_backups_secret_values detection
* validate_backups_env_var_reference messages
* normalize_backups_module_options legacy-key removal
* sanitize_module_options dispatch for the backups module (via core)
"""

from __future__ import annotations

from typing import Any

from quickscale_cli.backups_manifest import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    default_backups_module_options,
    has_legacy_backups_secret_values,
    normalize_backups_module_options,
    validate_backups_env_var_reference,
)
from quickscale_core.contracts.module_options import sanitize_module_options

# ---------------------------------------------------------------------------
# Gold expectations recovered from legacy contract and module.yml
# ---------------------------------------------------------------------------

_EXPECTED_DEFAULTS: dict[str, Any] = {
    "retention_days": 14,
    "naming_prefix": "db",
    "target_mode": "local",
    "local_directory": ".quickscale/backups",
    "remote_bucket_name": "",
    "remote_prefix": "backups/private",
    "remote_endpoint_url": "",
    "remote_region_name": "",
    "remote_access_key_id_env_var": "",
    "remote_secret_access_key_env_var": "",
    "automation_enabled": False,
    "schedule": "0 2 * * *",
}

_EXPECTED_CONSTANT_ACCESS_KEY_ID_ENV_VAR = "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
_EXPECTED_CONSTANT_SECRET_ACCESS_KEY_ENV_VAR = (
    "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"
)


# ===========================================================================
# 1. Constant parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must equal the values defined in core."""

    def test_option_name_access_key_id(self) -> None:
        assert (
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION
            == "remote_access_key_id_env_var"
        )

    def test_option_name_secret_access_key(self) -> None:
        assert (
            BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION
            == "remote_secret_access_key_env_var"
        )

    def test_default_access_key_id_env_var(self) -> None:
        assert (
            DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
            == _EXPECTED_CONSTANT_ACCESS_KEY_ID_ENV_VAR
        )

    def test_default_secret_access_key_env_var(self) -> None:
        assert (
            DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
            == _EXPECTED_CONSTANT_SECRET_ACCESS_KEY_ENV_VAR
        )

    def test_default_env_vars_are_not_empty_strings(self) -> None:
        """DEFAULT_BACKUPS_REMOTE_* are real env-var names, not blank strings."""
        assert DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR != ""
        assert DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR != ""

    def test_default_env_vars_differ_from_manifest_defaults(self) -> None:
        """module.yml stores '' for env-var option defaults; constants are distinct."""
        defaults = default_backups_module_options()
        assert defaults.get(BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION) == ""
        assert defaults.get(BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION) == ""
        # But the DEFAULT_BACKUPS_REMOTE_* constants are non-empty
        assert DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR != ""
        assert DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR != ""


# ===========================================================================
# 2. Default options parity
# ===========================================================================


class TestDefaultsParity:
    """Manifest-driven defaults must match the expected gold values."""

    def test_default_options_match_expected(self) -> None:
        defaults = default_backups_module_options()
        assert defaults == _EXPECTED_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        defaults = default_backups_module_options()
        assert set(defaults.keys()) == set(_EXPECTED_DEFAULTS.keys())

    def test_default_retention_days(self) -> None:
        defaults = default_backups_module_options()
        assert defaults["retention_days"] == 14

    def test_default_target_mode(self) -> None:
        defaults = default_backups_module_options()
        assert defaults["target_mode"] == "local"

    def test_default_env_var_options_are_blank(self) -> None:
        """Env-var option defaults are '' in module.yml; operators supply them."""
        defaults = default_backups_module_options()
        assert defaults[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION] == ""
        assert defaults[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION] == ""

    def test_default_automation_enabled_is_false(self) -> None:
        defaults = default_backups_module_options()
        assert defaults["automation_enabled"] is False

    def test_default_options_is_stable_across_calls(self) -> None:
        assert default_backups_module_options() == default_backups_module_options()


# ===========================================================================
# 3. has_legacy_backups_secret_values parity
# ===========================================================================


class TestHasLegacyBackupsSecretValuesParity:
    """has_legacy_backups_secret_values must detect the legacy raw-secret keys."""

    def test_none_returns_false(self) -> None:
        assert has_legacy_backups_secret_values(None) is False

    def test_empty_dict_returns_false(self) -> None:
        assert has_legacy_backups_secret_values({}) is False

    def test_canonical_options_return_false(self) -> None:
        options = {
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "MY_ACCESS_KEY_ENV",
            BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION: "MY_SECRET_ENV",
        }
        assert has_legacy_backups_secret_values(options) is False

    def test_legacy_remote_access_key_id_detected(self) -> None:
        options = {"remote_access_key_id": "AKIAFAKEACCESSKEYID123"}
        assert has_legacy_backups_secret_values(options) is True

    def test_legacy_remote_secret_access_key_detected(self) -> None:
        options = {"remote_secret_access_key": "fakesecretvalue12345678"}
        assert has_legacy_backups_secret_values(options) is True

    def test_both_legacy_keys_detected(self) -> None:
        options = {
            "remote_access_key_id": "AKIAFAKEACCESSKEYID123",
            "remote_secret_access_key": "fakesecretvalue12345678",
        }
        assert has_legacy_backups_secret_values(options) is True

    def test_blank_legacy_key_not_detected(self) -> None:
        """Blank values (not real secrets) must not be flagged."""
        options = {"remote_access_key_id": "", "remote_secret_access_key": "   "}
        assert has_legacy_backups_secret_values(options) is False


# ===========================================================================
# 4. validate_backups_env_var_reference parity
# ===========================================================================


class TestValidateBackupsEnvVarReferenceParity:
    """validate_backups_env_var_reference must produce the exact legacy messages."""

    def test_blank_value_returns_none(self) -> None:
        assert (
            validate_backups_env_var_reference("remote_access_key_id_env_var", "")
            is None
        )

    def test_whitespace_only_returns_none(self) -> None:
        assert (
            validate_backups_env_var_reference("remote_access_key_id_env_var", "  ")
            is None
        )

    def test_valid_env_var_name_returns_none(self) -> None:
        assert (
            validate_backups_env_var_reference(
                "remote_access_key_id_env_var", "MY_BACKUPS_KEY"
            )
            is None
        )

    def test_invalid_pattern_returns_error(self) -> None:
        result = validate_backups_env_var_reference(
            "remote_access_key_id_env_var", "not-valid-env"
        )
        assert result is not None
        assert "^[A-Z][A-Z0-9_]*$" in result
        assert "modules.backups.remote_access_key_id_env_var" in result

    def test_literal_aws_access_key_id_detected(self) -> None:
        """A value matching the AWS access key pattern must be rejected.

        The pattern is ^(?:AKIA|ASIA)[A-Z0-9]{16}$ — exactly 20 chars total.
        """
        result = validate_backups_env_var_reference(
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
            "AKIAFAKEACCESSKEY123",  # AKIA + 16 uppercase alphanum = 20 chars total
        )
        assert result is not None
        assert "literal AWS access key id" in result

    def test_secret_access_key_option_not_rejected_for_aws_pattern(self) -> None:
        """Only the access key ID option triggers the AWS literal key check.

        The secret access key option must NOT flag a value that matches the AWS
        access key ID pattern format, because that check only applies to the
        access key ID field.
        """
        result = validate_backups_env_var_reference(
            BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
            "AKIAFAKEACCESSKEY123",  # AKIA + 16 chars, matches AWS key ID pattern format
        )
        # Secret access key option does not trigger the AWS literal key check,
        # so this must either pass pattern validation or fail only on the
        # general env-var pattern (here it is 20 chars of uppercase+digits = valid).
        assert result is None


# ===========================================================================
# 5. normalize_backups_module_options parity
# ===========================================================================


class TestNormalizeBackupsModuleOptionsParity:
    """normalize_backups_module_options must behave identically to the core helper."""

    def test_none_returns_empty_dict(self) -> None:
        assert normalize_backups_module_options(None) == {}

    def test_empty_dict_returns_empty_dict(self) -> None:
        assert normalize_backups_module_options({}) == {}

    def test_canonical_options_pass_through(self) -> None:
        options = {
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "MY_KEY_ENV",
            "retention_days": 30,
        }
        normalized = normalize_backups_module_options(options)
        assert normalized[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION] == "MY_KEY_ENV"
        assert normalized["retention_days"] == 30

    def test_legacy_access_key_id_removed_and_env_var_set(self) -> None:
        """Legacy raw access_key_id must be removed and env_var set to the default."""
        options = {"remote_access_key_id": "AKIAFAKEACCESSKEYID123"}
        normalized = normalize_backups_module_options(options)
        assert "remote_access_key_id" not in normalized
        assert (
            normalized[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
            == DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )

    def test_legacy_secret_access_key_removed_and_env_var_set(self) -> None:
        """Legacy raw secret_access_key must be removed and env_var set to the default."""
        options = {"remote_secret_access_key": "fakesecretvalue12345678"}
        normalized = normalize_backups_module_options(options)
        assert "remote_secret_access_key" not in normalized
        assert (
            normalized[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
            == DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )

    def test_legacy_key_not_overwritten_when_env_var_already_set(self) -> None:
        """If the env_var option is already set, the legacy value must not overwrite it."""
        options = {
            "remote_access_key_id": "AKIAFAKEACCESSKEYID123",
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "EXISTING_ENV_VAR",
        }
        normalized = normalize_backups_module_options(options)
        assert "remote_access_key_id" not in normalized
        assert (
            normalized[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
            == "EXISTING_ENV_VAR"
        )


# ===========================================================================
# 6. sanitize_module_options dispatch via core (backups route)
# ===========================================================================


class TestSanitizeModuleOptionsBackupsDispatch:
    """sanitize_module_options (from core) must correctly dispatch to backups normalization."""

    def test_sanitize_empty_options(self) -> None:
        result = sanitize_module_options("backups", {})
        assert isinstance(result, dict)

    def test_sanitize_none_options(self) -> None:
        result = sanitize_module_options("backups", None)
        assert isinstance(result, dict)

    def test_sanitize_strips_legacy_keys(self) -> None:
        """The dispatcher must route to normalize_backups_module_options."""
        options = {"remote_access_key_id": "AKIAFAKEACCESSKEYID123"}
        result = sanitize_module_options("backups", options)
        assert "remote_access_key_id" not in result
        assert (
            result.get(BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION)
            == DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )

    def test_sanitize_canonical_options_preserved(self) -> None:
        options = {
            BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION: "MY_KEY_ENV",
            "retention_days": 7,
        }
        result = sanitize_module_options("backups", options)
        assert result[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION] == "MY_KEY_ENV"
        assert result["retention_days"] == 7

    def test_sanitize_result_matches_normalize_directly(self) -> None:
        """The dispatcher route must produce the same result as calling normalize directly."""
        options = {
            "remote_access_key_id": "AKIAFAKEACCESSKEYID123",
            "retention_days": 21,
        }
        via_dispatcher = sanitize_module_options("backups", options)
        via_normalize = normalize_backups_module_options(options)
        assert via_dispatcher == via_normalize
