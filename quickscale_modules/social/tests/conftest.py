"""Shared pytest fixtures for the QuickScale social module."""

from __future__ import annotations

from collections.abc import Iterator
import os
from pathlib import Path
import sys
from typing import TYPE_CHECKING, Any, cast

import django
import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client

if TYPE_CHECKING:
    from quickscale_modules_social.models import SocialEmbed, SocialLink

MODULE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = MODULE_ROOT / "src"

for path in (SRC_ROOT, MODULE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
django.setup()


@pytest.fixture(autouse=True)
def clear_social_cache() -> Iterator[None]:
    """Clear cached social payloads before each test for deterministic assertions."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def superuser(db: None) -> Any:
    """Return a superuser for admin tests."""
    user_model = cast(Any, get_user_model())
    return user_model.objects.create_superuser(
        username="social-admin",
        email="social-admin@example.com",
        password="adminpass123",
    )


@pytest.fixture
def admin_client(superuser: Any) -> Client:
    """Return an authenticated Django client for admin requests."""
    client = Client()
    client.force_login(superuser)
    return client


@pytest.fixture
def social_link(db: None) -> SocialLink:
    """Return a published curated social link."""
    return SocialLink.objects.create(
        title="QuickScale on LinkedIn",
        provider_name="",
        url="https://www.linkedin.com/company/quickscale/?utm_source=share",
        description="Company updates and launch notes.",
        display_order=10,
        is_published=True,
    )


@pytest.fixture
def social_embed(db: None) -> SocialEmbed:
    """Return a published curated social embed."""
    return SocialEmbed.objects.create(
        title="QuickScale launch video",
        provider_name="",
        url="https://youtu.be/abc123?si=share",
        description="Launch announcement clip.",
        display_order=5,
        is_published=True,
    )
