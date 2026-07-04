"""URL configuration for QuickScale blog module (single flat URL tree).

All blog routes live under ``/blog/...``.  No org-scoped paths
(``/orgs/<slug>/blog/...``) exist — D1/D5.
"""

from django.conf import settings
from django.urls import path

from . import views
from .feeds import LatestPostsFeed

app_name = "quickscale_blog"


def _blog_enable_rss() -> bool:
    """Return whether the blog RSS route should be exposed.

    Must be explicitly configured.  Startup validation in
    ``AppConfig.ready()`` ensures this setting is always present
    (SA17.5) — no fallback default.
    """
    value = settings.BLOG_ENABLE_RSS
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
    path("blog/", views.PostListView.as_view(), name="post_list"),
    path("blog/post/<slug:slug>/", views.PostDetailView.as_view(), name="post_detail"),
    path("blog/api/media/", views.upload_media_api, name="api_upload_media"),
    path("blog/api/publish/", views.publish_post_api, name="api_publish_post"),
    path(
        "blog/category/<slug:slug>/",
        views.CategoryListView.as_view(),
        name="category_list",
    ),
    path("blog/tag/<slug:slug>/", views.TagListView.as_view(), name="tag_list"),
]

if _blog_enable_rss():
    urlpatterns.append(path("blog/feed/", LatestPostsFeed(), name="feed"))
