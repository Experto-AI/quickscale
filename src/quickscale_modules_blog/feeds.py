"""RSS feed for QuickScale blog module"""

from django.contrib.syndication.views import Feed
from django.urls import reverse
from django.utils.feedgenerator import Rss201rev2Feed

from .models import Post


class LatestPostsFeed(Feed):
    """RSS feed for latest blog posts"""

    feed_type = Rss201rev2Feed
    title = "Latest Blog Posts"
    link = "/blog/"
    description = "Latest posts from our blog"

    def items(self):  # type: ignore[no-untyped-def]
        """Return the 20 most recent published posts"""
        return Post.objects.filter(status="published").order_by("-published_date")[:20]

    def item_title(self, item: Post) -> str:
        """Return post title"""
        return item.title

    def item_description(self, item: Post) -> str:
        """Return post excerpt or full content"""
        return item.excerpt if item.excerpt else item.content[:500]

    def item_link(self, item: Post) -> str:
        """Return post URL"""
        return reverse("quickscale_blog:post_detail", args=[item.slug])

    def item_pubdate(self, item: Post):  # type: ignore[no-untyped-def]
        """Return post publication date"""
        return item.published_date

    def item_author_name(self, item: Post) -> str:
        """Return post author name"""
        return item.author.get_full_name() or item.author.username

    def item_categories(self, item: Post) -> list[str]:
        """Return post categories and tags"""
        categories = []
        if item.category:
            categories.append(item.category.name)
        categories.extend([tag.name for tag in item.tags.all()])
        return categories
