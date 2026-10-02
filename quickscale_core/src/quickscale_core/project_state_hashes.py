"""Managed-file hashing and legacy ledger I/O for project state.

Owns the managed wiring constants, the SHA-256 helpers, and the
``file_hashes.yml`` compatibility ledger that the unified
:class:`~quickscale_core.project_state.ProjectStateManager` reads and writes.
The unified owner stays importable from ``quickscale_core.project_state``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from quickscale_core.project_state_records import ManagedFileHash
from quickscale_core.schema.state_schema import StateError

if TYPE_CHECKING:
    from collections.abc import Iterable

# File name for the separate managed-file hash ledger.
# Lives under .quickscale/ alongside state.yml and config.yml.
FILE_HASHES_FILENAME = "file_hashes.yml"

# Chunk size used when hashing managed files. 64 KiB keeps memory low and
# matches the I/O pattern of the small wiring files this writes to.
_HASH_CHUNK_SIZE = 65536

# Default managed wiring files produced by ``quickscale apply`` that we
# track for drift. Paths are repo-relative (forward slashes) to match the
# canonical layout emitted by ``write_managed_wiring``.
DEFAULT_MANAGED_WIRING_PATHS: tuple[str, ...] = (
    "settings/modules.py",
    "urls_modules.py",
)


def hash_managed_file(file_path: Path) -> str:
    """Return the SHA-256 hex digest of a single managed file.

    Args:
        file_path: Absolute path to the file to hash.

    Returns:
        Hex digest string.

    Raises:
        FileNotFoundError: If the file does not exist.
        OSError: For any other I/O error reading the file.

    """
    sha = hashlib.sha256()
    with open(file_path, "rb") as handle:
        for chunk in iter(lambda: handle.read(_HASH_CHUNK_SIZE), b""):
            sha.update(chunk)
    return sha.hexdigest()


def compute_file_hashes(
    project_path: Path,
    file_paths: Iterable[str],
) -> dict[str, str]:
    """Compute SHA-256 hashes for the given managed files.

    Args:
        project_path: Root of the generated project.
        file_paths: Iterable of repo-relative paths to managed files.

    Returns:
        Mapping of repo-relative path to hex digest. Paths whose files do
        not exist are simply omitted from the result (callers should
        treat missing managed files as drift).

    """
    hashes: dict[str, str] = {}
    base = Path(project_path)
    for raw_path in file_paths:
        # Normalize to forward-slash repo-relative form for stable keys.
        normalized = str(raw_path).replace("\\", "/").lstrip("/")
        if not normalized:
            continue
        candidate = base / normalized
        if not candidate.is_file():
            continue
        hashes[normalized] = hash_managed_file(candidate)
    return hashes


def _read_managed_file_hashes(project_path: Path) -> dict[str, ManagedFileHash]:
    """Load the managed-file hash ledger from disk, if present."""
    hashes_path = Path(project_path) / ".quickscale" / FILE_HASHES_FILENAME
    if not hashes_path.exists():
        return {}

    try:
        with open(hashes_path) as handle:
            data = yaml.safe_load(handle) or {}
    except yaml.YAMLError as error:
        raise StateError(f"Failed to parse {FILE_HASHES_FILENAME}: {error}") from error

    if not isinstance(data, dict):
        return {}

    files_section = data.get("files")
    if not isinstance(files_section, list):
        return {}

    hashes: dict[str, ManagedFileHash] = {}
    for entry in files_section:
        if not isinstance(entry, dict):
            continue
        try:
            record = ManagedFileHash.from_dict(entry)
        except KeyError, TypeError, ValueError:
            continue
        hashes[record.path] = record
    return hashes


def _write_managed_file_hashes(
    project_path: Path,
    hashes: dict[str, ManagedFileHash],
) -> None:
    """Persist the managed-file hash ledger to disk atomically."""
    base = Path(project_path)
    target_dir = base / ".quickscale"
    target_path = target_dir / FILE_HASHES_FILENAME

    payload = {
        "version": "1",
        "files": [record.to_dict() for record in hashes.values()],
    }

    target_dir.mkdir(parents=True, exist_ok=True)
    temp_path = target_path.with_suffix(".tmp")
    try:
        with open(temp_path, "w") as handle:
            yaml.dump(payload, handle, default_flow_style=False, sort_keys=False)
        temp_path.replace(target_path)
    except Exception:
        if temp_path.exists():
            try:
                temp_path.unlink()
            except OSError:
                pass
        raise
