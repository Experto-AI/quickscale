"""Managed-file hashing and legacy ledger I/O for project state.

Owns the managed-file path constants, the SHA-256 helpers, and the
``file_hashes.yml`` compatibility ledger that the unified
:class:`~quickscale_core.project_state.ProjectStateManager` reads and writes.
The unified owner stays importable from ``quickscale_core.project_state``.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from quickscale_core.generator.ci_environment import CI_ENVIRONMENT_RELATIVE_PATH
from quickscale_core.generator.operations_page import OPERATIONS_PAGE_RELATIVE_PATH
from quickscale_core.project_state_records import ManagedFileHash
from quickscale_core.runtime.seam import (
    SEAM_DECLARATION_RELATIVE_PATH,
    SEAM_KEY_MANIFEST_RELATIVE_PATH,
)
from quickscale_core.schema.state_schema import ManagedFileRecord, StateError

if TYPE_CHECKING:
    from collections.abc import Iterable, MutableMapping

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

#: Package-relative directory holding module-declared managed outputs.
#: ``write_managed_wiring`` regenerates the whole directory, so every file in
#: it is QuickScale-managed: a local edit is drift, never an unmanaged extra.
MANAGED_OUTPUT_DIRECTORY = "quickscale_managed"

#: Byte-compiled caches are interpreter artifacts, not managed outputs.
_PYCACHE_DIRECTORY = "__pycache__"

# Default managed project files that ``quickscale apply`` regenerates outside
# the Python package, so they resolve against the project root rather than the
# package directory.  The theme's seam declaration and its key manifest render
# from the shipped module set (SA276); the CI environment file renders from
# each installed module's declared CI placeholders and the operations page
# from each installed module's declared operations text (SA286).
DEFAULT_MANAGED_PROJECT_PATHS: tuple[str, ...] = (
    SEAM_DECLARATION_RELATIVE_PATH,
    SEAM_KEY_MANIFEST_RELATIVE_PATH,
    CI_ENVIRONMENT_RELATIVE_PATH,
    OPERATIONS_PAGE_RELATIVE_PATH,
)


def _is_managed_output_file(path: Path, managed_root: Path) -> bool:
    """Return whether a file under the managed root is a generated output."""
    relative = path.relative_to(managed_root)
    if any(
        part == _PYCACHE_DIRECTORY or part.startswith(".") for part in relative.parts
    ):
        return False
    return path.suffix not in {".pyc", ".pyo"}


def resolve_managed_file_paths(package_name: str, project_path: Path) -> list[str]:
    """Return the repo-relative managed file paths of a generated project.

    The managed wiring files are package-relative; the managed project files
    are rooted at the project itself.  Every file a module wrote under
    ``<package>/quickscale_managed/`` is also resolved here: that directory is
    regenerated wholesale by ``write_managed_wiring``, so a file left in it is
    a QuickScale-managed output and a local edit must surface as drift.
    Byte-compiled caches and dot files are interpreter/tooling artifacts, not
    generated outputs.
    """
    paths = [
        f"{package_name}/{relative}" for relative in DEFAULT_MANAGED_WIRING_PATHS
    ] + list(DEFAULT_MANAGED_PROJECT_PATHS)
    managed_root = Path(project_path) / package_name / MANAGED_OUTPUT_DIRECTORY
    if managed_root.is_dir():
        paths.extend(
            path.relative_to(project_path).as_posix()
            for path in sorted(managed_root.rglob("*"))
            if path.is_file() and _is_managed_output_file(path, managed_root)
        )
    return list(dict.fromkeys(paths))


def prune_stale_managed_output_records(
    managed_files: MutableMapping[str, ManagedFileRecord],
    project_path: Path,
    package_name: str,
) -> None:
    """Drop records for module outputs the regenerated directory no longer holds.

    ``quickscale_managed/`` is rewritten wholesale, so a removed module leaves
    hash records for files that are gone.  A missing recorded file would read
    as drift forever; the capture sites run this only after regeneration, when
    every remaining output is on disk.
    """
    prefix = f"{package_name}/{MANAGED_OUTPUT_DIRECTORY}/"
    for path in [
        recorded
        for recorded in managed_files
        if recorded.startswith(prefix) and not (Path(project_path) / recorded).is_file()
    ]:
        del managed_files[path]


def record_managed_file_hashes(
    managed_files: MutableMapping[str, ManagedFileRecord],
    project_path: Path,
    package_name: str,
) -> dict[str, str]:
    """Record the current managed-file hashes in applied state.

    Apply, update, remove, and contract adoption all funnel through this
    function, so every path that rewrites the managed files refreshes the same
    record set under the same rules.  Stale module outputs are pruned before
    the new records land, so a removal does not leave a permanent drift
    warning for a file the regeneration just deleted.
    """
    hashes = compute_file_hashes(
        project_path, resolve_managed_file_paths(package_name, project_path)
    )
    prune_stale_managed_output_records(managed_files, project_path, package_name)
    for path, digest in hashes.items():
        managed_files[path] = ManagedFileRecord(path=path, hash=digest)
    return hashes


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
