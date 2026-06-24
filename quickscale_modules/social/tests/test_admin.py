"""Tests for social module admin workflows."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.test import Client, RequestFactory
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
        self, admin_client: Client, org
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
                "organization": str(org.pk),
                "_save": "Save",
            },
        )

        link = SocialLink.all_objects.get()

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
        self, admin_client: Client, org
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
                "organization": str(org.pk),
                "_save": "Save",
            },
        )

        embed = SocialEmbed.all_objects.get()

        assert response.status_code == 302
        assert embed.resolution_status == SOCIAL_EMBED_RESOLUTION_RESOLVED
        assert embed.resolved_embed_url == "https://www.youtube.com/embed/abc123?rel=0"
        assert embed.last_resolution_attempt_at is not None

    def test_social_embed_add_view_rejects_non_embed_provider(
        self, admin_client: Client, org
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
                "organization": str(org.pk),
                "_save": "Save",
            },
        )

        assert response.status_code == 200
        assert SocialEmbed.objects.count() == 0
        assert "Embeds support only TikTok and YouTube" in response.content.decode(
            "utf-8"
        )


@pytest.mark.django_db
class TestSocialAdminOperatorPaths:
    """Phase F11.13a: verify social admin surfaces use all_objects for cross-tenant visibility."""

    def test_social_link_admin_uses_operator_queryset(self) -> None:
        """SocialLinkAdmin.get_queryset uses self.model.all_objects."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        site = AdminSite()
        admin_instance = SocialLinkAdmin(SocialLink, site)
        request = RequestFactory().get("/admin/")
        qs = admin_instance.get_queryset(request)
        assert qs.model == SocialLink
        assert str(qs.query) == str(SocialLink.all_objects.all().query)

    def test_social_embed_admin_uses_operator_queryset(self) -> None:
        """SocialEmbedAdmin.get_queryset uses self.model.all_objects."""
        from quickscale_modules_social.admin import SocialEmbedAdmin

        site = AdminSite()
        admin_instance = SocialEmbedAdmin(SocialEmbed, site)
        request = RequestFactory().get("/admin/")
        qs = admin_instance.get_queryset(request)
        assert qs.model == SocialEmbed
        assert str(qs.query) == str(SocialEmbed.all_objects.all().query)

    def test_social_link_admin_queryset_returns_cross_tenant_links(
        self, org_a, org_b
    ) -> None:
        """Operator admin queryset returns links from all organizations."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        SocialLink.objects.create(
            title="Link A",
            url="https://www.linkedin.com/company/org-a/",
            organization=org_a,
        )
        SocialLink.objects.create(
            title="Link B",
            url="https://www.linkedin.com/company/org-b/",
            organization=org_b,
        )

        site = AdminSite()
        admin_instance = SocialLinkAdmin(SocialLink, site)
        request = RequestFactory().get("/admin/")
        qs = admin_instance.get_queryset(request)
        titles = list(qs.values_list("title", flat=True))
        assert "Link A" in titles
        assert "Link B" in titles

    # ------------------------------------------------------------------
    # Spy-based seam verification: prove all_objects is actually called
    # ------------------------------------------------------------------

    def test_social_link_admin_get_queryset_calls_all_objects(self) -> None:
        """SocialLinkAdmin.get_queryset actually calls SocialLink.all_objects.all()."""
        from quickscale_modules_social.admin import SocialLinkAdmin

        with patch.object(SocialLink, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = SocialLink.objects.none()
            site = AdminSite()
            admin_instance = SocialLinkAdmin(SocialLink, site)
            request = RequestFactory().get("/admin/")
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()

    def test_social_embed_admin_get_queryset_calls_all_objects(self) -> None:
        """SocialEmbedAdmin.get_queryset actually calls SocialEmbed.all_objects.all()."""
        from quickscale_modules_social.admin import SocialEmbedAdmin

        with patch.object(SocialEmbed, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = SocialEmbed.objects.none()
            site = AdminSite()
            admin_instance = SocialEmbedAdmin(SocialEmbed, site)
            request = RequestFactory().get("/admin/")
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()
