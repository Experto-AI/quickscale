"""Tests for social module runtime services."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast

import pytest
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.db.utils import OperationalError, ProgrammingError
from django.test import override_settings

import quickscale_modules_social.services as social_services
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


def _activate_org_context(org_id: object) -> None:
    """Set the current org context for TenantManager auto-scoping.

    Must be paired with ``_reset_org_context()`` in a ``try/finally`` or
    ``yield`` fixture.
    """
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(org_id)


def _reset_org_context() -> None:
    """Reset the current org context to ``None`` (fail-closed)."""
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(None)


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
def test_list_published_social_links_uses_canonical_urls_and_invalidates_cache(
    org,
) -> None:
    """Published link payloads should normalize URLs and refresh after admin writes."""
    _activate_org_context(org.id)
    try:
        SocialLink.objects.create(
            title="QuickScale on LinkedIn",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/?utm_source=share",
            display_order=20,
            organization=org,
        )

        initial_records = list_published_social_links()

        assert [record.title for record in initial_records] == [
            "QuickScale on LinkedIn"
        ]
        assert initial_records[0].url == "https://www.linkedin.com/company/quickscale"

        SocialLink.objects.create(
            title="QuickScale on YouTube",
            provider_name="youtube",
            url="https://youtu.be/abc123?si=share",
            display_order=10,
            organization=org,
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

        assert [record.title for record in filtered_records] == [
            "QuickScale on YouTube"
        ]
    finally:
        _reset_org_context()


@django_db
def test_list_published_social_links_recovers_from_corrupt_cache_payload(org) -> None:
    """Corrupt cached link payloads should be ignored and refreshed from the DB."""
    _activate_org_context(org.id)
    try:
        SocialLink.objects.create(
            title="QuickScale on LinkedIn",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
            organization=org,
        )
    finally:
        _reset_org_context()

    # Set a corrupt payload on this org's cache partition, then query.
    org_cache_key = f"{SOCIAL_LINKS_CACHE_KEY}:org:{org.id}"
    cache.set(org_cache_key, [{"broken": True}], timeout=300)

    _activate_org_context(org.id)
    try:
        records = list_published_social_links()
        cached_payload = cache.get(org_cache_key)

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
    finally:
        _reset_org_context()


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
def test_list_published_social_embeds_honors_runtime_toggle_and_filtering(
    org,
) -> None:
    """Published embed payloads should respect embed toggles and provider filtering."""
    _activate_org_context(org.id)
    try:
        SocialEmbed.objects.create(
            title="QuickScale on YouTube",
            provider_name="",
            url="https://www.youtube.com/shorts/alpha123",
            display_order=20,
            organization=org,
        )
        SocialEmbed.objects.create(
            title="QuickScale on TikTok",
            provider_name="",
            url="https://vm.tiktok.com/ZM1234567/",
            display_order=10,
            organization=org,
        )

        initial_records = list_published_social_embeds()

        assert [record.provider_name for record in initial_records] == [
            "tiktok",
            "youtube",
        ]
        assert initial_records[0].resolution_status == SOCIAL_EMBED_RESOLUTION_ERROR
        assert initial_records[0].embed_url is None
        assert "canonical TikTok video URL" in (
            initial_records[0].resolution_error or ""
        )
        assert initial_records[1].resolution_status == SOCIAL_EMBED_RESOLUTION_RESOLVED
        assert (
            initial_records[1].embed_url
            == "https://www.youtube.com/embed/alpha123?rel=0"
        )

        with override_settings(
            QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"],
            QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE=1,
        ):
            filtered_records = list_published_social_embeds()

        assert len(filtered_records) == 1
        assert filtered_records[0].provider_name == "youtube"
        assert (
            filtered_records[0].embed_url
            == "https://www.youtube.com/embed/alpha123?rel=0"
        )

        with override_settings(QUICKSCALE_SOCIAL_EMBEDS_ENABLED=False):
            disabled_records = list_published_social_embeds()

        assert disabled_records == ()
    finally:
        _reset_org_context()


@django_db
def test_list_published_social_embeds_recovers_from_non_list_cache_payload(
    org,
) -> None:
    """Non-list embed cache payloads should be ignored and refreshed from the DB."""
    _activate_org_context(org.id)
    try:
        SocialEmbed.objects.create(
            title="QuickScale on YouTube",
            provider_name="",
            url="https://www.youtube.com/shorts/alpha123",
            display_order=10,
            organization=org,
        )
    finally:
        _reset_org_context()

    org_cache_key = f"{SOCIAL_EMBEDS_CACHE_KEY}:org:{org.id}"
    cache.set(org_cache_key, {"broken": True}, timeout=300)

    _activate_org_context(org.id)
    try:
        records = list_published_social_embeds()
        cached_payload = cast(list[dict[str, object]], cache.get(org_cache_key))

        assert [record.provider_name for record in records] == ["youtube"]
        assert cached_payload[0]["id"] == records[0].id
        assert cached_payload[0]["provider_name"] == "youtube"
        assert (
            cached_payload[0]["embed_url"]
            == "https://www.youtube.com/embed/alpha123?rel=0"
        )
    finally:
        _reset_org_context()


@django_db
def test_build_social_link_tree_payload_freezes_enabled_and_empty_semantics(
    org,
) -> None:
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

    _activate_org_context(org.id)
    try:
        SocialLink.objects.create(
            title="QuickScale on YouTube",
            provider_name="youtube",
            url="https://youtu.be/abc123?si=share",
            description="Launch clips and demos.",
            display_order=10,
            organization=org,
        )
        SocialLink.objects.create(
            title="QuickScale on LinkedIn",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/?utm_source=share",
            description="Company updates.",
            display_order=20,
            organization=org,
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
    finally:
        _reset_org_context()


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
def test_social_models_enforce_guardrails_and_invalidate_cache(org) -> None:
    """Social models should validate runtime guardrails and clear their cache keys."""
    _activate_org_context(org.id)
    try:
        cache.set(SOCIAL_LINKS_CACHE_KEY, ["stale"], timeout=300)
        link = SocialLink.objects.create(
            title="QuickScale on YouTube",
            provider_name="youtube",
            url="https://youtu.be/abc123?si=share",
            display_order=10,
            organization=org,
        )

        assert cache.get(SOCIAL_LINKS_CACHE_KEY) is None

        cache.set(SOCIAL_LINKS_CACHE_KEY, ["stale"], timeout=300)
        link.delete()

        assert cache.get(SOCIAL_LINKS_CACHE_KEY) is None
    finally:
        _reset_org_context()

    with override_settings(QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"]):
        invalid_link = SocialLink(
            title="QuickScale on LinkedIn",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
            organization=org,
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
            organization=org,
        )
        with pytest.raises(ValidationError) as exc_info:
            invalid_embed.full_clean()

    assert exc_info.value.message_dict["provider_name"] == [
        "Embeds support only TikTok and YouTube in v0.79.0."
    ]


def test_invalidate_social_cache_is_not_exported_as_public_bulk_api() -> None:
    """The bare-key cache helper should not be advertised as tenant-aware API."""
    assert hasattr(social_services, "invalidate_social_cache")
    assert "invalidate_social_cache" not in social_services.__all__


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
def test_build_social_embeds_payload_freezes_enabled_disabled_and_error_semantics(
    org,
) -> None:
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

    _activate_org_context(org.id)
    try:
        SocialEmbed.objects.create(
            title="QuickScale on YouTube",
            provider_name="",
            url="https://www.youtube.com/shorts/alpha123",
            description="Launch announcement clip.",
            display_order=20,
            organization=org,
        )
        SocialEmbed.objects.create(
            title="QuickScale on TikTok",
            provider_name="",
            url="https://vm.tiktok.com/ZM1234567/",
            description="Short product teaser.",
            display_order=10,
            organization=org,
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
        assert (
            enabled_payload["integration_embeds_path"] == SOCIAL_INTEGRATION_EMBEDS_PATH
        )
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
    finally:
        _reset_org_context()


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


# ---------------------------------------------------------------------------
# T1.9 — contextvar-based tenant-scoped service queries
# ---------------------------------------------------------------------------


@django_db
def test_list_published_social_links_scoped_to_org() -> None:
    """Org-scoped link queries should return only that org's published links."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    try:
        set_current_org_id(org_a.id)
        SocialLink.objects.create(
            title="Org A Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-a/",
            display_order=10,
            is_published=True,
            organization=org_a,
        )

        set_current_org_id(org_b.id)
        SocialLink.objects.create(
            title="Org B Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-b/",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        set_current_org_id(org_a.id)
        org_a_links = list_published_social_links()
        assert [r.title for r in org_a_links] == ["Org A Link"]

        set_current_org_id(org_b.id)
        org_b_links = list_published_social_links()
        assert [r.title for r in org_b_links] == ["Org B Link"]

        set_current_org_id(None)
        no_context_links = list_published_social_links()
        assert no_context_links == ()
    finally:
        set_current_org_id(None)


@django_db
def test_social_link_cache_is_partitioned_by_org() -> None:
    """Cross-org cache partition test: org A and org B must not share cache entries.

    Regression for CR-T1-9-001: global cache keys previously let one org's
    payload poison reads for another org.  Org-aware keys partition the cache
    so that a query from org A does not affect the cached result for org B.
    """
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    try:
        set_current_org_id(org_a.id)
        SocialLink.objects.create(
            title="Org A Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-a/",
            display_order=10,
            is_published=True,
            organization=org_a,
        )

        set_current_org_id(org_b.id)
        SocialLink.objects.create(
            title="Org B Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-b/",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        # Query from Org A — populates org A's cache partition.
        set_current_org_id(org_a.id)
        org_a_links = list_published_social_links()

        # Query from Org B  —  MUST NOT read org A's cache entry.
        # No cache.clear() between calls — this is the regression check.
        set_current_org_id(org_b.id)
        org_b_links = list_published_social_links()

        assert [r.title for r in org_a_links] == ["Org A Link"]
        assert [r.title for r in org_b_links] == ["Org B Link"]
    finally:
        set_current_org_id(None)


@django_db
def test_social_cache_invalidates_old_org_partition_on_reassignment() -> None:
    """When a social item moves from org A to org B, org A's stale cache is cleared.

    Regression for CR-T1-9-001: _keys_to_clear() only cleared the current
    (new) org's partition.  The old org's cached entry for the moved item
    would continue to be served until TTL expiry.

    RLS semantics and ``operator_access``
    -------------------------------------
    Under ``NOBYPASSRLS`` the FOR ALL policy requires BOTH
    ``current_org_id = old organization_id`` (USING) AND
    ``current_org_id = new organization_id`` (WITH CHECK).  A single
    UPDATE that changes ``organization_id`` is therefore blocked —
    no single ``current_org_id`` value can equal both the old and new
    organisation simultaneously.

    ``operator_access(reason=...)`` (SA14.5) extends only the
    ``FOR SELECT`` sub-policy — it grants cross-tenant **read**
    visibility, not write visibility.  It does NOT bypass the FOR ALL
    policy's USING or WITH CHECK clauses and cannot unblock a
    cross-org UPDATE.

    The test therefore performs the reassignment as two RLS-compatible
    operations:
      1. **Delete** from Org A context — USING matches, triggers
         ``BaseSocialItem.delete()`` cache invalidation for the old
         partition.
      2. **Create** in Org B context — WITH CHECK passes, ``save()``
         populates the new partition.

    It then uses ``operator_access()`` to demonstrate cross-org **read**
    capability via ``all_objects``: from Org A's context, where the
    default ``TenantManager`` would normally restrict the query,
    ``operator_access`` combined with the super-scope manager allows a
    cross-tenant read that confirms the link resides in Org B.
    """
    from quickscale_modules_orgs.current_org import (
        operator_access,
        set_current_org_id,
    )
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    try:
        set_current_org_id(org_a.id)

        # Create a link owned by Org A.
        link = SocialLink.objects.create(
            title="Shared Link",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
            is_published=True,
            organization=org_a,
        )

        # Query from Org A — populates org A's cache partition.
        org_a_links_before = list_published_social_links()
        assert [r.title for r in org_a_links_before] == ["Shared Link"]

        # ---- Move the link to Org B (RLS-compatible pattern) --------------
        #
        # RLS blocks cross-org UPDATE.  Instead, delete from old and create
        # in new — both operations pass their respective RLS checks, and
        # each triggers cache invalidation for its org partition.

        # Step 1: Delete from Org A's context.  FOR ALL USING matches
        # (current_org_id = org_a), cache is cleared for the old partition.
        set_current_org_id(org_a.id)
        link.delete()

        # Step 2: Create the link under Org B's context.  INSERT passes
        # WITH CHECK (current_org_id = org_b), and save() populates the
        # new org's cache partition.
        set_current_org_id(org_b.id)
        SocialLink.objects.create(
            title="Shared Link",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
            is_published=True,
            organization=org_b,
        )

        # ---- Cross-org read verification via operator_access ---------------
        # operator_access enables cross-tenant SELECT by extending the
        # FOR SELECT sub-policy.  From Org B's context, the default manager
        # already finds the link (current_org_id = org_b matches).
        org_b_links = list_published_social_links()
        assert [r.title for r in org_b_links] == ["Shared Link"]

        # From Org A's context the default TenantManager filters to org_a.
        # Without operator_access, all_objects would be blocked by RLS
        # FOR ALL USING (current_org_id = org_a ≠ org_b).
        # With operator_access, the _select sub-policy allows the read.
        set_current_org_id(org_a.id)
        with operator_access(reason="cross-org read — verify link in Org B"):
            confirmed = list(
                SocialLink.all_objects.filter(
                    title="Shared Link", organization=org_b
                ).values_list("pk", flat=True)
            )
        assert len(confirmed) == 1, (
            "operator_access must enable cross-org read: Org A context "
            "should see the link in Org B via all_objects."
        )

        # Finally, the default-scoped query from Org A returns nothing
        # (cache was invalidated by delete(); no row in org_a).
        org_a_links_after = list_published_social_links()
        assert org_a_links_after == (), (
            "Org A must not see the link after it was reassigned to Org B."
        )
    finally:
        set_current_org_id(None)


@django_db
def test_list_published_social_embeds_scoped_to_org() -> None:
    """Org-scoped embed queries should return only that org's published embeds."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    try:
        set_current_org_id(org_a.id)
        SocialEmbed.objects.create(
            title="Org A Embed",
            provider_name="",
            url="https://www.youtube.com/shorts/aaa111",
            display_order=10,
            is_published=True,
            organization=org_a,
        )

        set_current_org_id(org_b.id)
        SocialEmbed.objects.create(
            title="Org B Embed",
            provider_name="",
            url="https://www.youtube.com/shorts/bbb222",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        set_current_org_id(org_a.id)
        org_a_embeds = list_published_social_embeds()
        assert [r.title for r in org_a_embeds] == ["Org A Embed"]

        set_current_org_id(org_b.id)
        org_b_embeds = list_published_social_embeds()
        assert [r.title for r in org_b_embeds] == ["Org B Embed"]

        set_current_org_id(None)
        no_context_embeds = list_published_social_embeds()
        assert no_context_embeds == ()
    finally:
        set_current_org_id(None)


@django_db
def test_build_social_link_tree_payload_scoped_to_org() -> None:
    """Org-scoped build payload should return only that org's links."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    try:
        set_current_org_id(org_a.id)
        SocialLink.objects.create(
            title="Org A Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-a/",
            display_order=10,
            is_published=True,
            organization=org_a,
        )

        set_current_org_id(org_b.id)
        SocialLink.objects.create(
            title="Org B Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-b/",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        # Scope to Org A — only Org A's links should appear in the payload.
        set_current_org_id(org_a.id)
        payload_a = build_social_link_tree_payload()
        assert payload_a["status"] == SOCIAL_STATUS_ENABLED
        assert payload_a["total_links"] == 1
        assert payload_a["links"][0]["title"] == "Org A Link"

        # Scope to Org B — only Org B's links should appear.
        set_current_org_id(org_b.id)
        payload_b = build_social_link_tree_payload()
        assert payload_b["status"] == SOCIAL_STATUS_ENABLED
        assert payload_b["total_links"] == 1
        assert payload_b["links"][0]["title"] == "Org B Link"
    finally:
        set_current_org_id(None)


@django_db
def test_build_social_embeds_payload_scoped_to_org() -> None:
    """Org-scoped build payload should return only that org's embeds."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    try:
        set_current_org_id(org_a.id)
        SocialEmbed.objects.create(
            title="Org A Embed",
            provider_name="",
            url="https://www.youtube.com/shorts/aaa111",
            display_order=10,
            is_published=True,
            organization=org_a,
        )

        set_current_org_id(org_b.id)
        SocialEmbed.objects.create(
            title="Org B Embed",
            provider_name="",
            url="https://www.youtube.com/shorts/bbb222",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        # Scope to Org A — only Org A's embeds should appear in the payload.
        set_current_org_id(org_a.id)
        payload_a = build_social_embeds_payload()
        assert payload_a["status"] == SOCIAL_STATUS_ENABLED
        assert payload_a["total_embeds"] == 1
        assert payload_a["embeds"][0]["title"] == "Org A Embed"

        # Scope to Org B — only Org B's embeds should appear.
        set_current_org_id(org_b.id)
        payload_b = build_social_embeds_payload()
        assert payload_b["status"] == SOCIAL_STATUS_ENABLED
        assert payload_b["total_embeds"] == 1
        assert payload_b["embeds"][0]["title"] == "Org B Embed"
    finally:
        set_current_org_id(None)
