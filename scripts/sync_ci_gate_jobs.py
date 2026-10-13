#!/usr/bin/env python3
"""
Synchronize registry-bound gates across workflows and the generated Make include.

The registry owns gate membership, hosted job IDs, Make targets, publish
gate membership, and each gate's generated Make recipe (``make_recipe``).
This helper owns the intentionally static GitHub Actions display and step
metadata.  Only the marked hosted-job, consumer-``needs``, E2E path, and
publish gate-step regions are generated in the workflows, plus the fully
generated ``scripts/gates.mk`` include and the gate-roster table in
``docs/technical/validation_policy.md``; all other workflow and document
text remains byte-for-byte untouched.

The catalog, shared loaders, and the E2E, publish, Make-include, docs, and
marked-region projections live in private ``_sync_ci_gate_*`` siblings
(SA267) and are re-exported here; this facade keeps the action pins, the
hosted-workflow projection they feed, and the CLI.

A registry gate with a ``make_target`` must either carry a ``make_recipe`` or
be declared in ``HAND_OWNED_MAKE_TARGETS`` (the recipe is a large inline shell
program that cannot be expressed as a registry command list); generation
fails closed otherwise, and the include's per-target comments come from the
helper-owned ``MAKE_TARGET_COMMENTS`` catalog, falling back to the registry
description.

The publish workflow's gate steps are generated from the registry's
``publish`` context membership through the helper-owned ``PublishStepSpec``
catalog; a publish-context change that is not projected by that catalog fails
closed before any byte is written.

Exit codes:
    0 - clean (``--check``) or successfully written (``--write``)
    1 - generated text differs from the checked-in file (``--check``)
    2 - malformed input or an invariant violation
"""

from __future__ import annotations

import argparse
import difflib
import os as os
import re as re
import sys
import tempfile as tempfile
from dataclasses import dataclass as dataclass
from pathlib import Path
from typing import Any

try:
    import yaml as yaml
except ImportError:  # pragma: no cover - Poetry supplies PyYAML
    yaml = None  # type: ignore[assignment]

try:
    from check_gate_parity import SchemaValidationError, _parse_json_strict, _validate_registry
except ImportError:  # pragma: no cover - direct script execution supplies scripts/ on sys.path
    SchemaValidationError = None  # type: ignore[assignment,misc]
    _parse_json_strict = None  # type: ignore[assignment]
    _validate_registry = None  # type: ignore[assignment]

from _sync_ci_gate_catalog import (
    DOCS_TABLE_BEGIN,
    DOCS_TABLE_END,
    E2E_PATHS_BEGIN,
    E2E_PATHS_END,
    EXPECTED_UNOWNED_JOB_IDS,
    FIXED_NEEDS,
    HAND_OWNED_MAKE_TARGETS,
    HOSTED_GATE_ORDER,
    HOSTED_JOB_CATALOG,
    JOB_BEGIN,
    JOB_END,
    MAKE_TARGET_COMMENTS,
    NEEDS_BEGIN,
    NEEDS_END,
    NEEDS_GATE_IDS,
    PUBLISH_BEGIN,
    PUBLISH_END,
    PUBLISH_GATE_ORDER,
    PUBLISH_STEP_CATALOG,
    UNOWNED_JOB_IDS,
    UNOWNED_JOB_RATIONALES,
    HostedJobSpec,
    PublishStepSpec,
)
from _sync_ci_gate_core import (
    DEFAULT_DOCS,
    DEFAULT_E2E_WORKFLOW,
    DEFAULT_MAKE_INCLUDE,
    DEFAULT_PUBLISH_WORKFLOW,
    DEFAULT_REGISTRY,
    DEFAULT_WORKFLOW,
    REPO_ROOT,
    GeneratorError,
    _any_marker_present,
    _atomic_write,
    _expected_needs,
    _job_steps,
    _locate_hosted_job_headers,
    _locate_hosted_jobs,
    _parse_registry,
    _parse_workflow,
    _pins_same_action,
    _registry_bindings,
    _render_needs,
    _replace_marked_region,
    _step_matches,
    _sync_needs_markers,
    _top_level_job_headers,
    _validate_unowned_job_rationales,
)
from _sync_ci_gate_docs import expected_docs_text, sync_docs_table
from _sync_ci_gate_e2e import (
    _expected_e2e_paths,
    expected_e2e_workflow_text,
    sync_e2e_workflow,
)
from _sync_ci_gate_make import (
    MAKE_INCLUDE_HEADER,
    _generated_make_targets,
    _render_make_include,
    sync_make_include,
)
from _sync_ci_gate_publish import expected_publish_workflow_text, sync_publish_workflow
from _sync_ci_gate_regions import _validate_marked_regions

#: The names the facade publishes.  Every non-underscore pre-split definition
#: stays here so a wildcard import keeps the pre-split defined surface, and
#: the underscore-prefixed re-exports are listed so the facade's lint surface
#: and the explicit re-export block agree.  Per decisions.md § Split-Facade
#: Seams a facade re-exports public names only: incidental imported bindings
#: (``os``, ``yaml``, ``Path``, ...) stay module attributes but are
#: deliberately not part of the wildcard surface.
__all__ = [
    "CHECKOUT_COMMENT",
    "CHECKOUT_REF",
    "DEFAULT_DOCS",
    "DEFAULT_E2E_WORKFLOW",
    "DEFAULT_MAKE_INCLUDE",
    "DEFAULT_PUBLISH_WORKFLOW",
    "DEFAULT_REGISTRY",
    "DEFAULT_WORKFLOW",
    "DOCS_TABLE_BEGIN",
    "DOCS_TABLE_END",
    "E2E_PATHS_BEGIN",
    "E2E_PATHS_END",
    "EXPECTED_UNOWNED_JOB_IDS",
    "FIXED_NEEDS",
    "GeneratorError",
    "HAND_OWNED_MAKE_TARGETS",
    "HOSTED_GATE_ORDER",
    "HOSTED_JOB_CATALOG",
    "HostedJobSpec",
    "INSTALL_POETRY_COMMENT",
    "INSTALL_POETRY_REF",
    "JOB_BEGIN",
    "JOB_END",
    "MAKE_INCLUDE_HEADER",
    "MAKE_TARGET_COMMENTS",
    "NEEDS_BEGIN",
    "NEEDS_END",
    "NEEDS_GATE_IDS",
    "POETRY_VERSION",
    "PUBLISH_BEGIN",
    "PUBLISH_END",
    "PUBLISH_GATE_ORDER",
    "PUBLISH_STEP_CATALOG",
    "PublishStepSpec",
    "REPO_ROOT",
    "SETUP_PYTHON_COMMENT",
    "SETUP_PYTHON_REF",
    "UNOWNED_JOB_IDS",
    "UNOWNED_JOB_RATIONALES",
    "_atomic_write",
    "_bootstrap_job_markers",
    "_expected_e2e_paths",
    "_generated_make_targets",
    "_parse_registry",
    "_parse_workflow",
    "_render_make_include",
    "expected_docs_text",
    "expected_e2e_workflow_text",
    "expected_publish_workflow_text",
    "expected_workflow_text",
    "main",
    "sync_docs_table",
    "sync_e2e_workflow",
    "sync_make_include",
    "sync_publish_workflow",
    "sync_workflow",
]

# SA202 pins every generated job's third-party action to a full commit SHA with
# the human-readable version in a trailing comment, and pins the Poetry release
# the action installs. The comments are YAML comments, so the parsed step value
# is the bare ref while the emitted text carries the version.
CHECKOUT_REF = "actions/checkout@d23441a48e516b6c34aea4fa41551a30e30af803"
CHECKOUT_COMMENT = "# v6.1.0"
SETUP_PYTHON_REF = "actions/setup-python@ece7cb06caefa5fff74198d8649806c4678c61a1"
SETUP_PYTHON_COMMENT = "# v6.3.0"
INSTALL_POETRY_REF = "snok/install-poetry@a783c322200f0519c7926aa6faa857c4e23e9263"
INSTALL_POETRY_COMMENT = "# v1.4.2"
POETRY_VERSION = "2.4.1"


def _expected_action_refs() -> tuple[str, str, str]:
    """Return the catalog's pinned action refs in their emitted order."""
    return (CHECKOUT_REF, SETUP_PYTHON_REF, INSTALL_POETRY_REF)


def _resolve_hosted_locations(
    jobs: dict[str, Any], bindings: dict[str, tuple[str, str]], *, strict: bool
) -> dict[str, str]:
    """Locate the hosted jobs exactly (strict) or by display name (pre-edit)."""
    if strict:
        return {gate_id: bindings[gate_id][0] for gate_id in HOSTED_GATE_ORDER}
    return _locate_hosted_jobs(jobs, "ci.yml", allow_missing=True)


def _validate_hosted_job_set(jobs: dict[str, Any], hosted_locations: dict[str, str]) -> None:
    expected_job_ids = UNOWNED_JOB_IDS | set(hosted_locations.values())
    actual_job_ids = frozenset(jobs)
    if actual_job_ids != expected_job_ids:
        raise GeneratorError(
            "ci.yml: unsupported hosted job set: "
            f"expected {sorted(expected_job_ids)!r}, got {sorted(actual_job_ids)!r}"
        )


def _validate_job_step_uses(steps: list[dict[str, Any]], job_id: str, *, strict: bool) -> None:
    expected_refs = _expected_action_refs()
    if strict:
        actual_uses = tuple(step.get("uses") for step in steps if "uses" in step)
        if actual_uses != expected_refs:
            raise GeneratorError(f"ci.yml: jobs.{job_id} action versions/ordering drifted")
        return
    # Pre-edit, an action pin one release behind the catalog is projected
    # by --write rather than rejected; the action identity and its pinned
    # shape must still hold, and post-generation validation requires the
    # catalog's exact refs.
    for step, expected_ref in zip(steps, expected_refs):
        if not _pins_same_action(step.get("uses"), expected_ref):
            raise GeneratorError(f"ci.yml: jobs.{job_id} action versions/ordering drifted")


def _validate_job_step_values(
    steps: list[dict[str, Any]], job_id: str, spec: HostedJobSpec, *, strict: bool
) -> None:
    expected_checkout: dict[str, Any] = {
        "name": "Checkout code",
        "uses": CHECKOUT_REF,
    }
    if spec.full_history:
        expected_checkout["with"] = {"fetch-depth": "0"}
    if not _step_matches(steps[0], expected_checkout, strict=strict):
        raise GeneratorError(f"ci.yml: jobs.{job_id} checkout step drifted")
    if not _step_matches(
        steps[1],
        {
            "name": "Set up Python 3.14",
            "uses": SETUP_PYTHON_REF,
            "with": {"python-version": "3.14"},
        },
        strict=strict,
    ):
        raise GeneratorError(f"ci.yml: jobs.{job_id} Python setup step drifted")
    if not _step_matches(
        steps[2],
        {
            "name": "Install Poetry",
            "uses": INSTALL_POETRY_REF,
            "with": {
                "version": POETRY_VERSION,
                "virtualenvs-create": "true",
                "virtualenvs-in-project": "true",
            },
        },
        strict=strict,
    ):
        raise GeneratorError(f"ci.yml: jobs.{job_id} Poetry setup step drifted")
    if steps[3] != {"name": "Install dependencies", "run": "poetry install --with dev\n"}:
        raise GeneratorError(f"ci.yml: jobs.{job_id} dependency step drifted")


def _validate_job_check_step(
    steps: list[dict[str, Any]],
    job_id: str,
    check_step_name: str,
    make_target: str,
    *,
    strict: bool,
) -> None:
    if steps[4].get("name") != check_step_name or "run" not in steps[4]:
        raise GeneratorError(f"ci.yml: jobs.{job_id} check step metadata drifted")
    if strict:
        # Owned field: post-generation it must equal the registry binding
        # exactly; pre-edit it may be stale so --write can project it.
        if steps[4].get("run") != f"make {make_target}\n":
            raise GeneratorError(f"ci.yml: jobs.{job_id} check command drifted")
    elif not isinstance(steps[4].get("run"), str):
        raise GeneratorError(f"ci.yml: jobs.{job_id} check command is not a string")


def _validate_hosted_jobs(
    jobs: dict[str, Any],
    hosted_locations: dict[str, str],
    bindings: dict[str, tuple[str, str]],
    *,
    strict: bool,
) -> None:
    for gate_id in HOSTED_GATE_ORDER:
        job_id = hosted_locations.get(gate_id)
        if job_id is None:
            if strict:
                raise GeneratorError(f"ci.yml: hosted job for {gate_id!r} is missing")
            continue
        job = jobs.get(job_id)
        if not isinstance(job, dict):
            raise GeneratorError(f"ci.yml: jobs.{job_id} must be a mapping")
        spec = HOSTED_JOB_CATALOG[gate_id]
        make_target = bindings[gate_id][1]
        if job.get("name") != spec.display_name or job.get("runs-on") != "ubuntu-24.04":
            raise GeneratorError(f"ci.yml: jobs.{job_id} static display metadata drifted")
        steps = _job_steps(job, job_id)
        if len(steps) != 5:
            raise GeneratorError(f"ci.yml: jobs.{job_id} must retain exactly five steps")
        _validate_job_step_uses(steps, job_id, strict=strict)
        _validate_job_step_values(steps, job_id, spec, strict=strict)
        _validate_job_check_step(steps, job_id, spec.check_step_name, make_target, strict=strict)


def _validate_consumer_needs(
    jobs: dict[str, Any],
    hosted_locations: dict[str, str],
    gates: list[dict[str, Any]],
    *,
    strict: bool,
) -> None:
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
        if strict:
            # Owned field: post-generation the needs must match the registry
            # bindings exactly, in order.
            if actual_tuple != expected:
                raise GeneratorError(
                    f"ci.yml: jobs.{consumer}.needs drifted: expected {list(expected)!r}, "
                    f"got {list(actual_tuple)!r}"
                )
        elif set(actual_tuple) - (set(FIXED_NEEDS) | set(hosted_locations.values())):
            # Pre-edit the generated predecessors may be stale (registry ci_job
            # rename) but must still name real workflow jobs or fixed needs.
            raise GeneratorError(
                f"ci.yml: jobs.{consumer}.needs contains an unsupported predecessor"
            )


def _validate_workflow_projection(
    text: str, gates: list[dict[str, Any]], *, strict: bool = True
) -> dict[str, Any]:
    """
    Validate the workflow shape and all registry-bound static metadata.

    ``strict=True`` (post-generation) requires the registry's exact hosted job
    IDs, ``needs`` lists, and check commands.  ``strict=False`` (pre-edit)
    locates the hosted jobs by their static catalog display names so a registry
    ``ci_job`` (F-005) or Make-target edit can be projected by ``--write``;
    static display and step metadata is validated identically in both modes
    except that a stale action pin is tolerated pre-edit, exactly like a stale
    ``needs`` list or check command, so ``--write`` can project a catalog
    refresh into the marked region.
    """
    workflow = _parse_workflow(text, "ci.yml")
    jobs = workflow.get("jobs")
    if not isinstance(jobs, dict):
        raise GeneratorError("ci.yml: jobs must be a mapping")
    _validate_unowned_job_rationales()
    bindings = _registry_bindings(gates)
    hosted_locations = _resolve_hosted_locations(jobs, bindings, strict=strict)
    _validate_hosted_job_set(jobs, hosted_locations)
    _validate_hosted_jobs(jobs, hosted_locations, bindings, strict=strict)
    _validate_consumer_needs(jobs, hosted_locations, gates, strict=strict)
    return workflow


def _render_job(gate_id: str, job_id: str, make_target: str) -> str:
    spec = HOSTED_JOB_CATALOG[gate_id]
    checkout = f"    - name: Checkout code\n      uses: {CHECKOUT_REF} {CHECKOUT_COMMENT}\n" + (
        "      with:\n        fetch-depth: 0\n" if spec.full_history else ""
    )
    return (
        f"  {job_id}:\n"
        f"    name: {spec.display_name}\n"
        "    runs-on: ubuntu-24.04\n"
        "\n"
        "    steps:\n"
        f"{checkout}"
        "\n"
        "    - name: Set up Python 3.14\n"
        f"      uses: {SETUP_PYTHON_REF} {SETUP_PYTHON_COMMENT}\n"
        "      with:\n"
        '        python-version: "3.14"\n'
        "\n"
        "    - name: Install Poetry\n"
        f"      uses: {INSTALL_POETRY_REF} {INSTALL_POETRY_COMMENT}\n"
        "      with:\n"
        f"        version: {POETRY_VERSION}\n"
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


def _bootstrap_job_markers(lines: list[str], gates: list[dict[str, Any]]) -> list[str]:
    starts = _locate_hosted_job_headers(lines, allow_missing=True)
    if not starts:
        raise GeneratorError("hosted job bootstrap: no catalog-owned jobs were found")
    first = starts[0]
    last = starts[-1]
    next_header = next(
        (position for position, _ in _top_level_job_headers(lines) if position > last), len(lines)
    )
    end = next_header
    while end > last and not lines[end - 1].strip():
        end -= 1
    generated = _render_jobs(gates).splitlines(keepends=True)
    generated = [line if line.endswith("\n") else line + "\n" for line in generated]
    return lines[:first] + [JOB_BEGIN + "\n", *generated, JOB_END + "\n"] + lines[end:]


def expected_workflow_text(text: str, gates: list[dict[str, Any]]) -> str:
    """Return the deterministic generated workflow text for a registry."""
    _validate_workflow_projection(text, gates, strict=False)
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
    _validate_workflow_projection(result, gates, strict=True)
    return result


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


def _print_drift(current: str, expected: str, label: str = "ci.yml") -> None:
    diff = difflib.unified_diff(
        current.splitlines(keepends=True),
        expected.splitlines(keepends=True),
        fromfile=label,
        tofile=f"{label}.generated",
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
    parser.add_argument(
        "--workflow",
        type=Path,
        default=None,
        help="hosted CI workflow (explicitly selecting this preserves hosted-only behavior)",
    )
    parser.add_argument("--e2e-workflow", type=Path, default=None)
    parser.add_argument(
        "--publish-workflow",
        type=Path,
        default=None,
        help="publish release workflow (the gate-step region is generated)",
    )
    parser.add_argument(
        "--make-include",
        type=Path,
        default=None,
        help="generated Makefile include (explicit selection stays include-only)",
    )
    parser.add_argument(
        "--docs",
        type=Path,
        default=None,
        help="gate-roster table in docs/technical/validation_policy.md "
        "(explicit selection stays docs-only)",
    )
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        gates = _parse_registry(args.registry)
        if args.print_check_targets:
            print(_check_gate_targets(gates))
            return 0

        selected: list[tuple[str, Path, bool, str]] = []
        explicit = False
        if args.workflow is not None:
            explicit = True
            selected.append(("ci.yml", args.workflow, *sync_workflow(args.workflow, args.registry)))
        if args.e2e_workflow is not None:
            explicit = True
            selected.append(
                ("e2e.yml", args.e2e_workflow, *sync_e2e_workflow(args.e2e_workflow, args.registry))
            )
        if args.publish_workflow is not None:
            explicit = True
            selected.append(
                (
                    "publish.yml",
                    args.publish_workflow,
                    *sync_publish_workflow(args.publish_workflow, args.registry),
                )
            )
        if args.make_include is not None:
            explicit = True
            selected.append(
                (
                    "scripts/gates.mk",
                    args.make_include,
                    *sync_make_include(args.make_include, args.registry),
                )
            )
        if args.docs is not None:
            explicit = True
            selected.append(
                (
                    "docs/technical/validation_policy.md",
                    args.docs,
                    *sync_docs_table(args.docs, args.registry),
                )
            )
        if not explicit:
            selected.append(
                ("ci.yml", DEFAULT_WORKFLOW, *sync_workflow(DEFAULT_WORKFLOW, args.registry))
            )
            selected.append(
                (
                    "e2e.yml",
                    DEFAULT_E2E_WORKFLOW,
                    *sync_e2e_workflow(DEFAULT_E2E_WORKFLOW, args.registry),
                )
            )
            selected.append(
                (
                    "publish.yml",
                    DEFAULT_PUBLISH_WORKFLOW,
                    *sync_publish_workflow(DEFAULT_PUBLISH_WORKFLOW, args.registry),
                )
            )
            selected.append(
                (
                    "scripts/gates.mk",
                    DEFAULT_MAKE_INCLUDE,
                    *sync_make_include(DEFAULT_MAKE_INCLUDE, args.registry),
                )
            )
            selected.append(
                (
                    "docs/technical/validation_policy.md",
                    DEFAULT_DOCS,
                    *sync_docs_table(DEFAULT_DOCS, args.registry),
                )
            )
        drifted = [(label, path, expected) for label, path, drift, expected in selected if drift]
        if not drifted and not args.write:
            return 0
        if args.check:
            for label, path, expected in drifted:
                try:
                    current = path.read_text(encoding="utf-8")
                except FileNotFoundError:
                    current = ""
                _print_drift(current, expected, label)
            return 1
        for _label, path, _drift, expected in selected:
            try:
                current = path.read_text(encoding="utf-8")
            except FileNotFoundError:
                current = None
            if current != expected:
                _atomic_write(path, expected)
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
