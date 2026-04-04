"""Shared pytest fixtures for the QuickScale analytics module."""

from __future__ import annotations

import os
from pathlib import Path
import sys

import django

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
