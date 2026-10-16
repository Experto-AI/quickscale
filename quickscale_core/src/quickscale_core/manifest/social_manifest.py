"""Social module manifest-driven adapter code.

Provides the provider catalog, URL helpers, and managed-file renderers that
the module-owned :mod:`quickscale_modules_social.adapter` requires. Relocated
from the previous ``quickscale_cli.social_manifest`` adapter during T2.3 Phase 4.
"""

from __future__ import annotations

from dataclasses import dataclass
from pprint import pformat
import re
from textwrap import dedent
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from quickscale_core.contracts.module_discovery import resolve_manifest_base_path
from quickscale_core.contracts.module_options import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.manifest.loader import load_manifest_from_path


SOCIAL_LAYOUT_VARIANTS: tuple[str, ...] = ("list", "cards", "grid")
SOCIAL_STATUS_ENABLED: str = "enabled"
SOCIAL_STATUS_EMPTY: str = "empty"
SOCIAL_STATUS_DISABLED: str = "disabled"
SOCIAL_STATUS_ERROR: str = "error"
SOCIAL_PAYLOAD_STATUSES: tuple[str, ...] = (
    SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_ERROR,
)
SOCIAL_PAYLOAD_HTTP_STATUS: dict[str, int] = {
    SOCIAL_STATUS_ENABLED: 200,
    SOCIAL_STATUS_EMPTY: 200,
    SOCIAL_STATUS_DISABLED: 200,
    SOCIAL_STATUS_ERROR: 503,
}

_SCHEMELESS_URL_PATTERN: re.Pattern[str] = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Za-z]{2,}(?:[:/].*)?$"
)
_PROVIDER_TOKEN_PATTERN: re.Pattern[str] = re.compile(r"[^a-z0-9-]+")
_MULTI_DASH_PATTERN: re.Pattern[str] = re.compile(r"-{2,}")
_TRACKING_QUERY_PREFIXES: tuple[str, ...] = ("utm_",)
_TRACKING_QUERY_NAMES: set[str] = {
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

_SOCIAL_PROVIDER_BY_NAME: dict[str, SocialProviderMetadata] = {
    p.name: p for p in SOCIAL_PROVIDER_CATALOG
}
_SOCIAL_PROVIDER_ALIASES: dict[str, str] = {
    alias: p.name for p in SOCIAL_PROVIDER_CATALOG for alias in (p.name, *p.aliases)
}
_SOCIAL_PROVIDER_BY_HOST: dict[str, str] = {
    host: p.name for p in SOCIAL_PROVIDER_CATALOG for host in p.hosts
}

DEFAULT_SOCIAL_PROVIDER_ALLOWLIST: tuple[str, ...] = tuple(
    p.name for p in SOCIAL_PROVIDER_CATALOG
)
DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST: tuple[str, ...] = tuple(
    p.name for p in SOCIAL_PROVIDER_CATALOG if p.supports_embeds
)


def load_social_manifest() -> Any:
    """Load the social module manifest from ``module.yml``.

    The manifest path is resolved dynamically at call time via
    :func:`~quickscale_core.contracts.module_discovery.resolve_manifest_base_path`
    so that any runtime override set via
    :func:`~quickscale_core.contracts.module_discovery.set_modules_base_path`
    is picked up correctly, and so an installed wheel with no source workspace
    falls back to the bundled manifest snapshots.
    """
    manifest_path = resolve_manifest_base_path() / "social" / "module.yml"
    return load_manifest_from_path(manifest_path)


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
    return _SOCIAL_PROVIDER_BY_NAME.get(normalized)


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
        canonical_path_val, canonical_query = _canonical_youtube_parts(
            host,
            parsed.path,
            parsed.query,
        )
    else:
        canonical_path_val = _canonical_path(parsed.path)
        canonical_query = ""
    resolved_url = urlunsplit(
        ("https", canonical_host, canonical_path_val, canonical_query, ""),
    )
    return ResolvedSocialTarget(provider=detected_provider, url=resolved_url)


def normalize_social_url(url: str, *, provider: Any | None = None) -> str:
    """Return a canonical https social URL for a supported provider."""
    return resolve_social_target(url, provider=provider).url


# Managed-file renderers


def render_social_managed_init_module() -> str:
    """Render the ``quickscale_managed/__init__.py`` managed file content."""
    return (
        '"""QuickScale managed integration package.\n\n'
        "DO NOT EDIT MANUALLY. This package is regenerated by QuickScale.\n"
        '"""\n'
    )


def render_social_managed_urls_module() -> str:
    """Render the ``quickscale_managed/social_urls.py`` managed file content."""
    return dedent('''
        """QuickScale managed social integration URLs.

        DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.
        """

        from django.urls import path

        from .social_views import SocialEmbedsPayloadView, SocialLinkTreePayloadView

        app_name = "quickscale_managed_social"

        urlpatterns = [
            path("", SocialLinkTreePayloadView.as_view(), name="link_tree"),
            path("embeds/", SocialEmbedsPayloadView.as_view(), name="embeds"),
        ]
        ''').lstrip()


def render_social_managed_views_module(
    provider_allowlist: list[str],
    embed_provider_allowlist: list[str],
    *,
    layout_variant: str,
    cache_ttl_seconds: int,
    links_per_page: int,
    embeds_per_page: int,
) -> str:
    """Render the ``quickscale_managed/social_views.py`` managed file content.

    The rendered views are DRF views (Module Conventions rule 9): a public
    read API declares its guard explicitly (``AllowAny`` plus empty
    ``authentication_classes``), a failed payload build answers DRF's 503
    through core's exception handler — rule 9's one error shape, never the
    stored exception text — and the composed ``REST_FRAMEWORK`` defaults
    make the payload endpoints JSON-only, so the view pins no renderer.
    """
    provider_allowlist_text = pformat(provider_allowlist, width=88)
    embed_provider_allowlist_text = pformat(embed_provider_allowlist, width=88)

    return dedent(f'''
        """QuickScale managed social integration views.

        DO NOT EDIT MANUALLY. This file is regenerated by QuickScale.
        """

        from __future__ import annotations

        from typing import Any

        from rest_framework.exceptions import APIException
        from rest_framework.permissions import AllowAny
        from rest_framework.response import Response
        from rest_framework.views import APIView

        from quickscale_modules_orgs.current_org import get_current_org, org_scope

        DEFAULT_PROVIDER_ALLOWLIST = {provider_allowlist_text}
        DEFAULT_EMBED_PROVIDER_ALLOWLIST = {embed_provider_allowlist_text}
        DEFAULT_LINK_TREE_PATH = "{SOCIAL_LINK_TREE_PATH}"
        DEFAULT_EMBEDS_PATH = "{SOCIAL_EMBEDS_PATH}"
        DEFAULT_INTEGRATION_BASE_PATH = "{SOCIAL_INTEGRATION_BASE_PATH}"
        DEFAULT_INTEGRATION_EMBEDS_PATH = "{SOCIAL_INTEGRATION_EMBEDS_PATH}"
        DEFAULT_LAYOUT_VARIANT = "{layout_variant}"
        DEFAULT_CACHE_TTL_SECONDS = {cache_ttl_seconds}
        DEFAULT_LINKS_PER_PAGE = {links_per_page}
        DEFAULT_EMBEDS_PER_PAGE = {embeds_per_page}


        class SocialPayloadUnavailable(APIException):
            """503 for a failed public payload build.

            The one QuickScale exception handler renders this as rule 9's
            error shape with a stable ``service_unavailable`` code; the stored
            exception is chained for logs only and never reaches the response.
            """

            status_code = 503
            default_code = "service_unavailable"
            default_detail = "Unable to load the social payload."


        class _SocialPayloadView(APIView):
            """Public social payload endpoint base (Module Conventions rule 9).

            The guard is declared on the view: ``authentication_classes`` is
            empty (a public page presents no session) and ``AllowAny`` is the
            explicit public declaration.  A failed payload build answers DRF's
            503 through the one QuickScale exception handler — rule 9's shape,
            with no exception text echoed to the caller.
            """

            authentication_classes: list[Any] = []
            permission_classes = [AllowAny]
            http_method_names = ["get"]

            error_message = "Unable to load the social payload."

            def get(self, request: Any) -> Response:
                try:
                    return Response(self.build_payload(request))
                except Exception as error:
                    raise SocialPayloadUnavailable(self.error_message) from error

            def build_payload(self, request: Any) -> dict[str, Any]:
                raise NotImplementedError


        class SocialLinkTreePayloadView(_SocialPayloadView):
            """Public link-tree payload endpoint."""

            error_message = "Unable to load the social link tree payload."

            def build_payload(self, request: Any) -> dict[str, Any]:
                from quickscale_modules_orgs.models import Organization
                from quickscale_modules_social.services import (
                    build_social_link_tree_payload,
                )

                org = get_current_org(request)
                resolved_org = (
                    org if org is not None else Organization.objects.get_system_org()
                )
                with org_scope(resolved_org):
                    return build_social_link_tree_payload()


        class SocialEmbedsPayloadView(_SocialPayloadView):
            """Public embeds payload endpoint."""

            error_message = "Unable to load the social embeds payload."

            def build_payload(self, request: Any) -> dict[str, Any]:
                from quickscale_modules_orgs.models import Organization
                from quickscale_modules_social.services import (
                    build_social_embeds_payload,
                )

                org = get_current_org(request)
                resolved_org = (
                    org if org is not None else Organization.objects.get_system_org()
                )
                with org_scope(resolved_org):
                    return build_social_embeds_payload()
        ''').lstrip()


__all__ = [
    "DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST",
    "DEFAULT_SOCIAL_PROVIDER_ALLOWLIST",
    "SOCIAL_LAYOUT_VARIANTS",
    "SOCIAL_PAYLOAD_HTTP_STATUS",
    "SOCIAL_PAYLOAD_STATUSES",
    "SOCIAL_PROVIDER_CATALOG",
    "SOCIAL_STATUS_DISABLED",
    "SOCIAL_STATUS_EMPTY",
    "SOCIAL_STATUS_ENABLED",
    "SOCIAL_STATUS_ERROR",
    "ResolvedSocialTarget",
    "SocialProviderMetadata",
    "detect_social_provider",
    "get_social_provider_metadata",
    "load_social_manifest",
    "normalize_social_provider",
    "normalize_social_url",
    "render_social_managed_init_module",
    "render_social_managed_urls_module",
    "render_social_managed_views_module",
    "resolve_social_target",
    "social_payload_status_code",
    "social_provider_supports_embeds",
]
