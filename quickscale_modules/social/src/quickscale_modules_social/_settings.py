"""Private settings snapshot for the social module.

Rule 42: the runtime view of the module's settings lives here as a frozen
dataclass built by ``from_settings()``, reading each setting directly with no
default and no coercion.  ``services.py`` re-exports the names defined here
(Module Conventions rule 28) so existing imports and patch targets keep
working; the snapshot stays out of ``services.__all__``.
"""

from __future__ import annotations

from dataclasses import dataclass

from django.conf import settings


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

    @classmethod
    def from_settings(cls) -> SocialRuntimeSettingsSnapshot:
        """Create a snapshot from Django settings.

        Rule 3: every value is read directly from Django settings, which the
        module's generic startup check has validated against the manifest's
        schema — the layout choices, the provider allowlist's closed set and
        non-emptiness, the numeric bounds, and the cross-option rules that keep
        one public surface enabled and embeds backed by an embed-capable
        provider.  Apply writes canonical values, so no coercion happens here.
        """
        return cls(
            link_tree_enabled=settings.QUICKSCALE_SOCIAL_LINK_TREE_ENABLED,
            layout_variant=settings.QUICKSCALE_SOCIAL_LAYOUT_VARIANT,
            embeds_enabled=settings.QUICKSCALE_SOCIAL_EMBEDS_ENABLED,
            provider_allowlist=tuple(settings.QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST),
            cache_ttl_seconds=settings.QUICKSCALE_SOCIAL_CACHE_TTL_SECONDS,
            links_per_page=settings.QUICKSCALE_SOCIAL_LINKS_PER_PAGE,
            embeds_per_page=settings.QUICKSCALE_SOCIAL_EMBEDS_PER_PAGE,
        )


def get_social_runtime_settings() -> SocialRuntimeSettingsSnapshot:
    """Return the authoritative social runtime settings."""
    return SocialRuntimeSettingsSnapshot.from_settings()
