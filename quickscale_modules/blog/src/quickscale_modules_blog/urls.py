"""URL configuration for QuickScale blog module (single flat URL tree).

The module's mount lives in its manifest's ``url_includes`` entry
(``blog/``); this URLconf holds no prefix (Module Conventions rule 7).
"""

from django.conf import settings
from django.urls import path

from . import views
from .feeds import LatestPostsFeed

app_name = "quickscale_blog"


def _blog_rss_enabled() -> bool:
    """Return whether the blog RSS route should be exposed.

    Must be explicitly configured.  Startup validation in
    ``AppConfig.ready()`` ensures this setting is always present
    (SA17.5) — no fallback default.
    """
    value = settings.QUICKSCALE_BLOG_RSS_ENABLED
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
    path("api/media/", views.MediaUploadAPIView.as_view(), name="api_upload_media"),
    path("api/publish/", views.PostPublishAPIView.as_view(), name="api_publish_post"),
    path(
        "category/<slug:slug>/",
        views.CategoryListView.as_view(),
        name="category_list",
    ),
    path("tag/<slug:slug>/", views.TagListView.as_view(), name="tag_list"),
]

if _blog_rss_enabled():
    urlpatterns.append(path("feed/", LatestPostsFeed(), name="feed"))
