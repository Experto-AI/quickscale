"""URL configuration for blog module tests"""

from django.urls import include, path

urlpatterns = [
    path("blog/", include("quickscale_modules_blog.urls")),
]
