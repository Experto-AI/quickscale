"""Tests for blog URLs

Phase 2 (F11.11) adds additive org-scoped URL name assertions alongside
the existing flat path tests.
"""

from contextlib import contextmanager
from importlib import reload

import pytest
from django.urls import NoReverseMatch, clear_url_caches, reverse, set_urlconf


@contextmanager
def _reloaded_blog_test_urlconf():
    from . import urls as test_urls
    from quickscale_modules_blog import urls as blog_urls

    clear_url_caches()
    set_urlconf(None)
    reload(blog_urls)
    reload(test_urls)
    try:
        yield
    finally:
        clear_url_caches()
        set_urlconf(None)
        reload(blog_urls)
        reload(test_urls)


class TestBlogUrls:
    """Tests for blog URL configuration"""

    def test_post_list_url(self):
        """Test post list URL resolves correctly"""
        url = reverse("quickscale_blog:post_list")
        assert url == "/blog/"

    def test_post_detail_url(self):
        """Test post detail URL resolves correctly"""
        url = reverse("quickscale_blog:post_detail", args=["test-slug"])
        assert url == "/blog/post/test-slug/"

    def test_publish_api_url(self):
        """Test publish API URL resolves correctly"""
        url = reverse("quickscale_blog:api_publish_post")
        assert url == "/blog/api/publish/"

    def test_category_list_url(self):
        """Test category list URL resolves correctly"""
        url = reverse("quickscale_blog:category_list", args=["tech"])
        assert url == "/blog/category/tech/"

    def test_tag_list_url(self):
        """Test tag list URL resolves correctly"""
        url = reverse("quickscale_blog:tag_list", args=["python"])
        assert url == "/blog/tag/python/"

    @pytest.mark.parametrize(
        "configured_value",
        [None, True, "true", "yes", "1", "on"],
    )
    def test_feed_url(self, settings, configured_value):
        """Test RSS feed URL resolves correctly when enabled or unset."""
        if configured_value is None:
            if hasattr(settings, "BLOG_ENABLE_RSS"):
                delattr(settings, "BLOG_ENABLE_RSS")
        else:
            settings.BLOG_ENABLE_RSS = configured_value

        with _reloaded_blog_test_urlconf():
            url = reverse("quickscale_blog:feed")
            assert url == "/blog/feed/"

    @pytest.mark.parametrize(
        "configured_value",
        [False, "false", "no", "0", "off"],
    )
    def test_feed_url_omitted_when_rss_disabled(self, settings, configured_value):
        """Test RSS feed URL is omitted from the URLconf when disabled."""
        settings.BLOG_ENABLE_RSS = configured_value

        with _reloaded_blog_test_urlconf():
            with pytest.raises(NoReverseMatch):
                reverse("quickscale_blog:feed")


# ---------------------------------------------------------------------------
# Phase 2 (F11.11) — org-scoped URL name resolution tests
# ---------------------------------------------------------------------------


class TestOrgScopedBlogUrls:
    """Tests for org-scoped blog URL configuration (additive Phase 2)"""

    def test_org_post_list_url(self):
        """Test org-scoped post list URL resolves correctly"""
        url = reverse("quickscale_blog:org-post_list", kwargs={"org_slug": "my-org"})
        assert url == "/orgs/my-org/blog/"

    def test_org_post_detail_url(self):
        """Test org-scoped post detail URL resolves correctly"""
        url = reverse(
            "quickscale_blog:org-post_detail",
            kwargs={"org_slug": "my-org", "slug": "test-slug"},
        )
        assert url == "/orgs/my-org/blog/post/test-slug/"

    def test_org_publish_api_url(self):
        """Test org-scoped publish API URL resolves correctly"""
        url = reverse(
            "quickscale_blog:org-api_publish_post",
            kwargs={"org_slug": "my-org"},
        )
        assert url == "/orgs/my-org/blog/api/publish/"

    def test_org_media_api_url(self):
        """Test org-scoped media upload API URL resolves correctly"""
        url = reverse(
            "quickscale_blog:org-api_upload_media",
            kwargs={"org_slug": "my-org"},
        )
        assert url == "/orgs/my-org/blog/api/media/"

    def test_org_category_list_url(self):
        """Test org-scoped category list URL resolves correctly"""
        url = reverse(
            "quickscale_blog:org-category_list",
            kwargs={"org_slug": "my-org", "slug": "tech"},
        )
        assert url == "/orgs/my-org/blog/category/tech/"

    def test_org_tag_list_url(self):
        """Test org-scoped tag list URL resolves correctly"""
        url = reverse(
            "quickscale_blog:org-tag_list",
            kwargs={"org_slug": "my-org", "slug": "python"},
        )
        assert url == "/orgs/my-org/blog/tag/python/"

    @pytest.mark.parametrize(
        "configured_value",
        [None, True, "true", "yes", "1", "on"],
    )
    def test_org_feed_url(self, settings, configured_value):
        """Test org-scoped RSS feed URL resolves correctly when enabled."""
        if configured_value is None:
            if hasattr(settings, "BLOG_ENABLE_RSS"):
                delattr(settings, "BLOG_ENABLE_RSS")
        else:
            settings.BLOG_ENABLE_RSS = configured_value

        with _reloaded_blog_test_urlconf():
            url = reverse(
                "quickscale_blog:org-feed",
                kwargs={"org_slug": "my-org"},
            )
            assert url == "/orgs/my-org/blog/feed/"

    @pytest.mark.parametrize(
        "configured_value",
        [False, "false", "no", "0", "off"],
    )
    def test_org_feed_url_omitted_when_rss_disabled(self, settings, configured_value):
        """Test org-scoped RSS feed URL is omitted when RSS disabled."""
        settings.BLOG_ENABLE_RSS = configured_value

        with _reloaded_blog_test_urlconf():
            with pytest.raises(NoReverseMatch):
                reverse(
                    "quickscale_blog:org-feed",
                    kwargs={"org_slug": "my-org"},
                )
