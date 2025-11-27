"""Admin configuration for QuickScale blog module"""

from django.contrib import admin
from markdownx.admin import MarkdownxModelAdmin

from .models import AuthorProfile, Category, Post, Tag


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin for blog categories"""

    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "description"]


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    """Admin for blog tags"""

    list_display = ["name", "slug"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    """Admin for author profiles"""

    list_display = ["user", "bio"]
    search_fields = ["user__username", "user__email", "bio"]
    raw_id_fields = ["user"]


@admin.register(Post)
class PostAdmin(MarkdownxModelAdmin):
    """Admin for blog posts with Markdown support"""

    list_display = [
        "title",
        "author",
        "status",
        "category",
        "published_date",
        "created_at",
    ]
    list_filter = ["status", "category", "created_at", "published_date"]
    search_fields = ["title", "content", "author__username"]
    prepopulated_fields = {"slug": ("title",)}
    raw_id_fields = ["author"]
    filter_horizontal = ["tags"]
    date_hierarchy = "published_date"

    fieldsets = [
        (
            "Content",
            {
                "fields": ["title", "slug", "author", "content", "excerpt"],
            },
        ),
        (
            "Media",
            {
                "fields": ["featured_image", "featured_image_alt"],
            },
        ),
        (
            "Classification",
            {
                "fields": ["status", "category", "tags"],
            },
        ),
        (
            "Dates",
            {
                "fields": ["published_date"],
                "classes": ["collapse"],
            },
        ),
    ]

    def save_model(self, request, obj, form, change):  # type: ignore[no-untyped-def]
        """Save the model and set author if creating new post"""
        if not change:  # Creating new post
            if not obj.author_id:
                obj.author = request.user
        super().save_model(request, obj, form, change)
