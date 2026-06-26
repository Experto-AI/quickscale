"""Full API tests for quickscale_core.manifest.social_manifest.

Covers provider metadata resolution, URL detection/resolution, URL
normalization helpers, payload status helpers, and remaining managed-file
renderers that the existing test_social_managed_views_template.py does
not reach.
"""

from __future__ import annotations

import pytest

from quickscale_core.manifest.social_manifest import (
    DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST,
    DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
    SOCIAL_LAYOUT_VARIANTS,
    SOCIAL_PAYLOAD_HTTP_STATUS,
    SOCIAL_PAYLOAD_STATUSES,
    SOCIAL_PROVIDER_CATALOG,
    SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_ERROR,
    ResolvedSocialTarget,
    SocialProviderMetadata,
    detect_social_provider,
    get_social_provider_metadata,
    load_social_manifest,
    normalize_social_provider,
    normalize_social_url,
    render_social_managed_init_module,
    render_social_managed_urls_module,
    resolve_social_target,
    social_payload_status_code,
    social_provider_supports_embeds,
)


# ===================================================================
# Constants and data structures
# ===================================================================


class TestSocialConstants:
    """Tests for module-level constants and dataclasses."""

    def test_social_layout_variants(self) -> None:
        assert "list" in SOCIAL_LAYOUT_VARIANTS
        assert "cards" in SOCIAL_LAYOUT_VARIANTS
        assert "grid" in SOCIAL_LAYOUT_VARIANTS

    def test_social_payload_statuses(self) -> None:
        assert SOCIAL_STATUS_ENABLED in SOCIAL_PAYLOAD_STATUSES
        assert SOCIAL_STATUS_EMPTY in SOCIAL_PAYLOAD_STATUSES
        assert SOCIAL_STATUS_DISABLED in SOCIAL_PAYLOAD_STATUSES
        assert SOCIAL_STATUS_ERROR in SOCIAL_PAYLOAD_STATUSES

    def test_social_payload_http_status(self) -> None:
        assert SOCIAL_PAYLOAD_HTTP_STATUS[SOCIAL_STATUS_ENABLED] == 200
        assert SOCIAL_PAYLOAD_HTTP_STATUS[SOCIAL_STATUS_ERROR] == 503

    def test_provider_catalog_contains_expected(self) -> None:
        names = {p.name for p in SOCIAL_PROVIDER_CATALOG}
        assert "facebook" in names
        assert "instagram" in names
        assert "linkedin" in names
        assert "tiktok" in names
        assert "x" in names
        assert "youtube" in names

    def test_provider_catalog_metadata(self) -> None:
        youtube = next(p for p in SOCIAL_PROVIDER_CATALOG if p.name == "youtube")
        assert youtube.display_name == "YouTube"
        assert youtube.supports_embeds is True
        assert "youtu.be" in youtube.hosts

        facebook = next(p for p in SOCIAL_PROVIDER_CATALOG if p.name == "facebook")
        assert facebook.supports_embeds is False
        assert "fb" in facebook.aliases

    def test_default_allowlists(self) -> None:
        assert "youtube" in DEFAULT_SOCIAL_PROVIDER_ALLOWLIST
        assert "facebook" in DEFAULT_SOCIAL_PROVIDER_ALLOWLIST
        assert "youtube" in DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST
        assert "tiktok" in DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST
        assert "facebook" not in DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST

    def test_resolved_social_target_dataclass(self) -> None:
        target = ResolvedSocialTarget(
            provider="youtube", url="https://www.youtube.com/watch?v=abc123"
        )
        assert target.provider == "youtube"
        assert "youtube.com" in target.url

    def test_social_provider_metadata_dataclass(self) -> None:
        meta = SocialProviderMetadata(
            name="test",
            display_name="Test",
            supports_embeds=True,
            aliases=("t",),
            hosts=("test.com",),
        )
        assert meta.name == "test"
        assert meta.supports_embeds is True


# ===================================================================
# normalize_social_provider
# ===================================================================


class TestNormalizeSocialProvider:
    """Tests for normalize_social_provider."""

    def test_canonical_names(self) -> None:
        assert normalize_social_provider("facebook") == "facebook"
        assert normalize_social_provider("instagram") == "instagram"
        assert normalize_social_provider("linkedin") == "linkedin"
        assert normalize_social_provider("tiktok") == "tiktok"
        assert normalize_social_provider("x") == "x"
        assert normalize_social_provider("youtube") == "youtube"

    def test_aliases(self) -> None:
        assert normalize_social_provider("fb") == "facebook"
        assert normalize_social_provider("ig") == "instagram"
        assert normalize_social_provider("linked-in") == "linkedin"
        assert normalize_social_provider("tik-tok") == "tiktok"
        assert normalize_social_provider("twitter") == "x"
        assert normalize_social_provider("x-twitter") == "x"
        assert normalize_social_provider("you-tube") == "youtube"

    def test_case_insensitive(self) -> None:
        assert normalize_social_provider("Facebook") == "facebook"
        assert normalize_social_provider("TWITTER") == "x"

    def test_whitespace_stripped(self) -> None:
        assert normalize_social_provider("  youtube  ") == "youtube"

    def test_special_chars_handled(self) -> None:
        assert normalize_social_provider("you/tube") == "youtube"
        assert normalize_social_provider("you tube") == "youtube"
        assert normalize_social_provider("x_twitter") == "x"

    def test_empty_or_invalid_returns_none(self) -> None:
        assert normalize_social_provider("") is None
        assert normalize_social_provider("!!!") is None
        assert normalize_social_provider("  ") is None
        assert normalize_social_provider("unknown") is None


# ===================================================================
# get_social_provider_metadata
# ===================================================================


class TestGetSocialProviderMetadata:
    """Tests for get_social_provider_metadata."""

    def test_known_provider(self) -> None:
        meta = get_social_provider_metadata("youtube")
        assert meta is not None
        assert meta.name == "youtube"
        assert meta.supports_embeds is True

    def test_known_provider_via_alias(self) -> None:
        meta = get_social_provider_metadata("twitter")
        assert meta is not None
        assert meta.name == "x"

    def test_unknown_provider_returns_none(self) -> None:
        assert get_social_provider_metadata("unknown") is None
        assert get_social_provider_metadata("") is None

    def test_social_provider_supports_embeds(self) -> None:
        assert social_provider_supports_embeds("youtube") is True
        assert social_provider_supports_embeds("tiktok") is True
        assert social_provider_supports_embeds("facebook") is False
        assert social_provider_supports_embeds("unknown") is False


# ===================================================================
# social_payload_status_code
# ===================================================================


class TestSocialPayloadStatusCode:
    """Tests for social_payload_status_code."""

    def test_known_statuses(self) -> None:
        assert social_payload_status_code(SOCIAL_STATUS_ENABLED) == 200
        assert social_payload_status_code(SOCIAL_STATUS_EMPTY) == 200
        assert social_payload_status_code(SOCIAL_STATUS_DISABLED) == 200
        assert social_payload_status_code(SOCIAL_STATUS_ERROR) == 503

    def test_case_insensitive(self) -> None:
        assert social_payload_status_code("ENABLED") == 200

    def test_unknown_status_falls_back_to_error(self) -> None:
        assert social_payload_status_code("unknown") == 503


# ===================================================================
# URL helpers — _coerce_social_url (tested through resolve_social_target)
# ===================================================================


class TestResolveSocialTarget:
    """Tests for resolve_social_target — the main URL resolution entry point."""

    def test_facebook_url(self) -> None:
        target = resolve_social_target("https://www.facebook.com/myprofile")
        assert target.provider == "facebook"
        assert "www.facebook.com" in target.url
        assert target.url.startswith("https://")

    def test_instagram_url(self) -> None:
        target = resolve_social_target("https://instagram.com/user")
        assert target.provider == "instagram"
        assert "www.instagram.com" in target.url

    def test_linkedin_url(self) -> None:
        target = resolve_social_target("https://linkedin.com/in/user")
        assert target.provider == "linkedin"
        assert "www.linkedin.com" in target.url

    def test_tiktok_url(self) -> None:
        target = resolve_social_target("https://www.tiktok.com/@user")
        assert target.provider == "tiktok"
        assert "www.tiktok.com" in target.url

    def test_tiktok_vm_url(self) -> None:
        target = resolve_social_target("https://vm.tiktok.com/abc123")
        assert target.provider == "tiktok"
        assert "vm.tiktok.com" in target.url

    def test_x_url(self) -> None:
        target = resolve_social_target("https://twitter.com/user")
        assert target.provider == "x"
        assert "x.com" in target.url

    def test_youtube_url(self) -> None:
        target = resolve_social_target("https://www.youtube.com/watch?v=abc123")
        assert target.provider == "youtube"
        assert "www.youtube.com" in target.url
        assert "v=abc123" in target.url

    def test_youtu_be_url(self) -> None:
        target = resolve_social_target("https://youtu.be/abc123")
        assert target.provider == "youtube"
        assert "www.youtube.com" in target.url
        assert "v=abc123" in target.url

    def test_youtube_url_with_tracking_params_stripped(self) -> None:
        target = resolve_social_target(
            "https://www.youtube.com/watch?v=abc123&utm_source=twitter&gclid=abc"
        )
        assert "utm_source" not in target.url
        assert "gclid" not in target.url
        assert "v=abc123" in target.url

    def test_youtube_playlist(self) -> None:
        target = resolve_social_target("https://www.youtube.com/playlist?list=PLabc123")
        assert target.provider == "youtube"
        # Playlist path preserved without watch conversion
        assert "playlist" in target.url

    def test_schemeless_url(self) -> None:
        target = resolve_social_target("www.facebook.com/myprofile")
        assert target.provider == "facebook"

    def test_with_provider_override(self) -> None:
        target = resolve_social_target("https://x.com/user", provider="twitter")
        assert target.provider == "x"

    def test_provider_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="Social URL does not match"):
            resolve_social_target("https://facebook.com/user", provider="twitter")

    def test_unsupported_provider_override_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported social provider"):
            resolve_social_target("https://facebook.com/user", provider="unknown")

    def test_unsupported_provider_url_raises(self) -> None:
        with pytest.raises(ValueError, match="Unsupported social provider URL"):
            resolve_social_target("https://unsupported.example.com")

    def test_blank_url_raises(self) -> None:
        with pytest.raises(ValueError, match="cannot be blank"):
            resolve_social_target("")

    def test_http_scheme_accepted(self) -> None:
        target = resolve_social_target("http://facebook.com/user")
        assert target.provider == "facebook"
        assert target.url.startswith("https://")

    def test_double_slash_url(self) -> None:
        target = resolve_social_target("//facebook.com/user")
        assert target.provider == "facebook"

    def test_missing_host_raises(self) -> None:
        with pytest.raises(ValueError, match="must include a hostname"):
            resolve_social_target("https://")


# ===================================================================
# detect_social_provider
# ===================================================================


class TestDetectSocialProvider:
    """Tests for detect_social_provider."""

    def test_detect_facebook(self) -> None:
        assert detect_social_provider("https://www.facebook.com/user") == "facebook"

    def test_detect_instagram(self) -> None:
        assert detect_social_provider("https://instagram.com/user") == "instagram"

    def test_detect_youtube(self) -> None:
        assert detect_social_provider("https://youtu.be/abc") == "youtube"

    def test_detect_x(self) -> None:
        assert detect_social_provider("https://x.com/user") == "x"

    def test_unknown_url_returns_none(self) -> None:
        assert detect_social_provider("https://unknown.example.com") is None

    def test_blank_url_returns_none(self) -> None:
        assert detect_social_provider("") is None

    def test_schemeless_detection(self) -> None:
        assert detect_social_provider("facebook.com/user") == "facebook"

    def test_detect_tiktok(self) -> None:
        assert detect_social_provider("https://vm.tiktok.com/abc") == "tiktok"


# ===================================================================
# normalize_social_url
# ===================================================================


class TestNormalizeSocialUrl:
    """Tests for normalize_social_url."""

    def test_normalize_youtube(self) -> None:
        url = normalize_social_url("https://www.youtube.com/watch?v=abc123")
        assert "v=abc123" in url
        assert url.startswith("https://")

    def test_normalize_with_provider(self) -> None:
        url = normalize_social_url("https://x.com/user", provider="twitter")
        assert "x.com" in url


# ===================================================================
# load_social_manifest
# ===================================================================


class TestLoadSocialManifest:
    """Tests for load_social_manifest."""

    def test_load_social_manifest_returns_module_manifest(self) -> None:
        manifest = load_social_manifest()
        assert manifest is not None
        assert manifest.name == "social"


# ===================================================================
# Remaining renderers
# ===================================================================


class TestSocialManagedFileRenderers:
    """Tests for social managed-file renderers beyond social_views."""

    def test_render_social_managed_init_module(self) -> None:
        content = render_social_managed_init_module()
        assert "QuickScale managed integration package" in content
        assert "DO NOT EDIT" in content

    def test_render_social_managed_urls_module(self) -> None:
        content = render_social_managed_urls_module()
        assert "social_embeds_payload" in content
        assert "social_link_tree_payload" in content
        assert "urlpatterns" in content
        assert "quickscale-social-link-tree" in content
        assert "quickscale-social-embeds" in content
        assert "app_name = " in content
