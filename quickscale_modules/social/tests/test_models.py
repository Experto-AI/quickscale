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
def test_social_link_save_detects_provider_and_normalizes_url(org_context) -> None:
    """Curated links should persist canonical provider and URL data."""
    link = SocialLink.objects.create(
        title="QuickScale on Instagram",
        provider_name="",
        url="https://www.instagram.com/quickscale/?igshid=abc&utm_source=share",
        description="Photo updates.",
        display_order=3,
        organization=org_context,
    )

    assert link.provider_name == "instagram"
    assert link.normalized_url == "https://www.instagram.com/quickscale"
    assert str(link) == "QuickScale on Instagram"


@django_db
def test_social_link_rejects_provider_outside_runtime_allowlist(org_context) -> None:
    """Stored social links must obey the current settings-managed provider allowlist."""
    with override_settings(QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST=["youtube"]):
        with pytest.raises(ValidationError) as exc_info:
            SocialLink.objects.create(
                title="QuickScale on LinkedIn",
                provider_name="",
                url="https://www.linkedin.com/company/quickscale/",
                organization=org_context,
            )

    assert "allowlisted" in str(exc_info.value)


@django_db
def test_social_embed_requires_embed_capable_provider(org_context) -> None:
    """Only TikTok and YouTube should be accepted for stored social embeds."""
    with pytest.raises(ValidationError) as exc_info:
        SocialEmbed.objects.create(
            title="QuickScale on Instagram",
            provider_name="",
            url="https://www.instagram.com/quickscale/",
            organization=org_context,
        )

    assert "TikTok and YouTube" in str(exc_info.value)


@django_db
def test_social_embed_save_persists_backend_resolution_metadata(org_context) -> None:
    """Curated embeds should persist backend-owned preview metadata on save."""
    embed = SocialEmbed.objects.create(
        title="QuickScale launch short",
        provider_name="",
        url="https://www.youtube.com/shorts/abc123",
        description="Short-form launch clip.",
        organization=org_context,
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
def test_social_embed_records_operator_visible_resolution_error(org_context) -> None:
    """Unresolvable share links should persist an explicit operator-facing error state."""
    embed = SocialEmbed.objects.create(
        title="QuickScale teaser",
        provider_name="",
        url="https://vm.tiktok.com/ZM1234567/",
        organization=org_context,
    )

    assert embed.provider_name == "tiktok"
    assert embed.resolution_status == SOCIAL_EMBED_RESOLUTION_ERROR
    assert "canonical TikTok video URL" in embed.resolution_error
    assert embed.resolved_embed_url == ""
    assert embed.last_resolution_attempt_at is not None
    assert embed.last_resolved_at is None


@django_db
def test_social_embed_does_not_rerun_resolution_for_unrelated_updates(
    org_context,
) -> None:
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
            organization=org_context,
        )
        first_attempt_at = embed.last_resolution_attempt_at

        embed.title = "QuickScale launch short v2"
        embed.save()
        embed.refresh_from_db()

    assert mock_resolve.call_count == 1
    assert embed.last_resolution_attempt_at == first_attempt_at


@django_db
def test_social_link_can_be_created_with_organization() -> None:
    """Social links should accept an organization FK."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org = Organization.objects.create(name="Test Org", slug="test-org")
    set_current_org_id(org.id)
    try:
        link = SocialLink.objects.create(
            title="QuickScale on LinkedIn",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
            organization=org,
        )

        assert link.organization_id == org.id
        assert link.organization == org
    finally:
        set_current_org_id(None)


@django_db
def test_social_embed_can_be_created_with_organization() -> None:
    """Social embeds should accept an organization FK."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org = Organization.objects.create(name="Test Org", slug="test-org")
    set_current_org_id(org.id)
    try:
        embed = SocialEmbed.objects.create(
            title="QuickScale launch video",
            provider_name="",
            url="https://www.youtube.com/shorts/abc123",
            display_order=5,
            organization=org,
        )

        assert embed.organization_id == org.id
        assert embed.organization == org
    finally:
        set_current_org_id(None)


@django_db
def test_social_item_tenant_manager_auto_scopes_to_org_context() -> None:
    """The TenantManager should auto-scope queries to the current org context."""
    from quickscale_modules_orgs.current_org import (
        operator_access,
        set_current_org_id,
    )
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    set_current_org_id(org_a.id)
    SocialLink.objects.create(
        title="Org A Link",
        provider_name="",
        url="https://www.linkedin.com/company/org-a/",
        display_order=10,
        organization=org_a,
    )
    set_current_org_id(org_b.id)
    SocialLink.objects.create(
        title="Org B Link",
        provider_name="",
        url="https://www.linkedin.com/company/org-b/",
        display_order=20,
        organization=org_b,
    )

    # Scope to Org A — only Org A's link should be visible.
    set_current_org_id(org_a.id)
    org_a_links = list(SocialLink.objects.filter(is_published=True))
    assert [link.title for link in org_a_links] == ["Org A Link"]

    # Scope to Org B — only Org B's link should be visible.
    set_current_org_id(org_b.id)
    org_b_links = list(SocialLink.objects.filter(is_published=True))
    assert [link.title for link in org_b_links] == ["Org B Link"]

    # Reset context — TenantManager returns .none() (fail-closed).
    set_current_org_id(None)
    no_context_links = list(SocialLink.objects.filter(is_published=True))
    assert no_context_links == []

    # all_objects escape hatch with operator_access — the FOR ALL policy
    # requires current_org_id = organization_id, so cross-org reads need
    # operator_access to extend the FOR SELECT sub-policy (SA14.5).
    set_current_org_id(org_b.id)
    with operator_access(reason="verify all_objects cross-org read"):
        all_links = list(SocialLink.all_objects.filter(is_published=True))
    assert len(all_links) == 2

    # Clean up context for other tests.
    set_current_org_id(None)


@django_db
def test_social_item_all_objects_returns_all_rows() -> None:
    """The ``all_objects`` operator manager should return all rows."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org = Organization.objects.create(name="Test Org", slug="test-org")
    set_current_org_id(org.id)
    try:
        SocialLink.objects.create(
            title="Test Link",
            provider_name="",
            url="https://www.linkedin.com/company/test/",
            display_order=10,
            organization=org,
        )

        assert SocialLink.all_objects.count() == 1
        assert SocialEmbed.all_objects.count() == 0
    finally:
        set_current_org_id(None)


@django_db
def test_social_link_normalized_url_no_longer_globally_unique() -> None:
    """Multiple orgs may link to the same social URL without unique constraint violation."""
    from quickscale_modules_orgs.current_org import set_current_org_id
    from quickscale_modules_orgs.models import Organization

    org_a = Organization.objects.create(name="Org A", slug="org-a")
    org_b = Organization.objects.create(name="Org B", slug="org-b")

    set_current_org_id(org_a.id)
    try:
        link_a = SocialLink.objects.create(
            title="Org A Link",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=10,
            organization=org_a,
        )
    finally:
        set_current_org_id(None)

    set_current_org_id(org_b.id)
    try:
        link_b = SocialLink.objects.create(
            title="Org B Link",
            provider_name="",
            url="https://www.linkedin.com/company/quickscale/",
            display_order=20,
            organization=org_b,
        )
    finally:
        set_current_org_id(None)

    # Both should have the same normalized_url
    assert link_a.normalized_url == link_b.normalized_url
    assert link_a.normalized_url == "https://www.linkedin.com/company/quickscale"
