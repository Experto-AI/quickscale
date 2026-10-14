#!/usr/bin/env python3
"""
Private sibling: the local-CI arm and Makefile gate-help projections (SA275b).

``scripts/check_ci_locally.sh``'s display arms and the marked gate-help region
of the ``Makefile`` help block are rendered from each gate's registry-owned
``local`` and ``makefile_help`` metadata; the facade re-exports this module's
names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _sync_ci_gate_catalog import (
    LOCAL_ARMS_BEGIN,
    LOCAL_ARMS_END,
    MAKEFILE_HELP_BEGIN,
    MAKEFILE_HELP_END,
)
from _sync_ci_gate_core import (
    DEFAULT_LOCAL_SCRIPT,
    DEFAULT_MAKEFILE,
    DEFAULT_REGISTRY,
    GeneratorError,
    _line_index,
    _parse_registry,
    _replace_marked_region,
)

_LOCAL_ARM_FIELDS = ("order", "description", "success", "failure_label")
_MAKEFILE_HELP_FIELDS = ("order", "text")


def _ordered_metadata_gates(
    gates: list[dict[str, Any]], key: str, fields: tuple[str, ...]
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """
    Validate and return the ``(gate, metadata)`` pairs sorted by metadata order.

    Every gate carrying the metadata must also declare the Make target its
    rendered station keys on, or the projection would emit an unaddressable
    station; the schema enforces the same invariant, and this fail-closed
    re-check keeps the projection correct for hand-built gate lists.
    """
    entries: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for gate in gates:
        metadata = gate.get(key)
        if metadata is None:
            continue
        if not isinstance(metadata, dict):
            raise GeneratorError(f"gate {gate['id']!r} has a non-dict {key} metadata object")
        for field in fields:
            if field not in metadata:
                raise GeneratorError(
                    f"gate {gate['id']!r} is missing {key} metadata field {field!r}"
                )
        order = metadata["order"]
        if not isinstance(order, int) or isinstance(order, bool):
            raise GeneratorError(f"gate {gate['id']!r} has a non-integer {key} order")
        if not isinstance(gate["bindings"].get("make_target"), str):
            raise GeneratorError(f"gate {gate['id']!r} has {key} metadata but no Make target")
        entries.append((gate, metadata))
    return sorted(entries, key=lambda entry: entry[1]["order"])


def _render_local_arms(gates: list[dict[str, Any]]) -> list[str]:
    """Render the local runner's display arms in registry-declared order."""
    rendered: list[str] = []
    for gate, metadata in _ordered_metadata_gates(gates, "local", _LOCAL_ARM_FIELDS):
        target = gate["bindings"]["make_target"]
        rendered.extend(
            (
                f"        {target})\n",
                f'            LOCAL_GATE_DESCRIPTION="{metadata["description"]}"\n',
                f'            LOCAL_GATE_SUCCESS="{metadata["success"]}"\n',
                f'            LOCAL_GATE_FAILURE_LABEL="{metadata["failure_label"]}"\n',
                "            ;;\n",
            )
        )
    return rendered


def _render_makefile_help(gates: list[dict[str, Any]]) -> list[str]:
    """Render the Makefile help block's gate lines in registry-declared order."""
    rendered: list[str] = []
    for gate, metadata in _ordered_metadata_gates(gates, "makefile_help", _MAKEFILE_HELP_FIELDS):
        target = gate["bindings"]["make_target"]
        if not metadata["text"].startswith(f"make {target} "):
            raise GeneratorError(
                f"gate {gate['id']!r}: makefile_help text does not name its Make target"
            )
        rendered.append(f'\t@echo "  {metadata["text"]}"\n')
    return rendered


def _validate_arm_markers(lines: list[str]) -> None:
    """Prove the arm markers own the describe case's arm region."""
    begins = _line_index(lines, LOCAL_ARMS_BEGIN)
    ends = _line_index(lines, LOCAL_ARMS_END)
    if len(begins) != 1 or len(ends) != 1:
        raise GeneratorError(
            "check_ci_locally.sh: local arm marker pair is incomplete or duplicated"
        )
    begin, end = begins[0], ends[0]
    if begin >= end:
        raise GeneratorError("check_ci_locally.sh: local arm marker order is invalid")
    if begin == 0 or lines[begin - 1].rstrip("\n") != '    case "$target" in':
        raise GeneratorError(
            "check_ci_locally.sh: local arm markers are not owned by the describe case"
        )
    if end + 1 >= len(lines) or lines[end + 1].rstrip("\n") != "        *)":
        raise GeneratorError("check_ci_locally.sh: local arm markers do not enclose the arm region")
    if any("GENERATED:" in line for line in lines[begin + 1 : end]):
        raise GeneratorError("check_ci_locally.sh: local arm region contains nested markers")


def _help_recipe_span(lines: list[str]) -> tuple[int, int]:
    """Return the recipe line span of the Makefile's ``help`` target."""
    starts = _line_index(lines, "help:")
    if len(starts) != 1:
        raise GeneratorError("Makefile: expected exactly one help target")
    start = starts[0] + 1
    end = start
    while end < len(lines) and lines[end].startswith("\t"):
        end += 1
    return start, end


def _validate_help_markers(lines: list[str]) -> None:
    """Prove the help markers own a region inside the ``help`` recipe."""
    begins = _line_index(lines, MAKEFILE_HELP_BEGIN)
    ends = _line_index(lines, MAKEFILE_HELP_END)
    if len(begins) != 1 or len(ends) != 1:
        raise GeneratorError("Makefile: gate-help marker pair is incomplete or duplicated")
    begin, end = begins[0], ends[0]
    if begin >= end:
        raise GeneratorError("Makefile: gate-help marker order is invalid")
    recipe_start, recipe_end = _help_recipe_span(lines)
    if not recipe_start <= begin < end < recipe_end:
        raise GeneratorError("Makefile: gate-help markers are not owned by the help recipe")
    if any("GENERATED:" in line for line in lines[begin + 1 : end]):
        raise GeneratorError("Makefile: gate-help region contains nested markers")


def expected_local_arms_text(text: str, gates: list[dict[str, Any]]) -> str:
    """Return local-CI script text with only the owned arm region projected."""
    lines = text.splitlines(keepends=True)
    _validate_arm_markers(lines)
    return "".join(
        _replace_marked_region(
            lines,
            LOCAL_ARMS_BEGIN,
            LOCAL_ARMS_END,
            _render_local_arms(gates),
            "local gate-arm region",
        )
    )


def expected_makefile_help_text(text: str, gates: list[dict[str, Any]]) -> str:
    """Return Makefile text with only the owned gate-help region projected."""
    lines = text.splitlines(keepends=True)
    _validate_help_markers(lines)
    return "".join(
        _replace_marked_region(
            lines,
            MAKEFILE_HELP_BEGIN,
            MAKEFILE_HELP_END,
            _render_makefile_help(gates),
            "Makefile gate-help region",
        )
    )


def sync_local_arms(
    path: Path = DEFAULT_LOCAL_SCRIPT, registry_path: Path = DEFAULT_REGISTRY
) -> tuple[bool, str]:
    """Compute expected local-CI script content and return ``(drift, text)``."""
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeneratorError(f"cannot read local CI script {path}: {exc}") from None
    gates = _parse_registry(registry_path)
    expected = expected_local_arms_text(current, gates)
    return current != expected, expected


def sync_makefile_help(
    path: Path = DEFAULT_MAKEFILE, registry_path: Path = DEFAULT_REGISTRY
) -> tuple[bool, str]:
    """Compute expected Makefile content and return ``(drift, text)``."""
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeneratorError(f"cannot read Makefile {path}: {exc}") from None
    gates = _parse_registry(registry_path)
    expected = expected_makefile_help_text(current, gates)
    return current != expected, expected
