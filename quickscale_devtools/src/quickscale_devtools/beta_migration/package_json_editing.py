"""Frontend ``package.json`` dependency diffing and merge.

The donor's added frontend dependencies are merged into the fresh recipient's
generated manifest.  The recipient's version wins on a conflict, and every
conflict is reported; the merge never rewrites unrelated fields, so the
reconciled ``name`` and the fresh scaffold's scripts, engines, and dev tooling
stay untouched.
"""

from .model import (
    BetaMigrationReport,
    FrontendDependencyMerge,
    _append_blocker,
    _append_check,
)
from ..handoff_prompt import _write_text_atomically
from pathlib import Path
from typing import Any
import json


_DEPENDENCY_SECTIONS: tuple[str, ...] = ("dependencies", "devDependencies")


def _load_package_json(package_json_path: Path) -> dict[str, Any]:
    """Load a frontend manifest, failing closed on invalid JSON."""
    try:
        data = json.loads(package_json_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Frontend manifest {package_json_path} is not valid JSON: {exc}"
        ) from exc
    if not isinstance(data, dict):
        raise ValueError(f"Frontend manifest {package_json_path} is not a JSON object")
    return data


def _dependency_sections(
    data: dict[str, Any], package_json_path: Path
) -> dict[str, dict[str, str]]:
    """Return the ``dependencies`` and ``devDependencies`` maps of a manifest."""
    sections: dict[str, dict[str, str]] = {}
    for section in _DEPENDENCY_SECTIONS:
        if section not in data:
            sections[section] = {}
            continue
        value = data[section]
        if not isinstance(value, dict) or not all(
            isinstance(name, str) and isinstance(version, str)
            for name, version in value.items()
        ):
            raise ValueError(
                f"Frontend manifest {package_json_path} '{section}' must map "
                "dependency names to version strings"
            )
        sections[section] = value
    return sections


def _plan_frontend_dependency_merge(
    donor_data: dict[str, Any],
    recipient_data: dict[str, Any],
    *,
    donor_path: Path,
    recipient_path: Path,
) -> FrontendDependencyMerge:
    """Compute the donor-only dependency names and the version conflicts."""
    donor_sections = _dependency_sections(donor_data, donor_path)
    recipient_sections = _dependency_sections(recipient_data, recipient_path)

    donor_names = {
        name for section in _DEPENDENCY_SECTIONS for name in donor_sections[section]
    }
    recipient_names = {
        name for section in _DEPENDENCY_SECTIONS for name in recipient_sections[section]
    }

    conflicts: list[str] = []
    for section in _DEPENDENCY_SECTIONS:
        for name, version in sorted(donor_sections[section].items()):
            if name in recipient_sections[section]:
                recipient_version = recipient_sections[section][name]
                if recipient_version != version:
                    conflicts.append(
                        f"{name} (recipient {section} {recipient_version}, "
                        f"donor {section} {version})"
                    )
                continue
            other_section = next(
                (
                    candidate
                    for candidate in _DEPENDENCY_SECTIONS
                    if candidate != section and name in recipient_sections[candidate]
                ),
                None,
            )
            if other_section is not None:
                recipient_version = recipient_sections[other_section][name]
                if recipient_version != version:
                    conflicts.append(
                        f"{name} (recipient {other_section} {recipient_version}, "
                        f"donor {section} {version})"
                    )

    return FrontendDependencyMerge(
        donor_only=sorted(donor_names - recipient_names),
        recipient_only=sorted(recipient_names - donor_names),
        conflicts=conflicts,
    )


def _missing_frontend_dependencies(
    donor_data: dict[str, Any],
    recipient_data: dict[str, Any],
    *,
    donor_path: Path,
    recipient_path: Path,
) -> dict[str, dict[str, str]]:
    """Return the donor dependency entries the recipient does not declare."""
    donor_sections = _dependency_sections(donor_data, donor_path)
    recipient_sections = _dependency_sections(recipient_data, recipient_path)
    recipient_names = {
        name for section in _DEPENDENCY_SECTIONS for name in recipient_sections[section]
    }

    additions: dict[str, dict[str, str]] = {}
    for section in _DEPENDENCY_SECTIONS:
        missing = {
            name: version
            for name, version in sorted(donor_sections[section].items())
            if name not in recipient_names
        }
        if missing:
            additions[section] = missing
    return additions


def _collect_missing_frontend_dependencies(
    report: BetaMigrationReport,
) -> dict[str, dict[str, str]]:
    """Return the donor dependency entries the recipient does not declare."""
    if report.donor is None or report.recipient is None:
        raise ValueError("Donor and recipient snapshots are required before execution.")
    donor_path = report.donor.path / "frontend" / "package.json"
    recipient_path = report.recipient.path / "frontend" / "package.json"
    return _missing_frontend_dependencies(
        _load_package_json(donor_path),
        _load_package_json(recipient_path),
        donor_path=donor_path,
        recipient_path=recipient_path,
    )


def _validate_fresh_first_frontend_dependency_targets(
    report: BetaMigrationReport,
) -> None:
    """Plan the frontend merge before mutation and fail closed on bad manifests.

    The intended merge is rendered against the recipient manifest and parsed
    before any file changes, so a layout the writer cannot extend blocks the
    run instead of surfacing after earlier mutations.
    """
    if report.blockers or report.donor is None or report.recipient is None:
        return
    donor_manifest = report.donor.path / "frontend" / "package.json"
    recipient_manifest = report.recipient.path / "frontend" / "package.json"
    try:
        donor_data = _load_package_json(donor_manifest)
        recipient_data = _load_package_json(recipient_manifest)
        merge = _plan_frontend_dependency_merge(
            donor_data,
            recipient_data,
            donor_path=donor_manifest,
            recipient_path=recipient_manifest,
        )
        additions = _missing_frontend_dependencies(
            donor_data,
            recipient_data,
            donor_path=donor_manifest,
            recipient_path=recipient_manifest,
        )
        if any(additions.values()):
            preview = recipient_manifest.read_text()
            for section in _DEPENDENCY_SECTIONS:
                entries = additions.get(section) or {}
                if entries:
                    preview = _insert_dependency_entries(preview, section, entries)
            parsed_preview = json.loads(preview)
            preview_sections = _dependency_sections(parsed_preview, recipient_manifest)
            for section, entries in additions.items():
                for name, version in entries.items():
                    if preview_sections[section].get(name) != version:
                        raise ValueError(
                            "Rendered frontend merge did not place "
                            f"{name} in the top-level '{section}' section"
                        )
    except (OSError, ValueError) as exc:
        detail = f"Unable to validate the frontend dependency merge: {exc}"
        _append_check(
            report,
            name="fresh-first-frontend-dependency-merge",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return

    report.frontend_dependency_merge = merge
    _append_check(
        report,
        name="fresh-first-frontend-dependency-merge",
        status="passed",
        detail=(
            "Planned the frontend dependency merge: "
            f"donor-only={merge.donor_only or ['(none)']}, "
            f"recipient-only={merge.recipient_only or ['(none)']}, "
            f"version conflicts={merge.conflicts or ['(none)']}."
        ),
    )


def _validate_donor_frontend_manifest(
    report: BetaMigrationReport, *, donor_path: Path
) -> None:
    """Validate the donor manifest before iterate regeneration replaces anything."""
    if report.blockers:
        return
    manifest_path = donor_path / "frontend" / "package.json"
    if not manifest_path.is_file():
        # A missing manifest stays a required-path failure of the fresh-first
        # preflight; only a present-but-invalid manifest blocks here.
        return
    try:
        manifest_data = _load_package_json(manifest_path)
        _dependency_sections(manifest_data, manifest_path)
    except (OSError, ValueError) as exc:
        detail = f"Donor frontend manifest preflight failed: {exc}"
        _append_check(
            report,
            name="donor-frontend-manifest",
            status="failed",
            detail=detail,
        )
        _append_blocker(report, detail)
        return
    _append_check(
        report,
        name="donor-frontend-manifest",
        status="passed",
        detail=f"Validated the donor frontend manifest before regeneration: {manifest_path}.",
    )


def _find_top_level_dependency_brace(
    package_json_text: str, section: str
) -> tuple[int, int]:
    """Return the (key start, brace index) of the top-level ``section`` member.

    The scan tracks JSON nesting and string state, so a nested object that
    happens to contain a ``section`` key — for example a pnpm package
    extension's own ``dependencies`` — is never selected.
    """
    depth = 0
    index = 0
    length = len(package_json_text)
    while index < length:
        char = package_json_text[index]
        if char == '"':
            key_start = index
            index += 1
            while index < length:
                if package_json_text[index] == "\\":
                    index += 2
                    continue
                if package_json_text[index] == '"':
                    break
                index += 1
            if index >= length:
                break
            token = package_json_text[key_start : index + 1]
            cursor = index + 1
            while cursor < length and package_json_text[cursor] in " \t\r\n":
                cursor += 1
            if depth == 1 and cursor < length and package_json_text[cursor] == ":":
                cursor += 1
                while cursor < length and package_json_text[cursor] in " \t\r\n":
                    cursor += 1
                if (
                    cursor < length
                    and package_json_text[cursor] == "{"
                    and json.loads(token) == section
                ):
                    return key_start, cursor
            index += 1
            continue
        if char in "{[":
            depth += 1
        elif char in "}]":
            depth -= 1
        index += 1
    raise ValueError(f"frontend/package.json has no top-level '{section}' section")


def _insert_dependency_entries(
    package_json_text: str, section: str, entries: dict[str, str]
) -> str:
    """Insert entries into one top-level dependency object, preserving layout.

    Handles the generated multi-line layout, an empty object on one line or
    across lines, and a compact object, without touching any sibling or nested
    field.
    """
    key_start, opening_brace = _find_top_level_dependency_brace(
        package_json_text, section
    )
    cursor = opening_brace + 1
    while cursor < len(package_json_text) and package_json_text[cursor] in " \t\r\n":
        cursor += 1

    line_start = package_json_text.rfind("\n", 0, key_start) + 1
    key_indent = package_json_text[line_start:key_start]
    if key_indent.strip():
        # The key shares its line with other content; entries start at column 0.
        key_indent = ""
    entry_indent = key_indent + "  "
    rendered_entries = "".join(
        f"{entry_indent}{json.dumps(name)}: {json.dumps(version)},\n"
        for name, version in sorted(entries.items())
    )

    if cursor < len(package_json_text) and package_json_text[cursor] == "}":
        # Empty object: expand it and drop the final entry's trailing comma.
        body = rendered_entries.rstrip("\n").removesuffix(",") + "\n"
        return (
            package_json_text[: opening_brace + 1]
            + "\n"
            + body
            + key_indent
            + package_json_text[cursor:]
        )

    if "\n" not in package_json_text[opening_brace + 1 : cursor + 1]:
        # Content starts on the same line: insert inline after the brace.
        inline_entries = "".join(
            f"{json.dumps(name)}: {json.dumps(version)}, "
            for name, version in sorted(entries.items())
        )
        return (
            package_json_text[: opening_brace + 1]
            + inline_entries
            + package_json_text[opening_brace + 1 :]
        )

    # Content starts on a following line: insert before it.
    line_end = package_json_text.find("\n", opening_brace)
    if line_end == -1:
        raise ValueError(f"frontend/package.json '{section}' cannot be extended safely")
    return (
        package_json_text[: line_end + 1]
        + rendered_entries
        + package_json_text[line_end + 1 :]
    )


def _write_validated_package_json(path: Path, content: str) -> None:
    """Atomically write manifest content after the rewritten document parses.

    Atomic replacement by directory entry means the write can neither follow a
    recipient symlink into the donor nor share an inode with a donor file.
    """
    try:
        json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            f"Refusing to write invalid JSON to {path}: {error}"
        ) from error
    _write_text_atomically(path, content)


def _insert_frontend_dependencies(
    package_json_path: Path, additions: dict[str, dict[str, str]]
) -> bool:
    """Insert missing donor dependencies and return whether the file changed."""
    if not any(additions.values()):
        return False
    original = package_json_path.read_text()
    updated = original
    for section in _DEPENDENCY_SECTIONS:
        entries = additions.get(section) or {}
        if entries:
            updated = _insert_dependency_entries(updated, section, entries)
    _write_validated_package_json(package_json_path, updated)
    return updated != original
