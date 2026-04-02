"""Data models for the QuickScale social module."""

from __future__ import annotations

from typing import Any, ClassVar

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from quickscale_modules_social.contracts import (
    SOCIAL_EMBEDS_CACHE_KEY,
    SOCIAL_EMBED_RESOLUTION_CHOICES,
    SOCIAL_EMBED_RESOLUTION_ERROR,
    SOCIAL_EMBED_RESOLUTION_PENDING,
    SOCIAL_EMBED_RESOLUTION_RESOLVED,
    SOCIAL_LINKS_CACHE_KEY,
    SOCIAL_PROVIDER_CHOICES,
    SocialConfigurationError,
    get_social_runtime_settings,
    resolve_social_embed_metadata,
    resolve_social_target,
    social_provider_supports_embeds,
)


class BaseSocialItem(models.Model):
    """Shared curated social item fields and normalization behavior."""

    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    provider_name = models.CharField(
        max_length=32,
        blank=True,
        choices=SOCIAL_PROVIDER_CHOICES,
        db_index=True,
        help_text="Optional canonical provider name. Leave blank to detect it from the URL.",
    )
    url = models.URLField(max_length=500)
    normalized_url = models.URLField(
        max_length=500,
        blank=True,
        editable=False,
        unique=True,
    )
    display_order = models.PositiveIntegerField(
        default=0,
        db_index=True,
        validators=[MinValueValidator(0)],
    )
    is_published = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    cache_keys: ClassVar[tuple[str, ...]] = ()
    require_embed_support: ClassVar[bool] = False

    class Meta:
        abstract = True
        ordering = ["display_order", "title", "pk"]

    def __str__(self) -> str:
        return self.title

    def clean(self) -> None:
        super().clean()

        try:
            runtime_settings = get_social_runtime_settings()
        except SocialConfigurationError as exc:
            raise ValidationError({"__all__": str(exc)}) from exc

        try:
            resolved = resolve_social_target(
                self.url,
                provider=self.provider_name or None,
            )
        except ValueError as exc:
            raise ValidationError({"url": str(exc)}) from exc

        if resolved.provider not in runtime_settings.provider_allowlist:
            raise ValidationError(
                {
                    "provider_name": (
                        "This provider is not allowlisted by "
                        "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST."
                    )
                }
            )

        if self.require_embed_support and not social_provider_supports_embeds(
            resolved.provider
        ):
            raise ValidationError(
                {
                    "provider_name": (
                        "Embeds support only TikTok and YouTube in v0.79.0."
                    )
                }
            )

        self.provider_name = resolved.provider
        self.normalized_url = resolved.url

    def _prepare_for_save(self) -> None:
        return None

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
        self._prepare_for_save()
        super().save(*args, **kwargs)
        if self.cache_keys:
            cache.delete_many(self.cache_keys)

    def delete(self, *args: Any, **kwargs: Any) -> tuple[int, dict[str, int]]:
        result = super().delete(*args, **kwargs)
        if self.cache_keys:
            cache.delete_many(self.cache_keys)
        return result


class SocialLink(BaseSocialItem):
    """Curated outbound links for the public social link-tree surface."""

    cache_keys = (SOCIAL_LINKS_CACHE_KEY,)

    class Meta(BaseSocialItem.Meta):
        app_label = "quickscale_modules_social"
        verbose_name = "Social link"
        verbose_name_plural = "Social links"


class SocialEmbed(BaseSocialItem):
    """Curated embed-capable social entries for the public embed surface."""

    cache_keys = (SOCIAL_EMBEDS_CACHE_KEY,)
    require_embed_support = True
    resolution_status = models.CharField(
        max_length=16,
        choices=SOCIAL_EMBED_RESOLUTION_CHOICES,
        default=SOCIAL_EMBED_RESOLUTION_PENDING,
        editable=False,
        db_index=True,
    )
    resolution_error = models.TextField(blank=True, default="", editable=False)
    last_resolution_attempt_at = models.DateTimeField(
        blank=True,
        null=True,
        editable=False,
    )
    last_resolved_at = models.DateTimeField(blank=True, null=True, editable=False)
    resolved_embed_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        editable=False,
    )
    resolved_thumbnail_url = models.URLField(
        max_length=500,
        blank=True,
        default="",
        editable=False,
    )
    resolved_width = models.PositiveIntegerField(blank=True, null=True, editable=False)
    resolved_height = models.PositiveIntegerField(blank=True, null=True, editable=False)
    resolved_thumbnail_width = models.PositiveIntegerField(
        blank=True,
        null=True,
        editable=False,
    )
    resolved_thumbnail_height = models.PositiveIntegerField(
        blank=True,
        null=True,
        editable=False,
    )

    def _should_refresh_resolution(self) -> bool:
        if self.pk is None:
            return True

        previous = (
            SocialEmbed.objects.filter(pk=self.pk)
            .values(
                "normalized_url",
                "provider_name",
            )
            .first()
        )
        if previous is None:
            return True
        if previous["normalized_url"] != self.normalized_url:
            return True
        if previous["provider_name"] != self.provider_name:
            return True
        if self.last_resolution_attempt_at is None:
            return True
        return bool(
            self.resolution_status != SOCIAL_EMBED_RESOLUTION_ERROR
            and not self.resolved_embed_url
        )

    def refresh_resolution_metadata(self, *, force: bool = False) -> None:
        if not force and not self._should_refresh_resolution():
            return

        attempted_at = timezone.now()
        self.last_resolution_attempt_at = attempted_at
        try:
            metadata = resolve_social_embed_metadata(
                self.normalized_url or self.url,
                provider=self.provider_name,
            )
        except ValueError as exc:
            self.resolution_status = SOCIAL_EMBED_RESOLUTION_ERROR
            self.resolution_error = str(exc)
            self.last_resolved_at = None
            self.resolved_embed_url = ""
            self.resolved_thumbnail_url = ""
            self.resolved_width = None
            self.resolved_height = None
            self.resolved_thumbnail_width = None
            self.resolved_thumbnail_height = None
            return

        self.resolution_status = SOCIAL_EMBED_RESOLUTION_RESOLVED
        self.resolution_error = ""
        self.last_resolved_at = attempted_at
        self.resolved_embed_url = metadata.embed_url
        self.resolved_thumbnail_url = metadata.thumbnail_url or ""
        self.resolved_width = metadata.embed_width
        self.resolved_height = metadata.embed_height
        self.resolved_thumbnail_width = metadata.thumbnail_width
        self.resolved_thumbnail_height = metadata.thumbnail_height

    def _prepare_for_save(self) -> None:
        self.refresh_resolution_metadata()

    class Meta(BaseSocialItem.Meta):
        app_label = "quickscale_modules_social"
        verbose_name = "Social embed"
        verbose_name_plural = "Social embeds"
