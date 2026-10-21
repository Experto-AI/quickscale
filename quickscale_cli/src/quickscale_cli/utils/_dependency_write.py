"""TOML rewriting helpers for generated-project dependency syncing.

Implementation detail of
:mod:`quickscale_cli.utils.module_dependency_sync`; that module re-exports
every name defined here (Module Conventions rule 28), so existing import
paths and test patch targets keep working.
"""

from __future__ import annotations

import os
import tempfile
import tomllib
from pathlib import Path
from typing import Any, Mapping


import quickscale_cli.utils._dependency_io as _dependency_io
from quickscale_core.version import __version__ as CORE_VERSION


def _extract_version_tuple(spec: str) -> tuple[int, ...] | None:
    """Extract the first comparable version tuple from a Poetry version string."""
    match = _dependency_io._VERSION_PATTERN.search(spec)
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
    raise _dependency_io.DependencySyncError(
        f"Unsupported TOML dependency value: {value!r}"
    )


def _write_validated_toml(path: Path, content: str) -> None:
    """Write TOML content only after validating the rewritten document.

    The validated document lands in a fresh sibling temp file first and is
    moved over the target with ``os.replace``, so an interrupted write leaves
    the original file intact instead of truncating it.  The staging file
    takes the target's permission bits before the replacement, so a rewrite
    never changes who can read ``pyproject.toml``.
    """
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as error:
        raise _dependency_io.DependencySyncError(
            f"Refusing to write invalid TOML to {path}: {error}"
        ) from error

    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = 0o644
    descriptor, temporary_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary_path.chmod(mode)
        os.replace(temporary_path, path)
    except BaseException:
        temporary_path.unlink(missing_ok=True)
        raise


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
        raise _dependency_io.DependencySyncError(
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
    _write_validated_toml(pyproject_path, "\n".join(updated_lines) + "\n")


def _update_dependency_entries(
    pyproject_path: Path,
    updates: dict[str, Any],
) -> None:
    """Replace existing dependency entries in pyproject.toml with new values.

    Used by the update-path repin mode to replace stale path-style or
    out-of-range version entries with the declared package spec.
    """
    if not updates:
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
        raise _dependency_io.DependencySyncError(
            f"Unable to locate [tool.poetry.dependencies] in {pyproject_path}"
        )

    updated_lines = list(lines)
    for dep_name, dep_value in updates.items():
        rendered = _render_toml_literal(dep_value)
        new_line = f"{dep_name} = {rendered}"
        found = False
        for i in range(section_start + 1, section_end):
            stripped = updated_lines[i].strip()
            if stripped.startswith(f"{dep_name} =") or stripped.startswith(
                f"{dep_name}="
            ):
                updated_lines[i] = new_line
                found = True
                break
        if not found:
            # Defensive fallback: append if the key is somehow missing from
            # the section (should not happen when repinning existing entries).
            updated_lines.insert(section_end, new_line)
            section_end += 1

    _write_validated_toml(pyproject_path, "\n".join(updated_lines) + "\n")


def _resolve_declared_dependency_path(
    install_path: Path, dep_value: Any
) -> Path | None:
    """Return the filesystem path a path-style dependency points at, if any."""
    if not isinstance(dep_value, dict) or "path" not in dep_value:
        return None
    dep_path = Path(dep_value["path"])
    if not dep_path.is_absolute():
        dep_path = (install_path / dep_path).resolve()
    return dep_path


def _is_existing_wheel_path_dependency(base_path: Path, dep_value: Any) -> bool:
    """Return whether a dependency already points at a wheel on disk.

    A generated project may resolve ``quickscale-core`` from a committed
    wheel (``{path = ".quickscale/wheels/...whl"}``) when the version is not
    on PyPI yet.  That is a deliberate local resolution: dependency sync must
    leave the line untouched rather than replace it with an index pin that
    cannot be resolved.
    """
    dep_path = _resolve_declared_dependency_path(base_path, dep_value)
    return (
        dep_path is not None
        and dep_path.is_file()
        and dep_path.suffix.lower() == ".whl"
    )


def _has_unresolvable_path_dependency(
    install_path: Path,
    module_poetry_deps: Mapping[str, Any],
) -> bool:
    """Return whether any declared path dependency points outside the tree."""
    for dep_value in module_poetry_deps.values():
        dep_path = _resolve_declared_dependency_path(install_path, dep_value)
        if dep_path is not None and not dep_path.exists():
            return True
    return False


def _core_lockstep_release_spec(version: str) -> str:
    """Return the bounded lockstep spec for a core release version.

    The floor keeps the release's full ``major.minor.patch`` version, unlike
    the generator's major.minor runtime pin: an embedded module's replacement
    dependency must not admit an older patch than the release it ships with.
    """
    major, minor, *_ = version.split(".")
    return f">={version},<{major}.{int(minor) + 1}.0"


def _published_path_dependency_spec(dep_name: str) -> str | None:
    """Return the published spec for a monorepo path dependency (rule 39).

    Module manifests list dependency names only, and a path-style dependency
    (``quickscale-core``) is unresolvable inside a generated project, so its
    replacement spec is the bounded lockstep release spec derived from the
    running core version.  An unknown path dependency has no published spec.
    """
    if dep_name == "quickscale-core":
        return _core_lockstep_release_spec(CORE_VERSION)
    return None


def _build_path_dependency_overrides(
    project_path: Path,
    install_path: Path,
    module_poetry_deps: Mapping[str, Any],
    wheelhouse: Path | None = None,
) -> dict[str, Any]:
    """Build replacement values for unresolvable path dependencies."""
    overrides: dict[str, Any] = {}
    for dep_name, dep_value in module_poetry_deps.items():
        dep_path = _resolve_declared_dependency_path(install_path, dep_value)
        if dep_path is None or dep_path.exists():
            continue

        local_wheel = _dependency_io._resolve_local_wheel_dependency(
            project_path,
            install_path,
            dep_name,
            wheelhouse,
        )
        if local_wheel is not None:
            overrides[dep_name] = local_wheel
            continue

        spec = _published_path_dependency_spec(dep_name)
        if spec:
            overrides[dep_name] = spec
    return overrides


def _rewrite_dependency_lines(raw_toml: str, overrides: Mapping[str, Any]) -> str:
    """Rewrite matching dependency assignment lines with override values."""
    result_lines: list[str] = []
    for line in raw_toml.splitlines():
        stripped = line.strip()
        matched = False
        for dep_name, spec in overrides.items():
            if stripped.startswith(f"{dep_name} =") or stripped.startswith(
                f"{dep_name}="
            ):
                indent = line[: len(line) - len(line.lstrip())]
                if isinstance(spec, str):
                    rendered_spec = f'"{spec}"'
                else:
                    rendered_spec = _render_toml_literal(spec)
                result_lines.append(f"{indent}{dep_name} = {rendered_spec}")
                matched = True
                break
        if not matched:
            result_lines.append(line)
    return "\n".join(result_lines) + "\n"


def _patch_module_path_dependencies(
    project_path: Path,
    module_options_by_name: Mapping[str, Mapping[str, Any] | None],
    wheelhouse: Path | None = None,
) -> None:
    """Replace unresolvable path deps in embedded module pyproject.toml files.

    When a module's pyproject.toml declares a dependency via a path (e.g.
    ``quickscale-core = {path = "../../quickscale_core", develop = true}``)
    and that path does not exist inside the generated project tree, replace
    it with the dependency's published spec — the canonical ``quickscale-core``
    lockstep pin — or a local wheel so that ``poetry lock`` can resolve it.
    """
    for module_name in sorted(module_options_by_name):
        install_path = _dependency_io.resolve_embedded_module_install_path(
            project_path, module_name
        )
        if install_path is None:
            continue
        module_pyproject_path = install_path / "pyproject.toml"
        module_pyproject = _dependency_io._load_toml_file(module_pyproject_path)
        module_poetry_deps = _dependency_io._load_poetry_dependencies(
            module_pyproject_path, module_pyproject
        )

        if not _has_unresolvable_path_dependency(install_path, module_poetry_deps):
            continue

        raw_toml = module_pyproject_path.read_text(encoding="utf-8")
        overrides = _build_path_dependency_overrides(
            project_path,
            install_path,
            module_poetry_deps,
            wheelhouse,
        )
        if overrides:
            _write_validated_toml(
                module_pyproject_path,
                _rewrite_dependency_lines(raw_toml, overrides),
            )
