"""Tests for blog URLs"""

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
