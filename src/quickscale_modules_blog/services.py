"""Public service surface for the QuickScale blog module.

Module Conventions rule 4: another module uses blog only through this file,
and rule 23: exactly ``__all__`` below is the module's public service
surface, public functions take keyword-only parameters after at most one
leading subject, and a service that cannot do what it was asked raises
:class:`BlogError` (rule 10).

The request-shaped upload entry point stays public here because the module's
automation API is the operation's contract; it parses only the request's
``file``/``alt``/``kind`` fields and delegates validation to blog's own
settings and storage's public services.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping
from typing import Any, cast

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import DatabaseError, transaction
from django.http import HttpRequest
from django.utils.text import slugify
from PIL import Image, UnidentifiedImageError
from rest_framework.request import Request

from . import _storage
from .exceptions import (
    BlogError,
    BlogMediaUploadError,
    BlogMediaUploadValidationError,
    BlogPublishConflictError,
    BlogPublishError,
    BlogPublishValidationError,
)
from .models import BlogMediaAsset, Category, Post, Tag


def is_enabled() -> bool:
    """Return whether the module is enabled by ``QUICKSCALE_BLOG_ENABLED``.

    Rule 4: the question a caller asks before using an optional module;
    rule 3: the declared setting is read directly, with no default.
    """
    return bool(settings.QUICKSCALE_BLOG_ENABLED)


__all__ = [
    "BlogError",
    "create_blog_media_asset_from_request",
    "create_published_post_from_payload",
    "is_enabled",
]

IMAGE_BOMB_VALIDATION_ERROR = "Image exceeds safe pixel limit"

logger = logging.getLogger(__name__)


def _validate_blog_image_upload(uploaded_file: UploadedFile) -> tuple[int, int]:
    """Validate the uploaded image and return its dimensions."""
    max_upload_bytes = int(settings.QUICKSCALE_BLOG_API_UPLOAD_MAX_BYTES)
    max_upload_width = int(settings.QUICKSCALE_BLOG_API_UPLOAD_MAX_WIDTH)
    max_upload_height = int(settings.QUICKSCALE_BLOG_API_UPLOAD_MAX_HEIGHT)
    allowed_formats = {
        str(image_format).upper()
        for image_format in settings.QUICKSCALE_BLOG_API_ALLOWED_IMAGE_FORMATS
    }

    uploaded_file_size = uploaded_file.size or 0
    if uploaded_file_size > max_upload_bytes:
        raise BlogMediaUploadValidationError(
            {"file": f"File exceeds maximum upload size of {max_upload_bytes} bytes"}
        )

    services = _storage.storage_services()
    if services is not None:
        try:
            validated = services.validate_file_upload(
                uploaded_file,
                max_size_bytes=max_upload_bytes,
                allowed_image_formats=allowed_formats,
                max_width=max_upload_width,
                max_height=max_upload_height,
            )
        except services.StorageError as exc:
            raise BlogMediaUploadValidationError({"file": str(exc)}) from None
        return validated.width, validated.height

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()
    except Image.DecompressionBombError as exc:
        raise BlogMediaUploadValidationError(
            {"file": IMAGE_BOMB_VALIDATION_ERROR}
        ) from exc
    except (UnidentifiedImageError, OSError) as exc:
        raise BlogMediaUploadValidationError(
            {"file": "Unsupported or invalid image file"}
        ) from exc
    finally:
        uploaded_file.seek(0)

    image_format = (image.format or "").upper()
    if image_format not in allowed_formats:
        allowed_list = ", ".join(sorted(allowed_formats))
        raise BlogMediaUploadValidationError(
            {"file": f"Unsupported image format. Allowed formats: {allowed_list}"}
        )

    width = int(image.width)
    height = int(image.height)

    if width > max_upload_width:
        raise BlogMediaUploadValidationError(
            {"file": f"Image width exceeds maximum of {max_upload_width} pixels"}
        )

    if height > max_upload_height:
        raise BlogMediaUploadValidationError(
            {"file": f"Image height exceeds maximum of {max_upload_height} pixels"}
        )

    return width, height


def create_blog_media_asset_from_request(
    request: Request | HttpRequest,
    *,
    author: Any,
    organization: Any,
) -> BlogMediaAsset:
    """Create and return a stored media asset from a multipart upload request."""
    errors: dict[str, str] = {}

    uploaded_file = request.FILES.get("file")
    if not isinstance(uploaded_file, UploadedFile):
        errors["file"] = "This field is required"

    alt = request.POST.get("alt", "")
    if len(alt.strip()) > 200:
        errors["alt"] = "Must be 200 characters or fewer"

    kind = request.POST.get("kind", BlogMediaAsset.Kind.INLINE)
    if not kind.strip():
        errors["kind"] = "Must be a non-empty string"
    elif kind.strip() not in BlogMediaAsset.Kind.values:
        errors["kind"] = "Must be one of: " + ", ".join(BlogMediaAsset.Kind.values)

    if errors:
        raise BlogMediaUploadValidationError(errors)

    validated_upload = cast(UploadedFile, uploaded_file)
    width, height = _validate_blog_image_upload(validated_upload)

    try:
        with transaction.atomic():
            return BlogMediaAsset.objects.create(
                file=validated_upload,
                alt=alt.strip(),
                kind=kind.strip(),
                original_filename=validated_upload.name,
                width=width,
                height=height,
                uploaded_by=author,
                organization=organization,
            )
    except (OSError, DatabaseError) as exc:
        logger.exception("Unexpected error while storing a blog media asset")
        raise BlogMediaUploadError("Unable to store media asset") from exc


def create_published_post_from_payload(
    payload: Mapping[str, Any],
    *,
    author: Any,
    organization: Any,
) -> Post:
    """Create and return a published blog post from validated API payload.

    The post and all referenced resources (category, tags, media asset)
    are scoped to *organization*.
    """
    errors: dict[str, str] = {}

    title = payload.get("title")
    if not isinstance(title, str) or not title.strip():
        errors["title"] = "This field is required"
    elif not slugify(title.strip()):
        errors["title"] = "Must include at least one letter or number"

    content = payload.get("content")
    if not isinstance(content, str) or not content.strip():
        errors["content"] = "This field is required"

    excerpt = payload.get("excerpt")
    if excerpt is not None and not isinstance(excerpt, str):
        errors["excerpt"] = "Must be a string"

    featured_image_alt = payload.get("featured_image_alt")
    if featured_image_alt is not None and not isinstance(featured_image_alt, str):
        errors["featured_image_alt"] = "Must be a string"

    featured_media_asset = None
    featured_image_id = payload.get("featured_image_id")
    if featured_image_id is not None:
        if isinstance(featured_image_id, str) and featured_image_id.strip().isdigit():
            featured_image_id = int(featured_image_id.strip())

        if not isinstance(featured_image_id, int):
            errors["featured_image_id"] = "Must be an integer"
        else:
            featured_media_asset = BlogMediaAsset.all_objects.filter(
                pk=featured_image_id, organization=organization
            ).first()
            if featured_media_asset is None:
                errors["featured_image_id"] = "Media asset not found"
    elif featured_image_alt is not None and str(featured_image_alt).strip():
        errors["featured_image_alt"] = "featured_image_alt requires featured_image_id"

    category = None
    category_slug = payload.get("category_slug")
    if category_slug is not None:
        if not isinstance(category_slug, str) or not category_slug.strip():
            errors["category_slug"] = "Must be a non-empty string"
        else:
            category = Category.all_objects.filter(
                slug=category_slug.strip(), organization=organization
            ).first()
            if category is None:
                errors["category_slug"] = "Category not found"

    tag_names: list[str] = []
    tags = payload.get("tags")
    if tags is not None:
        if not isinstance(tags, list):
            errors["tags"] = "Must be a list of strings"
        else:
            for tag in tags:
                if not isinstance(tag, str) or not tag.strip():
                    errors["tags"] = "Must be a list of non-empty strings"
                    break
                if not slugify(tag.strip()):
                    errors["tags"] = (
                        "Each tag must include at least one letter or number"
                    )
                    break
                tag_names.append(tag.strip())

    if errors:
        raise BlogPublishValidationError(errors)

    title_text = str(title).strip()
    content_text = str(content).strip()
    generated_slug = slugify(title_text)

    if Post.all_objects.filter(slug=generated_slug, organization=organization).exists():
        raise BlogPublishConflictError("Post already exists for generated slug")

    try:
        with transaction.atomic():
            post = Post.objects.create(
                title=title_text,
                slug=generated_slug,
                content=content_text,
                excerpt=excerpt.strip() if isinstance(excerpt, str) else "",
                featured_image=(
                    featured_media_asset.file.name if featured_media_asset else None
                ),
                featured_image_alt=(
                    featured_image_alt.strip()
                    if isinstance(featured_image_alt, str)
                    else (featured_media_asset.alt if featured_media_asset else "")
                ),
                status="published",
                author=author,
                category=category,
                organization=organization,
            )

            if tag_names:
                tag_objects: list[Tag] = []
                for tag_name in tag_names:
                    tag_slug = slugify(tag_name)
                    tag_obj, _ = Tag.all_objects.filter(
                        organization=organization
                    ).get_or_create(
                        slug=tag_slug,
                        defaults={"name": tag_name, "organization": organization},
                    )
                    tag_objects.append(tag_obj)
                post.tags.add(*tag_objects)
    except DatabaseError as exc:
        # The write ran in its own savepoint, so the conflict lookup below runs
        # on a usable transaction even when the caller is inside atomic().
        if Post.all_objects.filter(
            slug=generated_slug, organization=organization
        ).exists():
            raise BlogPublishConflictError(
                "Post already exists for generated slug"
            ) from exc
        logger.exception("Unexpected database error while publishing post")
        raise BlogPublishError("Unable to publish post") from exc

    return post
