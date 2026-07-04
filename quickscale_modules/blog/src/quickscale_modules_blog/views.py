"""Views for QuickScale blog module."""

import json
import logging
import secrets
from time import time
from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Any, TypeVar, cast
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import UploadedFile
from django.db import IntegrityError
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.middleware.csrf import CsrfViewMiddleware
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.generic import DetailView, ListView
from markdownx.utils import markdownify
from PIL import Image, UnidentifiedImageError

from quickscale_modules_orgs.public_context import PublicSystemOrgReadMixin

from .models import BlogMediaAsset, Category, Post, Tag

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
DEFAULT_BLOG_API_RATE_LIMIT = "5/hour"
DEFAULT_BLOG_API_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_BLOG_API_UPLOAD_MAX_WIDTH = 4096
DEFAULT_BLOG_API_UPLOAD_MAX_HEIGHT = 4096
IMAGE_BOMB_VALIDATION_ERROR = "Image exceeds safe pixel limit"
DEFAULT_BLOG_POSTS_PER_PAGE = 10
RATE_LIMIT_VALUE_PARSE_ERRORS = (TypeError, ValueError)
RATE_LIMIT_CACHE_FALLBACK_ERRORS = (AttributeError, NotImplementedError, ValueError)

# ---------------------------------------------------------------------------
# Org-resolution helpers for the single-URL contract (T1.6)
# ---------------------------------------------------------------------------


def _resolve_api_org(request: HttpRequest, author: Any) -> Any:
    """Return the organization for staff API write operations.

    Session-authenticated requests use ``request.org`` from middleware.
    Token-authenticated requests resolve the user's personal org, falling
    back to the System org.
    """
    org = getattr(request, "org", None)
    if org is not None:
        return org
    # Token auth path — resolve user's personal org.
    from quickscale_modules_orgs.models import (
        Organization,
        OrganizationMembership,
    )

    membership = OrganizationMembership.objects.filter(
        user=author, organization__is_personal=True
    ).first()
    if membership is not None:
        return membership.organization
    return Organization.objects.get_system_org()


ViewFunc = TypeVar("ViewFunc", bound=Callable[..., Any])


def _typed_csrf_exempt(view_func: ViewFunc) -> ViewFunc:
    """Preserve view typing when applying Django's `csrf_exempt` decorator."""
    return csrf_exempt(view_func)


def _get_positive_int_setting(setting_name: str, default: int) -> int:
    """Return a positive integer setting value or the provided default."""
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


def _build_media_response_url(request: HttpRequest, stored_reference: str) -> str:
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


class BlogPublishValidationError(Exception):
    """Validation error for blog publish API payload"""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid payload")
        self.errors = errors


class BlogPublishConflictError(Exception):
    """Conflict error for blog publish API payload"""


class BlogMediaUploadValidationError(Exception):
    """Validation error for blog media upload payload."""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid media upload payload")
        self.errors = errors


def _get_blog_api_tokens() -> list[tuple[str, str]]:
    """Return configured token-to-username mappings for machine authentication."""
    configured_tokens = getattr(settings, "BLOG_API_TOKENS", [])
    if not isinstance(configured_tokens, list):
        logger.warning("BLOG_API_TOKENS must be configured as a list")
        return []

    valid_tokens: list[tuple[str, str]] = []
    for entry in configured_tokens:
        if not isinstance(entry, Mapping):
            continue
        raw_token = entry.get("token")
        username = entry.get("username")
        if not isinstance(raw_token, str) or not raw_token.strip():
            continue
        if not isinstance(username, str) or not username.strip():
            continue
        valid_tokens.append((raw_token.strip(), username.strip()))
    return valid_tokens


def _get_authorization_token(request: HttpRequest) -> str | None:
    """Extract a Bearer or Token authorization token from the request."""
    header_value = request.META.get("HTTP_AUTHORIZATION", "").strip()
    if not header_value:
        return None

    parts = header_value.split(None, 1)
    if len(parts) != 2:
        return ""

    scheme, token = parts
    if scheme.lower() not in {"bearer", "token"}:
        return ""

    return token.strip()


def _enforce_csrf(request: HttpRequest) -> HttpResponse | None:
    """Apply Django's CSRF validation for session-authenticated API requests."""
    middleware = CsrfViewMiddleware(lambda req: JsonResponse({"error": "Forbidden"}))
    return middleware.process_view(request, lambda req: JsonResponse({}), (), {})


def _parse_blog_api_rate_limit(rate_value: Any) -> tuple[int, int]:
    """Return the configured request count and window size for blog API throttling."""
    normalized_rate = (
        str(rate_value).strip()
        if isinstance(rate_value, str) and rate_value.strip()
        else DEFAULT_BLOG_API_RATE_LIMIT
    )
    count_text, _, period_text = normalized_rate.partition("/")

    try:
        request_count = int(count_text.strip())
    except RATE_LIMIT_VALUE_PARSE_ERRORS:
        if normalized_rate == DEFAULT_BLOG_API_RATE_LIMIT:
            return 5, 3600
        return _parse_blog_api_rate_limit(DEFAULT_BLOG_API_RATE_LIMIT)

    period = period_text.strip().lower()
    period_seconds_by_name = {
        "s": 1,
        "sec": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hour": 3600,
        "hours": 3600,
        "d": 86400,
        "day": 86400,
        "days": 86400,
    }
    window_seconds = period_seconds_by_name.get(period)

    if request_count <= 0 or window_seconds is None:
        if normalized_rate == DEFAULT_BLOG_API_RATE_LIMIT:
            return 5, 3600
        return _parse_blog_api_rate_limit(DEFAULT_BLOG_API_RATE_LIMIT)

    return request_count, window_seconds


def _get_blog_api_rate_limit_ident(request: HttpRequest) -> str:
    """Return the client identifier used for blog API throttling."""
    remote_addr = request.META.get("REMOTE_ADDR", "")
    if isinstance(remote_addr, str) and remote_addr.strip():
        return remote_addr.strip()

    return "unknown"


def _get_blog_api_rate_limit_cache_key(request: HttpRequest, bucket: int) -> str:
    """Build a stable cache key for the current blog API throttle bucket."""
    ident = _get_blog_api_rate_limit_ident(request)
    safe_ident = ident.replace(":", "_").replace(".", "_") or "unknown"
    return f"throttle_blog_api_{safe_ident}_{bucket}"


def _enforce_blog_api_rate_limit(request: HttpRequest) -> HttpResponse | None:
    """Apply additive per-IP throttling for authenticated blog API requests."""
    allowed_requests, window_seconds = _parse_blog_api_rate_limit(
        getattr(settings, "BLOG_API_RATE_LIMIT", DEFAULT_BLOG_API_RATE_LIMIT)
    )
    current_time = int(time())
    bucket = current_time // window_seconds
    cache_key = _get_blog_api_rate_limit_cache_key(request, bucket)

    try:
        if cache.add(cache_key, 1, timeout=window_seconds):
            request_count = 1
        else:
            request_count = cache.incr(cache_key)
    except RATE_LIMIT_CACHE_FALLBACK_ERRORS:
        cached_value = cache.get(cache_key, 0)
        request_count = cached_value if isinstance(cached_value, int) else 0
        request_count += 1
        cache.set(cache_key, request_count, timeout=window_seconds)

    if request_count <= allowed_requests:
        return None

    response = JsonResponse({"error": "Rate limit exceeded"}, status=429)
    response["Retry-After"] = str(
        max(window_seconds - (current_time % window_seconds), 1)
    )
    return response


def authenticate_blog_api_request(
    request: HttpRequest,
) -> tuple[Any | None, HttpResponse | None]:
    """Authenticate session or token-based blog API access.

    Session-authenticated requests keep Django CSRF protection.
    Token-authenticated requests bypass CSRF and are intended for automation.
    """
    token = _get_authorization_token(request)
    if token is not None:
        if not token:
            return None, JsonResponse(
                {"error": "Invalid Authorization header"},
                status=401,
            )

        user_model = get_user_model()
        for configured_token, username in _get_blog_api_tokens():
            if not secrets.compare_digest(token, configured_token):
                continue

            user = user_model.objects.filter(username=username, is_active=True).first()
            if user is None:
                logger.warning(
                    "BLOG_API_TOKENS references missing user '%s'",
                    username,
                )
                return None, JsonResponse({"error": "Invalid API token"}, status=401)
            if not getattr(user, "is_staff", False):
                return None, JsonResponse(
                    {"error": "Staff access required"},
                    status=403,
                )
            return user, None

        return None, JsonResponse({"error": "Invalid API token"}, status=401)

    if not request.user.is_authenticated:
        return None, JsonResponse({"error": "Authentication required"}, status=401)

    if not getattr(request.user, "is_staff", False):
        return None, JsonResponse({"error": "Staff access required"}, status=403)

    csrf_response = _enforce_csrf(request)
    if csrf_response is not None:
        return None, csrf_response

    return request.user, None


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
    max_upload_width = _get_positive_int_setting(
        "BLOG_API_UPLOAD_MAX_WIDTH",
        DEFAULT_BLOG_API_UPLOAD_MAX_WIDTH,
    )
    max_upload_height = _get_positive_int_setting(
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
    request: HttpRequest,
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


@_typed_csrf_exempt
def upload_media_api(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    """Upload a blog image for later use in Markdown or as a featured image.

    The media asset is stamped with the active organization from
    ``request.org`` (session auth) or the user's personal org (token auth).
    """
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed", "allowed_methods": ["POST"]},
            status=405,
        )

    author, auth_error = authenticate_blog_api_request(request)
    if auth_error is not None:
        return auth_error

    throttle_error = _enforce_blog_api_rate_limit(request)
    if throttle_error is not None:
        return throttle_error

    # Resolve org: session auth uses request.org from middleware;
    # token auth resolves the user's personal org.
    organization = _resolve_api_org(request, author)

    try:
        asset = create_blog_media_asset_from_request(
            request, author, organization=organization
        )
    except BlogMediaUploadValidationError as exc:
        return JsonResponse({"errors": exc.errors}, status=400)

    return JsonResponse(
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


@_typed_csrf_exempt
def publish_post_api(request: HttpRequest, **kwargs: Any) -> HttpResponse:
    """Create and publish a blog post from JSON payload for authenticated staff users.

    The post is stamped with the active organization from ``request.org``
    (session auth) or the user's personal org (token auth). Referenced
    resources (category, tags, media asset) are validated to belong to
    the same organization.
    """
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed", "allowed_methods": ["POST"]},
            status=405,
        )

    author, auth_error = authenticate_blog_api_request(request)
    if auth_error is not None:
        return auth_error

    throttle_error = _enforce_blog_api_rate_limit(request)
    if throttle_error is not None:
        return throttle_error

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON object payload expected"}, status=400)

    # Resolve org: session auth uses request.org from middleware;
    # token auth resolves the user's personal org.
    organization = _resolve_api_org(request, author)

    try:
        post = create_published_post_from_payload(
            payload, author, organization=organization
        )
    except BlogPublishValidationError as exc:
        return JsonResponse({"errors": exc.errors}, status=400)
    except BlogPublishConflictError as exc:
        return JsonResponse({"error": str(exc)}, status=409)
    except IntegrityError:
        logger.exception("Unexpected integrity error while publishing post")
        return JsonResponse(
            {"error": "Unable to publish post"},
            status=500,
        )

    return JsonResponse(
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
    template_name = "quickscale_modules_blog/blog/post_list.html"
    context_object_name = "posts"
    paginate_by = DEFAULT_BLOG_POSTS_PER_PAGE

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the runtime-configured posts-per-page value."""
        del queryset
        return _get_positive_int_setting(
            "BLOG_POSTS_PER_PAGE",
            DEFAULT_BLOG_POSTS_PER_PAGE,
        )

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
    template_name = "quickscale_modules_blog/blog/post_detail.html"
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
        context["rendered_content"] = markdownify(escape(self.object.content))
        return context


class CategoryListView(BlogPublicReadMixin, ListView):
    """Display posts filtered by category"""

    model = Post
    template_name = "quickscale_modules_blog/blog/category_list.html"
    context_object_name = "posts"
    paginate_by = DEFAULT_BLOG_POSTS_PER_PAGE

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the runtime-configured posts-per-page value."""
        del queryset
        return _get_positive_int_setting(
            "BLOG_POSTS_PER_PAGE",
            DEFAULT_BLOG_POSTS_PER_PAGE,
        )

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
    template_name = "quickscale_modules_blog/blog/tag_list.html"
    context_object_name = "posts"
    paginate_by = DEFAULT_BLOG_POSTS_PER_PAGE

    def get_paginate_by(self, queryset):  # type: ignore[no-untyped-def]
        """Return the runtime-configured posts-per-page value."""
        del queryset
        return _get_positive_int_setting(
            "BLOG_POSTS_PER_PAGE",
            DEFAULT_BLOG_POSTS_PER_PAGE,
        )

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
