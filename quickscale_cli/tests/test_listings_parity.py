"""Parity/regression tests for the manifest-driven listings path.

These tests encode the *legacy* ``_listings_wiring`` behaviour as gold
expectations and verify that the manifest-driven replacement
(``listings_manifest.py``) produces identical results for every public
entry point.

The gold values below were recovered from the listings ``module.yml``
manifest and the ``listings_manifest.py`` adapter.

Scope
-----
* Default option values
* Resolution (defaults + normalised overrides, idempotency)
* listings_per_page int coercion
* Validation messages (positive integer enforcement)
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.contracts.resolvers import (
    DEFAULT_LISTINGS_PER_PAGE,
    LISTINGS_MODULE_OPTION_KEYS,
    default_listings_module_options,
    normalize_listings_module_options,
    resolve_listings_module_options,
    validate_listings_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy _listings_wiring + module.yml
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "listings_per_page": 12,
}


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy(self) -> None:
        defaults = default_listings_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        defaults = default_listings_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_listings_per_page_is_12(self) -> None:
        defaults = default_listings_module_options()
        assert defaults["listings_per_page"] == DEFAULT_LISTINGS_PER_PAGE
        assert defaults["listings_per_page"] == 12


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must match the legacy values."""

    def test_default_listings_per_page_constant(self) -> None:
        assert DEFAULT_LISTINGS_PER_PAGE == 12

    def test_module_option_keys_frozenset(self) -> None:
        assert LISTINGS_MODULE_OPTION_KEYS == frozenset({"listings_per_page"})


# ===========================================================================
# 3. Normalisation parity
# ===========================================================================


class TestNormalizationParity:
    """Normalisation must behave identically to the legacy contract."""

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_listings_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_listings_module_options({})
        assert normalized == {}

    def test_listings_per_page_passes_through(self) -> None:
        normalized = normalize_listings_module_options({"listings_per_page": 25})
        assert normalized["listings_per_page"] == 25


# ===========================================================================
# 4. Resolution parity (defaults + normalised overrides)
# ===========================================================================


class TestResolutionParity:
    """resolve_listings_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_listings_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_listings_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_listings_per_page_override(self) -> None:
        resolved = resolve_listings_module_options({"listings_per_page": 25})
        assert resolved["listings_per_page"] == 25

    def test_listings_per_page_string_coerced_to_int(self) -> None:
        """Legacy _listings_wiring uses int(), so string "8" should resolve to 8."""
        resolved = resolve_listings_module_options({"listings_per_page": "8"})
        assert resolved["listings_per_page"] == 8
        assert isinstance(resolved["listings_per_page"], int)

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_listings_module_options({"listings_per_page": 25})
        assert resolve_listings_module_options(resolved) == resolved

    def test_resolved_keys_match_legacy(self) -> None:
        resolved = resolve_listings_module_options({"listings_per_page": 25})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_resolved_value_is_int(self) -> None:
        resolved = resolve_listings_module_options(None)
        assert isinstance(resolved["listings_per_page"], int)


# ===========================================================================
# 5. Validation parity
# ===========================================================================


class TestValidationParity:
    """validate_listings_module_options must produce legacy-compatible issues."""

    def test_defaults_pass_validation(self) -> None:
        issues = validate_listings_module_options(None)
        assert issues == []

    def test_valid_override_passes_validation(self) -> None:
        issues = validate_listings_module_options({"listings_per_page": 25})
        assert issues == []

    @pytest.mark.parametrize("bad_value", [0, -1, -100])
    def test_non_positive_listings_per_page_fails(self, bad_value: int) -> None:
        issues = validate_listings_module_options({"listings_per_page": bad_value})
        assert any("listings_per_page" in i for i in issues)


# ===========================================================================
# 6. Wiring-field values parity
# ===========================================================================


class TestWiringFieldsParity:
    """Resolved options must project to the exact wiring field values
    that ``_listings_wiring`` would have computed from the same input."""

    def test_default_wiring_listings_per_page(self) -> None:
        resolved = resolve_listings_module_options(None)
        # Mirrors: listings_per_page = int(options.get("listings_per_page", 12))
        assert resolved["listings_per_page"] == 12

    def test_custom_wiring_listings_per_page(self) -> None:
        resolved = resolve_listings_module_options({"listings_per_page": 6})
        assert resolved["listings_per_page"] == 6

    def test_resolved_contains_all_wiring_keys(self) -> None:
        resolved = resolve_listings_module_options(None)
        wiring_keys = {"listings_per_page"}
        assert wiring_keys.issubset(set(resolved.keys()))
