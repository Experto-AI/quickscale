"""Tests for blog's public service surface (Module Conventions rules 4, 23)."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest
from django.test import override_settings

from quickscale_modules_blog import services
from quickscale_modules_blog.exceptions import (
    BlogError,
    BlogMediaUploadError,
    BlogMediaUploadValidationError,
    BlogPublishConflictError,
    BlogPublishError,
    BlogPublishValidationError,
)

#: Exactly the names rule 23 makes the module's public service surface.
SERVICE_SURFACE = [
    "BlogError",
    "create_blog_media_asset_from_request",
    "create_published_post_from_payload",
    "is_enabled",
]


def test_services_publishes_exactly_the_declared_surface() -> None:
    """``__all__`` is the module's public surface, and nothing else is public."""
    assert services.__all__ == SERVICE_SURFACE
    for name in SERVICE_SURFACE:
        assert hasattr(services, name), f"{name} is missing from services.py"


def test_services_reexports_the_module_error_base() -> None:
    """Rule 10: ``services.py`` re-exports the one ``BlogError`` base."""
    assert services.BlogError is BlogError


@pytest.mark.parametrize(
    "name",
    [
        "create_blog_media_asset_from_request",
        "create_published_post_from_payload",
    ],
)
def test_publish_services_take_one_subject_then_keyword_only(name: str) -> None:
    """Rule 23: at most one leading subject; every other argument is keyword-only."""
    parameters = list(inspect.signature(getattr(services, name)).parameters.values())

    assert parameters[0].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert all(
        parameter.kind is inspect.Parameter.KEYWORD_ONLY for parameter in parameters[1:]
    )


@pytest.mark.django_db
class TestCreatePublishedPostFromPayload:
    """The publish operation answers through the module's own error classes."""

    def test_creates_a_published_post_scoped_to_the_organization(
        self,
        org,
        author_user,
        blog_org_scope,
    ) -> None:
        with blog_org_scope(org):
            post = services.create_published_post_from_payload(
                {"title": "Hello World", "content": "Body text"},
                author=author_user,
                organization=org,
            )

        assert post.slug == "hello-world"
        assert post.status == "published"
        assert post.author == author_user
        assert post.organization == org

    def test_links_tags_and_category_scoped_to_the_organization(
        self,
        org,
        author_user,
        blog_org_scope,
    ) -> None:
        from quickscale_modules_blog.models import Category

        with blog_org_scope(org):
            category = Category.objects.create(name="News", organization=org)
            post = services.create_published_post_from_payload(
                {
                    "title": "Tagged Post",
                    "content": "Body text",
                    "category_slug": category.slug,
                    "tags": ["Django", "Testing"],
                },
                author=author_user,
                organization=org,
            )
            tag_names = sorted(post.tags.values_list("name", flat=True))

        assert post.category == category
        assert tag_names == [
            "Django",
            "Testing",
        ]

    def test_invalid_payload_raises_the_module_validation_error(
        self,
        org,
        author_user,
    ) -> None:
        with pytest.raises(BlogPublishValidationError) as error:
            services.create_published_post_from_payload(
                {},
                author=author_user,
                organization=org,
            )

        assert error.value.errors == {
            "title": "This field is required",
            "content": "This field is required",
        }

    def test_duplicate_slug_raises_the_module_conflict_error(
        self,
        org,
        author_user,
        blog_org_scope,
    ) -> None:
        with blog_org_scope(org):
            services.create_published_post_from_payload(
                {"title": "Same Title", "content": "Body text"},
                author=author_user,
                organization=org,
            )

            with pytest.raises(BlogPublishConflictError):
                services.create_published_post_from_payload(
                    {"title": "Same Title", "content": "Body text"},
                    author=author_user,
                    organization=org,
                )

    def test_unexpected_integrity_error_raises_the_module_error(
        self,
        org,
        author_user,
        blog_org_scope,
    ) -> None:
        from django.db import IntegrityError as DjangoIntegrityError

        from quickscale_modules_blog.models import Post

        with blog_org_scope(org):
            with patch.object(
                Post.objects,
                "create",
                side_effect=DjangoIntegrityError("unexpected"),
            ):
                with pytest.raises(BlogPublishError):
                    services.create_published_post_from_payload(
                        {"title": "Broken Write", "content": "Body text"},
                        author=author_user,
                        organization=org,
                    )

    def test_conflict_race_inside_a_transaction_raises_the_module_conflict_error(
        self,
        org,
        author_user,
        blog_org_scope,
    ) -> None:
        """A real unique violation inside org_scope stays a BlogError."""
        from quickscale_modules_blog.models import Post

        with blog_org_scope(org):
            Post.objects.create(
                title="Race Winner",
                slug="race-title",
                content="Body text",
                author=author_user,
                organization=org,
            )
            missed = Post.all_objects.none()
            conflict = Post.all_objects.filter(slug="race-title", organization=org)

            with patch.object(
                Post.all_objects,
                "filter",
                side_effect=[missed, conflict],
            ):
                with pytest.raises(BlogPublishConflictError):
                    services.create_published_post_from_payload(
                        {"title": "Race Title", "content": "Body text"},
                        author=author_user,
                        organization=org,
                    )

            # The savepoint rollback left the surrounding transaction usable.
            assert Post.all_objects.filter(organization=org).exists()

    def test_tag_write_failure_rolls_back_the_post_and_raises_the_module_error(
        self,
        org,
        author_user,
        blog_org_scope,
    ) -> None:
        """A failed tag write leaves no partial post and answers with BlogError."""
        from quickscale_modules_blog.models import Post, Tag

        with blog_org_scope(org):
            Tag.objects.create(
                name="Django",
                slug="custom-django",
                organization=org,
            )

            with pytest.raises(BlogPublishError):
                services.create_published_post_from_payload(
                    {
                        "title": "Tagged Post",
                        "content": "Body text",
                        "tags": ["Django"],
                    },
                    author=author_user,
                    organization=org,
                )

            assert not Post.all_objects.filter(organization=org).exists()


@pytest.mark.django_db
class TestCreateBlogMediaAssetFromRequest:
    """The upload entry point validates before it writes."""

    def test_missing_file_raises_the_module_validation_error(
        self,
        org,
        author_user,
    ) -> None:
        request = SimpleNamespace(FILES={}, POST={})

        with pytest.raises(BlogMediaUploadValidationError) as error:
            services.create_blog_media_asset_from_request(
                request,
                author=author_user,
                organization=org,
            )

        assert error.value.errors == {"file": "This field is required"}

    def test_unsupported_kind_raises_the_module_validation_error(
        self,
        org,
        author_user,
    ) -> None:
        request: Any = SimpleNamespace(
            FILES={},
            POST={"kind": "banner"},
        )

        with pytest.raises(BlogMediaUploadValidationError) as error:
            services.create_blog_media_asset_from_request(
                request,
                author=author_user,
                organization=org,
            )

        assert "kind" in error.value.errors

    def test_media_write_failure_raises_the_module_media_error(
        self,
        org,
        author_user,
    ) -> None:
        """A storage/DB write failure reaches callers as a BlogError."""
        from django.core.files.uploadedfile import SimpleUploadedFile

        from quickscale_modules_blog.models import BlogMediaAsset

        request = SimpleNamespace(
            FILES={
                "file": SimpleUploadedFile(
                    "hero.png",
                    b"fake-bytes",
                    content_type="image/png",
                )
            },
            POST={},
        )

        with (
            patch.object(
                services,
                "_validate_blog_image_upload",
                return_value=(10, 10),
            ),
            patch.object(
                BlogMediaAsset.objects,
                "create",
                side_effect=OSError("disk full"),
            ),
        ):
            with pytest.raises(BlogMediaUploadError):
                services.create_blog_media_asset_from_request(
                    request,
                    author=author_user,
                    organization=org,
                )


def test_is_enabled_reads_the_module_enabled_setting() -> None:
    """Rule 1: ``is_enabled()`` reports ``QUICKSCALE_BLOG_ENABLED`` both ways."""
    with override_settings(QUICKSCALE_BLOG_ENABLED=True):
        assert services.is_enabled() is True
    with override_settings(QUICKSCALE_BLOG_ENABLED=False):
        assert services.is_enabled() is False
