"""Tests for social module admin workflows."""

from __future__ import annotations

import pytest
from django.contrib import admin
from django.test import Client
from django.urls import reverse

from quickscale_modules_social.contracts import SOCIAL_EMBED_RESOLUTION_RESOLVED
from quickscale_modules_social.models import SocialEmbed, SocialLink


@pytest.mark.django_db
class TestSocialAdmin:
    def test_models_are_registered(self) -> None:
        """Both curated social models should be available in Django admin."""
        assert admin.site.is_registered(SocialLink)
        assert admin.site.is_registered(SocialEmbed)

    def test_social_link_add_view_creates_normalized_record(
        self, admin_client: Client
    ) -> None:
        """Admin link creation should normalize provider and URL values on save."""
        response = admin_client.post(
            reverse("admin:quickscale_modules_social_sociallink_add"),
            {
                "title": "QuickScale on YouTube",
                "description": "Launch clips and demos.",
                "provider_name": "",
                "url": "https://youtu.be/abc123?si=share",
                "is_published": "on",
                "display_order": "4",
                "_save": "Save",
            },
        )

        link = SocialLink.objects.get()

        assert response.status_code == 302
        assert link.provider_name == "youtube"
        assert link.normalized_url == "https://www.youtube.com/watch?v=abc123"

    def test_social_embed_admin_exposes_resolution_fields(self) -> None:
        """The admin should surface embed resolution state and metadata to operators."""
        social_embed_admin = admin.site._registry[SocialEmbed]

        assert "resolution_status" in social_embed_admin.list_display
        assert "resolution_status" in social_embed_admin.list_filter
        for field_name in [
            "resolution_status",
            "resolution_error",
            "last_resolution_attempt_at",
            "last_resolved_at",
            "resolved_embed_url",
            "resolved_thumbnail_url",
        ]:
            assert field_name in social_embed_admin.readonly_fields
        assert any(
            "resolution_status" in fieldset[1]["fields"]
            for fieldset in social_embed_admin.fieldsets
        )
        assert any(
            "resolved_embed_url" in fieldset[1]["fields"]
            for fieldset in social_embed_admin.fieldsets
        )

    def test_social_embed_add_view_records_resolution_metadata(
        self, admin_client: Client
    ) -> None:
        """Admin embed creation should persist backend-owned resolution metadata."""
        response = admin_client.post(
            reverse("admin:quickscale_modules_social_socialembed_add"),
            {
                "title": "QuickScale launch short",
                "description": "Short-form launch clip.",
                "provider_name": "",
                "url": "https://www.youtube.com/shorts/abc123",
                "is_published": "on",
                "display_order": "2",
                "_save": "Save",
            },
        )

        embed = SocialEmbed.objects.get()

        assert response.status_code == 302
        assert embed.resolution_status == SOCIAL_EMBED_RESOLUTION_RESOLVED
        assert embed.resolved_embed_url == "https://www.youtube.com/embed/abc123?rel=0"
        assert embed.last_resolution_attempt_at is not None

    def test_social_embed_add_view_rejects_non_embed_provider(
        self, admin_client: Client
    ) -> None:
        """Admin embed creation should reject providers without approved embed support."""
        response = admin_client.post(
            reverse("admin:quickscale_modules_social_socialembed_add"),
            {
                "title": "QuickScale on Instagram",
                "description": "Social photos.",
                "provider_name": "",
                "url": "https://www.instagram.com/quickscale/",
                "is_published": "on",
                "display_order": "2",
                "_save": "Save",
            },
        )

        assert response.status_code == 200
        assert SocialEmbed.objects.count() == 0
        assert "Embeds support only TikTok and YouTube" in response.content.decode(
            "utf-8"
        )
