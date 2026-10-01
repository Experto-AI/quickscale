"""Staff-guarded Markdownx endpoints for the blog module.

The blog admin's Markdown editor posts to the two Markdownx paths, and the
shared ``markdownx.urls`` mount carries no authorization.  This URLconf is the
module's mount in every state: the same two paths, each refusing anonymous and
non-staff callers, so a switched-off module keeps a working editor (rule 1:
admin kept) without exposing an anonymous preview or upload surface.
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
