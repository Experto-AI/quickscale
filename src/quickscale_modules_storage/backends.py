"""S3-compatible storage backends owned by the storage module."""

from __future__ import annotations

import pathlib
import posixpath
from uuid import uuid4

from storages.backends.s3 import S3Storage
from storages.utils import clean_name


class UniqueKeyS3Storage(S3Storage):
    """S3-compatible storage that allocates a fresh object key for every save.

    ``file_overwrite = False`` only makes ``Storage.save`` check whether a key
    exists before writing.  Two uploads that race that check both see the same
    free key, and the later write replaces the earlier object.  This backend
    appends a random token to every allocated name before the check, so two
    concurrent saves of the same filename necessarily choose different keys.

    The caller's ``max_length`` contract is preserved: the delegated
    ``Storage.get_available_name`` trims the stem when needed and appends its
    own random alternative if the token itself collides.
    """

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        """Return a key whose stem carries a per-save random token."""
        cleaned = clean_name(name)
        directory, filename = posixpath.split(cleaned)
        extension = "".join(pathlib.PurePosixPath(filename).suffixes)
        stem = filename.removesuffix(extension)
        candidate = posixpath.join(
            directory,
            f"{stem}_{uuid4().hex[:12]}{extension}",
        )
        return super().get_available_name(candidate, max_length=max_length)
