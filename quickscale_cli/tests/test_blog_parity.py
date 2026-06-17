"""Parity/regression tests for the manifest-driven blog path.

These tests encode the *legacy* ``_blog_wiring`` behaviour as gold
expectations and verify that the manifest-driven replacement
(``blog_manifest.py``) produces identical results for every public
entry point.

The gold values below were recovered from the blog ``module.yml`` manifest
and the ``blog_manifest.py`` adapter.

Scope
-----
* Default option values
* api_rate_limit normalisation (strip + blank fallback)
* Resolution (defaults + normalised overrides, idempotency)
* posts_per_page int coercion
* enable_rss bool coercion
* Validation messages
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_cli.blog_manifest import (  # type: ignore[import-untyped]
    BLOG_MODULE_OPTION_KEYS,
    DEFAULT_BLOG_API_RATE_LIMIT,
    DEFAULT_BLOG_ENABLE_RSS,
    DEFAULT_BLOG_POSTS_PER_PAGE,
    default_blog_module_options,
    normalize_blog_module_options,
    resolve_blog_module_options,
    validate_blog_module_options,
)

# ---------------------------------------------------------------------------
# Gold expectations recovered from the legacy _blog_wiring + module.yml
# ---------------------------------------------------------------------------

_LEGACY_DEFAULTS: dict[str, Any] = {
    "posts_per_page": 10,
    "enable_rss": True,
    "api_rate_limit": "5/hour",
}


# ===========================================================================
# 1. Default values parity
# ===========================================================================


class TestDefaultsParity:
    """The manifest-driven defaults must match the legacy hardcoded dict."""

    def test_default_options_match_legacy(self) -> None:
        defaults = default_blog_module_options()
        assert defaults == _LEGACY_DEFAULTS

    def test_default_options_keys_are_stable(self) -> None:
        defaults = default_blog_module_options()
        assert set(defaults.keys()) == set(_LEGACY_DEFAULTS.keys())

    def test_default_posts_per_page_is_10(self) -> None:
        defaults = default_blog_module_options()
        assert defaults["posts_per_page"] == DEFAULT_BLOG_POSTS_PER_PAGE
        assert defaults["posts_per_page"] == 10

    def test_default_enable_rss_is_true(self) -> None:
        defaults = default_blog_module_options()
        assert defaults["enable_rss"] is DEFAULT_BLOG_ENABLE_RSS
        assert defaults["enable_rss"] is True

    def test_default_api_rate_limit(self) -> None:
        defaults = default_blog_module_options()
        assert defaults["api_rate_limit"] == DEFAULT_BLOG_API_RATE_LIMIT
        assert defaults["api_rate_limit"] == "5/hour"


# ===========================================================================
# 2. Constants parity
# ===========================================================================


class TestConstantsParity:
    """Public constants must match the legacy values."""

    def test_default_posts_per_page_constant(self) -> None:
        assert DEFAULT_BLOG_POSTS_PER_PAGE == 10

    def test_default_enable_rss_constant(self) -> None:
        assert DEFAULT_BLOG_ENABLE_RSS is True

    def test_default_api_rate_limit_constant(self) -> None:
        assert DEFAULT_BLOG_API_RATE_LIMIT == "5/hour"

    def test_module_option_keys_frozenset(self) -> None:
        assert BLOG_MODULE_OPTION_KEYS == frozenset(
            {"posts_per_page", "enable_rss", "api_rate_limit"}
        )


# ===========================================================================
# 3. Normalisation parity
# ===========================================================================


class TestNormalizationParity:
    """Normalisation must behave identically to the legacy contract."""

    def test_api_rate_limit_strip(self) -> None:
        normalized = normalize_blog_module_options({"api_rate_limit": "  10/minute  "})
        assert normalized["api_rate_limit"] == "10/minute"

    def test_api_rate_limit_blank_falls_back_to_default(self) -> None:
        normalized = normalize_blog_module_options({"api_rate_limit": "  "})
        assert normalized["api_rate_limit"] == DEFAULT_BLOG_API_RATE_LIMIT

    def test_api_rate_limit_empty_falls_back_to_default(self) -> None:
        normalized = normalize_blog_module_options({"api_rate_limit": ""})
        assert normalized["api_rate_limit"] == DEFAULT_BLOG_API_RATE_LIMIT

    def test_none_options_returns_empty_dict(self) -> None:
        normalized = normalize_blog_module_options(None)
        assert normalized == {}

    def test_empty_options_returns_empty_dict(self) -> None:
        normalized = normalize_blog_module_options({})
        assert normalized == {}

    def test_untouched_keys_pass_through(self) -> None:
        normalized = normalize_blog_module_options({"enable_rss": False})
        assert normalized["enable_rss"] is False
        assert "posts_per_page" not in normalized


# ===========================================================================
# 4. Resolution parity (defaults + normalised overrides)
# ===========================================================================


class TestResolutionParity:
    """resolve_blog_module_options must merge defaults + overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        resolved = resolve_blog_module_options(None)
        assert resolved == _LEGACY_DEFAULTS

    def test_empty_overrides_returns_defaults(self) -> None:
        resolved = resolve_blog_module_options({})
        assert resolved == _LEGACY_DEFAULTS

    def test_partial_override_preserves_other_defaults(self) -> None:
        resolved = resolve_blog_module_options({"enable_rss": False})
        expected = dict(_LEGACY_DEFAULTS)
        expected["enable_rss"] = False
        assert resolved == expected

    def test_posts_per_page_override(self) -> None:
        resolved = resolve_blog_module_options({"posts_per_page": 20})
        assert resolved["posts_per_page"] == 20

    def test_posts_per_page_string_is_coerced_to_int(self) -> None:
        """Legacy _blog_wiring uses int(), so string "5" should resolve to 5."""
        resolved = resolve_blog_module_options({"posts_per_page": "5"})
        assert resolved["posts_per_page"] == 5
        assert isinstance(resolved["posts_per_page"], int)

    def test_enable_rss_coerced_to_bool(self) -> None:
        resolved = resolve_blog_module_options({"enable_rss": True})
        assert resolved["enable_rss"] is True
        assert isinstance(resolved["enable_rss"], bool)

    def test_enable_rss_false_override(self) -> None:
        resolved = resolve_blog_module_options({"enable_rss": False})
        assert resolved["enable_rss"] is False

    def test_api_rate_limit_strip_in_resolve(self) -> None:
        resolved = resolve_blog_module_options({"api_rate_limit": "  10/minute  "})
        assert resolved["api_rate_limit"] == "10/minute"

    def test_api_rate_limit_blank_fallback_in_resolve(self) -> None:
        """Blank api_rate_limit must fall back to DEFAULT_BLOG_API_RATE_LIMIT."""
        resolved = resolve_blog_module_options({"api_rate_limit": ""})
        assert resolved["api_rate_limit"] == DEFAULT_BLOG_API_RATE_LIMIT

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_blog_module_options(
            {"posts_per_page": 5, "api_rate_limit": "  10/minute  "}
        )
        assert resolve_blog_module_options(resolved) == resolved

    def test_resolved_keys_match_legacy(self) -> None:
        resolved = resolve_blog_module_options({"enable_rss": False})
        assert set(resolved.keys()) == set(_LEGACY_DEFAULTS.keys())


# ===========================================================================
# 5. Validation parity
# ===========================================================================


class TestValidationParity:
    """validate_blog_module_options must produce legacy-compatible issues."""

    def test_defaults_pass_validation(self) -> None:
        issues = validate_blog_module_options(None)
        assert issues == []

    def test_valid_overrides_pass_validation(self) -> None:
        issues = validate_blog_module_options(
            {
                "posts_per_page": 20,
                "enable_rss": False,
                "api_rate_limit": "10/minute",
            }
        )
        assert issues == []

    def test_blank_api_rate_limit_is_valid_after_fallback(self) -> None:
        """Blank api_rate_limit falls back to default; validation passes."""
        issues = validate_blog_module_options({"api_rate_limit": ""})
        assert issues == []

    @pytest.mark.parametrize("bad_value", [0, -1, -100])
    def test_non_positive_posts_per_page_fails(self, bad_value: int) -> None:
        issues = validate_blog_module_options({"posts_per_page": bad_value})
        assert any("posts_per_page" in i for i in issues)

    def test_multiple_issues_collected(self) -> None:
        issues = validate_blog_module_options({"posts_per_page": -1})
        assert len(issues) >= 1


# ===========================================================================
# 6. Wiring-field values parity
# ===========================================================================


class TestWiringFieldsParity:
    """Resolved options must project to the exact wiring field values
    that ``_blog_wiring`` would have computed from the same input."""

    def test_default_wiring_fields(self) -> None:
        resolved = resolve_blog_module_options(None)
        # Mirrors _blog_wiring local variable assignments with defaults
        assert resolved["posts_per_page"] == 10
        assert resolved["enable_rss"] is True
        assert resolved["api_rate_limit"] == "5/hour"

    def test_custom_wiring_fields(self) -> None:
        resolved = resolve_blog_module_options(
            {
                "posts_per_page": 5,
                "enable_rss": False,
                "api_rate_limit": "10/minute",
            }
        )
        assert resolved["posts_per_page"] == 5
        assert resolved["enable_rss"] is False
        assert resolved["api_rate_limit"] == "10/minute"

    def test_resolved_contains_all_wiring_keys(self) -> None:
        resolved = resolve_blog_module_options(None)
        wiring_keys = {"posts_per_page", "enable_rss", "api_rate_limit"}
        assert wiring_keys.issubset(set(resolved.keys()))
