"""URL configuration for blog module tests

Phase 2 (F11.11): the blog URLconf now carries both flat ``/blog/...`` and
org-scoped ``/orgs/<slug>/blog/...`` paths as fully-qualified entries.
It is included at the root level so all paths resolve correctly.

The CRM module follows the same pattern in its own URLconf.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("quickscale_modules_blog.urls")),
]
