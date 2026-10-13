#!/usr/bin/env python3
"""
Private sibling: the publish workflow projection for ``sync_ci_gate_jobs``.

The publish gate-step region is rendered from the registry's ``publish``
membership through the catalog; the facade re-exports this module's names.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from _sync_ci_gate_catalog import (
    PUBLISH_BEGIN,
    PUBLISH_END,
    PUBLISH_GATE_ORDER,
    PUBLISH_STEP_CATALOG,
)
from _sync_ci_gate_core import (
    DEFAULT_PUBLISH_WORKFLOW,
    DEFAULT_REGISTRY,
    GeneratorError,
    _job_steps,
    _line_index,
    _parse_registry,
    _parse_workflow,
    _replace_marked_region,
    _top_level_job_headers,
)


def _publish_gate_bindings(gates: list[dict[str, Any]]) -> dict[str, str]:
    """
    Validate and return the publish-context gate Make targets.

    The registry's ``publish`` context membership must equal the helper-owned
    catalog exactly: a publish-bound gate without a catalog step, or a catalog
    step for a gate outside the publish context, fails closed so the generated
    workflow cannot silently drift from the registry.
    """
    publish_gates = [gate for gate in gates if "publish" in gate["required_contexts"]]
    publish_ids = tuple(gate["id"] for gate in publish_gates)
    expected = frozenset(PUBLISH_GATE_ORDER)
    if frozenset(publish_ids) != expected or len(publish_ids) != len(PUBLISH_GATE_ORDER):
        raise GeneratorError(
            "unsupported publish gate set: "
            f"expected {list(PUBLISH_GATE_ORDER)!r}, got {list(publish_ids)!r}"
        )
    if set(PUBLISH_STEP_CATALOG) != expected:
        raise GeneratorError("publish step catalog does not match the supported gate set")
    bindings: dict[str, str] = {}
    for gate in publish_gates:
        make_target = gate["bindings"].get("make_target")
        if not isinstance(make_target, str):
            raise GeneratorError(f"publish gate {gate['id']!r} has no Make target")
        bindings[gate["id"]] = make_target
    return bindings


def _publish_run_lines(gate_id: str, bindings: dict[str, str]) -> tuple[str, ...]:
    """Return the shell lines of one publish gate step."""
    spec = PUBLISH_STEP_CATALOG[gate_id]
    command = f"make {bindings[gate_id]}"
    if spec.command_prefix is not None:
        command = f"{spec.command_prefix} {command}"
    return (command,)


def _publish_expected_run(gate_id: str, bindings: dict[str, str]) -> str:
    """Return the exact YAML-parsed ``run`` value of one publish gate step."""
    return "".join(f"{line}\n" for line in _publish_run_lines(gate_id, bindings))


def _render_publish_steps(gates: list[dict[str, Any]]) -> list[str]:
    """Render the owned publish gate-step lines in catalog order."""
    bindings = _publish_gate_bindings(gates)
    rendered: list[str] = []
    for index, gate_id in enumerate(PUBLISH_GATE_ORDER):
        spec = PUBLISH_STEP_CATALOG[gate_id]
        if index:
            rendered.append("\n")
        rendered.append(f"      - name: {spec.step_name}\n")
        rendered.append("        run: |\n")
        for line in _publish_run_lines(gate_id, bindings):
            rendered.append(f"          {line}\n")
    return rendered


def _publish_test_steps_span(lines: list[str]) -> tuple[int, int]:
    """Return the ``steps:`` line index and job end of the top-level ``test`` job."""
    headers = _top_level_job_headers(lines)
    starts = [index for index, job_id in headers if job_id == "test"]
    if len(starts) != 1:
        raise GeneratorError("publish.yml: expected exactly one top-level test job")
    start = starts[0]
    end = next((index for index, _ in headers if index > start), len(lines))
    steps_lines = [
        index for index in range(start + 1, end) if lines[index].rstrip("\n") == "    steps:"
    ]
    if len(steps_lines) != 1:
        raise GeneratorError("publish.yml: test job must declare exactly one steps list")
    return steps_lines[0], end


def _publish_step_entries(
    lines: list[str], steps_line: int, span_end: int
) -> list[tuple[int, int]]:
    """Return the ``(start, end)`` line slices of every test-job step entry."""
    starts = [
        index for index in range(steps_line + 1, span_end) if lines[index].startswith("      - ")
    ]
    entries: list[tuple[int, int]] = []
    for index, start in enumerate(starts):
        end = starts[index + 1] if index + 1 < len(starts) else span_end
        entries.append((start, end))
    return entries


def _publish_entry_content_end(lines: list[str], start: int, end: int) -> int:
    """Return the slice end excluding trailing blank lines."""
    content_end = end
    while content_end > start and not lines[content_end - 1].strip():
        content_end -= 1
    return content_end


def _match_publish_entries(
    lines: list[str], entries: list[tuple[int, int]]
) -> dict[str, tuple[int, int]]:
    """Locate catalog-owned step entries by their exact catalog name line."""
    located: dict[str, tuple[int, int]] = {}
    for gate_id in PUBLISH_GATE_ORDER:
        name = PUBLISH_STEP_CATALOG[gate_id].step_name
        needle = f"      - name: {name}\n"
        matches = [entry for entry in entries if needle in "".join(lines[entry[0] : entry[1]])]
        if len(matches) > 1:
            raise GeneratorError(f"publish.yml: duplicate gate step named {name!r}")
        if matches:
            located[gate_id] = matches[0]
    return located


def _any_publish_marker_present(lines: list[str]) -> bool:
    return any(_line_index(lines, marker) for marker in (PUBLISH_BEGIN, PUBLISH_END))


def _publish_marker_bounds(lines: list[str]) -> tuple[int, int, int, int]:
    """Return the validated marker bounds and the enclosing test-job span."""
    begins = _line_index(lines, PUBLISH_BEGIN)
    ends = _line_index(lines, PUBLISH_END)
    if len(begins) != 1 or len(ends) != 1:
        raise GeneratorError("publish.yml: generated marker pair is incomplete or duplicated")
    begin, end = begins[0], ends[0]
    if begin >= end:
        raise GeneratorError("publish.yml: generated marker order is invalid")
    steps_line, span_end = _publish_test_steps_span(lines)
    if not steps_line < begin < end < span_end:
        raise GeneratorError("publish.yml: generated markers are outside the test job's steps")
    return begin, end, steps_line, span_end


def _validate_publish_markers(lines: list[str]) -> None:
    """
    Prove the publish marker pair owns exactly the catalog-owned gate steps.

    Line matching alone is insufficient: a marker pair moved into another job,
    or stretched over a sibling step, must not authorize rewriting those bytes.
    """
    begin, end, steps_line, span_end = _publish_marker_bounds(lines)
    if not lines[begin + 1].startswith("      - "):
        raise GeneratorError("publish.yml: begin marker is not adjacent to a gate step")
    entries = _publish_step_entries(lines, steps_line, span_end)
    located = _match_publish_entries(lines, entries)
    missing = [gate_id for gate_id in PUBLISH_GATE_ORDER if gate_id not in located]
    if missing:
        raise GeneratorError(
            "publish.yml: generated region is missing gate step(s): " + ", ".join(missing)
        )
    starts = [located[gate_id][0] for gate_id in PUBLISH_GATE_ORDER]
    if begin + 1 != starts[0]:
        raise GeneratorError("publish.yml: begin marker is not adjacent to the first gate step")
    last_start, last_end = located[PUBLISH_GATE_ORDER[-1]]
    if not last_start < end < last_end:
        raise GeneratorError("publish.yml: end marker is not at the gate-step region boundary")
    inside = [start for start, _ in entries if begin < start < end]
    if inside != starts:
        raise GeneratorError("publish.yml: marker region contains non-gate steps")
    if any("GENERATED:" in line for line in lines[begin + 1 : end]):
        raise GeneratorError("publish.yml: generated region contains nested markers")
    # A comment line does not end the last step's YAML mapping: step-level
    # content after the end marker still attaches to the final gate step, so
    # it must fail closed instead of riding along unchecked.
    trailing = lines[end + 1 : last_end]
    if any(
        line.strip() and not line.lstrip().startswith("#") and len(line) - len(line.lstrip(" ")) > 6
        for line in trailing
    ):
        raise GeneratorError(
            "publish.yml: content after the end marker belongs to the last gate step"
        )


def _bootstrap_publish_markers(lines: list[str], gates: list[dict[str, Any]]) -> list[str]:
    """Wrap the existing catalog-owned gate steps in the generated marker pair."""
    _publish_gate_bindings(gates)
    steps_line, span_end = _publish_test_steps_span(lines)
    entries = _publish_step_entries(lines, steps_line, span_end)
    located = _match_publish_entries(lines, entries)
    if not located:
        raise GeneratorError("publish.yml: no catalog-owned gate steps were found")
    order = [gate_id for gate_id in PUBLISH_GATE_ORDER if gate_id in located]
    entry_index = {entry: index for index, entry in enumerate(entries)}
    indices = [entry_index[located[gate_id]] for gate_id in order]
    if indices != list(range(indices[0], indices[0] + len(indices))):
        raise GeneratorError("publish.yml: catalog-owned gate steps are not one contiguous region")
    region_start = located[order[0]][0]
    region_end = _publish_entry_content_end(lines, *located[order[-1]])
    replacement = [PUBLISH_BEGIN + "\n", *_render_publish_steps(gates), PUBLISH_END + "\n"]
    return lines[:region_start] + replacement + lines[region_end:]


def _collect_publish_occurrences(
    jobs: dict[str, Any], catalog_names: set[str]
) -> dict[str, list[tuple[str, int]]]:
    """Return every catalog-named step occurrence, keyed by step name."""
    occurrences: dict[str, list[tuple[str, int]]] = {name: [] for name in catalog_names}
    for job_id, job_value in jobs.items():
        if not isinstance(job_value, dict):
            continue
        job_steps = job_value.get("steps", [])
        if not isinstance(job_steps, list):
            continue
        for index, step in enumerate(job_steps):
            if isinstance(step, dict) and step.get("name") in catalog_names:
                occurrences[step["name"]].append((job_id, index))
    return occurrences


def _validate_catalog_steps(
    steps: list[dict[str, Any]],
    occurrences: dict[str, list[tuple[str, int]]],
    bindings: dict[str, str],
    *,
    strict: bool,
) -> list[tuple[int, str]]:
    """Validate every catalog-owned step and return its ``(index, gate_id)`` rows."""
    located: list[tuple[int, str]] = []
    for gate_id in PUBLISH_GATE_ORDER:
        spec = PUBLISH_STEP_CATALOG[gate_id]
        matches = occurrences[spec.step_name]
        if len(matches) > 1:
            raise GeneratorError(f"publish.yml: duplicate gate step named {spec.step_name!r}")
        if not matches:
            if strict:
                raise GeneratorError(f"publish.yml: gate step named {spec.step_name!r} is missing")
            continue
        job_id, index = matches[0]
        if job_id != "test":
            raise GeneratorError(
                f"publish.yml: gate step {spec.step_name!r} is outside the test job"
            )
        run = steps[index].get("run")
        if not isinstance(run, str):
            raise GeneratorError(f"publish.yml: gate step {spec.step_name!r} has no run block")
        if strict and run != _publish_expected_run(gate_id, bindings):
            raise GeneratorError(f"publish.yml: gate step {spec.step_name!r} run drifted")
        located.append((index, gate_id))
    return located


def _validate_publish_projection(text: str, gates: list[dict[str, Any]], *, strict: bool) -> None:
    """
    Validate the publish gate-step projection.

    ``strict=True`` (post-generation) requires every catalog step, its exact
    order, and its exact registry-derived run value.  ``strict=False``
    (pre-edit) locates the steps by their catalog names so a stale owned run
    value can be projected by ``--write``, exactly like the hosted region.
    """
    workflow = _parse_workflow(text, "publish.yml")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise GeneratorError("publish.yml: jobs must be a mapping")
    job = jobs.get("test")
    if not isinstance(job, dict):
        raise GeneratorError("publish.yml: jobs.test must be a mapping")
    steps = _job_steps(job, "test")
    bindings = _publish_gate_bindings(gates)
    catalog_names = {PUBLISH_STEP_CATALOG[gate_id].step_name for gate_id in PUBLISH_GATE_ORDER}
    occurrences = _collect_publish_occurrences(jobs, catalog_names)
    located = _validate_catalog_steps(steps, occurrences, bindings, strict=strict)
    indices = [index for index, _ in located]
    if indices != sorted(indices):
        raise GeneratorError("publish.yml: catalog-owned gate steps are out of order")


def expected_publish_workflow_text(text: str, gates: list[dict[str, Any]]) -> str:
    """Return publish workflow text with only the owned gate-step region projected."""
    _validate_publish_projection(text, gates, strict=False)
    lines = text.splitlines(keepends=True)
    if _any_publish_marker_present(lines):
        _validate_publish_markers(lines)
        lines = _replace_marked_region(
            lines,
            PUBLISH_BEGIN,
            PUBLISH_END,
            _render_publish_steps(gates),
            "publish gate-step region",
        )
    else:
        lines = _bootstrap_publish_markers(lines, gates)
    result = "".join(lines)
    _validate_publish_projection(result, gates, strict=True)
    _validate_publish_markers(result.splitlines(keepends=True))
    return result


def sync_publish_workflow(
    path: Path = DEFAULT_PUBLISH_WORKFLOW, registry_path: Path = DEFAULT_REGISTRY
) -> tuple[bool, str]:
    """Compute expected publish content and return ``(drift, expected_text)``."""
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeneratorError(f"cannot read workflow {path}: {exc}") from None
    gates = _parse_registry(registry_path)
    expected = expected_publish_workflow_text(current, gates)
    return current != expected, expected
