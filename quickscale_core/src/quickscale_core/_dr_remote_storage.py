"""Private remote S3 storage adapter — isolated upload / delete operations.

SA89b Phase 1: ``S3Storage`` and Django ``File`` imports are isolated here so
the orchestration module does not need to import them at module level.
This module is intentionally placed outside ``DR_ENGINE_ROOT`` so the
unconditional AST gate over ``dr_engine/`` remains satisfiable after Phase 1.

This module is NOT part of the public runtime surface and is never
re-exported in ``__all__``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def upload_file_to_s3(
    local_path: Path,
    requested_key: str,
    storage_options: dict[str, Any],
) -> str:
    """Upload *local_path* to S3 at *requested_key*.

    Uses a function-local ``S3Storage`` constructed from a defensively-copied
    *storage_options* mapping, opens *local_path* as a binary stream, wraps
    it in Django ``File``, and calls ``storage.save()`` exactly once.

    Never materializes the full file into memory: no ``read_bytes()``,
    ``read(-1)``, ``BytesIO``, or full-buffer pattern.

    Returns *requested_key* unchanged (the backend return value is ignored).

    Exceptions from import, ``open()``, the ``S3Storage`` constructor,
    Django ``File``, or the backend are propagated unchanged.
    """
    from storages.backends.s3 import S3Storage
    from django.core.files import File

    # Defensive copy — never mutate the caller's mapping
    options = dict(storage_options)

    storage = S3Storage(**options)
    with local_path.open("rb") as handle:
        django_file = File(handle, name=local_path.name)
        storage.save(requested_key, django_file)
    return requested_key


def delete_s3_key(
    requested_key: str,
    storage_options: dict[str, Any],
) -> None:
    """Delete the S3 object at *requested_key*.

    Uses a function-local ``S3Storage`` constructed from a defensively-copied
    *storage_options* mapping and calls ``storage.delete()`` exactly once.

    No normalization, retry, wrapping, or return value.

    Exceptions from import, constructor, or the backend are propagated
    unchanged.
    """
    from storages.backends.s3 import S3Storage

    options = dict(storage_options)
    storage = S3Storage(**options)
    storage.delete(requested_key)
