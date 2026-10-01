"""TOML loading, validation, and path-dependency editing."""

from .model import BetaMigrationReport, _append_blocker, _append_check
import tomllib
from pathlib import Path
from typing import Any


def _load_toml_file(pyproject_path: Path) -> dict[str, Any]:
    """Load a TOML file from disk."""
    with open(pyproject_path, "rb") as file_handle:
        return tomllib.load(file_handle)


def _write_validated_toml(path: Path, content: str) -> None:
    """Write TOML content only after validating the rewritten document parses."""
    try:
        tomllib.loads(content)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(
            f"Refusing to write invalid TOML to {path}: {error}"
        ) from error
    path.write_text(content)


def _locate_toml_section_bounds(lines: list[str], section_name: str) -> tuple[int, int]:
    """Return the (start, end) line indices of a TOML section in a line list.

    The end boundary is the next header that is not a strict child of
    ``section_name``.  Child tables (``[foo.bar.child]``) and child
    array-of-tables (``[[foo.bar.child]]``) are intentionally not treated as
    the end of the current section so that rewrites do not split mid-table.
    Sibling array-of-tables headers (``[[unrelated.name]]``) *do* terminate
    the active section so that the bounds do not bleed into the next
    unrelated block.
    """
    section_header = f"[{section_name}]"
    child_prefix = f"{section_name}."
    section_start: int | None = None
    section_end = len(lines)
    for index, line in enumerate(lines):
        stripped = line.strip()
        if stripped == section_header:
            section_start = index
            continue
        if section_start is None:
            continue
        if not (stripped.startswith("[") and stripped.endswith("]")):
            continue
        # Array-of-tables headers: child AOTs stay in the section body,
        # sibling AOTs terminate the section.
        if stripped.startswith("[[") or stripped.endswith("]]"):
            aot_inner = stripped[2:-2].strip()
            if aot_inner == section_name or aot_inner.startswith(child_prefix):
                continue
            section_end = index
            break
        # Ignore strict child tables of the current section.
        inner = stripped[1:-1].strip()
        if inner == section_name or inner.startswith(child_prefix):
            continue
        section_end = index
        break
    if section_start is None:
        raise ValueError(f"Unable to locate {section_header} in TOML document")
    return section_start, section_end


def _extract_poetry_package(
    pyproject_data: dict[str, Any], pyproject_path: Path
) -> str:
    """Extract the primary package include from a Poetry project."""
    try:
        packages = pyproject_data["tool"]["poetry"]["packages"]
        include = packages[0]["include"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ValueError(
            f"Unable to resolve the Poetry package include from {pyproject_path}"
        ) from exc

    if not isinstance(include, str) or not include:
        raise ValueError(f"Invalid Poetry package include in {pyproject_path}")
    return include


def _extract_path_dependencies(pyproject_data: dict[str, Any]) -> list[str]:
    """Return sorted path dependency names from a Poetry project."""
    dependencies = (
        pyproject_data.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    if not isinstance(dependencies, dict):
        return []

    path_deps = []
    for dependency_name, dependency_value in dependencies.items():
        if isinstance(dependency_value, dict) and "path" in dependency_value:
            path_deps.append(dependency_name)
    return sorted(path_deps)


def _collect_missing_path_dependency_values(
    report: BetaMigrationReport,
) -> dict[str, dict[str, Any]]:
    """Collect missing donor path dependency tables that must be added to the recipient."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")

    donor_pyproject = _load_toml_file(report.donor.pyproject_path)
    recipient_pyproject = _load_toml_file(report.recipient.pyproject_path)
    donor_dependencies = (
        donor_pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    recipient_dependencies = (
        recipient_pyproject.get("tool", {}).get("poetry", {}).get("dependencies", {})
    )
    if not isinstance(donor_dependencies, dict) or not isinstance(
        recipient_dependencies, dict
    ):
        raise ValueError(
            "Unable to resolve Poetry dependencies for path dependency synchronization."
        )

    missing_dependencies: dict[str, dict[str, Any]] = {}
    for dependency_name, dependency_value in donor_dependencies.items():
        if (
            isinstance(dependency_value, dict)
            and "path" in dependency_value
            and dependency_name not in recipient_dependencies
        ):
            missing_dependencies[dependency_name] = dependency_value
    return missing_dependencies


def _validate_fresh_first_path_dependency_targets(report: BetaMigrationReport) -> None:
    """Block before mutation when a transferred path dependency would dangle."""
    if report.blockers or report.recipient is None:
        return
    try:
        missing_dependencies = _collect_missing_path_dependency_values(report)
    except (OSError, RuntimeError, ValueError) as exc:
        detail = f"Unable to validate fresh-first path dependencies: {exc}"
        _append_check(
            report,
            name="fresh-first-path-dependency-targets",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    recipient_root = report.recipient.path.resolve()
    invalid_targets: list[str] = []
    for dependency_name, dependency_value in missing_dependencies.items():
        raw_path = dependency_value.get("path")
        if not isinstance(raw_path, str) or not raw_path:
            invalid_targets.append(f"{dependency_name} has no static path")
            continue
        candidate = (recipient_root / raw_path).resolve()
        if not candidate.is_relative_to(recipient_root):
            invalid_targets.append(
                f"{dependency_name} escapes the recipient root via {raw_path!r}"
            )
        elif not candidate.is_dir():
            invalid_targets.append(
                f"{dependency_name} targets missing recipient directory {candidate}"
            )

    if invalid_targets:
        detail = "Fresh-first path dependency preflight failed: " + "; ".join(
            invalid_targets
        )
        _append_check(
            report,
            name="fresh-first-path-dependency-targets",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    _append_check(
        report,
        name="fresh-first-path-dependency-targets",
        status="passed",
        detail=(
            "Every missing donor path dependency resolves to an existing path inside "
            "the recipient."
        ),
    )


def _toml_literal(value: Any) -> str:
    """Serialize a limited TOML literal used by QuickScale path dependencies."""
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
        return "[" + ", ".join(_toml_literal(item) for item in value) + "]"
    if isinstance(value, dict):
        return _toml_inline_table(value)
    raise ValueError(
        f"Unsupported TOML literal for beta migration path dependency sync: {value!r}"
    )


def _toml_inline_table(value: dict[str, Any]) -> str:
    """Serialize a TOML inline table preserving the donor key order."""
    parts = [f"{key} = {_toml_literal(item)}" for key, item in value.items()]
    return "{" + ", ".join(parts) + "}"


def _insert_missing_path_dependencies(
    pyproject_path: Path,
    missing_dependencies: dict[str, dict[str, Any]],
) -> bool:
    """Insert missing path dependencies into the Poetry dependency section."""
    if not missing_dependencies:
        return False

    original = pyproject_path.read_text()
    lines = original.splitlines()
    section_start, section_end = _locate_toml_section_bounds(
        lines, "tool.poetry.dependencies"
    )

    insert_at = section_end
    child_prefix = "tool.poetry.dependencies."
    for index in range(section_start + 1, section_end):
        stripped = lines[index].strip()
        if stripped.startswith("[[") and stripped.endswith("]]"):
            header = stripped[2:-2].strip()
        elif stripped.startswith("[") and stripped.endswith("]"):
            header = stripped[1:-1].strip()
        else:
            continue
        if header.startswith(child_prefix):
            insert_at = index
            break
    while insert_at > section_start + 1 and lines[insert_at - 1].strip() == "":
        insert_at -= 1

    dependency_lines = [
        f"{dependency_name} = {_toml_inline_table(dependency_value)}"
        for dependency_name, dependency_value in missing_dependencies.items()
    ]
    updated_lines = lines[:insert_at] + dependency_lines + lines[insert_at:]
    _write_validated_toml(pyproject_path, "\n".join(updated_lines) + "\n")
    return True
