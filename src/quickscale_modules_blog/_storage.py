"""Blog's seam into the storage module's public services (rule 4).

Blog declares ``storage`` in ``required_modules`` (rule 5), so the required
module is imported directly and asked only ``is_enabled()`` (rule 43); call
sites keep their own local fallback while storage is switched off, and never
read a storage setting.
"""

from __future__ import annotations

from typing import Any


def storage_services() -> Any | None:
    """Return storage's public service module, or ``None`` while storage is off.

    The import stays lazy so blog stays importable without storage on the
    Python path, and the required module's ``is_enabled()`` is the only
    question (rule 43).  Call sites fall back to their own local behavior when
    this returns ``None``, and never read a storage setting.
    """
    import quickscale_modules_storage.services as services

    if not services.is_enabled():
        return None
    return services
