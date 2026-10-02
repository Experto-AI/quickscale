"""Provider-visible sanitization for the notifications module.

The email provider never receives raw caller tags or metadata: the applied
settings carry the allowlist, and this module normalizes every candidate to
its provider-visible shape.  ``services.py`` re-exports this surface (Module
Conventions rule 28).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TYPE_CHECKING, Any

from django.utils.text import slugify

if TYPE_CHECKING:
    from quickscale_modules_notifications._settings import (
        NotificationSettingsSnapshot,
    )

_DEFAULT_ALLOWED_TAGS = (
    "quickscale",
    "transactional",
    "notifications",
    "auth",
    "forms",
    "ops",
    "testing",
)
_DEFAULT_DEFAULT_TAGS = ("quickscale", "transactional")
_ALLOWED_METADATA_KEYS = {"template", "project", "workflow"}


def sanitize_provider_tags(
    tags: Sequence[str] | None,
    *,
    settings_snapshot: NotificationSettingsSnapshot,
) -> list[str]:
    """Return provider-visible tags limited to the approved non-sensitive allowlist.

    The allowlist is canonicalized for comparison the same way each candidate
    tag is, so an accepted but noncanonical entry (one that reached settings
    outside ``apply``'s normalization) still matches its canonical form
    instead of silently dropping the tag.
    """
    allowed_tags = {_normalize_tag(tag) for tag in settings_snapshot.allowed_tags}
    seen: set[str] = set()
    sanitized: list[str] = []
    for raw_value in [*settings_snapshot.default_tags, *(tags or ())]:
        normalized_tag = _normalize_tag(raw_value)
        if not normalized_tag or normalized_tag not in allowed_tags:
            continue
        if normalized_tag in seen:
            continue
        sanitized.append(normalized_tag)
        seen.add(normalized_tag)
    return sanitized


def sanitize_provider_metadata(
    metadata: Mapping[str, Any] | None,
    *,
    template_key: str,
) -> dict[str, str]:
    """Return provider-visible metadata constrained to non-sensitive keys and values."""
    sanitized: dict[str, str] = {}
    for key, value in (metadata or {}).items():
        normalized_key = _normalize_metadata_key(key)
        if normalized_key not in _ALLOWED_METADATA_KEYS:
            continue
        normalized_value = _sanitize_provider_visible_value(value)
        if normalized_value:
            sanitized[normalized_key] = normalized_value
    sanitized["template"] = _sanitize_provider_visible_value(template_key)
    return sanitized


def _normalize_tag_sequence(values: Sequence[Any]) -> tuple[str, ...]:
    normalized_values: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized_value = _normalize_tag(value)
        if not normalized_value or normalized_value in seen:
            continue
        seen.add(normalized_value)
        normalized_values.append(normalized_value)
    return tuple(normalized_values)


def _normalize_tag(value: Any) -> str:
    normalized = slugify(str(value).strip())
    return normalized[:50]


def _normalize_metadata_key(value: Any) -> str:
    return slugify(str(value).strip()).replace("-", "_")


def _sanitize_provider_visible_value(value: Any) -> str:
    normalized = slugify(str(value).strip().replace(".", "-").replace("_", "-"))
    return normalized[:64]
