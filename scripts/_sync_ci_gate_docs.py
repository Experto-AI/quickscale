#!/usr/bin/env python3
"""
Private sibling: the gate-roster docs table projection for ``sync_ci_gate_jobs``.

The owned region in ``docs/technical/validation_policy.md`` is rendered from
the registry; the facade re-exports this module's names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _sync_ci_gate_catalog import DOCS_TABLE_BEGIN, DOCS_TABLE_END
from _sync_ci_gate_core import (
    DEFAULT_DOCS,
    DEFAULT_REGISTRY,
    GeneratorError,
    _line_index,
    _parse_registry,
    _replace_marked_region,
)


def _validate_docs_markers(lines: list[str]) -> None:
    """Prove the docs region owns exactly one ordered, unnested marker pair."""
    begins = _line_index(lines, DOCS_TABLE_BEGIN)
    ends = _line_index(lines, DOCS_TABLE_END)
    if len(begins) != 1 or len(ends) != 1:
        raise GeneratorError("docs table: generated marker pair is incomplete or duplicated")
    begin, end = begins[0], ends[0]
    if begin >= end:
        raise GeneratorError("docs table: generated marker order is invalid")
    if any("GENERATED:" in line for line in lines[begin + 1 : end]):
        raise GeneratorError("docs table: generated region contains nested markers")


def _render_docs_table(gates: list[dict[str, Any]]) -> list[str]:
    """Render the gate-roster table from the registry, in declaration order."""
    rendered = [
        "| Gate | Make target | Contexts | Local stage | Hosted job |\n",
        "|---|---|---|---|---|\n",
    ]
    for gate in gates:
        bindings = gate.get("bindings", {})
        target = bindings.get("make_target")
        stage = bindings.get("local_ci_stage")
        ci_job = bindings.get("ci_job")
        target_cell = f"`make {target}`" if isinstance(target, str) else "—"
        job_cell = f"`{ci_job}`" if isinstance(ci_job, str) else "—"
        stage_cell = str(stage) if isinstance(stage, int) and not isinstance(stage, bool) else "—"
        contexts = ", ".join(gate["required_contexts"])
        rendered.append(
            f"| `{gate['id']}` | {target_cell} | {contexts} | {stage_cell} | {job_cell} |\n"
        )
    return rendered


def expected_docs_text(text: str, gates: list[dict[str, Any]]) -> str:
    """Return docs text with only the owned gate-roster region projected."""
    lines = text.splitlines(keepends=True)
    _validate_docs_markers(lines)
    return "".join(
        _replace_marked_region(
            lines,
            DOCS_TABLE_BEGIN,
            DOCS_TABLE_END,
            _render_docs_table(gates),
            "gate-roster docs table",
        )
    )


def sync_docs_table(
    path: Path = DEFAULT_DOCS, registry_path: Path = DEFAULT_REGISTRY
) -> tuple[bool, str]:
    """Compute the generated docs table and return ``(drift, expected_text)``."""
    try:
        current = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise GeneratorError(f"cannot read docs table file {path}") from None
    except OSError as exc:
        raise GeneratorError(f"cannot read docs table file {path}: {exc}") from None
    gates = _parse_registry(registry_path)
    expected = expected_docs_text(current, gates)
    return current != expected, expected
