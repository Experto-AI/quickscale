"""Tests for social module data models."""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar, cast
from unittest.mock import patch

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from quickscale_modules_social.contracts import (
    ResolvedSocialEmbedMetadata,
    SOCIAL_EMBED_RESOLUTION_ERROR,
    SOCIAL_EMBED_RESOLUTION_RESOLVED,
)
from quickscale_modules_social.models import SocialEmbed, SocialLink


TestFunction = TypeVar("TestFunction", bound=Callable[..., object])
django_db = cast(Callable[[TestFunction], TestFunction], pytest.mark.django_db)


@django_db
def test_social_link_save_detects_provider_and_normalizes_url() -> None:
    """Curated links should persist canonical provider and URL data."""
    link = SocialLink.objects.create(
        title="QuickScale on Instagram",
        provider_name="",
        url="https://www.instagram.com/quickscale/?igshid=abc&utm_source=share",
        description="Photo updates.",
        display_order=3,
    )

    assert link.provider_name == "instagram"
    assert link.normalized_url == "https://www.instagram.com/quickscale"
    assert str(link) == "QuickScale on Instagram"


@django_db
def test_social_link_rejects_provider_outside_runtime_allowlist() -> None:
    """Stored social links must obey the current settings-managed provider allowlist."""
    with override_settings(QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"]):
        with pytest.raises(ValidationError) as exc_info:
            SocialLink.objects.create(
                title="QuickScale on LinkedIn",
                provider_name="",
                url="https://www.linkedin.com/company/quickscale/",
            )

    assert "allowlisted" in str(exc_info.value)


@django_db
def test_social_embed_requires_embed_capable_provider() -> None:
    """Only TikTok and YouTube should be accepted for stored social embeds."""
    with pytest.raises(ValidationError) as exc_info:
        SocialEmbed.objects.create(
            title="QuickScale on Instagram",
            provider_name="",
            url="https://www.instagram.com/quickscale/",
        )

    assert "TikTok and YouTube" in str(exc_info.value)


@django_db
def test_social_embed_save_persists_backend_resolution_metadata() -> None:
    """Curated embeds should persist backend-owned preview metadata on save."""
    embed = SocialEmbed.objects.create(
        title="QuickScale launch short",
        provider_name="",
        url="https://www.youtube.com/shorts/abc123",
        description="Short-form launch clip.",
    )

    assert embed.provider_name == "youtube"
    assert embed.normalized_url == "https://www.youtube.com/shorts/abc123"
    assert embed.resolution_status == SOCIAL_EMBED_RESOLUTION_RESOLVED
    assert embed.resolved_embed_url == "https://www.youtube.com/embed/abc123?rel=0"
    assert embed.resolved_thumbnail_url == "https://i.ytimg.com/vi/abc123/hqdefault.jpg"
    assert embed.resolved_width == 560
    assert embed.resolved_height == 315
    assert embed.resolved_thumbnail_width == 480
    assert embed.resolved_thumbnail_height == 360
    assert embed.last_resolution_attempt_at is not None
    assert embed.last_resolved_at == embed.last_resolution_attempt_at


@django_db
def test_social_embed_records_operator_visible_resolution_error() -> None:
    """Unresolvable share links should persist an explicit operator-facing error state."""
    embed = SocialEmbed.objects.create(
        title="QuickScale teaser",
        provider_name="",
        url="https://vm.tiktok.com/ZM1234567/",
    )

    assert embed.provider_name == "tiktok"
    assert embed.resolution_status == SOCIAL_EMBED_RESOLUTION_ERROR
    assert "canonical TikTok video URL" in embed.resolution_error
    assert embed.resolved_embed_url == ""
    assert embed.last_resolution_attempt_at is not None
    assert embed.last_resolved_at is None


@django_db
def test_social_embed_does_not_rerun_resolution_for_unrelated_updates() -> None:
    """Editing non-URL fields should not re-run embed resolution for stable records."""
    with patch(
        "quickscale_modules_social.models.resolve_social_embed_metadata",
        return_value=ResolvedSocialEmbedMetadata(
            embed_url="https://www.youtube.com/embed/abc123?rel=0",
            thumbnail_url="https://i.ytimg.com/vi/abc123/hqdefault.jpg",
            embed_width=560,
            embed_height=315,
            thumbnail_width=480,
            thumbnail_height=360,
        ),
    ) as mock_resolve:
        embed = SocialEmbed.objects.create(
            title="QuickScale launch short",
            provider_name="",
            url="https://www.youtube.com/shorts/abc123",
        )
        first_attempt_at = embed.last_resolution_attempt_at

        embed.title = "QuickScale launch short v2"
        embed.save()
        embed.refresh_from_db()

    assert mock_resolve.call_count == 1
    assert embed.last_resolution_attempt_at == first_attempt_at
