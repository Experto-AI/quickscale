"""Admin configuration for QuickScale blog module"""

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from markdownx.admin import MarkdownxModelAdmin

from .models import AuthorProfile, Category, Post, Tag


class PostAdminForm(forms.ModelForm):
    """Admin form for blog posts."""

    class Meta:
        model = Post
        fields = "__all__"

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        if "author" in self.fields:
            self.fields["author"].required = False


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

    form = PostAdminForm

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

    def _get_author_queryset(self):
        """Return the full set of users that can be assigned as authors."""
        user_model = get_user_model()
        return user_model._default_manager.order_by(user_model.USERNAME_FIELD)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):  # type: ignore[no-untyped-def]
        """Show author as an optional dropdown of available users."""
        if db_field.name == "author":
            kwargs["required"] = False
            kwargs["empty_label"] = "No author"
            kwargs["queryset"] = self._get_author_queryset()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):  # type: ignore[no-untyped-def]
        """Save the model with explicit author selection from admin form."""
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):  # type: ignore[no-untyped-def]
        form_class = super().get_form(request, obj, change, **kwargs)

        if "author" in form_class.base_fields:
            form_class.base_fields["author"].required = False
        return form_class
