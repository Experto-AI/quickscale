"""QuickScale State Schema

Dataclasses and operations for .quickscale/state.yml state tracking.
Implements Terraform-style state management for incremental applies.

Phase 2 (M2) extends the state schema with consolidated sub-sections for
module-tracking metadata (previously in ``config.yml``) and managed-file
drift/hash records (previously in ``file_hashes.yml``).  The new fields
are optional so that existing ``state.yml`` files without consolidated
sections continue to load unchanged.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from quickscale_core.config import normalize_installed_version
from quickscale_core.contracts.module_options import sanitize_module_options


class StateError(Exception):
    """State file operation error"""

    pass


@dataclass
class ModuleState:
    """State tracking for an embedded module.

    Phase 2 adds optional tracking fields (``prefix``, ``branch``,
    ``installed_at``) that consolidate the module-tracking metadata
    previously stored only in ``.quickscale/config.yml``.  When these
    fields are present the state file is self-contained; when absent the
    unified :class:`~quickscale_core.project_state.ProjectStateManager`
    can read-through import from the legacy config file.
    """

    name: str
    version: str | None = None
    commit_sha: str | None = None
    embedded_at: str = field(default_factory=lambda: datetime.now().isoformat())
    options: dict[str, Any] = field(default_factory=dict)
    # Consolidated tracking fields (from legacy config.yml).
    prefix: str | None = None
    branch: str | None = None
    installed_at: str | None = None

    def __post_init__(self) -> None:
        self.version = normalize_installed_version(self.version)
        self.options = sanitize_module_options(self.name, self.options)

    @property
    def has_consolidated_tracking(self) -> bool:
        """Return True when the module carries full consolidated tracking."""
        return (
            self.prefix is not None
            and self.branch is not None
            and self.installed_at is not None
        )


@dataclass
class ManagedFileRecord:
    """Consolidated managed-file hash record stored inside ``state.yml``.

    This is the state-schema counterpart of
    :class:`~quickscale_core.project_state.ManagedFileHash`.  When the
    ``managed_files`` section is present in ``state.yml`` the separate
    ``file_hashes.yml`` ledger is no longer needed.

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
    def from_dict(cls, data: dict[str, Any]) -> "ManagedFileRecord":
        """Build a :class:`ManagedFileRecord` from a YAML mapping."""
        return cls(
            path=str(data["path"]),
            hash=str(data["hash"]),
            applied_at=str(data.get("applied_at", datetime.now().isoformat())),
        )


@dataclass
class ProjectState:
    """State tracking for the generated project.

    SA10.1 adds ``project_contract``: the QuickScale contract version that
    the project was generated (or last applied) against.  Absent on legacy
    state files — loaded as ``None`` for backward compatibility.
    """

    slug: str
    package: str
    theme: str
    project_contract: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_applied: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class QuickScaleState:
    """Complete QuickScale applied state from .quickscale/state.yml.

    Phase 2 adds an optional ``managed_files`` mapping that consolidates
    the managed-file hash ledger into the authoritative state file.
    """

    version: str
    project: ProjectState
    modules: dict[str, ModuleState] = field(default_factory=dict)
    managed_files: dict[str, ManagedFileRecord] = field(default_factory=dict)

    @property
    def has_consolidated_modules(self) -> bool:
        """Return True when every module carries consolidated tracking."""
        if not self.modules:
            return True  # vacuously — no modules to track
        return all(m.has_consolidated_tracking for m in self.modules.values())

    @property
    def has_consolidated_managed_files(self) -> bool:
        """Return True when the managed_files section is populated.

        An empty mapping with no legacy ``file_hashes.yml`` on disk is
        considered fully consolidated (there is nothing to import).
        """
        # The presence of the section (even empty) means consolidation
        # has happened.  Callers that need to distinguish "section absent"
        # from "section empty" should check the raw YAML instead.
        return True  # The field always exists; see ProjectStateManager for
        # the on-disk presence check.


class StateManager:
    """Manages state file operations for QuickScale projects"""

    def __init__(self, project_path: Path):
        """Initialize StateManager for a project

        Args:
            project_path: Path to the project root directory

        """
        self.project_path = Path(project_path)
        self.state_dir = self.project_path / ".quickscale"
        self.state_file = self.state_dir / "state.yml"

    def load(self) -> QuickScaleState | None:
        """Load state from .quickscale/state.yml

        Returns:
            QuickScaleState object if state file exists, None otherwise

        Raises:
            StateError: If state file exists but cannot be parsed

        """
        if not self.state_file.exists():
            return None

        try:
            with open(self.state_file) as f:
                data = yaml.safe_load(f)

            if not isinstance(data, dict):
                raise StateError("State file must be a YAML mapping")

            # Parse project state
            project_data = data.get("project", {})
            if not isinstance(project_data, dict):
                raise StateError("'project' in state file must be a mapping")

            if "name" in project_data and (
                "slug" not in project_data or "package" not in project_data
            ):
                raise StateError(
                    "Legacy state schema detected (project.name). "
                    "This version requires project.slug and project.package. "
                    "Regenerate state by re-running 'quickscale apply' with a "
                    "quickscale.yml that defines project.slug/project.package."
                )

            project_slug = project_data.get("slug")
            project_package = project_data.get("package")
            project_theme = project_data.get("theme")

            if not isinstance(project_slug, str) or not project_slug:
                raise StateError("State file project.slug must be a non-empty string")

            if not isinstance(project_package, str) or not project_package:
                raise StateError(
                    "State file project.package must be a non-empty string"
                )

            if not isinstance(project_theme, str) or not project_theme:
                raise StateError("State file project.theme must be a non-empty string")

            project = ProjectState(
                slug=project_slug,
                package=project_package,
                theme=project_theme,
                project_contract=project_data.get("project_contract"),
                created_at=project_data.get("created_at", datetime.now().isoformat()),
                last_applied=project_data.get(
                    "last_applied", datetime.now().isoformat()
                ),
            )

            # Parse module states
            modules_data = data.get("modules", {})
            if not isinstance(modules_data, dict):
                raise StateError("'modules' in state file must be a mapping")

            modules: dict[str, ModuleState] = {}
            for module_name, module_info in modules_data.items():
                if not isinstance(module_info, dict):
                    raise StateError(f"Module '{module_name}' state must be a mapping")

                modules[module_name] = ModuleState(
                    name=module_name,
                    version=normalize_installed_version(module_info.get("version")),
                    commit_sha=module_info.get("commit_sha"),
                    embedded_at=module_info.get(
                        "embedded_at", datetime.now().isoformat()
                    ),
                    options=sanitize_module_options(
                        module_name,
                        module_info.get("options") or {},
                    ),
                    # Phase 2 consolidated tracking fields (optional).
                    prefix=module_info.get("prefix"),
                    branch=module_info.get("branch"),
                    installed_at=module_info.get("installed_at"),
                )

            # Parse managed-file records (Phase 2 consolidated section).
            managed_files: dict[str, ManagedFileRecord] = {}
            managed_files_data = data.get("managed_files")
            if managed_files_data is not None:
                if isinstance(managed_files_data, list):
                    for entry in managed_files_data:
                        if not isinstance(entry, dict):
                            continue
                        try:
                            record = ManagedFileRecord.from_dict(entry)
                        except (KeyError, TypeError, ValueError):
                            continue
                        managed_files[record.path] = record
                elif isinstance(managed_files_data, dict):
                    for file_path, file_info in managed_files_data.items():
                        if not isinstance(file_info, dict):
                            continue
                        try:
                            record = ManagedFileRecord.from_dict(
                                {**file_info, "path": file_path}
                            )
                        except (KeyError, TypeError, ValueError):
                            continue
                        managed_files[record.path] = record

            return QuickScaleState(
                version=data.get("version", "1"),
                project=project,
                modules=modules,
                managed_files=managed_files,
            )
        except yaml.YAMLError as e:
            raise StateError(f"Failed to parse state file: {e}") from e
        except Exception as e:
            raise StateError(f"Failed to load state: {e}") from e

    def save(self, state: QuickScaleState) -> None:
        """Save state to .quickscale/state.yml atomically

        Args:
            state: QuickScaleState object to save

        Raises:
            StateError: If state cannot be saved

        """
        try:
            # Ensure .quickscale directory exists
            self.state_dir.mkdir(parents=True, exist_ok=True)

            # Build state data
            data: dict[str, Any] = {
                "version": state.version,
                "project": {
                    "slug": state.project.slug,
                    "package": state.project.package,
                    "theme": state.project.theme,
                    "project_contract": state.project.project_contract,
                    "created_at": state.project.created_at,
                    "last_applied": state.project.last_applied,
                },
            }

            if state.modules:
                data["modules"] = {
                    name: {
                        k: v
                        for k, v in {
                            "version": normalize_installed_version(module.version),
                            "commit_sha": module.commit_sha,
                            "embedded_at": module.embedded_at,
                            "options": (
                                sanitize_module_options(name, module.options)
                                if module.options
                                else None
                            ),
                            # Phase 2 consolidated tracking fields.
                            "prefix": module.prefix,
                            "branch": module.branch,
                            "installed_at": module.installed_at,
                        }.items()
                        if v is not None
                    }
                    for name, module in state.modules.items()
                }

            # Phase 2: write consolidated managed-file records when present.
            if state.managed_files:
                data["managed_files"] = [
                    record.to_dict() for record in state.managed_files.values()
                ]

            # Write atomically using temporary file
            temp_file = self.state_file.with_suffix(".tmp")
            try:
                with open(temp_file, "w") as f:
                    yaml.dump(data, f, default_flow_style=False, sort_keys=False)

                # Atomic rename (POSIX guarantees atomicity)
                temp_file.replace(self.state_file)
            except Exception:
                # Clean up temp file on error
                if temp_file.exists():
                    temp_file.unlink()
                raise

        except Exception as e:
            raise StateError(f"Failed to save state: {e}") from e

    def flush_empty_consolidated_sections(self) -> None:
        """Rewrite state.yml with explicit empty consolidated sections.

        After a removal that empties ``modules`` or ``managed_files``,
        :meth:`save` omits those keys (they are empty collections).  Downstream
        readers use the *absence* of consolidated keys to decide whether
        legacy ``config.yml`` / ``file_hashes.yml`` should be read-through
        imported.  An empty-but-authoritative state file must therefore
        write explicit ``modules: {}`` / ``managed_files: []`` markers so
        that readers can distinguish "M2 has spoken — nothing tracked"
        from "pre-M2 state that never had consolidated sections."

        This is a no-op when the state file already contains explicit
        consolidated keys.
        """
        if not self.state_file.exists():
            return
        try:
            with open(self.state_file) as fh:
                data = yaml.safe_load(fh) or {}
        except (yaml.YAMLError, OSError):
            return

        if not isinstance(data, dict):
            return

        needs_write = False
        if "modules" not in data:
            data["modules"] = {}
            needs_write = True
        if "managed_files" not in data:
            data["managed_files"] = []
            needs_write = True

        if not needs_write:
            return

        temp_file = self.state_file.with_suffix(".tmp")
        try:
            with open(temp_file, "w") as fh:
                yaml.dump(data, fh, default_flow_style=False, sort_keys=False)
            temp_file.replace(self.state_file)
        except Exception:
            if temp_file.exists():
                temp_file.unlink()
            raise

    def update(self, state: QuickScaleState) -> None:
        """Update state file with new last_applied timestamp and save

        Args:
            state: QuickScaleState object to update and save

        """
        state.project.last_applied = datetime.now().isoformat()
        self.save(state)

    def verify_filesystem(self) -> dict[str, list[str]]:
        """Verify state matches filesystem and detect drift

        Returns:
            Dictionary with drift information:
            - 'orphaned_modules': Modules in filesystem but not in state
            - 'missing_modules': Modules in state but not in filesystem

        """
        state = self.load()
        if state is None:
            return {"orphaned_modules": [], "missing_modules": []}

        modules_dir = self.project_path / "modules"
        orphaned_modules = []
        missing_modules = []

        # Check for orphaned modules (in filesystem but not in state)
        if modules_dir.exists():
            for module_dir in modules_dir.iterdir():
                if module_dir.is_dir() and module_dir.name not in state.modules:
                    orphaned_modules.append(module_dir.name)

        # Check for missing modules (in state but not in filesystem)
        for module_name in state.modules.keys():
            module_path = modules_dir / module_name
            if not module_path.exists():
                missing_modules.append(module_name)

        return {
            "orphaned_modules": orphaned_modules,
            "missing_modules": missing_modules,
        }
