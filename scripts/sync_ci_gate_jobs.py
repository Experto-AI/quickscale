#!/usr/bin/env python3
"""
Synchronize registry-bound hosted CI jobs without rewriting ``ci.yml``.

The registry owns gate membership, hosted job IDs, and Make targets.  This
helper owns the intentionally static GitHub Actions display and step metadata.
Only the marked hosted-job and consumer-``needs`` regions are generated; all
other workflow text remains byte-for-byte untouched.

Exit codes:
    0 - clean (``--check``) or successfully written (``--write``)
    1 - generated text differs from the checked-in workflow (``--check``)
    2 - malformed input or an invariant violation
"""

from __future__ import annotations

import argparse
import difflib
import os
import re
import sys
import tempfile
from dataclasses import dataclass
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

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ci.yml"
DEFAULT_REGISTRY = REPO_ROOT / "scripts" / "gate_registry.json"

JOB_BEGIN = "  # BEGIN GENERATED: hosted-gate-jobs"
JOB_END = "  # END GENERATED: hosted-gate-jobs"
NEEDS_BEGIN = {
    "test": "    # BEGIN GENERATED: needs-test",
    "isolation-conformance": "    # BEGIN GENERATED: needs-isolation-conformance",
    "lint-cli": "    # BEGIN GENERATED: needs-lint-cli",
}
NEEDS_END = {
    "test": "    # END GENERATED: needs-test",
    "isolation-conformance": "    # END GENERATED: needs-isolation-conformance",
    "lint-cli": "    # END GENERATED: needs-lint-cli",
}

HOSTED_GATE_ORDER = (
    "check-core-compat",
    "check-module-core-imports",
    "check-manifest-sync",
    "check-org-context-primitives",
    "check-csrf-exempt",
)
UNOWNED_JOB_IDS = frozenset(
    {
        "lint-frontend",
        "backups-validation",
        "module-manifest-contract",
        "test",
        "isolation-conformance",
        "lint-cli",
    }
)
NEEDS_GATE_IDS = {
    "test": HOSTED_GATE_ORDER,
    "isolation-conformance": (
        "check-manifest-sync",
        "check-org-context-primitives",
        "check-csrf-exempt",
    ),
    "lint-cli": (
        "check-manifest-sync",
        "check-org-context-primitives",
        "check-csrf-exempt",
    ),
}
FIXED_NEEDS = ("backups-validation", "module-manifest-contract")


@dataclass(frozen=True)
class HostedJobSpec:
    """Static presentation and execution metadata for one hosted gate."""

    display_name: str
    check_step_name: str


HOSTED_JOB_CATALOG: dict[str, HostedJobSpec] = {
    "check-core-compat": HostedJobSpec(
        "Module-vs-Oldest-Core Compatibility",
        "Run module-vs-core compatibility check (static analysis + install/import probe)",
    ),
    "check-module-core-imports": HostedJobSpec(
        "Module-Core Import Linter",
        "Run module-core import linter",
    ),
    "check-manifest-sync": HostedJobSpec(
        "Manifest Sync Gate (SA16.1)",
        "Verify module manifests match core snapshots",
    ),
    "check-org-context-primitives": HostedJobSpec(
        "Org-Context Primitives Gate (SA13.4)",
        "Verify no external use of privatized org-context primitives",
    ),
    "check-csrf-exempt": HostedJobSpec(
        "CSRF-Exempt Gate (SA46)",
        "Verify every csrf_exempt callsite pairs with _enforce_csrf or signature verification",
    ),
}


class GeneratorError(ValueError):
    """A deterministic malformed-input or invariant failure."""


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
    loader_type = type("StrictBaseLoader", (yaml.BaseLoader,), {})
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


def _registry_bindings(gates: list[dict[str, Any]]) -> dict[str, tuple[str, str]]:
    """Validate and return the supported hosted gate bindings."""
    hosted = [
        gate
        for gate in gates
        if "hosted" in gate["required_contexts"] or gate["bindings"].get("ci_job") is not None
    ]
    hosted_ids = tuple(gate["id"] for gate in hosted)
    if hosted_ids != HOSTED_GATE_ORDER:
        raise GeneratorError(
            "unsupported hosted gate set: "
            f"expected {list(HOSTED_GATE_ORDER)!r}, got {list(hosted_ids)!r}"
        )
    bindings: dict[str, tuple[str, str]] = {}
    for gate in hosted:
        ci_job = gate["bindings"].get("ci_job")
        make_target = gate["bindings"].get("make_target")
        if not isinstance(ci_job, str) or not isinstance(make_target, str):
            raise GeneratorError(f"hosted gate {gate['id']!r} has incomplete bindings")
        bindings[gate["id"]] = (ci_job, make_target)
    return bindings


def _expected_needs(gates: list[dict[str, Any]]) -> dict[str, tuple[str, ...]]:
    bindings = _registry_bindings(gates)
    needs: dict[str, tuple[str, ...]] = {}
    for consumer, gate_ids in NEEDS_GATE_IDS.items():
        try:
            registry_jobs = tuple(bindings[gate_id][0] for gate_id in gate_ids)
        except KeyError as exc:  # defensive: _registry_bindings checked the set
            raise GeneratorError(
                f"needs policy references unsupported gate {exc.args[0]!r}"
            ) from None
        needs[consumer] = FIXED_NEEDS + registry_jobs
    return needs


def _check_gate_targets(gates: list[dict[str, Any]]) -> str:
    """Return registry-bound ``check-*`` targets for Make's parse-time use."""
    targets = tuple(
        gate["bindings"]["make_target"]
        for gate in gates
        if isinstance(gate.get("bindings"), dict)
        and isinstance(gate["bindings"].get("make_target"), str)
        and gate["bindings"]["make_target"].startswith("check-")
    )
    if not targets:
        raise GeneratorError("registry: no check-* Make targets are declared")
    return " ".join(targets)


def _job_steps(job: dict[str, Any], job_id: str) -> list[dict[str, Any]]:
    steps = job.get("steps")
    if not isinstance(steps, list) or not all(isinstance(step, dict) for step in steps):
        raise GeneratorError(f"jobs.{job_id}.steps must be a list of mappings")
    return steps


def _validate_workflow_projection(text: str, gates: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate the pre-edit workflow shape and all registry-bound static metadata."""
    workflow = _parse_workflow(text, "ci.yml")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise GeneratorError("ci.yml: jobs must be a mapping")
    bindings = _registry_bindings(gates)
    expected_job_ids = UNOWNED_JOB_IDS | {job_id for job_id, _ in bindings.values()}
    actual_job_ids = frozenset(jobs)
    if actual_job_ids != expected_job_ids:
        raise GeneratorError(
            "ci.yml: unsupported hosted job set: "
            f"expected {sorted(expected_job_ids)!r}, got {sorted(actual_job_ids)!r}"
        )

    for gate_id, (job_id, make_target) in bindings.items():
        job = jobs.get(job_id)
        if not isinstance(job, dict):
            raise GeneratorError(f"ci.yml: jobs.{job_id} must be a mapping")
        spec = HOSTED_JOB_CATALOG[gate_id]
        if job.get("name") != spec.display_name or job.get("runs-on") != "ubuntu-24.04":
            raise GeneratorError(f"ci.yml: jobs.{job_id} static display metadata drifted")
        steps = _job_steps(job, job_id)
        if len(steps) != 5:
            raise GeneratorError(f"ci.yml: jobs.{job_id} must retain exactly five steps")
        expected_uses = (
            "actions/checkout@v6",
            "actions/setup-python@v6",
            "snok/install-poetry@v1",
        )
        actual_uses = tuple(step.get("uses") for step in steps if "uses" in step)
        if actual_uses != expected_uses:
            raise GeneratorError(f"ci.yml: jobs.{job_id} action versions/ordering drifted")
        if steps[0] != {"name": "Checkout code", "uses": "actions/checkout@v6"}:
            raise GeneratorError(f"ci.yml: jobs.{job_id} checkout step drifted")
        if steps[1] != {
            "name": "Set up Python 3.14",
            "uses": "actions/setup-python@v6",
            "with": {"python-version": "3.14"},
        }:
            raise GeneratorError(f"ci.yml: jobs.{job_id} Python setup step drifted")
        if steps[2] != {
            "name": "Install Poetry",
            "uses": "snok/install-poetry@v1",
            "with": {
                "version": "latest",
                "virtualenvs-create": "true",
                "virtualenvs-in-project": "true",
            },
        }:
            raise GeneratorError(f"ci.yml: jobs.{job_id} Poetry setup step drifted")
        if steps[3] != {"name": "Install dependencies", "run": "poetry install --with dev\n"}:
            raise GeneratorError(f"ci.yml: jobs.{job_id} dependency step drifted")
        if steps[4].get("name") != spec.check_step_name or "run" not in steps[4]:
            raise GeneratorError(f"ci.yml: jobs.{job_id} check step metadata drifted")
        if steps[4].get("run") != f"make {make_target}\n":
            # This is the owned field.  It is allowed to be stale so --write
            # can project a registry change into the workflow.
            if not isinstance(steps[4].get("run"), str):
                raise GeneratorError(f"ci.yml: jobs.{job_id} check command is not a string")

    expected_needs = _expected_needs(gates)
    for consumer, expected in expected_needs.items():
        job = jobs.get(consumer)
        if not isinstance(job, dict):
            raise GeneratorError(f"ci.yml: jobs.{consumer} must be a mapping")
        actual = job.get("needs", [])
        if isinstance(actual, str):
            actual_tuple = (actual,)
        elif isinstance(actual, list) and all(isinstance(value, str) for value in actual):
            actual_tuple = tuple(actual)
        else:
            raise GeneratorError(f"ci.yml: jobs.{consumer}.needs must be a string/list of strings")
        if len(set(actual_tuple)) != len(actual_tuple):
            raise GeneratorError(f"ci.yml: jobs.{consumer}.needs contains a duplicate predecessor")
        if set(actual_tuple) - set(expected):
            raise GeneratorError(
                f"ci.yml: jobs.{consumer}.needs contains an unsupported predecessor"
            )
    return workflow


def _render_job(gate_id: str, job_id: str, make_target: str) -> str:
    spec = HOSTED_JOB_CATALOG[gate_id]
    return (
        f"  {job_id}:\n"
        f"    name: {spec.display_name}\n"
        "    runs-on: ubuntu-24.04\n"
        "\n"
        "    steps:\n"
        "    - name: Checkout code\n"
        "      uses: actions/checkout@v6\n"
        "\n"
        "    - name: Set up Python 3.14\n"
        "      uses: actions/setup-python@v6\n"
        "      with:\n"
        '        python-version: "3.14"\n'
        "\n"
        "    - name: Install Poetry\n"
        "      uses: snok/install-poetry@v1\n"
        "      with:\n"
        "        version: latest\n"
        "        virtualenvs-create: true\n"
        "        virtualenvs-in-project: true\n"
        "\n"
        "    - name: Install dependencies\n"
        "      run: |\n"
        "        poetry install --with dev\n"
        "\n"
        f"    - name: {spec.check_step_name}\n"
        "      run: |\n"
        f"        make {make_target}\n"
    )


def _render_jobs(gates: list[dict[str, Any]]) -> str:
    bindings = _registry_bindings(gates)
    return "\n\n".join(
        _render_job(gate_id, *bindings[gate_id]).rstrip("\n") for gate_id in HOSTED_GATE_ORDER
    )


def _render_needs(gates: list[dict[str, Any]], consumer: str) -> str:
    expected = _expected_needs(gates)[consumer]
    return f"    needs: [{', '.join(expected)}]"


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


def _bootstrap_job_markers(lines: list[str], gates: list[dict[str, Any]]) -> list[str]:
    headers = _top_level_job_headers(lines)
    expected_names = [HOSTED_JOB_CATALOG[gate_id].display_name for gate_id in HOSTED_GATE_ORDER]
    # Use static display metadata to find the old IDs; this permits a registry
    # Make-target edit while keeping the bootstrap independent of job text.
    starts: list[int] = []
    for expected_name in expected_names:
        found = []
        for index, job_id in headers:
            end = next((position for position, _ in headers if position > index), len(lines))
            block = "".join(lines[index:end])
            if f"    name: {expected_name}\n" in block:
                found.append(index)
        if len(found) != 1:
            raise GeneratorError(f"hosted job bootstrap: expected one job named {expected_name!r}")
        starts.append(found[0])
    headers_between = [position for position, _ in headers if starts[0] <= position <= starts[-1]]
    if starts != sorted(starts) or headers_between != starts:
        raise GeneratorError(
            "hosted job bootstrap: registry-bound jobs are not one contiguous region"
        )
    first = starts[0]
    last = starts[-1]
    next_header = next((position for position, _ in headers if position > last), len(lines))
    end = next_header
    while end > last and not lines[end - 1].strip():
        end -= 1
    generated = _render_jobs(gates).splitlines(keepends=True)
    generated = [line if line.endswith("\n") else line + "\n" for line in generated]
    return lines[:first] + [JOB_BEGIN + "\n", *generated, JOB_END + "\n"] + lines[end:]


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


def _validate_marked_regions(lines: list[str], gates: list[dict[str, Any]]) -> None:
    if not _all_markers_present(lines):
        raise GeneratorError("ci.yml: generated marker pairs are incomplete or duplicated")
    # Marker regions must be structurally owned by the exact top-level jobs they
    # name.  Line matching alone is insufficient: a marker moved into another
    # job (or into a scalar that happens to contain marker-looking text) must not
    # authorize rewriting that job's bytes.
    jobs_lines = _line_index(lines, "jobs:")
    if len(jobs_lines) != 1:
        raise GeneratorError("ci.yml: expected exactly one top-level jobs section")
    headers = _top_level_job_headers(lines)
    header_locations = {job_id: index for index, job_id in headers}
    job_begin = _line_index(lines, JOB_BEGIN)[0]
    job_end = _line_index(lines, JOB_END)[0]
    if not jobs_lines[0] < job_begin < job_end:
        raise GeneratorError("ci.yml: hosted job markers are not owned by the jobs section")
    bindings = _registry_bindings(gates)
    expected_job_ids = tuple(bindings[gate_id][0] for gate_id in HOSTED_GATE_ORDER)
    enclosed_jobs = tuple(job_id for index, job_id in headers if job_begin < index < job_end)
    if enclosed_jobs != expected_job_ids:
        raise GeneratorError(
            "ci.yml: hosted job marker region must contain exactly the named top-level jobs "
            f"in order; got {list(enclosed_jobs)!r}"
        )
    if job_begin + 1 != header_locations[expected_job_ids[0]]:
        raise GeneratorError("ci.yml: hosted job begin marker is not adjacent to its first job")
    last_job_start = header_locations[expected_job_ids[-1]]
    if job_end <= last_job_start:
        raise GeneratorError("ci.yml: hosted job end marker is inside the last generated job")
    next_job_header = next((index for index, _ in headers if index > last_job_start), len(lines))
    if any(line.strip() for line in lines[job_end + 1 : next_job_header]):
        raise GeneratorError("ci.yml: hosted job end marker is not at the job-region boundary")

    if any("GENERATED:" in line for line in lines[job_begin + 1 : job_end]):
        raise GeneratorError("ci.yml: hosted job region contains nested generated markers")
    for consumer, begin in NEEDS_BEGIN.items():
        start = _line_index(lines, begin)[0]
        end = _line_index(lines, NEEDS_END[consumer])[0]
        if consumer not in header_locations:
            raise GeneratorError(f"ci.yml: needs marker consumer job {consumer!r} is missing")
        consumer_start = header_locations[consumer]
        consumer_end = next((index for index, _ in headers if index > consumer_start), len(lines))
        if not consumer_start < start < end < consumer_end:
            raise GeneratorError(
                f"ci.yml: needs marker region for {consumer} is not owned by its top-level job"
            )
        body = [line for line in lines[start + 1 : end] if line.strip()]
        if len(body) != 1 or not body[0].lstrip().startswith("needs:"):
            raise GeneratorError(f"ci.yml: needs marker region for {consumer} is malformed")


def expected_workflow_text(text: str, gates: list[dict[str, Any]]) -> str:
    """Return the deterministic generated workflow text for a registry."""
    _validate_workflow_projection(text, gates)
    lines = text.splitlines(keepends=True)
    if _any_marker_present(lines):
        _validate_marked_regions(lines, gates)
    else:
        lines = _bootstrap_job_markers(lines, gates)
        lines = _sync_needs_markers(lines, gates)
    lines = _replace_marked_region(
        lines,
        JOB_BEGIN,
        JOB_END,
        [line + "\n" for line in _render_jobs(gates).splitlines()],
        "hosted job region",
    )
    for consumer in NEEDS_BEGIN:
        lines = _replace_marked_region(
            lines,
            NEEDS_BEGIN[consumer],
            NEEDS_END[consumer],
            [_render_needs(gates, consumer) + "\n"],
            f"needs region for {consumer}",
        )
    result = "".join(lines)
    _validate_workflow_projection(result, gates)
    return result


def _atomic_write(path: Path, content: str) -> None:
    mode = path.stat().st_mode & 0o777
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


def sync_workflow(
    path: Path = DEFAULT_WORKFLOW, registry_path: Path = DEFAULT_REGISTRY
) -> tuple[bool, str]:
    """Compute expected content and return ``(drift, expected_text)``."""
    try:
        current = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise GeneratorError(f"cannot read workflow {path}: {exc}") from None
    gates = _parse_registry(registry_path)
    expected = expected_workflow_text(current, gates)
    return current != expected, expected


def _print_drift(current: str, expected: str) -> None:
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile="ci.yml",
        tofile="ci.yml.generated",
    )
    print("".join(diff), end="")


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--write", action="store_true")
    mode.add_argument(
        "--print-check-targets",
        action="store_true",
        help="print registry-bound check-* Make targets for parse-time Make derivation",
    )
    parser.add_argument("--workflow", type=Path, default=DEFAULT_WORKFLOW)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        gates = _parse_registry(args.registry)
        if args.print_check_targets:
            print(_check_gate_targets(gates))
            return 0

        drift, expected = sync_workflow(args.workflow, args.registry)
        if not drift:
            return 0
        if args.check:
            current = args.workflow.read_text(encoding="utf-8")
            _print_drift(current, expected)
            return 1
        _atomic_write(args.workflow, expected)
        return 0
    except (GeneratorError, OSError) as exc:
        print(f"ERROR: [CI_GATE_GENERATION] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - last-resort fail-closed guard
        print(
            f"ERROR: [CI_GATE_GENERATION] {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
