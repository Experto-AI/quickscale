"""Tests for blog publish API endpoint"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.test import Client
from django.urls import reverse

from quickscale_modules_blog.models import Category, Post, Tag


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
