"""Tests for blog views"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from PIL import Image
from quickscale_modules_blog.models import Category, Post, Tag


@pytest.mark.django_db
class TestPostListView:
    """Tests for PostListView"""

    def test_post_list_view(self, client, author_user):
        """Test post list displays published posts"""
        Post.objects.create(
            title="Published Post",
            author=author_user,
            content="Content",
            status="published",
        )
        Post.objects.create(
            title="Draft Post",
            author=author_user,
            content="Content",
            status="draft",
        )

        response = client.get(reverse("quickscale_blog:post_list"))
        assert response.status_code == 200
        assert "Published Post" in str(response.content)
        assert "Draft Post" not in str(response.content)


@pytest.mark.django_db
class TestPostDetailView:
    """Tests for PostDetailView"""

    def test_post_detail_view(self, client, author_user):
        """Test post detail view"""
        post = Post.objects.create(
            title="Test Post",
            author=author_user,
            content="Test content",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))
        assert response.status_code == 200
        assert "Test Post" in str(response.content)

    def test_post_detail_draft_not_found(self, client, author_user):
        """Test that draft posts return 404"""
        post = Post.objects.create(
            title="Draft Post",
            author=author_user,
            content="Draft content",
            status="draft",
        )
        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))
        assert response.status_code == 404

    def test_post_detail_styling_hooks_present_when_rendered(self, client, author_user):
        """Test post detail includes markdown wrapper and module stylesheet"""
        post = Post.objects.create(
            title="Styled Post",
            author=author_user,
            content="# Heading\n\nStyled content",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert 'class="blog-markdown-content"' in html
        assert "quickscale_modules_blog/blog.css" in html

    def test_post_detail_escapes_inline_html_in_markdown(self, client, author_user):
        """Test markdown rendering escapes raw HTML from post content"""
        post = Post.objects.create(
            title="Unsafe Post",
            author=author_user,
            content="# Heading\n\n<script>alert('xss')</script>",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert "<script>alert('xss')</script>" not in html
        assert "&lt;script&gt;alert(&#x27;xss&#x27;)&lt;/script&gt;" in html

    def test_post_detail_renders_markdown_image_links(self, client, author_user):
        """Test markdown image syntax renders inline images from uploaded URLs."""
        post = Post.objects.create(
            title="Image Markdown Post",
            author=author_user,
            content="![Diagram](https://cdn.example.com/blog/diagram.png)",
            status="published",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert (
            '<img alt="Diagram" src="https://cdn.example.com/blog/diagram.png"' in html
        )

    def test_post_detail_renders_featured_image(
        self,
        client,
        author_user,
        tmp_path,
        settings,
    ):
        """Test post detail renders the featured image uploaded via the model field."""
        settings.MEDIA_ROOT = str(tmp_path)

        image = Image.new("RGB", (800, 450), color="purple")
        image_path = tmp_path / "featured.png"
        image.save(str(image_path), format="PNG")

        with open(image_path, "rb") as image_handle:
            uploaded_file = SimpleUploadedFile(
                "featured.png",
                image_handle.read(),
                content_type="image/png",
            )

        post = Post.objects.create(
            title="Featured Image Post",
            author=author_user,
            content="Body",
            status="published",
            featured_image=uploaded_file,
            featured_image_alt="Featured diagram",
        )

        response = client.get(reverse("quickscale_blog:post_detail", args=[post.slug]))

        assert response.status_code == 200
        html = response.content.decode()
        assert "Featured diagram" in html
        assert post.featured_image.url in html


@pytest.mark.django_db
class TestCategoryListView:
    """Tests for CategoryListView"""

    def test_category_list_view(self, client, author_user):
        """Test category list displays published posts in category"""
        category = Category.objects.create(name="Tech")
        Post.objects.create(
            title="Tech Post",
            author=author_user,
            content="Content",
            status="published",
            category=category,
        )
        Post.objects.create(
            title="Draft Tech Post",
            author=author_user,
            content="Content",
            status="draft",
            category=category,
        )

        response = client.get(
            reverse("quickscale_blog:category_list", args=[category.slug])
        )
        assert response.status_code == 200
        assert "Tech Post" in str(response.content)
        assert "Draft Tech Post" not in str(response.content)
        assert response.context["category"] == category

    def test_category_list_view_nonexistent(self, client):
        """Test category list with nonexistent slug raises DoesNotExist"""
        from quickscale_modules_blog.models import Category

        with pytest.raises(Category.DoesNotExist):
            client.get(reverse("quickscale_blog:category_list", args=["nonexistent"]))


@pytest.mark.django_db
class TestTagListView:
    """Tests for TagListView"""

    def test_tag_list_view(self, client, author_user):
        """Test tag list displays published posts with tag"""
        tag = Tag.objects.create(name="Python")
        post = Post.objects.create(
            title="Python Post",
            author=author_user,
            content="Content",
            status="published",
        )
        post.tags.add(tag)

        draft = Post.objects.create(
            title="Draft Python",
            author=author_user,
            content="Content",
            status="draft",
        )
        draft.tags.add(tag)

        response = client.get(reverse("quickscale_blog:tag_list", args=[tag.slug]))
        assert response.status_code == 200
        assert "Python Post" in str(response.content)
        assert "Draft Python" not in str(response.content)
        assert response.context["tag"] == tag

    def test_tag_list_view_nonexistent(self, client):
        """Test tag list with nonexistent slug raises DoesNotExist"""
        from quickscale_modules_blog.models import Tag

        with pytest.raises(Tag.DoesNotExist):
            client.get(reverse("quickscale_blog:tag_list", args=["nonexistent"]))


@pytest.mark.django_db
class TestAuthorlessPostRendering:
    """Tests for rendering pages with authorless posts"""

    def test_authorless_post_omits_author_label_on_all_pages(self, client):
        """Test authorless post omits fallback label across list/detail/category/tag pages"""
        category = Category.objects.create(name="Authorless Category")
        tag = Tag.objects.create(name="Authorless Tag")
        post = Post.objects.create(
            title="Authorless Post",
            author=None,
            content="Authorless content",
            status="published",
            category=category,
        )
        post.tags.add(tag)

        page_urls = [
            reverse("quickscale_blog:post_list"),
            reverse("quickscale_blog:post_detail", args=[post.slug]),
            reverse("quickscale_blog:category_list", args=[category.slug]),
            reverse("quickscale_blog:tag_list", args=[tag.slug]),
        ]

        for url in page_urls:
            response = client.get(url)
            assert response.status_code == 200
            assert "Unknown author" not in response.content.decode()
