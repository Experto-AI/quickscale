"""Additional edge-case coverage for the CLI social contract helpers."""

from __future__ import annotations

import pytest

from quickscale_cli.social_contract import (
    get_social_provider_metadata,
    normalize_social_module_options,
    normalize_social_provider,
    normalize_social_provider_allowlist,
    resolve_social_module_options,
    resolve_social_target,
    social_payload_status_code,
    validate_social_module_options,
)


def test_normalize_social_provider_rejects_blank_tokens() -> None:
    assert normalize_social_provider("") is None
    assert normalize_social_provider("   ") is None
    assert normalize_social_provider(None) is None


def test_get_social_provider_metadata_returns_none_for_unknown_token() -> None:
    assert get_social_provider_metadata("unknown-network") is None


def test_normalize_social_provider_allowlist_accepts_scalar_inputs() -> None:
    assert normalize_social_provider_allowlist("youtube, twitter, youtube") == [
        "youtube",
        "x",
    ]
    assert normalize_social_provider_allowlist(123) == ["123"]


def test_normalize_social_module_options_normalizes_known_fields_only() -> None:
    normalized = normalize_social_module_options(
        {
            "provider_allowlist": [" YouTube ", "twitter"],
            "layout_variant": "  GRID ",
            "links_per_page": 48,
        }
    )

    assert normalized == {
        "provider_allowlist": ["youtube", "x"],
        "layout_variant": "grid",
        "links_per_page": 48,
    }


def test_resolve_social_module_options_reapplies_default_allowlist_normalization() -> (
    None
):
    resolved = resolve_social_module_options(
        {
            "provider_allowlist": ["twitter", "youtube", "twitter"],
            "layout_variant": "Cards",
        }
    )

    assert resolved["provider_allowlist"] == ["x", "youtube"]
    assert resolved["layout_variant"] == "cards"
    assert resolved["cache_ttl_seconds"] == 300


def test_validate_social_module_options_reports_invalid_scalar_values() -> None:
    issues = validate_social_module_options(
        {
            "link_tree_enabled": "yes",
            "embeds_enabled": "yes",
            "layout_variant": "carousel",
            "provider_allowlist": [],
            "cache_ttl_seconds": 0,
            "links_per_page": "many",
            "embeds_per_page": 0,
        }
    )

    assert "modules.social.link_tree_enabled must be a boolean" in issues
    assert "modules.social.embeds_enabled must be a boolean" in issues
    assert "modules.social.layout_variant must be one of: list, cards, grid" in issues
    assert "modules.social.provider_allowlist cannot be empty" in issues
    assert "modules.social.cache_ttl_seconds must be at least 1" in issues
    assert "modules.social.links_per_page must be an integer" in issues
    assert "modules.social.embeds_per_page must be at least 1" in issues


def test_validate_social_module_options_reports_unknown_provider() -> None:
    issues = validate_social_module_options(
        {
            "provider_allowlist": ["youtube", "mystery-network"],
            "embeds_enabled": False,
        }
    )

    assert (
        "modules.social.provider_allowlist contains unsupported providers: mystery-network"
        in issues
    )


def test_social_payload_status_code_normalizes_case_and_whitespace() -> None:
    assert social_payload_status_code(" Enabled ") == 200


def test_resolve_social_target_rejects_invalid_provider_declarations() -> None:
    with pytest.raises(ValueError, match="Unsupported social provider"):
        resolve_social_target(
            "https://www.youtube.com/watch?v=abc123",
            provider="not-a-provider",
        )

    with pytest.raises(
        ValueError,
        match="Social URL does not match the declared provider",
    ):
        resolve_social_target(
            "https://www.youtube.com/watch?v=abc123",
            provider="tiktok",
        )


@pytest.mark.parametrize(
    ("url", "message"),
    [
        ("", "Social URLs cannot be blank"),
        ("ftp://example.com/resource", "Social URLs must use http or https"),
        ("https:///missing-host", "Social URLs must include a hostname"),
    ],
)
def test_resolve_social_target_rejects_invalid_urls(url: str, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        resolve_social_target(url)


def test_resolve_social_target_normalizes_youtube_watch_queries() -> None:
    resolved = resolve_social_target(
        "https://www.youtube.com/watch?v=abc123&list=PL123&utm_source=share&si=dropme"
    )

    assert resolved.provider == "youtube"
    assert resolved.url == "https://www.youtube.com/watch?v=abc123&list=PL123"


def test_resolve_social_target_keeps_non_watch_youtube_paths_without_query() -> None:
    resolved = resolve_social_target("https://www.youtube.com/shorts/abc123?si=share")

    assert resolved.provider == "youtube"
    assert resolved.url == "https://www.youtube.com/shorts/abc123"


def test_resolve_social_target_normalizes_supported_provider_hosts() -> None:
    assert (
        resolve_social_target("https://www.linkedin.com/company/quickscale/").url
        == "https://www.linkedin.com/company/quickscale"
    )
    assert (
        resolve_social_target("https://vm.tiktok.com/ZM1234567/").url
        == "https://vm.tiktok.com/ZM1234567"
    )
    assert (
        resolve_social_target("https://fb.watch/quickscale/").url
        == "https://fb.watch/quickscale"
    )
