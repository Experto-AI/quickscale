"""Module-owned social contract helpers for runtime and admin consumers.

The provider catalog, canonical provider/URL normalization, and payload-status
helpers are core-owned: this module re-exports them from
``quickscale_core.runtime.manifest`` so runtime and admin consumers keep one
import path.  What stays here is what the social module owns — curated embed
preview metadata, the embed resolution lifecycle, module cache keys and paths,
and module-specific allowlist normalization.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.db import models

from quickscale_core.runtime.manifest import (
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
    get_social_provider_metadata,
    normalize_social_provider,
    normalize_social_url,
    resolve_social_target,
    social_payload_status_code,
    social_provider_supports_embeds,
)

from quickscale_modules_social.exceptions import SocialConfigurationError

SOCIAL_LINK_TREE_PATH = "/social"
SOCIAL_EMBEDS_PATH = "/social/embeds"
SOCIAL_INTEGRATION_BASE_PATH = "/_quickscale/social/"
SOCIAL_INTEGRATION_EMBEDS_PATH = "/_quickscale/social/embeds/"
SOCIAL_LINKS_CACHE_KEY = "quickscale_social:links"
SOCIAL_EMBEDS_CACHE_KEY = "quickscale_social:embeds"


class SocialEmbedResolution(models.TextChoices):
    """Resolution lifecycle of a curated social embed."""

    PENDING = "pending", "Pending"
    RESOLVED = "resolved", "Resolved"
    ERROR = "error", "Error"


SOCIAL_PROVIDER_CHOICES = tuple(
    (provider.name, provider.display_name) for provider in SOCIAL_PROVIDER_CATALOG
)

_PROVIDER_TOKEN_PATTERN = re.compile(r"[^a-z0-9-]+")
_MULTI_DASH_PATTERN = re.compile(r"-{2,}")
_YOUTUBE_EMBED_PATH_PATTERN = re.compile(r"^/(?:embed|live|shorts|v)/([^/?#]+)$")
_TIKTOK_VIDEO_PATH_PATTERN = re.compile(r"/video/(\d+)")
_YOUTUBE_EMBED_DIMENSIONS = (560, 315)
_YOUTUBE_THUMBNAIL_DIMENSIONS = (480, 360)
_TIKTOK_EMBED_DIMENSIONS = (325, 575)


@dataclass(frozen=True)
class ResolvedSocialEmbedMetadata:
    """Provider-safe inline preview metadata for a curated social embed."""

    embed_url: str
    thumbnail_url: str | None
    embed_width: int | None
    embed_height: int | None
    thumbnail_width: int | None
    thumbnail_height: int | None


def _normalize_provider_token(value: Any) -> str:
    candidate = str(value).strip().lower().replace("&", "and")
    candidate = re.sub(r"[\s_/]+", "-", candidate)
    candidate = _PROVIDER_TOKEN_PATTERN.sub("", candidate)
    return _MULTI_DASH_PATTERN.sub("-", candidate).strip("-")


def _coerce_allowlist_values(values: Sequence[Any] | Any) -> list[Any]:
    if values is None:
        return []
    if isinstance(values, str):
        return [part for part in values.split(",")]
    if isinstance(values, Sequence):
        return list(values)
    return [values]


def normalize_social_provider_allowlist(values: Sequence[Any] | Any) -> list[str]:
    """Normalize a social provider allowlist while preserving first-seen order."""
    normalized: list[str] = []
    seen: set[str] = set()

    for value in _coerce_allowlist_values(values):
        canonical = normalize_social_provider(value)
        candidate = canonical or _normalize_provider_token(value)
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        normalized.append(candidate)

    return normalized


def _query_value(query: str, key: str) -> str | None:
    for query_key, value in parse_qsl(query, keep_blank_values=False):
        if query_key == key and value.strip():
            return value.strip()
    return None


def _canonical_path(path: str) -> str:
    normalized = re.sub(r"/{2,}", "/", path or "/")
    if normalized != "/":
        normalized = normalized.rstrip("/")
    return normalized or "/"


def _resolve_youtube_embed_metadata(url: str) -> ResolvedSocialEmbedMetadata:
    parsed = urlsplit(url)
    video_id = _query_value(parsed.query, "v")
    if video_id is None:
        path_match = _YOUTUBE_EMBED_PATH_PATTERN.fullmatch(_canonical_path(parsed.path))
        video_id = path_match.group(1) if path_match is not None else None

    if not video_id:
        raise ValueError(
            "QuickScale could not derive a canonical YouTube video id for inline preview metadata."
        )

    embed_query_items = [("rel", "0")]
    playlist_id = _query_value(parsed.query, "list")
    if playlist_id:
        embed_query_items.append(("list", playlist_id))

    embed_url = (
        f"https://www.youtube.com/embed/{video_id}?{urlencode(embed_query_items)}"
    )
    return ResolvedSocialEmbedMetadata(
        embed_url=embed_url,
        thumbnail_url=f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg",
        embed_width=_YOUTUBE_EMBED_DIMENSIONS[0],
        embed_height=_YOUTUBE_EMBED_DIMENSIONS[1],
        thumbnail_width=_YOUTUBE_THUMBNAIL_DIMENSIONS[0],
        thumbnail_height=_YOUTUBE_THUMBNAIL_DIMENSIONS[1],
    )


def _resolve_tiktok_embed_metadata(url: str) -> ResolvedSocialEmbedMetadata:
    parsed = urlsplit(url)
    path_match = _TIKTOK_VIDEO_PATH_PATTERN.search(_canonical_path(parsed.path))
    video_id = path_match.group(1) if path_match is not None else None
    if not video_id:
        raise ValueError(
            "QuickScale needs a canonical TikTok video URL before it can resolve inline preview metadata."
        )

    return ResolvedSocialEmbedMetadata(
        embed_url=f"https://www.tiktok.com/embed/v2/{video_id}",
        thumbnail_url=None,
        embed_width=_TIKTOK_EMBED_DIMENSIONS[0],
        embed_height=_TIKTOK_EMBED_DIMENSIONS[1],
        thumbnail_width=None,
        thumbnail_height=None,
    )


def resolve_social_embed_metadata(
    url: str,
    *,
    provider: Any | None = None,
) -> ResolvedSocialEmbedMetadata:
    """Return backend-owned inline preview metadata for a curated social embed."""
    resolved = resolve_social_target(url, provider=provider)
    if resolved.provider == "youtube":
        return _resolve_youtube_embed_metadata(resolved.url)
    if resolved.provider == "tiktok":
        return _resolve_tiktok_embed_metadata(resolved.url)

    raise ValueError("Embeds support only TikTok and YouTube in v0.79.0.")


__all__ = [
    "DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST",
    "DEFAULT_SOCIAL_PROVIDER_ALLOWLIST",
    "ResolvedSocialEmbedMetadata",
    "SOCIAL_EMBEDS_CACHE_KEY",
    "SOCIAL_EMBEDS_PATH",
    "SocialEmbedResolution",
    "SOCIAL_INTEGRATION_BASE_PATH",
    "SOCIAL_INTEGRATION_EMBEDS_PATH",
    "SOCIAL_LAYOUT_VARIANTS",
    "SOCIAL_PAYLOAD_HTTP_STATUS",
    "SOCIAL_PAYLOAD_STATUSES",
    "SOCIAL_LINKS_CACHE_KEY",
    "SOCIAL_LINK_TREE_PATH",
    "SOCIAL_PROVIDER_CATALOG",
    "SOCIAL_PROVIDER_CHOICES",
    "SOCIAL_STATUS_DISABLED",
    "SOCIAL_STATUS_EMPTY",
    "SOCIAL_STATUS_ENABLED",
    "SOCIAL_STATUS_ERROR",
    "ResolvedSocialTarget",
    "SocialConfigurationError",
    "SocialProviderMetadata",
    "get_social_provider_metadata",
    "normalize_social_provider",
    "normalize_social_provider_allowlist",
    "normalize_social_url",
    "resolve_social_target",
    "resolve_social_embed_metadata",
    "social_payload_status_code",
    "social_provider_supports_embeds",
]
