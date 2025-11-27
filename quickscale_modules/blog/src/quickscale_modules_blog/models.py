"""Blog models for QuickScale blog module"""

from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from markdownx.models import MarkdownxField
from PIL import Image
import os


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

        image_path = self.featured_image.path
        img = Image.open(image_path)

        # Define thumbnail sizes
        sizes = {
            "small": (300, 200),
            "medium": (800, 450),
        }

        for size_name, dimensions in sizes.items():
            # Create thumbnail directory
            thumb_dir = os.path.join(
                os.path.dirname(image_path),
                "thumbnails",
            )
            os.makedirs(thumb_dir, exist_ok=True)

            # Generate thumbnail
            img_copy = img.copy()
            img_copy.thumbnail(dimensions, Image.Resampling.LANCZOS)

            # Save thumbnail
            filename = os.path.basename(image_path)
            name, ext = os.path.splitext(filename)
            thumb_filename = f"{name}_{size_name}{ext}"
            thumb_path = os.path.join(thumb_dir, thumb_filename)
            img_copy.save(thumb_path, quality=85, optimize=True)

    def get_thumbnail_url(self, size: str = "medium") -> str:
        """Get URL for thumbnail of specified size"""
        if not self.featured_image:
            return ""

        # Construct thumbnail URL
        base_url = self.featured_image.url
        path_parts = base_url.rsplit("/", 1)
        filename = path_parts[1]
        name, ext = os.path.splitext(filename)
        thumb_filename = f"{name}_{size}{ext}"

        return f"{path_parts[0]}/thumbnails/{thumb_filename}"
