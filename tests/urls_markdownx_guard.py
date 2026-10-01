"""Root URLconf for the listings Markdownx guard HTTP tests."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("markdownx/", include("quickscale_modules_listings.markdownx_urls")),
]
