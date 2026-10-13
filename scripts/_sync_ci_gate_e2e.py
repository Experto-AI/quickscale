#!/usr/bin/env python3
"""
Private sibling: the E2E workflow projection for ``sync_ci_gate_jobs`` (SA267).

The E2E path allowlist region is rendered from the registry's ``e2e-trigger``
membership; the facade re-exports this module's names.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from _sync_ci_gate_catalog import E2E_PATHS_BEGIN, E2E_PATHS_END
from _sync_ci_gate_core import (
    DEFAULT_E2E_WORKFLOW,
    DEFAULT_REGISTRY,
    GeneratorError,
    _line_index,
    _parse_registry,
    _parse_workflow,
    _replace_marked_region,
)


def _expected_e2e_paths(gates: list[dict[str, Any]]) -> tuple[str, ...]:
    """
    Flatten E2E trigger inputs in registry declaration order.

    The allowlist is a partition: every path has exactly one owning gate.  A
    path claimed by two gates is a registry invariant failure, not an ordering
    the generated workflow can express, so generation fails closed instead of
    rendering a duplicate.
    """
    paths: list[str] = []
    owners: dict[str, str] = {}
    for gate in gates:
        if "e2e-trigger" in gate["required_contexts"]:
            trigger_inputs = gate["trigger_inputs"]
            if not isinstance(trigger_inputs, list) or not all(
                isinstance(path, str) for path in trigger_inputs
            ):
                raise GeneratorError(f"gate {gate['id']!r} trigger_inputs must be path strings")
            for path in trigger_inputs:
                owner = owners.get(path)
                if owner is not None:
                    raise GeneratorError(
                        f"e2e trigger path {path!r} is claimed by both {owner!r} and "
                        f"{gate['id']!r}; the allowlist partition admits one owner per path"
                    )
                owners[path] = gate["id"]
            paths.extend(trigger_inputs)
    return tuple(paths)


def _parse_e2e_workflow(text: str) -> dict[str, Any]:
    """Parse E2E YAML and require exactly one pull-request path sequence."""
    workflow = _parse_workflow(text, "e2e.yml")
    trigger = workflow.get("on")
    if not isinstance(trigger, dict):
        raise GeneratorError("e2e.yml: on must be a mapping")
    pull_request = trigger.get("pull_request")
    if not isinstance(pull_request, dict):
        raise GeneratorError("e2e.yml: on.pull_request must be a mapping")
    paths = pull_request.get("paths")
    if not isinstance(paths, list) or not all(isinstance(path, str) for path in paths):
        raise GeneratorError("e2e.yml: on.pull_request.paths must be a sequence of strings")
    return workflow


def _e2e_paths_line_indices(lines: list[str]) -> tuple[int, list[int]]:
    path_lines = [
        index for index, line in enumerate(lines) if re.match(r"^    paths:\s*$", line.rstrip("\n"))
    ]
    if len(path_lines) != 1:
        raise GeneratorError("e2e.yml: expected exactly one pull_request.paths declaration")
    paths_index = path_lines[0]
    pull_request_index = next(
        (
            index
            for index in range(paths_index - 1, -1, -1)
            if lines[index].rstrip("\n") == "  pull_request:"
        ),
        None,
    )
    if pull_request_index is None:
        raise GeneratorError("e2e.yml: pull_request.paths is misplaced")
    for index in range(pull_request_index + 1, paths_index):
        if lines[index].strip() and not lines[index].startswith("    "):
            raise GeneratorError("e2e.yml: pull_request.paths is misplaced")
    end = paths_index + 1
    while end < len(lines) and (
        not lines[end].strip()
        or lines[end].startswith("      - ")
        or lines[end].rstrip("\n") == E2E_PATHS_BEGIN
        or lines[end].rstrip("\n") == E2E_PATHS_END
    ):
        end += 1
    item_indices = [
        index for index in range(paths_index + 1, end) if lines[index].startswith("      - ")
    ]
    return paths_index, item_indices


def _render_e2e_paths(paths: tuple[str, ...]) -> list[str]:
    return [f"      - '{path}'\n" for path in paths]


def _validate_e2e_markers(lines: list[str]) -> tuple[int, int]:
    begins = _line_index(lines, E2E_PATHS_BEGIN)
    ends = _line_index(lines, E2E_PATHS_END)
    if len(begins) != 1 or len(ends) != 1:
        raise GeneratorError("e2e.yml: generated marker pair is incomplete or duplicated")
    begin, end = begins[0], ends[0]
    if begin >= end:
        raise GeneratorError("e2e.yml: generated marker order is invalid")
    paths_index, _ = _e2e_paths_line_indices(lines)
    pull_request_index = next(
        (
            index
            for index in range(paths_index - 1, -1, -1)
            if lines[index].rstrip() == "  pull_request:"
        ),
        None,
    )
    if pull_request_index is None or not pull_request_index < begin < end:
        raise GeneratorError("e2e.yml: generated markers are outside pull_request.paths")
    if begin != paths_index + 1:
        raise GeneratorError("e2e.yml: begin marker is not adjacent to paths sequence")
    if end != begin + 1 and any(
        not re.match(r"^      - .*$", line.rstrip("\n")) for line in lines[begin + 1 : end]
    ):
        raise GeneratorError("e2e.yml: generated region contains misplaced content")
    if any("GENERATED:" in line for line in lines[begin + 1 : end]):
        raise GeneratorError("e2e.yml: generated region contains nested markers")
    return begin, end


def expected_e2e_workflow_text(text: str, gates: list[dict[str, Any]]) -> str:
    """Return E2E workflow text with only the owned allowlist projected."""
    _parse_e2e_workflow(text)
    lines = text.splitlines(keepends=True)
    has_markers = any(_line_index(lines, marker) for marker in (E2E_PATHS_BEGIN, E2E_PATHS_END))
    if has_markers:
        _validate_e2e_markers(lines)
        replacement = _render_e2e_paths(_expected_e2e_paths(gates))
        lines = _replace_marked_region(
            lines, E2E_PATHS_BEGIN, E2E_PATHS_END, replacement, "E2E path region"
        )
    else:
        paths_index, path_items = _e2e_paths_line_indices(lines)
        replacement = [
            E2E_PATHS_BEGIN + "\n",
            *_render_e2e_paths(_expected_e2e_paths(gates)),
            E2E_PATHS_END + "\n",
        ]
        start = paths_index + 1
        end = path_items[-1] + 1 if path_items else start
        lines = lines[:start] + replacement + lines[end:]
    result = "".join(lines)
    _parse_e2e_workflow(result)
    _validate_e2e_markers(result.splitlines(keepends=True))
    return result


def sync_e2e_workflow(
    path: Path = DEFAULT_E2E_WORKFLOW, registry_path: Path = DEFAULT_REGISTRY
) -> tuple[bool, str]:
    """Compute expected E2E content and return ``(drift, expected_text)``."""
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeneratorError(f"cannot read E2E workflow {path}: {exc}") from None
    gates = _parse_registry(registry_path)
    expected = expected_e2e_workflow_text(current, gates)
    return current != expected, expected
