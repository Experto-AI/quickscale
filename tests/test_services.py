"""Tests for social module runtime services."""

from __future__ import annotations

import pytest
from django.core.cache import cache
from django.test import override_settings

from quickscale_modules_social.contracts import (
    DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST,
    DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINKS_CACHE_KEY,
    SOCIAL_LINK_TREE_PATH,
    SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_ERROR,
    SocialConfigurationError,
    get_social_runtime_settings,
    social_payload_status_code,
)
from quickscale_modules_social.models import SocialEmbed, SocialLink
from quickscale_modules_social.services import (
    build_social_embeds_payload,
    build_social_link_tree_payload,
    list_published_social_embeds,
    list_published_social_links,
)


def test_get_social_runtime_settings_normalizes_provider_allowlist() -> None:
    """Runtime settings should normalize provider aliases and preserve order."""
    with override_settings(
        QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=[" YouTube ", "twitter", "youtube"],
        QUICKSCALE_SOCIAL_LAYOUT_VARIANT="cards",
    ):
        snapshot = get_social_runtime_settings()

    assert snapshot.provider_allowlist == ("youtube", "x")
    assert snapshot.layout_variant == "cards"


def test_get_social_runtime_settings_rejects_disabling_all_public_surfaces() -> None:
    """The runtime contract must keep at least one social surface enabled."""
    with override_settings(
        QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=False,
        QUICKSCALE_SOCIAL_EMBEDS_ENABLED=False,
    ):
        with pytest.raises(SocialConfigurationError) as exc_info:
            get_social_runtime_settings()

    assert "link_tree_enabled or embeds_enabled enabled" in str(exc_info.value)


@pytest.mark.django_db
def test_list_published_social_links_uses_canonical_urls_and_invalidates_cache() -> (
    None
):
    """Published link payloads should normalize URLs and refresh after admin writes."""
    SocialLink.objects.create(
        title="QuickScale on LinkedIn",
        provider_name="",
        url="https://www.linkedin.com/company/quickscale/?utm_source=share",
        display_order=20,
    )

    initial_records = list_published_social_links()

    assert [record.title for record in initial_records] == ["QuickScale on LinkedIn"]
    assert initial_records[0].url == "https://www.linkedin.com/company/quickscale"

    SocialLink.objects.create(
        title="QuickScale on YouTube",
        provider_name="youtube",
        url="https://youtu.be/abc123?si=share",
        display_order=10,
    )

    refreshed_records = list_published_social_links()

    assert [record.title for record in refreshed_records] == [
        "QuickScale on YouTube",
        "QuickScale on LinkedIn",
    ]
    assert refreshed_records[0].url == "https://www.youtube.com/watch?v=abc123"

    with override_settings(
        QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"],
        QUICKSCALE_SOCIAL_LINKS_PER_PAGE=1,
    ):
        filtered_records = list_published_social_links()

    assert [record.title for record in filtered_records] == ["QuickScale on YouTube"]


@pytest.mark.django_db
def test_list_published_social_links_recovers_from_corrupt_cache_payload() -> None:
    """Corrupt cached link payloads should be ignored and refreshed from the DB."""
    SocialLink.objects.create(
        title="QuickScale on LinkedIn",
        provider_name="",
        url="https://www.linkedin.com/company/quickscale/",
        display_order=10,
    )
    cache.set(SOCIAL_LINKS_CACHE_KEY, [{"broken": True}], timeout=300)

    records = list_published_social_links()
    cached_payload = cache.get(SOCIAL_LINKS_CACHE_KEY)

    assert [record.provider_name for record in records] == ["linkedin"]
    assert cached_payload == [
        {
            "id": records[0].id,
            "title": "QuickScale on LinkedIn",
            "description": "",
            "provider_name": "linkedin",
            "provider_display_name": "LinkedIn",
            "url": "https://www.linkedin.com/company/quickscale",
            "source_url": "https://www.linkedin.com/company/quickscale/",
            "display_order": 10,
        }
    ]


@pytest.mark.django_db
def test_list_published_social_embeds_honors_runtime_toggle_and_filtering() -> None:
    """Published embed payloads should respect embed toggles and provider filtering."""
    SocialEmbed.objects.create(
        title="QuickScale on YouTube",
        provider_name="",
        url="https://youtu.be/alpha123",
        display_order=20,
    )
    SocialEmbed.objects.create(
        title="QuickScale on TikTok",
        provider_name="",
        url="https://vm.tiktok.com/ZM1234567/",
        display_order=10,
    )

    initial_records = list_published_social_embeds()

    assert [record.provider_name for record in initial_records] == ["tiktok", "youtube"]

    with override_settings(
        QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"],
        QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE=1,
    ):
        filtered_records = list_published_social_embeds()

    assert len(filtered_records) == 1
    assert filtered_records[0].provider_name == "youtube"

    with override_settings(QUICKSCALE_SOCIAL_EMBEDS_ENABLED=False):
        disabled_records = list_published_social_embeds()

    assert disabled_records == ()


@pytest.mark.django_db
def test_build_social_link_tree_payload_freezes_enabled_and_empty_semantics() -> None:
    """Managed link-tree payloads should expose deterministic empty and enabled states."""
    empty_payload = build_social_link_tree_payload()

    assert empty_payload == {
        "module": "social",
        "surface": "link_tree",
        "status": SOCIAL_STATUS_EMPTY,
        "enabled": True,
        "public_path": SOCIAL_LINK_TREE_PATH,
        "integration_base_path": SOCIAL_INTEGRATION_BASE_PATH,
        "integration_embeds_path": SOCIAL_INTEGRATION_EMBEDS_PATH,
        "provider_allowlist": list(DEFAULT_SOCIAL_PROVIDER_ALLOWLIST),
        "embed_provider_allowlist": list(DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST),
        "layout_variant": "list",
        "links_per_page": 24,
        "total_links": 0,
        "links": [],
        "error": None,
    }
    assert social_payload_status_code(empty_payload["status"]) == 200

    SocialLink.objects.create(
        title="QuickScale on YouTube",
        provider_name="youtube",
        url="https://youtu.be/abc123?si=share",
        description="Launch clips and demos.",
        display_order=10,
    )
    SocialLink.objects.create(
        title="QuickScale on LinkedIn",
        provider_name="",
        url="https://www.linkedin.com/company/quickscale/?utm_source=share",
        description="Company updates.",
        display_order=20,
    )

    enabled_payload = build_social_link_tree_payload()

    assert enabled_payload["status"] == SOCIAL_STATUS_ENABLED
    assert enabled_payload["enabled"] is True
    assert enabled_payload["total_links"] == 2
    assert enabled_payload["links"] == [
        {
            "id": enabled_payload["links"][0]["id"],
            "title": "QuickScale on YouTube",
            "description": "Launch clips and demos.",
            "provider_name": "youtube",
            "provider_display_name": "YouTube",
            "url": "https://www.youtube.com/watch?v=abc123",
            "source_url": "https://youtu.be/abc123?si=share",
            "display_order": 10,
        },
        {
            "id": enabled_payload["links"][1]["id"],
            "title": "QuickScale on LinkedIn",
            "description": "Company updates.",
            "provider_name": "linkedin",
            "provider_display_name": "LinkedIn",
            "url": "https://www.linkedin.com/company/quickscale",
            "source_url": "https://www.linkedin.com/company/quickscale/?utm_source=share",
            "display_order": 20,
        },
    ]
    assert social_payload_status_code(enabled_payload["status"]) == 200


def test_build_social_link_tree_payload_freezes_disabled_and_error_semantics() -> None:
    """Managed link-tree payloads should distinguish disabled surfaces from errors."""
    with override_settings(
        QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=False,
        QUICKSCALE_SOCIAL_EMBEDS_ENABLED=True,
    ):
        disabled_payload = build_social_link_tree_payload()

    assert disabled_payload == {
        "module": "social",
        "surface": "link_tree",
        "status": SOCIAL_STATUS_DISABLED,
        "enabled": False,
        "public_path": SOCIAL_LINK_TREE_PATH,
        "integration_base_path": SOCIAL_INTEGRATION_BASE_PATH,
        "integration_embeds_path": SOCIAL_INTEGRATION_EMBEDS_PATH,
        "provider_allowlist": list(DEFAULT_SOCIAL_PROVIDER_ALLOWLIST),
        "embed_provider_allowlist": list(DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST),
        "layout_variant": "list",
        "links_per_page": 24,
        "total_links": 0,
        "links": [],
        "error": None,
    }
    assert social_payload_status_code(disabled_payload["status"]) == 200

    with override_settings(
        QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=False,
        QUICKSCALE_SOCIAL_EMBEDS_ENABLED=False,
    ):
        error_payload = build_social_link_tree_payload()

    assert error_payload["status"] == SOCIAL_STATUS_ERROR
    assert error_payload["enabled"] is False
    assert error_payload["links"] == []
    assert error_payload["total_links"] == 0
    assert "link_tree_enabled or embeds_enabled enabled" in error_payload["error"]
    assert social_payload_status_code(error_payload["status"]) == 503


@pytest.mark.django_db
def test_build_social_embeds_payload_freezes_enabled_disabled_and_error_semantics() -> (
    None
):
    """Managed embed payloads should expose deterministic state and filtered items."""
    empty_payload = build_social_embeds_payload()

    assert empty_payload == {
        "module": "social",
        "surface": "embeds",
        "status": SOCIAL_STATUS_EMPTY,
        "enabled": True,
        "public_path": SOCIAL_EMBEDS_PATH,
        "integration_base_path": SOCIAL_INTEGRATION_BASE_PATH,
        "integration_embeds_path": SOCIAL_INTEGRATION_EMBEDS_PATH,
        "provider_allowlist": list(DEFAULT_SOCIAL_PROVIDER_ALLOWLIST),
        "embed_provider_allowlist": list(DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST),
        "cache_ttl_seconds": 300,
        "embeds_per_page": 12,
        "total_embeds": 0,
        "embeds": [],
        "error": None,
    }

    SocialEmbed.objects.create(
        title="QuickScale on YouTube",
        provider_name="",
        url="https://youtu.be/alpha123",
        description="Launch announcement clip.",
        display_order=20,
    )
    SocialEmbed.objects.create(
        title="QuickScale on TikTok",
        provider_name="",
        url="https://vm.tiktok.com/ZM1234567/",
        description="Short product teaser.",
        display_order=10,
    )

    with override_settings(
        QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"],
        QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE=1,
        QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS=600,
    ):
        enabled_payload = build_social_embeds_payload()

    assert enabled_payload == {
        "module": "social",
        "surface": "embeds",
        "status": SOCIAL_STATUS_ENABLED,
        "enabled": True,
        "public_path": SOCIAL_EMBEDS_PATH,
        "integration_base_path": SOCIAL_INTEGRATION_BASE_PATH,
        "integration_embeds_path": SOCIAL_INTEGRATION_EMBEDS_PATH,
        "provider_allowlist": ["youtube"],
        "embed_provider_allowlist": ["youtube"],
        "cache_ttl_seconds": 600,
        "embeds_per_page": 1,
        "total_embeds": 1,
        "embeds": [
            {
                "id": enabled_payload["embeds"][0]["id"],
                "title": "QuickScale on YouTube",
                "description": "Launch announcement clip.",
                "provider_name": "youtube",
                "provider_display_name": "YouTube",
                "url": "https://www.youtube.com/watch?v=alpha123",
                "source_url": "https://youtu.be/alpha123",
                "display_order": 20,
            }
        ],
        "error": None,
    }
    assert social_payload_status_code(enabled_payload["status"]) == 200

    with override_settings(QUICKSCALE_SOCIAL_EMBEDS_ENABLED=False):
        disabled_payload = build_social_embeds_payload()

    assert disabled_payload["status"] == SOCIAL_STATUS_DISABLED
    assert disabled_payload["enabled"] is False
    assert disabled_payload["embeds"] == []
    assert disabled_payload["total_embeds"] == 0
    assert disabled_payload["error"] is None

    with override_settings(QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["facebook"]):
        error_payload = build_social_embeds_payload()

    assert error_payload["status"] == SOCIAL_STATUS_ERROR
    assert error_payload["enabled"] is False
    assert error_payload["embeds"] == []
    assert error_payload["total_embeds"] == 0
    assert "must include TikTok or YouTube" in error_payload["error"]
    assert social_payload_status_code(error_payload["status"]) == 503
