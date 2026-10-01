"""Blog's guarded seam into the storage module's public services (rule 4)."""

from __future__ import annotations

from importlib import import_module
from typing import Any

from django.apps import apps as django_apps


def storage_services() -> Any | None:
    """Return storage's public service module, or ``None`` when it is absent.

    Module Conventions rule 4 routes a downward call through the lower
    module's ``services.py``, guarded by ``apps.is_installed``; the import
    stays lazy so blog remains importable without storage on the path.  Call
    sites fall back to their own local behavior when this returns ``None``,
    and never read a storage setting.
    """
    if not django_apps.is_installed("quickscale_modules_storage"):
        return None
    return import_module("quickscale_modules_storage.services")
