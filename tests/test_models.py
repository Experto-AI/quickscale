"""Tests for blog models"""

import os
from io import BytesIO
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from quickscale_modules_blog.models import (
    _build_public_media_url,
    _prepare_thumbnail_image,
    _save_format_from_name,
    _thumbnail_save_kwargs,
    AuthorProfile,
    BlogMediaAsset,
    Category,
    Post,
    Tag,
)

User = get_user_model()


class TestModelHelpers:
    """Tests for blog model helper functions."""

    def test_build_public_media_url_returns_empty_for_blank_reference(self, settings):
        """Blank media references should resolve to an empty URL."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = ""
        settings.MEDIA_URL = "/media/"

        assert _build_public_media_url("") == ""

    def test_build_public_media_url_uses_configured_public_base_url(self, settings):
        """Configured CDN/public base URL should take precedence."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"
        settings.MEDIA_URL = "/media/"

        assert (
            _build_public_media_url("blog/images/example.png")
            == "https://cdn.example.com/media/blog/images/example.png"
        )

    def test_build_public_media_url_normalizes_relative_media_url(self, settings):
        """Relative MEDIA_URL values should be normalized into a public path."""
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = ""
        settings.MEDIA_URL = "uploads"

        assert _build_public_media_url("blog/images/example.png") == (
            "/uploads/blog/images/example.png"
        )

    @pytest.mark.parametrize(
        ("file_name", "detected_format", "expected_format"),
        [
            ("example.jpg", None, "JPEG"),
            ("example.jpeg", None, "JPEG"),
            ("example.png", None, "PNG"),
            ("example.webp", None, "WEBP"),
            ("example.gif", None, "GIF"),
            ("example.unknown", None, "JPEG"),
            ("example.bin", "JPG", "JPEG"),
            ("example.bin", "png", "PNG"),
        ],
    )
    def test_save_format_from_name_resolves_supported_formats(
        self,
        file_name,
        detected_format,
        expected_format,
    ):
        """Thumbnail save format inference should cover extensions and detected types."""
        assert _save_format_from_name(file_name, detected_format) == expected_format

    def test_thumbnail_save_kwargs_match_format_expectations(self):
        """Thumbnail save options should match the target image format."""
        assert _thumbnail_save_kwargs("JPEG") == {"quality": 85, "optimize": True}
        assert _thumbnail_save_kwargs("WEBP") == {"quality": 85, "optimize": True}
        assert _thumbnail_save_kwargs("PNG") == {"optimize": True}
        assert _thumbnail_save_kwargs("GIF") == {}

    def test_prepare_thumbnail_image_converts_non_rgb_jpeg(self):
        """JPEG thumbnails should be converted to an RGB-compatible mode."""
        image = Image.new("RGBA", (20, 20), color="navy")

        prepared = _prepare_thumbnail_image(image, "JPEG")

        assert prepared.mode == "RGB"

    def test_prepare_thumbnail_image_leaves_non_jpeg_modes_unchanged(self):
        """Non-JPEG thumbnail formats should preserve the source image mode."""
        image = Image.new("RGBA", (20, 20), color="teal")

        prepared = _prepare_thumbnail_image(image, "PNG")

        assert prepared.mode == "RGBA"


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

    def test_get_avatar_url_uses_public_base_url(self, user, tmp_path, settings):
        """Author avatars should resolve through the storage public URL helper."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"

        image = Image.new("RGB", (200, 200), color="teal")
        image_path = tmp_path / "avatar.png"
        image.save(str(image_path), format="PNG")

        with open(image_path, "rb") as image_handle:
            uploaded_file = SimpleUploadedFile(
                "avatar.png",
                image_handle.read(),
                content_type="image/png",
            )

        profile = AuthorProfile.objects.create(
            user=user,
            bio="Test author bio",
            avatar=uploaded_file,
        )

        assert profile.get_avatar_url().startswith("https://cdn.example.com/media/")


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
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"

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
        assert medium_url.startswith("https://cdn.example.com/media/")
        assert "thumbnails" in medium_url
        assert "medium" in medium_url

        small_url = post.get_thumbnail_url("small")
        assert small_url.startswith("https://cdn.example.com/media/")
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

    def test_get_thumbnail_url_falls_back_to_original_if_missing_variant(
        self,
        author_user,
        tmp_path,
        settings,
    ):
        """Test thumbnail URL falls back to the original image when variant is absent."""
        settings.MEDIA_ROOT = str(tmp_path)

        img_dir = tmp_path / "blog" / "images"
        img_dir.mkdir(parents=True)
        img_path = img_dir / "fallback.jpg"
        img = Image.new("RGB", (1200, 800), color="purple")
        img.save(str(img_path), format="JPEG")

        with open(str(img_path), "rb") as f:
            image_file = SimpleUploadedFile(
                "fallback.jpg", f.read(), content_type="image/jpeg"
            )
        post = Post.objects.create(
            title="Fallback Post",
            author=author_user,
            content="Content",
            featured_image=image_file,
        )

        assert post.get_thumbnail_url("large") == post.featured_image.url

    def test_get_featured_image_url_uses_public_base_url(
        self,
        author_user,
        tmp_path,
        settings,
    ):
        """Featured image public URL should be helper-backed when configured."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"

        image = Image.new("RGB", (800, 450), color="purple")
        image_path = tmp_path / "featured-helper.png"
        image.save(str(image_path), format="PNG")

        with open(image_path, "rb") as image_handle:
            uploaded_file = SimpleUploadedFile(
                "featured-helper.png",
                image_handle.read(),
                content_type="image/png",
            )

        post = Post.objects.create(
            title="Helper Image Post",
            author=author_user,
            content="Content",
            featured_image=uploaded_file,
        )

        assert post.get_featured_image_url().startswith(
            "https://cdn.example.com/media/blog/images/"
        )

    def test_generate_thumbnails_skips_non_filesystem_storage_path(
        self,
        author_user,
        tmp_path,
        settings,
        monkeypatch,
    ):
        """Test thumbnail generation exits cleanly when storage cannot open the source image."""
        settings.MEDIA_ROOT = str(tmp_path)

        image_bytes = BytesIO()
        Image.new("RGB", (400, 300), color="black").save(image_bytes, format="JPEG")
        image_file = SimpleUploadedFile(
            "remote.jpg",
            image_bytes.getvalue(),
            content_type="image/jpeg",
        )

        post = Post.objects.create(
            title="Remote Storage Post",
            author=author_user,
            content="Content",
            featured_image=image_file,
        )

        def _raise_not_implemented(*_args, **_kwargs):
            raise NotImplementedError

        monkeypatch.setattr(post.featured_image.storage, "open", _raise_not_implemented)
        post._generate_thumbnails()

    def test_generate_thumbnails_with_storage_open_without_filesystem_path(
        self,
        author_user,
        tmp_path,
        settings,
        monkeypatch,
    ):
        """Thumbnail generation should work via storage I/O without relying on `.path`."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"

        image_bytes = BytesIO()
        Image.new("RGB", (1200, 800), color="orange").save(
            image_bytes,
            format="JPEG",
        )
        image_file = SimpleUploadedFile(
            "remote-generated.jpg",
            image_bytes.getvalue(),
            content_type="image/jpeg",
        )

        post = Post.objects.create(
            title="Remote Thumbnail Post",
            author=author_user,
            content="Content",
            featured_image=image_file,
        )

        original_bytes = post.featured_image.read()
        stored_files: dict[str, bytes] = {post.featured_image.name: original_bytes}

        def _raise_not_implemented(_: str) -> str:
            raise NotImplementedError

        def _open(name: str, mode: str = "rb") -> BytesIO:
            return BytesIO(stored_files[name])

        def _save(name: str, content) -> str:
            stored_files[name] = content.read()
            return name

        def _exists(name: str) -> bool:
            return name in stored_files

        def _delete(name: str) -> None:
            stored_files.pop(name, None)

        monkeypatch.setattr(post.featured_image.storage, "path", _raise_not_implemented)
        monkeypatch.setattr(post.featured_image.storage, "open", _open)
        monkeypatch.setattr(post.featured_image.storage, "save", _save)
        monkeypatch.setattr(post.featured_image.storage, "exists", _exists)
        monkeypatch.setattr(post.featured_image.storage, "delete", _delete)
        post._generate_thumbnails()

        thumbnail_name = post._get_thumbnail_name("medium")
        assert post.featured_image.storage.exists(thumbnail_name)
        assert post.get_thumbnail_url("medium").startswith(
            "https://cdn.example.com/media/"
        )

    def test_helper_backed_urls_do_not_depend_on_storage_url(
        self,
        author_user,
        tmp_path,
        settings,
    ):
        """Public featured/thumbnail URLs should not call storage `.url` when helper-backed."""
        settings.MEDIA_ROOT = str(tmp_path)
        settings.QUICKSCALE_STORAGE_PUBLIC_BASE_URL = "https://cdn.example.com/media"

        image = Image.new("RGB", (1200, 800), color="navy")
        image_path = tmp_path / "helper-only.jpg"
        image.save(str(image_path), format="JPEG")

        with open(image_path, "rb") as image_handle:
            uploaded_file = SimpleUploadedFile(
                "helper-only.jpg",
                image_handle.read(),
                content_type="image/jpeg",
            )

        post = Post.objects.create(
            title="Helper Only URLs",
            author=author_user,
            content="Content",
            featured_image=uploaded_file,
        )

        with patch.object(
            post.featured_image.storage, "url", side_effect=AssertionError
        ):
            assert post.get_featured_image_url().startswith(
                "https://cdn.example.com/media/blog/images/"
            )
            assert post.get_thumbnail_url("medium").startswith(
                "https://cdn.example.com/media/blog/images/thumbnails/"
            )


@pytest.mark.django_db
class TestBlogMediaAsset:
    """Tests for BlogMediaAsset model."""

    def test_blog_media_asset_creation(self, author_user, tmp_path, settings):
        """Test creating a blog media asset stores metadata."""
        settings.MEDIA_ROOT = str(tmp_path)

        image = Image.new("RGB", (640, 360), color="green")
        image_path = tmp_path / "asset.png"
        image.save(str(image_path), format="PNG")

        with open(image_path, "rb") as image_handle:
            uploaded_file = SimpleUploadedFile(
                "asset.png",
                image_handle.read(),
                content_type="image/png",
            )

        asset = BlogMediaAsset.objects.create(
            file=uploaded_file,
            alt="Diagram",
            kind=BlogMediaAsset.Kind.INLINE,
            original_filename="asset.png",
            width=640,
            height=360,
            uploaded_by=author_user,
        )

        assert asset.alt == "Diagram"
        assert asset.kind == BlogMediaAsset.Kind.INLINE
        assert asset.width == 640
        assert asset.height == 360
        assert asset.uploaded_by == author_user
        assert asset.file.name.startswith("blog/uploads/")
