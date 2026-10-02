"""Dependency-sync data types and TOML/install-path reading helpers.

Implementation detail of
:mod:`quickscale_cli.utils.module_dependency_sync`; that module re-exports
every name defined here (Module Conventions rule 28), so existing import
paths and test patch targets keep working.
"""

from __future__ import annotations

import os
import re
import shutil
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

import quickscale_cli.utils.module_dependency_sync as _module_dependency_sync


_DEPENDENCY_NAME_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)")
_VERSION_PATTERN = re.compile(r"(\d+(?:\.\d+)*)")
_STORAGE_CLOUD_BACKENDS = frozenset({"r2", "s3"})
_STORAGE_CLOUD_DEPENDENCIES = frozenset({"boto3", "django-storages"})
_STORAGE_CLOUD_EXTRA = "cloud"
_LOCAL_WHEELHOUSE_ENV = "QUICKSCALE_LOCAL_WHEELHOUSE"
_LOCAL_WHEEL_DISTRIBUTIONS = frozenset({"quickscale-core"})
# Wheelhouse staged next to a locally installed CLI (scripts/install_global.sh).
# A local (unpublished) build must resolve its own quickscale-core from these
# wheels; without it every generated project pins a PyPI version that does not
# exist yet and `poetry lock` fails during `quickscale apply`.
_INSTALL_WHEELHOUSE_DIRNAME = "quickscale_wheels"


class DependencySyncError(Exception):
    """Raised when generated-project dependency synchronization cannot proceed."""


@dataclass(frozen=True)
class ProjectDependencySyncResult:
    """Summary of dependency entries added or updated in a generated project."""

    added_path_dependencies: list[str] = field(default_factory=list)
    added_package_dependencies: list[str] = field(default_factory=list)
    updated_package_dependencies: list[str] = field(default_factory=list)

    @property
    def changed(self) -> bool:
        """Return True when the project pyproject.toml was updated."""
        return bool(
            self.added_path_dependencies
            or self.added_package_dependencies
            or self.updated_package_dependencies
        )


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
        raise _module_dependency_sync.DependencySyncError(
            f"Failed to read TOML file {path}: {error}"
        ) from error
    except tomllib.TOMLDecodeError as error:
        raise _module_dependency_sync.DependencySyncError(
            f"Invalid TOML in {path}: {error}"
        ) from error

    if not isinstance(data, dict):
        raise _module_dependency_sync.DependencySyncError(
            f"TOML file {path} did not parse to a mapping"
        )
    return data


def _load_project_name(
    pyproject_path: Path, data: dict[str, Any], module_name: str
) -> str:
    """Load the module package name from `[project].name`."""
    project_table = data.get("project", {})
    if not isinstance(project_table, dict):
        raise _module_dependency_sync.DependencySyncError(
            f"Embedded {module_name} pyproject.toml is missing a valid [project] table"
        )

    package_name = project_table.get("name")
    if not isinstance(package_name, str) or not package_name.strip():
        raise _module_dependency_sync.DependencySyncError(
            f"Embedded {module_name} pyproject.toml is missing [project].name"
        )
    return package_name.strip()


def _load_poetry_dependencies(
    pyproject_path: Path, data: dict[str, Any]
) -> dict[str, Any]:
    """Load `[tool.poetry.dependencies]` from a TOML document."""
    tool_table = data.get("tool", {})
    if not isinstance(tool_table, dict):
        raise _module_dependency_sync.DependencySyncError(
            f"Unable to locate [tool.poetry.dependencies] in {pyproject_path}"
        )

    poetry_table = tool_table.get("poetry", {})
    if not isinstance(poetry_table, dict):
        raise _module_dependency_sync.DependencySyncError(
            f"Unable to locate [tool.poetry.dependencies] in {pyproject_path}"
        )

    dependencies = poetry_table.get("dependencies", {})
    if not isinstance(dependencies, dict):
        raise _module_dependency_sync.DependencySyncError(
            f"[tool.poetry.dependencies] must be a mapping in {pyproject_path}"
        )

    return dependencies


def _extract_dependency_name(requirement: str, module_name: str) -> str:
    """Extract a dependency key name from a manifest requirement string."""
    match = _module_dependency_sync._DEPENDENCY_NAME_PATTERN.match(requirement)
    if match is None:
        raise _module_dependency_sync.DependencySyncError(
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
    if backend in _module_dependency_sync._STORAGE_CLOUD_BACKENDS:
        return False
    return dependency_name in _module_dependency_sync._STORAGE_CLOUD_DEPENDENCIES


def _resolve_wheelhouse_dir() -> Path | None:
    """Return the wheelhouse to resolve QuickScale distributions from, if any.

    ``QUICKSCALE_LOCAL_WHEELHOUSE`` wins when set (installed-wheel acceptance
    runs).  Otherwise a wheelhouse staged beside the running CLI install is
    used, so a locally installed build resolves its own unpublished wheels
    instead of pinning a PyPI version that does not exist.
    """
    if _module_dependency_sync._LOCAL_WHEELHOUSE_ENV in os.environ:
        wheelhouse_value = os.environ[_module_dependency_sync._LOCAL_WHEELHOUSE_ENV]
        wheelhouse = Path(wheelhouse_value)
        if not wheelhouse.is_absolute() or not wheelhouse.is_dir():
            raise _module_dependency_sync.DependencySyncError(
                f"{_module_dependency_sync._LOCAL_WHEELHOUSE_ENV} must name an "
                "absolute wheelhouse directory"
            )
        return wheelhouse

    install_wheelhouse = (
        Path(sys.prefix) / _module_dependency_sync._INSTALL_WHEELHOUSE_DIRNAME
    )
    if install_wheelhouse.is_dir():
        return install_wheelhouse
    return None


def _find_local_wheel_candidates(
    wheelhouse: Path,
    normalized_name: str,
) -> list[Path]:
    """Return wheels whose distribution component matches a normalized name."""
    return sorted(
        candidate
        for candidate in wheelhouse.iterdir()
        if candidate.is_file()
        and candidate.suffix.lower() == ".whl"
        and re.sub(r"[-_.]+", "_", candidate.name.split("-", 1)[0]).lower()
        == normalized_name
    )


def _raise_for_missing_explicit_wheel(
    wheelhouse: Path,
    dependency_name: str,
    wheel_pattern: str,
) -> None:
    """Fail when an explicit wheelhouse lacks its requested local artifact."""
    if _module_dependency_sync._LOCAL_WHEELHOUSE_ENV not in os.environ:
        return

    available_wheels = sorted(
        candidate.name
        for candidate in wheelhouse.iterdir()
        if candidate.is_file() and candidate.suffix.lower() == ".whl"
    )
    raise _module_dependency_sync.DependencySyncError(
        f"{_module_dependency_sync._LOCAL_WHEELHOUSE_ENV} requested local dependency "
        f"{dependency_name}, but no matching wheel was found in "
        f"{wheelhouse}; searched directory {wheelhouse} with pattern "
        f"{wheel_pattern!r}. Available wheels: "
        f"{available_wheels or '[none]'}. Build or copy a wheel matching "
        f"{wheel_pattern!r}, or unset "
        f"{_module_dependency_sync._LOCAL_WHEELHOUSE_ENV} to use the "
        "manifest version spec."
    )


def _resolve_local_wheel_dependency(
    project_path: Path,
    dependency_base: Path,
    dependency_name: str,
    wheelhouse: Path | None,
) -> dict[str, str] | None:
    """Materialize and return an exact local wheel for installed acceptance."""
    normalized_name = re.sub(r"[-_.]+", "-", dependency_name).lower()
    if normalized_name not in _module_dependency_sync._LOCAL_WHEEL_DISTRIBUTIONS:
        return None

    if wheelhouse is None:
        return None

    # Wheel distribution names use the PEP 503 spelling: runs of hyphens,
    # underscores, and dots compare as one underscore, case-insensitively.
    # Do the comparison against the filename's distribution component rather
    # than relying on Path.glob's case-sensitive, hyphen-only matching.
    normalized_name = re.sub(r"[-_.]+", "_", dependency_name).lower()
    wheel_pattern = f"{normalized_name}-*.whl"
    candidates = _module_dependency_sync._find_local_wheel_candidates(
        wheelhouse, normalized_name
    )
    if not candidates:
        _module_dependency_sync._raise_for_missing_explicit_wheel(
            wheelhouse,
            dependency_name,
            wheel_pattern,
        )
        return None
    if len(candidates) != 1:
        raise _module_dependency_sync.DependencySyncError(
            f"Wheelhouse {wheelhouse} has ambiguous wheels for {dependency_name}: "
            f"{[candidate.name for candidate in candidates]}"
        )

    project_wheelhouse = project_path / ".quickscale" / "wheels"
    project_wheelhouse.mkdir(parents=True, exist_ok=True)
    project_wheel = project_wheelhouse / candidates[0].name
    shutil.copy2(candidates[0], project_wheel)
    relative_wheel = os.path.relpath(project_wheel, start=dependency_base)
    return {"path": Path(relative_wheel).as_posix()}


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
        if backend in _module_dependency_sync._STORAGE_CLOUD_BACKENDS:
            dependency_value["extras"] = [_module_dependency_sync._STORAGE_CLOUD_EXTRA]

    return dependency_value


def _iter_required_dependency_names(
    module_name: str,
    manifest_dependencies: list[str],
    module_options: Mapping[str, Any] | None,
) -> list[str]:
    """Resolve manifest dependency requirements to project dependency keys."""
    dependency_names: list[str] = []
    for requirement in manifest_dependencies:
        dependency_name = _module_dependency_sync._extract_dependency_name(
            requirement, module_name
        )
        if _module_dependency_sync._should_skip_manifest_dependency(
            module_name, dependency_name, module_options
        ):
            continue
        dependency_names.append(dependency_name)
    return dependency_names
