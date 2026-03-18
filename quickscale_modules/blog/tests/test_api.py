"""Tests for blog publish API endpoint"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse
from PIL import Image

from quickscale_modules_blog.models import BlogMediaAsset, Category, Post, Tag


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
    """Create a staff user"""
    user_model = get_user_model()
    return user_model.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="staffpass123",
        is_staff=True,
    )


@pytest.mark.django_db
class TestPublishPostApi:
    """Tests for publish post API"""

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

    def test_upload_media_api_valid_png_returns_metadata(
        self,
        client,
        staff_user,
        tmp_path,
        settings,
    ):
        """Test upload API stores the file and returns stable metadata."""
        settings.MEDIA_ROOT = str(tmp_path)
        client.force_login(staff_user)

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
