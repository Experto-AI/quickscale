"""Dependency-sync entry points and repin-mode bookkeeping.

Implementation detail of
:mod:`quickscale_cli.utils.module_dependency_sync`; that module re-exports
every name defined here (Module Conventions rule 28), so existing import
paths and test patch targets keep working.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Mapping

from quickscale_cli.utils._dependency_io import ProjectDependencySyncResult
import quickscale_cli.utils._dependency_io as _dependency_io
import quickscale_cli.utils._dependency_write as _dependency_write
import quickscale_core.manifest.loader as _loader
import quickscale_core.manifest.loader_errors as _loader_errors


def _resolve_declared_dependency_value(
    *,
    module_name: str,
    dependency_name: str,
    requirement: str,
    module_poetry_dependencies: Mapping[str, Any],
) -> Any:
    """Return the Poetry dependency value declared for a manifest requirement.

    When pyproject.toml declares a non-string (e.g. path/table) dependency,
    fall back to the version spec from the module.yml manifest requirement so
    generated projects receive a proper bounded version range instead of a
    developer-only path entry.
    """
    if dependency_name not in module_poetry_dependencies:
        raise _dependency_io.DependencySyncError(
            "Embedded module pyproject.toml is missing the Poetry dependency "
            f"version for {module_name}.{dependency_name}"
        )
    dependency_value = module_poetry_dependencies[dependency_name]
    if not isinstance(dependency_value, str):
        spec = requirement[len(dependency_name) :].strip()
        dependency_value = spec if spec else dependency_value
    return dependency_value


def _merge_preferred_dependency(
    pending: dict[str, Any],
    dependency_name: str,
    dependency_value: Any,
) -> None:
    """Record a dependency value, keeping the preferred one on conflict.

    Cross-module conflict resolution using ``_prefer_dependency_value``
    ensures the highest compatible version floor wins regardless of module
    iteration order (SA9.1-REV-004).
    """
    if dependency_name in pending:
        pending[dependency_name] = _dependency_write._prefer_dependency_value(
            pending[dependency_name],
            dependency_value,
        )
    else:
        pending[dependency_name] = dependency_value


def _record_repin_update(
    pending_package_updates: dict[str, Any],
    *,
    module_name: str,
    dependency_name: str,
    requirement: str,
    module_poetry_dependencies: Mapping[str, Any],
) -> None:
    """Queue a repin-mode replacement for an existing project dependency.

    The comparison against current project values happens once after the
    full module loop.
    """
    desired_value = _resolve_declared_dependency_value(
        module_name=module_name,
        dependency_name=dependency_name,
        requirement=requirement,
        module_poetry_dependencies=module_poetry_dependencies,
    )
    _merge_preferred_dependency(pending_package_updates, dependency_name, desired_value)


def _apply_pending_dependency_updates(
    pyproject_path: Path,
    project_dependencies: Mapping[str, Any],
    pending_package_updates: Mapping[str, Any],
) -> dict[str, Any]:
    """Write repin-mode updates, skipping entries already at the target value.

    Entries whose cross-module maximum already matches the current project
    value are filtered out to avoid unnecessary rewrites (SA9.1-REV-004).
    """
    if not pending_package_updates:
        return dict(pending_package_updates)
    filtered_updates = {
        dep_name: dep_value
        for dep_name, dep_value in pending_package_updates.items()
        if dep_name not in project_dependencies
        or project_dependencies[dep_name] != dep_value
    }
    if filtered_updates:
        _dependency_write._update_dependency_entries(pyproject_path, filtered_updates)
    return filtered_updates


def _wheel_distribution_version(filename: str) -> str | None:
    """Return the version component of a wheel filename, if it is well formed."""
    if not filename.endswith(".whl"):
        return None
    parts = filename[: -len(".whl")].split("-")
    if len(parts) < 5:
        return None
    if re.sub(r"[-_.]+", "_", parts[0]).lower() != "quickscale_core":
        return None
    return parts[1]


def _version_satisfies_bounded_pin(version: str, pin: str) -> bool:
    """Return whether *version* falls inside a ``>=floor,<ceiling`` pin."""
    match = re.fullmatch(
        r">=\s*([0-9]+(?:\.[0-9]+)*)\s*,\s*<\s*([0-9]+(?:\.[0-9]+)*)",
        pin.strip(),
    )
    if match is None:
        return False
    try:
        candidate = tuple(int(part) for part in version.split("."))
        floor = tuple(int(part) for part in match.group(1).split("."))
        ceiling = tuple(int(part) for part in match.group(2).split("."))
    except ValueError:
        return False
    if len(candidate) < len(floor):
        candidate = candidate + (0,) * (len(floor) - len(candidate))
    return floor <= candidate < ceiling


def sync_project_core_dependency(
    project_path: Path,
    wheelhouse: Path | None = None,
) -> bool:
    """Point the project's lockstep ``quickscale-core`` pin at a local wheel.

    Generated projects declare the bounded ``quickscale-core`` lockstep pin
    from the generator's version.  When the running CLI resolves QuickScale
    distributions from a local wheelhouse — an unpublished development build —
    that pin must be replaced with the local wheel path, or ``poetry lock``
    chases a version that is not on PyPI.  Projects that do not declare the
    dependency are left untouched; this function never adds it.

    Returns True when ``pyproject.toml`` changed.
    """
    pyproject_path = project_path / "pyproject.toml"
    if not pyproject_path.exists():
        return False

    project_pyproject = _dependency_io._load_toml_file(pyproject_path)
    project_dependencies = _dependency_io._load_poetry_dependencies(
        pyproject_path, project_pyproject
    )
    if "quickscale-core" not in project_dependencies:
        return False
    if isinstance(project_dependencies["quickscale-core"], dict):
        # Already resolved to a local artifact (the module dependency sync ran
        # first); leave the existing resolution in place.
        return False

    resolved_wheelhouse = (
        wheelhouse
        if wheelhouse is not None
        else _dependency_io._resolve_wheelhouse_dir()
    )
    local_wheel = _dependency_io._resolve_local_wheel_dependency(
        project_path,
        project_path,
        "quickscale-core",
        resolved_wheelhouse,
    )
    if local_wheel is None or project_dependencies["quickscale-core"] == local_wheel:
        return False

    declared_pin = project_dependencies["quickscale-core"]
    wheel_filename = Path(str(local_wheel.get("path", ""))).name
    wheel_version = _wheel_distribution_version(wheel_filename)
    if wheel_version is None or not _version_satisfies_bounded_pin(
        wheel_version, str(declared_pin)
    ):
        raise _dependency_io.DependencySyncError(
            f"Local quickscale-core wheel {wheel_filename!r} does not satisfy the "
            f"project's lockstep pin {declared_pin!r}. Build the wheel from the "
            "matching VERSION, or unset QUICKSCALE_LOCAL_WHEELHOUSE to resolve the "
            "pin from an index."
        )

    _dependency_write._update_dependency_entries(
        pyproject_path, {"quickscale-core": local_wheel}
    )
    return True


def sync_project_module_dependencies(
    project_path: Path,
    module_options_by_name: Mapping[str, Mapping[str, Any] | None],
    repin_existing: bool = False,
) -> ProjectDependencySyncResult:
    """Add or update module path and third-party dependencies in a project pyproject.

    In the default add-only mode (``repin_existing=False``), existing project
    dependency values always win and only truly missing entries are appended.

    In repin mode (``repin_existing=True``), existing project dependency
    entries are compared against the manifest-derived bounded range, and any
    that differ are replaced inline.  This is used by the update path to
    repin pre-SA9.1 path-style or out-of-range entries to the correct
    compatible version range.
    """
    if not module_options_by_name:
        return _dependency_io.ProjectDependencySyncResult()

    # Validate an explicit wheelhouse at the dependency-sync boundary, before
    # inspecting module dependencies.  This keeps malformed explicit input
    # fail-hard even when the selected modules have only public dependencies,
    # while preserving the intentional no-module no-op above.
    wheelhouse = _dependency_io._resolve_wheelhouse_dir()

    pyproject_path = project_path / "pyproject.toml"
    project_pyproject = _dependency_io._load_toml_file(pyproject_path)
    project_dependencies = _dependency_io._load_poetry_dependencies(
        pyproject_path, project_pyproject
    )
    existing_dependency_names = set(project_dependencies.keys())

    pending_path_dependencies: dict[str, Any] = {}
    pending_package_dependencies: dict[str, Any] = {}
    pending_package_updates: dict[str, Any] = {}

    for module_name in sorted(module_options_by_name):
        module_options = module_options_by_name.get(module_name) or {}
        install_path = _dependency_io.resolve_embedded_module_install_path(
            project_path, module_name
        )
        if install_path is None:
            continue

        module_pyproject_path = install_path / "pyproject.toml"
        module_pyproject = _dependency_io._load_toml_file(module_pyproject_path)
        module_package_name = _dependency_io._load_project_name(
            module_pyproject_path,
            module_pyproject,
            module_name,
        )
        module_poetry_dependencies = _dependency_io._load_poetry_dependencies(
            module_pyproject_path,
            module_pyproject,
        )

        if (
            module_package_name not in existing_dependency_names
            and module_package_name not in pending_path_dependencies
        ):
            relative_install_path = install_path.relative_to(project_path).as_posix()
            pending_path_dependencies[module_package_name] = (
                _dependency_io._build_module_path_dependency_value(
                    module_name,
                    relative_install_path,
                    module_options,
                )
            )

        manifest = _loader.get_manifest_for_module(
            project_path, module_name, strict=True
        )
        if manifest is None:
            raise _loader_errors.ManifestError(
                f"Manifest file not found: {project_path / 'modules' / module_name / 'module.yml'}",
                module_name,
            )

        for requirement in manifest.dependencies:
            dependency_name = _dependency_io._extract_dependency_name(
                requirement, module_name
            )

            if _dependency_io._should_skip_manifest_dependency(
                module_name, dependency_name, module_options
            ):
                continue

            local_wheel = _dependency_io._resolve_local_wheel_dependency(
                project_path,
                project_path,
                dependency_name,
                wheelhouse,
            )

            if dependency_name in existing_dependency_names:
                if (
                    local_wheel is not None
                    and project_dependencies[dependency_name] != local_wheel
                ):
                    pending_package_updates[dependency_name] = local_wheel
                    continue
                # Repin mode: replace existing entries that differ from the
                # manifest-derived bounded range.
                if repin_existing:
                    _record_repin_update(
                        pending_package_updates,
                        module_name=module_name,
                        dependency_name=dependency_name,
                        requirement=requirement,
                        module_poetry_dependencies=module_poetry_dependencies,
                    )
                continue

            dependency_value = _resolve_declared_dependency_value(
                module_name=module_name,
                dependency_name=dependency_name,
                requirement=requirement,
                module_poetry_dependencies=module_poetry_dependencies,
            )
            if local_wheel is not None:
                dependency_value = local_wheel

            _merge_preferred_dependency(
                pending_package_dependencies, dependency_name, dependency_value
            )

    # Apply updates to existing entries (repin mode) before appending new ones.
    # Entries whose cross-module maximum already matches the current project
    # value are filtered out to avoid unnecessary rewrites (SA9.1-REV-004).
    pending_package_updates = _apply_pending_dependency_updates(
        pyproject_path,
        project_dependencies,
        pending_package_updates,
    )

    entries_to_add = [
        (dependency_name, pending_package_dependencies[dependency_name])
        for dependency_name in sorted(pending_package_dependencies)
    ]
    entries_to_add.extend(
        (dependency_name, pending_path_dependencies[dependency_name])
        for dependency_name in sorted(pending_path_dependencies)
    )
    _dependency_write._append_dependency_entries(pyproject_path, entries_to_add)

    # Patch module pyproject.toml files: replace path-style dependencies
    # that point to non-existent locations with version constraints from
    # the module.yml manifest.  This prevents poetry lock from failing
    # when a module's pyproject.toml references a monorepo-local path
    # (e.g. quickscale-core = {path = "../../quickscale_core"}) that
    # doesn't exist in the generated project's isolated tree.
    _dependency_write._patch_module_path_dependencies(
        project_path, module_options_by_name, wheelhouse
    )

    return _dependency_io.ProjectDependencySyncResult(
        added_path_dependencies=sorted(pending_path_dependencies),
        added_package_dependencies=sorted(pending_package_dependencies),
        updated_package_dependencies=sorted(pending_package_updates),
    )
