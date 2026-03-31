"""Tests for the Phase A social contract foundations."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from quickscale_cli.social_contract import (
    DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST,
    DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LAYOUT_VARIANTS,
    SOCIAL_LINK_TREE_PATH,
    default_social_module_options,
    detect_social_provider,
    normalize_social_provider,
    normalize_social_provider_allowlist,
    normalize_social_url,
    resolve_social_target,
    social_provider_supports_embeds,
    validate_social_module_options,
)
from quickscale_core.manifest.loader import load_manifest_from_path

REPO_ROOT = Path(__file__).resolve().parents[2]
SOCIAL_MANIFEST_PATH = REPO_ROOT / "quickscale_modules" / "social" / "module.yml"


def _load_social_manifest() -> Any:
    return load_manifest_from_path(SOCIAL_MANIFEST_PATH)


def test_social_routes_are_fixed() -> None:
    """The public social routes must stay fixed and config-free."""
    assert SOCIAL_LINK_TREE_PATH == "/social"
    assert SOCIAL_EMBEDS_PATH == "/social/embeds"
    assert SOCIAL_INTEGRATION_BASE_PATH == "/_quickscale/social/"
    assert SOCIAL_INTEGRATION_EMBEDS_PATH == "/_quickscale/social/embeds/"


def test_default_social_embed_provider_allowlist_is_stable() -> None:
    """The embed-capable provider set should remain explicitly constrained."""
    assert DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST == ("tiktok", "youtube")


@pytest.mark.parametrize(
    ("raw_provider", "expected"),
    [
        ("Twitter", "x"),
        ("x-twitter", "x"),
        ("Tik Tok", "tiktok"),
        ("YouTube", "youtube"),
        ("linked_in", "linkedin"),
    ],
)
def test_normalize_social_provider_aliases(
    raw_provider: str,
    expected: str,
) -> None:
    """Provider aliases should collapse to the canonical provider names."""
    assert normalize_social_provider(raw_provider) == expected


def test_normalize_social_provider_allowlist_preserves_order_and_deduplicates() -> None:
    """Allowlist normalization should preserve first-seen canonical order."""
    normalized = normalize_social_provider_allowlist(
        [" YouTube ", "twitter", "youtube", "Tik Tok", "twitter"]
    )

    assert normalized == ["youtube", "x", "tiktok"]


@pytest.mark.parametrize(
    ("url", "expected_provider"),
    [
        ("youtube.com/watch?v=abc123", "youtube"),
        ("https://youtu.be/abc123", "youtube"),
        ("https://mobile.twitter.com/QuickScaleHQ", "x"),
        ("https://www.instagram.com/quickscale/", "instagram"),
        ("https://fb.watch/quickscale", "facebook"),
        ("https://www.linkedin.com/company/quickscale", "linkedin"),
        ("https://vm.tiktok.com/ZM1234567/", "tiktok"),
    ],
)
def test_detect_social_provider_from_supported_urls(
    url: str,
    expected_provider: str,
) -> None:
    """Host normalization should detect every supported provider family."""
    assert detect_social_provider(url) == expected_provider


def test_resolve_social_target_normalizes_x_urls() -> None:
    """X/Twitter URLs should normalize to the fixed X host without fragments."""
    resolved = resolve_social_target(
        "https://mobile.twitter.com/QuickScaleHQ/status/123?utm_source=share#top"
    )

    assert resolved.provider == "x"
    assert resolved.url == "https://x.com/QuickScaleHQ/status/123"


def test_normalize_social_url_normalizes_youtube_short_links() -> None:
    """YouTube short links should normalize to the canonical watch URL."""
    normalized = normalize_social_url("https://youtu.be/abc123?si=share")

    assert normalized == "https://www.youtube.com/watch?v=abc123"


def test_normalize_social_url_strips_tracking_from_link_tree_urls() -> None:
    """Canonical link-tree URLs should drop tracking params and trailing slashes."""
    normalized = normalize_social_url(
        "https://www.instagram.com/quickscale/?igshid=abc&utm_source=share"
    )

    assert normalized == "https://www.instagram.com/quickscale"


def test_resolve_social_target_rejects_unknown_hosts() -> None:
    """Unsupported providers should fail fast with a clear contract error."""
    with pytest.raises(ValueError, match="Unsupported social provider URL"):
        resolve_social_target("https://example.com/not-supported")


def test_social_provider_supports_embeds_only_for_approved_set() -> None:
    """Only TikTok and YouTube should report embed support in v0.79.0."""
    assert social_provider_supports_embeds("youtube") is True
    assert social_provider_supports_embeds("tiktok") is True
    assert social_provider_supports_embeds("instagram") is False
    assert social_provider_supports_embeds("x") is False


def test_validate_social_module_options_accepts_defaults() -> None:
    """The default Phase A contract should validate cleanly."""
    assert validate_social_module_options(default_social_module_options()) == []


def test_validate_social_module_options_rejects_disabled_public_surfaces() -> None:
    """The contract must keep at least one public surface enabled."""
    issues = validate_social_module_options(
        {
            "link_tree_enabled": False,
            "embeds_enabled": False,
        }
    )

    assert (
        "modules.social must leave link_tree_enabled or embeds_enabled enabled"
        in issues
    )


def test_validate_social_module_options_requires_embed_provider_when_embeds_enabled() -> (
    None
):
    """Embed support requires an allowlisted provider that actually supports embeds."""
    issues = validate_social_module_options(
        {
            "provider_allowlist": ["facebook", "instagram", "linkedin", "x"],
            "embeds_enabled": True,
        }
    )

    assert (
        "modules.social.provider_allowlist must include tiktok or youtube when embeds_enabled is true"
        in issues
    )


def test_social_manifest_defaults_match_cli_contract_defaults() -> None:
    """The social manifest should stay in lockstep with the CLI contract defaults."""
    manifest = _load_social_manifest()
    defaults = default_social_module_options()

    assert set(manifest.mutable_options.keys()) == set(defaults.keys())
    assert manifest.mutable_options["provider_allowlist"].default == list(
        DEFAULT_SOCIAL_PROVIDER_ALLOWLIST
    )
    assert manifest.mutable_options["layout_variant"].default in SOCIAL_LAYOUT_VARIANTS


def test_social_manifest_keeps_route_fields_out_of_config_surface() -> None:
    """Route-bearing config must not leak into the social manifest surface."""
    manifest = _load_social_manifest()
    config_keys = set(manifest.mutable_options.keys()) | set(
        manifest.immutable_options.keys()
    )

    assert {"public_path", "link_tree_path", "embeds_path", "slug"}.isdisjoint(
        config_keys
    )
