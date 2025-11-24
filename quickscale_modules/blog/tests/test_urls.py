"""Tests for blog URLs"""

from django.urls import reverse


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

    def test_category_list_url(self):
        """Test category list URL resolves correctly"""
        url = reverse("quickscale_blog:category_list", args=["tech"])
        assert url == "/blog/category/tech/"

    def test_tag_list_url(self):
        """Test tag list URL resolves correctly"""
        url = reverse("quickscale_blog:tag_list", args=["python"])
        assert url == "/blog/tag/python/"

    def test_feed_url(self):
        """Test RSS feed URL resolves correctly"""
        url = reverse("quickscale_blog:feed")
        assert url == "/blog/feed/"
