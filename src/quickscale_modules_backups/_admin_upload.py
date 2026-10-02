"""Crash-safe upload copy helpers for the backups admin restore flow.

Imported by ``quickscale_modules_backups.services``, which keeps the
staging, guard, and policy lookups beside
``prepare_admin_uploaded_restore_artifact`` because callers and tests patch
those names at the services module.
"""

from __future__ import annotations

import os
from pathlib import Path
from tempfile import mkstemp
from typing import Any

from quickscale_core.runtime import BackupError


def _copy_admin_upload_crash_safe(
    source_path: Path,
    local_path: Path,
    local_dir: Path,
) -> None:
    """Copy *source_path* onto *local_path* atomically through a temp file.

    The temp file is written through its file descriptor (fd) — never
    closed and reopened by pathname — so a swap-to-symlink race between
    close and reopen is eliminated.
    """
    try:
        fd, tmp_path = mkstemp(dir=local_dir)
    except OSError as exc:
        raise BackupError(f"Failed to stage the restore artifact: {exc}") from exc
    try:
        with open(source_path, "rb") as src_f:
            _write_all_bytes(fd, src_f)
        os.fsync(fd)
        os.replace(tmp_path, local_path)
    except OSError as exc:
        _remove_file_quietly(tmp_path)
        raise BackupError(f"Failed to materialize the restore artifact: {exc}") from exc
    except Exception:
        _remove_file_quietly(tmp_path)
        raise
    finally:
        os.close(fd)


def _write_all_bytes(fd: int, src_f: Any) -> None:
    """Write every byte of *src_f* to *fd*, retrying short writes.

    CR-SA53-REV-002: Retry short ``os.write()`` returns using
    memoryview slicing so a partial write never silently truncates the
    artifact.
    """
    while True:
        buf = src_f.read(65536)
        if not buf:
            break
        view = memoryview(buf)
        while view:
            view = view[os.write(fd, view) :]


def _remove_file_quietly(path: str | Path) -> None:
    """Remove *path*, ignoring a missing-file error."""
    try:
        os.unlink(path)
    except OSError:
        pass
