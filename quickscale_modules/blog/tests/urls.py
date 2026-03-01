"""URL configuration for blog module tests"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("blog/", include("quickscale_modules_blog.urls")),
]
