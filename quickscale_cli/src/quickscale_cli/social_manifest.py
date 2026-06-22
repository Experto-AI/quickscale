"""Social module manifest-driven configuration adapter.

Replaces the legacy ``social_contract.py`` by sourcing defaults from the social
``module.yml`` manifest and routing core normalization, validation, and
resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

The public API is a drop-in replacement for the old contract file so callers in
``apply_command.py`` and ``module_config.py`` can use it without rewriting
their logic.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from pprint import pformat
import re
from textwrap import dedent
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from quickscale_core.manifest.derivation import (
    DerivedSetting,
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

SOCIAL_LINK_TREE_PATH = "/social"
SOCIAL_EMBEDS_PATH = "/social/embeds"
SOCIAL_INTEGRATION_BASE_PATH = "/_quickscale/social/"
SOCIAL_INTEGRATION_EMBEDS_PATH = "/_quickscale/social/embeds/"
SOCIAL_LAYOUT_VARIANTS = ("list", "cards", "grid")
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

_REPO_ROOT = Path(__file__).resolve().parents[3]
_SOCIAL_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "social" / "module.yml"


def load_social_manifest() -> Any:
    """Load the social module manifest from ``module.yml``.

    Public entry point so manifest adapters and tests can consume the
    manifest-declared ``managed_files`` contract without hardcoding paths.
    """
    return load_manifest_from_path(_SOCIAL_MANIFEST_PATH)


# Backwards-compatible alias for internal callers that used the private name.
_load_social_manifest = load_social_manifest


def _build_social_derivation_schema() -> ModuleDerivationSchema:
    """Build the derivation schema for the social module.

    Captures the normalization and validation rules that the generic resolver
    can execute. Social-specific rules that the resolver does not support
    natively (provider alias normalization and embed-support checks) are applied
    as post-resolution steps in the adapter functions below.
    """

    return ModuleDerivationSchema(
        module_name="social",
        version="1",
        option_derivations={
            "link_tree_enabled": OptionDerivation(
                option_key="link_tree_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_LINK_TREE_ENABLED",
                        source_options=["link_tree_enabled"],
                        derivation_type="direct",
                        expression={"option": "link_tree_enabled"},
                    )
                ],
            ),
            "layout_variant": OptionDerivation(
                option_key="layout_variant",
                normalization_rules=[
                    NormalizationRule(
                        source_key="layout_variant",
                        target_key="layout_variant",
                        rule_type="strip",
                    ),
                    NormalizationRule(
                        source_key="layout_variant",
                        target_key="layout_variant",
                        rule_type="lowercase",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="layout_variant",
                        rule_type="choices",
                        allowed_values=list(SOCIAL_LAYOUT_VARIANTS),
                        description=(
                            "modules.social.layout_variant must be one of: list, cards, grid"
                        ),
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_LAYOUT_VARIANT",
                        source_options=["layout_variant"],
                        derivation_type="direct",
                        expression={"option": "layout_variant"},
                    )
                ],
            ),
            "embeds_enabled": OptionDerivation(
                option_key="embeds_enabled",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_EMBEDS_ENABLED",
                        source_options=["embeds_enabled"],
                        derivation_type="direct",
                        expression={"option": "embeds_enabled"},
                    )
                ],
            ),
            "provider_allowlist": OptionDerivation(
                option_key="provider_allowlist",
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST",
                        source_options=["provider_allowlist"],
                        derivation_type="direct",
                        expression={"option": "provider_allowlist"},
                    )
                ],
            ),
            "cache_ttl_seconds": OptionDerivation(
                option_key="cache_ttl_seconds",
                normalization_rules=[
                    NormalizationRule(
                        source_key="cache_ttl_seconds",
                        target_key="cache_ttl_seconds",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="cache_ttl_seconds",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.social.cache_ttl_seconds must be an integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS",
                        source_options=["cache_ttl_seconds"],
                        derivation_type="direct",
                        expression={"option": "cache_ttl_seconds"},
                    )
                ],
            ),
            "links_per_page": OptionDerivation(
                option_key="links_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="links_per_page",
                        target_key="links_per_page",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="links_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.social.links_per_page must be an integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_LINKS_PER_PAGE",
                        source_options=["links_per_page"],
                        derivation_type="direct",
                        expression={"option": "links_per_page"},
                    )
                ],
            ),
            "embeds_per_page": OptionDerivation(
                option_key="embeds_per_page",
                normalization_rules=[
                    NormalizationRule(
                        source_key="embeds_per_page",
                        target_key="embeds_per_page",
                        rule_type="strip",
                    )
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="embeds_per_page",
                        rule_type="pattern",
                        pattern=r"^\d+$",
                        description="modules.social.embeds_per_page must be an integer",
                    )
                ],
                derived_settings=[
                    DerivedSetting(
                        setting_key="QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE",
                        source_options=["embeds_per_page"],
                        derivation_type="direct",
                        expression={"option": "embeds_per_page"},
                    )
                ],
            ),
        },
    )


def default_social_module_options() -> dict[str, Any]:
    """Return the social module contract defaults."""
    manifest = _load_social_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


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


def normalize_social_module_options(
    options: Mapping[str, Any] | None,
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


def resolve_social_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge default social options with normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction and core
    normalization, then applies social-specific post-resolution normalization for
    provider aliases and layout casing.
    """
    manifest = _load_social_manifest()
    schema = _build_social_derivation_schema()

    cleaned = normalize_social_module_options(options)
    result = resolve_module_config(manifest, schema, overrides=cleaned)
    resolved = dict(result.resolved)

    resolved["provider_allowlist"] = normalize_social_provider_allowlist(
        resolved.get("provider_allowlist", [])
    )
    resolved["layout_variant"] = str(resolved.get("layout_variant", "")).strip().lower()
    return resolved


def validate_social_module_options(options: Mapping[str, Any] | None) -> list[str]:
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
        except (TypeError, ValueError):
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


# ---------------------------------------------------------------------------
# Managed-file renderers
# ---------------------------------------------------------------------------


def render_social_managed_init_module() -> str:
    """Render the ``quickscale_managed/__init__.py`` managed file content."""
    return (
        '"""QuickScale managed integration package.\n\n'
        "DO NOT EDIT MANUALLY. This package is regenerated by QuickScale.\n"
        '"""\n'
    )


def render_social_managed_urls_module() -> str:
    """Render the ``quickscale_managed/social_urls.py`` managed file content."""
    return dedent(
        '''
        """QuickScale managed social integration URLs.

        DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.
        """

        from django.urls import path

        from .social_views import social_embeds_payload, social_link_tree_payload

        app_name = "quickscale_managed_social"

        urlpatterns = [
            path("", social_link_tree_payload, name="quickscale-social-link-tree"),
            path("embeds/", social_embeds_payload, name="quickscale-social-embeds"),
        ]
        '''
    ).lstrip()


def render_social_managed_views_module(
    provider_allowlist: list[str],
    embed_provider_allowlist: list[str],
    *,
    layout_variant: str,
    cache_ttl_seconds: int,
    links_per_page: int,
    embeds_per_page: int,
) -> str:
    """Render the ``quickscale_managed/social_views.py`` managed file content."""
    provider_allowlist_text = pformat(provider_allowlist, width=88)
    embed_provider_allowlist_text = pformat(embed_provider_allowlist, width=88)

    return (
        '"""QuickScale managed social integration views.\n\n'
        "DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.\n"
        '"""\n\n'
        "from __future__ import annotations\n\n"
        "from django.http import HttpRequest, JsonResponse\n"
        "from quickscale_modules_orgs.current_org import get_current_org\n\n"
        f"DEFAULT_PROVIDER_ALLOWLIST = {provider_allowlist_text}\n"
        f"DEFAULT_EMBED_PROVIDER_ALLOWLIST = {embed_provider_allowlist_text}\n"
        f'DEFAULT_LINK_TREE_PATH = "{SOCIAL_LINK_TREE_PATH}"\n'
        f'DEFAULT_EMBEDS_PATH = "{SOCIAL_EMBEDS_PATH}"\n'
        f'DEFAULT_INTEGRATION_BASE_PATH = "{SOCIAL_INTEGRATION_BASE_PATH}"\n'
        f'DEFAULT_INTEGRATION_EMBEDS_PATH = "{SOCIAL_INTEGRATION_EMBEDS_PATH}"\n\n'
        f'DEFAULT_LAYOUT_VARIANT = "{layout_variant}"\n'
        f"DEFAULT_CACHE_TTL_SECONDS = {cache_ttl_seconds}\n"
        f"DEFAULT_LINKS_PER_PAGE = {links_per_page}\n"
        f"DEFAULT_EMBEDS_PER_PAGE = {embeds_per_page}\n"
        "PAYLOAD_STATUS_HTTP = {\n"
        f'    "{SOCIAL_STATUS_ENABLED}": 200,\n'
        f'    "{SOCIAL_STATUS_EMPTY}": 200,\n'
        f'    "{SOCIAL_STATUS_DISABLED}": 200,\n'
        f'    "{SOCIAL_STATUS_ERROR}": 503,\n'
        "}\n\n"
        "def _error_message(exc: Exception, fallback: str) -> str:\n"
        "    message = str(exc).strip()\n"
        "    return message or fallback\n\n"
        "def _error_payload(\n"
        "    *,\n"
        "    surface: str,\n"
        "    public_path: str,\n"
        "    items_key: str,\n"
        "    total_key: str,\n"
        "    per_page_key: str,\n"
        "    per_page_value: int,\n"
        "    message: str,\n"
        "    include_layout: bool = False,\n"
        ") -> dict[str, object]:\n"
        "    payload = {\n"
        '        "module": "social",\n'
        '        "surface": surface,\n'
        f'        "status": "{SOCIAL_STATUS_ERROR}",\n'
        '        "enabled": False,\n'
        '        "public_path": public_path,\n'
        '        "integration_base_path": DEFAULT_INTEGRATION_BASE_PATH,\n'
        '        "integration_embeds_path": DEFAULT_INTEGRATION_EMBEDS_PATH,\n'
        '        "provider_allowlist": list(DEFAULT_PROVIDER_ALLOWLIST),\n'
        '        "embed_provider_allowlist": list(DEFAULT_EMBED_PROVIDER_ALLOWLIST),\n'
        "        per_page_key: per_page_value,\n"
        "        total_key: 0,\n"
        "        items_key: [],\n"
        '        "error": message,\n'
        "    }\n"
        "    if include_layout:\n"
        '        payload["layout_variant"] = DEFAULT_LAYOUT_VARIANT\n'
        "    else:\n"
        '        payload["cache_ttl_seconds"] = DEFAULT_CACHE_TTL_SECONDS\n'
        "    return payload\n\n"
        "def _payload_response(payload: dict[str, object]) -> JsonResponse:\n"
        f'    status = str(payload.get("status", "{SOCIAL_STATUS_ERROR}"))\n'
        f"    return JsonResponse(payload, status=PAYLOAD_STATUS_HTTP.get(status, 503))\n\n"
        "def social_link_tree_payload(request: HttpRequest) -> JsonResponse:\n"
        "    org = get_current_org(request)\n"
        "    try:\n"
        "        from quickscale_modules_social.services import build_social_link_tree_payload\n"
        "\n"
        "        payload = build_social_link_tree_payload(\n"
        "            organization_id=org.id if org is not None else None,\n"
        "        )\n"
        "    except Exception as exc:\n"
        "        payload = _error_payload(\n"
        '            surface="link_tree",\n'
        "            public_path=DEFAULT_LINK_TREE_PATH,\n"
        '            items_key="links",\n'
        '            total_key="total_links",\n'
        '            per_page_key="links_per_page",\n'
        "            per_page_value=DEFAULT_LINKS_PER_PAGE,\n"
        "            include_layout=True,\n"
        '            message=_error_message(exc, "Unable to load social link tree payload."),\n'
        "        )\n"
        "    return _payload_response(payload)\n\n"
        "def social_embeds_payload(request: HttpRequest) -> JsonResponse:\n"
        "    org = get_current_org(request)\n"
        "    try:\n"
        "        from quickscale_modules_social.services import build_social_embeds_payload\n"
        "\n"
        "        payload = build_social_embeds_payload(\n"
        "            organization_id=org.id if org is not None else None,\n"
        "        )\n"
        "    except Exception as exc:\n"
        "        payload = _error_payload(\n"
        '            surface="embeds",\n'
        "            public_path=DEFAULT_EMBEDS_PATH,\n"
        '            items_key="embeds",\n'
        '            total_key="total_embeds",\n'
        '            per_page_key="embeds_per_page",\n'
        "            per_page_value=DEFAULT_EMBEDS_PER_PAGE,\n"
        '            message=_error_message(exc, "Unable to load social embeds payload."),\n'
        "        )\n"
        "    return _payload_response(payload)\n"
    )


__all__ = [
    "DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST",
    "DEFAULT_SOCIAL_PROVIDER_ALLOWLIST",
    "SOCIAL_EMBEDS_PATH",
    "SOCIAL_INTEGRATION_BASE_PATH",
    "SOCIAL_INTEGRATION_EMBEDS_PATH",
    "SOCIAL_LAYOUT_VARIANTS",
    "SOCIAL_PAYLOAD_HTTP_STATUS",
    "SOCIAL_PAYLOAD_STATUSES",
    "SOCIAL_LINK_TREE_PATH",
    "SOCIAL_PROVIDER_CATALOG",
    "SOCIAL_STATUS_DISABLED",
    "SOCIAL_STATUS_EMPTY",
    "SOCIAL_STATUS_ENABLED",
    "SOCIAL_STATUS_ERROR",
    "ResolvedSocialTarget",
    "SocialProviderMetadata",
    "default_social_module_options",
    "detect_social_provider",
    "get_social_provider_metadata",
    "normalize_social_module_options",
    "normalize_social_provider",
    "normalize_social_provider_allowlist",
    "normalize_social_url",
    "render_social_managed_init_module",
    "render_social_managed_urls_module",
    "render_social_managed_views_module",
    "resolve_social_module_options",
    "resolve_social_target",
    "social_payload_status_code",
    "social_provider_supports_embeds",
    "load_social_manifest",
    "validate_social_module_options",
]
