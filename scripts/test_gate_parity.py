"""
Focused tests for SA122a gate parity checker.

Test matrix
-----------
- Current reproduction (exact publish gap + no spurious diagnostics)
- Fake-gate fan-out (add a gate, verify it propagates)
- Complete schema validation (every field constraint)
- Malformed sources (bad JSON, missing files)
- Parser precision (serial/parallel/hosted/publish extraction)
- Additive boundary (new gate in registry but not in any source)
"""

from __future__ import annotations

import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from scripts.check_gate_parity import (
    SchemaValidationError,
    _assert_canonical_makefile_input,
    _extract_check_ci_parallel_gates,
    _extract_check_ci_serial_gates,
    _extract_check_members,
    _extract_ci_job_names,
    _extract_e2e_trigger_paths,
    _extract_makefile_targets,
    _extract_publish_gates,
    _is_subsequence,
    _run_bash_observation,
    _validate_registry,
)

SCRIPT = Path(__file__).with_name("check_gate_parity.py")
REPO_ROOT = SCRIPT.parents[1]
CHECK_CI = REPO_ROOT / "scripts" / "check_ci_locally.sh"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_YML = REPO_ROOT / ".github" / "workflows" / "publish.yml"
E2E_YML = REPO_ROOT / ".github" / "workflows" / "e2e.yml"

# The 5 known publish conformance-gate gaps (SA122-DEC-001)
PUBLISH_GAP_IDS: frozenset[str] = frozenset(
    {
        "check-core-compat",
        "check-module-core-imports",
        "check-manifest-sync",
        "check-org-context-primitives",
        "check-csrf-exempt",
    }
)

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


def _make_registry_json(gates: list[dict[str, Any]], tmp_path: Path) -> Path:
    """Write a registry JSON file and return its path (includes all 5 contexts)."""
    data: dict[str, Any] = {
        "schema_version": 1,
        "description": "Test registry",
        "contexts": dict(_ALL_CONTEXTS),
        "gates": gates,
    }
    path = tmp_path / "test_registry.json"
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return path


# =========================================================================
# Current reproduction
# =========================================================================


class TestCurrentReproduction:
    """Tests that run against the real repository state."""

    def test_reports_exactly_five_publish_gaps(self) -> None:
        """Exit 1 with exactly 5 missing publish conformance gates."""
        result = _run_checker()
        assert result.returncode == 1
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        assert len(lines) == 5, f"Expected 5 diagnostics, got {len(lines)}"

    def test_each_publish_gap_is_a_conformance_gate(self) -> None:
        """Every missing gate ID is one of the five known conformance gates."""
        result = _run_checker()
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        found_ids = {json.loads(line)["gate_id"] for line in lines}
        assert found_ids == PUBLISH_GAP_IDS, f"Expected {PUBLISH_GAP_IDS}, got {found_ids}"

    def test_all_diagnostics_are_publish_context(self) -> None:
        """Every diagnostic is a context='publish' missing gate."""
        result = _run_checker()
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        for line in lines:
            record = json.loads(line)
            assert record["level"] == "missing"
            assert record["context"] == "publish"
            assert record["gate_id"] in PUBLISH_GAP_IDS

    def test_stdout_is_valid_jsonl(self) -> None:
        """Every stdout line is parseable JSON."""
        result = _run_checker()
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        for line in lines:
            record = json.loads(line)
            assert "level" in record
            assert "context" in record
            assert "gate_id" in record
            assert "source" in record
            assert "detail" in record

    def test_stderr_contains_no_error_when_exit_1(self) -> None:
        """Exit 1 should have no ERROR: on stderr."""
        result = _run_checker()
        assert result.returncode == 1
        assert "ERROR:" not in result.stderr


# =========================================================================
# Fake-gate fan-out
# =========================================================================


class TestFakeGateFanOut:
    """Adding a gate to the registry propagates to diagnostics."""

    def test_fake_gate_in_publish_appears_as_diagnostic(self, tmp_path: Path) -> None:
        """A gate requiring publish context that is not in publish.yml shows as missing."""
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
        assert result.returncode == 1
        lines = [line for line in result.stdout.splitlines() if line.strip()]
        # One for publish missing, none for makefile because check-core-compat IS in Makefile
        publish_diags = [
            json.loads(ln) for ln in lines if json.loads(ln).get("context") == "publish"
        ]
        assert len(publish_diags) == 1
        record = publish_diags[0]
        assert record["gate_id"] == "fake-gate"
        assert record["level"] == "missing"

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
        # Should still report the five publish gaps (exit 1), not exit 0
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
        path = tmp_path / "bad_registry.json"
        path.write_text(json.dumps(registry, indent=2), encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2, (
            f"Expected exit 2, got {result.returncode}: stderr={result.stderr}"
        )
        assert "ERROR:" in result.stderr

    def _check_accepted(self, registry: dict[str, Any], tmp_path: Path) -> None:
        path = tmp_path / "good_registry.json"
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
        path = tmp_path / "dupe_keys.json"
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
        path = tmp_path / "nested_dupe.json"
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
        missing = tmp_path / "nonexistent.json"
        result = _run_checker(["--registry", str(missing)])
        assert result.returncode == 2
        assert "ERROR:" in result.stderr
        assert "FILE_NOT_FOUND" in result.stderr or "SCHEMA_ERROR" in result.stderr

    def test_invalid_registry_json(self, tmp_path: Path) -> None:
        """Malformed JSON in registry produces exit 2."""
        path = tmp_path / "bad.json"
        path.write_text("this is not json", encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2
        assert "ERROR:" in result.stderr

    def test_empty_registry(self, tmp_path: Path) -> None:
        """Empty file produces exit 2."""
        path = tmp_path / "empty.json"
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
        assert targets == CONFORMANCE_MAKE_TARGETS, (
            f"Serial extraction returned {targets}, expected {CONFORMANCE_MAKE_TARGETS}"
        )

    def test_parallel_extracts_all_five_conformance_gates(self) -> None:
        """The parallel path in check_ci_locally.sh has all 5 check gates."""
        targets = _extract_check_ci_parallel_gates(CHECK_CI)
        assert targets == CONFORMANCE_MAKE_TARGETS, (
            f"Parallel extraction returned {targets}, expected {CONFORMANCE_MAKE_TARGETS}"
        )

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

    def test_publish_has_none_of_the_five_check_gates(self) -> None:
        """publish.yml has none of the 5 check-* make targets."""
        targets = _extract_publish_gates(PUBLISH_YML)
        overlap = CONFORMANCE_MAKE_TARGETS & targets
        assert not overlap, f"publish.yml unexpectedly contains make targets: {overlap}"

    def test_serial_does_not_pick_up_parallel_gates(self) -> None:
        """Serial extraction should not pick gates that only exist in parallel."""
        serial = _extract_check_ci_serial_gates(CHECK_CI)
        parallel = _extract_check_ci_parallel_gates(CHECK_CI)
        # All 5 conformance gates are in both — verify this holds
        assert serial == parallel, (
            f"Serial and parallel extraction disagree: serial={serial}, parallel={parallel}"
        )

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

    def test_publish_has_none_of_five_check_targets(self) -> None:
        """publish.yml must NOT contain any of the 5 conformance gate make targets."""
        targets = _extract_publish_gates(PUBLISH_YML)
        overlap = CONFORMANCE_MAKE_TARGETS & targets
        assert not overlap, f"publish.yml unexpectedly contains make targets: {overlap}"

    def test_publish_structural_parsing_rejects_duplicate_yaml_keys(self, tmp_path: Path) -> None:
        """Duplicate YAML keys in publish.yml structure raise exit 2."""
        from scripts.check_gate_parity import SchemaValidationError, _parse_yaml_strict

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
        """A joined worker's delayed child cannot mutate logs after acceptance."""
        script = tmp_path / "sa128b_parallel_residual_descendant.sh"
        residual_marker = tmp_path / "residual-marker"
        script.write_text(
            "run_static_gates_parallel() {\n"
            "    joined_worker() {\n"
            f"        ( /bin/sleep 0.25; printf late > {residual_marker} ) &\n"
            "    }\n"
            "    launch_static_gate joined 1 desc ok label joined_worker\n"
            '    wait "${WORKER_PIDS[0]}"\n'
            "}\n",
            encoding="utf-8",
        )
        with pytest.raises(SchemaValidationError, match="live descendants|process group"):
            _run_bash_observation(script, "run_static_gates_parallel")

        # The cleanup must happen before the observer accepts the inventory;
        # waiting past the child delay proves that no delayed recorder work
        # remains able to mutate the external marker.
        import time

        time.sleep(0.35)
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
        import scripts.check_gate_parity as parity

        monkeypatch.setattr(parity, "_BASH_TIMEOUT_SECONDS", 0.2)
        script = tmp_path / "sa128b_timeout.sh"
        script.write_text("run_static_gates_serial() { while :; do :; done; }\n", encoding="utf-8")
        with pytest.raises(SchemaValidationError, match="timeout"):
            _extract_check_ci_serial_gates(script)


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
        from scripts.check_gate_parity import SchemaValidationError

        path = self._make_publish_yaml(tmp_path, "            make frontend-proof || true\n")
        with pytest.raises(SchemaValidationError, match="Deceptive|control"):
            _extract_publish_gates(path)

    def test_make_with_and_other_rejected(self, tmp_path: Path) -> None:
        """Deceptive 'make TARGET && make OTHER' raises SchemaValidationError."""
        from scripts.check_gate_parity import SchemaValidationError

        path = self._make_publish_yaml(
            tmp_path, "            make frontend-proof && make smoke-install\n"
        )
        with pytest.raises(SchemaValidationError, match="Deceptive|control"):
            _extract_publish_gates(path)

    def test_make_inside_conditional_rejected(self, tmp_path: Path) -> None:
        """Make inside if/then conditional raises SchemaValidationError."""
        from scripts.check_gate_parity import SchemaValidationError

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
        from scripts.check_gate_parity import SchemaValidationError

        path = self._make_publish_yaml(tmp_path, "            make frontend-proof &\n")
        with pytest.raises(SchemaValidationError, match="Deceptive|control"):
            _extract_publish_gates(path)


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
        path = tmp_path / "bad.json"
        path.write_text("not valid json", encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2
        assert "ERROR:" in result.stderr
        assert not result.stdout.strip()

    def test_exit_two_empty_stdout_one_error_no_traceback(self, tmp_path: Path) -> None:
        """Exit 2: empty stdout, exactly one ERROR line on stderr, no traceback."""
        path = tmp_path / "bad.json"
        path.write_text("this is not json", encoding="utf-8")
        result = _run_checker(["--registry", str(path)])
        assert result.returncode == 2
        assert not result.stdout.strip(), "Expected empty stdout on exit 2"
        error_lines = [line for line in result.stderr.splitlines() if line.startswith("ERROR:")]
        assert len(error_lines) == 1, (
            f"Expected exactly one ERROR line, got {len(error_lines)}: {result.stderr}"
        )
        assert "Traceback" not in result.stderr

    def test_make_wrapper_translates_exit_1_to_exit_2(self) -> None:
        """Make check-gate-parity translates exit 1 to exit 2 (tested via subprocess)."""
        result = subprocess.run(
            ["make", "check-gate-parity"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        # With real registry, should exit 2 because of publish gap
        assert result.returncode == 2, (
            f"Expected exit 2 from make, got {result.returncode}: stderr={result.stderr}"
        )
        assert "ERROR:" in result.stderr


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
        import scripts.check_gate_parity as parity

        monkeypatch.setattr(parity, "_MAKE_TIMEOUT_SECONDS", 0.5)
        makefile = tmp_path / "Makefile"
        makefile.write_text("SLOW := $(shell sleep 5)\ntarget:\n\techo ok\n")
        with pytest.raises(SchemaValidationError, match="timeout"):
            _extract_makefile_targets(makefile)

    def test_output_overrun_fails_hard(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A make observation that exceeds the output bound fails hard."""
        import scripts.check_gate_parity as parity

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
        missing = tmp_path / "Makefile"
        with pytest.raises(FileNotFoundError):
            _assert_canonical_makefile_input(missing)


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
