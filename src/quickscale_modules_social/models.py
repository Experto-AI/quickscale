"""Data models for the QuickScale social module."""

from __future__ import annotations

from typing import Any, ClassVar

from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from quickscale_modules_social.contracts import (
    SOCIAL_EMBEDS_CACHE_KEY,
    SOCIAL_LINKS_CACHE_KEY,
    SOCIAL_PROVIDER_CHOICES,
    SocialConfigurationError,
    get_social_runtime_settings,
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

    def save(self, *args: Any, **kwargs: Any) -> None:
        self.full_clean()
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

    class Meta(BaseSocialItem.Meta):
        app_label = "quickscale_modules_social"
        verbose_name = "Social embed"
        verbose_name_plural = "Social embeds"
