"""The shared, staff-guarded Markdownx endpoints (Module Conventions rule 41).

The Markdown editors of every installed module post to the two Markdownx
paths, and the vendor's ``markdownx.urls`` mount carries no authorization.
This URLconf is the one mounted copy: the same two paths, each refusing
anonymous and non-staff callers, so every installed module's editor keeps
working and no anonymous preview or upload surface is exposed.  Storage owns
the mount because it is the media layer both consumers depend on; the mount
and its ``MARKDOWNX_*`` settings are declared here only.

The upload endpoint is served by the module's decoded-image form instead of
the vendor's plain ``ImageForm``: the vendor form keeps the client's filename
extension and content type, and its GIF and SVG shortcut stores those bytes
without Pillow, so without the wrapper an HTML or SVG document could land in
public media on the site's origin.  The wrapper decodes every upload through
storage's shared image validation and stores the decoded format's own
identity -- the fixed extension and content-type mappings -- never the
client's claims.
"""

from __future__ import annotations

from pathlib import Path

from django.contrib.admin.views.decorators import staff_member_required
from django.core.exceptions import ValidationError
from django.urls import path

from markdownx.forms import ImageForm
from markdownx.settings import MARKDOWNX_UPLOAD_MAX_SIZE
from markdownx.views import ImageUploadView, MarkdownifyView

from quickscale_modules_storage._helpers import (
    _image_content_type_for_format,
    _image_extension_for_format,
    validate_file_upload,
)

#: The formats a shared editor upload may carry: the content types the module
#: adapter writes for ``MARKDOWNX_UPLOAD_CONTENT_TYPES`` minus SVG, so an
#: upload is stored only once Pillow decoded it as one of them.  SVG is an
#: active document on the site's origin and is never an accepted upload.
_ALLOWED_UPLOAD_FORMATS = frozenset({"JPEG", "PNG", "GIF"})


class _DecodedImageForm(ImageForm):
    """The vendor image form, storing only the decoded upload's own identity.

    ``clean`` runs the vendor content-type and size checks, then decodes the
    upload through the module's shared validation so a document that is not
    one of the allowed image formats is refused instead of stored.  The
    stored name's extension and the stored content type are re-derived from
    the decoded format, so a mislabelled filename or ``Content-Type`` cannot
    choose either.
    """

    def clean(self):
        """Refuse undecodable uploads and re-derive the stored identity."""
        upload = super().clean()
        try:
            validated = validate_file_upload(
                upload,
                max_size_bytes=MARKDOWNX_UPLOAD_MAX_SIZE,
                allowed_image_formats=set(_ALLOWED_UPLOAD_FORMATS),
            )
        except ValueError as error:
            raise ValidationError(str(error)) from error

        extension = _image_extension_for_format(validated.format)
        upload.name = f"{Path(upload.name).stem}{extension}"
        upload.content_type = _image_content_type_for_format(validated.format)
        return upload


class _DecodedImageUploadView(ImageUploadView):
    """The vendor upload view serving the module's decoded-image form."""

    form_class = _DecodedImageForm


urlpatterns = [
    path(
        "upload/",
        staff_member_required(_DecodedImageUploadView.as_view()),
        name="markdownx_upload",
    ),
    path(
        "markdownify/",
        staff_member_required(MarkdownifyView.as_view()),
        name="markdownx_markdownify",
    ),
]
