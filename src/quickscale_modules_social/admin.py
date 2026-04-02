"""Admin configuration for the QuickScale social module."""

from django.contrib import admin

from quickscale_modules_social.models import SocialEmbed, SocialLink


@admin.register(SocialLink)
class SocialLinkAdmin(admin.ModelAdmin):
    """Admin workflow for curated link-tree records."""

    list_display = [
        "title",
        "provider_name",
        "is_published",
        "display_order",
        "updated_at",
    ]
    list_filter = ["provider_name", "is_published"]
    search_fields = ["title", "description", "url", "normalized_url"]
    readonly_fields = ["normalized_url", "created_at", "updated_at"]
    ordering = ["display_order", "title", "pk"]
    fieldsets = [
        (
            "Link details",
            {
                "fields": [
                    "title",
                    "description",
                    "provider_name",
                    "url",
                    "is_published",
                    "display_order",
                ]
            },
        ),
        (
            "Normalized record",
            {
                "fields": ["normalized_url", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]


@admin.register(SocialEmbed)
class SocialEmbedAdmin(admin.ModelAdmin):
    """Admin workflow for curated embed-capable records."""

    list_display = [
        "title",
        "provider_name",
        "is_published",
        "display_order",
        "updated_at",
    ]
    list_filter = ["provider_name", "is_published"]
    search_fields = ["title", "description", "url", "normalized_url"]
    readonly_fields = ["normalized_url", "created_at", "updated_at"]
    ordering = ["display_order", "title", "pk"]
    fieldsets = [
        (
            "Embed details",
            {
                "fields": [
                    "title",
                    "description",
                    "provider_name",
                    "url",
                    "is_published",
                    "display_order",
                ]
            },
        ),
        (
            "Normalized record",
            {
                "fields": ["normalized_url", "created_at", "updated_at"],
                "classes": ["collapse"],
            },
        ),
    ]
