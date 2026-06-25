"""RSS feed for QuickScale blog module

The single RSS feed scopes to System-org content (D2).
"""

from django.contrib.syndication.views import Feed
from django.utils.feedgenerator import Rss201rev2Feed

from .models import Post


class LatestPostsFeed(Feed):
    """RSS feed for latest published blog posts (System org, D2)."""

    feed_type = Rss201rev2Feed
    title = "Latest Blog Posts"
    link = "/blog/"
    description = "Latest posts from our blog"

    def items(self):  # type: ignore[no-untyped-def]
        """Return the 20 most recent published System-org posts."""
        from quickscale_modules_orgs.models import Organization

        return Post.all_objects.filter(
            status="published", organization=Organization.objects.get_system_org()
        ).order_by("-published_date")[:20]

    def item_title(self, item: Post) -> str:
        """Return post title"""
        return item.title

    def item_description(self, item: Post) -> str:
        """Return post excerpt or full content"""
        return item.excerpt if item.excerpt else item.content[:500]

    def item_link(self, item: Post) -> str:
        """Return the flat route URL for this post."""
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
