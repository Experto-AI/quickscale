"""Add persisted embed resolution metadata for social embeds."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit

from django.db import migrations, models


SOCIAL_EMBED_RESOLUTION_PENDING = "pending"
SOCIAL_EMBED_RESOLUTION_RESOLVED = "resolved"
SOCIAL_EMBED_RESOLUTION_ERROR = "error"
SOCIAL_EMBED_RESOLUTION_CHOICES = (
    (SOCIAL_EMBED_RESOLUTION_PENDING, "Pending"),
    (SOCIAL_EMBED_RESOLUTION_RESOLVED, "Resolved"),
    (SOCIAL_EMBED_RESOLUTION_ERROR, "Error"),
)
_YOUTUBE_EMBED_PATH_PATTERN = re.compile(r"^/(?:embed|live|shorts|v)/([^/?#]+)$")
_TIKTOK_VIDEO_PATH_PATTERN = re.compile(r"/video/(\d+)")


def _canonical_path(path: str) -> str:
    normalized = re.sub(r"/{2,}", "/", path or "/")
    if normalized != "/":
        normalized = normalized.rstrip("/")
    return normalized or "/"


def _query_value(query: str, key: str) -> str | None:
    for query_key, value in parse_qsl(query, keep_blank_values=False):
        if query_key == key and value.strip():
            return value.strip()
    return None


def _apply_resolution_defaults(
    embed: Any,
    attempted_at: Any,
    error_message: str,
) -> None:
    embed.resolution_status = SOCIAL_EMBED_RESOLUTION_ERROR
    embed.resolution_error = error_message
    embed.last_resolution_attempt_at = attempted_at
    embed.last_resolved_at = None
    embed.resolved_embed_url = ""
    embed.resolved_thumbnail_url = ""
    embed.resolved_width = None
    embed.resolved_height = None
    embed.resolved_thumbnail_width = None
    embed.resolved_thumbnail_height = None


def _populate_embed_resolution_metadata(apps: Any, schema_editor: Any) -> None:
    del schema_editor
    SocialEmbed = apps.get_model("quickscale_modules_social", "SocialEmbed")

    for embed in SocialEmbed.objects.all().iterator():
        attempted_at = embed.updated_at or embed.created_at
        provider = str(embed.provider_name or "").strip().lower()
        parsed = urlsplit(embed.normalized_url or embed.url)

        if provider == "youtube":
            video_id = _query_value(parsed.query, "v")
            if video_id is None:
                path_match = _YOUTUBE_EMBED_PATH_PATTERN.fullmatch(
                    _canonical_path(parsed.path)
                )
                video_id = path_match.group(1) if path_match is not None else None

            if not video_id:
                _apply_resolution_defaults(
                    embed,
                    attempted_at,
                    "QuickScale could not derive a canonical YouTube video id for inline preview metadata.",
                )
            else:
                embed_query_items = [("rel", "0")]
                playlist_id = _query_value(parsed.query, "list")
                if playlist_id:
                    embed_query_items.append(("list", playlist_id))

                embed.resolution_status = SOCIAL_EMBED_RESOLUTION_RESOLVED
                embed.resolution_error = ""
                embed.last_resolution_attempt_at = attempted_at
                embed.last_resolved_at = attempted_at
                embed.resolved_embed_url = (
                    f"https://www.youtube.com/embed/{video_id}?"
                    f"{urlencode(embed_query_items)}"
                )
                embed.resolved_thumbnail_url = (
                    f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"
                )
                embed.resolved_width = 560
                embed.resolved_height = 315
                embed.resolved_thumbnail_width = 480
                embed.resolved_thumbnail_height = 360
        elif provider == "tiktok":
            path_match = _TIKTOK_VIDEO_PATH_PATTERN.search(_canonical_path(parsed.path))
            video_id = path_match.group(1) if path_match is not None else None
            if not video_id:
                _apply_resolution_defaults(
                    embed,
                    attempted_at,
                    "QuickScale needs a canonical TikTok video URL before it can resolve inline preview metadata.",
                )
            else:
                embed.resolution_status = SOCIAL_EMBED_RESOLUTION_RESOLVED
                embed.resolution_error = ""
                embed.last_resolution_attempt_at = attempted_at
                embed.last_resolved_at = attempted_at
                embed.resolved_embed_url = f"https://www.tiktok.com/embed/v2/{video_id}"
                embed.resolved_thumbnail_url = ""
                embed.resolved_width = 325
                embed.resolved_height = 575
                embed.resolved_thumbnail_width = None
                embed.resolved_thumbnail_height = None
        else:
            _apply_resolution_defaults(
                embed,
                attempted_at,
                "Embeds support only TikTok and YouTube in v0.79.0.",
            )

        embed.save(
            update_fields=[
                "resolution_status",
                "resolution_error",
                "last_resolution_attempt_at",
                "last_resolved_at",
                "resolved_embed_url",
                "resolved_thumbnail_url",
                "resolved_width",
                "resolved_height",
                "resolved_thumbnail_width",
                "resolved_thumbnail_height",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("quickscale_modules_social", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="socialembed",
            name="last_resolved_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="last_resolution_attempt_at",
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolution_error",
            field=models.TextField(blank=True, default="", editable=False),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolution_status",
            field=models.CharField(
                choices=SOCIAL_EMBED_RESOLUTION_CHOICES,
                db_index=True,
                default=SOCIAL_EMBED_RESOLUTION_PENDING,
                editable=False,
                max_length=16,
            ),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolved_embed_url",
            field=models.URLField(
                blank=True, default="", editable=False, max_length=500
            ),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolved_height",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolved_thumbnail_height",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolved_thumbnail_url",
            field=models.URLField(
                blank=True, default="", editable=False, max_length=500
            ),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolved_thumbnail_width",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.AddField(
            model_name="socialembed",
            name="resolved_width",
            field=models.PositiveIntegerField(blank=True, editable=False, null=True),
        ),
        migrations.RunPython(
            _populate_embed_resolution_metadata,
            migrations.RunPython.noop,
        ),
    ]
