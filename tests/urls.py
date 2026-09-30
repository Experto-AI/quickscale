"""URL configuration for blog module tests.

The module's mount lives in its manifest's ``url_includes`` entry; the test
project mounts the module at the same ``blog/`` path, so every ``/blog/...``
path the suite exercises matches the shipped wiring.
"""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("blog/", include("quickscale_modules_blog.urls")),
]
