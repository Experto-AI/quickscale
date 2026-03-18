"""Blog models for QuickScale blog module"""

import posixpath
from collections.abc import Callable
from importlib import import_module
from pathlib import Path
from typing import Any
from uuid import uuid4

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from markdownx.models import MarkdownxField
from PIL import Image

storage_build_upload_path: Callable[..., str] | None = None
storage_helpers: Any | None
try:
    storage_helpers = import_module("quickscale_modules_storage.helpers")
except ModuleNotFoundError:
    storage_helpers = None

if storage_helpers is not None:
    storage_build_upload_path = getattr(storage_helpers, "build_upload_path", None)


def blog_media_upload_to(_: "BlogMediaAsset", filename: str) -> str:
    """Build a stable, collision-resistant upload path for blog media assets."""
    if storage_build_upload_path is not None:
        return storage_build_upload_path("blog", "uploads", filename)

    extension = Path(filename).suffix.lower() or ".bin"
    stem = slugify(Path(filename).stem) or "image"
    return f"blog/uploads/{timezone.now():%Y/%m}/{stem}-{uuid4().hex[:12]}{extension}"


class Category(models.Model):
    """Blog post category"""

    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True, blank=True)
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        """Return the URL for this category"""
        return reverse("quickscale_blog:category_list", kwargs={"slug": self.slug})


class Tag(models.Model):
    """Blog post tag"""

    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True, blank=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        """Return the URL for this tag"""
        return reverse("quickscale_blog:tag_list", kwargs={"slug": self.slug})


class AuthorProfile(models.Model):
    """Extended profile for blog post authors"""

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="author_profile",
    )
    bio = models.TextField(blank=True, help_text="Author biography")
    avatar = models.ImageField(
        upload_to="blog/avatars/",
        blank=True,
        null=True,
        help_text="Author profile picture",
    )

    class Meta:
        ordering = ["user__username"]

    def __str__(self) -> str:
        return f"{self.user.username} - Author Profile"


class BlogMediaAsset(models.Model):
    """Uploaded media asset that can be referenced by blog automation workflows."""

    class Kind(models.TextChoices):
        INLINE = "inline", "Inline"
        FEATURED = "featured", "Featured"
        GENERAL = "general", "General"

    file = models.ImageField(upload_to=blog_media_upload_to)
    alt = models.CharField(
        max_length=200,
        blank=True,
        help_text="Alt text for the uploaded image (accessibility)",
    )
    kind = models.CharField(
        max_length=20,
        choices=Kind.choices,
        default=Kind.INLINE,
        help_text="How the asset is intended to be used by the blog workflow",
    )
    original_filename = models.CharField(max_length=255)
    width = models.PositiveIntegerField(null=True, blank=True)
    height = models.PositiveIntegerField(null=True, blank=True)
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="uploaded_blog_media_assets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_filename


class Post(models.Model):
    """Blog post model with Markdown support"""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blog_posts",
        null=True,
        blank=True,
    )
    content = MarkdownxField(help_text="Post content in Markdown format")
    excerpt = models.TextField(
        max_length=500,
        blank=True,
        help_text="Short excerpt (auto-generated from content if not provided)",
    )
    featured_image = models.ImageField(
        upload_to="blog/images/",
        blank=True,
        null=True,
        help_text="Featured image for the post",
    )
    featured_image_alt = models.CharField(
        max_length=200,
        blank=True,
        help_text="Alt text for featured image (accessibility)",
    )
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="draft")
    category = models.ForeignKey(
        Category,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="posts",
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="posts")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_date = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-published_date", "-created_at"]
        indexes = [
            models.Index(fields=["-published_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Auto-generate slug and excerpt if not provided"""
        if not self.slug:
            self.slug = slugify(self.title)

        # Set published_date when status changes to published
        if self.status == "published" and not self.published_date:
            self.published_date = timezone.now()

        # Auto-generate excerpt from content if not provided
        if not self.excerpt and self.content:
            # Remove markdown formatting for excerpt
            plain_text = self.content.replace("#", "").replace("*", "").replace("`", "")
            self.excerpt = (
                plain_text[:300] + "..." if len(plain_text) > 300 else plain_text
            )

        super().save(*args, **kwargs)

        # Generate thumbnails for featured image
        if self.featured_image:
            self._generate_thumbnails()

    def get_absolute_url(self) -> str:
        """Return the URL for this post"""
        return reverse("quickscale_blog:post_detail", kwargs={"slug": self.slug})

    def _generate_thumbnails(self) -> None:
        """Generate thumbnail versions of featured image"""
        if not self.featured_image:
            return

        try:
            image_path = self.featured_image.path
        except NotImplementedError, ValueError, AttributeError:
            return

        sizes = {
            "small": (300, 200),
            "medium": (800, 450),
        }

        image_path_obj = Path(image_path)
        thumb_dir = image_path_obj.parent / "thumbnails"
        thumb_dir.mkdir(parents=True, exist_ok=True)

        with Image.open(image_path) as img:
            for size_name, dimensions in sizes.items():
                img_copy = img.copy()
                img_copy.thumbnail(dimensions, Image.Resampling.LANCZOS)
                thumb_path = (
                    thumb_dir
                    / f"{image_path_obj.stem}_{size_name}{image_path_obj.suffix}"
                )
                img_copy.save(thumb_path, quality=85, optimize=True)

    def get_thumbnail_url(self, size: str = "medium") -> str:
        """Get URL for thumbnail of specified size"""
        if not self.featured_image:
            return ""

        file_name = str(self.featured_image.name)
        directory, filename = posixpath.split(file_name)
        stem, extension = posixpath.splitext(filename)
        thumbnail_name = posixpath.join(
            directory,
            "thumbnails",
            f"{stem}_{size}{extension}",
        )

        try:
            if self.featured_image.storage.exists(thumbnail_name):
                return self.featured_image.storage.url(thumbnail_name)
        except Exception:
            return self.featured_image.url

        return self.featured_image.url
