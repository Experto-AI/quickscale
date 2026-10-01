"""Tests for the blog module's DRF automation API endpoints."""

import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ImproperlyConfigured
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import Client, override_settings
from django.urls import reverse
from PIL import Image
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.throttling import ScopedRateThrottle

from quickscale_modules_blog.models import BlogMediaAsset, Category, Post, Tag
from quickscale_modules_blog.throttles import BlogApiThrottle
from quickscale_modules_blog.views import (
    MediaUploadAPIView,
    PostPublishAPIView,
    _build_media_response_url,
)
from quickscale_modules_orgs.current_org import get_client_ip

BLOG_API_SCOPE = "quickscale_blog_api"

#: The blog suite installs storage, so the service-backed cases below exercise
#: the real storage services; the "storage-absent" cases patch the guarded
#: seam to simulate an installation without the module.
STORAGE_PATHS = (
    pytest.param(False, id="storage-installed"),
    pytest.param(True, id="storage-absent"),
)

DECOMPRESSION_BOMB_PATHS = (
    pytest.param(
        False,
        "quickscale_modules_storage.helpers.Image.open",
        id="storage-installed",
    ),
    pytest.param(
        True,
        "quickscale_modules_blog.views.Image.open",
        id="storage-absent",
    ),
)


@contextmanager
def without_storage_services(missing: bool):
    """Simulate storage's absence at the blog seam for one test block."""
    if not missing:
        yield
        return
    with patch("quickscale_modules_blog._storage.storage_services", return_value=None):
        yield


_MISSING = object()

BLOG_CLIENT_IP_CASES = (
    pytest.param(False, 2, "198.51.100.1, 10.0.0.1", id="disabled"),
    pytest.param(True, 0, "198.51.100.1, 10.0.0.1", id="zero"),
    pytest.param(True, 1, None, id="absent"),
    pytest.param(True, 1, "", id="empty"),
    pytest.param(True, 3, "198.51.100.1, , 10.0.0.1", id="empty-hop"),
    pytest.param(True, 2, "198.51.100.1", id="short"),
    pytest.param(True, 2, "198.51.100.1, 10.0.0.1", id="equal"),
    pytest.param(
        True,
        2,
        "198.51.100.1, 198.51.100.2, 10.0.0.1, 10.0.0.2",
        id="long",
    ),
)

BLOG_INVALID_PROXY_SETTINGS = (
    pytest.param("USE_X_FORWARDED_FOR", _MISSING, id="missing-use-xff"),
    pytest.param("USE_X_FORWARDED_FOR", None, id="invalid-use-xff"),
    pytest.param("USE_X_FORWARDED_FOR", "yes", id="invalid-use-xff-string"),
    pytest.param("TRUSTED_PROXY_COUNT", _MISSING, id="missing-proxy-count"),
    pytest.param("TRUSTED_PROXY_COUNT", "1", id="invalid-proxy-count"),
    pytest.param("TRUSTED_PROXY_COUNT", -1, id="invalid-proxy-count-negative"),
    pytest.param("TRUSTED_PROXY_COUNT", True, id="invalid-proxy-count-bool"),
)


def _login_with_org(client, user):
    """Log in *user* and activate their personal org in the session.

    TenantMiddleware in SaaS mode requires ACTIVE_ORG_SESSION_KEY for
    authenticated users; without it the middleware redirects to /orgs/.
    """
    from quickscale_modules_orgs.constants import ACTIVE_ORG_SESSION_KEY
    from quickscale_modules_orgs.models import OrganizationMembership

    client.force_login(user)
    membership = OrganizationMembership.objects.filter(
        user=user, organization__is_personal=True
    ).first()
    if membership is not None:
        session = client.session
        session[ACTIVE_ORG_SESSION_KEY] = str(membership.organization_id)
        session.save()


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


def _rest_framework(rate: str) -> dict[str, object]:
    """Return a REST_FRAMEWORK dict carrying *rate* for the blog API scope."""
    return {
        "DEFAULT_AUTHENTICATION_CLASSES": [
            "rest_framework.authentication.SessionAuthentication",
        ],
        "DEFAULT_THROTTLE_RATES": {BLOG_API_SCOPE: rate},
        "EXCEPTION_HANDLER": "quickscale_core.runtime.conventions.exception_handler",
    }


@contextmanager
def blog_api_rate(rate: str):
    """Apply *rate* as the blog API throttle rate for one test block.

    DRF binds ``DEFAULT_THROTTLE_RATES`` onto the throttle class at import
    time, so the test applies both bindings, as the sibling DRF module's
    suite does.
    """
    cache.clear()
    rates = {BLOG_API_SCOPE: rate}
    with (
        override_settings(REST_FRAMEWORK=_rest_framework(rate)),
        patch.object(ScopedRateThrottle, "THROTTLE_RATES", rates),
    ):
        yield
    cache.clear()


def _error(response) -> dict:
    """Return the one QuickScale error body from *response*."""
    body = response.json()
    assert "error" in body, body
    return body["error"]


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


@pytest.fixture
def staff_org(db, staff_user):
    """Return the personal organization for ``staff_user``."""
    from quickscale_modules_orgs.models import OrganizationMembership

    membership = OrganizationMembership.objects.filter(
        user=staff_user, organization__is_personal=True
    ).first()
    if membership is not None:
        return membership.organization
    from quickscale_modules_orgs.models import Organization

    return Organization.objects.get_system_org()


@pytest.fixture(autouse=True)
def clear_blog_api_throttle_cache():
    """Keep DRF throttle history isolated across tests."""
    cache.clear()
    yield
    cache.clear()


def _assert_org_context_restored_to_none(system_org) -> None:
    """Assert the org ContextVar and GUC are restored and re-prime freshly."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from quickscale_modules_orgs.current_org import (
        get_current_org_id,
        set_current_org_id,
    )

    assert get_current_org_id() is None, (
        "ContextVar should be restored after the request completes"
    )
    with connection.cursor() as cursor:
        cursor.execute("SELECT current_setting('app.current_org_id', true)")
        (raw_guc,) = cursor.fetchone()
    assert raw_guc == "" or raw_guc is None, (
        f"GUC should be empty after restore, got {raw_guc!r}"
    )

    with CaptureQueriesContext(connection) as captured:
        set_current_org_id(system_org.pk)
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_setting('app.current_org_id', true)")
        finally:
            set_current_org_id(None)

    set_local_count = sum(
        1 for q in captured.captured_queries if "SET LOCAL" in q["sql"]
    )
    assert set_local_count == 1, (
        f"Expected 1 SET LOCAL after memo-clear re-prime, got {set_local_count}"
    )


@pytest.mark.django_db
class TestPublishPostApi:
    """Tests for the publish post API"""

    def test_publish_post_api_get_method_not_allowed_returns_405(
        self, client, staff_user
    ):
        """Test API rejects non-POST methods for an authenticated caller"""
        _login_with_org(client, staff_user)

        response = client.get(reverse("quickscale_blog:api_publish_post"))

        assert response.status_code == 405
        assert _error(response)["code"] == "method_not_allowed"

    def test_publish_post_api_unauthenticated_returns_401(self, client):
        """Test API requires authentication"""
        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 401
        assert _error(response)["code"] == "not_authenticated"

    def test_publish_post_api_non_staff_returns_403(self, client, user):
        """Test API requires staff permissions"""
        _login_with_org(client, user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        error = _error(response)
        assert error["code"] == "permission_denied"
        assert error["message"] == "Staff access required"

    def test_publish_post_api_missing_csrf_returns_403(self, staff_user):
        """Test API enforces CSRF protection for session-authenticated requests"""
        csrf_client = Client(enforce_csrf_checks=True)
        _login_with_org(csrf_client, staff_user)

        response = csrf_client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Post", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 403
        assert _error(response)["code"] == "permission_denied"

    def test_publish_post_api_invalid_json_returns_400(self, client, staff_user):
        """Test API validates JSON format"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data="not-json",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["code"] == "parse_error"

    def test_publish_post_api_non_object_payload_returns_400(self, client, staff_user):
        """Test API requires JSON object payload"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(["not", "an", "object"]),
            content_type="application/json",
        )

        assert response.status_code == 400
        error = _error(response)
        assert error["code"] == "validation_error"
        assert error["fields"] == {"non_field_errors": ["JSON object payload expected"]}

    def test_publish_post_api_invalid_utf8_payload_returns_400(
        self, client, staff_user
    ):
        """Test API rejects non-UTF-8 request body payload"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=b"\xff",
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["code"] == "parse_error"

    def test_publish_post_api_missing_required_fields_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates required fields"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": ""}),
            content_type="application/json",
        )

        assert response.status_code == 400
        error = _error(response)
        assert error["code"] == "validation_error"
        assert error["message"] == "Invalid input."
        assert error["fields"] == {
            "title": ["This field is required"],
            "content": ["This field is required"],
        }

    def test_publish_post_api_non_sluggable_title_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API requires title to generate a usable slug"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "!!!", "content": "Content"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["fields"] == {
            "title": ["Must include at least one letter or number"]
        }

    def test_publish_post_api_unknown_category_returns_400(
        self,
        client,
        staff_user,
        staff_org,
        blog_org_scope,
    ):
        """Test API validates category slug exists"""
        # Create a category in a different org to confirm it's not found
        with blog_org_scope(staff_org):
            Category.objects.create(
                name="Missing Cat", slug="missing-category", organization=staff_org
            )
        _login_with_org(client, staff_user)

        # Use a slug that doesn't exist in the resolved org
        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps(
                {
                    "title": "API Post",
                    "content": "Post content",
                    "category_slug": "nonexistent-category",
                }
            ),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["fields"] == {"category_slug": ["Category not found"]}

    def test_publish_post_api_non_string_excerpt_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates excerpt type"""
        _login_with_org(client, staff_user)

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
        assert _error(response)["fields"] == {"excerpt": ["Must be a string"]}

    def test_publish_post_api_non_string_category_slug_returns_400(
        self,
        client,
        staff_user,
    ):
        """Test API validates category_slug type"""
        _login_with_org(client, staff_user)

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
        assert _error(response)["fields"] == {
            "category_slug": ["Must be a non-empty string"]
        }

    def test_publish_post_api_valid_payload_creates_published_post(
        self,
        client,
        staff_user,
        staff_org,
        blog_org_scope,
    ):
        """Test API creates published post and returns metadata"""
        with blog_org_scope(staff_org):
            category = Category.objects.create(
                name="Automation", organization=staff_org
            )
        _login_with_org(client, staff_user)

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

        with blog_org_scope(staff_org):
            post = Post.all_objects.get(slug="automated-post")
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
        staff_org,
        tmp_path,
        settings,
        blog_org_scope,
    ):
        """Test publish API can attach a previously uploaded media asset."""
        settings.MEDIA_ROOT = str(tmp_path)
        with blog_org_scope(staff_org):
            asset = BlogMediaAsset.objects.create(
                file=make_uploaded_test_image(filename="featured.png"),
                alt="Generated cover image",
                kind=BlogMediaAsset.Kind.FEATURED,
                original_filename="featured.png",
                width=1200,
                height=800,
                uploaded_by=staff_user,
                organization=staff_org,
            )
        _login_with_org(client, staff_user)

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
        with blog_org_scope(staff_org):
            post = Post.all_objects.get(slug="featured-asset-post")
            assert post.featured_image.name == asset.file.name
            assert post.featured_image_alt == "Generated cover image"

    def test_publish_post_api_unknown_featured_image_returns_400(
        self,
        client,
        staff_user,
        staff_org,
    ):
        """Test publish API validates the uploaded featured image reference."""
        _login_with_org(client, staff_user)

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
        assert _error(response)["fields"] == {
            "featured_image_id": ["Media asset not found"]
        }

    def test_publish_post_api_featured_image_alt_requires_image(
        self,
        client,
        staff_user,
    ):
        """Test publish API rejects a featured image alt without an image."""
        _login_with_org(client, staff_user)

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
        assert _error(response)["fields"] == {
            "featured_image_alt": ["featured_image_alt requires featured_image_id"]
        }

    def test_publish_post_api_duplicate_slug_returns_409(
        self, client, staff_user, staff_org, blog_org_scope
    ):
        """Test API handles duplicate generated slug as conflict"""
        with blog_org_scope(staff_org):
            Post.objects.create(
                title="Duplicate Title",
                content="Existing content",
                status="published",
                author=staff_user,
                organization=staff_org,
            )
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "Duplicate Title", "content": "New content"}),
            content_type="application/json",
        )

        assert response.status_code == 409
        error = _error(response)
        assert error["code"] == "post_conflict"
        assert error["message"] == "Post already exists for generated slug"

    def test_publish_post_api_invalid_tags_returns_400(self, client, staff_user):
        """Test API validates tags payload type"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "API Post", "content": "Body", "tags": "bad"}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["fields"] == {"tags": ["Must be a list of strings"]}

    def test_publish_post_api_non_sluggable_tag_returns_400(self, client, staff_user):
        """Test API validates tags can generate usable slugs"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "API Post", "content": "Body", "tags": ["!!!"]}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["fields"] == {
            "tags": ["Each tag must include at least one letter or number"]
        }

    def test_publish_post_api_non_string_tag_value_returns_400(
        self, client, staff_user
    ):
        """Test API validates each tag value type"""
        _login_with_org(client, staff_user)

        response = client.post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "API Post", "content": "Body", "tags": [1]}),
            content_type="application/json",
        )

        assert response.status_code == 400
        assert _error(response)["fields"] == {
            "tags": ["Must be a list of non-empty strings"]
        }

    def test_publish_post_api_unexpected_integrity_error_returns_500(
        self,
        client,
        staff_user,
    ):
        """Test API returns server error for non-conflict integrity failures"""
        _login_with_org(client, staff_user)

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
        error = _error(response)
        assert error["code"] == "publish_failed"
        assert error["message"] == "Unable to publish post"

    def test_publish_post_api_conflict_detected_after_race_returns_409(
        self,
        client,
        staff_user,
    ):
        """Test API maps race-condition slug conflicts to conflict response"""
        _login_with_org(client, staff_user)

        initial_slug_lookup = MagicMock()
        initial_slug_lookup.exists.return_value = False
        race_check_slug_lookup = MagicMock()
        race_check_slug_lookup.exists.return_value = True

        with (
            patch(
                "quickscale_modules_blog.views.Post.all_objects.filter",
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
        assert _error(response)["code"] == "post_conflict"

    def test_publish_post_api_creates_missing_tags(
        self, client, staff_user, staff_org, blog_org_scope
    ):
        """Test API creates new tags when they do not exist"""
        _login_with_org(client, staff_user)
        with blog_org_scope(staff_org):
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
        with blog_org_scope(staff_org):
            assert Tag.all_objects.filter(slug="launch", name="Launch").exists()
            # Tag should be created in the user's personal org
            tag = Tag.all_objects.get(slug="launch")
            assert tag.organization is not None

    # ------------------------------------------------------------------
    # Throttling (Module Conventions rule 32)
    # ------------------------------------------------------------------

    def test_blog_api_throttle_scope_carries_the_module_stem(self):
        """The scope is the stemmed DRF scope rule 32 requires."""
        assert BlogApiThrottle.scope == BLOG_API_SCOPE

    def test_blog_api_rate_limit_comes_from_the_setting(
        self,
        client,
        staff_user,
    ):
        """The configured rate bounds authenticated writes through DRF."""
        _login_with_org(client, staff_user)

        with blog_api_rate("1/hour"):
            first_response = client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "Rate Post One", "content": "Body"}),
                content_type="application/json",
            )
            second_response = client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "Rate Post Two", "content": "Body"}),
                content_type="application/json",
            )

        assert first_response.status_code == 201
        assert second_response.status_code == 429
        error = _error(second_response)
        assert error["code"] == "throttled"
        assert int(second_response["Retry-After"]) > 0

    def test_blog_api_throttle_uses_remote_addr_by_default(
        self,
        client,
        staff_user,
        staff_org,
        blog_org_scope,
    ):
        """A spoofed X-Forwarded-For cannot split the throttle bucket by default."""
        _login_with_org(client, staff_user)

        with blog_api_rate("1/hour"):
            first_response = client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "Rate Post One", "content": "Body"}),
                content_type="application/json",
                HTTP_X_FORWARDED_FOR="198.51.100.10",
                REMOTE_ADDR="10.0.0.8",
            )
            second_response = client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "Rate Post Two", "content": "Body"}),
                content_type="application/json",
                HTTP_X_FORWARDED_FOR="198.51.100.11",
                REMOTE_ADDR="10.0.0.8",
            )

        assert first_response.status_code == 201
        assert second_response.status_code == 429
        with blog_org_scope(staff_org):
            assert Post.objects.filter(slug="rate-post-two").count() == 0

    def test_blog_api_throttle_uses_xff_when_configured(
        self,
        client,
        staff_user,
    ):
        """Configured proxy trust gives each forwarded client its own bucket."""
        _login_with_org(client, staff_user)

        with blog_api_rate("1/hour"):
            with override_settings(
                USE_X_FORWARDED_FOR=True,
                TRUSTED_PROXY_COUNT=1,
            ):
                first_response = client.post(
                    reverse("quickscale_blog:api_publish_post"),
                    data=json.dumps({"title": "Xff Post One", "content": "Body"}),
                    content_type="application/json",
                    HTTP_X_FORWARDED_FOR="198.51.100.10",
                    REMOTE_ADDR="10.0.0.8",
                )
                second_response = client.post(
                    reverse("quickscale_blog:api_publish_post"),
                    data=json.dumps({"title": "Xff Post Two", "content": "Body"}),
                    content_type="application/json",
                    HTTP_X_FORWARDED_FOR="198.51.100.11",
                    REMOTE_ADDR="10.0.0.9",
                )
                third_response = client.post(
                    reverse("quickscale_blog:api_publish_post"),
                    data=json.dumps({"title": "Xff Post Three", "content": "Body"}),
                    content_type="application/json",
                    HTTP_X_FORWARDED_FOR="198.51.100.10",
                    REMOTE_ADDR="10.0.0.8",
                )

        assert first_response.status_code == 201
        assert second_response.status_code == 201, (
            "Different X-Forwarded-For values should get independent buckets "
            "when USE_X_FORWARDED_FOR is enabled"
        )
        assert third_response.status_code == 429

    @pytest.mark.parametrize("use_xff,proxy_count,xff", BLOG_CLIENT_IP_CASES)
    def test_blog_throttle_ident_matches_direct_resolver(
        self,
        rf,
        use_xff: bool,
        proxy_count: int,
        xff: str | None,
    ) -> None:
        """The throttle client identity is the shared proxy-aware resolver value."""
        request_kwargs: dict[str, str] = {"REMOTE_ADDR": "10.0.0.1"}
        if xff is not None:
            request_kwargs["HTTP_X_FORWARDED_FOR"] = xff
        request = rf.post("/blog/api/publish/", **request_kwargs)

        with override_settings(
            USE_X_FORWARDED_FOR=use_xff,
            TRUSTED_PROXY_COUNT=proxy_count,
        ):
            assert BlogApiThrottle().get_ident(request) == get_client_ip(request)

    @pytest.mark.parametrize("setting_name,setting_value", BLOG_INVALID_PROXY_SETTINGS)
    def test_publish_post_api_invalid_proxy_settings_fail_loud_without_mutation(
        self,
        client,
        settings,
        staff_user,
        staff_org,
        blog_org_scope,
        setting_name: str,
        setting_value: object,
    ) -> None:
        """Invalid proxy trust settings raise before any post is written."""
        _login_with_org(client, staff_user)
        settings_values: dict[str, object] = {
            "USE_X_FORWARDED_FOR": False,
            "TRUSTED_PROXY_COUNT": 1,
        }
        missing_setting: str | None = None
        if setting_value is _MISSING:
            missing_setting = setting_name
        else:
            settings_values[setting_name] = setting_value

        with blog_org_scope(staff_org):
            initial_count = Post.all_objects.filter(slug="invalid-proxy-post").count()

        with override_settings(**settings_values):
            if missing_setting is not None:
                delattr(settings, missing_setting)
            with pytest.raises(ImproperlyConfigured) as endpoint_error:
                client.post(
                    reverse("quickscale_blog:api_publish_post"),
                    data=json.dumps({"title": "Invalid Proxy Post", "content": "Body"}),
                    content_type="application/json",
                    REMOTE_ADDR="10.0.0.1",
                    HTTP_X_FORWARDED_FOR="198.51.100.1",
                )

            assert setting_name in str(endpoint_error.value)

        with blog_org_scope(staff_org):
            assert Post.all_objects.filter(slug="invalid-proxy-post").count() == (
                initial_count
            )

    def test_publish_post_api_missing_csrf_still_returns_403_when_rate_limited(
        self,
        staff_user,
    ):
        """CSRF enforcement runs ahead of throttling for session requests."""
        warm_client = Client()
        csrf_client = Client(enforce_csrf_checks=True)
        _login_with_org(warm_client, staff_user)
        _login_with_org(csrf_client, staff_user)

        with blog_api_rate("1/hour"):
            warm_response = warm_client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "Warm Post", "content": "Body"}),
                content_type="application/json",
            )
            csrf_response = csrf_client.post(
                reverse("quickscale_blog:api_publish_post"),
                data=json.dumps({"title": "Blocked Post", "content": "Body"}),
                content_type="application/json",
            )

        assert warm_response.status_code == 201
        assert csrf_response.status_code == 403

    # ------------------------------------------------------------------
    # ContextVar lifecycle restoration tests
    # ------------------------------------------------------------------

    def test_publish_post_api_system_fallback_restores_prior_context(
        self,
        rf,
        staff_org,
        system_org,
        blog_org_scope,
    ):
        """A user without a personal org falls back to the System org and
        restores the prior ContextVar through the shared org scope.

        Runs under an explicit outer ``transaction.atomic()``, asserts both
        the Python ContextVar and the PostgreSQL GUC return to the exact
        prior (None), and proves the next wrapped tenant query re-primes
        with a fresh ``SET LOCAL`` (memo was invalidated).
        """
        from django.db import transaction

        from quickscale_modules_orgs.current_org import get_current_org_id

        User = get_user_model()
        fallback_user = User.objects.create_user(
            username="sysfallback",
            email="sysfallback@example.com",
            password="pass",
            is_staff=True,
        )
        # No personal org → System org fallback in _resolve_api_org.
        request = APIRequestFactory().post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "System Fallback", "content": "Body"}),
            content_type="application/json",
        )
        force_authenticate(request, user=fallback_user)

        with transaction.atomic():
            response = PostPublishAPIView.as_view()(request)

            assert get_current_org_id() is None, (
                "ContextVar should be restored after the request completes"
            )
            _assert_org_context_restored_to_none(system_org)

        assert response.status_code == 201

        # Readback: post should belong to System org (fallback)
        with blog_org_scope(system_org):
            post = Post.all_objects.get(slug="system-fallback")
            assert post.organization == system_org

    def test_publish_post_api_handled_error_restores_prior_context(
        self,
        staff_user,
        system_org,
    ):
        """A handled publish error (400) restores the prior org context.

        Uses a direct ``APIRequestFactory`` call so there is no middleware
        org context to reset the prior: the view resolves and primes the org
        for the write, and on a handled validation error restores the
        ContextVar and GUC to the fail-closed default and clears the priming
        memo.
        """
        from django.db import transaction

        from quickscale_modules_orgs.current_org import get_current_org_id

        request = APIRequestFactory().post(
            reverse("quickscale_blog:api_publish_post"),
            data=json.dumps({"title": "!!!", "content": "Body"}),
            content_type="application/json",
        )
        force_authenticate(request, user=staff_user)

        with transaction.atomic():
            response = PostPublishAPIView.as_view()(request)

            assert get_current_org_id() is None, (
                "ContextVar should be restored after a handled error"
            )
            _assert_org_context_restored_to_none(system_org)

        assert response.status_code == 400


@pytest.mark.django_db
class TestUploadMediaApi:
    """Tests for blog media upload API."""

    def test_build_media_response_url_without_storage_uses_media_url(
        self,
        rf,
        settings,
    ):
        """Without storage, the fallback uses MEDIA_URL and reads no storage setting."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"
        settings.MEDIA_URL = "/media/"

        request = rf.get(reverse("quickscale_blog:api_upload_media"))

        with without_storage_services(True):
            assert (
                _build_media_response_url(
                    request, "blog/uploads/2026/03/hero-image.png"
                )
                == "http://testserver/media/blog/uploads/2026/03/hero-image.png"
            )

    def test_build_media_response_url_without_storage_preserves_absolute_reference(
        self,
        rf,
    ):
        """Fallback URL builder should return already-absolute references unchanged."""
        request = rf.get(reverse("quickscale_blog:api_upload_media"))
        absolute_url = "https://cdn.example.com/blog/uploads/2026/03/hero-image.png"

        with without_storage_services(True):
            assert _build_media_response_url(request, absolute_url) == absolute_url

    def test_build_media_response_url_without_storage_normalizes_relative_media_url(
        self,
        rf,
        settings,
    ):
        """Fallback URL builder should normalize relative `MEDIA_URL` prefixes."""
        settings.MEDIA_URL = "media"

        request = rf.get(reverse("quickscale_blog:api_upload_media"))

        with without_storage_services(True):
            assert (
                _build_media_response_url(
                    request, "blog/uploads/2026/03/hero-image.png"
                )
                == "http://testserver/media/blog/uploads/2026/03/hero-image.png"
            )

    def test_build_media_response_url_without_storage_uses_leading_slash_path(
        self,
        rf,
    ):
        """Fallback URL builder should preserve leading-slash media references."""
        request = rf.get(reverse("quickscale_blog:api_upload_media"))

        with without_storage_services(True):
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
        assert _error(response)["code"] == "not_authenticated"

    def test_upload_media_api_non_staff_returns_403(self, client, user):
        """Test media uploads require staff access."""
        _login_with_org(client, user)

        response = client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image()},
        )

        assert response.status_code == 403
        assert _error(response)["message"] == "Staff access required"

    def test_upload_media_api_missing_csrf_returns_403(self, staff_user):
        """Test session-authenticated media uploads enforce CSRF protection."""
        csrf_client = Client(enforce_csrf_checks=True)
        _login_with_org(csrf_client, staff_user)

        response = csrf_client.post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image()},
        )

        assert response.status_code == 403

    @pytest.mark.parametrize("storage_missing", STORAGE_PATHS)
    def test_upload_media_api_valid_png_returns_metadata(
        self,
        client,
        staff_user,
        staff_org,
        tmp_path,
        settings,
        storage_missing,
        blog_org_scope,
    ):
        """Test upload API stores the file and returns stable metadata."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.BLOG_API_UPLOAD_MAX_WIDTH = 1600
        settings.BLOG_API_UPLOAD_MAX_HEIGHT = 900
        _login_with_org(client, staff_user)

        with without_storage_services(storage_missing):
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
        with blog_org_scope(staff_org):
            asset = BlogMediaAsset.all_objects.get(pk=payload["id"])
            # Media asset should be stamped with the user's personal org
            assert asset.organization is not None

    @pytest.mark.parametrize("storage_missing", STORAGE_PATHS)
    def test_upload_media_api_rejects_excessive_width_with_or_without_helper(
        self,
        client,
        staff_user,
        settings,
        storage_missing,
    ):
        """Upload API should apply the same width ceiling in both validation paths."""
        settings.BLOG_API_UPLOAD_MAX_WIDTH = 1600
        settings.BLOG_API_UPLOAD_MAX_HEIGHT = 900
        _login_with_org(client, staff_user)

        with without_storage_services(storage_missing):
            response = client.post(
                reverse("quickscale_blog:api_upload_media"),
                data={"file": make_uploaded_test_image(size=(1601, 900))},
            )

        assert response.status_code == 400
        assert _error(response)["fields"] == {
            "file": ["Image width exceeds maximum of 1600 pixels"]
        }

    @pytest.mark.parametrize("storage_missing", STORAGE_PATHS)
    def test_upload_media_api_rejects_excessive_height_with_or_without_helper(
        self,
        client,
        staff_user,
        settings,
        storage_missing,
    ):
        """Upload API should apply the same height ceiling in both validation paths."""
        settings.BLOG_API_UPLOAD_MAX_WIDTH = 1600
        settings.BLOG_API_UPLOAD_MAX_HEIGHT = 900
        _login_with_org(client, staff_user)

        with without_storage_services(storage_missing):
            response = client.post(
                reverse("quickscale_blog:api_upload_media"),
                data={"file": make_uploaded_test_image(size=(1600, 901))},
            )

        assert response.status_code == 400
        assert _error(response)["fields"] == {
            "file": ["Image height exceeds maximum of 900 pixels"]
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
        _login_with_org(client, staff_user)

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
        _login_with_org(client, staff_user)

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
        _login_with_org(client, staff_user)

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

    def test_build_media_response_url_uses_local_media_url_when_public_base_url_is_unset(
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
        _login_with_org(client, staff_user)
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
        assert _error(response)["fields"] == {
            "file": ["Unsupported or invalid image file"]
        }

    @pytest.mark.parametrize(
        ("storage_missing", "image_open_target"),
        DECOMPRESSION_BOMB_PATHS,
    )
    def test_upload_media_api_rejects_decompression_bombs_with_or_without_helper(
        self,
        client,
        staff_user,
        settings,
        storage_missing,
        image_open_target,
    ):
        """Upload API should normalize Pillow bomb protection failures in both paths."""
        _login_with_org(client, staff_user)

        with (
            without_storage_services(storage_missing),
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
        assert _error(response)["fields"] == {
            "file": ["Image exceeds safe pixel limit"]
        }

    # ------------------------------------------------------------------
    # ContextVar lifecycle restoration tests
    # ------------------------------------------------------------------

    def test_upload_media_api_success_restores_prior_context(
        self,
        staff_user,
        staff_org,
        tmp_path,
        system_org,
        settings,
        blog_org_scope,
    ):
        """Upload success restores the exact non-None prior ContextVar and GUC.

        Uses a direct ``APIRequestFactory`` call so there is no middleware to
        reset the prior: the test pre-primes the ContextVar and GUC to a
        distinct org, invokes the view, then asserts both equal that exact
        prior (proving the shared org scope restores a non-None value), and
        finally proves the next wrapped tenant query re-primes freshly.
        """
        from django.db import connection, transaction
        from django.test.utils import CaptureQueriesContext

        from quickscale_modules_orgs.current_org import (
            get_current_org_id,
            set_current_org_id,
        )
        from quickscale_modules_orgs.models import Organization

        prior_org = Organization.objects.create(name="Prior Org", slug="prior-org")
        distinct_prior = prior_org.pk

        settings.MEDIA_ROOT = str(tmp_path)

        request = APIRequestFactory().post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": make_uploaded_test_image()},
            format="multipart",
        )
        force_authenticate(request, user=staff_user)

        with transaction.atomic():
            set_current_org_id(distinct_prior)
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")

            response = MediaUploadAPIView.as_view()(request)

            # ContextVar restored to the pre-primed distinct prior.
            assert get_current_org_id() == distinct_prior, (
                f"Expected ContextVar = {distinct_prior} (pre-primed prior), "
                f"got {get_current_org_id()!r}"
            )
            # GUC restored to match the pre-primed prior.  Temporarily clear
            # the ContextVar so the execute wrapper cannot re-prime the GUC
            # (masking its actual value) before the raw read.
            prior_var = get_current_org_id()
            set_current_org_id(None)
            try:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT current_setting('app.current_org_id', true)")
                    (raw_guc,) = cursor.fetchone()
            finally:
                set_current_org_id(prior_var)
            assert raw_guc == str(distinct_prior), (
                f"Expected GUC = {distinct_prior} (restored prior), got {raw_guc!r}"
            )

            # Switch to a different intended org and prove fresh SET LOCAL.
            with CaptureQueriesContext(connection) as captured:
                set_current_org_id(system_org.pk)
                try:
                    with connection.cursor() as cursor:
                        cursor.execute(
                            "SELECT current_setting('app.current_org_id', true)"
                        )
                        (switched_guc,) = cursor.fetchone()
                finally:
                    set_current_org_id(None)

            assert switched_guc == str(system_org.pk), (
                f"Expected GUC = {system_org.pk} after fresh SET LOCAL, "
                f"got {switched_guc!r}"
            )
            set_local_count = sum(
                1 for q in captured.captured_queries if "SET LOCAL" in q["sql"]
            )
            assert set_local_count == 1, (
                f"Expected 1 SET LOCAL after upload success memo-clear, "
                f"got {set_local_count}"
            )

        assert response.status_code == 201

        # Readback: media asset should be stored with the user's org
        with blog_org_scope(staff_org):
            payload = response.data
            asset = BlogMediaAsset.all_objects.get(pk=payload["id"])
            assert asset.organization is not None

    def test_upload_media_api_handled_error_restores_prior_context(
        self,
        staff_user,
        system_org,
    ):
        """Upload handled error (400) restores the prior org context.

        Uses a direct ``APIRequestFactory`` call so there is no middleware
        org context to reset the prior, then asserts both the Python
        ContextVar and the PostgreSQL GUC return to the fail-closed default
        and the next wrapped tenant query re-primes with a fresh
        ``SET LOCAL`` (memo was invalidated).
        """
        from django.db import transaction

        from quickscale_modules_orgs.current_org import get_current_org_id

        bad_file = SimpleUploadedFile(
            "notes.txt",
            b"not an image",
            content_type="text/plain",
        )
        request = APIRequestFactory().post(
            reverse("quickscale_blog:api_upload_media"),
            data={"file": bad_file},
            format="multipart",
        )
        force_authenticate(request, user=staff_user)

        with transaction.atomic():
            response = MediaUploadAPIView.as_view()(request)

            assert get_current_org_id() is None, (
                "ContextVar should be restored after upload handled error"
            )
            _assert_org_context_restored_to_none(system_org)

        assert response.status_code == 400
