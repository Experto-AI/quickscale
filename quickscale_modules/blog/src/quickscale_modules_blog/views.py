"""Views for QuickScale blog module."""

import logging
from collections.abc import Callable, Iterator, Mapping
from contextlib import contextmanager
from importlib import import_module
from typing import Any, cast
from urllib.parse import urlparse

from django.conf import settings
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError, connection
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from django.utils.text import slugify
from django.views.generic import DetailView, ListView
from markdownx.utils import markdownify
from PIL import Image, UnidentifiedImageError
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_orgs.public_context import PublicSystemOrgReadMixin
from quickscale_modules_orgs.sanitization import sanitize_rendered_html

from .exceptions import (
    BlogMediaUploadValidationError,
    BlogPublishConflictError,
    BlogPublishError,
    BlogPublishValidationError,
)
from .models import BlogMediaAsset, Category, Post, Tag
from .permissions import IsStaffUser
from .throttles import BlogApiThrottle

storage_build_public_media_url: Callable[..., str] | None = None
storage_validate_file_upload: Callable[..., Any] | None = None
storage_helpers: Any | None
try:
    storage_helpers = import_module("quickscale_modules_storage.helpers")
except ModuleNotFoundError:
    storage_helpers = None

if storage_helpers is not None:
    storage_build_public_media_url = getattr(
        storage_helpers, "build_public_media_url", None
    )
    storage_validate_file_upload = getattr(
        storage_helpers, "validate_file_upload", None
    )


logger = logging.getLogger(__name__)

DEFAULT_BLOG_API_ALLOWED_IMAGE_FORMATS = ("PNG", "JPEG", "WEBP", "GIF")
DEFAULT_BLOG_API_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_BLOG_API_UPLOAD_MAX_WIDTH = 4096
DEFAULT_BLOG_API_UPLOAD_MAX_HEIGHT = 4096
IMAGE_BOMB_VALIDATION_ERROR = "Image exceeds safe pixel limit"

# ---------------------------------------------------------------------------
# Org-resolution helpers for the single-URL contract (T1.6)
# ---------------------------------------------------------------------------


def _resolve_api_org(request: Request | HttpRequest, author: Any) -> Any:
    """Return the organization for staff API write operations.

    Requests authenticated by the session use ``request.org`` from
    middleware.  A request without a middleware org context resolves the
    user's personal org, falling back to the System org.

    .. caution::
       As a side effect this function calls
       ``set_current_org_id(org.pk)`` so that tenant-scoped managers
       and the GUC priming wrapper see the correct org for subsequent
       ORM operations.  Callers **must** capture
       ``get_current_org_id()`` beforehand and restore the Python
       ContextVar with ``set_current_org_id(prior)`` afterward.  When
       PostgreSQL is the database backend **and** the caller is inside
       an active ``transaction.atomic()`` block, callers **must** also
       restore the DB GUC and clear the per-transaction priming memo
       by calling ``_restore_current_org_id(prior)`` **after**
       ``set_current_org_id(prior)`` (Python ContextVar first, then
       DB GUC).
    """
    from quickscale_modules_orgs.current_org import set_current_org_id

    org = getattr(request, "org", None)
    if org is None:
        # No middleware org context — resolve the user's personal org.
        from quickscale_modules_orgs.models import (
            Organization,
            OrganizationMembership,
        )

        membership = OrganizationMembership.objects.filter(
            user=author, organization__is_personal=True
        ).first()
        org = (
            membership.organization
            if membership is not None
            else Organization.objects.get_system_org()
        )

    set_current_org_id(org.pk)
    return org


def _upload_limit_setting(setting_name: str, default: int) -> int:
    """Return an optional image-upload limit or *default*.

    The upload limits are not manifest options yet, so their defaults live in
    code; once the manifest declares them, ``apply`` writes them and this
    helper goes.
    """
    value = getattr(settings, setting_name, default)
    if isinstance(value, bool):
        return default

    try:
        parsed_value = int(value)
    except TypeError:
        return default
    except ValueError:
        return default

    return parsed_value if parsed_value > 0 else default


def _build_media_response_url(
    request: Request | HttpRequest, stored_reference: str
) -> str:
    """Build a public media URL using storage helper when available, with local fallback."""
    public_base_url = str(
        getattr(settings, "QUICKSCALE_STORAGE_PUBLIC_BASE_URL", "")
    ).strip()
    media_url = str(settings.MEDIA_URL).strip()

    if storage_build_public_media_url is not None:
        return storage_build_public_media_url(
            stored_reference,
            request=request,
            public_base_url=public_base_url,
            media_url=media_url,
        )

    reference = (stored_reference or "").strip()
    if not reference:
        return ""

    parsed = urlparse(reference)
    if parsed.scheme and parsed.netloc:
        return reference

    if public_base_url:
        return f"{public_base_url.rstrip('/')}/{reference.lstrip('/')}"

    if reference.startswith("/"):
        return request.build_absolute_uri(reference)

    normalized_media_url = media_url
    if not normalized_media_url.startswith("/") and not normalized_media_url.startswith(
        "http"
    ):
        normalized_media_url = "/" + normalized_media_url
    if not normalized_media_url.endswith("/"):
        normalized_media_url += "/"

    return request.build_absolute_uri(f"{normalized_media_url}{reference.lstrip('/')}")


@contextmanager
def _blog_org_scope(request: Request | HttpRequest, author: Any) -> Iterator[Any]:
    """Resolve the API org for one write and restore the prior org afterwards.

    Resolution stamps ``set_current_org_id(org.pk)`` so tenant-scoped
    managers and the GUC priming wrapper see the correct org for the
    request's ORM operations.  On exit the Python ContextVar is always
    restored; when PostgreSQL is the backend and the caller sits inside an
    active ``transaction.atomic()`` block, the ``app.current_org_id`` GUC
    and the per-transaction priming memo are restored too (Python ContextVar
    first, then DB GUC).
    """
    from quickscale_modules_orgs.current_org import (
        _restore_current_org_id,
        get_current_org_id,
        set_current_org_id,
    )

    prior = get_current_org_id()
    organization = _resolve_api_org(request, author)
    try:
        yield organization
    finally:
        set_current_org_id(prior)
        if connection.vendor == "postgresql" and connection.in_atomic_block:
            _restore_current_org_id(prior)


def _validate_blog_image_upload(uploaded_file: UploadedFile) -> tuple[int, int]:
    """Validate the uploaded image and return its dimensions."""
    max_upload_bytes_setting = getattr(
        settings,
        "BLOG_API_UPLOAD_MAX_BYTES",
        DEFAULT_BLOG_API_UPLOAD_MAX_BYTES,
    )
    max_upload_bytes = int(
        max_upload_bytes_setting or DEFAULT_BLOG_API_UPLOAD_MAX_BYTES
    )
    max_upload_width = _upload_limit_setting(
        "BLOG_API_UPLOAD_MAX_WIDTH",
        DEFAULT_BLOG_API_UPLOAD_MAX_WIDTH,
    )
    max_upload_height = _upload_limit_setting(
        "BLOG_API_UPLOAD_MAX_HEIGHT",
        DEFAULT_BLOG_API_UPLOAD_MAX_HEIGHT,
    )
    allowed_formats = {
        str(image_format).upper()
        for image_format in getattr(
            settings,
            "BLOG_API_ALLOWED_IMAGE_FORMATS",
            DEFAULT_BLOG_API_ALLOWED_IMAGE_FORMATS,
        )
    }

    uploaded_file_size = uploaded_file.size or 0
    if uploaded_file_size > max_upload_bytes:
        raise BlogMediaUploadValidationError(
            {"file": f"File exceeds maximum upload size of {max_upload_bytes} bytes"}
        )

    if storage_validate_file_upload is not None:
        try:
            validated = storage_validate_file_upload(
                uploaded_file,
                max_size_bytes=max_upload_bytes,
                allowed_image_formats=allowed_formats,
                max_width=max_upload_width,
                max_height=max_upload_height,
            )
        except ValueError as exc:
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


def create_published_post_from_payload(
    payload: Mapping[str, Any],
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
    except IntegrityError as exc:
        if Post.all_objects.filter(
            slug=generated_slug, organization=organization
        ).exists():
            raise BlogPublishConflictError(
                "Post already exists for generated slug"
            ) from exc
        raise

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

    return post


class BlogSessionAuthentication(SessionAuthentication):
    """Session authentication that keeps a 401 challenge for anonymous callers.

    DRF answers an unauthenticated request 403 when the authentication scheme
    declares no challenge header; the blog API has always answered 401, so the
    scheme names its challenge.
    """

    def authenticate_header(self, request: Request) -> str:
        del request
        return "Session"


class BlogApiBaseView(APIView):
    """Shared contract for the blog module's DRF automation API views.

    Session authentication only (Module Conventions rule 9): DRF's
    ``SessionAuthentication`` enforces CSRF on unsafe methods.  The staff
    role is the module's platform-level write gate (Module Conventions rule
    19's operator path), and every error goes through the one QuickScale
    exception handler the generated settings install.
    """

    authentication_classes = [BlogSessionAuthentication]
    permission_classes = [IsAuthenticated, IsStaffUser]
    throttle_classes = [BlogApiThrottle]
    throttle_scope = "quickscale_blog_api"
    http_method_names = ["post"]


class MediaUploadAPIView(BlogApiBaseView):
    """Upload a blog image for later use in Markdown or as a featured image.

    The media asset is stamped with the active organization from
    ``request.org``, resolved through :func:`_blog_org_scope`, which also
    restores the prior org context on exit.
    """

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        author = request.user
        try:
            with _blog_org_scope(request, author) as organization:
                asset = create_blog_media_asset_from_request(
                    request, author, organization=organization
                )
        except BlogMediaUploadValidationError as exc:
            raise ValidationError(exc.errors) from exc

        return Response(
            {
                "id": asset.pk,
                "url": _build_media_response_url(request, asset.file.name or ""),
                "alt": asset.alt,
                "kind": asset.kind,
                "width": asset.width,
                "height": asset.height,
            },
            status=201,
        )


class PostPublishAPIView(BlogApiBaseView):
    """Create and publish a blog post from a JSON payload.

    The post is stamped with the active organization from ``request.org``.
    Referenced resources (category, tags, media asset) are validated to
    belong to the same organization.  The prior org context is restored on
    exit through :func:`_blog_org_scope`.
    """

    parser_classes = [JSONParser]

    def post(self, request: Request, *args: Any, **kwargs: Any) -> Response:
        del args, kwargs
        payload = request.data
        if not isinstance(payload, Mapping):
            raise ValidationError("JSON object payload expected")

        author = request.user
        try:
            with _blog_org_scope(request, author) as organization:
                post = create_published_post_from_payload(
                    payload, author, organization=organization
                )
        except BlogPublishValidationError as exc:
            raise ValidationError(exc.errors) from exc
        except IntegrityError as exc:
            logger.exception("Unexpected integrity error while publishing post")
            raise BlogPublishError("Unable to publish post") from exc

        return Response(
            {
                "id": post.pk,
                "slug": post.slug,
                "url": post.get_absolute_url(),
                "status": post.status,
            },
            status=201,
        )


class BlogPublicReadMixin(PublicSystemOrgReadMixin):
    """Mixin for blog public read views that resolves org context.

    Anonymous/public readers see System-org content (D2).
    Authenticated readers see their active org via ``request.org``.

    Wraps ``dispatch()`` in ``org_scope()`` to prime both the Python
    ContextVar and the PostgreSQL GUC ``app.current_org_id``, so that
    tenant-scoped default managers auto-scope queries correctly and
    RLS policies see the correct org context.
    """

    request: HttpRequest

    def get_public_org(self) -> Any | None:  # type: ignore[override]
        """Return the organization for this request.

        Authenticated readers are scoped to their active org via
        ``request.org``.  Anonymous/public readers default to the
        System org singleton.
        """
        user = getattr(self.request, "user", None)
        if user is not None and user.is_authenticated:
            return getattr(self.request, "org", None)
        return super().get_public_org()


class PostListView(BlogPublicReadMixin, ListView):
    """Display paginated list of published blog posts"""

    model = Post
    template_name = "quickscale_blog/blog/post_list.html"
    context_object_name = "posts"

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the project's declared posts-per-page value (rule 3)."""
        del queryset
        return settings.BLOG_POSTS_PER_PAGE

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return only published posts, ordered by publish date"""
        return (
            Post.objects.filter(status="published")
            .select_related("author", "category")
            .prefetch_related("tags")
        )


class PostDetailView(BlogPublicReadMixin, DetailView):
    """Display single blog post"""

    model = Post
    template_name = "quickscale_blog/blog/post_detail.html"
    context_object_name = "post"

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return only published posts"""
        return (
            Post.objects.filter(status="published")
            .select_related("author", "category")
            .prefetch_related("tags")
        )

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add rendered markdown content to context"""
        context = super().get_context_data(**kwargs)
        rendered = markdownify(escape(self.object.content))
        context["rendered_content"] = sanitize_rendered_html(rendered)
        return context


class CategoryListView(BlogPublicReadMixin, ListView):
    """Display posts filtered by category"""

    model = Post
    template_name = "quickscale_blog/blog/category_list.html"
    context_object_name = "posts"

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the project's declared posts-per-page value (rule 3)."""
        del queryset
        return settings.BLOG_POSTS_PER_PAGE

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return published posts in the specified category"""
        self.category = get_object_or_404(
            Category.objects.all(),
            slug=self.kwargs["slug"],
        )
        return (
            Post.objects.filter(status="published", category=self.category)
            .select_related("author", "category")
            .prefetch_related("tags")
        )

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add category to context"""
        context = super().get_context_data(**kwargs)
        context["category"] = self.category
        return context


class TagListView(BlogPublicReadMixin, ListView):
    """Display posts filtered by tag"""

    model = Post
    template_name = "quickscale_blog/blog/tag_list.html"
    context_object_name = "posts"

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the project's declared posts-per-page value (rule 3)."""
        del queryset
        return settings.BLOG_POSTS_PER_PAGE

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return published posts with the specified tag"""
        self.tag = get_object_or_404(
            Tag.objects.all(),
            slug=self.kwargs["slug"],
        )
        return (
            Post.objects.filter(status="published", tags=self.tag)
            .select_related("author", "category")
            .prefetch_related("tags")
        )

    def get_context_data(self, **kwargs):  # type: ignore[no-untyped-def]
        """Add tag to context"""
        context = super().get_context_data(**kwargs)
        context["tag"] = self.tag
        return context
