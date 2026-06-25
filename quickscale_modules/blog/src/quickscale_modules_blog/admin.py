"""Admin configuration for QuickScale blog module"""

from typing import Any

from django import forms
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.forms import ModelForm
from markdownx.admin import MarkdownxModelAdmin

from .models import AuthorProfile, BlogMediaAsset, Category, Post, Tag


# ---------------------------------------------------------------------------
# Blog-local same-org validation utility  (mirrors CRM's pattern without
# introducing a cross-module dependency)
# ---------------------------------------------------------------------------


def _make_same_org_validated_form(
    base_form_class: type[ModelForm],
    org_related_fields: list[str],
) -> type[ModelForm]:
    """Return a form subclass that validates same-org membership for related fields.

    The returned form's ``clean()`` checks that all FK and M2M values in
    ``org_related_fields`` belong to the same organization as the row's
    ``organization`` field (add forms) or the instance's current
    ``organization_id`` (change forms).  NULL-org related values are
    accepted for legacy compatibility.
    """

    class SameOrgValidatedForm(base_form_class):  # type: ignore[misc, valid-type]
        def clean(self) -> dict[str, Any]:
            cleaned_data = super().clean()

            # Determine org_id from cleaned_data (add) or instance (change).
            org = cleaned_data.get("organization")
            if org is not None:
                org_id = org.pk if hasattr(org, "pk") else org
            elif (
                self.instance is not None
                and self.instance.pk is not None
                and hasattr(self.instance, "organization_id")
            ):
                org_id = self.instance.organization_id
            else:
                org_id = None

            if org_id is not None:
                for field_name in org_related_fields:
                    values = cleaned_data.get(field_name)
                    if not values:
                        continue
                    # FK fields return a single model instance; M2M fields
                    # return a list/QuerySet of instances.
                    if hasattr(values, "_meta"):
                        # Single FK value.
                        related_org_id = getattr(values, "organization_id", None)
                        if related_org_id is not None and related_org_id != org_id:
                            raise ValidationError(
                                {
                                    field_name: (
                                        f"{field_name} must belong to the "
                                        "same organization."
                                    )
                                }
                            )
                    else:
                        # M2M iterable of values.
                        for val in values:
                            related_org_id = getattr(val, "organization_id", None)
                            if related_org_id is not None and related_org_id != org_id:
                                raise ValidationError(
                                    {
                                        field_name: (
                                            f"All {field_name} must belong "
                                            "to the same organization."
                                        )
                                    }
                                )

            return cleaned_data  # type: ignore[no-any-return]

    SameOrgValidatedForm.__name__ = f"{base_form_class.__name__}SameOrgValidated"
    return SameOrgValidatedForm


class _BlogOrgAwareAdminMixin:
    """Mixin that adds org-aware safeguards for blog admin operator paths.

    Phase F11.13b contract:
    - **Add forms**: ``organization`` is required so the operator must choose
      one when creating a new row.
    - **Change forms**: ``organization`` is read-only so the operator can
      see which org owns the row but cannot reassign it.
    - **Cross-org related validation**: the admin form rejects related
      selections (category, tags) whose organization differs from the
      row's organization.
    """

    # Subclasses list FK/M2M field names that carry an ``organization_id``
    # and must be validated for same-org membership.
    _org_related_fields: list[str] = []

    def get_form(
        self,
        request: Any,
        obj: Any | None = None,
        change: bool | None = None,
        **kwargs: Any,
    ) -> type[ModelForm]:
        is_change = change if change is not None else obj is not None
        form_class = super().get_form(request, obj, change=change, **kwargs)  # type: ignore[misc]

        # Wrap in a same-org validated form when there are related fields.
        if self._org_related_fields:
            form_class = _make_same_org_validated_form(
                form_class, list(self._org_related_fields)
            )

        if not is_change:
            # Add form: ensure organization is present and required.
            if "organization" in form_class.base_fields:
                form_class.base_fields["organization"].required = True

        return form_class  # type: ignore[no-any-return]

    def get_readonly_fields(self, request: Any, obj: Any | None = None) -> list[str]:
        """Show organization read-only on change forms."""
        readonly = list(super().get_readonly_fields(request, obj))  # type: ignore[misc]
        if obj is not None and "organization" not in readonly:
            readonly.append("organization")
        return readonly

    def get_exclude(self, request: Any, obj: Any | None = None) -> list[str] | None:
        """Include organization in the form on both add and change."""
        excludes = list(super().get_exclude(request, obj) or [])  # type: ignore[misc]
        excludes = [f for f in excludes if f != "organization"]
        return excludes or None

    def get_fieldsets(self, request: Any, obj: Any | None = None) -> list[Any]:
        """Ensure organization appears in the fieldsets."""
        fieldsets = super().get_fieldsets(request, obj)  # type: ignore[misc]
        all_fields: list[str] = []
        for _, options in fieldsets:
            all_fields.extend(options.get("fields", ()))
        if "organization" not in all_fields:
            first_name, first_opts = fieldsets[0]
            first_opts = dict(first_opts)
            first_opts["fields"] = ("organization",) + tuple(
                first_opts.get("fields", ())
            )
            fieldsets = [(first_name, first_opts)] + list(fieldsets[1:])
        return fieldsets  # type: ignore[no-any-return]

    def save_model(self, request: Any, obj: Any, form: Any, change: bool) -> None:
        """Validate cross-org FK selections before saving.

        M2M fields (tags) require a PK and are handled in ``save_related``.
        """
        org_id = getattr(obj, "organization_id", None)
        if org_id is not None:
            opts = obj._meta
            m2m_field_names = {f.name for f in opts.many_to_many}
            for field_name in self._org_related_fields:
                if field_name in m2m_field_names:
                    continue
                value = getattr(obj, field_name, None)
                if value is None:
                    continue
                if hasattr(value, "organization_id"):
                    related_org_id = value.organization_id
                    if related_org_id is not None and related_org_id != org_id:
                        raise ValidationError(
                            f"{field_name} must belong to the same organization."
                        )
        super().save_model(request, obj, form, change)  # type: ignore[misc]

    def save_related(
        self,
        request: Any,
        form: ModelForm,
        formsets: list[Any],
        change: bool,
    ) -> None:
        """Save related objects.

        M2M same-org validation is handled in the form-level ``clean()``
        hook before any save occurs.
        """
        super().save_related(request, form, formsets, change)  # type: ignore[misc]


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
class CategoryAdmin(_BlogOrgAwareAdminMixin, admin.ModelAdmin):
    """Admin for blog categories"""

    list_display = ["name", "slug", "organization"]
    list_filter = ["organization"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name", "description"]

    def get_queryset(self, request: Any) -> models.QuerySet:
        """Operator path: use all_objects for cross-tenant visibility."""
        return Category.all_objects.all()


@admin.register(Tag)
class TagAdmin(_BlogOrgAwareAdminMixin, admin.ModelAdmin):
    """Admin for blog tags"""

    list_display = ["name", "slug", "organization"]
    list_filter = ["organization"]
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ["name"]

    def get_queryset(self, request: Any) -> models.QuerySet:
        """Operator path: use all_objects for cross-tenant visibility."""
        return Tag.all_objects.all()


@admin.register(AuthorProfile)
class AuthorProfileAdmin(admin.ModelAdmin):
    """Admin for author profiles"""

    list_display = ["user", "bio"]
    search_fields = ["user__username", "user__email", "bio"]
    raw_id_fields = ["user"]


@admin.register(BlogMediaAsset)
class BlogMediaAssetAdmin(_BlogOrgAwareAdminMixin, admin.ModelAdmin):
    """Admin for uploaded blog media assets."""

    list_display = [
        "original_filename",
        "kind",
        "organization",
        "uploaded_by",
        "width",
        "height",
        "created_at",
    ]
    list_filter = ["organization", "kind", "created_at"]
    search_fields = ["original_filename", "alt", "uploaded_by__username"]
    readonly_fields = ["width", "height", "created_at"]

    def get_queryset(self, request: Any) -> models.QuerySet:
        """Operator path: use all_objects for cross-tenant visibility."""
        return BlogMediaAsset.all_objects.all()


@admin.register(Post)
class PostAdmin(_BlogOrgAwareAdminMixin, MarkdownxModelAdmin):
    """Admin for blog posts with Markdown support"""

    form = PostAdminForm
    _org_related_fields = ["category", "tags"]

    list_display = [
        "title",
        "author",
        "status",
        "category",
        "organization",
        "published_date",
        "created_at",
    ]
    list_filter = ["organization", "status", "category", "created_at", "published_date"]
    search_fields = ["title", "content", "author__username"]
    prepopulated_fields = {"slug": ("title",)}
    filter_horizontal = ["tags"]
    date_hierarchy = "published_date"

    fieldsets = [
        (
            "Content",
            {
                "fields": [
                    "title",
                    "slug",
                    "author",
                    "organization",
                    "content",
                    "excerpt",
                ],
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

    def get_queryset(self, request: Any) -> models.QuerySet:
        """Operator path: use all_objects for cross-tenant visibility."""
        return Post.all_objects.all()

    def formfield_for_foreignkey(self, db_field, request, **kwargs):  # type: ignore[no-untyped-def]
        """Show author as dropdown with blank default and current user option.

        Uses ``all_objects`` for the category FK to bypass TenantManager
        auto-scoping in the admin (operator path).
        """
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
                    current_author_id = Post.all_objects.values_list(
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
        if db_field.name == "category":
            kwargs["queryset"] = Category.all_objects.all()
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def formfield_for_manytomany(self, db_field, request, **kwargs):  # type: ignore[no-untyped-def]
        """Use ``all_objects`` for the tags M2M to bypass TenantManager auto-scoping."""
        if db_field.name == "tags":
            kwargs["queryset"] = Tag.all_objects.all()
        return super().formfield_for_manytomany(db_field, request, **kwargs)

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
