"""RSS feed for QuickScale blog module

Phase 2 (F11.11) adds ``LatestPostsFeedOrgScoped`` for org-scoped routes.
"""

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Rss201rev2Feed

from .models import Post


class LatestPostsFeed(Feed):
    """RSS feed for latest blog posts (flat/solo routes)"""

    feed_type = Rss201rev2Feed
    title = "Latest Blog Posts"
    link = "/blog/"
    description = "Latest posts from our blog"

    def items(self):  # type: ignore[no-untyped-def]
        """Return the 20 most recent published tenant-agnostic posts.

        Only tenant-agnostic posts (``organization=None``) appear in the
        flat feed, keeping flat ``/blog/...`` compatibility.
        """
        return Post.objects.filter(
            status="published", organization__isnull=True
        ).order_by("-published_date")[:20]

    def item_title(self, item: Post) -> str:
        """Return post title"""
        return item.title

    def item_description(self, item: Post) -> str:
        """Return post excerpt or full content"""
        return item.excerpt if item.excerpt else item.content[:500]

    def item_link(self, item: Post) -> str:
        """Return post URL using the model's route-aware helper."""
        return item.get_absolute_url()

    def item_pubdate(self, item):  # type: ignore[no-untyped-def]
        """Return post publication date"""
        return item.published_date

    def item_author_name(self, item: Post) -> str | None:
        """Return post author name"""
        if item.author is None:
            return None
        return item.author.get_full_name() or item.author.username

    def item_categories(self, item: Post) -> list[str]:
        """Return post categories and tags"""
        categories = []
        if item.category:
            categories.append(item.category.name)
        categories.extend([tag.name for tag in item.tags.all()])
        return categories


class LatestPostsFeedOrgScoped(Feed):
    """RSS feed for latest blog posts (org-scoped SaaS routes)

    Filters posts to the organization resolved by middleware.
    """

    feed_type = Rss201rev2Feed
    title = "Latest Blog Posts"
    link = "/blog/"
    description = "Latest posts from our blog"

    def get_object(self, request, *args, **kwargs):  # type: ignore[no-untyped-def]
        """Resolve the active organization from request context."""
        from quickscale_modules_orgs.current_org import (
            get_current_org,
        )

        return get_current_org(request)

    def items(self, obj):  # type: ignore[no-untyped-def]
        """Return the 20 most recent published posts for this org."""
        if obj is None:
            return Post.objects.none()
        return Post.objects.filter(status="published", organization=obj).order_by(
            "-published_date"
        )[:20]

    def item_title(self, item: Post) -> str:
        """Return post title"""
        return item.title

    def item_description(self, item: Post) -> str:
        """Return post excerpt or full content"""
        return item.excerpt if item.excerpt else item.content[:500]

    def item_link(self, item: Post) -> str:
        """Return post URL using the model's route-aware helper."""
        return item.get_absolute_url()

    def item_pubdate(self, item):  # type: ignore[no-untyped-def]
        """Return post publication date"""
        return item.published_date

    def item_author_name(self, item: Post) -> str | None:
        """Return post author name"""
        if item.author is None:
            return None
        return item.author.get_full_name() or item.author.username

    def item_categories(self, item: Post) -> list[str]:
        """Return post categories and tags"""
        categories = []
        if item.category:
            categories.append(item.category.name)
        categories.extend([tag.name for tag in item.tags.all()])
        return categories
