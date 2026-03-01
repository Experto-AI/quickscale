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

    def formfield_for_foreignkey(self, db_field, request, **kwargs):  # type: ignore[no-untyped-def]
        """Show author as dropdown with blank default and current user option."""
        if db_field.name == "author":
            user_model = get_user_model()
            allowed_author_ids: set[object] = set()
            if request.user.is_authenticated and request.user.pk is not None:
                allowed_author_ids.add(request.user.pk)
            kwargs["required"] = False

            object_id = (
                request.resolver_match.kwargs.get("object_id")
                if request.resolver_match
                else None
            )
            if object_id:
                try:
                    current_post = Post.objects.only("author_id").get(pk=object_id)
                    current_author_id = getattr(current_post, "author_id", None)
                    if current_author_id is not None:
                        allowed_author_ids.add(current_author_id)
                except Post.DoesNotExist, ValueError, TypeError:
                    pass

            kwargs["empty_label"] = "No author"

            kwargs["queryset"] = user_model.objects.filter(
                pk__in=allowed_author_ids
            ).order_by("username")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):  # type: ignore[no-untyped-def]
        """Save the model with explicit author selection from admin form."""
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):  # type: ignore[no-untyped-def]
        form_class = super().get_form(request, obj, change, **kwargs)

        if "author" in form_class.base_fields:
            form_class.base_fields["author"].required = False
        return form_class
