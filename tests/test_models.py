"""Tests for blog models"""

import os

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from quickscale_modules_blog.models import AuthorProfile, Category, Post, Tag

User = get_user_model()


@pytest.mark.django_db
class TestCategory:
    """Tests for Category model"""

    def test_category_creation(self):
        """Test creating a category"""
        category = Category.objects.create(
            name="Technology",
            description="Tech posts",
        )
        assert category.name == "Technology"
        assert category.slug == "technology"
        assert str(category) == "Technology"

    def test_category_auto_slug(self):
        """Test automatic slug generation"""
        category = Category.objects.create(name="Web Development")
        assert category.slug == "web-development"

    def test_category_get_absolute_url(self):
        """Test category URL generation"""
        category = Category.objects.create(name="Python")
        url = category.get_absolute_url()
        assert "/category/python/" in url


@pytest.mark.django_db
class TestTag:
    """Tests for Tag model"""

    def test_tag_creation(self):
        """Test creating a tag"""
        tag = Tag.objects.create(name="Django")
        assert tag.name == "Django"
        assert tag.slug == "django"
        assert str(tag) == "Django"

    def test_tag_auto_slug(self):
        """Test automatic slug generation"""
        tag = Tag.objects.create(name="Machine Learning")
        assert tag.slug == "machine-learning"

    def test_tag_get_absolute_url(self):
        """Test tag URL generation"""
        tag = Tag.objects.create(name="Python")
        url = tag.get_absolute_url()
        assert "/tag/python/" in url


@pytest.mark.django_db
class TestAuthorProfile:
    """Tests for AuthorProfile model"""

    def test_author_profile_creation(self, user):
        """Test creating an author profile"""
        profile = AuthorProfile.objects.create(
            user=user,
            bio="Test author bio",
        )
        assert profile.user == user
        assert profile.bio == "Test author bio"
        assert str(profile) == f"{user.username} - Author Profile"


@pytest.mark.django_db
class TestPost:
    """Tests for Post model"""

    def test_post_creation(self, author_user):
        """Test creating a blog post"""
        post = Post.objects.create(
            title="Test Post",
            author=author_user,
            content="# Test Content\n\nThis is a test post.",
            status="draft",
        )
        assert post.title == "Test Post"
        assert post.slug == "test-post"
        assert post.author == author_user
        assert post.status == "draft"
        assert str(post) == "Test Post"

    def test_post_auto_slug(self, author_user):
        """Test automatic slug generation"""
        post = Post.objects.create(
            title="My Awesome Blog Post",
            author=author_user,
            content="Content here",
        )
        assert post.slug == "my-awesome-blog-post"

    def test_post_auto_excerpt(self, author_user):
        """Test automatic excerpt generation"""
        long_content = "A" * 500  # 500 characters
        post = Post.objects.create(
            title="Test",
            author=author_user,
            content=long_content,
        )
        assert len(post.excerpt) <= 303  # 300 + "..."
        assert post.excerpt.endswith("...")

    def test_post_manual_excerpt(self, author_user):
        """Test manual excerpt"""
        post = Post.objects.create(
            title="Test",
            author=author_user,
            content="Long content here",
            excerpt="Custom excerpt",
        )
        assert post.excerpt == "Custom excerpt"

    def test_post_published_date_auto_set(self, author_user):
        """Test published_date is set when status changes to published"""
        post = Post.objects.create(
            title="Test",
            author=author_user,
            content="Content",
            status="draft",
        )
        assert post.published_date is None

        post.status = "published"
        post.save()
        assert post.published_date is not None

    def test_post_with_category_and_tags(self, author_user):
        """Test post with category and tags"""
        category = Category.objects.create(name="Tech")
        tag1 = Tag.objects.create(name="Python")
        tag2 = Tag.objects.create(name="Django")

        post = Post.objects.create(
            title="Test",
            author=author_user,
            content="Content",
            category=category,
        )
        post.tags.add(tag1, tag2)

        assert post.category == category
        assert post.tags.count() == 2
        assert tag1 in post.tags.all()
        assert tag2 in post.tags.all()

    def test_post_get_absolute_url(self, author_user):
        """Test post URL generation"""
        post = Post.objects.create(
            title="Test Post",
            author=author_user,
            content="Content",
        )
        url = post.get_absolute_url()
        assert "/post/test-post/" in url

    def test_post_short_content_no_ellipsis(self, author_user):
        """Test excerpt for short content has no ellipsis"""
        post = Post.objects.create(
            title="Short",
            author=author_user,
            content="Short content",
        )
        assert post.excerpt == "Short content"
        assert not post.excerpt.endswith("...")

    def test_post_save_with_featured_image(self, author_user, tmp_path, settings):
        """Test saving a post with a featured image triggers thumbnail generation"""
        settings.MEDIA_ROOT = str(tmp_path)

        # Create a test image
        img_dir = tmp_path / "blog" / "images"
        img_dir.mkdir(parents=True)
        img_path = img_dir / "test.jpg"
        img = Image.new("RGB", (1200, 800), color="red")
        img.save(str(img_path), format="JPEG")

        # Create post with featured image
        with open(str(img_path), "rb") as f:
            image_file = SimpleUploadedFile(
                "test.jpg", f.read(), content_type="image/jpeg"
            )
        post = Post.objects.create(
            title="Image Post",
            author=author_user,
            content="Content with image",
            featured_image=image_file,
        )

        # Verify thumbnails were generated
        image_dir = os.path.dirname(post.featured_image.path)
        thumb_dir = os.path.join(image_dir, "thumbnails")
        assert os.path.isdir(thumb_dir)

        # Check both small and medium thumbnails exist
        assert any("small" in f for f in os.listdir(thumb_dir))
        assert any("medium" in f for f in os.listdir(thumb_dir))

    def test_get_thumbnail_url_with_image(self, author_user, tmp_path, settings):
        """Test get_thumbnail_url returns correct URL when image exists"""
        settings.MEDIA_ROOT = str(tmp_path)

        img_dir = tmp_path / "blog" / "images"
        img_dir.mkdir(parents=True)
        img_path = img_dir / "thumb_test.jpg"
        img = Image.new("RGB", (1200, 800), color="blue")
        img.save(str(img_path), format="JPEG")

        with open(str(img_path), "rb") as f:
            image_file = SimpleUploadedFile(
                "thumb_test.jpg", f.read(), content_type="image/jpeg"
            )
        post = Post.objects.create(
            title="Thumbnail Post",
            author=author_user,
            content="Content",
            featured_image=image_file,
        )

        medium_url = post.get_thumbnail_url("medium")
        assert "thumbnails" in medium_url
        assert "medium" in medium_url

        small_url = post.get_thumbnail_url("small")
        assert "thumbnails" in small_url
        assert "small" in small_url

    def test_get_thumbnail_url_without_image(self, author_user):
        """Test get_thumbnail_url returns empty string when no image"""
        post = Post.objects.create(
            title="No Image Post",
            author=author_user,
            content="Content",
        )
        assert post.get_thumbnail_url() == ""
        assert post.get_thumbnail_url("small") == ""
