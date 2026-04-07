"""Views for QuickScale blog module."""

import json
import logging
import secrets
from collections.abc import Callable, Mapping
from importlib import import_module
from typing import Any, TypeVar, cast
from urllib.parse import urlparse

from django.conf import settings
from django.contrib.auth import get_user_model
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
DEFAULT_BLOG_API_UPLOAD_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_BLOG_POSTS_PER_PAGE = 10

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
    except TypeError, ValueError:
        return default

    return parsed_value if parsed_value > 0 else default


def _build_media_response_url(request: HttpRequest, stored_reference: str) -> str:
    """Build a public media URL using storage helper when available, with local fallback."""
    public_base_url = str(
        getattr(settings, "QUICKSCALE_STORAGE_PUBLIC_BASE_URL", "")
    ).strip()
    media_url = str(getattr(settings, "MEDIA_URL", "/media/")).strip() or "/media/"

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
            )
        except ValueError as exc:
            raise BlogMediaUploadValidationError({"file": str(exc)}) from None
        return validated.width, validated.height

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.load()
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

    return image.width, image.height


def create_blog_media_asset_from_request(
    request: HttpRequest,
    author: Any,
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
    )


def create_published_post_from_payload(payload: Mapping[str, Any], author: Any) -> Post:
    """Create and return a published blog post from validated API payload"""
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
            featured_media_asset = BlogMediaAsset.objects.filter(
                pk=featured_image_id
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
            category = Category.objects.filter(slug=category_slug.strip()).first()
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

    if Post.objects.filter(slug=generated_slug).exists():
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
        )
    except IntegrityError as exc:
        if Post.objects.filter(slug=generated_slug).exists():
            raise BlogPublishConflictError(
                "Post already exists for generated slug"
            ) from exc
        raise

    if tag_names:
        tag_objects: list[Tag] = []
        for tag_name in tag_names:
            tag_slug = slugify(tag_name)
            tag_obj, _ = Tag.objects.get_or_create(
                slug=tag_slug,
                defaults={"name": tag_name},
            )
            tag_objects.append(tag_obj)
        post.tags.add(*tag_objects)

    return post


@_typed_csrf_exempt
def upload_media_api(request: HttpRequest) -> JsonResponse:
    """Upload a blog image for later use in Markdown or as a featured image."""
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed", "allowed_methods": ["POST"]},
            status=405,
        )

    author, auth_error = authenticate_blog_api_request(request)
    if auth_error is not None:
        return auth_error  # type: ignore[return-value]

    try:
        asset = create_blog_media_asset_from_request(request, author)
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
def publish_post_api(request: HttpRequest) -> JsonResponse:
    """Create and publish a blog post from JSON payload for authenticated staff users"""
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed", "allowed_methods": ["POST"]},
            status=405,
        )

    author, auth_error = authenticate_blog_api_request(request)
    if auth_error is not None:
        return auth_error  # type: ignore[return-value]

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON object payload expected"}, status=400)

    try:
        post = create_published_post_from_payload(payload, author)
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


class PostListView(ListView):
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


class PostDetailView(DetailView):
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


class CategoryListView(ListView):
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
        self.category = get_object_or_404(Category, slug=self.kwargs["slug"])
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


class TagListView(ListView):
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
        self.tag = get_object_or_404(Tag, slug=self.kwargs["slug"])
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
