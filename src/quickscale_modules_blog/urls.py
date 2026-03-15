"""URL configuration for QuickScale blog module"""

from django.urls import path

from . import views
from .feeds import LatestPostsFeed

app_name = "quickscale_blog"

urlpatterns = [
    path("", views.PostListView.as_view(), name="post_list"),
    path("post/<slug:slug>/", views.PostDetailView.as_view(), name="post_detail"),
    path("api/media/", views.upload_media_api, name="api_upload_media"),
    path("api/publish/", views.publish_post_api, name="api_publish_post"),
    path(
        "category/<slug:slug>/", views.CategoryListView.as_view(), name="category_list"
    ),
    path("tag/<slug:slug>/", views.TagListView.as_view(), name="tag_list"),
    path("feed/", LatestPostsFeed(), name="feed"),
]
