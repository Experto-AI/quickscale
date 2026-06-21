"""URL configuration for QuickScale blog module

Phase 2 (F11.11) adds additive org-scoped routes under ``/orgs/<slug>/blog/``
alongside the existing flat ``/blog/`` paths.

Following the CRM module pattern: both flat and org-scoped paths live in
``urlpatterns`` as fully-qualified path strings.  This module should be
included at the root level (``path("", include(...))``).  Views detect the
route type via ``_is_org_scoped_route()`` and scope queries accordingly.
"""

from django.conf import settings
from django.urls import path

from . import views
from .feeds import LatestPostsFeed, LatestPostsFeedOrgScoped

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


# Flat (solo) paths — unchanged contract
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

# ---------------------------------------------------------------------------
# Org-scoped (SaaS) paths — additive, same view classes route-aware
# ---------------------------------------------------------------------------

urlpatterns += [
    path(
        "orgs/<slug:org_slug>/blog/",
        views.PostListView.as_view(),
        name="org-post_list",
    ),
    path(
        "orgs/<slug:org_slug>/blog/post/<slug:slug>/",
        views.PostDetailView.as_view(),
        name="org-post_detail",
    ),
    path(
        "orgs/<slug:org_slug>/blog/api/media/",
        views.upload_media_api,
        name="org-api_upload_media",
    ),
    path(
        "orgs/<slug:org_slug>/blog/api/publish/",
        views.publish_post_api,
        name="org-api_publish_post",
    ),
    path(
        "orgs/<slug:org_slug>/blog/category/<slug:slug>/",
        views.CategoryListView.as_view(),
        name="org-category_list",
    ),
    path(
        "orgs/<slug:org_slug>/blog/tag/<slug:slug>/",
        views.TagListView.as_view(),
        name="org-tag_list",
    ),
]

if _blog_enable_rss():
    urlpatterns.append(
        path(
            "orgs/<slug:org_slug>/blog/feed/",
            LatestPostsFeedOrgScoped(),
            name="org-feed",
        )
    )
