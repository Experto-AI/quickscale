"""Listing models for QuickScale listings module"""

from django.db import models
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify


class AbstractListing(models.Model):
    """Abstract base model for marketplace listings"""

    STATUS_CHOICES = [
        ("draft", "Draft"),
        ("published", "Published"),
        ("sold", "Sold"),
        ("archived", "Archived"),
    ]

    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=200, unique=True, blank=True)
    description = models.TextField(
        blank=True,
        help_text="Plain text description of the listing",
    )
    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Price in default currency (leave blank for 'Contact for price')",
    )
    location = models.CharField(
        max_length=200,
        blank=True,
        help_text="Free-text location description",
    )
    status = models.CharField(
        max_length=10,
        choices=STATUS_CHOICES,
        default="draft",
    )
    featured_image = models.ImageField(
        upload_to="listings/images/",
        blank=True,
        null=True,
        help_text="Featured image for the listing",
    )
    featured_image_alt = models.CharField(
        max_length=200,
        blank=True,
        help_text="Alt text for featured image (accessibility)",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    published_date = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Date when listing was published",
    )

    class Meta:
        abstract = True
        ordering = ["-published_date", "-created_at"]
        indexes = [
            models.Index(fields=["-published_date"]),
            models.Index(fields=["status"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self) -> str:
        return self.title

    def save(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        """Auto-generate slug and set published_date on status change"""
        if not self.slug:
            self.slug = slugify(self.title)

        # Set published_date when status changes to published
        if self.status == "published" and not self.published_date:
            self.published_date = timezone.now()

        super().save(*args, **kwargs)

    def get_absolute_url(self) -> str:
        """Return the URL for this listing"""
        return reverse("quickscale_listings:listing_detail", kwargs={"slug": self.slug})

    @property
    def is_published(self) -> bool:
        """Check if listing is published"""
        return self.status == "published"

    @property
    def is_sold(self) -> bool:
        """Check if listing is sold"""
        return self.status == "sold"

    @property
    def has_price(self) -> bool:
        """Check if listing has a price set"""
        return self.price is not None
