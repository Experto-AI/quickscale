"""The shared, staff-guarded Markdownx endpoints (Module Conventions rule 41).

The Markdown editors of every installed module post to the two Markdownx
paths, and the vendor's ``markdownx.urls`` mount carries no authorization.
This URLconf is the one mounted copy: the same two paths, each refusing
anonymous and non-staff callers, so every installed module's editor keeps
working and no anonymous preview or upload surface is exposed.  Storage owns
the mount because it is the media layer both consumers depend on; the mount
and its ``MARKDOWNX_*`` settings are declared here only.
"""

from __future__ import annotations

from django.contrib.admin.views.decorators import staff_member_required
from django.urls import path

from markdownx.views import ImageUploadView, MarkdownifyView

urlpatterns = [
    path(
        "upload/",
        staff_member_required(ImageUploadView.as_view()),
        name="markdownx_upload",
    ),
    path(
        "markdownify/",
        staff_member_required(MarkdownifyView.as_view()),
        name="markdownx_markdownify",
    ),
]
