"""Rule 1 (D3): the listings Markdownx editor mount is staff-guarded.

The editor endpoints are mounted through the module's guarded URLconf in every
state, so a switched-off listings module keeps a working editor without
exposing an anonymous preview or upload surface.  These are HTTP-level checks
of that boundary; tenant middleware is isolated out so the guard itself is
exercised.
"""

from __future__ import annotations

import base64

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client

_ONE_PIXEL_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)

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
        "listings-markdownx-staff", password="pw", is_staff=True
    )
    client = Client()
    client.force_login(user)
    return client


@pytest.mark.django_db
class TestListingsMarkdownxGuard:
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
            "listings-markdownx-user", password="pw"
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
