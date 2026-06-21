"""Tests for blog publish API endpoint"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from PIL import Image

from quickscale_modules_blog.models import BlogMediaAsset, Category, Post, Tag
from quickscale_modules_blog.views import (
    _build_media_response_url,
    _get_authorization_token,
    _get_blog_api_tokens,
    authenticate_blog_api_request,
)
from quickscale_modules_storage.helpers import (
    validate_file_upload as storage_validate_file_upload,
)


UPLOAD_VALIDATION_PATHS = (
    pytest.param(storage_validate_file_upload, id="helper-backed"),
    pytest.param(None, id="helper-absent"),
)

DECOMPRESSION_BOMB_PATHS = (
    pytest.param(
        storage_validate_file_upload,
        "quickscale_modules_storage.helpers.Image.open",
        id="helper-backed",
    ),
    pytest.param(
        None,
        "quickscale_modules_blog.views.Image.open",
        id="helper-absent",
    ),
)


def make_uploaded_test_image(
    *,
    filename: str = "upload.png",
    image_format: str = "PNG",
    size: tuple[int, int] = (1200, 800),
) -> SimpleUploadedFile:
    """Create an in-memory uploaded image file for API tests."""
    from io import BytesIO

    image_bytes = BytesIO()
    image = Image.new("RGB", size, color="orange")
    image.save(image_bytes, format=image_format)
    return SimpleUploadedFile(
        filename,
        image_bytes.getvalue(),
        content_type=f"image/{image_format.lower()}",
    )


@pytest.fixture
def staff_user(db):
    """Create a staff user with a personal org (SaaS mode)."""
    from quickscale_modules_orgs.models import Organization

    user_model = get_user_model()
    staff_user = user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="staffpass123",
        is_staff=True,
    )
    Organization.objects.create_personal_for(staff_user)
    return staff_user


@pytest.fixture(autouse=True)
def clear_blog_api_rate_limit_cache():
    """Keep per-IP blog API throttle state isolated across tests."""
    cache.clear()
    yield
    cache.clear()


@pytest.mark.django_db
class TestPublishPostApi:
    """Tests for publish post API"""

    def test_get_blog_api_tokens_ignores_invalid_entries(self, settings):
        """Token config helper should keep only valid token/username mappings."""
        settings.BLOG_API_TOKENS = [
            {"token": " valid-token ", "username": " author "},
            {"token": "", "username": "missing-token"},
            {"token": "missing-user", "username": ""},
            "invalid-entry",
        ]

        assert _get_blog_api_tokens() == [("valid-token", "author")]

    def test_get_authorization_token_rejects_malformed_headers(self, rf):
        """Authorization parsing should reject malformed or unsupported headers."""
        assert _get_authorization_token(rf.get("/blog/api")) is None
        assert (
            _get_authorization_token(rf.get("/blog/api", HTTP_AUTHORIZATION="Bearer"))
            == ""
        )
        assert (
            _get_authorization_token(
                rf.get("/blog/api", HTTP_AUTHORIZATION="Basic abc123")
            )
            == ""
        )

    def test_authenticate_blog_api_request_rejects_missing_token_user(
        self,
        rf,
        settings,
    ):
        """Token auth should fail when the configured username does not exist."""
        settings.BLOG_API_TOKENS = [{"token": "publish-token", "username": "ghost"}]

        _, response = authenticate_blog_api_request(
            rf.post("/blog/api", HTTP_AUTHORIZATION="Bearer publish-token")
        )

        assert response is not None
        assert response.status_code == 401
        assert response.content == b'{"error": "Invalid API token"}'

    def test_authenticate_blog_api_request_rejects_non_staff_token_user(
        self,
        rf,
        settings,
        user,
    ):
        """Token auth should still require staff access for machine users."""
        settings.BLOG_API_TOKENS = [
            {"token": "publish-token", "username": user.username}
        ]

        _, response = authenticate_blog_api_request(
            rf.post("/blog/api", HTTP_AUTHORIZATION="Token publish-token")
        )

        assert response is not None
        assert response.status_code == 403
        assert response.content == b'{"error": "Staff access required"}'

    def test_publish_post_api_get_method_not_allowed_returns_405(self, client):
        """Test API rejects non-POST methods"""
        response = client.get(reverse("quickscale_blog:api_publish_post"))

        assert response.status_code == 405
        assert response.json()["error"] == "Method not allowed"

    def test_publish_post_api_unauthenticated_returns_401(self, client):
        """Test API requires authentication"""
        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 401
        assert response.json()["error"] == "Authentication required"

    def test_publish_post_api_non_staff_returns_403(self, client, user):
        """Test API requires staff permissions"""
        client.force_login(user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        assert response.json()["error"] == "Staff access required"

    def test_publish_post_api_missing_csrf_returns_403(self, staff_user):
        """Test API enforces CSRF protection for session-authenticated requests"""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(staff_user)

        response = csrf_client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 403

    def test_publish_post_api_token_auth_bypasses_csrf(
        self,
        settings,
        staff_user,
    ):
        """Test machine-authenticated publish requests can use bearer tokens."""
        settings.BLOG_API_TOKENS = [
            {"token": "publish-token", "username": staff_user.username}
        ]
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Token Post", "content": "Body"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer publish-token",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="token-post")
        assert post.author == staff_user

    def test_publish_post_api_token_auth_ignores_spoofed_forwarded_for_for_rate_limit(
        self,
        settings,
        staff_user,
    ):
        """Token-authenticated publish requests should throttle by REMOTE_ADDR by default."""
        settings.BLOG_API_RATE_LIMIT = "1/hour"
        settings.BLOG_API_TOKENS = [
            {"token": "publish-token", "username": staff_user.username}
        ]
        csrf_client = Client(enforce_csrf_checks=True)

        first_response = csrf_client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Token Post One", "content": "Body"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer publish-token",
            HTTP_X_FORWARDED_FOR="198.51.100.10",
            REMOTE_ADDR="10.0.0.8",
        )
        second_response = csrf_client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Token Post Two", "content": "Body"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer publish-token",
            HTTP_X_FORWARDED_FOR="198.51.100.11",
            REMOTE_ADDR="10.0.0.8",
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 429
        assert second_response.json() == {"error": "Rate limit exceeded"}
        assert int(second_response["Retry-After"]) > 0
        assert Post.objects.filter(slug="token-post-two").count() == 0

    def test_publish_post_api_missing_csrf_still_returns_403_when_rate_limited(
        self,
        settings,
        staff_user,
    ):
        """Session-authenticated requests should keep CSRF enforcement ahead of throttling."""
        settings.BLOG_API_RATE_LIMIT = "1/hour"
        settings.BLOG_API_TOKENS = [
            {"token": "publish-token", "username": staff_user.username}
        ]

        token_client = Client(enforce_csrf_checks=True)
        session_client = Client(enforce_csrf_checks=True)
        session_client.force_login(staff_user)

        warm_response = token_client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Warm Post", "content": "Body"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer publish-token",
        )
        csrf_response = session_client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Blocked Post", "content": "Body"}),
            content_type="application/json",
        )

        assert warm_response.status_code == 201
        assert csrf_response.status_code == 403

    def test_publish_post_api_invalid_json_returns_400(self, client, staff_user):
        """Test API validates JSON format"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data="not-json",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "Invalid JSON payload"

    def test_publish_post_api_non_object_payload_returns_400(self, client, staff_user):
        """Test API requires JSON object payload"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(["not", "an", "object"]),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "JSON object payload expected"

    def test_publish_post_api_invalid_utf8_payload_returns_400(
        self, client, staff_user
    ):
        """Test API rejects non-UTF-8 request body payload"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=b"\xff",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["error"] == "Invalid JSON payload"

    def test_publish_post_api_missing_required_fields_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates required fields"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "title": "This field is required",
            "content": "This field is required",
        }

    def test_publish_post_api_non_sluggable_title_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API requires title to generate a usable slug"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "!!!", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "title": "Must include at least one letter or number"
        }

    def test_publish_post_api_unknown_category_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates category slug exists"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "API Post",
                    "content": "Post content",
                    "category_slug": "missing-category",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {"category_slug": "Category not found"}

    def test_publish_post_api_non_string_excerpt_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates excerpt type"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "API Post",
                    "content": "Post content",
                    "excerpt": 123,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {"excerpt": "Must be a string"}

    def test_publish_post_api_non_string_category_slug_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates category_slug type"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "API Post",
                    "content": "Post content",
                    "category_slug": 1,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "category_slug": "Must be a non-empty string"
        }

    def test_publish_post_api_valid_payload_creates_published_post(
        self,
        client,
        staff_user,
    ):
        """Test API creates published post and returns metadata"""
        category = Category.objects.create(name="Automation")
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Automated Post",
                    "content": "# Markdown content",
                    "excerpt": "Generated excerpt",
                    "category_slug": category.slug,
                    "tags": ["Release", "Automation"],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["status"] == "published"
        assert payload["slug"] == "automated-post"
        assert payload["url"] == "/blog/post/automated-post/"

        post = Post.objects.get(slug="automated-post")
        assert post.status == "published"
        assert post.author == staff_user
        assert post.category == category
        assert post.excerpt == "Generated excerpt"
        assert set(post.tags.values_list("slug", flat=True)) == {
            "release",
            "automation",
        }

    def test_publish_post_api_featured_image_id_assigns_uploaded_asset(
        self,
        client,
        staff_user,
        tmp_path,
        settings,
    ):
        """Test publish API can attach a previously uploaded media asset."""
        settings.MEDIA_ROOT = str(tmp_path)
        asset = BlogMediaAsset.objects.create(
            file=make_uploaded_test_image(filename="featured.png"),
            alt="Generated cover image",
            kind=BlogMediaAsset.Kind.FEATURED,
            original_filename="featured.png",
            width=1200,
            height=800,
            uploaded_by=staff_user,
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Featured Asset Post",
                    "content": "Body",
                    "featured_image_id": asset.pk,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="featured-asset-post")
        assert post.featured_image.name == asset.file.name
        assert post.featured_image_alt == "Generated cover image"

    def test_publish_post_api_unknown_featured_image_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test publish API validates the uploaded featured image reference."""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Missing Asset Post",
                    "content": "Body",
                    "featured_image_id": 99999,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "featured_image_id": "Media asset not found"
        }

    def test_publish_post_api_featured_image_alt_requires_image(
        self,
        client,
        staff_user,
    ):
        """Test publish API rejects a featured image alt without an image."""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Alt Without Image",
                    "content": "Body",
                    "featured_image_alt": "No asset",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "featured_image_alt": "featured_image_alt requires featured_image_id"
        }

    def test_publish_post_api_duplicate_slug_returns_409(self, client, staff_user):
        """Test API handles duplicate generated slug as conflict"""
        Post.objects.create(
            title="Duplicate Title",
            content="Existing content",
            status="published",
            author=staff_user,
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Duplicate Title", "content": "New content"}),
            content_type="application/json",
        )

        assert response.status_code == 409
        assert response.json()["error"] == "Post already exists for generated slug"

    def test_publish_post_api_invalid_tags_returns_400(self, client, staff_user):
        """Test API validates tags payload type"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "API Post", "content": "Body", "tags": "bad"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {"tags": "Must be a list of strings"}

    def test_publish_post_api_non_sluggable_tag_returns_400(self, client, staff_user):
        """Test API validates tags can generate usable slugs"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "API Post", "content": "Body", "tags": ["!!!"]}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "tags": "Each tag must include at least one letter or number"
        }

    def test_publish_post_api_non_string_tag_value_returns_400(
        self, client, staff_user
    ):
        """Test API validates each tag value type"""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "API Post", "content": "Body", "tags": [1]}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "tags": "Must be a list of non-empty strings"
        }

    def test_publish_post_api_unexpected_integrity_error_returns_500(
        self,
        client,
        staff_user,
    ):
        """Test API returns server error for non-conflict integrity failures"""
        client.force_login(staff_user)

        with patch(
            "quickscale_modules_blog.views.create_published_post_from_payload",
            side_effect=IntegrityError("other integrity error"),
        ):
            response = client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "API Post", "content": "Body"}),
                content_type="application/json",
            )

        assert response.status_code == 500
        assert response.json()["error"] == "Unable to publish post"

    def test_publish_post_api_conflict_detected_after_race_returns_409(
        self,
        client,
        staff_user,
    ):
        """Test API maps race-condition slug conflicts to conflict response"""
        client.force_login(staff_user)

        initial_slug_lookup = MagicMock()
        initial_slug_lookup.exists.return_value = False
        race_check_slug_lookup = MagicMock()
        race_check_slug_lookup.exists.return_value = True

        with (
            patch(
                "quickscale_modules_blog.views.Post.objects.filter",
                side_effect=[initial_slug_lookup, race_check_slug_lookup],
            ),
            patch(
                "quickscale_modules_blog.views.Post.objects.create",
                side_effect=IntegrityError("slug conflict"),
            ),
        ):
            response = client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "API Post", "content": "Body"}),
                content_type="application/json",
            )

        assert response.status_code == 409
        assert response.json()["error"] == "Post already exists for generated slug"

    def test_publish_post_api_creates_missing_tags(self, client, staff_user):
        """Test API creates new tags when they do not exist"""
        client.force_login(staff_user)
        assert Tag.objects.count() == 0

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Tag Post",
                    "content": "Body",
                    "tags": ["Launch"],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        assert Tag.objects.filter(slug="launch", name="Launch").exists()


@pytest.mark.django_db
class TestUploadMediaApi:
    """Tests for blog media upload API."""

    def test_build_media_response_url_without_helper_uses_public_base_url(
        self,
        rf,
        settings,
    ):
        """Fallback URL builder should use the canonical public base when configured."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"

        request = rf.get(reverse("quickscale_blog:api_upload_media"))

        with patch(
            "quickscale_modules_blog.views.storage_build_public_media_url", None
        ):
            assert (
                _build_media_response_url(
                    request, "blog/uploads/2026/03/hero-image.png"
                )
                == "https://cdn.example.com/media/blog/uploads/2026/03/hero-image.png"
            )

    def test_build_media_response_url_without_helper_preserves_absolute_reference(
        self,
        rf,
    ):
        """Fallback URL builder should return already-absolute references unchanged."""
        request = rf.get(reverse("quickscale_blog:api_upload_media"))
        absolute_url = "https://cdn.example.com/blog/uploads/2026/03/hero-image.png"

        with patch(
            "quickscale_modules_blog.views.storage_build_public_media_url", None
        ):
            assert _build_media_response_url(request, absolute_url) == absolute_url

    def test_build_media_response_url_without_helper_normalizes_relative_media_url(
        self,
        rf,
        settings,
    ):
        """Fallback URL builder should normalize relative `MEDIA_URL` prefixes."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = ""
        settings.MEDIA_URL = "media"

        request = rf.get(reverse("quickscale_blog:api_upload_media"))

        with patch(
            "quickscale_modules_blog.views.storage_build_public_media_url", None
        ):
            assert (
                _build_media_response_url(
                    request, "blog/uploads/2026/03/hero-image.png"
                )
                == "http://testserver/media/blog/uploads/2026/03/hero-image.png"
            )

    def test_build_media_response_url_without_helper_uses_leading_slash_path(
        self,
        rf,
        settings,
    ):
        """Fallback URL builder should preserve leading-slash media references."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = ""

        request = rf.get(reverse("quickscale_blog:api_upload_media"))

        with patch(
            "quickscale_modules_blog.views.storage_build_public_media_url", None
        ):
            assert (
                _build_media_response_url(
                    request, "/media/blog/uploads/2026/03/hero-image.png"
                )
                == "http://testserver/media/blog/uploads/2026/03/hero-image.png"
            )

    def test_upload_media_api_requires_authentication(self, client):
        """Test media uploads require authentication."""
        response = client.post(reverse("quickscale_blog:api_upload_media"))

        assert response.status_code == 401
        assert response.json()["error"] == "Authentication required"

    def test_upload_media_api_non_staff_returns_403(self, client, user):
        """Test media uploads require staff access."""
        client.force_login(user)

        response = client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image()},
        )

        assert response.status_code == 403
        assert response.json()["error"] == "Staff access required"

    def test_upload_media_api_missing_csrf_returns_403(self, staff_user):
        """Test session-authenticated media uploads enforce CSRF protection."""
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(staff_user)

        response = csrf_client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image()},
        )

        assert response.status_code == 403

    @pytest.mark.parametrize("storage_validator", UPLOAD_VALIDATION_PATHS)
    def test_upload_media_api_valid_png_returns_metadata(
        self,
        client,
        staff_user,
        tmp_path,
        settings,
        storage_validator,
    ):
        """Test upload API stores the file and returns stable metadata."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.BLOG_API_UPLOAD_MAX_WIDTH = 1600
        settings.BLOG_API_UPLOAD_MAX_HEIGHT = 900
        client.force_login(staff_user)

        with patch(
            "quickscale_modules_blog.views.storage_validate_file_upload",
            storage_validator,
        ):
            response = client.post(
                reverse("quickscale_blog:api_upload_media"),
                data={
                    "file": make_uploaded_test_image(size=(1600, 900)),
                    "alt": "Pep Martorell interview diagram",
                    "kind": BlogMediaAsset.Kind.INLINE,
                },
            )

        assert response.status_code == 201
        payload = response.json()
        assert payload["alt"] == "Pep Martorell interview diagram"
        assert payload["kind"] == BlogMediaAsset.Kind.INLINE
        assert payload["width"] == 1600
        assert payload["height"] == 900
        assert payload["url"].startswith("http://testserver/media/blog/uploads/")
        assert BlogMediaAsset.objects.filter(pk=payload["id"]).exists()

    @pytest.mark.parametrize("storage_validator", UPLOAD_VALIDATION_PATHS)
    def test_upload_media_api_rejects_excessive_width_with_or_without_helper(
        self,
        client,
        staff_user,
        settings,
        storage_validator,
    ):
        """Upload API should apply the same width ceiling in both validation paths."""
        settings.BLOG_API_UPLOAD_MAX_WIDTH = 1600
        settings.BLOG_API_UPLOAD_MAX_HEIGHT = 900
        client.force_login(staff_user)

        with patch(
            "quickscale_modules_blog.views.storage_validate_file_upload",
            storage_validator,
        ):
            response = client.post(
                reverse("quickscale_blog:api_upload_media"),
                data={"file": make_uploaded_test_image(size=(1601, 900))},
            )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "file": "Image width exceeds maximum of 1600 pixels"
        }

    @pytest.mark.parametrize("storage_validator", UPLOAD_VALIDATION_PATHS)
    def test_upload_media_api_rejects_excessive_height_with_or_without_helper(
        self,
        client,
        staff_user,
        settings,
        storage_validator,
    ):
        """Upload API should apply the same height ceiling in both validation paths."""
        settings.BLOG_API_UPLOAD_MAX_WIDTH = 1600
        settings.BLOG_API_UPLOAD_MAX_HEIGHT = 900
        client.force_login(staff_user)

        with patch(
            "quickscale_modules_blog.views.storage_validate_file_upload",
            storage_validator,
        ):
            response = client.post(
                reverse("quickscale_blog:api_upload_media"),
                data={"file": make_uploaded_test_image(size=(1600, 901))},
            )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "file": "Image height exceeds maximum of 900 pixels"
        }

    def test_upload_media_api_uses_public_base_url_when_configured(
        self,
        client,
        staff_user,
        tmp_path,
        settings,
    ):
        """Test upload API returns CDN/public base URL when configured."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={
                "file": make_uploaded_test_image(size=(900, 600)),
                "alt": "CDN image",
                "kind": BlogMediaAsset.Kind.GENERAL,
            },
        )

        assert response.status_code == 201
        payload = response.json()
        assert payload["url"].startswith("https://cdn.example.com/media/")

    @patch("quickscale_modules_blog.views.create_blog_media_asset_from_request")
    def test_upload_media_api_uses_stored_key_not_provider_url_for_public_base(
        self,
        mock_create_asset,
        client,
        staff_user,
        settings,
    ):
        """Upload API should build canonical CDN URLs from the stored key."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"
        client.force_login(staff_user)

        file_mock = MagicMock()
        file_mock.name = "blog/uploads/2026/03/hero-image.png"
        file_mock.url = (
            "https://bucket.s3.amazonaws.com/blog/uploads/2026/03/"
            "hero-image.png?signature=abc"
        )

        asset = MagicMock()
        asset.pk = 123
        asset.file = file_mock
        asset.alt = "CDN image"
        asset.kind = BlogMediaAsset.Kind.GENERAL
        asset.width = 900
        asset.height = 600
        mock_create_asset.return_value = asset

        response = client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image(size=(900, 600))},
        )

        assert response.status_code == 201
        payload = response.json()
        assert (
            payload["url"]
            == "https://cdn.example.com/media/blog/uploads/2026/03/hero-image.png"
        )

    @patch("quickscale_modules_blog.views.create_blog_media_asset_from_request")
    def test_upload_media_api_uses_local_media_url_when_public_base_url_is_unset(
        self,
        mock_create_asset,
        client,
        staff_user,
        settings,
    ):
        """Upload API should build local media URLs from the stored key."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = ""
        client.force_login(staff_user)

        file_mock = MagicMock()
        file_mock.name = "blog/uploads/2026/03/hero-image.png"
        file_mock.url = (
            "https://bucket.s3.amazonaws.com/blog/uploads/2026/03/"
            "hero-image.png?signature=abc"
        )

        asset = MagicMock()
        asset.pk = 456
        asset.file = file_mock
        asset.alt = "Provider image"
        asset.kind = BlogMediaAsset.Kind.GENERAL
        asset.width = 900
        asset.height = 600
        mock_create_asset.return_value = asset

        response = client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image(size=(900, 600))},
        )

        assert response.status_code == 201
        payload = response.json()
        assert (
            payload["url"]
            == "http://testserver/media/blog/uploads/2026/03/hero-image.png"
        )

    def test_build_media_response_url_uses_local_media_fallback_when_no_public_base_url(
        self,
        rf,
        settings,
    ):
        """Media response helper should fall back to local media paths without a canonical base URL."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = ""

        request = rf.get(reverse("quickscale_blog:api_upload_media"))

        assert (
            _build_media_response_url(
                request,
                "blog/uploads/2026/03/hero-image.png",
            )
            == "http://testserver/media/blog/uploads/2026/03/hero-image.png"
        )

    def test_upload_media_api_rejects_unsupported_file_type(
        self,
        client,
        staff_user,
    ):
        """Test upload API rejects files that are not valid supported images."""
        client.force_login(staff_user)
        bad_file = SimpleUploadedFile(
            "notes.txt",
            b"not an image",
            content_type="text/plain",
        )

        response = client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": bad_file},
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "file": "Unsupported or invalid image file"
        }

    @pytest.mark.parametrize(
        ("storage_validator", "image_open_target"),
        DECOMPRESSION_BOMB_PATHS,
    )
    def test_upload_media_api_rejects_decompression_bombs_with_or_without_helper(
        self,
        client,
        staff_user,
        settings,
        storage_validator,
        image_open_target,
    ):
        """Upload API should normalize Pillow bomb protection failures in both paths."""
        client.force_login(staff_user)

        with (
            patch(
                "quickscale_modules_blog.views.storage_validate_file_upload",
                storage_validator,
            ),
            patch(
                image_open_target,
                side_effect=Image.DecompressionBombError("too many pixels"),
            ),
        ):
            response = client.post(
                reverse("quickscale_blog:api_upload_media"),
                data={"file": make_uploaded_test_image(size=(900, 600))},
            )

        assert response.status_code == 400
        assert response.json()["errors"] == {"file": "Image exceeds safe pixel limit"}

    def test_upload_media_api_token_auth_bypasses_csrf(
        self,
        settings,
        staff_user,
        tmp_path,
    ):
        """Test machine-authenticated media uploads can use bearer tokens."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.BLOG_API_TOKENS = [
            {"token": "upload-token", "username": staff_user.username}
        ]
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image()},
            HTTP_AUTHORIZATION="Bearer upload-token",
        )

        assert response.status_code == 201

    def test_upload_media_api_token_auth_ignores_spoofed_forwarded_for_for_rate_limit(
        self,
        settings,
        staff_user,
        tmp_path,
    ):
        """Token-authenticated uploads should throttle by REMOTE_ADDR by default."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.BLOG_API_RATE_LIMIT = "1/hour"
        settings.BLOG_API_TOKENS = [
            {"token": "upload-token", "username": staff_user.username}
        ]
        csrf_client = Client(enforce_csrf_checks=True)

        first_response = csrf_client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image()},
            HTTP_AUTHORIZATION="Bearer upload-token",
            HTTP_X_FORWARDED_FOR="198.51.100.20",
            REMOTE_ADDR="10.0.0.9",
        )
        second_response = csrf_client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image(filename="upload-2.png")},
            HTTP_AUTHORIZATION="Bearer upload-token",
            HTTP_X_FORWARDED_FOR="198.51.100.21",
            REMOTE_ADDR="10.0.0.9",
        )

        assert first_response.status_code == 201
        assert second_response.status_code == 429
        assert second_response.json() == {"error": "Rate limit exceeded"}
        assert int(second_response["Retry-After"]) > 0


@pytest.mark.django_db
class TestOrgScopedPublishPostApi:
    """Tests for org-scoped publish post API (Phase 2, F11.11)"""

    def test_org_scoped_publish_stamps_organization(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Test that an org-scoped publish creates a post stamped with the org."""
        client.force_login(org_a_admin)

        response = client.post(
            reverse(
                "quickscale_blog:org-api_publish_post",
                kwargs={"org_slug": org_a.slug},
            ),
            data=json.dumps({"title": "Org A Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="org-a-post")
        assert post.organization == org_a

    def test_org_scoped_publish_category_must_be_same_org(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
    ):
        """Test that referencing a category from another org fails."""
        from quickscale_modules_blog.models import Category

        cat_b = Category.objects.create(
            name="Org B Cat", slug="org-b-cat", organization=org_b
        )

        client.force_login(org_a_admin)

        response = client.post(
            reverse(
                "quickscale_blog:org-api_publish_post",
                kwargs={"org_slug": org_a.slug},
            ),
            data=json.dumps(
                {
                    "title": "Cross Org Post",
                    "content": "Body",
                    "category_slug": cat_b.slug,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {"category_slug": "Category not found"}

    def test_org_scoped_publish_referenced_media_must_be_same_org(
        self,
        client,
        org_a,
        org_b,
        org_a_admin,
        tmp_path,
        settings,
    ):
        """Test that referencing a media asset from another org fails."""
        settings.MEDIA_ROOT = str(tmp_path)
        from quickscale_modules_blog.models import BlogMediaAsset

        asset_b = BlogMediaAsset.objects.create(
            file=make_uploaded_test_image(filename="featured-b.png"),
            alt="Org B featured",
            kind=BlogMediaAsset.Kind.FEATURED,
            original_filename="featured-b.png",
            width=800,
            height=600,
            uploaded_by=org_a_admin,
            organization=org_b,
        )

        client.force_login(org_a_admin)

        response = client.post(
            reverse(
                "quickscale_blog:org-api_publish_post",
                kwargs={"org_slug": org_a.slug},
            ),
            data=json.dumps(
                {
                    "title": "Cross Media Post",
                    "content": "Body",
                    "featured_image_id": asset_b.pk,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "featured_image_id": "Media asset not found"
        }

    def test_org_scoped_media_upload_stamps_org(
        self,
        client,
        org_a,
        org_a_admin,
        tmp_path,
        settings,
    ):
        """Test that an org-scoped media upload stamps the org."""
        settings.MEDIA_ROOT = str(tmp_path)
        client.force_login(org_a_admin)

        response = client.post(
            reverse(
                "quickscale_blog:org-api_upload_media",
                kwargs={"org_slug": org_a.slug},
            ),
            data={
                "file": make_uploaded_test_image(),
                "alt": "Org A image",
                "kind": BlogMediaAsset.Kind.GENERAL,
            },
        )

        assert response.status_code == 201
        payload = response.json()
        asset = BlogMediaAsset.objects.get(pk=payload["id"])
        assert asset.organization == org_a


@pytest.mark.django_db
class TestOrgScopedCategoryTagValidation:
    """Tests for org-scoped same-org validation on category and tag lookups.

    Phase 2 (F11.11): when creating posts via org-scoped routes, referenced
    categories and tags must belong to the same organization.
    """

    def test_org_scoped_publish_same_org_category_succeeds(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Test that referencing a same-org category succeeds."""
        from quickscale_modules_blog.models import Category

        cat_a = Category.objects.create(
            name="Org A Cat", slug="org-a-cat", organization=org_a
        )

        client.force_login(org_a_admin)

        response = client.post(
            reverse(
                "quickscale_blog:org-api_publish_post",
                kwargs={"org_slug": org_a.slug},
            ),
            data=json.dumps(
                {
                    "title": "Same Org Post",
                    "content": "Body",
                    "category_slug": cat_a.slug,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="same-org-post")
        assert post.category == cat_a
        assert post.organization == org_a

    def test_org_scoped_publish_same_org_tag_succeeds(
        self,
        client,
        org_a,
        org_a_admin,
    ):
        """Test that creating a tag within the same org via org-scoped publish works."""
        client.force_login(org_a_admin)

        response = client.post(
            reverse(
                "quickscale_blog:org-api_publish_post",
                kwargs={"org_slug": org_a.slug},
            ),
            data=json.dumps(
                {
                    "title": "Tagged Org Post",
                    "content": "Body",
                    "tags": ["org-a-tag"],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="tagged-org-post")
        assert post.organization == org_a
        tag_slugs = list(post.tags.values_list("slug", flat=True))
        assert "org-a-tag" in tag_slugs
        # Verify tag is org-scoped
        from quickscale_modules_blog.models import Tag

        tag = Tag.objects.get(slug="org-a-tag")
        assert tag.organization == org_a

    def test_flat_publish_does_not_stamp_org(
        self,
        client,
        staff_user,
    ):
        """Test that the flat (non-org-scoped) publish path does not stamp org."""
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Flat Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="flat-post")
        assert post.organization is None, (
            "Flat publish should leave organization as None"
        )

    def test_flat_media_upload_does_not_stamp_org(
        self,
        client,
        staff_user,
        tmp_path,
        settings,
    ):
        """Test that the flat media upload path does not stamp org."""
        settings.MEDIA_ROOT = str(tmp_path)
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={
                "file": make_uploaded_test_image(),
                "alt": "Flat image",
                "kind": BlogMediaAsset.Kind.GENERAL,
            },
        )

        assert response.status_code == 201
        payload = response.json()
        asset = BlogMediaAsset.objects.get(pk=payload["id"])
        assert asset.organization is None, (
            "Flat media upload should leave organization as None"
        )


# ---------------------------------------------------------------------------
# CR-001 regression: solo-mode gate for token-authenticated blog APIs
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestTokenAuthSoloModeGate:
    """Token-authenticated org-scoped requests must be rejected in solo mode.

    ``TenantMiddleware._handle_solo_request()`` returns 404 for
    ``/orgs/...`` routes, but token-auth requests bypass the middleware
    (``request.user`` is anonymous at middleware time so it passes through).
    ``_resolve_org_for_token_auth()`` must independently enforce the same
    solo-mode gate.
    """

    def test_token_publish_on_org_route_rejected_in_solo_mode(
        self,
        settings,
        org_a,
        org_a_admin,
    ):
        """Org-scoped token publish must be rejected in solo mode.

        Uses ``org_a_admin`` (an org member) to prove the solo-mode gate
        independently blocks token auth — the rejection is not coming
        from a membership check.
        """
        settings.QUICKSCALE_MODE = "solo"
        settings.BLOG_API_TOKENS = [
            {"token": "publish-token", "username": org_a_admin.username}
        ]
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse(
                "quickscale_blog:org-api_publish_post",
                kwargs={"org_slug": org_a.slug},
            ),
            data=json.dumps({"title": "Solo Token Post", "content": "Body"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer publish-token",
        )

        assert response.status_code == 403
        assert response.json() == {"error": "Organization not found or access denied"}

    def test_token_publish_on_org_route_saas_mode_authorizes_org_member(
        self,
        settings,
        org_a,
        org_a_admin,
    ):
        """Org-scoped token publish in SaaS mode authorizes org members.

        Uses the same ``org_a_admin`` fixture as the solo-mode rejection
        test above.  This paired proof shows that the same token user IS
        authorized in SaaS mode — the solo-mode rejection is from the
        independent solo gate, not from a membership check.
        """
        settings.QUICKSCALE_MODE = "saas"
        settings.BLOG_API_TOKENS = [
            {"token": "publish-token", "username": org_a_admin.username}
        ]
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse(
                "quickscale_blog:org-api_publish_post",
                kwargs={"org_slug": org_a.slug},
            ),
            data=json.dumps({"title": "Saas Token Post", "content": "Body"}),
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer publish-token",
        )

        # org_a_admin is an admin member of org_a, so token auth
        # succeeds in SaaS mode — proving membership validation works
        # and the solo-mode rejection is the additive gate.
        assert response.status_code == 201
        payload = response.json()
        assert payload["slug"] == "saas-token-post"

    def test_token_upload_on_org_route_rejected_in_solo_mode(
        self,
        settings,
        org_a,
        org_a_admin,
        tmp_path,
    ):
        """Org-scoped token media upload must be rejected in solo mode.

        Uses ``org_a_admin`` (an org member) to prove the solo-mode gate
        independently blocks token upload — the rejection is not coming
        from a membership check.
        """
        settings.MEDIA_ROOT = str(tmp_path)
        settings.QUICKSCALE_MODE = "solo"
        settings.BLOG_API_TOKENS = [
            {"token": "upload-token", "username": org_a_admin.username}
        ]
        csrf_client = Client(enforce_csrf_checks=True)

        response = csrf_client.post(
            reverse(
                "quickscale_blog:org-api_upload_media",
                kwargs={"org_slug": org_a.slug},
            ),
            data={"file": make_uploaded_test_image()},
            HTTP_AUTHORIZATION="Bearer upload-token",
        )

        assert response.status_code == 403
        assert response.json() == {"error": "Organization not found or access denied"}


# ---------------------------------------------------------------------------
# CR-002 regression: flat publish must not cross-bind org-owned records
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestFlatPublishTenantIsolation:
    """Flat (non-org-scoped) publish must remain tenant-agnostic.

    ``create_published_post_from_payload`` with ``organization=None`` must
    not resolve category, media, or tag rows that belong to an organization.
    All lookups must restrict to ``organization__isnull=True``.
    """

    def test_flat_publish_org_owned_category_not_found(
        self,
        client,
        staff_user,
        org_a,
    ):
        """Flat publish must not find an org-owned category slug."""
        Category.objects.create(name="Org Cat", slug="org-cat", organization=org_a)
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Flat Post",
                    "content": "Body",
                    "category_slug": "org-cat",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {"category_slug": "Category not found"}

    def test_flat_publish_tenant_agnostic_category_found(
        self,
        client,
        staff_user,
        org_a,
    ):
        """Flat publish must still find a tenant-agnostic category."""
        # An org-owned category with the same slug must not shadow the
        # tenant-agnostic one.
        Category.objects.create(name="Org Cat", slug="shared-slug", organization=org_a)
        flat_cat = Category.objects.create(
            name="Flat Cat", slug="shared-slug", organization=None
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Flat Post",
                    "content": "Body",
                    "category_slug": "shared-slug",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="flat-post")
        assert post.category == flat_cat
        assert post.organization is None

    def test_flat_publish_org_owned_media_not_found(
        self,
        client,
        staff_user,
        org_a,
        tmp_path,
        settings,
    ):
        """Flat publish must not find an org-owned media asset."""
        settings.MEDIA_ROOT = str(tmp_path)
        asset = BlogMediaAsset.objects.create(
            file=make_uploaded_test_image(filename="org-featured.png"),
            alt="Org featured",
            kind=BlogMediaAsset.Kind.FEATURED,
            original_filename="org-featured.png",
            width=800,
            height=600,
            uploaded_by=staff_user,
            organization=org_a,
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Flat Media Post",
                    "content": "Body",
                    "featured_image_id": asset.pk,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert response.json()["errors"] == {
            "featured_image_id": "Media asset not found"
        }

    def test_flat_publish_tenant_agnostic_media_found(
        self,
        client,
        staff_user,
        org_a,
        tmp_path,
        settings,
    ):
        """Flat publish must still find a tenant-agnostic media asset."""
        settings.MEDIA_ROOT = str(tmp_path)
        # Create an org-owned asset with same pk context — just create a
        # separate tenant-agnostic asset.
        BlogMediaAsset.objects.create(
            file=make_uploaded_test_image(filename="org-owned.png"),
            alt="Org owned",
            kind=BlogMediaAsset.Kind.FEATURED,
            original_filename="org-owned.png",
            width=800,
            height=600,
            uploaded_by=staff_user,
            organization=org_a,
        )
        flat_asset = BlogMediaAsset.objects.create(
            file=make_uploaded_test_image(filename="flat-featured.png"),
            alt="Flat featured",
            kind=BlogMediaAsset.Kind.FEATURED,
            original_filename="flat-featured.png",
            width=800,
            height=600,
            uploaded_by=staff_user,
            organization=None,
        )
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Flat Media Post",
                    "content": "Body",
                    "featured_image_id": flat_asset.pk,
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="flat-media-post")
        assert post.featured_image.name == flat_asset.file.name

    def test_flat_publish_tag_does_not_cross_bind_org_owned(
        self,
        client,
        staff_user,
        org_a,
    ):
        """Flat publish must create a new tenant-agnostic tag instead of
        cross-binding an org-owned tag with the same slug."""
        Tag.objects.create(name="Launch", slug="launch", organization=org_a)
        client.force_login(staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "Tag Isolation Post",
                    "content": "Body",
                    "tags": ["Launch"],
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 201
        post = Post.objects.get(slug="tag-isolation-post")
        # Verify we created a separate tenant-agnostic tag, not re-used the
        # org-owned one.
        flat_tag = Tag.objects.filter(slug="launch", organization__isnull=True)
        org_tag = Tag.objects.filter(slug="launch", organization=org_a)
        assert flat_tag.exists(), "Flat publish should create a tenant-agnostic tag"
        assert org_tag.exists(), "The original org-owned tag must still exist"
        # The post should be linked to the tenant-agnostic tag.
        post_tags = post.tags.all()
        assert flat_tag.first() in post_tags
        assert org_tag.first() not in post_tags
        assert post.organization is None
