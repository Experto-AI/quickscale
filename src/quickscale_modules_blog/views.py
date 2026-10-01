"""Views for QuickScale blog module."""

import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Any
from urllib.parse import urlparse

from django.conf import settings
from django.db import IntegrityError, connection
from django.http import HttpRequest
from django.shortcuts import get_object_or_404
from django.utils.html import escape
from django.views.generic import DetailView, ListView
from markdownx.utils import markdownify
from rest_framework.authentication import SessionAuthentication
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from quickscale_modules_orgs.public_context import PublicSystemOrgReadMixin
from quickscale_modules_orgs.sanitization import sanitize_rendered_html

from . import _storage
from .exceptions import (
    BlogMediaUploadValidationError,
    BlogPublishError,
    BlogPublishValidationError,
)
from .models import Category, Post, Tag
from .permissions import IsStaffUser
from .services import (
    create_blog_media_asset_from_request,
    create_published_post_from_payload,
)
from .throttles import BlogApiThrottle


logger = logging.getLogger(__name__)

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


def _build_media_response_url(
    request: Request | HttpRequest, stored_reference: str
) -> str:
    """Build a public media URL through storage's services, with a local fallback.

    Storage's service resolves storage's own settings (rules 3, 4, and 34);
    without storage installed, the fallback uses only the project's
    ``MEDIA_URL`` and reads no storage setting.
    """
    services = _storage.storage_services()
    if services is not None:
        return services.build_public_media_url(stored_reference, request=request)

    reference = (stored_reference or "").strip()
    if not reference:
        return ""

    parsed = urlparse(reference)
    if parsed.scheme and parsed.netloc:
        return reference

    if reference.startswith("/"):
        return request.build_absolute_uri(reference)

    normalized_media_url = str(settings.MEDIA_URL).strip()
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
                    request, author=author, organization=organization
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
                    payload, author=author, organization=organization
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
        return settings.QUICKSCALE_BLOG_POSTS_PER_PAGE

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
        return settings.QUICKSCALE_BLOG_POSTS_PER_PAGE

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
        return settings.QUICKSCALE_BLOG_POSTS_PER_PAGE

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
