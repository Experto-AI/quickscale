"""Read-only runtime services for the QuickScale social module."""

from __future__ import annotations

from dataclasses import asdict, dataclass

from django.core.cache import cache

from quickscale_modules_social.contracts import (
    DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST,
    DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
    SOCIAL_EMBEDS_CACHE_KEY,
    SOCIAL_EMBEDS_PATH,
    SOCIAL_EMBED_RESOLUTION_PENDING,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINKS_CACHE_KEY,
    SOCIAL_LINK_TREE_PATH,
    SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_ERROR,
    SocialConfigurationError,
    SocialRuntimeSettingsSnapshot,
    get_social_provider_metadata,
    get_social_runtime_settings,
    social_provider_supports_embeds,
)
from quickscale_modules_social.models import SocialEmbed, SocialLink

_CACHE_MISS = object()


@dataclass(frozen=True)
class SocialLinkRecord:
    """Read-only runtime representation of a published social link."""

    id: int
    title: str
    description: str
    provider_name: str
    provider_display_name: str
    url: str
    source_url: str
    display_order: int

    @classmethod
    def from_model(cls, link: SocialLink) -> SocialLinkRecord:
        """Build a runtime record from a stored social link row."""
        metadata = get_social_provider_metadata(link.provider_name)
        return cls(
            id=link.pk,
            title=link.title,
            description=link.description,
            provider_name=link.provider_name,
            provider_display_name=(
                metadata.display_name if metadata is not None else link.provider_name
            ),
            url=link.normalized_url,
            source_url=link.url,
            display_order=link.display_order,
        )


@dataclass(frozen=True)
class SocialEmbedRecord:
    """Read-only runtime representation of a published social embed."""

    id: int
    title: str
    description: str
    provider_name: str
    provider_display_name: str
    url: str
    source_url: str
    display_order: int
    resolution_status: str
    resolution_error: str | None
    embed_url: str | None
    thumbnail_url: str | None
    embed_width: int | None
    embed_height: int | None
    thumbnail_width: int | None
    thumbnail_height: int | None
    last_resolution_attempt_at: str | None
    last_resolved_at: str | None

    @classmethod
    def from_model(cls, embed: SocialEmbed) -> SocialEmbedRecord:
        """Build a runtime record from a stored social embed row."""
        metadata = get_social_provider_metadata(embed.provider_name)
        return cls(
            id=embed.pk,
            title=embed.title,
            description=embed.description,
            provider_name=embed.provider_name,
            provider_display_name=(
                metadata.display_name if metadata is not None else embed.provider_name
            ),
            url=embed.normalized_url,
            source_url=embed.url,
            display_order=embed.display_order,
            resolution_status=embed.resolution_status
            or SOCIAL_EMBED_RESOLUTION_PENDING,
            resolution_error=embed.resolution_error or None,
            embed_url=embed.resolved_embed_url or None,
            thumbnail_url=embed.resolved_thumbnail_url or None,
            embed_width=embed.resolved_width,
            embed_height=embed.resolved_height,
            thumbnail_width=embed.resolved_thumbnail_width,
            thumbnail_height=embed.resolved_thumbnail_height,
            last_resolution_attempt_at=(
                embed.last_resolution_attempt_at.isoformat()
                if embed.last_resolution_attempt_at is not None
                else None
            ),
            last_resolved_at=(
                embed.last_resolved_at.isoformat()
                if embed.last_resolved_at is not None
                else None
            ),
        )


def invalidate_social_cache() -> None:
    """Clear cached social payloads after admin or service mutations."""
    cache.delete_many([SOCIAL_LINKS_CACHE_KEY, SOCIAL_EMBEDS_CACHE_KEY])


def _serialize_records(
    records: tuple[SocialLinkRecord, ...] | tuple[SocialEmbedRecord, ...],
) -> list[dict[str, object]]:
    return [asdict(record) for record in records]


def _load_link_records(payload: object) -> tuple[SocialLinkRecord, ...] | None:
    if not isinstance(payload, list):
        return None

    records: list[SocialLinkRecord] = []
    try:
        for item in payload:
            if not isinstance(item, dict):
                return None
            records.append(SocialLinkRecord(**item))
    except TypeError:
        return None

    return tuple(records)


def _load_embed_records(payload: object) -> tuple[SocialEmbedRecord, ...] | None:
    if not isinstance(payload, list):
        return None

    records: list[SocialEmbedRecord] = []
    try:
        for item in payload:
            if not isinstance(item, dict):
                return None
            records.append(SocialEmbedRecord(**item))
    except TypeError:
        return None

    return tuple(records)


def _embed_provider_allowlist(provider_allowlist: tuple[str, ...]) -> list[str]:
    return [
        provider
        for provider in provider_allowlist
        if social_provider_supports_embeds(provider)
    ]


def _payload_allowlists(
    runtime_settings: SocialRuntimeSettingsSnapshot | None,
) -> tuple[list[str], list[str]]:
    if runtime_settings is None:
        return (
            list(DEFAULT_SOCIAL_PROVIDER_ALLOWLIST),
            list(DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST),
        )

    provider_allowlist = list(runtime_settings.provider_allowlist)
    return (
        provider_allowlist,
        _embed_provider_allowlist(runtime_settings.provider_allowlist),
    )


def _base_payload(
    *,
    surface: str,
    status: str,
    enabled: bool,
    public_path: str,
    runtime_settings: SocialRuntimeSettingsSnapshot | None,
    error: str | None,
) -> dict[str, object]:
    provider_allowlist, embed_provider_allowlist = _payload_allowlists(runtime_settings)
    return {
        "module": "social",
        "surface": surface,
        "status": status,
        "enabled": enabled,
        "public_path": public_path,
        "integration_base_path": SOCIAL_INTEGRATION_BASE_PATH,
        "integration_embeds_path": SOCIAL_INTEGRATION_EMBEDS_PATH,
        "provider_allowlist": provider_allowlist,
        "embed_provider_allowlist": embed_provider_allowlist,
        "error": error,
    }


def _link_tree_payload(
    *,
    status: str,
    enabled: bool,
    runtime_settings: SocialRuntimeSettingsSnapshot | None,
    links: tuple[SocialLinkRecord, ...] = (),
    error: str | None = None,
) -> dict[str, object]:
    payload = _base_payload(
        surface="link_tree",
        status=status,
        enabled=enabled,
        public_path=SOCIAL_LINK_TREE_PATH,
        runtime_settings=runtime_settings,
        error=error,
    )
    payload.update(
        {
            "layout_variant": (
                runtime_settings.layout_variant
                if runtime_settings is not None
                else "list"
            ),
            "links_per_page": (
                runtime_settings.links_per_page if runtime_settings is not None else 24
            ),
            "total_links": len(links),
            "links": _serialize_records(links),
        }
    )
    return payload


def _embeds_payload(
    *,
    status: str,
    enabled: bool,
    runtime_settings: SocialRuntimeSettingsSnapshot | None,
    embeds: tuple[SocialEmbedRecord, ...] = (),
    error: str | None = None,
) -> dict[str, object]:
    payload = _base_payload(
        surface="embeds",
        status=status,
        enabled=enabled,
        public_path=SOCIAL_EMBEDS_PATH,
        runtime_settings=runtime_settings,
        error=error,
    )
    payload.update(
        {
            "cache_ttl_seconds": (
                runtime_settings.cache_ttl_seconds
                if runtime_settings is not None
                else 300
            ),
            "embeds_per_page": (
                runtime_settings.embeds_per_page if runtime_settings is not None else 12
            ),
            "total_embeds": len(embeds),
            "embeds": _serialize_records(embeds),
        }
    )
    return payload


def list_published_social_links(
    runtime_settings: SocialRuntimeSettingsSnapshot | None = None,
) -> tuple[SocialLinkRecord, ...]:
    """Return published curated links filtered by the active runtime settings."""
    runtime_settings = runtime_settings or get_social_runtime_settings()
    if not runtime_settings.link_tree_enabled:
        return ()

    cached_payload = cache.get(SOCIAL_LINKS_CACHE_KEY, _CACHE_MISS)
    records = (
        None if cached_payload is _CACHE_MISS else _load_link_records(cached_payload)
    )
    if records is None:
        records = tuple(
            SocialLinkRecord.from_model(link)
            for link in SocialLink.objects.filter(is_published=True).order_by(
                "display_order",
                "title",
                "pk",
            )
        )
        cache.set(
            SOCIAL_LINKS_CACHE_KEY,
            _serialize_records(records),
            timeout=runtime_settings.cache_ttl_seconds,
        )

    filtered = [
        record
        for record in records
        if record.provider_name in runtime_settings.provider_allowlist
    ]
    return tuple(filtered[: runtime_settings.links_per_page])


def list_published_social_embeds(
    runtime_settings: SocialRuntimeSettingsSnapshot | None = None,
) -> tuple[SocialEmbedRecord, ...]:
    """Return published curated embeds filtered by the active runtime settings."""
    runtime_settings = runtime_settings or get_social_runtime_settings()
    if not runtime_settings.embeds_enabled:
        return ()

    cached_payload = cache.get(SOCIAL_EMBEDS_CACHE_KEY, _CACHE_MISS)
    records = (
        None if cached_payload is _CACHE_MISS else _load_embed_records(cached_payload)
    )
    if records is None:
        records = tuple(
            SocialEmbedRecord.from_model(embed)
            for embed in SocialEmbed.objects.filter(is_published=True).order_by(
                "display_order",
                "title",
                "pk",
            )
        )
        cache.set(
            SOCIAL_EMBEDS_CACHE_KEY,
            _serialize_records(records),
            timeout=runtime_settings.cache_ttl_seconds,
        )

    filtered = [
        record
        for record in records
        if record.provider_name in runtime_settings.provider_allowlist
        and social_provider_supports_embeds(record.provider_name)
    ]
    return tuple(filtered[: runtime_settings.embeds_per_page])


def build_social_link_tree_payload() -> dict[str, object]:
    """Return the managed link-tree JSON contract for React/backend consumers."""
    try:
        runtime_settings = get_social_runtime_settings()
    except SocialConfigurationError as exc:
        return _link_tree_payload(
            status=SOCIAL_STATUS_ERROR,
            enabled=False,
            runtime_settings=None,
            error=str(exc),
        )

    if not runtime_settings.link_tree_enabled:
        return _link_tree_payload(
            status=SOCIAL_STATUS_DISABLED,
            enabled=False,
            runtime_settings=runtime_settings,
        )

    links = list_published_social_links(runtime_settings=runtime_settings)
    return _link_tree_payload(
        status=SOCIAL_STATUS_ENABLED if links else SOCIAL_STATUS_EMPTY,
        enabled=True,
        runtime_settings=runtime_settings,
        links=links,
    )


def build_social_embeds_payload() -> dict[str, object]:
    """Return the managed embeds JSON contract for React/backend consumers."""
    try:
        runtime_settings = get_social_runtime_settings()
    except SocialConfigurationError as exc:
        return _embeds_payload(
            status=SOCIAL_STATUS_ERROR,
            enabled=False,
            runtime_settings=None,
            error=str(exc),
        )

    if not runtime_settings.embeds_enabled:
        return _embeds_payload(
            status=SOCIAL_STATUS_DISABLED,
            enabled=False,
            runtime_settings=runtime_settings,
        )

    embeds = list_published_social_embeds(runtime_settings=runtime_settings)
    return _embeds_payload(
        status=SOCIAL_STATUS_ENABLED if embeds else SOCIAL_STATUS_EMPTY,
        enabled=True,
        runtime_settings=runtime_settings,
        embeds=embeds,
    )


__all__ = [
    "SocialEmbedRecord",
    "SocialLinkRecord",
    "build_social_embeds_payload",
    "build_social_link_tree_payload",
    "invalidate_social_cache",
    "list_published_social_embeds",
    "list_published_social_links",
]
