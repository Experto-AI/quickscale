"""
Focused tests for SA122a gate parity checker.

Test matrix
-----------
- Current repository state (green publish parity + no spurious diagnostics)
- Fake-gate fan-out (add a gate, verify it propagates)
- Complete schema validation (every field constraint)
- Malformed sources (bad JSON, missing files)
- Parser precision (serial/parallel/hosted/publish extraction)
- Additive boundary (new gate in registry but not in any source)
"""

from __future__ import annotations

import json
import os
import select
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest
import sync_ci_gate_jobs as sync_ci_gate_jobs_module
from check_gate_parity import (
    _CONTEXT_SOURCES,
    SchemaValidationError,
    _assert_canonical_makefile_input,
    _BashObservationReadBudget,
    _canonical_input_path,
    _communicate_bounded,
    _extract_check_ci_parallel_gates,
    _extract_check_ci_serial_gates,
    _extract_check_members,
    _extract_ci_job_names,
    _extract_ci_needs,
    _extract_e2e_trigger_paths,
    _extract_hosted_run_values,
    _extract_makefile_targets,
    _extract_publish_gates,
    _extract_publish_run_values,
    _is_subsequence,
    _kill_make_process_group,
    _live_process_group_members,
    _MakeOutputError,
    _observe_publish_run_blocks,
    _read_bash_event_log,
    _read_bash_recorder_log,
    _run_bash_observation,
    _run_make,
    _validate_registry,
)
from sync_ci_gate_jobs import (
    DEFAULT_REGISTRY,
    DEFAULT_WORKFLOW,
    JOB_BEGIN,
    JOB_END,
    NEEDS_BEGIN,
    NEEDS_END,
    GeneratorError,
    _atomic_write,
    _parse_registry,
    _parse_workflow,
    expected_workflow_text,
)

SCRIPT = Path(__file__).with_name("check_gate_parity.py")
REPO_ROOT = SCRIPT.parents[1]
CHECK_CI = REPO_ROOT / "scripts" / "check_ci_locally.sh"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_YML = REPO_ROOT / ".github" / "workflows" / "publish.yml"
E2E_YML = REPO_ROOT / ".github" / "workflows" / "e2e.yml"

# The 5 conformance gate make targets
CONFORMANCE_MAKE_TARGETS: frozenset[str] = frozenset(
    {
        "check-core-compat",
        "check-module-core-imports",
        "check-manifest-sync",
        "check-org-context-primitives",
        "check-csrf-exempt",
    }
)


def _registry_local_gate_targets() -> list[str]:
    """Return local registry targets in their declared stage order."""
    registry = json.loads(
        (REPO_ROOT / "scripts" / "gate_registry.json").read_text(encoding="utf-8")
    )
    gates = [
        (gate["bindings"]["local_ci_stage"], index, gate["bindings"]["make_target"])
        for index, gate in enumerate(registry["gates"])
        if gate["bindings"].get("make_target")
        and gate["bindings"].get("local_ci_stage") is not None
        and 3 <= gate["bindings"]["local_ci_stage"] <= 7
    ]
    return [target for _, _, target in sorted(gates)]


# All five known execution contexts
_ALL_CONTEXTS: dict[str, str] = {
    "local-serial": "serial mode",
    "local-parallel": "parallel mode",
    "hosted": "hosted CI",
    "publish": "release workflow",
    "e2e-trigger": "ordered path allowlist",
}

# Canonical registry for hermetic-schema tests
_MINIMAL_VALID_GATE: dict[str, Any] = {
    "id": "test-gate",
    "description": "A test gate",
    "required_contexts": ["local-serial"],
    "bindings": {"make_target": "test-gate", "ci_job": None, "local_ci_stage": None},
    "depends_on": [],
    "trigger_inputs": [],
}

_MINIMAL_REGISTRY: dict[str, Any] = {
    "schema_version": 1,
    "description": "Test registry",
    "contexts": dict(_ALL_CONTEXTS),
    "gates": [_MINIMAL_VALID_GATE],
}

# CLI registry inputs intentionally have to be canonical files in the
# repository.  Keep subprocess fixtures inside that boundary while arming
# every fixture directory for removal when its test finishes.
_REPO_FIXTURE_DIRS: set[Path] = set()


@pytest.fixture(autouse=True)
def _cleanup_repo_contained_fixtures() -> Any:
    """Remove repository-contained subprocess fixtures after each test."""
    yield
    for fixture_dir in tuple(_REPO_FIXTURE_DIRS):
        shutil.rmtree(fixture_dir, ignore_errors=True)
        _REPO_FIXTURE_DIRS.discard(fixture_dir)


# =========================================================================
# Helpers
# =========================================================================


def _run_checker(argv: list[str] | None = None) -> subprocess.CompletedProcess:
    """Run the checker as a subprocess."""
    cmd = [sys.executable, str(SCRIPT)]
    if argv:
        cmd.extend(argv)
    return subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=30,
    )


def _repo_fixture_file(tmp_path: Path, filename: str) -> Path:
    """Return a cleanup-armed, canonical fixture path inside the repository."""
    fixture_dir = Path(
        tempfile.mkdtemp(prefix=f".pytest-gate-parity-{tmp_path.name}-", dir=REPO_ROOT)
    )
    _REPO_FIXTURE_DIRS.add(fixture_dir)
    return fixture_dir / filename


def _make_registry_json(gates: list[dict[str, Any]], tmp_path: Path) -> Path:
    """Write a registry JSON file and return its path (includes all 5 contexts)."""
    data: dict[str, Any] = {
        "schema_version": 1,
        "description": "Test registry",
        "contexts": dict(_ALL_CONTEXTS),
        "gates": gates,
    }
    # The checker CLI deliberately rejects external paths.  ``tmp_path`` still
    # supplies pytest's unique test identity, while the actual input lives in
    # a unique, canonical directory below the trusted repository root.
    path = _repo_fixture_file(tmp_path, "test_registry.json")
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# =========================================================================
# Current repository state
# =========================================================================


class TestCurrentRepositoryState:
    """Tests that run against the real repository state."""

    def test_real_checker_exits_zero(self) -> None:
        """The real registry and all required execution contexts are green."""
        result = _run_checker()
        assert result.returncode == 0, f"Expected exit 0, got {result.returncode}: {result.stderr}"

    def test_real_checker_stdout_is_empty(self) -> None:
        """A green checker emits no JSONL diagnostics on stdout."""
        result = _run_checker()
        assert not result.stdout.strip(), f"Expected empty stdout, got: {result.stdout}"

    def test_real_checker_stderr_reports_success(self) -> None:
        """A green checker reports its success contract on stderr."""
        result = _run_checker()
        assert "All gates present in all required contexts." in result.stderr

    def test_real_checker_stderr_contains_no_error(self) -> None:
        """A green checker does not emit an ERROR diagnostic."""
        result = _run_checker()
        assert "ERROR:" not in result.stderr


# =========================================================================
# Fake-gate fan-out
# =========================================================================


class TestFakeGateFanOut:
    """Adding a gate to the registry propagates to execution contexts."""

    def test_fake_gate_with_existing_publish_target_is_not_missing(self, tmp_path: Path) -> None:
        """A publish gate bound to an existing target is present in publish.yml."""
        gates = [
            {
                "id": "fake-gate",
                "description": "Fake gate for testing",
                "required_contexts": ["publish"],
                "bindings": {
                    "make_target": "check-core-compat",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": [],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 0, f"stderr: {result.stderr}"
        assert not result.stdout.strip()

    def test_fake_gate_in_local_serial_is_not_missing(self, tmp_path: Path) -> None:
        """A gate that IS a make target in check_ci_locally.sh serial path is not reported."""
        # Use a real existing gate make target
        gates = [
            {
                "id": "check-core-compat",
                "description": "Core compat check",
                "required_contexts": ["local-serial"],
                "bindings": {
                    "make_target": "check-core-compat",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": [],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 0, f"stderr: {result.stderr}"

    def test_fake_gate_in_e2e_trigger_appears_as_diagnostic(self, tmp_path: Path) -> None:
        """Fake gate with unique trigger_input not in e2e.yml shows as missing."""
        gates = [
            {
                "id": "fake-gate",
                "description": "Fake gate for e2e-trigger testing",
                "required_contexts": ["e2e-trigger"],
                "bindings": {
                    "make_target": "fake-gate",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": ["nonexistent/path/that/does/not/exist"],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        # Gate-level missing + aggregate path missing
        e2e_diagnostics = [ln for ln in lines if json.loads(ln)["context"] == "e2e-trigger"]
        assert any(json.loads(ln)["gate_id"] == "fake-gate" for ln in e2e_diagnostics), (
            "Expected gate-level diagnostic for fake-gate in e2e-trigger"
        )

    def test_fake_gate_with_all_five_contexts_reports_everywhere(self, tmp_path: Path) -> None:
        """Fake gate requiring all 5 contexts reported missing in each (plus makefile)."""
        gates = [
            {
                "id": "five-context-gate",
                "description": "Fake gate requiring all 5 contexts",
                "required_contexts": [
                    "local-serial",
                    "local-parallel",
                    "hosted",
                    "publish",
                    "e2e-trigger",
                ],
                "bindings": {
                    "make_target": "five-context-gate",
                    "ci_job": "five-context-gate",
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": ["unique/unlisted/path"],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        # Separate gate-level from aggregate-level diagnostics
        gate_diags = [
            json.loads(ln) for ln in lines if json.loads(ln).get("gate_id") != "**aggregate**"
        ]
        contexts_found: set[str] = set()
        for record in gate_diags:
            assert record["gate_id"] == "five-context-gate"
            contexts_found.add(record["context"])
        # Now includes makefile as an additional context
        expected_contexts = {
            "local-serial",
            "local-parallel",
            "hosted",
            "publish",
            "e2e-trigger",
            "makefile",
        }
        assert contexts_found == expected_contexts, (
            f"Expected diagnostics for all 5 contexts + makefile, got: {contexts_found}"
        )

    def test_fake_gate_with_matching_e2e_trigger_input_not_missing(self, tmp_path: Path) -> None:
        """Gate with trigger_inputs found in e2e.yml is NOT missing in e2e-trigger."""
        gates = [
            {
                "id": "matching-gate",
                "description": "Gate with trigger_inputs matching e2e paths",
                "required_contexts": ["e2e-trigger"],
                "bindings": {
                    "make_target": "matching-gate",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": ["Makefile"],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        e2e_diagnostics = [ln for ln in lines if json.loads(ln)["context"] == "e2e-trigger"]
        # May still have aggregate-level diagnostics, but NOT gate-level e2e-trigger missing
        gate_level = [
            ln
            for ln in e2e_diagnostics
            if json.loads(ln).get("gate_id") == "matching-gate"
            and json.loads(ln).get("level") == "missing"
        ]
        assert not gate_level, (
            f"matching-gate should not be reported missing in e2e-trigger: {gate_level}"
        )


# =========================================================================
# e2e-trigger aggregate path comparison
# =========================================================================


# The 26 ordered paths from the real e2e.yml pull_request.paths allowlist
_E2E_PATHS: list[str] = [
    "quickscale_modules/backups/**",
    "quickscale_cli/src/quickscale_cli/commands/plan_command.py",
    "quickscale_cli/src/quickscale_cli/commands/apply_command.py",
    "quickscale_cli/src/quickscale_cli/commands/development_commands.py",
    "quickscale_cli/src/quickscale_cli/utils/docker_utils.py",
    "quickscale_cli/tests/test_apply_command_extended.py",
    "quickscale_core/src/quickscale_core/generator/**",
    "quickscale_cli/tests/test_module_lifecycle_cycle.py",
    "quickscale_cli/tests/test_e2e_development_workflow.py",
    "quickscale_cli/tests/test_react_theme_e2e.py",
    "quickscale_core/src/quickscale_core/generator/templates/Dockerfile.j2",
    "quickscale_core/src/quickscale_core/generator/templates/github/workflows/ci.yml.j2",
    "quickscale_core/tests/test_generator/test_templates.py",
    "quickscale_core/tests/test_react_theme_integration.py",
    "quickscale_core/tests/test_integration.py",
    "quickscale_core/tests/test_e2e_full_workflow.py",
    "quickscale_core/tests/test_generated_project_runtime.py",
    "quickscale_core/tests/generator/test_themes.py",
    "quickscale_core/tests/fixtures/sa90_emission_manifests.json",
    "Makefile",
    "scripts/check_ci_locally.sh",
    "scripts/_qs_jobs.sh",
    "scripts/test_e2e.sh",
    "scripts/test_e2e_parallel.py",
    ".github/workflows/ci.yml",
    ".github/workflows/e2e.yml",
]


def _e2e_gate(paths: list[str], gate_id: str = "e2e-gate") -> dict[str, Any]:
    """Build a minimal gate that requires e2e-trigger context with given trigger_inputs."""
    return {
        "id": gate_id,
        "description": f"Gate for {gate_id}",
        "required_contexts": ["e2e-trigger"],
        "bindings": {"make_target": gate_id, "ci_job": None, "local_ci_stage": None},
        "depends_on": [],
        "trigger_inputs": paths,
    }


class TestE2eTriggerAggregate:
    """Aggregate-level path comparison for e2e-trigger context."""

    def test_aggregate_missing_path_detected(self, tmp_path: Path) -> None:
        """A trigger_input path not in e2e.yml is reported as aggregate missing."""
        gates = [
            {
                "id": "gate-a",
                "description": "Gate with a path not in e2e.yml",
                "required_contexts": ["e2e-trigger"],
                "bindings": {
                    "make_target": "gate-a",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": ["scripts/check_ci_locally.sh", "some/missing/path"],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        aggregate_missing = [
            json.loads(ln)
            for ln in lines
            if json.loads(ln).get("gate_id") == "**aggregate**"
            and json.loads(ln).get("level") == "missing"
            and json.loads(ln).get("context") == "e2e-trigger"
        ]
        assert len(aggregate_missing) == 1, (
            f"Expected 1 aggregate missing diagnostic, got: {aggregate_missing}"
        )
        assert "some/missing/path" in aggregate_missing[0]["detail"]

    def test_aggregate_exact_sequence_match_produces_no_order_diagnostic(
        self, tmp_path: Path
    ) -> None:
        """Registry trigger_inputs exactly matching e2e.yml sequence produces no order error."""
        gates = [_e2e_gate(list(_E2E_PATHS))]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        order_diags = [
            json.loads(ln)
            for ln in lines
            if json.loads(ln).get("level") == "order"
            and json.loads(ln).get("context") == "e2e-trigger"
        ]
        assert not order_diags, f"Expected no order diagnostics for exact match, got: {order_diags}"
        # The custom registry still has an e2e-trigger diagnostic (exit 1), not exit 0.
        assert result.returncode == 1

    def test_aggregate_interior_swap_detected(self, tmp_path: Path) -> None:
        """Swapping two mid-sequence paths triggers an order diagnostic."""
        swapped = list(_E2E_PATHS)
        # Swap positions 5 and 6
        swapped[5], swapped[6] = swapped[6], swapped[5]
        gates = [_e2e_gate(swapped)]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        order_diags = [
            json.loads(ln)
            for ln in lines
            if json.loads(ln).get("level") == "order"
            and json.loads(ln).get("context") == "e2e-trigger"
        ]
        assert order_diags, "Expected order diagnostic for swapped paths"
        assert "interior" not in order_diags[0]["detail"].lower()

    def test_aggregate_reorder_first_path_detected(self, tmp_path: Path) -> None:
        """Moving the first path to a later position triggers an order diagnostic."""
        reordered = list(_E2E_PATHS)
        first = reordered.pop(0)
        reordered.insert(5, first)
        gates = [_e2e_gate(reordered)]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        order_diags = [
            json.loads(ln)
            for ln in lines
            if json.loads(ln).get("level") == "order"
            and json.loads(ln).get("context") == "e2e-trigger"
        ]
        assert order_diags, "Expected order diagnostic for reordered paths"

    def test_aggregate_duplicate_path_in_registry_detected_as_extra(self, tmp_path: Path) -> None:
        """A path appearing twice across two gates' trigger_inputs creates cardinality mismatch."""
        # Use two gates with the same path so aggregate has duplicate but neither
        # gate individually violates the no-duplicate trigger_inputs constraint.
        shared = ["Makefile"]
        gates = [
            _e2e_gate(list(_E2E_PATHS)),
            _e2e_gate(shared, gate_id="second-gate"),
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        # With same set but different cardinality, it should either be an order
        # or extra diagnostic due to positional mismatch
        order_or_extra = [
            json.loads(ln)
            for ln in lines
            if json.loads(ln).get("level") in ("order", "extra")
            and json.loads(ln).get("context") == "e2e-trigger"
        ]
        assert order_or_extra, "Expected order or extra diagnostic for duplicate path"

    def test_aggregate_extra_path_when_last_omitted(self, tmp_path: Path) -> None:
        """Omitting the last e2e path from trigger_inputs triggers an extra diagnostic."""
        subset = list(_E2E_PATHS[:-1])
        gates = [_e2e_gate(subset)]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        extra_diags = [
            json.loads(ln)
            for ln in lines
            if json.loads(ln).get("level") == "extra"
            and json.loads(ln).get("context") == "e2e-trigger"
            and json.loads(ln).get("gate_id") == "**aggregate**"
        ]
        assert extra_diags, (
            f"Expected aggregate extra diagnostic for omitted path, got stdout: {lines}"
        )

    def test_aggregate_extra_path_in_e2e_detected(self, tmp_path: Path) -> None:
        """A path in e2e.yml but not in any trigger_input is reported as extra."""
        # The real e2e.yml has 26 paths; use a subset that leaves some uncovered.
        # Use just one path that exists in e2e.yml.
        gates = [
            {
                "id": "gate-b",
                "description": "Gate covering only one e2e path",
                "required_contexts": ["e2e-trigger"],
                "bindings": {
                    "make_target": "gate-b",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": ["Makefile"],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        extra_diag = [
            json.loads(ln)
            for ln in lines
            if json.loads(ln).get("level") == "extra"
            and json.loads(ln).get("context") == "e2e-trigger"
        ]
        assert len(extra_diag) == 1, f"Expected 1 extra path diagnostic, got: {extra_diag}"
        # Should mention uncovered paths like quickscale_modules/backups/**
        assert "quickscale_modules" in extra_diag[0]["detail"]


# =========================================================================
# Complete schema validation
# =========================================================================


class TestRegistrySchemaValidation:
    """Every schema constraint is enforced."""

    def _check_rejected(self, registry: dict[str, Any], tmp_path: Path) -> None:
        path = _repo_fixture_file(tmp_path, "bad_registry.json")
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2, (
            f"Expected exit 2, got {result.returncode}: stderr={result.stderr}"
        )
        assert "ERROR:" in result.stderr

    def _check_accepted(self, registry: dict[str, Any], tmp_path: Path) -> None:
        path = _repo_fixture_file(tmp_path, "good_registry.json")
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode in (0, 1), (
            f"Expected exit 0/1, got {result.returncode}: stderr={result.stderr}"
        )

    def test_missing_schema_version(self, tmp_path: Path) -> None:
        data: dict[str, Any] = {
            "description": "No schema_version",
            "contexts": dict(_ALL_CONTEXTS),
            "gates": [_MINIMAL_VALID_GATE],
        }
        self._check_rejected(data, tmp_path)

    def test_schema_version_not_int(self, tmp_path: Path) -> None:
        data = dict(_MINIMAL_REGISTRY)
        data["schema_version"] = "one"
        self._check_rejected(data, tmp_path)

    def test_schema_version_wrong(self, tmp_path: Path) -> None:
        data = dict(_MINIMAL_REGISTRY)
        data["schema_version"] = 2
        self._check_rejected(data, tmp_path)

    def test_gate_id_empty_string(self, tmp_path: Path) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["id"] = ""
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        self._check_rejected(data, tmp_path)

    def test_gate_id_missing(self, tmp_path: Path) -> None:
        gate: dict[str, Any] = {
            "description": "No id",
            "required_contexts": ["local-serial"],
            "bindings": {},
            "depends_on": [],
            "trigger_inputs": [],
        }
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        self._check_rejected(data, tmp_path)

    def test_duplicate_gate_id(self, tmp_path: Path) -> None:
        gates = [
            dict(_MINIMAL_VALID_GATE),
            dict(_MINIMAL_VALID_GATE),
        ]
        gates[1]["id"] = "test-gate"  # same as first
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = gates
        self._check_rejected(data, tmp_path)

    def test_duplicate_json_keys_rejected(self, tmp_path: Path) -> None:
        """JSON duplicate-key detection rejects duplicate mapping keys."""
        content = (
            '{"schema_version": 1, "schema_version": 2, '
            '"description": "dupe keys", '
            '"contexts": {"local-serial": "desc"}, '
            '"gates": []}'
        )
        path = _repo_fixture_file(tmp_path, "dupe_keys.json")
        path.write_text(content, encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2, (
            f"Expected exit 2 for duplicate keys, got {result.returncode}"
        )
        assert "Duplicate JSON key" in result.stderr or "ERROR:" in result.stderr

    def test_duplicate_nested_json_keys_rejected(self, tmp_path: Path) -> None:
        """Nested duplicate JSON keys are also rejected."""
        content = (
            '{"schema_version": 1, "description": "nested dupe", '
            '"contexts": {"a": "x", "a": "y"}, '
            '"gates": []}'
        )
        path = _repo_fixture_file(tmp_path, "nested_dupe.json")
        path.write_text(content, encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2, (
            f"Expected exit 2 for nested duplicate keys, got {result.returncode}"
        )
        assert "Duplicate JSON key" in result.stderr or "ERROR:" in result.stderr

    def test_unknown_context(self, tmp_path: Path) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["required_contexts"] = ["unknown-context"]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        self._check_rejected(data, tmp_path)

    def test_required_contexts_not_a_list(self, tmp_path: Path) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["required_contexts"] = "local-serial"
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        self._check_rejected(data, tmp_path)

    def test_description_empty(self, tmp_path: Path) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["description"] = ""
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        self._check_rejected(data, tmp_path)

    def test_bindings_not_dict(self, tmp_path: Path) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = "not-a-dict"
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        self._check_rejected(data, tmp_path)

    def test_gates_not_a_list(self, tmp_path: Path) -> None:
        data: dict[str, Any] = {
            "schema_version": 1,
            "description": "Gates is not a list",
            "contexts": dict(_ALL_CONTEXTS),
            "gates": "not-a-list",
        }
        self._check_rejected(data, tmp_path)

    def test_minimal_valid_registry(self, tmp_path: Path) -> None:
        """A perfectly minimal valid registry is accepted."""
        self._check_accepted(_MINIMAL_REGISTRY, tmp_path)


# =========================================================================
# Malformed sources
# =========================================================================


class TestMalformedSources:
    """Error handling for unreadable or malformed inputs."""

    def test_missing_registry_file(self, tmp_path: Path) -> None:
        """Non-existent registry path produces exit 2."""
        missing = REPO_ROOT / "scripts" / f".pytest-missing-{tmp_path.name}.json"
        result = _run_checker(["--registry", str(missing)])
        assert result.returncode == 2
        assert "ERROR:" in result.stderr
        assert "FILE_NOT_FOUND" in result.stderr or "SCHEMA_ERROR" in result.stderr

    def test_invalid_registry_json(self, tmp_path: Path) -> None:
        """Malformed JSON in registry produces exit 2."""
        path = _repo_fixture_file(tmp_path, "bad.json")
        path.write_text("this is not json", encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_empty_registry(self, tmp_path: Path) -> None:
        """Empty file produces exit 2."""
        path = _repo_fixture_file(tmp_path, "empty.json")
        path.write_text("", encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2
        assert "ERROR:" in result.stderr


# =========================================================================
# Parser precision
# =========================================================================


class TestParserPrecision:
    """Extraction functions correctly identify gates in each source."""

    def test_serial_extracts_all_five_conformance_gates(self) -> None:
        """The serial path in check_ci_locally.sh has all 5 check gates."""
        targets = _extract_check_ci_serial_gates(CHECK_CI)
        expected = set(_registry_local_gate_targets())
        assert targets == expected, f"Serial extraction returned {targets}, expected {expected}"

    def test_parallel_extracts_all_five_conformance_gates(self) -> None:
        """The parallel path in check_ci_locally.sh has all 5 check gates."""
        targets = _extract_check_ci_parallel_gates(CHECK_CI)
        expected = set(_registry_local_gate_targets())
        assert targets == expected, f"Parallel extraction returned {targets}, expected {expected}"

    def test_hosted_has_all_five_conformance_jobs(self) -> None:
        """ci.yml job names include all 5 conformance gate jobs."""
        ci_jobs = _extract_ci_job_names(CI_YML)
        expected_jobs: frozenset[str] = frozenset(
            {
                "module-core-compat",
                "module-core-import-linter",
                "manifest-sync-gate",
                "org-context-primitives-gate",
                "csrf-exempt-gate",
            }
        )
        assert expected_jobs.issubset(ci_jobs), (
            f"ci.yml jobs {ci_jobs} missing some conformance jobs"
        )

    def test_publish_has_all_five_check_gates(self) -> None:
        """publish.yml contains every conformance gate make target."""
        targets = _extract_publish_gates(PUBLISH_YML)
        missing = CONFORMANCE_MAKE_TARGETS - targets
        assert not missing, f"publish.yml is missing make targets: {missing}"

    def test_serial_does_not_pick_up_parallel_gates(self) -> None:
        """Serial extraction should not pick gates that only exist in parallel."""
        serial = _extract_check_ci_serial_gates(CHECK_CI)
        parallel = _extract_check_ci_parallel_gates(CHECK_CI)
        # All 5 conformance gates are in both — verify this holds
        assert serial == parallel, (
            f"Serial and parallel extraction disagree: serial={serial}, parallel={parallel}"
        )

    def test_registry_stage_order_is_used_by_both_local_contexts(self) -> None:
        """Both local functions execute registry targets in stage order."""
        expected = _registry_local_gate_targets()
        for function_name in ("run_static_gates_serial", "run_static_gates_parallel"):
            invocations = _run_bash_observation(CHECK_CI, function_name)
            observed = [
                argument
                for invocation in invocations
                for argument in invocation
                if argument in expected
            ]
            assert observed == expected, (function_name, observed, expected)

    def test_registry_addition_appears_in_both_local_contexts(self, tmp_path: Path) -> None:
        """A temporary local registry gate is visible to serial and parallel observation."""
        registry = json.loads(
            (REPO_ROOT / "scripts" / "gate_registry.json").read_text(encoding="utf-8")
        )
        registry["gates"].append(
            {
                "id": "temporary-local-gate",
                "description": "Temporary local derivation gate",
                "required_contexts": ["local-serial", "local-parallel"],
                "bindings": {
                    "make_target": "check-temporary-local-gate",
                    "ci_job": None,
                    "local_ci_stage": 7,
                },
                "depends_on": [],
                "trigger_inputs": [],
            }
        )
        registry_path = _repo_fixture_file(tmp_path, "temporary_registry.json")
        registry_path.write_text(json.dumps(registry), encoding="utf-8")

        for function_name in ("run_static_gates_serial", "run_static_gates_parallel"):
            invocations = _run_bash_observation(
                CHECK_CI,
                function_name,
                extra_env={"GATE_REGISTRY": str(registry_path)},
            )
            observed = [
                argument
                for invocation in invocations
                for argument in invocation
                if argument == "check-temporary-local-gate"
            ]
            assert observed == ["check-temporary-local-gate"]

    def test_serial_isolation_from_parallel_content(self, tmp_path: Path) -> None:
        """Serial parser does not pick up gates only in the parallel function."""
        script = tmp_path / "fake_ci.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "run_static_gates_serial() {\n"
            "    make check-core-compat\n"
            "}\n"
            "run_static_gates_parallel() {\n"
            '    launch_static_gate foo 1 "desc" "ok" "label" make check-only-parallel\n'
            '    wait "${WORKER_PIDS[0]}"\n'
            "}\n"
        )
        serial = _extract_check_ci_serial_gates(script)
        parallel = _extract_check_ci_parallel_gates(script)
        assert "check-core-compat" in serial
        assert "check-only-parallel" not in serial
        assert "check-only-parallel" in parallel

    def test_serial_skips_echo_strings(self, tmp_path: Path) -> None:
        """Serial parser does not count make targets in echo strings."""
        script = tmp_path / "fake_ci_echo.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "run_static_gates_serial() {\n"
            '    echo "Running make check-core-compat..."\n'
            "    make check-core-compat\n"
            '    echo "make frontend-proof done"\n'
            "}\n"
        )
        gates = _extract_check_ci_serial_gates(script)
        assert gates == {"check-core-compat"}

    def test_parallel_skips_comments(self, tmp_path: Path) -> None:
        """Parallel parser does not count make targets in comments."""
        script = tmp_path / "fake_ci_comments.sh"
        script.write_text(
            "#!/usr/bin/env bash\n"
            "run_static_gates_parallel() {\n"
            '    # launch_static_gate old-gate 0 "desc" "ok" "label" make check-old-gate\n'
            '    launch_static_gate compat 1 "desc" "ok" "label" make check-core-compat\n'
            '    wait "${WORKER_PIDS[0]}"\n'
            "}\n"
        )
        gates = _extract_check_ci_parallel_gates(script)
        assert gates == {"check-core-compat"}

    def test_e2e_extracts_twenty_six_paths(self) -> None:
        """e2e.yml has exactly 26 ordered trigger paths."""
        paths = _extract_e2e_trigger_paths(E2E_YML)
        assert len(paths) == 26, f"Expected 26 paths, got {len(paths)}"

    def test_e2e_paths_order_preserved(self) -> None:
        """e2e trigger paths preserve the order from the workflow file."""
        paths = _extract_e2e_trigger_paths(E2E_YML)
        # First and last paths as order sentinels
        assert paths[0] == "quickscale_modules/backups/**"
        assert paths[-1] == ".github/workflows/e2e.yml"
        # Confirm a few mid-sequence paths in order
        backup_idx = paths.index("quickscale_modules/backups/**")
        plan_idx = paths.index("quickscale_cli/src/quickscale_cli/commands/plan_command.py")
        assert plan_idx > backup_idx, "plan_command should come after backups"

    def test_publish_extracts_job_names_via_yaml(self) -> None:
        """publish.yml job names are extracted via structural YAML parsing (BaseLoader)."""
        jobs = _extract_publish_gates(PUBLISH_YML)
        # Expected job names from publish.yml
        expected_jobs = {
            "verify",
            "test",
            "build",
            "publish-testpypi",
            "publish-pypi",
            "create-release",
        }
        for job in expected_jobs:
            assert job in jobs, f"Expected {job} in publish.yml jobs, got: {jobs}"

    def test_publish_has_all_five_check_targets(self) -> None:
        """publish.yml must contain all 5 conformance gate make targets."""
        targets = _extract_publish_gates(PUBLISH_YML)
        missing = CONFORMANCE_MAKE_TARGETS - targets
        assert not missing, f"publish.yml is missing make targets: {missing}"

    def test_publish_structural_parsing_rejects_duplicate_yaml_keys(self, tmp_path: Path) -> None:
        """Duplicate YAML keys in publish.yml structure raise exit 2."""
        from check_gate_parity import SchemaValidationError, _parse_yaml_strict

        bad_yaml = tmp_path / "bad_publish.yml"
        bad_yaml.write_text(
            "name: Publish\n"
            "on:\n"
            "  push:\n"
            "    tags: ['v*']\n"
            "jobs:\n"
            "  verify:\n"
            "    name: Verify\n"
            "    runs-on: ubuntu-latest\n"
            "  verify:\n"  # Duplicate job key
            "    name: Verify Again\n"
            "    runs-on: ubuntu-latest\n"
        )
        with pytest.raises(SchemaValidationError, match="Duplicate YAML key"):
            _parse_yaml_strict(bad_yaml.read_text(encoding="utf-8"), str(bad_yaml))

    def test_hosted_needs_and_stage_topology_match_current_source(self) -> None:
        """Hosted dependency edges are observed structurally and in order."""
        assert _extract_ci_needs(CI_YML) == {
            "backups-validation": (),
            "csrf-exempt-gate": (),
            "isolation-conformance": (
                "backups-validation",
                "module-manifest-contract",
                "manifest-sync-gate",
                "org-context-primitives-gate",
                "csrf-exempt-gate",
            ),
            "lint-cli": (
                "backups-validation",
                "module-manifest-contract",
                "manifest-sync-gate",
                "org-context-primitives-gate",
                "csrf-exempt-gate",
            ),
            "lint-frontend": (),
            "manifest-sync-gate": (),
            "module-core-compat": (),
            "module-core-import-linter": (),
            "module-manifest-contract": (),
            "org-context-primitives-gate": (),
            "test": (
                "backups-validation",
                "module-manifest-contract",
                "module-core-compat",
                "module-core-import-linter",
                "manifest-sync-gate",
                "org-context-primitives-gate",
                "csrf-exempt-gate",
            ),
        }

    def test_all_ten_bound_hosted_run_values_match_current_source(self) -> None:
        """The five bound hosted jobs expose their ten exact run values."""
        bound_jobs = {
            "module-core-compat",
            "module-core-import-linter",
            "manifest-sync-gate",
            "org-context-primitives-gate",
            "csrf-exempt-gate",
        }
        assert _extract_hosted_run_values(CI_YML, bound_jobs) == {
            "module-core-compat": ("poetry install --with dev\n", "make check-core-compat\n"),
            "module-core-import-linter": (
                "poetry install --with dev\n",
                "make check-module-core-imports\n",
            ),
            "manifest-sync-gate": ("poetry install --with dev\n", "make check-manifest-sync\n"),
            "org-context-primitives-gate": (
                "poetry install --with dev\n",
                "make check-org-context-primitives\n",
            ),
            "csrf-exempt-gate": ("poetry install --with dev\n", "make check-csrf-exempt\n"),
        }

    def test_all_twenty_one_publish_run_values_are_structural(self) -> None:
        """Every current publish run block matches the literal ordered oracle."""
        values = _extract_publish_run_values(PUBLISH_YML)
        assert values == [
            (
                "verify",
                "TAG_VERSION=${GITHUB_REF#refs/tags/}\n"
                "TAG_VERSION=${TAG_VERSION#v}\n"
                'echo "version=$TAG_VERSION" >> $GITHUB_OUTPUT\n'
                'echo "Tag version: $TAG_VERSION"\n',
            ),
            (
                "verify",
                "TAG_VERSION=${{ steps.get_version.outputs.version }}\n"
                "FILE_VERSION=$(cat VERSION | tr -d '\\r' | sed -e 's/^\\s*//' -e "
                "'s/\\s*$//')\n"
                'if [[ "$FILE_VERSION" != "$TAG_VERSION" ]]; then\n'
                '  echo "❌ Version mismatch!"\n'
                '  echo "   VERSION file: $FILE_VERSION"\n'
                '  echo "   Git tag: $TAG_VERSION"\n'
                "  exit 1\n"
                "fi\n"
                'echo "✅ VERSION verified: $FILE_VERSION"\n',
            ),
            ("verify", "./scripts/version_tool.sh check\n"),
            ("test", 'echo "STORE_PATH=$(pnpm store path --silent)" >> $GITHUB_ENV'),
            ("test", "poetry install --with dev\n"),
            ("test", "make check-core-compat\n"),
            ("test", "make check-module-core-imports\n"),
            ("test", "make check-manifest-sync\n"),
            ("test", "make check-org-context-primitives\n"),
            ("test", "make check-csrf-exempt\n"),
            ("test", "make frontend-proof\n"),
            ("test", "make smoke-install\n"),
            ("test", "make lint -- --core --cli --modules --devtools\n"),
            ("test", "make test-integration-worker-pool\n"),
            ("test", "make typecheck -- --core --cli --modules --devtools\n"),
            (
                "test",
                "sudo apt-get update -qq\n"
                "sudo apt-get install -y -qq --no-install-recommends postgresql-client\n"
                "for db in \\\n"
                "  test_quickscale_smoke \\\n"
                "  test_quickscale_analytics \\\n"
                "  test_quickscale_auth \\\n"
                "  test_quickscale_backups \\\n"
                "  test_quickscale_billing \\\n"
                "  test_quickscale_blog \\\n"
                "  test_quickscale_crm \\\n"
                "  test_quickscale_forms \\\n"
                "  test_quickscale_listings \\\n"
                "  test_quickscale_notifications \\\n"
                "  test_quickscale_orgs \\\n"
                "  test_quickscale_social \\\n"
                "  test_quickscale_storage; do\n"
                '  createdb -h localhost -U postgres "$db" 2>/dev/null || echo '
                '"Database $db already exists"\n'
                "done\n",
            ),
            (
                "test",
                "./scripts/provision_test_roles.sh\n"
                "\n"
                'ROLE="quickscale_test_role"\n'
                "\n"
                "# Grant ownership of all test databases to the restricted role so\n"
                "# Django's test runner can create test_* databases from these templates.\n"
                "for db in \\\n"
                "test_quickscale_analytics \\\n"
                "test_quickscale_auth \\\n"
                "test_quickscale_backups \\\n"
                "test_quickscale_billing \\\n"
                "test_quickscale_blog \\\n"
                "test_quickscale_crm \\\n"
                "test_quickscale_forms \\\n"
                "test_quickscale_listings \\\n"
                "test_quickscale_notifications \\\n"
                "test_quickscale_orgs \\\n"
                "test_quickscale_social \\\n"
                "test_quickscale_storage; do\n"
                'psql -h localhost -U postgres -c "ALTER DATABASE \\"$db\\" OWNER TO '
                '${ROLE};"\n'
                '  psql -h localhost -U postgres -d "$db" -c "GRANT ALL ON SCHEMA public TO '
                '${ROLE};"\n'
                "done\n"
                'echo "✓ Database ownership and schema permissions granted to ${ROLE}"\n',
            ),
            ("test", 'make test-unit SECTION="core cli"\n'),
            ("test", "./scripts/test_integration.sh\n"),
            (
                "build",
                "set -euo pipefail\n"
                "\n"
                'ROOT="$GITHUB_WORKSPACE"\n'
                'BUILD_DIR="$ROOT/dist"\n'
                'PACKAGES=("quickscale_core" "quickscale_cli" "quickscale")\n'
                "\n"
                'mkdir -p "$BUILD_DIR"\n'
                "\n"
                'for pkg in "${PACKAGES[@]}"; do\n'
                '  pkg_dir="$ROOT/$pkg"\n'
                '  pyproject="$pkg_dir/pyproject.toml"\n'
                '  backup="$pkg_dir/pyproject.toml.backup"\n'
                "  readme_copied=0\n"
                "\n"
                '  echo "Building $pkg..."\n'
                "\n"
                '  if [[ ! -f "$pyproject" ]]; then\n'
                '    echo "pyproject.toml not found for $pkg"\n'
                "    exit 1\n"
                "  fi\n"
                "\n"
                '  cp "$pyproject" "$backup"\n'
                "\n"
                '  if [[ -f "$ROOT/README.md" ]] && [[ ! -f "$pkg_dir/README.md" ]]; then\n'
                '    cp "$ROOT/README.md" "$pkg_dir/README.md"\n'
                "    readme_copied=1\n"
                "  fi\n"
                "\n"
                '  sed -i \'s|readme = "\\.\\./README\\.md"|readme = "README.md"|\' '
                '"$pyproject"\n'
                "\n"
                '  if [[ "$pkg" == "quickscale_cli" ]]; then\n'
                '    sed -i "s|quickscale-core = {path = '
                '\\"../quickscale_core\\"[^}]*}|quickscale-core = \\"^${VERSION}\\"|" '
                '"$pyproject"\n'
                "  fi\n"
                "\n"
                '  if [[ "$pkg" == "quickscale" ]]; then\n'
                '    sed -i "s|quickscale-core = {path = '
                '\\"../quickscale_core\\"[^}]*}|quickscale-core = \\"^${VERSION}\\"|" '
                '"$pyproject"\n'
                '    sed -i "s|quickscale-cli = {path = '
                '\\"../quickscale_cli\\"[^}]*}|quickscale-cli = \\"^${VERSION}\\"|" '
                '"$pyproject"\n'
                "  fi\n"
                "\n"
                '  rm -rf "$pkg_dir/dist"\n'
                '  (cd "$pkg_dir" && poetry build)\n'
                "\n"
                '  cp "$pkg_dir"/dist/* "$BUILD_DIR"/\n'
                "\n"
                '  mv "$backup" "$pyproject"\n'
                '  if [[ "$readme_copied" -eq 1 ]]; then\n'
                '    rm -f "$pkg_dir/README.md"\n'
                "  fi\n"
                "done\n"
                "\n"
                'ls -la "$BUILD_DIR"\n',
            ),
            (
                "create-release",
                "VERSION=${{ needs.verify.outputs.version }}\n"
                'CHANGELOG_LINE=$(grep -m1 -E "^- v?${VERSION}\\\\b" CHANGELOG.md || true)\n'
                "\n"
                'if [[ -n "$CHANGELOG_LINE" ]]; then\n'
                '  echo "Release v$VERSION" > release_notes.md\n'
                '  echo "" >> release_notes.md\n'
                '  echo "$CHANGELOG_LINE" >> release_notes.md\n'
                "else\n"
                '  echo "Release v$VERSION" > release_notes.md\n'
                '  echo "" >> release_notes.md\n'
                '  echo "See [CHANGELOG.md](https://github.com/Experto-AI/quickscale/'
                "blob/main/CHANGELOG.md) "
                'for details." >> release_notes.md\n'
                "fi\n"
                "\n"
                "cat release_notes.md\n",
            ),
        ]


# =========================================================================
# SA128b Bash execution
# =========================================================================


class TestSA128bBashObservation:
    """Local shell inventories come from Bash execution, not source text."""

    @staticmethod
    def _write_serial_fixture(tmp_path: Path) -> Path:
        script = tmp_path / "sa128b_serial.sh"
        script.write_text(
            "run_static_gates_serial() {\n"
            '    echo "make check-echoed"\n'
            "    while IFS= read -r _line; do :; done <<'EOF'\n"
            "make check-heredoc\n"
            "EOF\n"
            "    uncalled_gate() { make check-uncalled; }\n"
            "    false && make check-short-circuit\n"
            "    # make check-commented \\\n"
            "    # check-commented-continuation\n"
            "    if true; then\n"
            "        make check-first\n"
            "        make check-second\n"
            "    fi\n"
            "}\n",
            encoding="utf-8",
        )
        return script

    def test_serial_inert_forms_are_absent_and_reached_order_is_observed(
        self, tmp_path: Path
    ) -> None:
        """Inert forms do not count, while reached commands retain order."""
        script = self._write_serial_fixture(tmp_path)
        observed = _run_bash_observation(script, "run_static_gates_serial")
        assert observed == [("check-first",), ("check-second",)]
        assert _extract_check_ci_serial_gates(script) == {"check-first", "check-second"}

    def test_parallel_join_observes_all_workers(self, tmp_path: Path) -> None:
        """A parallel function that joins its workers reports every completed gate."""
        script = tmp_path / "sa128b_parallel.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    launch_static_gate first 1 desc ok label make check-first\n"
            "    launch_static_gate second 2 desc ok label make check-second\n"
            '    for pid in "${WORKER_PIDS[@]}"; do wait "$pid"; done\n'
            "}\n",
            encoding="utf-8",
        )
        assert _extract_check_ci_parallel_gates(script) == {"check-first", "check-second"}

    def test_parallel_worker_failure_fails_closed(self, tmp_path: Path) -> None:
        """A joined worker failure rejects the otherwise partial inventory."""
        script = tmp_path / "sa128b_parallel_failure.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    launch_static_gate failing 1 desc ok label make check-failing\n"
            "    failed=0\n"
            '    for pid in "${WORKER_PIDS[@]}"; do wait "$pid" || failed=1; done\n'
            '    return "$failed"\n'
            "}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaValidationError, match="failed|status"):
            _run_bash_observation(
                script,
                "run_static_gates_parallel",
                recorder_fail_target="check-failing",
            )

    def test_failed_recorder_command_fails_closed(self, tmp_path: Path) -> None:
        """A recorder failure cannot produce a partial inventory."""
        script = tmp_path / "sa128b_failure.sh"
        after_failure = tmp_path / "after-failure"
        script.write_text(
            "set -e\n"
            "run_static_gates_serial() {\n"
            "    make check-failing\n"
            "    make check-after-failure\n"
            f"    printf reached > {after_failure}\n"
            "}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaValidationError, match="failed|status"):
            _run_bash_observation(
                script,
                "run_static_gates_serial",
                recorder_fail_target="check-failing",
            )
        assert not after_failure.exists(), "inherited errexit allowed later work to run"

    def test_parallel_join_order_is_declaration_order(self, tmp_path: Path) -> None:
        """A completion handshake proves fast-before-slow without timing inference."""
        script = tmp_path / "sa128b_parallel_order.sh"
        fast_completed = tmp_path / "fast-completed"
        fast_completed_path = shlex.quote(str(fast_completed))
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    slow_gate() {\n"
            f"        while [ ! -f {fast_completed_path} ]; do :; done\n"
            "        make check-slow\n"
            "    }\n"
            "    fast_gate() {\n"
            "        make check-fast\n"
            f"        printf 'fast-completed\\n' > {fast_completed_path}\n"
            "    }\n"
            "    launch_static_gate slow 1 desc ok label slow_gate\n"
            "    launch_static_gate fast 2 desc ok label fast_gate\n"
            '    wait "${WORKER_PIDS[0]}"\n'
            '    wait "${WORKER_PIDS[1]}"\n'
            "}\n",
            encoding="utf-8",
        )
        assert _run_bash_observation(script, "run_static_gates_parallel") == [
            ("check-slow",),
            ("check-fast",),
        ]
        assert fast_completed.read_text(encoding="utf-8") == "fast-completed\n"

    def test_parallel_join_with_residual_descendant_fails_and_cleans_up(
        self, tmp_path: Path
    ) -> None:
        """A joined worker's delayed child cannot mutate logs after cleanup."""
        script = tmp_path / "sa128b_parallel_residual_descendant.sh"
        residual_marker = tmp_path / "residual-marker"
        residual_pid = tmp_path / "residual-pid"
        residual_pid_path = shlex.quote(str(residual_pid))
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    joined_worker() {\n"
            f"        ( printf '%s\\n' \"$BASHPID\" > {residual_pid_path}; "
            f"/bin/sleep 0.25; printf late > {residual_marker} ) &\n"
            "    }\n"
            "    launch_static_gate joined 1 desc ok label joined_worker\n"
            '    wait "${WORKER_PIDS[0]}"\n'
            "}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaValidationError, match="live descendants|process group"):
            _run_bash_observation(script, "run_static_gates_parallel")

        # The READY-equivalent PID write happens before the delayed action;
        # synchronous group cleanup is therefore asserted against an
        # authoritative captured child PID, not a sleep-only timing guess.
        assert residual_pid.exists()
        child_pid = int(residual_pid.read_text(encoding="utf-8"))
        assert not (Path("/proc") / str(child_pid)).exists()
        assert not residual_marker.exists(), "residual descendant survived cleanup"

    def test_parallel_omitted_wait_fails_closed(self, tmp_path: Path) -> None:
        """A parallel function that returns without joining is incomplete."""
        script = tmp_path / "sa128b_parallel_omitted_wait.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    launch_static_gate first 1 desc ok label make check-first\n"
            "    launch_static_gate second 2 desc ok label make check-second\n"
            "}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaValidationError, match="join|worker"):
            _run_bash_observation(script, "run_static_gates_parallel")

    def test_parallel_reverse_wait_order_fails_closed(self, tmp_path: Path) -> None:
        """A complete but reverse-order join does not satisfy ordered replay."""
        script = tmp_path / "sa128b_parallel_reverse_wait.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    launch_static_gate first 1 desc ok label make check-first\n"
            "    launch_static_gate second 2 desc ok label make check-second\n"
            '    wait "${WORKER_PIDS[1]}"\n'
            '    wait "${WORKER_PIDS[0]}"\n'
            "}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaValidationError, match="order"):
            _run_bash_observation(script, "run_static_gates_parallel")

    def test_parallel_worker_failure_cannot_be_swallowed(self, tmp_path: Path) -> None:
        """A joined worker failure is rejected even when the function returns zero."""
        script = tmp_path / "sa128b_parallel_swallowed_failure.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    launch_static_gate failing 1 desc ok label make check-failing\n"
            '    wait "${WORKER_PIDS[0]}" || true\n'
            "    return 0\n"
            "}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaValidationError, match="failed|status"):
            _run_bash_observation(
                script,
                "run_static_gates_parallel",
                recorder_fail_target="check-failing",
            )

    def test_recorder_preserves_argv_boundaries(self, tmp_path: Path) -> None:
        """A multiword gate-shaped argv element is not reparsed as a target."""
        script = tmp_path / "sa128b_argv_boundaries.sh"
        script.write_text(
            "run_static_gates_serial() {\n"
            "    make 'check-deceptive target' 'frontend proof' check-real\n"
            "}\n",
            encoding="utf-8",
        )
        assert _run_bash_observation(script, "run_static_gates_serial") == [
            ("check-deceptive target", "frontend proof", "check-real")
        ]
        assert _extract_check_ci_serial_gates(script) == {"check-real"}

    def test_recorder_rejects_multiword_gate_as_target(self, tmp_path: Path) -> None:
        """A deceptive multiword gate-shaped argument cannot create a gate."""
        script = tmp_path / "sa128b_argv_deceptive.sh"
        script.write_text(
            "run_static_gates_serial() {\n    make 'check-only deceptive'\n}\n",
            encoding="utf-8",
        )
        assert _extract_check_ci_serial_gates(script) == set()

    def test_bash_timeout_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An executing shell that never completes is bounded and rejected."""
        import check_gate_parity as parity

        monkeypatch.setattr(parity, "_BASH_TIMEOUT_SECONDS", 0.2)
        script = tmp_path / "sa128b_timeout.sh"
        script.write_text("run_static_gates_serial() { while :; do :; done; }\n", encoding="utf-8")
        with pytest.raises(SchemaValidationError, match="timeout"):
            _extract_check_ci_serial_gates(script)

    def test_serial_recorder_file_overflow_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Serial recorder argv data shares the bounded observation contract."""
        import check_gate_parity as parity

        script = tmp_path / "sa128b_serial_recorder_overflow.sh"
        script.write_text(
            "run_static_gates_serial() {\n"
            "    payload=$(printf '%*s' 4096 '')\n"
            '    make "$payload"\n'
            "}\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(parity, "_BASH_MAX_OUTPUT_BYTES", 256)
        with pytest.raises(SchemaValidationError, match=r"output bound.*cleanup"):
            _run_bash_observation(script, "run_static_gates_serial")

    def test_parallel_launch_log_overflow_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Parallel launch event data is bounded before it is parsed."""
        import check_gate_parity as parity

        script = tmp_path / "sa128b_parallel_launch_overflow.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    stage=$(printf '%*s' 4096 '')\n"
            '    launch_static_gate "$stage" 1 desc ok label make check-first\n'
            '    wait "${WORKER_PIDS[0]}"\n'
            "}\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(parity, "_BASH_MAX_OUTPUT_BYTES", 256)
        with pytest.raises(SchemaValidationError, match=r"output bound.*cleanup"):
            _run_bash_observation(script, "run_static_gates_parallel")

    def test_parallel_wait_event_overflow_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Repeated wait events cannot bypass the combined event limit."""
        import check_gate_parity as parity

        script = tmp_path / "sa128b_parallel_wait_overflow.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    launch_static_gate first 1 desc ok label make check-first\n"
            "    launch_static_gate second 2 desc ok label make check-second\n"
            "    launch_static_gate third 3 desc ok label make check-third\n"
            "    launch_static_gate fourth 4 desc ok label make check-fourth\n"
            "    launch_static_gate fifth 5 desc ok label make check-fifth\n"
            '    for pid in "${WORKER_PIDS[@]}"; do wait "$pid"; done\n'
            "}\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(parity, "_BASH_MAX_EVENTS", 4)
        with pytest.raises(SchemaValidationError, match="event count"):
            _run_bash_observation(script, "run_static_gates_parallel")

    def test_parallel_worker_recorder_overflow_fails_closed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Per-worker recorder argv data is included in the bounded contract."""
        import check_gate_parity as parity

        script = tmp_path / "sa128b_parallel_worker_overflow.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    worker() {\n"
            "        payload=$(printf '%*s' 4096 '')\n"
            '        make "$payload"\n'
            "    }\n"
            "    launch_static_gate worker 1 desc ok label worker\n"
            '    wait "${WORKER_PIDS[0]}"\n'
            "}\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(parity, "_BASH_MAX_OUTPUT_BYTES", 256)
        with pytest.raises(SchemaValidationError, match=r"output bound.*cleanup"):
            _run_bash_observation(script, "run_static_gates_parallel")

    def test_pipe_silent_file_growth_is_sampled_while_producer_is_live(
        self, tmp_path: Path
    ) -> None:
        """A silent producer cannot grow a watched file past the live byte bound."""
        watched = tmp_path / "silent-observation.log"
        command = f"while :; do printf '%*s' 1024 '' >> {shlex.quote(str(watched))}; done"
        proc = subprocess.Popen(
            ["/bin/bash", "-c", command],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            with pytest.raises(_MakeOutputError, match="output bound"):
                _communicate_bounded(
                    proc,
                    256,
                    2.0,
                    watched_file_bytes=lambda: watched.stat().st_size if watched.exists() else 0,
                )
        finally:
            _kill_make_process_group(proc, proc.pid)

    def test_shared_event_budget_fails_during_second_under_limit_log(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Two individually valid event logs share one running aggregate budget."""
        import check_gate_parity as parity

        first = tmp_path / "first.events"
        second = tmp_path / "second.events"
        first.write_text("a\t1\tx\nb\t2\ty\n", encoding="utf-8")
        second.write_text("c\t3\tz\nd\t4\tw\n", encoding="utf-8")
        monkeypatch.setattr(parity, "_BASH_MAX_EVENTS", 3)
        budget = _BashObservationReadBudget()
        assert _read_bash_event_log(first, 3, "first.events", budget) == [
            ("a", "1", "x"),
            ("b", "2", "y"),
        ]
        with pytest.raises(SchemaValidationError, match="event count"):
            _read_bash_event_log(second, 3, "second.events", budget)
        assert budget.event_count == 4

    def test_shared_frame_budget_fails_before_last_worker_file_is_consumed(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Aggregate frame overflow stops worker replay before a later file."""
        import check_gate_parity as parity

        worker_logs = [tmp_path / f"worker_{index}.argv" for index in range(3)]
        for path in worker_logs:
            path.write_bytes(b"ARGV:0\0ARGV:0\0")
        monkeypatch.setattr(parity, "_BASH_MAX_FRAMES", 3)
        budget = _BashObservationReadBudget()
        consumed: list[Path] = []
        with pytest.raises(SchemaValidationError, match="frame count"):
            for path in worker_logs:
                consumed.append(path)
                _read_bash_recorder_log(path, "worker recorder", budget)
        assert consumed == worker_logs[:2]


class TestBoundedObservationLifecycle:
    """Deterministic bounds and cleanup for both observer implementations."""

    @staticmethod
    def _ready_pipe_process() -> tuple[subprocess.Popen[bytes], int, int]:
        """Start a group whose child announces readiness while holding stdout."""
        ready_read, ready_write = os.pipe()
        proc = subprocess.Popen(
            [
                "/bin/bash",
                "-c",
                (
                    f"( printf 'READY:%s\\n' \"$BASHPID\" >&{ready_write}; "
                    "exec /bin/sleep 30 ) & exit 0"
                ),
            ],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            pass_fds=(ready_write,),
            start_new_session=True,
        )
        os.close(ready_write)
        readable, _, _ = select.select([ready_read], [], [], 2.0)
        assert readable, "child READY handshake did not arrive"
        handshake = os.read(ready_read, 128).decode("ascii")
        os.close(ready_read)
        assert handshake.startswith("READY:")
        child_pid = int(handshake.split(":", 1)[1])
        return proc, proc.pid, child_pid

    def test_ready_child_holding_observation_pipe_is_bounded_and_cleaned(self) -> None:
        """A parent exit cannot make inherited observer pipes wait forever."""
        import check_gate_parity as parity

        proc, process_group_id, child_pid = self._ready_pipe_process()
        try:
            with pytest.raises(subprocess.TimeoutExpired):
                _communicate_bounded(proc, 1024, 0.2)
            residual = _kill_make_process_group(proc, process_group_id)
            assert residual == {}, f"cleanup left process-group members: {residual}"
            assert _live_process_group_members(process_group_id) == {}
            assert not (Path("/proc") / str(child_pid)).exists()
        finally:
            # The assertion path above is authoritative; this is only a
            # defensive cleanup if a test assertion interrupts it.
            _kill_make_process_group(proc, process_group_id)
        assert parity._live_process_group_members(process_group_id) == {}

    def test_closed_observation_pipes_do_not_release_live_direct_process(self) -> None:
        """EOF on both pipes still waits for the direct observer within the deadline."""
        ready_read, ready_write = os.pipe()
        hold_read, hold_write = os.pipe()
        proc: subprocess.Popen[bytes] | None = None
        try:
            proc = subprocess.Popen(
                [
                    "/bin/bash",
                    "-c",
                    (
                        f"printf 'READY:%s\\n' \"$BASHPID\" >&{ready_write}; "
                        f"exec 1>&-; exec 2>&-; read -r _ <&{hold_read}"
                    ),
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                pass_fds=(ready_write, hold_read),
                start_new_session=True,
            )
            os.close(ready_write)
            ready_write = -1
            readable, _, _ = select.select([ready_read], [], [], 2.0)
            assert readable, "live-process READY handshake did not arrive"
            assert os.read(ready_read, 128).startswith(b"READY:")
            assert proc.poll() is None

            with pytest.raises(subprocess.TimeoutExpired):
                _communicate_bounded(proc, 1024, 0.2)
        finally:
            if proc is not None:
                residual = _kill_make_process_group(proc, proc.pid)
                assert residual == {}, f"cleanup left process-group members: {residual}"
            if ready_write >= 0:
                os.close(ready_write)
            os.close(ready_read)
            os.close(hold_write)
            os.close(hold_read)

    def test_make_closed_pipes_live_process_translates_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The Make wrapper preserves the deadline after both captured pipes close."""
        import check_gate_parity as parity

        fake_make = tmp_path / "make"
        ready_file = tmp_path / "make-ready"
        hold_fifo = tmp_path / "make-hold"
        os.mkfifo(hold_fifo)
        fake_make.write_text(
            "#!/bin/bash\n"
            'printf \'%s\\n\' "$$" > "$SA128_READY_FILE"\n'
            "exec 1>&-\n"
            "exec 2>&-\n"
            'read -r _ < "$SA128_HOLD_FIFO"\n',
            encoding="utf-8",
        )
        fake_make.chmod(0o700)
        monkeypatch.setattr(
            parity,
            "_make_observation_env",
            lambda: {
                "PATH": str(tmp_path),
                "SA128_READY_FILE": str(ready_file),
                "SA128_HOLD_FIFO": str(hold_fifo),
            },
        )
        monkeypatch.setattr(parity, "_MAKE_TIMEOUT_SECONDS", 0.2)

        with pytest.raises(SchemaValidationError, match=r"timeout.*cleanup"):
            _run_make(["-qp", "-f", str(tmp_path / "Makefile")], tmp_path, "fake make")

        assert ready_file.exists()
        make_pid = int(ready_file.read_text(encoding="utf-8"))
        assert not (Path("/proc") / str(make_pid)).exists()

    def test_bash_closed_pipes_live_process_translates_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The Bash wrapper translates the same closed-pipe deadline failure."""
        import check_gate_parity as parity

        source = tmp_path / "closed-pipes.sh"
        source.write_text("run_static_gates_serial() { :; }\n", encoding="utf-8")
        ready_file = tmp_path / "bash-ready"
        hold_fifo = tmp_path / "bash-hold"
        os.mkfifo(hold_fifo)
        monkeypatch.setattr(
            parity,
            "_shell_observation_harness",
            lambda path, function_name: (
                'printf \'%s\\n\' "$$" > "$SA128_READY_FILE"\n'
                "exec 1>&-\n"
                "exec 2>&-\n"
                'read -r _ < "$SA128_HOLD_FIFO"\n'
            ),
        )
        monkeypatch.setattr(parity, "_BASH_TIMEOUT_SECONDS", 0.2)

        with pytest.raises(SchemaValidationError, match=r"timeout.*cleanup"):
            _run_bash_observation(
                source,
                "run_static_gates_serial",
                extra_env={
                    "SA128_READY_FILE": str(ready_file),
                    "SA128_HOLD_FIFO": str(hold_fifo),
                },
                repository_source=False,
            )

        assert ready_file.exists()
        bash_pid = int(ready_file.read_text(encoding="utf-8"))
        assert not (Path("/proc") / str(bash_pid)).exists()

    def test_make_timeout_and_output_overrun_retain_cleanup_detail(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Make timeout and byte overrun both fail with the shared cleanup contract."""
        import check_gate_parity as parity

        slow_makefile = tmp_path / "slow.Makefile"
        slow_makefile.write_text("VALUE := $(shell sleep 5)\ntarget:\n\techo ok\n")
        monkeypatch.setattr(parity, "_MAKE_TIMEOUT_SECONDS", 0.2)
        with pytest.raises(SchemaValidationError, match=r"timeout.*cleanup"):
            _run_make(["-qp", "-f", str(slow_makefile)], tmp_path, str(slow_makefile))

        # Keep the output-bound assertion independent from the shorter timeout
        # used by the preceding observation.
        monkeypatch.setattr(parity, "_MAKE_TIMEOUT_SECONDS", 30.0)
        monkeypatch.setattr(parity, "_MAKE_MAX_OUTPUT_BYTES", 64)
        with pytest.raises(SchemaValidationError, match=r"output bound.*cleanup"):
            _run_make(
                ["-qp", "-r", "-R", "--no-print-directory", "-f", str(REPO_ROOT / "Makefile")],
                REPO_ROOT,
                str(REPO_ROOT / "Makefile"),
            )

    def test_bash_output_overrun_is_controlled_and_cleaned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bash output overrun is exit-2 material, not a partial inventory."""
        import check_gate_parity as parity

        script = tmp_path / "bash-output-overrun.sh"
        script.write_text(
            "run_static_gates_serial() {\n    /usr/bin/yes x | /usr/bin/head -c 4096\n}\n",
            encoding="utf-8",
        )
        monkeypatch.setattr(parity, "_BASH_MAX_OUTPUT_BYTES", 64)
        with pytest.raises(SchemaValidationError, match=r"output bound.*cleanup"):
            _run_bash_observation(script, "run_static_gates_serial")

    def test_bash_deadline_is_controlled_and_cleaned(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A non-terminating Bash observer is bounded and leaves no group."""
        import check_gate_parity as parity

        script = tmp_path / "bash-deadline.sh"
        script.write_text("run_static_gates_serial() { while :; do :; done; }\n", encoding="utf-8")
        monkeypatch.setattr(parity, "_BASH_TIMEOUT_SECONDS", 0.2)
        with pytest.raises(SchemaValidationError, match=r"timeout.*cleanup"):
            _run_bash_observation(script, "run_static_gates_serial")

    def test_cleanup_failure_does_not_replace_primary_observation_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The primary output error remains visible when cleanup leaves a residual."""
        import check_gate_parity as parity

        script = tmp_path / "bash-primary-error.sh"
        script.write_text("run_static_gates_serial() { printf '%*s' 4096 x; }\n", encoding="utf-8")
        monkeypatch.setattr(parity, "_BASH_MAX_OUTPUT_BYTES", 64)
        monkeypatch.setattr(
            parity, "_kill_make_process_group", lambda proc, group=None: {4242: "S"}
        )
        with pytest.raises(SchemaValidationError, match=r"output bound.*cleanup left"):
            _run_bash_observation(script, "run_static_gates_serial")


# =========================================================================
# Publish structural parsing and deceptive form rejection
# =========================================================================


class TestPublishStructuralParsing:
    """publish.yml structural YAML parsing with deceptive form rejection."""

    def _make_publish_yaml(self, tmp_path: Path, run_content: str) -> Path:
        """Create a minimal publish.yml with given run content."""
        yml = tmp_path / "publish.yml"
        yml.write_text(
            "name: Publish\n"
            "on:\n"
            "  push:\n"
            "    tags: ['v*']\n"
            "jobs:\n"
            "  test-job:\n"
            "    name: Test\n"
            "    runs-on: ubuntu-latest\n"
            "    steps:\n"
            "      - name: Test step\n"
            "        run: |\n" + run_content + "\n"
        )
        return yml

    def test_standalone_make_accepted(self, tmp_path: Path) -> None:
        """Canonical standalone make invocation is accepted."""
        path = self._make_publish_yaml(tmp_path, "            make frontend-proof\n")
        gates = _extract_publish_gates(path)
        assert "frontend-proof" in gates

    def test_standalone_make_with_args_accepted(self, tmp_path: Path) -> None:
        """Canonical make with arguments is accepted."""
        path = self._make_publish_yaml(tmp_path, "            make check-core-compat -- --core\n")
        gates = _extract_publish_gates(path)
        assert "check-core-compat" in gates

    def test_make_with_or_true_rejected(self, tmp_path: Path) -> None:
        """Deceptive 'make TARGET || true' raises SchemaValidationError."""
        from check_gate_parity import SchemaValidationError

        path = self._make_publish_yaml(tmp_path, "            make frontend-proof || true\n")
        with pytest.raises(SchemaValidationError, match="Deceptive|control"):
            _extract_publish_gates(path)

    def test_make_with_and_other_rejected(self, tmp_path: Path) -> None:
        """Deceptive 'make TARGET && make OTHER' raises SchemaValidationError."""
        from check_gate_parity import SchemaValidationError

        path = self._make_publish_yaml(
            tmp_path, "            make frontend-proof && make smoke-install\n"
        )
        with pytest.raises(SchemaValidationError, match="Deceptive|control"):
            _extract_publish_gates(path)

    def test_make_inside_conditional_rejected(self, tmp_path: Path) -> None:
        """Make inside if/then conditional raises SchemaValidationError."""
        from check_gate_parity import SchemaValidationError

        path = self._make_publish_yaml(
            tmp_path,
            "            if [[ -f somefile ]]; then\n"
            "              make frontend-proof\n"
            "            fi\n",
        )
        with pytest.raises(SchemaValidationError, match="Deceptive|control"):
            _extract_publish_gates(path)

    def test_make_with_redirect_accepted(self, tmp_path: Path) -> None:
        """Canonical make with redirect (2>&1) is still standalone and accepted."""
        path = self._make_publish_yaml(tmp_path, "            make frontend-proof 2>&1\n")
        gates = _extract_publish_gates(path)
        assert "frontend-proof" in gates

    def test_make_with_background_rejected(self, tmp_path: Path) -> None:
        """Deceptive 'make TARGET &' raises SchemaValidationError."""
        from check_gate_parity import SchemaValidationError

        path = self._make_publish_yaml(tmp_path, "            make frontend-proof &\n")
        with pytest.raises(SchemaValidationError, match="Deceptive|control"):
            _extract_publish_gates(path)

    def test_publish_steps_do_not_share_shell_state(self) -> None:
        """A shell mutation in one step cannot affect the next step's recorder."""
        run_values = [
            ("test", "make check-first\nPATH=/no-such-directory\n"),
            ("test", "make check-second\n"),
        ]

        assert _observe_publish_run_blocks(run_values, PUBLISH_YML) == [
            ("check-first",),
            ("check-second",),
        ]


# =========================================================================
# _is_subsequence
# =========================================================================


class TestIsSubsequence:
    """Order-preserving subsequence matching."""

    def test_exact_match(self) -> None:
        assert _is_subsequence(["a", "b"], ["a", "b"])

    def test_subsequence_in_middle(self) -> None:
        assert _is_subsequence(["b", "c"], ["a", "b", "c", "d"])

    def test_single_element_match(self) -> None:
        assert _is_subsequence(["x"], ["a", "x", "z"])

    def test_not_found(self) -> None:
        assert not _is_subsequence(["x", "y"], ["a", "b", "c"])

    def test_order_violation(self) -> None:
        assert not _is_subsequence(["b", "a"], ["a", "b"])

    def test_empty_needles(self) -> None:
        """Empty needle list always matches."""
        assert _is_subsequence([], ["a", "b"])


# =========================================================================
# Additive boundary
# =========================================================================


class TestAdditiveBoundary:
    """A new gate in the registry propagates to diagnostics."""

    def test_new_gate_without_context_reported_as_missing(self, tmp_path: Path) -> None:
        """A gate requiring a context where it does not exist is reported."""
        gate = {
            "id": "new-boundary-gate",
            "description": "New gate not yet wired anywhere",
            "required_contexts": ["local-serial"],
            "bindings": {
                "make_target": "check-gate-parity",
                "ci_job": None,
                "local_ci_stage": None,
            },
            "depends_on": [],
            "trigger_inputs": [],
        }
        reg_path = _make_registry_json([gate], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        # One for local-serial missing (check-gate-parity is not in serial extraction)
        serial_diags = [
            json.loads(ln) for ln in lines if json.loads(ln).get("context") == "local-serial"
        ]
        assert len(serial_diags) == 1, f"Expected 1 serial diagnostic, got: {lines}"
        record = serial_diags[0]
        assert record["gate_id"] == "new-boundary-gate"
        assert record["level"] == "missing"
        # One for makefile: check-gate-parity is a standalone recipe-owning
        # target that is NOT reachable from the check target, so it must not
        # satisfy the registry (F-001: global effectiveness is not check
        # aggregation).
        makefile_diags = [
            json.loads(ln) for ln in lines if json.loads(ln).get("context") == "makefile"
        ]
        assert len(makefile_diags) == 1, f"Expected 1 makefile diagnostic, got: {lines}"
        assert makefile_diags[0]["gate_id"] == "new-boundary-gate"
        assert "check-gate-parity" in makefile_diags[0]["detail"]

    def test_non_phony_make_target_detected(self, tmp_path: Path) -> None:
        """A gate with make_target not in Makefile's .PHONY is reported."""
        gate = {
            "id": "non-existent-target-gate",
            "description": "Gate with no real make target",
            "required_contexts": ["local-serial"],
            "bindings": {
                "make_target": "this-target-does-not-exist-in-makefile",
                "ci_job": None,
                "local_ci_stage": None,
            },
            "depends_on": [],
            "trigger_inputs": [],
        }
        reg_path = _make_registry_json([gate], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        makefile_diags = [
            json.loads(ln) for ln in lines if json.loads(ln).get("context") == "makefile"
        ]
        assert makefile_diags, f"Expected makefile context diagnostic, got stdout: {lines}"
        assert makefile_diags[0]["gate_id"] == "non-existent-target-gate"
        assert "this-target-does-not-exist-in-makefile" in makefile_diags[0]["detail"]

    def test_new_gate_in_existing_context_not_reported(self, tmp_path: Path) -> None:
        """A gate whose make_target exists in the context is NOT reported."""
        # check-core-compat already exists in local-serial as a make target
        gate = {
            "id": "check-core-compat",
            "description": "Core compat check",
            "required_contexts": ["local-serial"],
            "bindings": {
                "make_target": "check-core-compat",
                "ci_job": None,
                "local_ci_stage": None,
            },
            "depends_on": [],
            "trigger_inputs": [],
        }
        reg_path = _make_registry_json([gate], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr}"
        )


# =========================================================================
# Hermetic schema validation (direct function calls)
# =========================================================================


class TestSchemaValidationDirect:
    """Direct function-level schema validation (hermetic, no subprocess)."""

    def test_validate_minimal_accepts(self) -> None:
        """Minimal valid registry passes schema validation."""
        gates = _validate_registry(_MINIMAL_REGISTRY)
        assert len(gates) == 1
        assert gates[0]["id"] == "test-gate"

    def test_validate_duplicate_id_raises(self) -> None:
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [dict(_MINIMAL_VALID_GATE), dict(_MINIMAL_VALID_GATE)]
        with pytest.raises(SchemaValidationError, match="duplicate gate id"):
            _validate_registry(data)

    def test_validate_missing_id_field_raises(self) -> None:
        gate: dict[str, Any] = {}
        # Use _MINIMAL_REGISTRY as base but with empty gate
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError):
            _validate_registry(data)

    def test_validate_bindings_make_target_string_or_null(self) -> None:
        """bindings.make_target must be a string or null."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": 42}
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError):
            _validate_registry(data)

    def test_validate_unknown_top_level_key_raises(self) -> None:
        """Unknown top-level key is rejected."""
        data = dict(_MINIMAL_REGISTRY)
        data["extra_key"] = "value"
        with pytest.raises(SchemaValidationError, match="unknown top-level key"):
            _validate_registry(data)

    def test_validate_unknown_gate_key_raises(self) -> None:
        """Unknown key inside a gate object is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["invalid_field"] = "bad"
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="unknown key"):
            _validate_registry(data)

    def test_validate_missing_top_level_description_raises(self) -> None:
        """Missing top-level description is rejected."""
        data: dict[str, Any] = {
            "schema_version": 1,
            "contexts": dict(_ALL_CONTEXTS),
            "gates": [_MINIMAL_VALID_GATE],
        }
        with pytest.raises(SchemaValidationError, match="description"):
            _validate_registry(data)

    def test_validate_empty_gates_list_raises(self) -> None:
        """Empty gates list is rejected."""
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = []
        with pytest.raises(SchemaValidationError, match="non-empty"):
            _validate_registry(data)

    def test_validate_unsafe_id_raises(self) -> None:
        """Gate ID with unsafe characters is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["id"] = "bad id with spaces"
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="unsafe"):
            _validate_registry(data)

    def test_validate_duplicate_required_contexts_raises(self) -> None:
        """Duplicate context in required_contexts is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["required_contexts"] = ["local-serial", "local-serial"]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="duplicate context"):
            _validate_registry(data)

    def test_validate_empty_required_contexts_raises(self) -> None:
        """Empty required_contexts is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["required_contexts"] = []
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="non-empty"):
            _validate_registry(data)

    def test_validate_duplicate_trigger_inputs_raises(self) -> None:
        """Duplicate trigger_inputs paths are rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["trigger_inputs"] = ["path/a", "path/a"]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="duplicate path"):
            _validate_registry(data)

    def test_validate_unsafe_trigger_input_path_raises(self) -> None:
        """Trigger input path with unsafe characters is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["trigger_inputs"] = ["../path/with/traversal"]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="unsafe"):
            _validate_registry(data)

    def test_validate_string_null_ci_job_raises(self) -> None:
        """String 'null' as ci_job is rejected — must be JSON null."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": "test-gate", "ci_job": "null", "local_ci_stage": None}
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="string.*null"):
            _validate_registry(data)

    def test_validate_string_null_make_target_raises(self) -> None:
        """String 'null' as make_target is rejected — must be JSON null."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": "null", "ci_job": None, "local_ci_stage": None}
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="string.*null"):
            _validate_registry(data)

    def test_validate_missing_gate_required_keys_raises(self) -> None:
        """Gate missing required keys is rejected."""
        gate: dict[str, Any] = {"id": "partial-gate"}  # missing description, etc.
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError):
            _validate_registry(data)

    def test_validate_self_dependency_raises(self) -> None:
        """Gate depending on itself is rejected."""
        gate_a = dict(_MINIMAL_VALID_GATE)
        gate_a["id"] = "gate-a"
        gate_a["depends_on"] = ["gate-a"]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate_a]
        with pytest.raises(SchemaValidationError, match="depends on itself"):
            _validate_registry(data)

    def test_validate_unknown_dependency_raises(self) -> None:
        """Gate depending on nonexistent gate is rejected."""
        gate_a = dict(_MINIMAL_VALID_GATE)
        gate_a["id"] = "gate-a"
        gate_a["bindings"] = {"make_target": "gate-a", "ci_job": None, "local_ci_stage": None}
        gate_a["depends_on"] = ["nonexistent-gate"]
        gate_b = dict(_MINIMAL_VALID_GATE)
        gate_b["id"] = "gate-b"
        gate_b["bindings"] = {"make_target": "gate-b", "ci_job": None, "local_ci_stage": None}
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate_a, gate_b]
        with pytest.raises(SchemaValidationError, match="unknown gate"):
            _validate_registry(data)

    def test_validate_circular_dependency_raises(self) -> None:
        """Mutual dependency between two gates is rejected."""
        gate_a = dict(_MINIMAL_VALID_GATE)
        gate_a["id"] = "gate-a"
        gate_a["bindings"] = {"make_target": "gate-a", "ci_job": None, "local_ci_stage": None}
        gate_a["depends_on"] = ["gate-b"]
        gate_b = dict(_MINIMAL_VALID_GATE)
        gate_b["id"] = "gate-b"
        gate_b["bindings"] = {"make_target": "gate-b", "ci_job": None, "local_ci_stage": None}
        gate_b["depends_on"] = ["gate-a"]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate_a, gate_b]
        with pytest.raises(SchemaValidationError, match="circular"):
            _validate_registry(data)

    def test_validate_binding_collision_make_target_raises(self) -> None:
        """Two gates with same make_target is rejected."""
        gate_a = dict(_MINIMAL_VALID_GATE)
        gate_a["id"] = "gate-a"
        gate_b = dict(_MINIMAL_VALID_GATE)
        gate_b["id"] = "gate-b"
        # Both have bindings.make_target = "test-gate"
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate_a, gate_b]
        with pytest.raises(SchemaValidationError, match="already used"):
            _validate_registry(data)

    def test_validate_binding_collision_ci_job_raises(self) -> None:
        """Two gates with same ci_job is rejected."""
        gate_a = dict(_MINIMAL_VALID_GATE)
        gate_a["id"] = "gate-a"
        gate_a["bindings"] = {
            "make_target": "target-a",
            "ci_job": "shared-job",
            "local_ci_stage": None,
        }
        gate_b = dict(_MINIMAL_VALID_GATE)
        gate_b["id"] = "gate-b"
        gate_b["bindings"] = {
            "make_target": "target-b",
            "ci_job": "shared-job",
            "local_ci_stage": None,
        }
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate_a, gate_b]
        with pytest.raises(SchemaValidationError, match="already used"):
            _validate_registry(data)

    def test_validate_bindings_unknown_key_raises(self) -> None:
        """Unknown key inside bindings is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": "test-gate", "unknown_key": True}
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="unknown key"):
            _validate_registry(data)

    def test_validate_non_string_context_description_raises(self) -> None:
        """Context description that is not a non-empty string is rejected."""
        data = dict(_MINIMAL_REGISTRY)
        data["contexts"] = dict(_ALL_CONTEXTS)
        data["contexts"]["local-serial"] = ""
        with pytest.raises(SchemaValidationError, match="description"):
            _validate_registry(data)

    def test_validate_required_contexts_non_string_raises(self) -> None:
        """Non-string entry in required_contexts is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["required_contexts"] = [42]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="non-string"):
            _validate_registry(data)

    def test_validate_incomplete_contexts_raises(self) -> None:
        """Registry with incomplete contexts dict is rejected."""
        data = dict(_MINIMAL_REGISTRY)
        data["contexts"] = {"local-serial": "desc"}
        with pytest.raises(SchemaValidationError, match="incomplete contexts"):
            _validate_registry(data)

    def test_validate_non_dict_bindings_missing_keys(self) -> None:
        """Gate missing bindings entirely is rejected (missing required keys)."""
        gate: dict[str, Any] = {
            "id": "no-bindings",
            "description": "Missing bindings",
            "required_contexts": ["local-serial"],
            "depends_on": [],
            "trigger_inputs": [],
        }
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="missing"):
            _validate_registry(data)


class TestDependencyGraphValidation:
    """Dependency validation accepts arbitrary DAGs and rejects every cycle."""

    @staticmethod
    def _registry_for_dependencies(
        dependencies: dict[str, list[str]], order: list[str] | None = None
    ) -> dict[str, Any]:
        """Build a registry whose gate order and edges are fixture-owned."""
        gate_ids = order if order is not None else list(dependencies)
        gates: list[dict[str, Any]] = []
        for gate_id in gate_ids:
            gates.append(
                {
                    "id": gate_id,
                    "description": f"Dependency graph gate {gate_id}",
                    "required_contexts": ["local-serial"],
                    "bindings": {
                        "make_target": None,
                        "ci_job": None,
                        "local_ci_stage": None,
                    },
                    "depends_on": list(dependencies[gate_id]),
                    "trigger_inputs": [],
                }
            )
        registry = dict(_MINIMAL_REGISTRY)
        registry["gates"] = gates
        return registry

    def test_empty_dependency_set_is_accepted(self) -> None:
        """A graph with no dependency edges is a valid disconnected DAG."""
        registry = self._registry_for_dependencies({"gate-a": [], "gate-b": []})
        assert [gate["id"] for gate in _validate_registry(registry)] == ["gate-a", "gate-b"]

    def test_long_chain_is_accepted_without_recursion(self) -> None:
        """A chain longer than the usual recursion limit remains valid."""
        gate_ids = [f"gate-{index:04d}" for index in range(1200)]
        dependencies = {
            gate_id: ([gate_ids[index - 1]] if index else [])
            for index, gate_id in enumerate(gate_ids)
        }
        validated = _validate_registry(self._registry_for_dependencies(dependencies, gate_ids))
        assert [gate["id"] for gate in validated] == gate_ids

    def test_branching_diamond_is_accepted(self) -> None:
        """A diamond with a shared dependency is an acyclic graph."""
        dependencies = {
            "gate-root": ["gate-left", "gate-right"],
            "gate-left": ["gate-leaf"],
            "gate-right": ["gate-leaf"],
            "gate-leaf": [],
        }
        validated = _validate_registry(self._registry_for_dependencies(dependencies))
        assert {gate["id"] for gate in validated} == set(dependencies)

    def test_disconnected_acyclic_components_are_accepted(self) -> None:
        """Independent chains are validated together as one DAG."""
        dependencies = {
            "component-a-root": ["component-a-leaf"],
            "component-a-leaf": [],
            "component-b-root": ["component-b-middle"],
            "component-b-middle": ["component-b-leaf"],
            "component-b-leaf": [],
        }
        validated = _validate_registry(self._registry_for_dependencies(dependencies))
        assert len(validated) == len(dependencies)

    def test_self_cycle_preserves_named_error(self) -> None:
        """Self-dependencies retain the existing dedicated diagnostic."""
        with pytest.raises(SchemaValidationError, match="gate-a.*depends on itself"):
            _validate_registry(self._registry_for_dependencies({"gate-a": ["gate-a"]}))

    def test_two_node_cycle_is_rejected_deterministically(self) -> None:
        """A mutual dependency reports both members in stable order."""
        dependencies = {"gate-b": ["gate-a"], "gate-a": ["gate-b"]}
        with pytest.raises(
            SchemaValidationError,
            match=r"circular dependency between 'gate-a' and 'gate-b'",
        ):
            _validate_registry(self._registry_for_dependencies(dependencies))

    def test_cycle_longer_than_two_is_rejected_with_all_members(self) -> None:
        """A cycle of arbitrary length reports its complete named cycle."""
        dependencies = {
            "gate-c": ["gate-a"],
            "gate-a": ["gate-b"],
            "gate-b": ["gate-c"],
        }
        with pytest.raises(
            SchemaValidationError,
            match=r"circular dependency among gates: 'gate-a', 'gate-b', 'gate-c'",
        ):
            _validate_registry(self._registry_for_dependencies(dependencies))

    def test_cycle_in_disconnected_component_is_rejected(self) -> None:
        """A cycle is rejected even when another component is acyclic."""
        dependencies = {
            "acyclic-root": ["acyclic-leaf"],
            "acyclic-leaf": [],
            "cycle-a": ["cycle-b"],
            "cycle-b": ["cycle-c"],
            "cycle-c": ["cycle-a"],
        }
        with pytest.raises(
            SchemaValidationError,
            match=r"'cycle-a'.*'cycle-b'.*'cycle-c'",
        ):
            _validate_registry(self._registry_for_dependencies(dependencies))


# =========================================================================
# Fail-closed source parsing
# =========================================================================


class TestSourceFailClosed:
    """Source extraction fails closed on malformed inputs."""

    def test_serial_function_not_found_raises(self, tmp_path: Path) -> None:
        """Missing serial function raises SchemaValidationError."""
        script = tmp_path / "no_serial.sh"
        script.write_text("#!/usr/bin/env bash\necho 'no function'\n")
        with pytest.raises(SchemaValidationError, match="not found"):
            _extract_check_ci_serial_gates(script)

    def test_parallel_function_not_found_raises(self, tmp_path: Path) -> None:
        """Missing parallel function raises SchemaValidationError."""
        script = tmp_path / "no_parallel.sh"
        script.write_text("#!/usr/bin/env bash\necho 'no function'\n")
        with pytest.raises(SchemaValidationError, match="not found"):
            _extract_check_ci_parallel_gates(script)

    def test_duplicate_serial_function_uses_bash_definition(self, tmp_path: Path) -> None:
        """Bash semantics select the last definition of a duplicate function."""
        script = tmp_path / "dup_serial.sh"
        script.write_text(
            "run_static_gates_serial() {\n"
            "    make check-core-compat\n"
            "}\n"
            "run_static_gates_serial() {\n"
            "    make check-module-core-imports\n"
            "}\n"
        )
        assert _extract_check_ci_serial_gates(script) == {"check-module-core-imports"}

    def test_unclosed_serial_function_raises(self, tmp_path: Path) -> None:
        """Unclosed brace in serial function raises SchemaValidationError."""
        script = tmp_path / "unclosed_serial.sh"
        script.write_text(
            "run_static_gates_serial() {\n    make check-core-compat\n"
            # No closing }
        )
        with pytest.raises(SchemaValidationError, match="unclosed"):
            _extract_check_ci_serial_gates(script)

    def test_unclosed_parallel_function_raises(self, tmp_path: Path) -> None:
        """Unclosed brace in parallel function raises SchemaValidationError."""
        script = tmp_path / "unclosed_parallel.sh"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    launch_static_gate test 1 desc label label make check-core-compat\n"
        )
        with pytest.raises(SchemaValidationError, match="unclosed"):
            _extract_check_ci_parallel_gates(script)

    def test_empty_function_body_is_valid_absent(self, tmp_path: Path) -> None:
        """Empty serial function body returns empty set (valid absent)."""
        script = tmp_path / "empty_serial.sh"
        script.write_text("run_static_gates_serial() {\n    true\n}\n")
        gates = _extract_check_ci_serial_gates(script)
        assert gates == set()

    def test_indented_function_header_is_executed_by_bash(self, tmp_path: Path) -> None:
        """Bash, rather than a column-sensitive parser, recognizes the function."""
        script = tmp_path / "indented_header.sh"
        script.write_text(
            " run_static_gates_serial() {\n"  # Leading space
            "    make check-core-compat\n"
            "}\n"
        )
        assert _extract_check_ci_serial_gates(script) == {"check-core-compat"}

    def test_indented_function_close_is_executed_by_bash(self, tmp_path: Path) -> None:
        """Bash accepts an indented function close as valid shell syntax."""
        script = tmp_path / "indented_close.sh"
        script.write_text(
            "run_static_gates_serial() {\n"
            "    make check-core-compat\n"
            " }\n"  # Leading space before }
        )
        assert _extract_check_ci_serial_gates(script) == {"check-core-compat"}

    def test_echo_and_comments_not_counted(self, tmp_path: Path) -> None:
        """Echo and comments in serial function are not counted as gates."""
        script = tmp_path / "echo_comments.sh"
        script.write_text(
            "run_static_gates_serial() {\n"
            '    echo "Running make check-core-compat..."\n'
            "    # make check-module-core-imports\n"
            "    make check-core-compat\n"
            "}\n"
        )
        gates = _extract_check_ci_serial_gates(script)
        assert gates == {"check-core-compat"}


# =========================================================================
# e2e trigger ownership collision
# =========================================================================


class TestE2eOwnershipCollision:
    """e2e-trigger ownership collision detection."""

    def test_overlapping_e2e_paths_detected(self, tmp_path: Path) -> None:
        """Two gates with overlapping e2e trigger_inputs produce ownership diagnostic."""
        gates = [
            {
                "id": "gate-a",
                "description": "Gate A",
                "required_contexts": ["e2e-trigger"],
                "bindings": {"make_target": "gate-a", "ci_job": None, "local_ci_stage": None},
                "depends_on": [],
                "trigger_inputs": ["Makefile", "scripts/check_ci_locally.sh"],
            },
            {
                "id": "gate-b",
                "description": "Gate B",
                "required_contexts": ["e2e-trigger"],
                "bindings": {"make_target": "gate-b", "ci_job": None, "local_ci_stage": None},
                "depends_on": [],
                "trigger_inputs": ["Makefile", "scripts/test_e2e.sh"],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        ownership_diags = [
            json.loads(ln) for ln in lines if json.loads(ln).get("gate_id") == "**ownership**"
        ]
        assert ownership_diags, "Expected ownership collision diagnostic"
        assert "gate-a" in ownership_diags[0]["detail"]
        assert "gate-b" in ownership_diags[0]["detail"]

    def test_non_overlapping_e2e_paths_no_collision(self, tmp_path: Path) -> None:
        """Two gates with disjoint e2e trigger_inputs produce no ownership diagnostic."""
        gates = [
            {
                "id": "gate-a",
                "description": "Gate A",
                "required_contexts": ["e2e-trigger"],
                "bindings": {"make_target": "gate-a", "ci_job": None, "local_ci_stage": None},
                "depends_on": [],
                "trigger_inputs": ["Makefile"],
            },
            {
                "id": "gate-b",
                "description": "Gate B",
                "required_contexts": ["e2e-trigger"],
                "bindings": {"make_target": "gate-b", "ci_job": None, "local_ci_stage": None},
                "depends_on": [],
                "trigger_inputs": ["nonexistent/path"],
            },
        ]
        reg_path = _make_registry_json(gates, tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        ownership_diags = [
            json.loads(ln) for ln in lines if json.loads(ln).get("gate_id") == "**ownership**"
        ]
        assert not ownership_diags, f"Expected no ownership collision, got: {ownership_diags}"


# =========================================================================
# Stream behavior
# =========================================================================


class TestStreamBehavior:
    """Direct CLI stream behavior for exit 0/1/2."""

    def test_exit_zero_has_clean_streams(self, tmp_path: Path) -> None:
        """Exit 0: stdout empty (JSONL), stderr has success message, no ERROR."""
        # A gate that IS present in local-serial context achieves perfect parity
        gate = {
            "id": "check-core-compat",
            "description": "Core compat check",
            "required_contexts": ["local-serial"],
            "bindings": {
                "make_target": "check-core-compat",
                "ci_job": None,
                "local_ci_stage": None,
            },
            "depends_on": [],
            "trigger_inputs": [],
        }
        reg_path = _make_registry_json([gate], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr}"
        )
        # stdout empty (no JSONL)
        assert not result.stdout.strip(), f"Expected empty stdout, got: {result.stdout}"
        # stderr has success message, no ERROR
        assert "All gates present" in result.stderr
        assert "ERROR:" not in result.stderr

    def test_exit_one_has_jsonl_on_stdout(self, tmp_path: Path) -> None:
        """Exit 1: JSONL on stdout, no ERROR on stderr."""
        gate = {
            "id": "fake-gate",
            "description": "Fake gate not wired",
            "required_contexts": ["publish"],
            "bindings": {"make_target": "fake-gate", "ci_job": None, "local_ci_stage": None},
            "depends_on": [],
            "trigger_inputs": [],
        }
        reg_path = _make_registry_json([gate], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        assert result.stdout.strip(), "Expected JSONL on stdout"
        for line in result.stdout.splitlines():
            if line.strip():
                parsed = json.loads(line)
                assert "level" in parsed
                assert "context" in parsed
                assert "gate_id" in parsed
        assert "ERROR:" not in result.stderr

    def test_exit_two_has_error_on_stderr(self, tmp_path: Path) -> None:
        """Exit 2: ERROR on stderr, stdout empty."""
        path = _repo_fixture_file(tmp_path, "bad.json")
        path.write_text("not valid json", encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2
        assert "ERROR:" in result.stderr
        assert not result.stdout.strip()

    def test_exit_two_empty_stdout_one_error_no_traceback(self, tmp_path: Path) -> None:
        """Exit 2: empty stdout, exactly one ERROR line on stderr, no traceback."""
        path = _repo_fixture_file(tmp_path, "bad.json")
        path.write_text("this is not json", encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2
        assert not result.stdout.strip(), "Expected empty stdout on exit 2"
        error_lines = [line for line in result.stderr.splitlines() if line.startswith("ERROR:")]
        assert len(error_lines) == 1, (
            f"Expected exactly one ERROR line, got {len(error_lines)}: {result.stderr}"
        )
        assert "Traceback" not in result.stderr

    def test_make_wrapper_passes_real_registry(self) -> None:
        """Make check-gate-parity reports the green real-registry result."""
        result = subprocess.run(
            ["make", "check-gate-parity"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"Expected exit 0 from make, got {result.returncode}: stderr={result.stderr}"
        )
        assert "All gates present in all required contexts." in result.stdout
        assert "ERROR:" not in result.stdout
        assert "ERROR:" not in result.stderr


# =========================================================================
# Makefile target+recipe parsing
# =========================================================================


class TestMakefileTargetParsing:
    """Makefile target extraction verifies actual recipe existence."""

    def test_known_make_targets_present(self) -> None:
        """Known gate make targets are present in the real Makefile."""
        makefile = REPO_ROOT / "Makefile"
        targets = _extract_makefile_targets(makefile)
        for target in (
            "check-core-compat",
            "check-csrf-exempt",
            "check-gate-parity",
            "check-manifest-sync",
            "check-module-core-imports",
            "check-org-context-primitives",
        ):
            assert target in targets, f"Expected {target} in Makefile targets, got: {targets}"

    def test_nonexistent_target_not_present(self) -> None:
        """A target not defined in Makefile is not extracted."""
        makefile = REPO_ROOT / "Makefile"
        targets = _extract_makefile_targets(makefile)
        assert "this-target-does-not-exist-in-makefile" not in targets


# =========================================================================
# YAML structural parsing
# =========================================================================


class TestYamlStructuralParsing:
    """ci.yml structural parsing with duplicate-key rejection."""

    def test_ci_job_names_extracted(self) -> None:
        """ci.yml job names are extracted via structural YAML parsing."""
        jobs = _extract_ci_job_names(CI_YML)
        # Should include the five conformance gate job names
        for job in (
            "module-core-compat",
            "module-core-import-linter",
            "manifest-sync-gate",
            "org-context-primitives-gate",
            "csrf-exempt-gate",
        ):
            assert job in jobs, f"Expected {job} in ci.yml jobs, got: {jobs}"

    def test_on_not_confused_with_job(self) -> None:
        """The 'on' key in GHA workflow is not treated as a job name."""
        jobs = _extract_ci_job_names(CI_YML)
        assert "on" not in jobs, "'on' key should not be treated as a job name"

    def test_meta_keys_not_treated_as_jobs(self) -> None:
        """Metadata keys like 'name', 'env' are not misidentified as jobs."""
        jobs = _extract_ci_job_names(CI_YML)
        for meta in ("name", "env", "defaults", "concurrency", "permissions"):
            assert meta not in jobs, f"Metadata key {meta!r} should not be a job"


# =========================================================================
# Real Makefile target and recipe validation
# =========================================================================


class TestMakefileRecipeValidation:
    """Actual Makefile target recipe verification."""

    def test_check_gate_parity_recipe_exists(self) -> None:
        """check-gate-parity target has an actual recipe."""
        makefile = REPO_ROOT / "Makefile"
        targets = _extract_makefile_targets(makefile)
        assert "check-gate-parity" in targets

    def test_phony_only_target_not_counted_without_recipe(self, tmp_path: Path) -> None:
        """.PHONY declarations are NOT evidence — targets without recipes are excluded."""
        makefile = tmp_path / "Makefile"
        makefile.write_text(".PHONY: no-recipe-target\nreal-target:\n\techo hello\n")
        targets = _extract_makefile_targets(makefile)
        assert "real-target" in targets
        # .PHONY-only targets without a recipe should NOT be counted
        assert "no-recipe-target" not in targets


# =========================================================================
# SA128a — GNU Make semantic observation
# =========================================================================


class TestMakefileSemanticObservation:
    """make -qp database + --dry-run delegation proof (SA128a)."""

    def test_variable_composed_target_resolved(self, tmp_path: Path) -> None:
        """Variable-composed target names are resolved by GNU make itself."""
        makefile = tmp_path / "Makefile"
        makefile.write_text("SUFFIX := core-compat\ncheck-$(SUFFIX):\n\t@echo gate\n")
        targets = _extract_makefile_targets(makefile)
        assert "check-core-compat" in targets

    def test_variable_composed_prerequisite_resolved(self, tmp_path: Path) -> None:
        """A delegation prereq written as $(VAR) resolves to the concrete target."""
        makefile = tmp_path / "Makefile"
        makefile.write_text(
            "SUFFIX := core-compat\ncheck-$(SUFFIX):\n\t@echo gate\ndelegate: check-$(SUFFIX)\n"
        )
        targets = _extract_makefile_targets(makefile)
        assert "check-core-compat" in targets
        assert "delegate" in targets

    def test_delegated_target_present(self, tmp_path: Path) -> None:
        """A command-less target that delegates to a check target is present."""
        makefile = tmp_path / "Makefile"
        makefile.write_text("delegate: check-core-compat\ncheck-core-compat:\n\t@echo gate\n")
        targets = _extract_makefile_targets(makefile)
        assert "delegate" in targets

    def test_check_aggregation_target_present(self, tmp_path: Path) -> None:
        """A check-only aggregation target (no recipe of its own) is present."""
        makefile = tmp_path / "Makefile"
        makefile.write_text("all: check-a check-b\ncheck-a:\n\t@echo A\ncheck-b:\n\techo B\n")
        targets = _extract_makefile_targets(makefile)
        assert "all" in targets

    def test_recipe_owner_present_alongside_delegation(self, tmp_path: Path) -> None:
        """Recipe owners stay present next to delegation targets."""
        makefile = tmp_path / "Makefile"
        makefile.write_text("gate:\n\t@echo gate\naggregate: gate\n")
        targets = _extract_makefile_targets(makefile)
        assert "gate" in targets
        assert "aggregate" in targets

    def test_delegation_to_phony_only_target_absent(self, tmp_path: Path) -> None:
        """Delegation to a .PHONY-only target without a rule runs nothing."""
        makefile = tmp_path / "Makefile"
        makefile.write_text(".PHONY: ghost\ndelegate-ghost: ghost\n")
        targets = _extract_makefile_targets(makefile)
        assert "delegate-ghost" not in targets
        assert "ghost" not in targets

    def test_recursive_make_delegation_never_dry_run(self, tmp_path: Path) -> None:
        """
        Delegation through a $(MAKE) recipe is effective and never dry-run.

        GNU make executes $(MAKE) recipe lines even under --dry-run, so the
        observer must classify such targets from the database alone.  A real
        side effect would appear if the target were dry-run, proving the
        deterministic-observation bound holds.
        """
        makefile = tmp_path / "Makefile"
        marker = tmp_path / "marker.txt"
        makefile.write_text(
            "delegate: recursive\n"
            "recursive:\n"
            "\t$(MAKE) touch-side-effect\n"
            "touch-side-effect:\n"
            f"\ttouch {marker}\n"
        )
        targets = _extract_makefile_targets(makefile)
        assert "delegate" in targets
        assert "recursive" in targets
        assert not marker.exists(), "dry-run executed a $(MAKE) recipe line for real"

    def test_malformed_makefile_raises(self, tmp_path: Path) -> None:
        """A Makefile GNU make cannot parse fails hard (exit-2 contract)."""
        makefile = tmp_path / "Makefile"
        makefile.write_text("VALUE := $(UNTERMINATED\n")
        with pytest.raises(SchemaValidationError, match="unterminated"):
            _extract_makefile_targets(makefile)

    def test_missing_separator_raises(self, tmp_path: Path) -> None:
        """A tab-indented line before any target fails hard."""
        makefile = tmp_path / "Makefile"
        makefile.write_text("\techo stray\n")
        with pytest.raises(SchemaValidationError, match="missing separator|commences before"):
            _extract_makefile_targets(makefile)

    def test_missing_makefile_raises(self, tmp_path: Path) -> None:
        """A nonexistent Makefile path fails hard."""
        missing = tmp_path / "nope" / "Makefile"
        with pytest.raises(SchemaValidationError, match="not found"):
            _extract_makefile_targets(missing)

    def test_timeout_fails_hard(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A make observation that exceeds the timeout bound fails hard."""
        import check_gate_parity as parity

        monkeypatch.setattr(parity, "_MAKE_TIMEOUT_SECONDS", 0.5)
        makefile = tmp_path / "Makefile"
        makefile.write_text("SLOW := $(shell sleep 5)\ntarget:\n\techo ok\n")
        with pytest.raises(SchemaValidationError, match="timeout"):
            _extract_makefile_targets(makefile)

    def test_output_overrun_fails_hard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A make observation that exceeds the output bound fails hard."""
        import check_gate_parity as parity

        # The real Makefile database is tens of KB; a tiny bound must trip.
        monkeypatch.setattr(parity, "_MAKE_MAX_OUTPUT_BYTES", 64)
        with pytest.raises(SchemaValidationError, match="output bound"):
            _extract_makefile_targets(REPO_ROOT / "Makefile")


class TestCanonicalMakefileInput:
    """Canonical in-repo Makefile security checks (SA128a)."""

    def test_real_makefile_accepted(self) -> None:
        """The repository Makefile passes the canonical input check."""
        _assert_canonical_makefile_input(REPO_ROOT / "Makefile")  # no exception

    def test_symlink_rejected(self, tmp_path: Path) -> None:
        """A symlinked Makefile is a security-boundary violation."""
        target = tmp_path / "real_makefile.txt"
        target.write_text("target:\n\techo hi\n", encoding="utf-8")
        link = tmp_path / "Makefile"
        link.symlink_to(target)
        with pytest.raises(SchemaValidationError, match="symlink"):
            _assert_canonical_makefile_input(link)

    def test_missing_rejected(self, tmp_path: Path) -> None:
        """A missing canonical Makefile raises FileNotFoundError (FILE_NOT_FOUND)."""
        missing = REPO_ROOT / "scripts" / f".pytest-missing-{tmp_path.name}-Makefile"
        with pytest.raises(FileNotFoundError):
            _assert_canonical_makefile_input(missing)


class TestCanonicalPathBoundary:
    """Every accepted source is a canonical regular file in the repository."""

    def test_real_registry_and_all_context_sources_are_accepted(self) -> None:
        registry = REPO_ROOT / "scripts" / "gate_registry.json"
        assert _canonical_input_path(registry, "registry") == registry
        for source in _CONTEXT_SOURCES.values():
            assert _canonical_input_path(source, "context source") == source

    def test_relative_and_absolute_registry_spellings_are_accepted(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.chdir(REPO_ROOT)
        relative = Path("scripts/gate_registry.json")
        absolute = REPO_ROOT / relative
        assert _canonical_input_path(relative, "registry") == absolute
        assert _canonical_input_path(absolute, "registry") == absolute

    def test_dot_dot_alias_is_rejected(self) -> None:
        alias = REPO_ROOT / "scripts" / ".." / "scripts" / "gate_registry.json"
        with pytest.raises(SchemaValidationError, match="canonical path"):
            _canonical_input_path(alias, "registry")

    def test_final_and_ancestor_symlinks_are_rejected(self, tmp_path: Path) -> None:
        real = REPO_ROOT / "scripts" / "gate_registry.json"
        final_link = tmp_path / "registry.json"
        final_link.symlink_to(real)
        with pytest.raises(SchemaValidationError, match="symlink"):
            _canonical_input_path(final_link, "registry")

        linked_parent = tmp_path / "scripts"
        linked_parent.symlink_to(real.parent, target_is_directory=True)
        with pytest.raises(SchemaValidationError, match="symlink"):
            _canonical_input_path(linked_parent / real.name, "registry")

    def test_outside_missing_and_non_file_inputs_fail_closed(self, tmp_path: Path) -> None:
        with pytest.raises(SchemaValidationError, match="inside the repository"):
            _canonical_input_path(tmp_path / "registry.json", "registry")
        with pytest.raises(FileNotFoundError):
            _canonical_input_path(REPO_ROOT / "scripts" / "does-not-exist.json", "registry")
        with pytest.raises(SchemaValidationError, match="regular file"):
            _canonical_input_path(REPO_ROOT / "scripts", "registry")

    def test_make_reported_outside_include_is_rejected(self) -> None:
        from check_gate_parity import _validate_make_consumed_sources

        output = b"Reading makefile '/outside/gates.mk' (search path)...\n"
        with pytest.raises(SchemaValidationError, match="inside the repository"):
            _validate_make_consumed_sources(output, REPO_ROOT / "Makefile")

    def test_outside_registry_cli_has_controlled_exit_two(self, tmp_path: Path) -> None:
        outside = tmp_path / "registry.json"
        outside.write_text("{}", encoding="utf-8")
        result = _run_checker(["--registry", str(outside)])
        assert result.returncode == 2
        assert not result.stdout
        assert [line for line in result.stderr.splitlines() if line.startswith("ERROR:")] == [
            result.stderr.strip()
        ]

    def test_hostile_cwd_keeps_fixed_sources_and_stream_contract(self, tmp_path: Path) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT)],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0
        assert not result.stdout.strip()
        assert "All gates present in all required contexts." in result.stderr
        assert "ERROR:" not in result.stderr


# =========================================================================
# SA128a F-001/F-002 — check aggregation membership (real check target)
# =========================================================================


def _write_make_fixture(
    tmp_path: Path,
    makefile: str,
    extra: dict[str, str] | None = None,
) -> Path:
    """Write a Makefile fixture (plus optional include fragments) and return its path."""
    path = tmp_path / "Makefile"
    path.write_text(makefile, encoding="utf-8")
    for name, content in (extra or {}).items():
        (tmp_path / name).write_text(content, encoding="utf-8")
    return path


class TestCheckAggregationMembership:
    """Effective membership is derived through the real check target (F-001)."""

    def test_prereq_delegated_check_member_present(self, tmp_path: Path) -> None:
        """A gate aggregated as a check prerequisite is a member."""
        path = _write_make_fixture(tmp_path, "check: check-a\ncheck-a:\n\t@echo A\n")
        members = _extract_check_members(path)
        assert "check-a" in members
        assert "check" in members

    def test_recursive_make_recipe_member_present(self, tmp_path: Path) -> None:
        """A gate invoked through $(MAKE) in the check recipe is a member."""
        path = _write_make_fixture(tmp_path, "check:\n\t$(MAKE) check-a\ncheck-a:\n\t@echo A\n")
        members = _extract_check_members(path)
        assert "check-a" in members

    def test_variable_composed_prereq_member_present(self, tmp_path: Path) -> None:
        """A variable-composed prerequisite resolves to a concrete member."""
        path = _write_make_fixture(
            tmp_path,
            "SUFFIX := core-compat\ncheck: check-$(SUFFIX)\ncheck-core-compat:\n\t@echo gate\n",
        )
        members = _extract_check_members(path)
        assert "check-core-compat" in members

    def test_variable_composed_recipe_goal_present(self, tmp_path: Path) -> None:
        """A $(MAKE) goal composed from make variables resolves to a member."""
        path = _write_make_fixture(
            tmp_path,
            "SUFFIX := core-compat\nREC := check-$(SUFFIX)\n"
            "check:\n\t$(MAKE) $(REC)\ncheck-core-compat:\n\t@echo gate\n",
        )
        members = _extract_check_members(path)
        assert "check-core-compat" in members

    def test_delegation_chain_reaches_member(self, tmp_path: Path) -> None:
        """Membership is transitive through the prerequisite closure."""
        path = _write_make_fixture(tmp_path, "check: all\nall: check-a\ncheck-a:\n\t@echo A\n")
        members = _extract_check_members(path)
        assert "all" in members
        assert "check-a" in members

    def test_standalone_recipe_owner_removed_from_check_absent(self, tmp_path: Path) -> None:
        """A recipe-owning gate removed from check is NOT a member (F-001)."""
        path = _write_make_fixture(
            tmp_path, "check: check-a\ncheck-a:\n\t@echo A\ncheck-b:\n\t@echo B\n"
        )
        members = _extract_check_members(path)
        assert "check-a" in members
        assert "check-b" not in members

    def test_makefile_without_check_root_yields_empty_members(self, tmp_path: Path) -> None:
        """No check target means nothing is a check member (fail-closed)."""
        path = _write_make_fixture(tmp_path, "check-a:\n\t@echo A\n")
        members = _extract_check_members(path)
        assert members == set()

    def test_include_fixture_members_present(self, tmp_path: Path) -> None:
        """Check members defined in an included fragment are present (F-002)."""
        path = _write_make_fixture(
            tmp_path,
            "include gates.mk\ncheck:\n\t$(MAKE) check-included\n",
            {"gates.mk": "check-included:\n\t@echo included\n"},
        )
        members = _extract_check_members(path)
        assert "check-included" in members


class TestIncludeFailHard:
    """Missing/malformed includes fail hard with named errors (F-002)."""

    def test_missing_include_fails_hard_named(self, tmp_path: Path) -> None:
        """A missing included file makes observation fail hard naming the file."""
        path = _write_make_fixture(tmp_path, "include missing.mk\ncheck:\n\t@echo ok\n")
        with pytest.raises(SchemaValidationError, match="missing.mk"):
            _extract_check_members(path)

    def test_malformed_include_fails_hard_named(self, tmp_path: Path) -> None:
        """A malformed included fragment fails hard naming the file."""
        path = _write_make_fixture(
            tmp_path,
            "include gates.mk\ncheck:\n\t@echo ok\n",
            {"gates.mk": "$(UNTERMINATED\n"},
        )
        with pytest.raises(SchemaValidationError, match="gates.mk"):
            _extract_check_members(path)


class TestRealCheckMembership:
    """The repository Makefile's check aggregation invariant (F-001)."""

    def test_five_conformance_gates_are_check_members(self) -> None:
        """All five conformance gates are reachable from the real check target."""
        members = _extract_check_members(REPO_ROOT / "Makefile")
        for target in CONFORMANCE_MAKE_TARGETS:
            assert target in members, f"Expected {target} in check members"

    def test_standalone_targets_absent_from_check(self) -> None:
        """Standalone gates not wired into check are absent (F-001 false-green)."""
        members = _extract_check_members(REPO_ROOT / "Makefile")
        assert "frontend-proof" not in members
        assert "smoke-install" not in members
        assert "check-gate-parity" not in members


class TestMakeRegistryDerivation:
    """The Make check aggregation is sourced from a registry fixture."""

    def test_non_local_check_gate_is_picked_up_without_makefile_edit(self, tmp_path: Path) -> None:
        """A registry-only check-* gate is included regardless of its context."""
        registry_path = tmp_path / "gate_registry.json"
        registry = json.loads(
            (REPO_ROOT / "scripts" / "gate_registry.json").read_text(encoding="utf-8")
        )
        registry["gates"].append(
            {
                "id": "fake-non-local-check",
                "description": "Temporary non-local check gate",
                "required_contexts": ["publish"],
                "bindings": {
                    "make_target": "check-gate-parity",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": [],
            }
        )
        registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

        result = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "-n",
                "check",
                f"GATE_REGISTRY={registry_path}",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
        output = result.stdout + result.stderr
        assert (
            "make check-core-compat check-module-core-imports check-manifest-sync "
            "check-org-context-primitives check-csrf-exempt check-gate-parity"
        ) in output

    def test_local_non_check_gate_is_excluded_without_makefile_edit(self, tmp_path: Path) -> None:
        """A local gate without a check-* target is excluded from Make check."""
        registry_path = tmp_path / "gate_registry.json"
        registry = json.loads(
            (REPO_ROOT / "scripts" / "gate_registry.json").read_text(encoding="utf-8")
        )
        registry["gates"].append(
            {
                "id": "fake-local-non-check",
                "description": "Temporary local non-check gate",
                "required_contexts": ["local-serial", "local-parallel"],
                "bindings": {
                    "make_target": "temporary-local-non-check",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": [],
            }
        )
        registry_path.write_text(json.dumps(registry, indent=2), encoding="utf-8")

        result = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "-n",
                "check",
                f"GATE_REGISTRY={registry_path}",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )

        assert result.returncode == 0, f"stdout={result.stdout}\nstderr={result.stderr}"
        output = result.stdout + result.stderr
        assert (
            "make check-core-compat check-module-core-imports check-manifest-sync "
            "check-org-context-primitives check-csrf-exempt"
        ) in output
        assert "make temporary-local-non-check" not in output


# =========================================================================
# SA122b — hybrid hosted CI gate generation
# =========================================================================


class TestHostedCiGateGeneration:
    """The generated regions preserve hosted workflow semantics exactly."""

    @staticmethod
    def _projection(
        text: str,
    ) -> tuple[
        frozenset[str],
        dict[str, tuple[str, ...]],
        dict[str, tuple[str, ...]],
    ]:
        workflow = _parse_workflow(text, "fixture ci.yml")
        jobs = workflow["jobs"]
        assert isinstance(jobs, dict)
        needs: dict[str, tuple[str, ...]] = {}
        run_values: dict[str, tuple[str, ...]] = {}
        for job_id, job in jobs.items():
            assert isinstance(job, dict)
            raw_needs = job.get("needs", [])
            needs[job_id] = (raw_needs,) if isinstance(raw_needs, str) else tuple(raw_needs)
            run_values[job_id] = tuple(
                step["run"]
                for step in job.get("steps", [])
                if isinstance(step, dict) and "run" in step
            )
        return frozenset(jobs), needs, run_values

    def test_base_loader_projection_has_all_jobs_and_three_generated_needs(self) -> None:
        """BaseLoader observes the exact static job and dependency projection."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        jobs, needs, run_values = self._projection(workflow_text)
        assert len(jobs) == 11
        assert needs["test"] == (
            "backups-validation",
            "module-manifest-contract",
            "module-core-compat",
            "module-core-import-linter",
            "manifest-sync-gate",
            "org-context-primitives-gate",
            "csrf-exempt-gate",
        )
        for consumer in ("isolation-conformance", "lint-cli"):
            assert needs[consumer] == (
                "backups-validation",
                "module-manifest-contract",
                "manifest-sync-gate",
                "org-context-primitives-gate",
                "csrf-exempt-gate",
            )
        assert run_values["module-core-compat"][-1] == "make check-core-compat\n"
        assert expected_workflow_text(workflow_text, registry) == workflow_text

    def test_generation_is_idempotent(self) -> None:
        """A generated workflow is stable under a second generation pass."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        generated = expected_workflow_text(workflow_text, registry)
        assert expected_workflow_text(generated, registry) == generated
        assert self._projection(generated) == self._projection(workflow_text)

    def test_malformed_marker_fails_closed(self) -> None:
        """An incomplete generated pair is an invalid input, not drift."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        malformed = workflow_text.replace(f"{JOB_END}\n", "", 1)
        with pytest.raises(GeneratorError, match="marker"):
            expected_workflow_text(malformed, registry)

    def test_duplicate_yaml_key_fails_closed(self) -> None:
        """BaseLoader parsing rejects duplicate workflow mapping keys."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        malformed = workflow_text.replace("name: CI\n", "name: CI\nname: Duplicate\n", 1)
        with pytest.raises(GeneratorError, match="Duplicate YAML key"):
            expected_workflow_text(malformed, registry)

    def test_unsupported_hosted_registry_fails_closed(self, tmp_path: Path) -> None:
        """A registry hosted set outside the supported static catalog is rejected."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"] = registry_data["gates"][:4] + registry_data["gates"][5:]
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        with pytest.raises(GeneratorError, match="unsupported hosted gate set"):
            expected_workflow_text(
                DEFAULT_WORKFLOW.read_text(encoding="utf-8"), _parse_registry(registry_path)
            )

    def test_registry_make_target_propagates_to_hosted_job(self, tmp_path: Path) -> None:
        """A registry target edit propagates only to its owned hosted run value."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"][0]["bindings"]["make_target"] = "check-core-compat-renamed"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        gates = _parse_registry(registry_path)
        current = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        generated = expected_workflow_text(current, gates)

        assert "make check-core-compat-renamed\n" in generated
        assert "make check-core-compat\n" not in generated
        assert "needs-test" in generated
        assert (
            "needs: [backups-validation, module-manifest-contract, module-core-compat" in generated
        )

    def test_registry_ci_job_rename_generates_new_hosted_job_ids(self, tmp_path: Path) -> None:
        """A supported ci_job rename is not rejected before generation (F-005)."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"][0]["bindings"]["ci_job"] = "module-core-compat-renamed"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        gates = _parse_registry(registry_path)
        current = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        generated = expected_workflow_text(current, gates)

        assert "  module-core-compat-renamed:\n" in generated
        assert "  module-core-compat:\n" not in generated
        assert (
            "needs: [backups-validation, module-manifest-contract, module-core-compat-renamed, "
            "module-core-import-linter, manifest-sync-gate, org-context-primitives-gate, "
            "csrf-exempt-gate]" in generated
        )
        assert expected_workflow_text(generated, gates) == generated

    def test_ci_job_rename_preserves_unowned_workflow_bytes(self, tmp_path: Path) -> None:
        """A ci_job rename preserves every byte outside the owned marker regions."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"][0]["bindings"]["ci_job"] = "module-core-compat-renamed"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        gates = _parse_registry(registry_path)
        current = DEFAULT_WORKFLOW.read_text(encoding="utf-8").replace(
            "name: CI\n", "name: CI\n# unowned sentinel\n", 1
        )
        generated = expected_workflow_text(current, gates)

        def without_owned_regions(text: str) -> str:
            lines = text.splitlines(keepends=True)
            ranges = [(lines.index(JOB_BEGIN + "\n"), lines.index(JOB_END + "\n"))]
            for consumer in NEEDS_BEGIN:
                ranges.append(
                    (
                        lines.index(NEEDS_BEGIN[consumer] + "\n"),
                        lines.index(NEEDS_END[consumer] + "\n"),
                    )
                )
            owned = {index for start, end in ranges for index in range(start, end + 1)}
            return "".join(line for index, line in enumerate(lines) if index not in owned)

        assert without_owned_regions(generated) == without_owned_regions(current)

    def test_ci_job_rename_bootstraps_markers_from_marker_less_workflow(
        self, tmp_path: Path
    ) -> None:
        """A marker-less workflow is bootstrapped around a renamed hosted job set."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"][0]["bindings"]["ci_job"] = "module-core-compat-renamed"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        gates = _parse_registry(registry_path)
        current = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        for marker in (JOB_BEGIN, JOB_END, *NEEDS_BEGIN.values(), *NEEDS_END.values()):
            current = current.replace(marker + "\n", "", 1)
        generated = expected_workflow_text(current, gates)

        assert "  module-core-compat-renamed:\n" in generated
        assert "  module-core-compat:\n" not in generated
        assert (
            "needs: [backups-validation, module-manifest-contract, module-core-compat-renamed, "
            "module-core-import-linter, manifest-sync-gate, org-context-primitives-gate, "
            "csrf-exempt-gate]" in generated
        )
        assert expected_workflow_text(generated, gates) == generated

    def test_cli_ci_job_rename_check_write_and_clean_exit_contract(self, tmp_path: Path) -> None:
        """A registry ci_job rename is reported as drift, written, then checks clean."""
        workflow_path = tmp_path / "ci.yml"
        workflow_path.write_text(DEFAULT_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"][0]["bindings"]["ci_job"] = "module-core-compat-renamed"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        command = [sys.executable, str(Path(sync_ci_gate_jobs_module.__file__))]
        args = ["--workflow", str(workflow_path), "--registry", str(registry_path)]

        check = subprocess.run(
            [*command, "--check", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert check.returncode == 1, check.stderr
        assert "module-core-compat-renamed" in check.stdout

        write = subprocess.run(
            [*command, "--write", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert write.returncode == 0, write.stderr
        written = workflow_path.read_text(encoding="utf-8")
        assert "  module-core-compat-renamed:\n" in written
        assert "  module-core-compat:\n" not in written
        assert (
            "needs: [backups-validation, module-manifest-contract, module-core-compat-renamed, "
            "module-core-import-linter, manifest-sync-gate, org-context-primitives-gate, "
            "csrf-exempt-gate]" in written
        )

        clean = subprocess.run(
            [*command, "--check", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert clean.returncode == 0, clean.stderr

    def test_unowned_workflow_bytes_are_preserved_exactly(self, tmp_path: Path) -> None:
        """Generation preserves every byte outside the owned marker regions."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"][0]["bindings"]["make_target"] = "check-core-compat-renamed"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        gates = _parse_registry(registry_path)
        current = DEFAULT_WORKFLOW.read_text(encoding="utf-8").replace(
            "name: CI\n", "name: CI\n# unowned sentinel\n", 1
        )
        generated = expected_workflow_text(current, gates)

        def without_owned_regions(text: str) -> str:
            lines = text.splitlines(keepends=True)
            ranges = [(lines.index(JOB_BEGIN + "\n"), lines.index(JOB_END + "\n"))]
            for consumer in NEEDS_BEGIN:
                ranges.append(
                    (
                        lines.index(NEEDS_BEGIN[consumer] + "\n"),
                        lines.index(NEEDS_END[consumer] + "\n"),
                    )
                )
            owned = {index for start, end in ranges for index in range(start, end + 1)}
            return "".join(line for index, line in enumerate(lines) if index not in owned)

        assert without_owned_regions(generated) == without_owned_regions(current)

    def test_hosted_markers_must_own_exact_top_level_jobs(self) -> None:
        """A hosted marker pair moved around another job fails closed."""
        current = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        relocated = current.replace(JOB_BEGIN + "\n", "", 1).replace(JOB_END + "\n", "", 1)
        relocated = relocated.replace("  test:\n", JOB_BEGIN + "\n  test:\n", 1)
        relocated = relocated.replace(
            "  isolation-conformance:\n", JOB_END + "\n  isolation-conformance:\n", 1
        )
        with pytest.raises(GeneratorError, match="exactly the named top-level jobs"):
            expected_workflow_text(relocated, _parse_registry(DEFAULT_REGISTRY))

    def test_needs_markers_must_own_named_consumer_job(self) -> None:
        """A needs marker pair in a sibling job cannot authorize rewriting it."""
        current = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        begin = NEEDS_BEGIN["test"] + "\n"
        end = NEEDS_END["test"] + "\n"
        relocated = current.replace(begin, "", 1).replace(end, "", 1)
        needs_line = (
            "    needs: [backups-validation, module-manifest-contract, "
            "manifest-sync-gate, org-context-primitives-gate, csrf-exempt-gate]\n"
        )
        relocated = relocated.replace(needs_line, begin + needs_line + end, 1)
        with pytest.raises(GeneratorError, match="not owned by its top-level job"):
            expected_workflow_text(relocated, _parse_registry(DEFAULT_REGISTRY))

    def test_cli_check_write_and_clean_exit_contract(self, tmp_path: Path) -> None:
        """CLI check/read-write modes report drift, atomically write, then cleanly check."""
        workflow_path = tmp_path / "ci.yml"
        workflow_path.write_text(
            DEFAULT_WORKFLOW.read_text(encoding="utf-8").replace(
                "make check-core-compat\n", "make check-core-compat-renamed\n", 1
            ),
            encoding="utf-8",
        )
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"][0]["bindings"]["make_target"] = "check-core-compat-renamed"
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")

        command = [sys.executable, str(Path(sync_ci_gate_jobs_module.__file__))]
        check = subprocess.run(
            [
                *command,
                "--check",
                "--workflow",
                str(workflow_path),
                "--registry",
                str(registry_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert check.returncode == 0, check.stderr

        workflow_path.write_text(
            workflow_path.read_text(encoding="utf-8").replace(
                "make check-core-compat-renamed\n", "make check-core-compat-stale\n", 1
            ),
            encoding="utf-8",
        )
        drift = subprocess.run(
            [
                *command,
                "--check",
                "--workflow",
                str(workflow_path),
                "--registry",
                str(registry_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert drift.returncode == 1
        assert "check-core-compat-stale" in drift.stdout
        write = subprocess.run(
            [
                *command,
                "--write",
                "--workflow",
                str(workflow_path),
                "--registry",
                str(registry_path),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert write.returncode == 0, write.stderr
        assert "make check-core-compat-renamed\n" in workflow_path.read_text(encoding="utf-8")

    def test_atomic_write_cleans_temporary_file_on_replace_failure(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Atomic replacement failure leaves the original and no temporary file."""
        target = tmp_path / "ci.yml"
        target.write_text("original\n", encoding="utf-8")

        def fail_replace(
            source: str | bytes | os.PathLike[str], destination: str | bytes | os.PathLike[str]
        ) -> None:
            raise OSError("replace failed")

        monkeypatch.setattr(sync_ci_gate_jobs_module.os, "replace", fail_replace)
        with pytest.raises(OSError, match="replace failed"):
            _atomic_write(target, "replacement\n")
        assert target.read_text(encoding="utf-8") == "original\n"
        assert not tuple(tmp_path.glob(".ci.yml.*"))

    def test_helper_accepts_checker_valid_long_dag(self, tmp_path: Path) -> None:
        """The generator accepts the same long acyclic dependency class as the checker."""
        gate_ids = [f"gate-{index:04d}" for index in range(1200)]
        registry = {
            "schema_version": 1,
            "description": "Long DAG",
            "contexts": dict(_ALL_CONTEXTS),
            "gates": [
                {
                    "id": gate_id,
                    "description": gate_id,
                    "required_contexts": ["local-serial"],
                    "bindings": {
                        "make_target": None,
                        "ci_job": None,
                        "local_ci_stage": None,
                    },
                    "depends_on": [gate_ids[index - 1]] if index else [],
                    "trigger_inputs": [],
                }
                for index, gate_id in enumerate(gate_ids)
            ],
        }
        path = tmp_path / "long-dag.json"
        path.write_text(json.dumps(registry), encoding="utf-8")
        assert [gate["id"] for gate in _parse_registry(path)] == gate_ids

    def test_helper_rejects_duplicate_registry_key(self, tmp_path: Path) -> None:
        """Duplicate registry keys are rejected before generation."""
        path = tmp_path / "duplicate.json"
        path.write_text(
            '{"schema_version": 1, "schema_version": 1, "description": "x", '
            '"contexts": {}, "gates": []}',
            encoding="utf-8",
        )
        with pytest.raises(GeneratorError, match="Duplicate JSON key"):
            _parse_registry(path)


# =========================================================================
# F-006 — mandatory generation drift gate
# =========================================================================


class TestMandatoryGenerationGate:
    """CI workflow generation drift fails mandatory ``make check`` (F-006)."""

    def test_mandatory_check_plans_generation_drift_gate(self) -> None:
        """The real Makefile's check recipe plans the direct generation check."""
        result = subprocess.run(
            ["make", "-n", "check", "QUIET=1"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert "scripts/sync_ci_gate_jobs.py --check" in result.stdout, (
            "make check must plan the direct generation drift gate (F-006)"
        )

    def test_generation_drift_fails_mandatory_gate_command(self, tmp_path: Path) -> None:
        """Stale generated content fails the check-recipe generation command."""
        workflow_path = tmp_path / "ci.yml"
        workflow_path.write_text(
            DEFAULT_WORKFLOW.read_text(encoding="utf-8").replace(
                "make check-core-compat\n", "make check-core-compat-stale\n", 1
            ),
            encoding="utf-8",
        )
        result = subprocess.run(
            [
                sys.executable,
                str(Path(sync_ci_gate_jobs_module.__file__)),
                "--check",
                "--workflow",
                str(workflow_path),
                "--registry",
                str(DEFAULT_REGISTRY),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 1, result.stderr
        assert "check-core-compat-stale" in result.stdout

    def test_generation_clean_passes_mandatory_gate_command(self, tmp_path: Path) -> None:
        """Clean generated content passes the check-recipe generation command."""
        workflow_path = tmp_path / "ci.yml"
        workflow_path.write_text(DEFAULT_WORKFLOW.read_text(encoding="utf-8"), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(sync_ci_gate_jobs_module.__file__)),
                "--check",
                "--workflow",
                str(workflow_path),
                "--registry",
                str(DEFAULT_REGISTRY),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr

        # The real standalone target must also pass on the clean tree.
        target = subprocess.run(
            ["make", "check-ci-gate-generation"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert target.returncode == 0, target.stderr


# =========================================================================
# F-006 caller parity — Make generator checks use the selected registry
# =========================================================================


class TestGenerationGateRegistryParity:
    """Every Make-driven generation check consumes the invocation's GATE_REGISTRY."""

    @staticmethod
    def _custom_registry(tmp_path: Path, *, renamed: bool) -> Path:
        """Write a repo-contained registry fixture, optionally with a run drift."""
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        if renamed:
            data["gates"][0]["bindings"]["make_target"] = "check-core-compat-renamed"
        path = _repo_fixture_file(tmp_path, "custom_registry.json")
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return path

    def test_custom_registry_drift_fails_standalone_target(self, tmp_path: Path) -> None:
        """A GATE_REGISTRY override whose hosted run drifted fails the target."""
        registry_path = self._custom_registry(tmp_path, renamed=True)
        result = subprocess.run(
            ["make", "check-ci-gate-generation", f"GATE_REGISTRY={registry_path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        # GNU Make maps the script's drift exit (1) to its own recipe-failure
        # exit (2); the meaningful assertion is that the gate failed and the
        # drift diff names the selected registry's target.
        assert result.returncode != 0, result.stderr
        assert "check-core-compat-renamed" in result.stdout

    def test_custom_registry_clean_passes_standalone_target(self, tmp_path: Path) -> None:
        """A GATE_REGISTRY override identical to the default passes the target."""
        registry_path = self._custom_registry(tmp_path, renamed=False)
        result = subprocess.run(
            ["make", "check-ci-gate-generation", f"GATE_REGISTRY={registry_path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr

    def test_mandatory_check_plans_selected_registry(self, tmp_path: Path) -> None:
        """Make check plans the generation gate with the selected GATE_REGISTRY."""
        # A registry-identical fixture keeps the -n recursive derivation on
        # targets that exist, so the planned generation line is what is proven.
        registry_path = self._custom_registry(tmp_path, renamed=False)
        result = subprocess.run(
            ["make", "-n", "check", "QUIET=1", f"GATE_REGISTRY={registry_path}"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert f'sync_ci_gate_jobs.py --check --registry "{registry_path}"' in result.stdout

    def test_selected_registry_drift_fails_mandatory_gate_command(self, tmp_path: Path) -> None:
        """The mandatory-recipe command fails/cleans against the selected registry."""
        command = [sys.executable, str(Path(sync_ci_gate_jobs_module.__file__)), "--check"]
        drifted = self._custom_registry(tmp_path, renamed=True)
        clean = self._custom_registry(tmp_path, renamed=False)

        fail = subprocess.run(
            [*command, "--registry", str(drifted)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert fail.returncode == 1, fail.stderr
        assert "check-core-compat-renamed" in fail.stdout

        ok = subprocess.run(
            [*command, "--registry", str(clean)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert ok.returncode == 0, ok.stderr


class TestMakeRegistryDerivationFailure:
    """Make derives targets strictly and aborts during parsing on bad input."""

    def test_malformed_registry_stops_make_before_recipe(self, tmp_path: Path) -> None:
        """A malformed registry cannot fall through to a Make recipe."""
        registry_path = tmp_path / "bad-registry.json"
        registry_path.write_text("{not valid json", encoding="utf-8")
        marker = tmp_path / "recipe-ran"
        result = subprocess.run(
            [
                "make",
                "--no-print-directory",
                "check-gate-parity",
                f"GATE_REGISTRY={registry_path}",
                f"CHECK_GATE_TARGETS_SENTINEL={marker}",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode != 0
        assert "Unable to derive local check gate targets" in result.stderr
        assert not marker.exists()
