"""QuickScale State Schema

Dataclasses and operations for .quickscale/state.yml state tracking.
Implements Terraform-style state management for incremental applies.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


class StateError(Exception):
    """State file operation error"""

    pass


@dataclass
class ModuleState:
    """State tracking for an embedded module"""

    name: str
    version: str | None = None
    commit_sha: str | None = None
    embedded_at: str = field(default_factory=lambda: datetime.now().isoformat())
    options: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProjectState:
    """State tracking for the generated project"""

    name: str
    theme: str
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_applied: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class QuickScaleState:
    """Complete QuickScale applied state from .quickscale/state.yml"""

    version: str
    project: ProjectState
    modules: dict[str, ModuleState] = field(default_factory=dict)


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

            project = ProjectState(
                name=project_data.get("name", ""),
                theme=project_data.get("theme", ""),
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
                    version=module_info.get("version"),
                    commit_sha=module_info.get("commit_sha"),
                    embedded_at=module_info.get(
                        "embedded_at", datetime.now().isoformat()
                    ),
                    options=module_info.get("options", {}),
                )

            return QuickScaleState(
                version=data.get("version", "1"),
                project=project,
                modules=modules,
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
                    "name": state.project.name,
                    "theme": state.project.theme,
                    "created_at": state.project.created_at,
                    "last_applied": state.project.last_applied,
                },
            }

            if state.modules:
                data["modules"] = {
                    name: {
                        "version": module.version,
                        "commit_sha": module.commit_sha,
                        "embedded_at": module.embedded_at,
                        "options": module.options if module.options else None,
                    }
                    for name, module in state.modules.items()
                }

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
