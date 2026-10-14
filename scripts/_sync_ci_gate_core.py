#!/usr/bin/env python3
"""
Private sibling: shared loading and line utilities for ``sync_ci_gate_jobs``.

Paths, the deterministic ``GeneratorError``, strict YAML/JSON parsing, line and
marker helpers, hosted-job/needs helpers, YAML job-header discovery, and the
atomic writer.  The facade re-exports this module's names; the projection
siblings import the defining names directly.
"""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError:  # pragma: no cover - Poetry supplies PyYAML
    yaml = None  # type: ignore[assignment]

try:
    from check_gate_parity import SchemaValidationError, _parse_json_strict, _validate_registry
except ImportError:  # pragma: no cover - direct script execution supplies scripts/ on sys.path
    SchemaValidationError = None  # type: ignore[assignment,misc]
    _parse_json_strict = None  # type: ignore[assignment]
    _validate_registry = None  # type: ignore[assignment]

from _sync_ci_gate_catalog import (
    EXPECTED_UNOWNED_JOB_IDS,
    FIXED_NEEDS,
    JOB_BEGIN,
    JOB_END,
    NEEDS_ALL_HOSTED_CONSUMERS,
    NEEDS_BEGIN,
    NEEDS_END,
    NEEDS_GATE_IDS,
    UNOWNED_JOB_RATIONALES,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEFAULT_E2E_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "e2e.yml"
DEFAULT_PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "publish.yml"
DEFAULT_REGISTRY = REPO_ROOT / "scripts" / "gate_registry.json"
DEFAULT_MAKE_INCLUDE = REPO_ROOT / "scripts" / "gates.mk"
DEFAULT_DOCS = REPO_ROOT / "docs" / "technical" / "validation_policy.md"


class GeneratorError(ValueError):
    """A deterministic malformed-input or invariant failure."""


def _validate_unowned_job_rationales() -> None:
    if frozenset(UNOWNED_JOB_RATIONALES) != EXPECTED_UNOWNED_JOB_IDS:
        raise GeneratorError(
            "unowned hosted-job rationale keys do not match the seven-job exemption set"
        )
    if any(
        not isinstance(reason, str) or not reason.strip()
        for reason in UNOWNED_JOB_RATIONALES.values()
    ):
        raise GeneratorError("every unowned hosted job must have a nonempty rationale")


class _DuplicateYamlKeyError(ValueError):
    """Raised by the strict BaseLoader constructor for duplicate keys."""


def _yaml_mapping(loader: Any, node: Any) -> dict[Any, Any]:
    mapping: dict[Any, Any] = {}
    seen: set[Any] = set()
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=False)
        if key in seen:
            raise _DuplicateYamlKeyError(f"Duplicate YAML key: {key!r}")
        seen.add(key)
        mapping[key] = loader.construct_object(value_node, deep=False)
    return mapping


def _parse_workflow(text: str, label: str) -> dict[str, Any]:
    """Parse YAML with BaseLoader semantics and duplicate-key rejection."""
    if yaml is None:
        raise GeneratorError("PyYAML is not available")
    loader_type: Any = type("StrictBaseLoader", (yaml.BaseLoader,), {})
    loader_type.add_constructor(
        yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
        _yaml_mapping,
    )
    try:
        value = yaml.load(text, Loader=loader_type)
    except _DuplicateYamlKeyError as exc:
        raise GeneratorError(f"{label}: {exc}") from None
    except yaml.YAMLError as exc:
        raise GeneratorError(f"{label}: YAML parse error: {exc}") from None
    except Exception as exc:
        raise GeneratorError(f"{label}: YAML parse error: {exc}") from None
    if not isinstance(value, dict):
        raise GeneratorError(f"{label}: workflow must be a YAML mapping")
    return value


def _parse_registry(path: Path) -> list[dict[str, Any]]:
    """Load the registry with the parity checker's authoritative schema."""
    if SchemaValidationError is None or _parse_json_strict is None or _validate_registry is None:
        raise GeneratorError("registry: authoritative parity validator is unavailable")
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeneratorError(f"cannot read registry {path}: {exc}") from None
    try:
        data = _parse_json_strict(raw, str(path))
        return _validate_registry(data)
    except SchemaValidationError as exc:
        location = f"{exc.source}:{exc.path}" if exc.path else exc.source
        raise GeneratorError(f"{location}: {exc.message}") from None


def _job_steps(job: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise GeneratorError(f"jobs.{job_id}.steps must be a list of mappings")
    return steps


def _line_index(lines: list[str], marker: str) -> list[int]:
    return [index for index, line in enumerate(lines) if line.rstrip("\n") == marker]


def _replace_marked_region(
    lines: list[str], begin: str, end: str, replacement: list[str], label: str
) -> list[str]:
    begins = _line_index(lines, begin)
    ends = _line_index(lines, end)
    if len(begins) != 1 or len(ends) != 1:
        raise GeneratorError(f"{label}: expected exactly one marker pair")
    if begins[0] >= ends[0]:
        raise GeneratorError(f"{label}: marker order is invalid")
    return lines[: begins[0] + 1] + replacement + lines[ends[0] :]


def _all_markers_present(lines: list[str]) -> bool:
    markers = [JOB_BEGIN, JOB_END, *NEEDS_BEGIN.values(), *NEEDS_END.values()]
    return all(len(_line_index(lines, marker)) == 1 for marker in markers)


def _any_marker_present(lines: list[str]) -> bool:
    markers = [JOB_BEGIN, JOB_END, *NEEDS_BEGIN.values(), *NEEDS_END.values()]
    return any(_line_index(lines, marker) for marker in markers)


def _top_level_job_headers(lines: list[str]) -> list[tuple[int, str]]:
    """Find job headers beneath ``jobs:`` without interpreting YAML scalars."""
    jobs_line = next((i for i, line in enumerate(lines) if line.rstrip() == "jobs:"), None)
    if jobs_line is None:
        raise GeneratorError("ci.yml: jobs section is missing")
    headers: list[tuple[int, str]] = []
    header_re = re.compile(r"^  ([A-Za-z][A-Za-z0-9_-]*):\s*$")
    for index in range(jobs_line + 1, len(lines)):
        match = header_re.match(lines[index].rstrip("\n"))
        if match:
            headers.append((index, match.group(1)))
    return headers


def _hosted_gates(gates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """
    Return the hosted-context gates in their registry-declared order.

    The registry's per-gate ``hosted`` metadata owns the order, display name,
    and check-step label the hosted-workflow projection consumes (SA275a);
    this helper fails closed when a hosted gate does not carry it.
    """
    hosted = [gate for gate in gates if "hosted" in gate["required_contexts"]]
    for gate in hosted:
        metadata = gate.get("hosted")
        if not isinstance(metadata, dict):
            raise GeneratorError(f"hosted gate {gate['id']!r} has no hosted metadata")
        for key in ("order", "display_name", "check_step_name"):
            if key not in metadata:
                raise GeneratorError(
                    f"hosted gate {gate['id']!r} is missing hosted metadata field {key!r}"
                )
        if not isinstance(metadata["order"], int) or isinstance(metadata["order"], bool):
            raise GeneratorError(f"hosted gate {gate['id']!r} has a non-integer hosted order")
    return sorted(hosted, key=lambda gate: gate["hosted"]["order"])


def _registry_bindings(gates: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Validate and return the hosted gate bindings, in registry order."""
    bindings: dict[str, tuple[str, str]] = {}
    for gate in _hosted_gates(gates):
        ci_job = gate["bindings"].get("ci_job")
        make_target = gate["bindings"].get("make_target")
        if not isinstance(ci_job, str) or not isinstance(make_target, str):
            raise GeneratorError(f"hosted gate {gate['id']!r} has incomplete bindings")
        bindings[gate["id"]] = (ci_job, make_target)
    return bindings


def _expected_needs(gates: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    bindings = _registry_bindings(gates)
    all_hosted_jobs = tuple(bindings[gate_id][0] for gate_id in bindings)
    needs: dict[str, tuple[str, ...]] = {
        consumer: FIXED_NEEDS + all_hosted_jobs for consumer in NEEDS_ALL_HOSTED_CONSUMERS
    }
    for consumer, gate_ids in NEEDS_GATE_IDS.items():
        try:
            registry_jobs = tuple(bindings[gate_id][0] for gate_id in gate_ids)
        except KeyError as exc:  # defensive: _registry_bindings checked the set
            raise GeneratorError(
                f"needs policy references unsupported gate {exc.args[0]!r}"
            ) from None
        needs[consumer] = FIXED_NEEDS + registry_jobs
    return needs


def _render_needs(gates: list[dict[str, Any]], consumer: str) -> str:
    expected = _expected_needs(gates)[consumer]
    return f"    needs: [{', '.join(expected)}]"


def _locate_hosted_jobs(
    jobs: dict[str, Any],
    hosted_gates: list[dict[str, Any]],
    label: str,
    *,
    allow_missing: bool = False,
) -> dict[str, str]:
    """
    Locate the registry-bound hosted jobs by their registry-owned display names.

    Display metadata is registry data, so the generated job IDs may be stale
    before an edit: a registry ``ci_job`` (F-005) or Make-target change must be
    projectable by ``--write`` without treating the previously generated job
    IDs as drift.
    """
    located: dict[str, str] = {}
    for gate in hosted_gates:
        display_name = gate["hosted"]["display_name"]
        matches = [
            job_id
            for job_id, job in jobs.items()
            if isinstance(job, dict) and job.get("name") == display_name
        ]
        if not matches and allow_missing:
            continue
        if len(matches) != 1:
            raise GeneratorError(f"{label}: expected exactly one job named {display_name!r}")
        located[gate["id"]] = matches[0]
    return located


_PINNED_REF_RE = re.compile(r"[0-9a-f]{40}")


def _pins_same_action(actual: Any, expected_ref: str) -> bool:
    """
    Return True when *actual* pins the same action as *expected_ref* to a SHA.

    Pre-edit projection tolerates a stale commit SHA — an action-pin refresh is
    projected by ``--write`` — but not a different action, a missing pin, or a
    mutable ref.
    """
    if not isinstance(actual, str) or "@" not in actual:
        return False
    actual_repo, _, actual_ref = actual.rpartition("@")
    expected_repo, _, _ = expected_ref.rpartition("@")
    return actual_repo == expected_repo and _PINNED_REF_RE.fullmatch(actual_ref) is not None


def _step_matches(actual: Any, expected: dict[str, Any], *, strict: bool) -> bool:
    """Compare one job step; outside strict mode a stale action ref is tolerated."""
    if not isinstance(actual, dict):
        return False
    if strict:
        return actual == expected
    return {key: value for key, value in actual.items() if key != "uses"} == {
        key: value for key, value in expected.items() if key != "uses"
    }


def _locate_hosted_job_headers(
    lines: list[str], hosted_gates: list[dict[str, Any]], *, allow_missing: bool = False
) -> list[int]:
    """
    Locate the registry-bound hosted job header lines by their display names.

    Use registry-owned display metadata to find the (possibly stale) hosted job
    IDs; this permits a registry ``ci_job`` (F-005) or Make-target edit while
    keeping the bootstrap independent of generated job text.
    """
    headers = _top_level_job_headers(lines)
    starts: list[int] = []
    for gate in hosted_gates:
        expected_name = gate["hosted"]["display_name"]
        found = [
            index
            for index, _job_id in headers
            if f"    name: {expected_name}\n"
            in "".join(
                lines[
                    index : next(
                        (position for position, _ in headers if position > index), len(lines)
                    )
                ]
            )
        ]
        if not found and allow_missing:
            continue
        if len(found) != 1:
            raise GeneratorError(f"hosted job bootstrap: expected one job named {expected_name!r}")
        starts.append(found[0])
    if not starts:
        return []
    headers_between = [position for position, _ in headers if starts[0] <= position <= starts[-1]]
    if starts != sorted(starts) or headers_between != starts:
        raise GeneratorError(
            "hosted job bootstrap: registry-bound jobs are not one contiguous region"
        )
    return starts


def _sync_needs_markers(lines: list[str], gates: list[dict[str, Any]]) -> list[str]:
    headers = _top_level_job_headers(lines)
    locations = {job_id: index for index, job_id in headers}
    for consumer in NEEDS_BEGIN:
        if consumer not in locations:
            raise GeneratorError(f"needs bootstrap: job {consumer!r} is missing")
        start = locations[consumer]
        end = next((position for position, _ in headers if position > start), len(lines))
        needs_lines = [
            index
            for index in range(start + 1, end)
            if re.match(r"^    needs:\s*", lines[index].rstrip("\n"))
        ]
        if len(needs_lines) != 1:
            raise GeneratorError(f"needs bootstrap: expected one needs line for {consumer}")
        line_index = needs_lines[0]
        replacement = [
            NEEDS_BEGIN[consumer] + "\n",
            _render_needs(gates, consumer) + "\n",
            NEEDS_END[consumer] + "\n",
        ]
        lines = lines[:line_index] + replacement + lines[line_index + 1 :]
        headers = _top_level_job_headers(lines)
        locations = {job_id: index for index, job_id in headers}
    return lines


def _atomic_write(path: Path, content: str) -> None:
    try:
        mode = path.stat().st_mode & 0o777
    except FileNotFoundError:
        mode = 0o644
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.chmod(mode)
        os.replace(temporary, path)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
