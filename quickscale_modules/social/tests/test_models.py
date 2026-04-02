"""Tests for social module data models."""

from __future__ import annotations

import pytest
from django.core.exceptions import ValidationError
from django.test import override_settings

from quickscale_modules_social.models import SocialEmbed, SocialLink


@pytest.mark.django_db
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


@pytest.mark.django_db
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


@pytest.mark.django_db
def test_social_embed_requires_embed_capable_provider() -> None:
    """Only TikTok and YouTube should be accepted for stored social embeds."""
    with pytest.raises(ValidationError) as exc_info:
        SocialEmbed.objects.create(
            title="QuickScale on Instagram",
            provider_name="",
            url="https://www.instagram.com/quickscale/",
        )

    assert "TikTok and YouTube" in str(exc_info.value)
