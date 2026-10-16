"""Shared pytest fixtures for the QuickScale analytics module."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import django

# The bypass_rls marker and its collection-time opt-in come from core's
# conftest plugin (decisions rule 18), so every module suite shares one copy.
from quickscale_core.testing.pytest_plugin import (  # noqa: F401
    pytest_collection_modifyitems,
    pytest_configure,
)

MODULE_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = MODULE_ROOT / "src"

for path in (SRC_ROOT, MODULE_ROOT):
    path_str = str(path)
    if path_str not in sys.path:
        sys.path.insert(0, path_str)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tests.settings")
os.environ.pop("POSTHOG_API_KEY", None)
os.environ.pop("POSTHOG_HOST", None)
django.setup()
