"""Helpers for syncing generated-project Poetry dependencies for embedded modules."""

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from quickscale_core.manifest.loader import ManifestError, get_manifest_for_module


_DEPENDENCY_NAME_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
_VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+)*)")
_STORAGE_CLOUD_BACKENDS = frozenset({"r2", "s3"})
_STORAGE_CLOUD_DEPENDENCIES = frozenset({"boto3", "django-storages"})
_STORAGE_CLOUD_EXTRA = "cloud"


class DependencySyncError(Exception):
    """Raised when generated-project dependency synchronization cannot proceed."""


@dataclass(frozen=True)
class ProjectDependencySyncResult:
    """Summary of dependency entries added to a generated project."""

    added_path_dependencies: list[str] = field(default_factory=list)
    added_package_dependencies: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        """Return True when the project pyproject.toml was updated."""
        return bool(self.added_path_dependencies or self.added_package_dependencies)


def resolve_embedded_module_install_path(
    project_path: Path, module: str
) -> Path | None:
    """Return the installable package path for an embedded module, if any."""
    module_dir = project_path / "modules" / module
    if not module_dir.exists():
        return None

    nested_path = module_dir / "quickscale_modules" / module
    if nested_path.exists() and (nested_path / "pyproject.toml").exists():
        return nested_path

    if (module_dir / "pyproject.toml").exists():
        return module_dir

    return None


def _load_toml_file(path: Path) -> dict[str, Any]:
    """Load a TOML document from disk."""
    try:
        with open(path, "rb") as file_handle:
            data = tomllib.load(file_handle)
    except OSError as error:
        raise DependencySyncError(
            f"Failed to read TOML file {path}: {error}"
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise DependencySyncError(f"Invalid TOML in {path}: {error}") from error

    if not isinstance(data, dict):
        raise DependencySyncError(f"TOML file {path} did not parse to a mapping")
    return data


def _load_project_name(
    pyproject_path: Path, data: dict[str, Any], module_name: str
) -> str:
    """Load the module package name from `[project].name`."""
    project_table = data.get("project", {})
    if not isinstance(project_table, dict):
        raise DependencySyncError(
            f"Embedded {module_name} pyproject.toml is missing a valid [project] table"
        )

    package_name = project_table.get("name")
    if not isinstance(package_name, str) or not package_name.strip():
        raise DependencySyncError(
            f"Embedded {module_name} pyproject.toml is missing [project].name"
        )
    return package_name.strip()


def _load_poetry_dependencies(
    pyproject_path: Path, data: dict[str, Any]
) -> dict[str, Any]:
    """Load `[tool.poetry.dependencies]` from a TOML document."""
    tool_table = data.get("tool", {})
    if not isinstance(tool_table, dict):
        raise DependencySyncError(
            f"Unable to locate [tool.poetry.dependencies] in {pyproject_path}"
        )

    poetry_table = tool_table.get("poetry", {})
    if not isinstance(poetry_table, dict):
        raise DependencySyncError(
            f"Unable to locate [tool.poetry.dependencies] in {pyproject_path}"
        )

    dependencies = poetry_table.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise DependencySyncError(
            f"[tool.poetry.dependencies] must be a mapping in {pyproject_path}"
        )

    return dependencies


def _extract_dependency_name(requirement: str, module_name: str) -> str:
    """Extract a dependency key name from a manifest requirement string."""
    match = _DEPENDENCY_NAME_PATTERN.match(requirement)
    if match is None:
        raise DependencySyncError(
            f"Unable to parse dependency name from {module_name} manifest entry: {requirement!r}"
        )
    return match.group(1)


def _should_skip_manifest_dependency(
    module_name: str,
    dependency_name: str,
    module_options: Mapping[str, Any] | None,
) -> bool:
    """Return True when a module dependency is intentionally skipped."""
    if module_name != "storage":
        return False

    backend = str((module_options or {}).get("backend", "local")).strip().lower()
    if backend in _STORAGE_CLOUD_BACKENDS:
        return False
    return dependency_name in _STORAGE_CLOUD_DEPENDENCIES


def _build_module_path_dependency_value(
    module_name: str,
    relative_install_path: str,
    module_options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Build the project path-dependency entry for an embedded module."""
    dependency_value: dict[str, Any] = {
        "path": f"./{relative_install_path}",
        "develop": True,
    }

    if module_name == "storage":
        backend = str((module_options or {}).get("backend", "local")).strip().lower()
        if backend in _STORAGE_CLOUD_BACKENDS:
            dependency_value["extras"] = [_STORAGE_CLOUD_EXTRA]

    return dependency_value


def _iter_required_dependency_names(
    module_name: str,
    manifest_dependencies: list[str],
    module_options: Mapping[str, Any] | None,
) -> list[str]:
    """Resolve manifest dependency requirements to project dependency keys."""
    dependency_names: list[str] = []
    for requirement in manifest_dependencies:
        dependency_name = _extract_dependency_name(requirement, module_name)
        if _should_skip_manifest_dependency(
            module_name, dependency_name, module_options
        ):
            continue
        dependency_names.append(dependency_name)
    return dependency_names


def _extract_version_tuple(spec: str) -> tuple[int, ...] | None:
    """Extract the first comparable version tuple from a Poetry version string."""
    match = _VERSION_PATTERN.search(spec)
    if match is None:
        return None
    return tuple(int(part) for part in match.group(1).split("."))


def _prefer_dependency_value(current: Any, candidate: Any) -> Any:
    """Prefer the highest comparable Poetry version string when conflicts appear."""
    if current == candidate:
        return current
    if not isinstance(current, str) or not isinstance(candidate, str):
        return current

    current_version = _extract_version_tuple(current)
    candidate_version = _extract_version_tuple(candidate)
    if current_version is None or candidate_version is None:
        return current
    return candidate if candidate_version > current_version else current


def _render_toml_literal(value: Any) -> str:
    """Serialize a limited TOML literal used for dependency entries."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        return str(value)
    if isinstance(value, (list, tuple)):
        return "[" + ", ".join(_render_toml_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        rendered_items = [
            f"{key} = {_render_toml_literal(item)}" for key, item in value.items()
        ]
        return "{" + ", ".join(rendered_items) + "}"
    raise DependencySyncError(f"Unsupported TOML dependency value: {value!r}")


def _append_dependency_entries(
    pyproject_path: Path,
    entries: list[tuple[str, Any]],
) -> None:
    """Append missing dependency entries to `[tool.poetry.dependencies]`."""
    if not entries:
        return

    original = pyproject_path.read_text()
    lines = original.splitlines()
    section_header = "[tool.poetry.dependencies]"
    section_start: int | None = None
    section_end = len(lines)

    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == section_header:
            section_start = index
            continue
        if (
            section_start is not None
            and stripped.startswith("[")
            and stripped.endswith("]")
        ):
            section_end = index
            break

    if section_start is None:
        raise DependencySyncError(
            f"Unable to locate [tool.poetry.dependencies] in {pyproject_path}"
        )

    insertion_index = section_end
    while (
        insertion_index > section_start + 1 and lines[insertion_index - 1].strip() == ""
    ):
        insertion_index -= 1

    rendered_entries = [
        f"{dependency_name} = {_render_toml_literal(dependency_value)}"
        for dependency_name, dependency_value in entries
    ]
    updated_lines = (
        lines[:insertion_index]
        + rendered_entries
        + lines[insertion_index:section_end]
        + lines[section_end:]
    )
    pyproject_path.write_text("\n".join(updated_lines) + "\n")


def sync_project_module_dependencies(
    project_path: Path,
    module_options_by_name: Mapping[str, Mapping[str, Any] | None],
) -> ProjectDependencySyncResult:
    """Add missing module path and third-party dependencies to a project pyproject.

    The sync is intentionally add-only. Existing project dependency values always win.
    """
    if not module_options_by_name:
        return ProjectDependencySyncResult()

    pyproject_path = project_path / "pyproject.toml"
    project_pyproject = _load_toml_file(pyproject_path)
    project_dependencies = _load_poetry_dependencies(pyproject_path, project_pyproject)
    existing_dependency_names = set(project_dependencies.keys())

    pending_path_dependencies: dict[str, Any] = {}
    pending_package_dependencies: dict[str, Any] = {}

    for module_name in sorted(module_options_by_name):
        module_options = module_options_by_name.get(module_name) or {}
        install_path = resolve_embedded_module_install_path(project_path, module_name)
        if install_path is None:
            continue

        module_pyproject_path = install_path / "pyproject.toml"
        module_pyproject = _load_toml_file(module_pyproject_path)
        module_package_name = _load_project_name(
            module_pyproject_path,
            module_pyproject,
            module_name,
        )
        module_poetry_dependencies = _load_poetry_dependencies(
            module_pyproject_path,
            module_pyproject,
        )

        if (
            module_package_name not in existing_dependency_names
            and module_package_name not in pending_path_dependencies
        ):
            relative_install_path = install_path.relative_to(project_path).as_posix()
            pending_path_dependencies[module_package_name] = (
                _build_module_path_dependency_value(
                    module_name,
                    relative_install_path,
                    module_options,
                )
            )

        manifest = get_manifest_for_module(project_path, module_name, strict=True)
        if manifest is None:
            raise ManifestError(
                f"Manifest file not found: {project_path / 'modules' / module_name / 'module.yml'}",
                module_name,
            )

        for dependency_name in _iter_required_dependency_names(
            module_name,
            manifest.dependencies,
            module_options,
        ):
            if dependency_name in existing_dependency_names:
                continue

            if dependency_name not in module_poetry_dependencies:
                raise DependencySyncError(
                    "Embedded module pyproject.toml is missing the Poetry dependency "
                    f"version for {module_name}.{dependency_name}"
                )

            dependency_value = module_poetry_dependencies[dependency_name]
            if dependency_name in pending_package_dependencies:
                pending_package_dependencies[dependency_name] = (
                    _prefer_dependency_value(
                        pending_package_dependencies[dependency_name],
                        dependency_value,
                    )
                )
            else:
                pending_package_dependencies[dependency_name] = dependency_value

    entries_to_add = [
        (dependency_name, pending_package_dependencies[dependency_name])
        for dependency_name in sorted(pending_package_dependencies)
    ]
    entries_to_add.extend(
        (dependency_name, pending_path_dependencies[dependency_name])
        for dependency_name in sorted(pending_path_dependencies)
    )
    _append_dependency_entries(pyproject_path, entries_to_add)

    return ProjectDependencySyncResult(
        added_path_dependencies=sorted(pending_path_dependencies),
        added_package_dependencies=sorted(pending_package_dependencies),
    )
