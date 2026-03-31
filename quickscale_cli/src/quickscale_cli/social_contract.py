"""Dependency-light social module contract helpers.

This module defines the canonical Phase A social contract used by planner-side
validation and future generated-project wiring. Runtime/admin consumers must not
import quickscale_cli directly; later phases should copy these fixed values into
module-owned or generated-project-owned code paths instead.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

SOCIAL_LINK_TREE_PATH = "/social"
SOCIAL_EMBEDS_PATH = "/social/embeds"
SOCIAL_INTEGRATION_BASE_PATH = "/_quickscale/social/"
SOCIAL_INTEGRATION_EMBEDS_PATH = "/_quickscale/social/embeds/"
SOCIAL_LAYOUT_VARIANTS = ("list", "cards", "grid")

_SCHEMELESS_URL_PATTERN = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}(?:[:/].*)?$"
)
_PROVIDER_TOKEN_PATTERN = re.compile(r"[^a-z0-9-]+")
_MULTI_DASH_PATTERN = re.compile(r"-{2,}")
_TRACKING_QUERY_PREFIXES = ("utm_",)
_TRACKING_QUERY_NAMES = {
    "fbclid",
    "gclid",
    "igshid",
    "mc_cid",
    "mc_eid",
    "ref",
    "ref_src",
    "ref_url",
    "si",
}


@dataclass(frozen=True)
class SocialProviderMetadata:
    """Canonical metadata for a supported social provider."""

    name: str
    display_name: str
    supports_embeds: bool
    aliases: tuple[str, ...]
    hosts: tuple[str, ...]


@dataclass(frozen=True)
class ResolvedSocialTarget:
    """A provider-resolved canonical social URL."""

    provider: str
    url: str


SOCIAL_PROVIDER_CATALOG: tuple[SocialProviderMetadata, ...] = (
    SocialProviderMetadata(
        name="facebook",
        display_name="Facebook",
        supports_embeds=False,
        aliases=("fb",),
        hosts=("facebook.com", "www.facebook.com", "m.facebook.com", "fb.watch"),
    ),
    SocialProviderMetadata(
        name="instagram",
        display_name="Instagram",
        supports_embeds=False,
        aliases=("ig",),
        hosts=("instagram.com", "www.instagram.com", "m.instagram.com"),
    ),
    SocialProviderMetadata(
        name="linkedin",
        display_name="LinkedIn",
        supports_embeds=False,
        aliases=("linked-in",),
        hosts=("linkedin.com", "www.linkedin.com"),
    ),
    SocialProviderMetadata(
        name="tiktok",
        display_name="TikTok",
        supports_embeds=True,
        aliases=("tik-tok",),
        hosts=("tiktok.com", "www.tiktok.com", "m.tiktok.com", "vm.tiktok.com"),
    ),
    SocialProviderMetadata(
        name="x",
        display_name="X",
        supports_embeds=False,
        aliases=("twitter", "x-twitter", "x-twitter-com"),
        hosts=(
            "twitter.com",
            "www.twitter.com",
            "mobile.twitter.com",
            "x.com",
            "www.x.com",
            "mobile.x.com",
        ),
    ),
    SocialProviderMetadata(
        name="youtube",
        display_name="YouTube",
        supports_embeds=True,
        aliases=("you-tube",),
        hosts=("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be"),
    ),
)

_SOCIAL_PROVIDER_BY_NAME = {
    provider.name: provider for provider in SOCIAL_PROVIDER_CATALOG
}
_SOCIAL_PROVIDER_ALIASES = {
    alias: provider.name
    for provider in SOCIAL_PROVIDER_CATALOG
    for alias in (provider.name, *provider.aliases)
}
_SOCIAL_PROVIDER_BY_HOST = {
    host: provider.name
    for provider in SOCIAL_PROVIDER_CATALOG
    for host in provider.hosts
}

DEFAULT_SOCIAL_PROVIDER_ALLOWLIST = tuple(
    provider.name for provider in SOCIAL_PROVIDER_CATALOG
)
DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST = tuple(
    provider.name for provider in SOCIAL_PROVIDER_CATALOG if provider.supports_embeds
)


def default_social_module_options() -> dict[str, Any]:
    """Return the Phase A social module contract defaults."""
    return {
        "link_tree_enabled": True,
        "layout_variant": "list",
        "embeds_enabled": True,
        "provider_allowlist": list(DEFAULT_SOCIAL_PROVIDER_ALLOWLIST),
        "cache_ttl_seconds": 300,
        "links_per_page": 24,
        "embeds_per_page": 12,
    }


def _normalize_provider_token(value: Any) -> str:
    candidate = str(value).strip().lower().replace("&", "and")
    candidate = re.sub(r"[\s_/]+", "-", candidate)
    candidate = _PROVIDER_TOKEN_PATTERN.sub("", candidate)
    return _MULTI_DASH_PATTERN.sub("-", candidate).strip("-")


def normalize_social_provider(value: Any) -> str | None:
    """Return the canonical provider name for a raw alias/token."""
    token = _normalize_provider_token(value)
    if not token:
        return None
    return _SOCIAL_PROVIDER_ALIASES.get(token)


def get_social_provider_metadata(provider: Any) -> SocialProviderMetadata | None:
    """Return canonical provider metadata for a raw provider token."""
    normalized = normalize_social_provider(provider)
    if not normalized:
        return None
    return _SOCIAL_PROVIDER_BY_NAME[normalized]


def social_provider_supports_embeds(provider: Any) -> bool:
    """Return whether a provider supports curated embeds in v0.79.0."""
    metadata = get_social_provider_metadata(provider)
    return bool(metadata and metadata.supports_embeds)


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


def normalize_social_module_options(
    options: dict[str, Any] | None,
) -> dict[str, Any]:
    """Return a normalized social module options mapping."""
    normalized = dict(options or {})

    if "provider_allowlist" in normalized:
        normalized["provider_allowlist"] = normalize_social_provider_allowlist(
            normalized["provider_allowlist"]
        )

    if "layout_variant" in normalized:
        normalized["layout_variant"] = str(normalized["layout_variant"]).strip().lower()

    return normalized


def resolve_social_module_options(options: dict[str, Any] | None) -> dict[str, Any]:
    """Merge default social options with normalized overrides."""
    resolved = default_social_module_options()
    resolved.update(normalize_social_module_options(options))
    resolved["provider_allowlist"] = normalize_social_provider_allowlist(
        resolved["provider_allowlist"]
    )
    resolved["layout_variant"] = str(resolved["layout_variant"]).strip().lower()
    return resolved


def validate_social_module_options(options: dict[str, Any] | None) -> list[str]:
    """Return validation issues for the social module contract."""
    resolved = resolve_social_module_options(options)
    issues: list[str] = []

    if not isinstance(resolved.get("link_tree_enabled"), bool):
        issues.append("modules.social.link_tree_enabled must be a boolean")
    if not isinstance(resolved.get("embeds_enabled"), bool):
        issues.append("modules.social.embeds_enabled must be a boolean")

    layout_variant = str(resolved.get("layout_variant", "")).strip().lower()
    if layout_variant not in SOCIAL_LAYOUT_VARIANTS:
        issues.append("modules.social.layout_variant must be one of: list, cards, grid")

    provider_allowlist = normalize_social_provider_allowlist(
        resolved.get("provider_allowlist", [])
    )
    if not provider_allowlist:
        issues.append("modules.social.provider_allowlist cannot be empty")

    unknown_providers = [
        provider
        for provider in provider_allowlist
        if provider not in _SOCIAL_PROVIDER_BY_NAME
    ]
    if unknown_providers:
        issues.append(
            "modules.social.provider_allowlist contains unsupported providers: "
            + ", ".join(sorted(unknown_providers))
        )

    if not resolved.get("link_tree_enabled") and not resolved.get("embeds_enabled"):
        issues.append(
            "modules.social must leave link_tree_enabled or embeds_enabled enabled"
        )

    if resolved.get("embeds_enabled"):
        embed_providers = [
            provider
            for provider in provider_allowlist
            if social_provider_supports_embeds(provider)
        ]
        if not embed_providers:
            issues.append(
                "modules.social.provider_allowlist must include tiktok or youtube when embeds_enabled is true"
            )

    for option_name in ("cache_ttl_seconds", "links_per_page", "embeds_per_page"):
        try:
            value = int(resolved.get(option_name, 0))
            if value < 1:
                issues.append(f"modules.social.{option_name} must be at least 1")
        except TypeError, ValueError:
            issues.append(f"modules.social.{option_name} must be an integer")

    return issues


def _coerce_social_url(raw_url: str) -> str:
    candidate = str(raw_url).strip()
    if not candidate:
        raise ValueError("Social URLs cannot be blank")
    if candidate.startswith("//"):
        return f"https:{candidate}"
    if _SCHEMELESS_URL_PATTERN.fullmatch(candidate):
        return f"https://{candidate}"
    return candidate


def _clean_query_items(provider: str, query: str) -> list[tuple[str, str]]:
    if not query:
        return []

    query_items = parse_qsl(query, keep_blank_values=False)
    if provider == "youtube":
        allowed = []
        for key, value in query_items:
            lowered = key.lower()
            if lowered.startswith(_TRACKING_QUERY_PREFIXES):
                continue
            if lowered in _TRACKING_QUERY_NAMES:
                continue
            if lowered in {"v", "list"}:
                allowed.append((lowered, value))
        return allowed

    return []


def _canonical_host(provider: str, host: str) -> str:
    if provider == "facebook":
        return "fb.watch" if host == "fb.watch" else "www.facebook.com"
    if provider == "instagram":
        return "www.instagram.com"
    if provider == "linkedin":
        return "www.linkedin.com"
    if provider == "tiktok":
        return "vm.tiktok.com" if host == "vm.tiktok.com" else "www.tiktok.com"
    if provider == "x":
        return "x.com"
    if provider == "youtube":
        return "www.youtube.com"
    return host


def _canonical_path(path: str) -> str:
    normalized = re.sub(r"/{2,}", "/", path or "/")
    if normalized != "/":
        normalized = normalized.rstrip("/")
    return normalized or "/"


def _canonical_youtube_parts(host: str, path: str, query: str) -> tuple[str, str]:
    canonical_path = _canonical_path(path)
    if host == "youtu.be":
        video_id = canonical_path.lstrip("/")
        if video_id:
            return "/watch", urlencode([("v", video_id)])

    cleaned_items = _clean_query_items("youtube", query)
    if canonical_path == "/watch":
        return canonical_path, urlencode(cleaned_items)

    return canonical_path, ""


def detect_social_provider(url: str) -> str | None:
    """Return the canonical provider detected from a social URL."""
    try:
        parsed = urlsplit(_coerce_social_url(url))
    except ValueError:
        return None

    if parsed.scheme.lower() not in {"http", "https"}:
        return None

    host = (parsed.hostname or "").lower()
    if not host:
        return None

    return _SOCIAL_PROVIDER_BY_HOST.get(host)


def resolve_social_target(
    url: str,
    *,
    provider: Any | None = None,
) -> ResolvedSocialTarget:
    """Resolve a raw social URL into a canonical provider and URL."""
    parsed = urlsplit(_coerce_social_url(url))
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError("Social URLs must use http or https")

    host = (parsed.hostname or "").lower()
    if not host:
        raise ValueError("Social URLs must include a hostname")

    detected_provider = _SOCIAL_PROVIDER_BY_HOST.get(host)
    if not detected_provider:
        raise ValueError("Unsupported social provider URL")

    declared_provider = (
        normalize_social_provider(provider) if provider is not None else None
    )
    if provider is not None and not declared_provider:
        raise ValueError("Unsupported social provider")
    if declared_provider and declared_provider != detected_provider:
        raise ValueError("Social URL does not match the declared provider")

    canonical_host = _canonical_host(detected_provider, host)
    if detected_provider == "youtube":
        canonical_path, canonical_query = _canonical_youtube_parts(
            host,
            parsed.path,
            parsed.query,
        )
    else:
        canonical_path = _canonical_path(parsed.path)
        canonical_query = ""

    resolved_url = urlunsplit(
        (
            "https",
            canonical_host,
            canonical_path,
            canonical_query,
            "",
        )
    )
    return ResolvedSocialTarget(provider=detected_provider, url=resolved_url)


def normalize_social_url(url: str, *, provider: Any | None = None) -> str:
    """Return a canonical https social URL for a supported provider."""
    return resolve_social_target(url, provider=provider).url


__all__ = [
    "DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST",
    "DEFAULT_SOCIAL_PROVIDER_ALLOWLIST",
    "SOCIAL_EMBEDS_PATH",
    "SOCIAL_INTEGRATION_BASE_PATH",
    "SOCIAL_INTEGRATION_EMBEDS_PATH",
    "SOCIAL_LAYOUT_VARIANTS",
    "SOCIAL_LINK_TREE_PATH",
    "SOCIAL_PROVIDER_CATALOG",
    "ResolvedSocialTarget",
    "SocialProviderMetadata",
    "default_social_module_options",
    "detect_social_provider",
    "get_social_provider_metadata",
    "normalize_social_module_options",
    "normalize_social_provider",
    "normalize_social_provider_allowlist",
    "normalize_social_url",
    "resolve_social_module_options",
    "resolve_social_target",
    "social_provider_supports_embeds",
    "validate_social_module_options",
]
