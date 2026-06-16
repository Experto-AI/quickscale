"""Parity/regression tests for the manifest-driven auth path.

These tests encode the *legacy* ``auth_contract.py`` behaviour as gold
expectations and verify that the manifest-driven replacement
(``auth_manifest.py``) produces identical results for every public
entry point.

The legacy contract file was deleted when the auth module was migrated
to the manifest-driven path (Phase 4, auth migration).  The gold values
below were recovered from the last committed version of
``auth_contract.py`` and from the auth ``module.yml`` manifest that
now owns the defaults.

Scope
-----
* Default option values (all 4 keys including immutable authentication_method)
* Legacy-key normalisation (allow_registration -> registration_enabled, social_providers dropped)
* Resolution (defaults + normalised overrides)
* Behavioral equivalence of ``format_auth_desired_config_contract()`` (canonical keys, value shapes, legacy guidance)
"""

from __future__ import annotations

from typing import Any

from quickscale_cli.auth_manifest import (  # type: ignore[import-untyped]
    AUTH_AUTHENTICATION_METHOD_OPTION,
    AUTH_AUTHENTICATION_METHOD_VALUES,
    AUTH_EMAIL_VERIFICATION_OPTION,
    AUTH_EMAIL_VERIFICATION_VALUES,
    AUTH_REGISTRATION_ENABLED_OPTION,
    AUTH_SESSION_COOKIE_AGE_OPTION,
    CANONICAL_AUTH_MODULE_OPTION_KEYS,
    LEGACY_AUTH_ALLOW_REGISTRATION_OPTION,
    LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION,
    default_auth_module_options,
    format_auth_desired_config_contract,
    normalize_auth_module_options,
    resolve_auth_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy auth_contract.py
# get_defaults() includes BOTH mutable and immutable options (CR2 compliance).
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "registration_enabled": True,
    "email_verification": "none",
    "authentication_method": "email",
    "session_cookie_age": 1209600,
}


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy_contract(self) -> None:
        """Every default must equal the value the old contract file returned."""
        defaults = default_auth_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        """The key set must not drift from the legacy contract."""
        defaults = default_auth_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_registration_enabled_is_true(self) -> None:
        defaults = default_auth_module_options()
        assert defaults["registration_enabled"] is True

    def test_default_email_verification_is_none(self) -> None:
        defaults = default_auth_module_options()
        assert defaults["email_verification"] == "none"

    def test_default_authentication_method_is_email(self) -> None:
        """authentication_method is immutable in module.yml; must appear in defaults."""
        defaults = default_auth_module_options()
        assert defaults["authentication_method"] == "email"

    def test_default_session_cookie_age(self) -> None:
        defaults = default_auth_module_options()
        assert defaults["session_cookie_age"] == 1209600

    def test_immutable_authentication_method_present_in_defaults(self) -> None:
        """CR2: get_defaults() includes immutable options; no defensive fallback needed."""
        defaults = default_auth_module_options()
        assert AUTH_AUTHENTICATION_METHOD_OPTION in defaults


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must remain identical to the legacy contract values."""

    def test_option_name_constants(self) -> None:
        assert AUTH_REGISTRATION_ENABLED_OPTION == "registration_enabled"
        assert AUTH_EMAIL_VERIFICATION_OPTION == "email_verification"
        assert AUTH_AUTHENTICATION_METHOD_OPTION == "authentication_method"
        assert AUTH_SESSION_COOKIE_AGE_OPTION == "session_cookie_age"

    def test_legacy_option_name_constants(self) -> None:
        assert LEGACY_AUTH_ALLOW_REGISTRATION_OPTION == "allow_registration"
        assert LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION == "social_providers"

    def test_email_verification_values_tuple(self) -> None:
        assert AUTH_EMAIL_VERIFICATION_VALUES == ("none", "optional", "mandatory")

    def test_authentication_method_values_tuple(self) -> None:
        assert AUTH_AUTHENTICATION_METHOD_VALUES == ("email", "username", "both")

    def test_canonical_option_keys_frozenset(self) -> None:
        expected = frozenset(
            {
                "registration_enabled",
                "email_verification",
                "authentication_method",
                "session_cookie_age",
            }
        )
        assert CANONICAL_AUTH_MODULE_OPTION_KEYS == expected


# ===========================================================================
# 3. Normalisation parity
# ===========================================================================


class TestNormalizationParity:
    """Normalisation must behave identically to the legacy contract."""

    def test_legacy_allow_registration_migrated_when_absent(self) -> None:
        """allow_registration -> registration_enabled when registration_enabled is absent."""
        normalized = normalize_auth_module_options(
            {LEGACY_AUTH_ALLOW_REGISTRATION_OPTION: False}
        )
        assert normalized.get("registration_enabled") is False
        assert LEGACY_AUTH_ALLOW_REGISTRATION_OPTION not in normalized

    def test_legacy_allow_registration_not_migrated_when_present(self) -> None:
        """registration_enabled takes precedence over allow_registration."""
        normalized = normalize_auth_module_options(
            {
                AUTH_REGISTRATION_ENABLED_OPTION: True,
                LEGACY_AUTH_ALLOW_REGISTRATION_OPTION: False,
            }
        )
        assert normalized.get("registration_enabled") is True
        assert LEGACY_AUTH_ALLOW_REGISTRATION_OPTION not in normalized

    def test_legacy_social_providers_dropped(self) -> None:
        """social_providers is always removed during normalization."""
        normalized = normalize_auth_module_options(
            {LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION: ["google", "github"]}
        )
        assert LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION not in normalized

    def test_both_legacy_keys_dropped_simultaneously(self) -> None:
        normalized = normalize_auth_module_options(
            {
                LEGACY_AUTH_ALLOW_REGISTRATION_OPTION: True,
                LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION: ["google"],
            }
        )
        assert LEGACY_AUTH_ALLOW_REGISTRATION_OPTION not in normalized
        assert LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION not in normalized
        assert normalized.get("registration_enabled") is True

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_auth_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_auth_module_options({})
        assert normalized == {}

    def test_canonical_keys_pass_through_unchanged(self) -> None:
        opts = {
            "registration_enabled": False,
            "email_verification": "mandatory",
            "authentication_method": "username",
            "session_cookie_age": 86400,
        }
        normalized = normalize_auth_module_options(opts)
        assert normalized == opts


# ===========================================================================
# 4. Resolution parity (defaults + normalised overrides)
# ===========================================================================


class TestResolutionParity:
    """resolve_auth_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_auth_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_auth_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_partial_override_preserves_other_defaults(self) -> None:
        resolved = resolve_auth_module_options({"registration_enabled": False})
        expected = dict(_LEGACY_DEFAULTS)
        expected["registration_enabled"] = False
        assert resolved == expected

    def test_multiple_overrides(self) -> None:
        resolved = resolve_auth_module_options(
            {
                "registration_enabled": False,
                "email_verification": "mandatory",
                "authentication_method": "username",
            }
        )
        assert resolved["registration_enabled"] is False
        assert resolved["email_verification"] == "mandatory"
        assert resolved["authentication_method"] == "username"
        # Untouched default remains
        assert resolved["session_cookie_age"] == 1209600

    def test_legacy_allow_registration_resolved_via_normalize(self) -> None:
        """Legacy allow_registration is migrated before resolution."""
        resolved = resolve_auth_module_options(
            {LEGACY_AUTH_ALLOW_REGISTRATION_OPTION: False}
        )
        assert resolved["registration_enabled"] is False
        assert LEGACY_AUTH_ALLOW_REGISTRATION_OPTION not in resolved

    def test_legacy_social_providers_dropped_in_resolved(self) -> None:
        resolved = resolve_auth_module_options(
            {LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION: ["google"]}
        )
        assert LEGACY_AUTH_SOCIAL_PROVIDERS_OPTION not in resolved

    def test_resolved_keys_match_legacy(self) -> None:
        """The resolved dict must contain exactly the same keys as legacy."""
        resolved = resolve_auth_module_options({"registration_enabled": False})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_session_cookie_age_override(self) -> None:
        resolved = resolve_auth_module_options({"session_cookie_age": 86400})
        assert resolved["session_cookie_age"] == 86400


# ===========================================================================
# 5. format_auth_desired_config_contract parity
# ===========================================================================


class TestFormatAuthDesiredConfigContractParity:
    """format_auth_desired_config_contract must provide behavioral-equivalent contract info."""

    def test_format_string_provides_behavioral_equivalence(self) -> None:
        """Verify the contract output contains all required behavioral elements.

        Assert *semantics* instead of literal presentation fragments so that
        cosmetic changes (separator style, whitespace, rephrasing) cannot
        break the test while the underlying meaning is preserved.
        """
        contract = format_auth_desired_config_contract()

        # Verify it's a non-empty multi-line string
        assert isinstance(contract, str)
        assert len(contract) > 0
        lines = contract.split("\n")
        assert len(lines) >= 5, (
            "Contract should have header + 4 canonical keys + legacy guidance"
        )

        # Verify header introduces canonical auth keys (structural, not cosmetic)
        assert lines[0].lower().startswith("canonical auth keys")

        # Build a mapping from canonical key -> the line that declares it.
        # Each canonical key must appear exactly once as a modules.auth.<key>: entry.
        key_lines: dict[str, str] = {}
        for key in CANONICAL_AUTH_MODULE_OPTION_KEYS:
            matches = [line for line in lines if f"modules.auth.{key}:" in line]
            assert len(matches) == 1, (
                f"Expected exactly one line for {key}, found {len(matches)}"
            )
            key_lines[key] = matches[0]

        # registration_enabled: line must convey boolean (true/false) semantics
        reg_line = key_lines["registration_enabled"].lower()
        assert "true" in reg_line and "false" in reg_line, (
            "registration_enabled line must convey boolean semantics"
        )

        # email_verification: line must include every enum member,
        # independent of separator or whitespace
        ev_line = key_lines["email_verification"].lower()
        for member in AUTH_EMAIL_VERIFICATION_VALUES:
            assert member in ev_line, (
                f"email_verification line must include enum member '{member}'"
            )

        # authentication_method: line must include every enum member,
        # independent of separator or whitespace
        am_line = key_lines["authentication_method"].lower()
        for member in AUTH_AUTHENTICATION_METHOD_VALUES:
            assert member in am_line, (
                f"authentication_method line must include enum member '{member}'"
            )

        # session_cookie_age: line must convey positive-integer-in-seconds meaning
        # without pinning one exact phrase
        sc_line = key_lines["session_cookie_age"].lower()
        assert "integer" in sc_line and "second" in sc_line, (
            "session_cookie_age line must convey positive-integer-in-seconds meaning"
        )

        # Legacy key remediation guidance: both legacy keys must be mentioned
        # somewhere in the contract, with removal or migration intent
        contract_lower = contract.lower()
        assert "allow_registration" in contract_lower, (
            "Contract must mention allow_registration legacy key"
        )
        assert "social_providers" in contract_lower, (
            "Contract must mention social_providers legacy key"
        )
        assert any(
            term in contract_lower
            for term in ("remove", "deprecated", "migrate", "migration")
        ), "Legacy key guidance should mention removal or migration"

    def test_format_string_contains_all_canonical_keys(self) -> None:
        contract = format_auth_desired_config_contract()
        assert "registration_enabled" in contract
        assert "email_verification" in contract
        assert "authentication_method" in contract
        assert "session_cookie_age" in contract

    def test_format_string_mentions_legacy_keys(self) -> None:
        contract = format_auth_desired_config_contract()
        assert "allow_registration" in contract
        assert "social_providers" in contract

    def test_format_string_is_stable_across_calls(self) -> None:
        """Multiple calls must return the same string."""
        assert (
            format_auth_desired_config_contract()
            == format_auth_desired_config_contract()
        )
