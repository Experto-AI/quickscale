"""Parity/regression tests for the manifest-driven orgs option-resolution path.

These tests encode the *legacy* ``_orgs_wiring`` option-resolution behaviour
as gold expectations and verify that the manifest-driven replacement
(``orgs_manifest.py``) produces identical results for every public entry point.

This file is ADDITIVE to ``test_orgs_contract.py``.  It focuses solely on
option-resolution parity (defaults, normalisation, resolution, validation) and
does NOT test wiring integration — that is covered by the existing contract
tests.

The gold values below were recovered from the orgs ``module.yml`` manifest
and the ``orgs_manifest.py`` adapter.

Scope
-----
* Default option values
* mode normalisation (strip + lowercase)
* mode fallback (invalid value → "solo")
* Resolution (defaults + normalised overrides, idempotency)
* Validation messages (choices enforcement)
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.contracts.module_options import (
    DEFAULT_ORGS_MODE,
    ORGS_MODE_SAAS,
    ORGS_MODE_SOLO,
    ORGS_MODES,
    ORGS_MODULE_OPTION_KEYS,
)
from quickscale_core.contracts.resolvers import (
    default_orgs_module_options,
    normalize_orgs_module_options,
    resolve_orgs_module_options,
    validate_orgs_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy _orgs_wiring + module.yml
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "mode": "solo",
}


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy(self) -> None:
        defaults = default_orgs_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        defaults = default_orgs_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_mode_is_solo(self) -> None:
        defaults = default_orgs_module_options()
        assert defaults["mode"] == DEFAULT_ORGS_MODE
        assert defaults["mode"] == "solo"


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must match the legacy values."""

    def test_default_mode_constant(self) -> None:
        assert DEFAULT_ORGS_MODE == "solo"

    def test_mode_constants(self) -> None:
        assert ORGS_MODE_SOLO == "solo"
        assert ORGS_MODE_SAAS == "saas"

    def test_modes_tuple(self) -> None:
        assert set(ORGS_MODES) == {"solo", "saas"}
        assert "solo" in ORGS_MODES
        assert "saas" in ORGS_MODES

    def test_module_option_keys_frozenset(self) -> None:
        assert ORGS_MODULE_OPTION_KEYS == frozenset({"mode"})


# ===========================================================================
# 3. Normalisation parity (mirrors _orgs_wiring coercion)
# ===========================================================================


class TestNormalizationParity:
    """Normalisation must behave identically to the legacy contract."""

    def test_mode_strip(self) -> None:
        """Whitespace is stripped from mode (mirrors str(...).strip())."""
        normalized = normalize_orgs_module_options({"mode": "  solo  "})
        assert normalized["mode"] == "solo"

    def test_mode_lowercase(self) -> None:
        """Mode is lowercased (mirrors .lower())."""
        normalized = normalize_orgs_module_options({"mode": "SOLO"})
        assert normalized["mode"] == "solo"

    def test_mode_saas_strip_and_lower(self) -> None:
        normalized = normalize_orgs_module_options({"mode": "  SaaS  "})
        assert normalized["mode"] == "saas"

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_orgs_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_orgs_module_options({})
        assert normalized == {}

    def test_already_normalized_mode_passes_through(self) -> None:
        normalized = normalize_orgs_module_options({"mode": "saas"})
        assert normalized["mode"] == "saas"


# ===========================================================================
# 4. Resolution parity (defaults + normalised overrides + fallback)
# ===========================================================================


class TestResolutionParity:
    """resolve_orgs_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_orgs_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_orgs_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_solo_mode_override(self) -> None:
        resolved = resolve_orgs_module_options({"mode": "solo"})
        assert resolved["mode"] == "solo"

    def test_saas_mode_override(self) -> None:
        resolved = resolve_orgs_module_options({"mode": "saas"})
        assert resolved["mode"] == "saas"

    def test_mode_is_strip_and_lowercased_in_resolve(self) -> None:
        resolved = resolve_orgs_module_options({"mode": "  SaaS  "})
        assert resolved["mode"] == "saas"

    def test_invalid_mode_passes_through(self) -> None:
        """SA27: invalid mode passes through instead of coercing to 'solo'."""
        resolved = resolve_orgs_module_options({"mode": "team"})
        assert resolved["mode"] == "team"

    def test_empty_mode_passes_through(self) -> None:
        """SA27: empty mode passes through instead of coercing to 'solo'."""
        resolved = resolve_orgs_module_options({"mode": ""})
        assert resolved["mode"] == ""

    def test_blank_mode_passes_through(self) -> None:
        """SA27: blank mode passes through instead of coercing to 'solo'."""
        resolved = resolve_orgs_module_options({"mode": "   "})
        assert resolved["mode"] == ""

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_orgs_module_options({"mode": "saas"})
        assert resolve_orgs_module_options(resolved) == resolved

    def test_resolved_keys_match_legacy(self) -> None:
        resolved = resolve_orgs_module_options({"mode": "saas"})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())


# ===========================================================================
# 5. Validation parity
# ===========================================================================


class TestValidationParity:
    """validate_orgs_module_options must produce legacy-compatible issues."""

    def test_defaults_pass_validation(self) -> None:
        issues = validate_orgs_module_options(None)
        assert issues == []

    def test_solo_mode_passes_validation(self) -> None:
        issues = validate_orgs_module_options({"mode": "solo"})
        assert issues == []

    def test_saas_mode_passes_validation(self) -> None:
        issues = validate_orgs_module_options({"mode": "saas"})
        assert issues == []

    @pytest.mark.parametrize("invalid_mode", ["team", "enterprise", "INVALID", "0"])
    def test_invalid_mode_fails_validation(self, invalid_mode: str) -> None:
        issues = validate_orgs_module_options({"mode": invalid_mode})
        assert len(issues) >= 1
        assert any("mode" in i for i in issues)
        assert any("solo" in i and "saas" in i for i in issues)

    def test_valid_modes_parametrized(self) -> None:
        for valid_mode in ("solo", "saas"):
            issues = validate_orgs_module_options({"mode": valid_mode})
            assert issues == [], f"Expected no issues for mode={valid_mode!r}"

    def test_case_insensitive_mode_passes_validation(self) -> None:
        """Mixed-case valid modes are normalized before validation."""
        assert validate_orgs_module_options({"mode": "Solo"}) == []
        assert validate_orgs_module_options({"mode": "SAAS"}) == []


# ===========================================================================
# 6. Wiring-field values parity
# ===========================================================================


class TestWiringFieldsParity:
    """Resolved options must project to the exact wiring field values
    that ``_orgs_wiring`` would have computed from the same input."""

    def test_default_wiring_mode_is_solo(self) -> None:
        resolved = resolve_orgs_module_options(None)
        # Mirrors: mode = str(options.get("mode", "solo")).strip().lower() or "solo"
        assert resolved["mode"] == "solo"

    def test_saas_wiring_mode(self) -> None:
        resolved = resolve_orgs_module_options({"mode": "saas"})
        assert resolved["mode"] == "saas"

    def test_invalid_mode_passes_through_in_wiring(self) -> None:
        """SA27: invalid mode passes through instead of coercing to 'solo'."""
        resolved = resolve_orgs_module_options({"mode": "enterprise"})
        assert resolved["mode"] == "enterprise"

    def test_resolved_contains_all_wiring_keys(self) -> None:
        resolved = resolve_orgs_module_options(None)
        wiring_keys = {"mode"}
        assert wiring_keys.issubset(set(resolved.keys()))
