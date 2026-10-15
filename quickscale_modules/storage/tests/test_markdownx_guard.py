"""Rule 41: the shared Markdownx editor mount is staff-guarded.

Storage mounts the one staff-guarded URLconf every installed module's Markdown
editor posts to, so the editor keeps working without exposing an anonymous
preview or upload surface.  These are HTTP-level checks of that boundary;
tenant middleware is isolated out so the guard itself is exercised.  The
upload checks also pin the stored identity: the shared form decodes every
upload and stores the decoded format's extension and content type, so a
document that merely claims an image media type is refused.
"""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import HttpResponse
from django.test import Client
from PIL import Image

from quickscale_modules_storage.markdownx_urls import _DecodedImageForm

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

_DOCUMENT_BODY = b"<!doctype html><html><body><script>alert(1)</script></body></html>"

_SVG_BODY = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>'

_GUARD_TEST_MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


def _staff_client() -> Client:
    user = get_user_model().objects.create_user(
        "storage-markdownx-staff", password="pw", is_staff=True
    )
    client = Client()
    client.force_login(user)
    return client


def _upload(client: Client, name: str, body: bytes, content_type: str) -> HttpResponse:
    """Post one upload to the shared endpoint the way the editor does."""
    return client.post(
        "/markdownx/upload/",
        {"image": SimpleUploadedFile(name, body, content_type=content_type)},
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )


def _stored_upload_names(media_root: Path) -> list[str]:
    """Return the file names the shared endpoint stored under ``markdownx/``."""
    upload_dir = media_root / "markdownx"
    if not upload_dir.is_dir():
        return []
    return sorted(path.name for path in upload_dir.iterdir())


def _jpeg_bytes() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (2, 2), "red").save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.mark.django_db
class TestSharedMarkdownxGuard:
    @pytest.fixture(autouse=True)
    def _guard_settings(self, settings) -> None:
        settings.ROOT_URLCONF = "tests.urls_markdownx_guard"
        settings.MIDDLEWARE = _GUARD_TEST_MIDDLEWARE

    def test_anonymous_markdownify_is_refused(self) -> None:
        response = Client().post("/markdownx/markdownify/", {"content": "# hi"})
        assert response.status_code == 302

    def test_anonymous_upload_is_refused(self) -> None:
        response = Client().post("/markdownx/upload/")
        assert response.status_code == 302

    def test_authenticated_non_staff_is_refused(self) -> None:
        user = get_user_model().objects.create_user(
            "storage-markdownx-user", password="pw"
        )
        client = Client()
        client.force_login(user)
        response = client.post("/markdownx/markdownify/", {"content": "# hi"})
        assert response.status_code == 302

    def test_staff_markdownify_renders(self) -> None:
        response = _staff_client().post("/markdownx/markdownify/", {"content": "# hi"})
        assert response.status_code == 200

    def test_staff_upload_saves(self, settings, tmp_path) -> None:
        settings.MEDIA_ROOT = tmp_path
        upload = SimpleUploadedFile("dot.png", _ONE_PIXEL_PNG, content_type="image/png")
        response = _staff_client().post(
            "/markdownx/upload/",
            {"image": upload},
            HTTP_X_REQUESTED_WITH="XMLHttpRequest",
        )
        assert response.status_code == 200
        assert "image_code" in response.json()


@pytest.mark.django_db
class TestDecodedUploadIdentity:
    """The upload stores the decoded image's identity, never the client's claim.

    The vendor form keeps the client's filename extension and content type,
    and GIF and SVG skip its Pillow step, so an HTML document named ``.png``
    could land in public media.  The module's form decodes every upload and
    re-derives the stored extension and content type from the decoded format.
    """

    @pytest.fixture(autouse=True)
    def _guard_settings(self, settings) -> None:
        settings.ROOT_URLCONF = "tests.urls_markdownx_guard"
        settings.MIDDLEWARE = _GUARD_TEST_MIDDLEWARE

    def test_html_named_png_is_refused_and_stored_nowhere(
        self, settings, tmp_path
    ) -> None:
        """An HTML document claiming `image/png` never reaches media."""
        settings.MEDIA_ROOT = tmp_path

        response = _upload(_staff_client(), "evil.png", _DOCUMENT_BODY, "image/png")

        assert response.status_code == 400
        assert _stored_upload_names(tmp_path) == []

    def test_html_with_a_gif_media_type_is_refused(self, settings, tmp_path) -> None:
        """GIF is a vendor skip-Pillow type, so the decode step refuses the lie."""
        settings.MEDIA_ROOT = tmp_path

        response = _upload(_staff_client(), "evil.png", _DOCUMENT_BODY, "image/gif")

        assert response.status_code == 400
        assert _stored_upload_names(tmp_path) == []

    def test_svg_is_refused(self, settings, tmp_path) -> None:
        """SVG is not an accepted upload type and never reaches media."""
        settings.MEDIA_ROOT = tmp_path

        response = _upload(_staff_client(), "evil.svg", _SVG_BODY, "image/svg+xml")

        assert response.status_code == 400
        assert _stored_upload_names(tmp_path) == []

    def test_svg_body_is_refused_by_the_decode_step(
        self, settings, tmp_path, monkeypatch
    ) -> None:
        """A vendor gate that accepts SVG still never stores an SVG body."""
        import markdownx.forms

        settings.MEDIA_ROOT = tmp_path
        monkeypatch.setattr(
            markdownx.forms,
            "MARKDOWNX_UPLOAD_CONTENT_TYPES",
            (*markdownx.forms.MARKDOWNX_UPLOAD_CONTENT_TYPES, "image/svg+xml"),
        )

        response = _upload(_staff_client(), "evil.svg", _SVG_BODY, "image/svg+xml")

        assert response.status_code == 400
        assert _stored_upload_names(tmp_path) == []

    def test_stored_extension_comes_from_the_decoded_format(
        self, settings, tmp_path
    ) -> None:
        """A real PNG named `.html` is stored under its decoded `.png` extension."""
        settings.MEDIA_ROOT = tmp_path

        response = _upload(_staff_client(), "notes.html", _ONE_PIXEL_PNG, "image/png")

        assert response.status_code == 200
        stored = _stored_upload_names(tmp_path)
        assert len(stored) == 1
        assert stored[0].endswith(".png")
        assert stored[0] in response.json()["image_code"]

    def test_saved_upload_takes_the_decoded_content_type(self) -> None:
        """A JPEG mislabelled as PNG is saved as the decoded JPEG."""
        form = _DecodedImageForm(
            data={},
            files={
                "image": SimpleUploadedFile(
                    "photo.png", _jpeg_bytes(), content_type="image/png"
                )
            },
        )

        assert form.is_valid(), form.errors
        saved = form.save(commit=False)

        assert saved.path.endswith(".jpg")
        assert saved.image.content_type == "image/jpeg"
