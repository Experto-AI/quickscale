"""URL configuration for QuickScale blog module"""

from django.conf import settings
from django.urls import path

from . import views
from .feeds import LatestPostsFeed

app_name = "quickscale_blog"


def _blog_enable_rss() -> bool:
    """Return whether the blog RSS route should be exposed."""
    value = getattr(settings, "BLOG_ENABLE_RSS", True)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"0", "false", "no", "off"}:
            return False
        if normalized in {"1", "true", "yes", "on"}:
            return True
    return bool(value)


urlpatterns = [
    path("", views.PostListView.as_view(), name="post_list"),
    path("post/<slug:slug>/", views.PostDetailView.as_view(), name="post_detail"),
    path("api/media/", views.upload_media_api, name="api_upload_media"),
    path("api/publish/", views.publish_post_api, name="api_publish_post"),
    path(
        "category/<slug:slug>/", views.CategoryListView.as_view(), name="category_list"
    ),
    path("tag/<slug:slug>/", views.TagListView.as_view(), name="tag_list"),
]

if _blog_enable_rss():
    urlpatterns.append(path("feed/", LatestPostsFeed(), name="feed"))
