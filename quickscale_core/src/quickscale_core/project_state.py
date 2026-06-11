"""Unified owner for QuickScale project state and module configuration.

Phase 3 unifies ``.quickscale/state.yml`` (authoritative applied state) and
``.quickscale/config.yml`` (legacy module tracking) under a single Python
owner without merging the two files on disk. The two YAML files keep their
existing serialization format and location so that the on-disk contract is
unchanged.

The unified surface provides:

* :class:`ProjectStateManager` — load/save both files and verify they agree
  on module versions.
* :class:`ManagedFileHash` — typed record of a managed file's last-known
  hash and the timestamp it was captured at.
* :func:`compute_file_hashes` — hash managed wiring files for drift detection.
* :func:`check_version_drift` — compare module versions in state vs config.

The existing ``StateManager`` (``.quickscale/state.yml``) and
``ModuleConfig``/``load_config``/``save_config`` (``.quickscale/config.yml``)
helpers are re-exported here so that callers can adopt a single import
without changing semantics. The lower-level helpers remain in their original
modules and continue to work without modification.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

# Re-export the schema/state surface so callers can use a single import.
from quickscale_core.config import (  # noqa: F401
    ConfigError,
    ModuleConfig,
    ModuleInfo,
    add_module,
    load_config,
    normalize_installed_version,
    remove_module,
    save_config,
    update_module_version,
)
from quickscale_core.schema.state_schema import (  # noqa: F401
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)

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


@dataclass
class ManagedFileHash:
    """Hash of a managed file captured at a known timestamp.

    Attributes:
        path: Repo-relative path of the managed file (forward slashes).
        hash: SHA-256 hex digest of the file contents at capture time.
        applied_at: ISO-8601 timestamp when the hash was recorded.

    """

    path: str
    hash: str
    applied_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, str]:
        """Return a YAML-friendly dictionary representation."""
        return {
            "path": self.path,
            "hash": self.hash,
            "applied_at": self.applied_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, str]) -> "ManagedFileHash":
        """Build a :class:`ManagedFileHash` from a YAML mapping."""
        return cls(
            path=str(data["path"]),
            hash=str(data["hash"]),
            applied_at=str(data.get("applied_at", datetime.now().isoformat())),
        )


@dataclass
class VersionDriftWarning:
    """A single module version disagreement between state and config.

    The two sources are:
    * ``state_version`` — ``state.modules[module].version``
    * ``config_version`` — ``config.modules[module].installed_version``

    Only modules present in both sources are considered; modules present in
    only one source are reported separately through the existing
    ``StateManager.verify_filesystem`` drift channel.
    """

    module: str
    state_version: str | None
    config_version: str | None

    @property
    def message(self) -> str:
        """Human-readable drift description."""
        return (
            f"Module '{self.module}': state version is "
            f"{self.state_version!r} but config version is "
            f"{self.config_version!r}"
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
        except (KeyError, TypeError, ValueError):
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


def check_version_drift(
    state: QuickScaleState | None,
    config: ModuleConfig | None,
) -> list[VersionDriftWarning]:
    """Return a list of module-version disagreements between state and config.

    Only modules present in both sources produce a warning; modules that
    exist in only one source are intentionally ignored here because that
    situation is already reported through ``StateManager.verify_filesystem``
    and the existing delta computations. Both ``state`` and ``config`` may
    be ``None`` to indicate missing files; in that case the result is empty.

    Args:
        state: Loaded :class:`QuickScaleState` (or ``None`` if no state file).
        config: Loaded :class:`ModuleConfig` (or ``None`` if no config file).

    Returns:
        List of :class:`VersionDriftWarning` entries for modules whose
        normalized version disagrees between the two sources.

    """
    if state is None or config is None:
        return []

    warnings: list[VersionDriftWarning] = []
    state_modules = state.modules or {}
    config_modules = config.modules or {}

    common = sorted(set(state_modules) & set(config_modules))
    for module_name in common:
        state_version = normalize_installed_version(state_modules[module_name].version)
        config_info = config_modules[module_name]
        config_version = normalize_installed_version(config_info.installed_version)

        if state_version == config_version:
            continue

        warnings.append(
            VersionDriftWarning(
                module=module_name,
                state_version=state_version,
                config_version=config_version,
            )
        )

    return warnings


class ProjectStateManager:
    """Unified owner of the two QuickScale-managed YAML files.

    The two files keep their on-disk format and location:

    * ``.quickscale/state.yml`` — authoritative applied state
      (delegated to :class:`StateManager`).
    * ``.quickscale/config.yml`` — legacy module tracking
      (delegated to ``quickscale_core.config`` helpers).

    The class is additive: it does not replace the existing per-file
    loaders/savers, it just exposes a single entry point that can act on
    both. The single-file helpers continue to work without modification.
    """

    def __init__(self, project_path: Path):
        """Initialize the unified manager.

        Args:
            project_path: Root of the generated project.

        """
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / ".quickscale"
        self.state_file = self.state_dir / "state.yml"
        self.config_file = self.state_dir / "config.yml"
        self.file_hashes_file = self.state_dir / FILE_HASHES_FILENAME

        # Reuse existing managers so behavior stays identical.
        self._state_manager = StateManager(self.project_path)

    # ------------------------------------------------------------------
    # State (.quickscale/state.yml)
    # ------------------------------------------------------------------

    def load_state(self) -> QuickScaleState | None:
        """Load ``.quickscale/state.yml`` via the existing ``StateManager``."""
        return self._state_manager.load()

    def save_state(self, state: QuickScaleState) -> None:
        """Persist ``.quickscale/state.yml`` via the existing ``StateManager``."""
        self._state_manager.save(state)

    # ------------------------------------------------------------------
    # Config (.quickscale/config.yml)
    # ------------------------------------------------------------------

    def load_config(self) -> ModuleConfig:
        """Load ``.quickscale/config.yml`` via the existing helpers.

        Returns the default empty config when the file is missing.
        """
        return load_config(self.project_path)

    def save_config(self, config: ModuleConfig) -> None:
        """Persist ``.quickscale/config.yml`` via the existing helpers."""
        save_config(config, self.project_path)

    # ------------------------------------------------------------------
    # Managed file hashes (.quickscale/file_hashes.yml)
    # ------------------------------------------------------------------

    def load_managed_file_hashes(self) -> dict[str, ManagedFileHash]:
        """Load the managed-file hash ledger, returning empty on absence."""
        return _read_managed_file_hashes(self.project_path)

    def save_managed_file_hashes(
        self,
        hashes: dict[str, ManagedFileHash] | dict[str, str],
    ) -> None:
        """Persist a managed-file hash ledger.

        Accepts either :class:`ManagedFileHash` records or plain hex
        digest strings; when strings are given the current timestamp is
        recorded for each path.
        """
        if not hashes:
            return

        normalized: dict[str, ManagedFileHash] = {}
        for path, value in hashes.items():
            normalized_path = str(path).replace("\\", "/").lstrip("/")
            if isinstance(value, ManagedFileHash):
                normalized[normalized_path] = value
            else:
                normalized[normalized_path] = ManagedFileHash(
                    path=normalized_path,
                    hash=str(value),
                )
        _write_managed_file_hashes(self.project_path, normalized)

    def capture_managed_file_hashes(
        self,
        file_paths: Iterable[str],
    ) -> dict[str, ManagedFileHash]:
        """Compute hashes for the given managed files and persist them.

        Returns the full set of persisted hash records. Paths whose files
        do not exist at capture time are omitted (callers should treat
        missing files as drift and surface a separate warning).
        """
        computed = compute_file_hashes(self.project_path, file_paths)
        records = {
            path: ManagedFileHash(path=path, hash=digest)
            for path, digest in computed.items()
        }
        if records:
            self.save_managed_file_hashes(records)
        return records

    def detect_managed_file_drift(
        self,
        file_paths: Iterable[str] | None = None,
    ) -> list[ManagedFileHash]:
        """Return a list of managed files that have drifted since last apply.

        A file is considered drifted if:

        * it was hashed at last apply but no longer exists, or
        * it was hashed at last apply and its current content hash differs
          from the recorded hash.

        The list contains the *recorded* :class:`ManagedFileHash` so the
        caller can report both the path and the expected hash. The current
        hash, if any, is recomputed here and not stored on the record.
        """
        stored = self.load_managed_file_hashes()
        if not stored:
            return []

        candidates = list(file_paths) if file_paths is not None else list(stored)
        normalized_targets = {str(p).replace("\\", "/").lstrip("/") for p in candidates}

        drifted: list[ManagedFileHash] = []
        for path, record in stored.items():
            if normalized_targets and path not in normalized_targets:
                continue
            current = self.project_path / path
            if not current.is_file():
                drifted.append(record)
                continue
            try:
                current_hash = hash_managed_file(current)
            except OSError:
                drifted.append(record)
                continue
            if current_hash != record.hash:
                drifted.append(record)
        return drifted

    # ------------------------------------------------------------------
    # Cross-file consistency
    # ------------------------------------------------------------------

    def verify_consistency(self) -> dict[str, list[VersionDriftWarning]]:
        """Cross-check state and config and report version disagreements.

        Returns:
            A mapping with a single key ``"version_drift"`` whose value is
            a list of :class:`VersionDriftWarning` entries. The wrapper
            dict leaves room for additional consistency categories without
            changing the call sites.

        Raises:
            StateError: If ``.quickscale/config.yml`` cannot be loaded
                because the file is malformed. The boundary normalizes
                :class:`quickscale_core.config.ConfigError` (and the
                underlying :class:`yaml.YAMLError`) into :class:`StateError`
                so that downstream CLI surfaces only need to handle one
                error type for both ``state.yml`` and ``config.yml``.
        """
        state = self.load_state()
        try:
            config = self.load_config()
        except (ConfigError, OSError, yaml.YAMLError) as error:
            raise StateError(
                f"Failed to load .quickscale/config.yml: {error}"
            ) from error
        return {
            "version_drift": check_version_drift(state, config),
        }


__all__ = [
    # Re-exports from quickscale_core.config
    "ConfigError",
    "ModuleConfig",
    "ModuleInfo",
    "add_module",
    "load_config",
    "normalize_installed_version",
    "remove_module",
    "save_config",
    "update_module_version",
    # Re-exports from quickscale_core.schema.state_schema
    "ModuleState",
    "ProjectState",
    "QuickScaleState",
    "StateError",
    "StateManager",
    # New unified surface
    "DEFAULT_MANAGED_WIRING_PATHS",
    "FILE_HASHES_FILENAME",
    "ManagedFileHash",
    "ProjectStateManager",
    "VersionDriftWarning",
    "check_version_drift",
    "compute_file_hashes",
    "hash_managed_file",
]
