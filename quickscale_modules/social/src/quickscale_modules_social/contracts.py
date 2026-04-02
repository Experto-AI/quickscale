"""Module-owned social contract helpers for runtime and admin consumers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings

SOCIAL_LINK_TREE_PATH = "/social"
SOCIAL_EMBEDS_PATH = "/social/embeds"
SOCIAL_INTEGRATION_BASE_PATH = "/_quickscale/social/"
SOCIAL_INTEGRATION_EMBEDS_PATH = "/_quickscale/social/embeds/"
SOCIAL_LAYOUT_VARIANTS = ("list", "cards", "grid")
SOCIAL_LINKS_CACHE_KEY = "quickscale_modules_social:links"
SOCIAL_EMBEDS_CACHE_KEY = "quickscale_modules_social:embeds"
SOCIAL_STATUS_ENABLED = "enabled"
SOCIAL_STATUS_EMPTY = "empty"
SOCIAL_STATUS_DISABLED = "disabled"
SOCIAL_STATUS_ERROR = "error"
SOCIAL_PAYLOAD_STATUSES = (
    SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_ERROR,
)
SOCIAL_PAYLOAD_HTTP_STATUS = {
    SOCIAL_STATUS_ENABLED: 200,
    SOCIAL_STATUS_EMPTY: 200,
    SOCIAL_STATUS_DISABLED: 200,
    SOCIAL_STATUS_ERROR: 503,
}

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
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


class SocialConfigurationError(Exception):
    """Raised when the runtime social settings are invalid."""


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


@dataclass(frozen=True)
class SocialRuntimeSettingsSnapshot:
    """Read-only runtime view of the authoritative social settings."""

    link_tree_enabled: bool
    layout_variant: str
    embeds_enabled: bool
    provider_allowlist: tuple[str, ...]
    cache_ttl_seconds: int
    links_per_page: int
    embeds_per_page: int


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

SOCIAL_PROVIDER_CHOICES = tuple(
    (provider.name, provider.display_name) for provider in SOCIAL_PROVIDER_CATALOG
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


def social_payload_status_code(status: Any) -> int:
    """Return the managed JSON transport HTTP status for a social payload state."""
    normalized = str(status).strip().lower()
    return SOCIAL_PAYLOAD_HTTP_STATUS.get(
        normalized,
        SOCIAL_PAYLOAD_HTTP_STATUS[SOCIAL_STATUS_ERROR],
    )


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


def _coerce_bool_setting(value: Any, setting_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in _TRUE_VALUES:
            return True
        if lowered in _FALSE_VALUES:
            return False
    raise SocialConfigurationError(f"{setting_name} must be a boolean")


def _coerce_positive_int_setting(value: Any, setting_name: str) -> int:
    try:
        normalized = int(value)
    except (TypeError, ValueError) as exc:
        raise SocialConfigurationError(f"{setting_name} must be an integer") from exc

    if normalized < 1:
        raise SocialConfigurationError(f"{setting_name} must be at least 1")
    return normalized


def get_social_runtime_settings() -> SocialRuntimeSettingsSnapshot:
    """Return the authoritative social runtime settings from Django settings."""
    link_tree_enabled = _coerce_bool_setting(
        getattr(settings, "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED", True),
        "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED",
    )
    embeds_enabled = _coerce_bool_setting(
        getattr(settings, "QUICKSCALE_SOCIAL_EMBEDS_ENABLED", True),
        "QUICKSCALE_SOCIAL_EMBEDS_ENABLED",
    )
    layout_variant = (
        str(getattr(settings, "QUICKSCALE_SOCIAL_LAYOUT_VARIANT", "list"))
        .strip()
        .lower()
    )
    provider_allowlist = tuple(
        normalize_social_provider_allowlist(
            getattr(
                settings,
                "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST",
                DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
            )
        )
    )
    cache_ttl_seconds = _coerce_positive_int_setting(
        getattr(settings, "QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS", 300),
        "QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS",
    )
    links_per_page = _coerce_positive_int_setting(
        getattr(settings, "QUICKSCALE_SOCIAL_LINKS_PER_PAGE", 24),
        "QUICKSCALE_SOCIAL_LINKS_PER_PAGE",
    )
    embeds_per_page = _coerce_positive_int_setting(
        getattr(settings, "QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE", 12),
        "QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE",
    )

    if layout_variant not in SOCIAL_LAYOUT_VARIANTS:
        raise SocialConfigurationError(
            "QUICKSCALE_SOCIAL_LAYOUT_VARIANT must be one of: list, cards, grid"
        )
    if not provider_allowlist:
        raise SocialConfigurationError(
            "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST cannot be empty"
        )

    unknown_providers = [
        provider
        for provider in provider_allowlist
        if provider not in _SOCIAL_PROVIDER_BY_NAME
    ]
    if unknown_providers:
        joined = ", ".join(sorted(unknown_providers))
        raise SocialConfigurationError(
            "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST contains unsupported providers: "
            f"{joined}"
        )
    if not link_tree_enabled and not embeds_enabled:
        raise SocialConfigurationError(
            "QuickScale social must leave link_tree_enabled or embeds_enabled enabled"
        )
    if embeds_enabled and not any(
        social_provider_supports_embeds(provider) for provider in provider_allowlist
    ):
        raise SocialConfigurationError(
            "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST must include TikTok or YouTube when embeds are enabled"
        )

    return SocialRuntimeSettingsSnapshot(
        link_tree_enabled=link_tree_enabled,
        layout_variant=layout_variant,
        embeds_enabled=embeds_enabled,
        provider_allowlist=provider_allowlist,
        cache_ttl_seconds=cache_ttl_seconds,
        links_per_page=links_per_page,
        embeds_per_page=embeds_per_page,
    )


__all__ = [
    "DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST",
    "DEFAULT_SOCIAL_PROVIDER_ALLOWLIST",
    "SOCIAL_EMBEDS_CACHE_KEY",
    "SOCIAL_EMBEDS_PATH",
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
    "SocialRuntimeSettingsSnapshot",
    "get_social_provider_metadata",
    "get_social_runtime_settings",
    "normalize_social_provider",
    "normalize_social_provider_allowlist",
    "normalize_social_url",
    "resolve_social_target",
    "social_payload_status_code",
    "social_provider_supports_embeds",
]
