"""Admin configuration for QuickScale blog module"""

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from markdownx.admin import MarkdownxModelAdmin

from .models import AuthorProfile, BlogMediaAsset, Category, Post, Tag


class PostAdminForm(forms.ModelForm):
    """Admin form for blog posts."""

    class Meta:
        model = Post
        fields = "__all__"

    def __init__(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        self.request = kwargs.pop("request", None)
        super().__init__(*args, **kwargs)
        if "author" in self.fields:
            self.fields["author"].required = False
            if (
                not self.instance.pk
                and self.request
                and self.request.user.is_authenticated
            ):
                self.fields["author"].initial = self.request.user


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


@admin.register(BlogMediaAsset)
class BlogMediaAssetAdmin(admin.ModelAdmin):
    """Admin for uploaded blog media assets."""

    list_display = [
        "original_filename",
        "kind",
        "uploaded_by",
        "width",
        "height",
        "created_at",
    ]
    list_filter = ["kind", "created_at"]
    search_fields = ["original_filename", "alt", "uploaded_by__username"]
    readonly_fields = ["width", "height", "created_at"]


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
            allowed_author_ids = {request.user.pk}

            object_id = (
                request.resolver_match.kwargs.get("object_id")
                if request.resolver_match
                else None
            )
            if object_id:
                try:
                    current_author_id = Post.objects.values_list(
                        "author_id", flat=True
                    ).get(pk=object_id)
                    allowed_author_ids.add(current_author_id)
                except Post.DoesNotExist:
                    pass
                except ValueError:
                    pass
                except TypeError:
                    pass

            kwargs["empty_label"] = "No author"

            kwargs["queryset"] = user_model.objects.filter(
                pk__in=allowed_author_ids
            ).order_by("username")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):  # type: ignore[no-untyped-def]
        """Save the model."""
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, change=False, **kwargs):  # type: ignore[no-untyped-def]
        form_class = super().get_form(request, obj, change, **kwargs)

        class RequestAwareForm(form_class):  # type: ignore[valid-type,misc]
            def __init__(self, *args, **inner_kwargs):  # type: ignore[no-untyped-def]
                inner_kwargs["request"] = request
                super().__init__(*args, **inner_kwargs)

        return RequestAwareForm
