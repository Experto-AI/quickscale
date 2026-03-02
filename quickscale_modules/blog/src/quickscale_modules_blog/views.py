"""Views for QuickScale blog module."""

import json
import logging
from typing import Any, Mapping

from django.db import IntegrityError
from django.http import HttpRequest, JsonResponse
from django.utils.html import escape
from django.utils.text import slugify
from django.views.generic import DetailView, ListView
from markdownx.utils import markdownify

from .models import Category, Post, Tag


logger = logging.getLogger(__name__)


class BlogPublishValidationError(Exception):
    """Validation error for blog publish API payload"""

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__("Invalid payload")
        self.errors = errors


class BlogPublishConflictError(Exception):
    """Conflict error for blog publish API payload"""


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


def publish_post_api(request: HttpRequest) -> JsonResponse:
    """Create and publish a blog post from JSON payload for authenticated staff users"""
    if request.method != "POST":
        return JsonResponse(
            {"error": "Method not allowed", "allowed_methods": ["POST"]},
            status=405,
        )

    if not request.user.is_authenticated:
        return JsonResponse({"error": "Authentication required"}, status=401)

    if not getattr(request.user, "is_staff", False):
        return JsonResponse({"error": "Staff access required"}, status=403)

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except UnicodeDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid JSON payload"}, status=400)

    if not isinstance(payload, dict):
        return JsonResponse({"error": "JSON object payload expected"}, status=400)

    try:
        post = create_published_post_from_payload(payload, request.user)
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
    paginate_by = 10

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
    paginate_by = 10

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return published posts in the specified category"""
        self.category = Category.objects.get(slug=self.kwargs["slug"])
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
    paginate_by = 10

    def get_queryset(self):  # type: ignore[no-untyped-def]
        """Return published posts with the specified tag"""
        self.tag = Tag.objects.get(slug=self.kwargs["slug"])
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
