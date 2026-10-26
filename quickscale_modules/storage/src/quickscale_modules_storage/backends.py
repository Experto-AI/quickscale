"""S3-compatible storage backends owned by the storage module."""

from __future__ import annotations

import pathlib
import posixpath
from uuid import uuid4

from storages.backends.s3 import S3Storage
from storages.utils import clean_name

#: Length of the per-save random token in the common case.
_UNIQUE_TOKEN_LENGTH = 12
#: Fewer available stem characters than this cannot carry a meaningful token.
_MIN_RANDOM_STEM_LENGTH = 6


class UniqueKeyS3Storage(S3Storage):
    """S3-compatible storage that allocates a fresh object key for every save.

    ``file_overwrite = False`` only makes ``Storage.save`` check whether a key
    exists before writing.  Two uploads that race that check both see the same
    free key, and the later write replaces the earlier object.  This backend
    appends a random token to every allocated name before the check, so two
    concurrent saves of the same filename necessarily choose different keys.

    The caller's ``max_length`` contract is preserved.  When the directory and
    extension leave at least :data:`_MIN_RANDOM_STEM_LENGTH` characters, the
    token consumes them and the original stem is truncated as needed.  A field
    whose limit leaves less room than that cannot host a per-save token; it
    keeps Django's stock allocation so previously valid uploads still succeed.
    Django's default media ``max_length`` (100) is far above the floor.
    """

    def get_available_name(self, name: str, max_length: int | None = None) -> str:
        """Return a key whose stem carries a per-save random token."""
        candidate = self._unique_candidate(clean_name(name), max_length)
        return super().get_available_name(candidate, max_length=max_length)

    @staticmethod
    def _unique_candidate(name: str, max_length: int | None) -> str:
        """Build the tokenised name, or keep *name* below the token floor."""
        directory, filename = posixpath.split(name)
        extension = "".join(pathlib.PurePosixPath(filename).suffixes)
        stem = filename.removesuffix(extension)

        if max_length is None:
            token = uuid4().hex[:_UNIQUE_TOKEN_LENGTH]
            return posixpath.join(directory, f"{stem}_{token}{extension}")

        prefix_length = len(directory) + (1 if directory else 0)
        available = max_length - prefix_length - len(extension)
        if available < _MIN_RANDOM_STEM_LENGTH:
            # No room for a meaningful random token: preserve Django's
            # stock contract for this field rather than rejecting its input.
            return name

        token_length = min(_UNIQUE_TOKEN_LENGTH, available)
        token = uuid4().hex[:token_length]
        stem_length = available - token_length
        if stem_length >= 2:
            return posixpath.join(
                directory,
                f"{stem[: stem_length - 1]}_{token}{extension}",
            )
        return posixpath.join(directory, f"{token}{extension}")
