"""Blog models for QuickScale blog module"""

import posixpath
import warnings
from io import BytesIO
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from django.conf import settings
from django.core.files.base import ContentFile
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from markdownx.models import MarkdownxField
from PIL import Image

from quickscale_modules_orgs.models import TenantModel

from . import _storage


def _build_public_media_url(stored_reference: str) -> str:
    """Return a public URL for a stored media reference.

    Storage's service resolves storage's own settings (rules 3, 4, and 34);
    without storage installed, the fallback uses only the project's
    ``MEDIA_URL`` and reads no storage setting.
    """
    services = _storage.storage_services()
    if services is not None:
        return services.build_public_media_url(stored_reference)

    reference = (stored_reference or "").strip()
    if not reference:
        return ""

    parsed = urlparse(reference)
    if parsed.scheme and parsed.netloc:
        return reference

    if reference.startswith("/"):
        return reference

    normalized_media_url = str(settings.MEDIA_URL).strip()
    if not normalized_media_url.startswith("/") and not normalized_media_url.startswith(
        "http"
    ):
        normalized_media_url = "/" + normalized_media_url
    if not normalized_media_url.endswith("/"):
        normalized_media_url += "/"
    return f"{normalized_media_url}{reference.lstrip('/')}"


def _save_format_from_name(file_name: str, detected_format: str | None) -> str:
    """Infer a Pillow save format from the original file name or detected format."""
    if detected_format:
        normalized = detected_format.upper()
        if normalized == "JPG":
            return "JPEG"
        return normalized

    extension = Path(file_name).suffix.lower()
    if extension in {".jpg", ".jpeg"}:
        return "JPEG"
    if extension == ".png":
        return "PNG"
    if extension == ".webp":
        return "WEBP"
    if extension == ".gif":
        return "GIF"
    return "JPEG"


def _thumbnail_save_kwargs(image_format: str) -> dict[str, Any]:
    """Return image-save keyword arguments appropriate for the target format."""
    if image_format in {"JPEG", "WEBP"}:
        return {"quality": 85, "optimize": True}
    if image_format == "PNG":
        return {"optimize": True}
    return {}


def _prepare_thumbnail_image(image: Image.Image, image_format: str) -> Image.Image:
    """Normalize image mode for the requested thumbnail format."""
    if image_format == "JPEG" and image.mode not in {"RGB", "L"}:
        return image.convert("RGB")
    return image


def blog_media_upload_to(_: "BlogMediaAsset", filename: str) -> str:
    """Build a stable, collision-resistant upload path for blog media assets."""
    services = _storage.storage_services()
    if services is not None:
        return services.build_upload_path(
            "blog", asset_kind="uploads", filename=filename
        )

    extension = Path(filename).suffix.lower() or ".bin"
    stem = slugify(Path(filename).stem) or "image"
    return f"blog/uploads/{timezone.now():%Y/%m}/{stem}-{uuid4().hex[:12]}{extension}"


class Category(TenantModel):
    """Blog post category"""

    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100, blank=True)
    description = models.TextField(blank=True)

    class Meta(TenantModel.Meta):
        verbose_name_plural = "Categories"
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "organization"],
                name="quickscale_blog_category_name_organization_unique",
            ),
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="quickscale_blog_category_slug_organization_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        """Return the flat route URL for this category."""
        return reverse("quickscale_blog:category_list", kwargs={"slug": self.slug})


class Tag(TenantModel):
    """Blog post tag"""

    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=50, blank=True)

    class Meta(TenantModel.Meta):
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(
                fields=["name", "organization"],
                name="quickscale_blog_tag_name_organization_unique",
            ),
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="quickscale_blog_tag_slug_organization_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Auto-generate slug from name if not provided"""
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        """Return the flat route URL for this tag."""
        return reverse("quickscale_blog:tag_list", kwargs={"slug": self.slug})


class AuthorProfile(models.Model):
    """Extended profile for blog post authors

    User-profile extension linked to auth.User — not tenant-scoped.
    """

    tenant_excluded = "User-profile extension linked to auth.User, not tenant-scoped."

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="quickscale_blog_author_profile",
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

    def get_avatar_url(self) -> str:
        """Return the public avatar URL through storage's services when available."""
        if not self.avatar:
            return ""
        return _build_public_media_url(str(self.avatar.name))


class BlogMediaAsset(TenantModel):
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
        related_name="quickscale_blog_media_assets",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta(TenantModel.Meta):
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.original_filename


class Post(TenantModel):
    """Blog post model with Markdown support"""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PUBLISHED = "published", "Published"

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, blank=True)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="quickscale_blog_posts",
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
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT
    )
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

    class Meta(TenantModel.Meta):
        ordering = ["-published_date", "-created_at"]
        indexes = [
            models.Index(fields=["-published_date"], name="qs_blog_post_publish_idx"),
            models.Index(fields=["status"], name="qs_blog_post_status_idx"),
            models.Index(fields=["slug"], name="qs_blog_post_slug_idx"),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["slug", "organization"],
                name="quickscale_blog_post_slug_organization_unique",
            ),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Auto-generate slug and excerpt if not provided"""
        if not self.slug:
            self.slug = slugify(self.title)

        # Set published_date when status changes to published
        if self.status == self.Status.PUBLISHED and not self.published_date:
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
        """Return the flat route URL for this post."""
        return reverse("quickscale_blog:post_detail", kwargs={"slug": self.slug})

    def get_featured_image_url(self) -> str:
        """Return the public featured image URL through storage's services when available."""
        if not self.featured_image:
            return ""
        return _build_public_media_url(str(self.featured_image.name))

    def _get_thumbnail_name(self, size: str) -> str:
        """Return the storage-relative thumbnail name for a given size."""
        file_name = str(self.featured_image.name)
        directory, filename = posixpath.split(file_name)
        stem, extension = posixpath.splitext(filename)
        return posixpath.join(
            directory,
            "thumbnails",
            f"{stem}_{size}{extension}",
        )

    def _generate_thumbnails(self) -> None:
        """Generate thumbnail versions of featured image"""
        if not self.featured_image:
            return

        sizes = {
            "small": (300, 200),
            "medium": (800, 450),
        }

        storage = self.featured_image.storage
        source_name = str(self.featured_image.name)

        try:
            with warnings.catch_warnings():
                warnings.simplefilter("error", Image.DecompressionBombWarning)
                with storage.open(source_name, "rb") as source_file:
                    with Image.open(source_file) as image:
                        source_format = _save_format_from_name(
                            source_name, image.format
                        )
                        for size_name, dimensions in sizes.items():
                            img_copy = image.copy()
                            img_copy.thumbnail(dimensions, Image.Resampling.LANCZOS)
                            prepared = _prepare_thumbnail_image(img_copy, source_format)
                            thumbnail_name = self._get_thumbnail_name(size_name)
                            output = BytesIO()
                            prepared.save(
                                output,
                                format=source_format,
                                **_thumbnail_save_kwargs(source_format),
                            )
                            output.seek(0)
                            if storage.exists(thumbnail_name):
                                storage.delete(thumbnail_name)
                            storage.save(
                                thumbnail_name,
                                ContentFile(output.getvalue()),
                            )
        except (
            AttributeError,
            FileNotFoundError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
            NotImplementedError,
            OSError,
            ValueError,
        ):
            return

    def get_thumbnail_url(self, size: str = "medium") -> str:
        """Get URL for thumbnail of specified size"""
        if not self.featured_image:
            return ""

        thumbnail_name = self._get_thumbnail_name(size)

        try:
            if self.featured_image.storage.exists(thumbnail_name):
                return _build_public_media_url(thumbnail_name)
        except (
            AttributeError,
            FileNotFoundError,
            NotImplementedError,
            OSError,
            ValueError,
        ):
            return self.get_featured_image_url()

        return self.get_featured_image_url()
