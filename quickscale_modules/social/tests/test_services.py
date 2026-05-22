"""Tests for social module runtime services."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError, ProgrammingError
from django.test import override_settings

from quickscale_modules_social.contracts import (
    SOCIAL_EMBEDS_CACHE_KEY,
    DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST,
    DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_EMBED_RESOLUTION_ERROR,
    SOCIAL_EMBED_RESOLUTION_RESOLVED,
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
    normalize_social_provider_allowlist,
    normalize_social_url,
    resolve_social_embed_metadata,
    resolve_social_target,
    social_payload_status_code,
)
from quickscale_modules_social.models import SocialEmbed, SocialLink
from quickscale_modules_social.services import (
    build_social_embeds_payload,
    build_social_link_tree_payload,
    list_published_social_embeds,
    list_published_social_links,
)


TestFunction = TypeVar("TestFunction", bound=Callable[..., object])
django_db = cast(Callable[[TestFunction], TestFunction], pytest.mark.django_db)


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


@django_db
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


@django_db
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


def test_build_social_link_tree_payload_uses_empty_state_for_missing_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing link tables should degrade to the existing empty public payload."""

    def raise_missing_table(*args: object, **kwargs: object) -> object:
        raise OperationalError(
            'relation "quickscale_modules_social_sociallink" does not exist'
        )

    cache.delete(SOCIAL_LINKS_CACHE_KEY)
    monkeypatch.setattr(SocialLink.objects, "filter", raise_missing_table)

    payload = build_social_link_tree_payload()

    assert payload["status"] == SOCIAL_STATUS_EMPTY
    assert payload["enabled"] is True
    assert payload["links"] == []
    assert payload["total_links"] == 0
    assert payload["error"] is None
    assert cache.get(SOCIAL_LINKS_CACHE_KEY) is None


def test_list_published_social_links_reraises_unrelated_database_faults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only missing-table faults should be absorbed by the public fallback."""

    def raise_unrelated_error(*args: object, **kwargs: object) -> object:
        raise OperationalError("database is locked")

    monkeypatch.setattr(SocialLink.objects, "filter", raise_unrelated_error)

    with pytest.raises(OperationalError, match="database is locked"):
        list_published_social_links()


@django_db
def test_list_published_social_embeds_honors_runtime_toggle_and_filtering() -> None:
    """Published embed payloads should respect embed toggles and provider filtering."""
    SocialEmbed.objects.create(
        title="QuickScale on YouTube",
        provider_name="",
        url="https://www.youtube.com/shorts/alpha123",
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
    assert initial_records[0].resolution_status == SOCIAL_EMBED_RESOLUTION_ERROR
    assert initial_records[0].embed_url is None
    assert "canonical TikTok video URL" in (initial_records[0].resolution_error or "")
    assert initial_records[1].resolution_status == SOCIAL_EMBED_RESOLUTION_RESOLVED
    assert (
        initial_records[1].embed_url == "https://www.youtube.com/embed/alpha123?rel=0"
    )

    with override_settings(
        QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"],
        QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE=1,
    ):
        filtered_records = list_published_social_embeds()

    assert len(filtered_records) == 1
    assert filtered_records[0].provider_name == "youtube"
    assert (
        filtered_records[0].embed_url == "https://www.youtube.com/embed/alpha123?rel=0"
    )

    with override_settings(QUICKSCALE_SOCIAL_EMBEDS_ENABLED=False):
        disabled_records = list_published_social_embeds()

    assert disabled_records == ()


@django_db
def test_list_published_social_embeds_recovers_from_non_list_cache_payload() -> None:
    """Non-list embed cache payloads should be ignored and refreshed from the DB."""
    SocialEmbed.objects.create(
        title="QuickScale on YouTube",
        provider_name="",
        url="https://www.youtube.com/shorts/alpha123",
        display_order=10,
    )
    cache.set(SOCIAL_EMBEDS_CACHE_KEY, {"broken": True}, timeout=300)

    records = list_published_social_embeds()
    cached_payload = cast(list[dict[str, object]], cache.get(SOCIAL_EMBEDS_CACHE_KEY))

    assert [record.provider_name for record in records] == ["youtube"]
    assert cached_payload[0]["id"] == records[0].id
    assert cached_payload[0]["provider_name"] == "youtube"
    assert (
        cached_payload[0]["embed_url"] == "https://www.youtube.com/embed/alpha123?rel=0"
    )


@django_db
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
    links = cast(list[dict[str, object]], enabled_payload["links"])

    assert enabled_payload["status"] == SOCIAL_STATUS_ENABLED
    assert enabled_payload["enabled"] is True
    assert enabled_payload["total_links"] == 2
    assert enabled_payload["links"] == [
        {
            "id": links[0]["id"],
            "title": "QuickScale on YouTube",
            "description": "Launch clips and demos.",
            "provider_name": "youtube",
            "provider_display_name": "YouTube",
            "url": "https://www.youtube.com/watch?v=abc123",
            "source_url": "https://youtu.be/abc123?si=share",
            "display_order": 10,
        },
        {
            "id": links[1]["id"],
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


def test_contract_helpers_normalize_urls_and_raise_specific_errors() -> None:
    """Contract helpers should keep normalization and validation edge cases stable."""
    assert normalize_social_provider_allowlist(None) == []
    assert normalize_social_provider_allowlist(" youtube , twitter ") == [
        "youtube",
        "x",
    ]
    assert normalize_social_provider_allowlist(123) == ["123"]
    assert social_payload_status_code("unexpected") == 503
    assert normalize_social_url("//youtu.be/abc123?si=share") == (
        "https://www.youtube.com/watch?v=abc123"
    )
    assert (
        normalize_social_url(
            "youtube.com/watch?v=abc123&list=PL123&utm_source=share&ref=campaign"
        )
        == "https://www.youtube.com/watch?v=abc123&list=PL123"
    )
    assert normalize_social_url("x.com/quickscale///") == "https://x.com/quickscale"

    youtube_embed = resolve_social_embed_metadata(
        "https://www.youtube.com/watch?v=abc123&list=PL123&utm_source=share",
        provider="youtube",
    )
    assert youtube_embed.embed_url == (
        "https://www.youtube.com/embed/abc123?rel=0&list=PL123"
    )

    with pytest.raises(ValueError, match="Social URLs cannot be blank"):
        normalize_social_url("   ")
    with pytest.raises(ValueError, match="Social URLs must use http or https"):
        normalize_social_url("ftp://www.linkedin.com/company/quickscale")
    with pytest.raises(ValueError, match="Unsupported social provider"):
        resolve_social_target(
            "https://www.youtube.com/watch?v=abc123",
            provider="mastodon",
        )
    with pytest.raises(ValueError, match="does not match the declared provider"):
        resolve_social_target(
            "https://www.youtube.com/watch?v=abc123",
            provider="linkedin",
        )
    with pytest.raises(
        ValueError,
        match="Embeds support only TikTok and YouTube in v0.79.0.",
    ):
        resolve_social_embed_metadata("https://www.linkedin.com/company/quickscale")
    with pytest.raises(
        ValueError,
        match="derive a canonical YouTube video id",
    ):
        resolve_social_embed_metadata("https://www.youtube.com/watch?list=PL123")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        (
            {"QUICKSCALE_SOCIAL_LINK_TREE_ENABLED": "sometimes"},
            "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED must be a boolean",
        ),
        (
            {"QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE": 0},
            "QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE must be at least 1",
        ),
        (
            {"QUICKSCALE_SOCIAL_LAYOUT_VARIANT": "mosaic"},
            "QUICKSCALE_SOCIAL_LAYOUT_VARIANT must be one of: list, cards, grid",
        ),
        (
            {"QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": []},
            "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST cannot be empty",
        ),
        (
            {"QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": ["youtube", "mastodon"]},
            "contains unsupported providers: mastodon",
        ),
        (
            {"QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST": ["linkedin"]},
            "must include TikTok or YouTube when embeds are enabled",
        ),
    ],
)
def test_get_social_runtime_settings_rejects_additional_invalid_values(
    overrides: dict[str, object],
    message: str,
) -> None:
    """Runtime settings should reject invalid types and unsupported provider mixes."""
    with override_settings(**overrides):
        with pytest.raises(SocialConfigurationError, match=message):
            get_social_runtime_settings()


@django_db
def test_social_models_enforce_guardrails_and_invalidate_cache() -> None:
    """Social models should validate runtime guardrails and clear their cache keys."""
    cache.set(SOCIAL_LINKS_CACHE_KEY, ["stale"], timeout=300)
    link = SocialLink.objects.create(
        title="QuickScale on YouTube",
        provider_name="youtube",
        url="https://youtu.be/abc123?si=share",
        display_order=10,
    )

    assert cache.get(SOCIAL_LINKS_CACHE_KEY) is None

    cache.set(SOCIAL_LINKS_CACHE_KEY, ["stale"], timeout=300)
    link.delete()

    assert cache.get(SOCIAL_LINKS_CACHE_KEY) is None

    with override_settings(QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"]):
        invalid_link = SocialLink(
            title="QuickScale on LinkedIn",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
        )
        with pytest.raises(ValidationError) as exc_info:
            invalid_link.full_clean()

    assert exc_info.value.message_dict["provider_name"] == [
        "This provider is not allowlisted by QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST."
    ]

    with override_settings(
        QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["linkedin", "youtube"]
    ):
        invalid_embed = SocialEmbed(
            title="QuickScale on LinkedIn",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
        )
        with pytest.raises(ValidationError) as exc_info:
            invalid_embed.full_clean()

    assert exc_info.value.message_dict["provider_name"] == [
        "Embeds support only TikTok and YouTube in v0.79.0."
    ]


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
    error_message = cast(str, error_payload["error"])

    assert error_payload["status"] == SOCIAL_STATUS_ERROR
    assert error_payload["enabled"] is False
    assert error_payload["links"] == []
    assert error_payload["total_links"] == 0
    assert "link_tree_enabled or embeds_enabled enabled" in error_message
    assert social_payload_status_code(error_payload["status"]) == 503


@django_db
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
        url="https://www.youtube.com/shorts/alpha123",
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
    embeds = cast(list[dict[str, object]], enabled_payload["embeds"])

    assert enabled_payload["module"] == "social"
    assert enabled_payload["surface"] == "embeds"
    assert enabled_payload["status"] == SOCIAL_STATUS_ENABLED
    assert enabled_payload["enabled"] is True
    assert enabled_payload["public_path"] == SOCIAL_EMBEDS_PATH
    assert enabled_payload["integration_base_path"] == SOCIAL_INTEGRATION_BASE_PATH
    assert enabled_payload["integration_embeds_path"] == SOCIAL_INTEGRATION_EMBEDS_PATH
    assert enabled_payload["provider_allowlist"] == ["youtube"]
    assert enabled_payload["embed_provider_allowlist"] == ["youtube"]
    assert enabled_payload["cache_ttl_seconds"] == 600
    assert enabled_payload["embeds_per_page"] == 1
    assert enabled_payload["total_embeds"] == 1
    assert enabled_payload["error"] is None
    assert enabled_payload["embeds"] == [
        {
            "id": embeds[0]["id"],
            "title": "QuickScale on YouTube",
            "description": "Launch announcement clip.",
            "provider_name": "youtube",
            "provider_display_name": "YouTube",
            "url": "https://www.youtube.com/shorts/alpha123",
            "source_url": "https://www.youtube.com/shorts/alpha123",
            "display_order": 20,
            "resolution_status": SOCIAL_EMBED_RESOLUTION_RESOLVED,
            "resolution_error": None,
            "embed_url": "https://www.youtube.com/embed/alpha123?rel=0",
            "thumbnail_url": "https://i.ytimg.com/vi/alpha123/hqdefault.jpg",
            "embed_width": 560,
            "embed_height": 315,
            "thumbnail_width": 480,
            "thumbnail_height": 360,
            "last_resolution_attempt_at": embeds[0]["last_resolution_attempt_at"],
            "last_resolved_at": embeds[0]["last_resolved_at"],
        }
    ]
    assert embeds[0]["last_resolution_attempt_at"] is not None
    assert embeds[0]["last_resolved_at"] == embeds[0]["last_resolution_attempt_at"]
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
    error_message = cast(str, error_payload["error"])

    assert error_payload["status"] == SOCIAL_STATUS_ERROR
    assert error_payload["enabled"] is False
    assert error_payload["embeds"] == []
    assert error_payload["total_embeds"] == 0
    assert "must include TikTok or YouTube" in error_message
    assert social_payload_status_code(error_payload["status"]) == 503


def test_build_social_embeds_payload_uses_empty_state_for_missing_table(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Missing embed tables should degrade to the existing empty public payload."""

    def raise_missing_table(*args: object, **kwargs: object) -> object:
        raise ProgrammingError("no such table: quickscale_modules_social_socialembed")

    cache.delete(SOCIAL_EMBEDS_CACHE_KEY)
    monkeypatch.setattr(SocialEmbed.objects, "filter", raise_missing_table)

    payload = build_social_embeds_payload()

    assert payload["status"] == SOCIAL_STATUS_EMPTY
    assert payload["enabled"] is True
    assert payload["embeds"] == []
    assert payload["total_embeds"] == 0
    assert payload["error"] is None
    assert cache.get(SOCIAL_EMBEDS_CACHE_KEY) is None
