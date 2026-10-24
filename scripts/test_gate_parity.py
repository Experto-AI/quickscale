"""
Focused tests for the SA259 gate-wiring currency checker.

Test matrix
-----------
- Current repository state (every generated file is current)
- Complete registry schema validation (every field constraint)
- Malformed sources (bad JSON, missing files)
- Generated-file drift detection (Make include and docs table)
- The generator's hosted-job, E2E, publish, and Make-include projections
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import check_gate_parity as check_gate_parity_module
import pytest
import sync_ci_gate_jobs as sync_ci_gate_jobs_module
import yaml
from check_gate_parity import (
    SchemaValidationError,
    _canonical_input_path,
    _validate_registry,
)
from sync_ci_gate_jobs import (
    CHECKOUT_REF,
    DEFAULT_DOCS,
    DEFAULT_E2E_WORKFLOW,
    DEFAULT_LOCAL_SCRIPT,
    DEFAULT_MAKE_INCLUDE,
    DEFAULT_MAKEFILE,
    DEFAULT_PUBLISH_WORKFLOW,
    DEFAULT_REGISTRY,
    DEFAULT_WORKFLOW,
    E2E_PATHS_BEGIN,
    E2E_PATHS_END,
    HAND_OWNED_MAKE_TARGETS,
    JOB_BEGIN,
    JOB_END,
    LOCAL_ARMS_BEGIN,
    LOCAL_ARMS_END,
    MAKEFILE_HELP_BEGIN,
    MAKEFILE_HELP_END,
    NEEDS_BEGIN,
    NEEDS_END,
    PUBLISH_BEGIN,
    PUBLISH_END,
    UNOWNED_JOB_IDS,
    GeneratorError,
    _atomic_write,
    _expected_e2e_paths,
    _parse_registry,
    _parse_workflow,
    expected_docs_text,
    expected_e2e_workflow_text,
    expected_publish_workflow_text,
    expected_workflow_text,
)


def _rename_make_target(registry_data: dict[str, Any], gate_id: str, target: str) -> None:
    """
    Rename one gate's Make target, keeping its registry-owned help line in step.

    A ``makefile_help`` line must name its own target, so a target rename is
    authored in the same registry row rather than left for the schema to reject.
    """
    for gate in registry_data["gates"]:
        if gate["id"] != gate_id:
            continue
        previous = gate["bindings"]["make_target"]
        gate["bindings"]["make_target"] = target
        if "makefile_help" in gate:
            gate["makefile_help"]["text"] = gate["makefile_help"]["text"].replace(previous, target)
        return
    raise AssertionError(gate_id)


def test_markerless_bootstrap_without_registry_owned_jobs_fails_cleanly() -> None:
    """A markerless workflow with no hosted registry job raises GeneratorError, not IndexError."""
    gates = sync_ci_gate_jobs_module._parse_registry(sync_ci_gate_jobs_module.DEFAULT_REGISTRY)
    lines = [
        "name: CI\n",
        "jobs:\n",
        "  unrelated:\n",
        "    name: Unrelated Job\n",
    ]

    with pytest.raises(
        sync_ci_gate_jobs_module.GeneratorError,
        match="no registry-owned jobs were found",
    ):
        sync_ci_gate_jobs_module._bootstrap_job_markers(lines, gates)


SCRIPT = Path(__file__).with_name("check_gate_parity.py")
REPO_ROOT = SCRIPT.parents[1]
CHECK_CI = REPO_ROOT / "scripts" / "check_ci_locally.sh"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"
PUBLISH_YML = REPO_ROOT / ".github" / "workflows" / "publish.yml"
E2E_YML = REPO_ROOT / ".github" / "workflows" / "e2e.yml"

#: The one hand pin on the count (SA285 (a)): the gate oracles read their sets
#: from ``gate_registry.json``, so a registry resize would otherwise flow
#: through every derived expectation unnoticed.  Adding or removing a gate
#: fails here until this literal is re-pinned deliberately.
EXPECTED_GATE_COUNT = 21

# These service-backed workflow stations are the only callers allowed to
# provision hosted PostgreSQL.  This mapping is the test-owned station
# contract; profile facts themselves come from provision_ci_postgres.sh.
EXPECTED_HOSTED_PROFILE_BY_STATION: dict[tuple[str, str], str] = {
    (".github/workflows/ci.yml", "backups-validation"): "backups",
    (".github/workflows/ci.yml", "test"): "restricted",
    (".github/workflows/ci.yml", "isolation-conformance"): "isolation",
    (".github/workflows/publish.yml", "test"): "restricted",
    (".github/workflows/e2e.yml", "e2e-tests"): "client-only",
    (".github/workflows/nightly-bypassrls.yml", "bypassrls"): "bypassrls",
}


def _hosted_setup_calls(path: Path, job_id: str) -> list[str]:
    """Return helper hosted-setup profiles from one structurally parsed job."""
    workflow = sync_ci_gate_jobs_module._parse_workflow(path.read_text(encoding="utf-8"), str(path))
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    job = jobs.get(job_id)
    assert isinstance(job, dict), f"{job_id} is missing from {path}"
    if "uses" in job:
        assert "steps" not in job
        return []
    steps = job.get("steps")
    assert isinstance(steps, list)
    profiles: list[str] = []
    pattern = re.compile(r"^scripts/provision_ci_postgres\.sh hosted-setup --profile ([a-z-]+)$")
    for step in steps:
        if not isinstance(step, dict) or not isinstance(step.get("run"), str):
            continue
        match = pattern.fullmatch(step["run"].strip())
        if match:
            profiles.append(match.group(1))
    return profiles


def _workflow_job_run_text(path: Path, job_id: str) -> str:
    """Return only shell blocks belonging to one structurally parsed job."""
    workflow = sync_ci_gate_jobs_module._parse_workflow(path.read_text(encoding="utf-8"), str(path))
    jobs = workflow.get("jobs")
    assert isinstance(jobs, dict)
    job = jobs.get(job_id)
    assert isinstance(job, dict)
    steps = job.get("steps")
    assert isinstance(steps, list)
    return "\n".join(
        step["run"] for step in steps if isinstance(step, dict) and isinstance(step.get("run"), str)
    )


def _registry_hosted_bindings(registry: Path = DEFAULT_REGISTRY) -> dict[str, str]:
    """Return hosted CI job IDs mapped to their registry-owned Make targets."""
    bindings: dict[str, str] = {}
    for gate in _parse_registry(registry):
        if "hosted" not in gate["required_contexts"]:
            continue
        ci_job = gate["bindings"].get("ci_job")
        make_target = gate["bindings"].get("make_target")
        assert isinstance(ci_job, str) and isinstance(make_target, str)
        bindings[ci_job] = make_target
    return bindings


def _expected_ci_job_ids(registry: Path = DEFAULT_REGISTRY) -> frozenset[str]:
    """Return the closed hosted workflow job universe for a registry."""
    return UNOWNED_JOB_IDS | frozenset(_registry_hosted_bindings(registry))


def _registry_generated_needs(
    registry: Path = DEFAULT_REGISTRY,
) -> dict[str, tuple[str, ...]]:
    """
    Derive every generated consumer ``needs`` list from registry bindings.

    The needs policy (the fixed prerequisites and which gates each consumer
    waits on) is read from the generator's published names; the job order and
    identities come from the parsed registry — hosted gates in their
    ``hosted.order``, the order the generator's own bindings use — so a new
    hosted gate reaches the expectations without a hand edit here.
    """
    hosted = [gate for gate in _parse_registry(registry) if "hosted" in gate["required_contexts"]]
    hosted.sort(key=lambda gate: gate["hosted"]["order"])
    hosted_jobs: dict[str, str] = {}
    for gate in hosted:
        ci_job = gate["bindings"].get("ci_job")
        assert isinstance(ci_job, str), f"hosted gate {gate['id']!r} has no ci_job"
        hosted_jobs[gate["id"]] = ci_job
    needs = {
        "test": sync_ci_gate_jobs_module.FIXED_NEEDS + tuple(hosted_jobs.values()),
    }
    for consumer, gate_ids in sync_ci_gate_jobs_module.NEEDS_GATE_IDS.items():
        needs[consumer] = sync_ci_gate_jobs_module.FIXED_NEEDS + tuple(
            hosted_jobs[gate_id] for gate_id in gate_ids
        )
    return needs


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
    "bindings": {"make_target": "test-gate", "ci_job": None, "local_ci_stage": 3},
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


# ``make -n check`` expands the whole recursive check plan; it costs ~2 s idle
# but competes for CPU with every xdist worker inside a full ``make check``.
_MAKE_PLAN_TIMEOUT = 300


def _plan_make_check(*make_args: str) -> subprocess.CompletedProcess:
    """
    Dry-run the real Makefile's ``check`` recipe with a load-tolerant timeout.

    The plan must not inherit a caller's ``QUIET``: the quiet branch's recursive
    ``$(MAKE)`` lines execute even under ``-n``, and the nested unit run reads
    from the captured test process's stdin.  ``make check QUIET=1`` is the
    documented gate command, so the plan strips that variable.
    """
    return subprocess.run(
        ["make", "-n", "check", *make_args],
        cwd=str(REPO_ROOT),
        env={**os.environ, "QUIET": ""},
        capture_output=True,
        text=True,
        timeout=_MAKE_PLAN_TIMEOUT,
    )


@pytest.fixture(scope="module")
def make_check_plan() -> subprocess.CompletedProcess:
    """One shared default-registry ``make -n check`` plan per module."""
    return _plan_make_check()


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

    def test_registry_gate_count_is_pinned(self) -> None:
        """The registry's size is the one hand pin the gate oracles keep."""
        assert len(_parse_registry(DEFAULT_REGISTRY)) == EXPECTED_GATE_COUNT

    def test_real_checker_stdout_is_empty(self) -> None:
        """A green checker emits no JSONL diagnostics on stdout."""
        result = _run_checker()
        assert not result.stdout.strip(), f"Expected empty stdout, got: {result.stdout}"

    def test_real_checker_stderr_reports_success(self) -> None:
        """A green checker reports its success contract on stderr."""
        result = _run_checker()
        assert "All generated gate wiring is current." in result.stderr

    def test_real_checker_stderr_contains_no_error(self) -> None:
        """A green checker does not emit an ERROR diagnostic."""
        result = _run_checker()
        assert "ERROR:" not in result.stderr


class TestHostedPostgresProfileParity:
    """Hosted workflow stations delegate to the single profile authority."""

    def test_workflow_stations_use_expected_profiles(self) -> None:
        observed: dict[tuple[str, str], str] = {}
        actual_call_counts: dict[tuple[str, str], int] = {}
        workflow_dir = REPO_ROOT / ".github" / "workflows"
        workflow_paths = sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])
        for workflow_path in workflow_paths:
            workflow = yaml.safe_load(workflow_path.read_text())
            jobs = workflow.get("jobs", {})
            for job_id in jobs:
                calls = _hosted_setup_calls(workflow_path, job_id)
                if calls:
                    station = (workflow_path.relative_to(REPO_ROOT).as_posix(), job_id)
                    actual_call_counts[station] = len(calls)

        assert set(actual_call_counts) == set(EXPECTED_HOSTED_PROFILE_BY_STATION)
        assert set(actual_call_counts.values()) == {1}
        total_calls = 0
        for station, expected_profile in EXPECTED_HOSTED_PROFILE_BY_STATION.items():
            workflow_name, job_id = station
            workflow_path = REPO_ROOT / workflow_name
            calls = _hosted_setup_calls(workflow_path, job_id)
            assert len(calls) == 1, f"{station} must have exactly one hosted-setup call"
            assert calls[0] == expected_profile
            observed[station] = calls[0]
            total_calls += len(calls)

            job_text = _workflow_job_run_text(workflow_path, job_id)
            assert "apt-get" not in job_text
            assert "createdb" not in job_text
            assert "ALTER DATABASE" not in job_text
            assert "provision_test_roles.sh" not in job_text

        assert observed == EXPECTED_HOSTED_PROFILE_BY_STATION
        assert total_calls == len(EXPECTED_HOSTED_PROFILE_BY_STATION)

    def test_profiles_are_bound_by_helper_describe_json(self) -> None:
        helper = REPO_ROOT / "scripts" / "provision_ci_postgres.sh"
        for profile in sorted(set(EXPECTED_HOSTED_PROFILE_BY_STATION.values())):
            result = subprocess.run(
                [
                    "/bin/bash",
                    str(helper),
                    "describe",
                    "--profile",
                    profile,
                    "--format",
                    "json",
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            assert result.returncode == 0, result.stderr
            description = json.loads(result.stdout)
            assert description["profile"] == profile
            assert description["schema_version"] == 1
            if profile == "client-only":
                assert description["databases"] == []
                assert description["environment"] == {}
            else:
                assert description["databases"]
                assert description["role"]["flags"]

    def test_bypassrls_reusable_workflow_is_the_only_authorized_hosted_lane(self) -> None:
        ci_workflow = sync_ci_gate_jobs_module._parse_workflow(
            CI_YML.read_text(encoding="utf-8"), str(CI_YML)
        )
        ci_jobs = ci_workflow["jobs"]
        assert ci_jobs["bypassrls"] == {
            "name": "Run BYPASSRLS-privileged tests",
            "uses": "./.github/workflows/nightly-bypassrls.yml",
        }

        nightly_path = REPO_ROOT / ".github" / "workflows" / "nightly-bypassrls.yml"
        nightly = sync_ci_gate_jobs_module._parse_workflow(
            nightly_path.read_text(encoding="utf-8"), str(nightly_path)
        )
        assert set(nightly["on"]) == {"workflow_dispatch", "workflow_call"}
        privileged_step = next(
            step
            for step in nightly["jobs"]["bypassrls"]["steps"]
            if step["name"] == "Run BYPASSRLS-privileged tests (make test-bypassrls)"
        )
        assert privileged_step["env"] == {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}

        backups_step = next(
            step
            for step in ci_jobs["backups-validation"]["steps"]
            if step["name"] == "Run backups module validation tests"
        )
        assert "QUICKSCALE_ALLOW_BYPASSRLS" not in backups_step.get("env", {})

        authorization_sites: list[tuple[str, str, str]] = []
        workflow_dir = REPO_ROOT / ".github" / "workflows"
        workflow_paths = sorted([*workflow_dir.glob("*.yml"), *workflow_dir.glob("*.yaml")])
        for workflow_path in workflow_paths:
            workflow = sync_ci_gate_jobs_module._parse_workflow(
                workflow_path.read_text(encoding="utf-8"), str(workflow_path)
            )
            assert workflow.get("env", {}).get("QUICKSCALE_ALLOW_BYPASSRLS") != "1"
            for job_id, job in workflow.get("jobs", {}).items():
                assert job.get("env", {}).get("QUICKSCALE_ALLOW_BYPASSRLS") != "1"
                for step in job.get("steps", []):
                    if step.get("env", {}).get("QUICKSCALE_ALLOW_BYPASSRLS") == "1":
                        authorization_sites.append(
                            (
                                workflow_path.relative_to(REPO_ROOT).as_posix(),
                                job_id,
                                step["name"],
                            )
                        )

        assert authorization_sites == [
            (
                ".github/workflows/nightly-bypassrls.yml",
                "bypassrls",
                "Run BYPASSRLS-privileged tests (make test-bypassrls)",
            )
        ]


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
        """A perfectly minimal valid registry passes schema validation."""
        assert _validate_registry(_MINIMAL_REGISTRY) == _MINIMAL_REGISTRY["gates"]

    def test_trigger_inputs_contract_is_explicit_at_both_schema_surfaces(self) -> None:
        """The legacy field name cannot hide its exact non-skip semantics."""
        registry = json.loads(
            (REPO_ROOT / "scripts" / "gate_registry.json").read_text(encoding="utf-8")
        )
        descriptions = (
            check_gate_parity_module.__doc__ or "",
            registry["description"],
        )
        for description in descriptions:
            normalized = " ".join(description.split()).lower()
            assert "ordered" in normalized
            assert "bidirectional" in normalized
            assert "allowlist" in normalized
            assert "skip" in normalized

    def test_trigger_inputs_validation_error_states_non_skip_contract(self) -> None:
        """Malformed values report what the misleading legacy name actually means."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["trigger_inputs"] = "not-a-list"
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError) as error:
            _validate_registry(data)
        assert "ordered, bidirectional E2E allowlist partition" in error.value.message
        assert "never controls whether a gate runs" in error.value.message


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
        gate_a["bindings"] = {"make_target": "gate-a", "ci_job": None, "local_ci_stage": 3}
        gate_a["depends_on"] = ["nonexistent-gate"]
        gate_b = dict(_MINIMAL_VALID_GATE)
        gate_b["id"] = "gate-b"
        gate_b["bindings"] = {"make_target": "gate-b", "ci_job": None, "local_ci_stage": 3}
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate_a, gate_b]
        with pytest.raises(SchemaValidationError, match="unknown gate"):
            _validate_registry(data)

    def test_validate_circular_dependency_raises(self) -> None:
        """Mutual dependency between two gates is rejected."""
        gate_a = dict(_MINIMAL_VALID_GATE)
        gate_a["id"] = "gate-a"
        gate_a["bindings"] = {"make_target": "gate-a", "ci_job": None, "local_ci_stage": 3}
        gate_a["depends_on"] = ["gate-b"]
        gate_b = dict(_MINIMAL_VALID_GATE)
        gate_b["id"] = "gate-b"
        gate_b["bindings"] = {"make_target": "gate-b", "ci_job": None, "local_ci_stage": 3}
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
        gate_a["required_contexts"] = ["hosted"]
        gate_a["bindings"] = {
            "make_target": "target-a",
            "ci_job": "shared-job",
            "local_ci_stage": None,
        }
        gate_a["hosted"] = {"order": 1, "display_name": "Gate A", "check_step_name": "Run gate a"}
        gate_b = dict(_MINIMAL_VALID_GATE)
        gate_b["id"] = "gate-b"
        gate_b["required_contexts"] = ["hosted"]
        gate_b["bindings"] = {
            "make_target": "target-b",
            "ci_job": "shared-job",
            "local_ci_stage": None,
        }
        gate_b["hosted"] = {"order": 2, "display_name": "Gate B", "check_step_name": "Run gate b"}
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

    def test_local_context_without_executable_stage_raises(self) -> None:
        """A local-context gate must carry a stage the local runner executes."""
        for stage in (None, 2, 8):
            gate = dict(_MINIMAL_VALID_GATE)
            gate["bindings"] = {
                "make_target": "test-gate",
                "ci_job": None,
                "local_ci_stage": stage,
            }
            data = dict(_MINIMAL_REGISTRY)
            data["gates"] = [gate]
            with pytest.raises(SchemaValidationError, match="outside the executable stages"):
                _validate_registry(data)

    def test_local_context_without_make_target_raises(self) -> None:
        """A local-context gate without a Make target would be silently skipped."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": None, "ci_job": None, "local_ci_stage": 3}
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="no Make target"):
            _validate_registry(data)


class TestRegistryMetadataFields:
    """The registry-owned hosted/publish/help fields are enforced fail-closed."""

    @staticmethod
    def _hosted_gate(**over: Any) -> dict[str, Any]:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["required_contexts"] = ["hosted"]
        gate["bindings"] = {
            "make_target": "test-gate",
            "ci_job": "test-job",
            "local_ci_stage": None,
        }
        gate["hosted"] = {
            "order": 1,
            "display_name": "Test Gate",
            "check_step_name": "Run test gate",
        }
        gate.update(over)
        return gate

    @staticmethod
    def _publish_gate(**over: Any) -> dict[str, Any]:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["required_contexts"] = ["publish"]
        gate["bindings"] = {"make_target": "test-gate", "ci_job": None, "local_ci_stage": None}
        gate["publish"] = {"order": 1, "step_name": "Run test gate"}
        gate.update(over)
        return gate

    @staticmethod
    def _registry_with(gates: list[dict[str, Any]]) -> dict[str, Any]:
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = gates
        return data

    def test_valid_metadata_is_accepted(self) -> None:
        """Hosted, publish, and multi-line help metadata are all valid."""
        assert _validate_registry(self._registry_with([self._hosted_gate()]))
        assert _validate_registry(self._registry_with([self._publish_gate()]))
        helped = dict(_MINIMAL_VALID_GATE)
        helped["help"] = "First line\nSecond line"
        assert _validate_registry(self._registry_with([helped]))

    def test_hosted_context_requires_hosted_metadata(self) -> None:
        """A hosted-context gate without its display metadata cannot be projected."""
        gate = self._hosted_gate()
        gate.pop("hosted")
        with pytest.raises(SchemaValidationError, match="hosted is required"):
            _validate_registry(self._registry_with([gate]))

    def test_hosted_metadata_requires_hosted_context(self) -> None:
        """Hosted metadata without the declared context would never be projected."""
        gate = self._hosted_gate()
        gate["required_contexts"] = ["local-serial"]
        gate["bindings"] = {"make_target": "test-gate", "ci_job": None, "local_ci_stage": 3}
        with pytest.raises(SchemaValidationError, match="requires the hosted context"):
            _validate_registry(self._registry_with([gate]))

    def test_ci_job_requires_hosted_context(self) -> None:
        """A ci_job binding no hosted projection consumes is dead metadata."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {
            "make_target": "test-gate",
            "ci_job": "orphan-job",
            "local_ci_stage": 3,
        }
        with pytest.raises(SchemaValidationError, match="ci_job requires the hosted context"):
            _validate_registry(self._registry_with([gate]))

    def test_hosted_metadata_shape_is_rejected(self) -> None:
        """Missing keys, unknown keys, bad orders, and a bad label all fail closed."""
        missing = self._hosted_gate()
        missing["hosted"] = {"order": 1, "display_name": "Test Gate"}
        with pytest.raises(SchemaValidationError, match="missing required key"):
            _validate_registry(self._registry_with([missing]))

        unknown = self._hosted_gate()
        unknown["hosted"]["extra"] = True
        with pytest.raises(SchemaValidationError, match="unknown key"):
            _validate_registry(self._registry_with([unknown]))

        for order in (0, True, "first"):
            bad_order = self._hosted_gate()
            bad_order["hosted"]["order"] = order
            with pytest.raises(SchemaValidationError, match="positive integer"):
                _validate_registry(self._registry_with([bad_order]))

        multiline = self._hosted_gate()
        multiline["hosted"]["display_name"] = "Two\nLines"
        with pytest.raises(SchemaValidationError, match="single line"):
            _validate_registry(self._registry_with([multiline]))

        bad_history = self._hosted_gate()
        bad_history["hosted"]["full_history"] = "yes"
        with pytest.raises(SchemaValidationError, match="must be a boolean"):
            _validate_registry(self._registry_with([bad_history]))

        null_history = self._hosted_gate()
        null_history["hosted"]["full_history"] = None
        with pytest.raises(SchemaValidationError, match="must be a boolean"):
            _validate_registry(self._registry_with([null_history]))

        null_object = self._hosted_gate()
        null_object["hosted"] = None
        with pytest.raises(SchemaValidationError, match="must be a dict"):
            _validate_registry(self._registry_with([null_object]))

    def test_duplicate_hosted_order_is_rejected(self) -> None:
        """Two hosted gates cannot claim the same execution order."""
        first = self._hosted_gate()
        second = self._hosted_gate(id="second-gate")
        second["bindings"] = {
            "make_target": "check-second",
            "ci_job": "job-second",
            "local_ci_stage": None,
        }
        with pytest.raises(SchemaValidationError, match="already used"):
            _validate_registry(self._registry_with([first, second]))

    def test_publish_context_requires_publish_metadata(self) -> None:
        """A publish-context gate without its step metadata cannot be projected."""
        gate = self._publish_gate()
        gate.pop("publish")
        with pytest.raises(SchemaValidationError, match="publish is required"):
            _validate_registry(self._registry_with([gate]))

    def test_publish_metadata_requires_publish_context(self) -> None:
        """Publish metadata without the declared context would never be projected."""
        gate = self._publish_gate()
        gate["required_contexts"] = ["e2e-trigger"]
        with pytest.raises(SchemaValidationError, match="requires the publish context"):
            _validate_registry(self._registry_with([gate]))

    def test_publish_metadata_shape_is_rejected(self) -> None:
        """Missing keys, unknown keys, and bad orders fail closed."""
        missing = self._publish_gate()
        missing["publish"] = {"order": 1}
        with pytest.raises(SchemaValidationError, match="missing required key"):
            _validate_registry(self._registry_with([missing]))

        unknown = self._publish_gate()
        unknown["publish"]["extra"] = True
        with pytest.raises(SchemaValidationError, match="unknown key"):
            _validate_registry(self._registry_with([unknown]))

        bad_order = self._publish_gate()
        bad_order["publish"]["order"] = False
        with pytest.raises(SchemaValidationError, match="positive integer"):
            _validate_registry(self._registry_with([bad_order]))

        null_prefix = self._publish_gate()
        null_prefix["publish"]["command_prefix"] = None
        with pytest.raises(SchemaValidationError, match="non-empty string"):
            _validate_registry(self._registry_with([null_prefix]))

        null_object = self._publish_gate()
        null_object["publish"] = None
        with pytest.raises(SchemaValidationError, match="must be a dict"):
            _validate_registry(self._registry_with([null_object]))

    def test_duplicate_publish_order_is_rejected(self) -> None:
        """Two publish gates cannot claim the same execution order."""
        first = self._publish_gate()
        second = self._publish_gate(id="second-gate")
        second["bindings"] = {"make_target": "check-second", "ci_job": None, "local_ci_stage": None}
        with pytest.raises(SchemaValidationError, match="already used"):
            _validate_registry(self._registry_with([first, second]))

    def test_help_metadata_must_be_a_trimmed_nonempty_string(self) -> None:
        """An empty, untrimmed, null, or non-string curated comment is rejected."""
        for value in ("", "   ", "trailing space  ", None):
            gate = dict(_MINIMAL_VALID_GATE)
            gate["help"] = value
            with pytest.raises(SchemaValidationError, match="non-empty trimmed string"):
                _validate_registry(self._registry_with([gate]))
        gate = dict(_MINIMAL_VALID_GATE)
        gate["help"] = 42
        with pytest.raises(SchemaValidationError, match="non-empty trimmed string"):
            _validate_registry(self._registry_with([gate]))


class TestLocalAndMakefileHelpMetadata:
    """The local-arm and Makefile-help metadata are enforced fail-closed."""

    @staticmethod
    def _local_gate(**over: Any) -> dict[str, Any]:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["local"] = {
            "order": 1,
            "description": "Running test gate...",
            "success": "✓ Test gate passed",
            "failure_label": "Test Gate",
        }
        gate.update(over)
        return gate

    @staticmethod
    def _makefile_gate(**over: Any) -> dict[str, Any]:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["makefile_help"] = {"order": 1, "text": "make test-gate - Test gate help line"}
        gate.update(over)
        return gate

    @staticmethod
    def _registry_with(gates: list[dict[str, Any]]) -> dict[str, Any]:
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = gates
        return data

    def test_valid_metadata_is_accepted(self) -> None:
        """Local arms and Makefile help lines validate on a local gate."""
        assert _validate_registry(self._registry_with([self._local_gate()]))
        assert _validate_registry(self._registry_with([self._makefile_gate()]))

    def test_metadata_requires_a_string_make_target(self) -> None:
        """Metadata no generated station could address fails closed."""
        for build in (self._local_gate, self._makefile_gate):
            gate = build()
            gate["required_contexts"] = ["e2e-trigger"]
            gate["bindings"] = {"make_target": None, "ci_job": None, "local_ci_stage": None}
            with pytest.raises(SchemaValidationError, match="requires a string make_target"):
                _validate_registry(self._registry_with([gate]))

    def test_metadata_shape_is_rejected(self) -> None:
        """Missing keys, unknown keys, bad orders, and null objects fail closed."""
        missing = self._local_gate()
        missing["local"] = {"order": 1, "description": "Running test gate..."}
        with pytest.raises(SchemaValidationError, match="missing required key"):
            _validate_registry(self._registry_with([missing]))

        unknown = self._makefile_gate()
        unknown["makefile_help"]["extra"] = True
        with pytest.raises(SchemaValidationError, match="unknown key"):
            _validate_registry(self._registry_with([unknown]))

        for order in (0, True, "first"):
            bad_order = self._local_gate()
            bad_order["local"]["order"] = order
            with pytest.raises(SchemaValidationError, match="positive integer"):
                _validate_registry(self._registry_with([bad_order]))

        null_local = self._local_gate()
        null_local["local"] = None
        with pytest.raises(SchemaValidationError, match="must be a dict"):
            _validate_registry(self._registry_with([null_local]))

        null_help = self._makefile_gate()
        null_help["makefile_help"] = None
        with pytest.raises(SchemaValidationError, match="must be a dict"):
            _validate_registry(self._registry_with([null_help]))

    def test_unsafe_text_is_rejected(self) -> None:
        """Emitted text cannot carry newlines or shell metacharacters."""
        for value, pattern in (
            ("two\nlines", "single line"),
            ('quote " inside', "must not contain"),
            ("dollar $ inside", "must not contain"),
            ("backslash \\ inside", "must not contain"),
            ("backtick ` inside", "must not contain"),
            ("  padded", "whitespace-trimmed"),
        ):
            gate = self._local_gate()
            gate["local"]["description"] = value
            with pytest.raises(SchemaValidationError, match=pattern):
                _validate_registry(self._registry_with([gate]))

        trailing = self._makefile_gate()
        trailing["makefile_help"]["text"] = "make test-gate - trailing  "
        with pytest.raises(SchemaValidationError, match="whitespace-trimmed"):
            _validate_registry(self._registry_with([trailing]))

    def test_help_line_must_name_its_own_make_target(self) -> None:
        """A help line naming another target would render a stale station."""
        gate = self._makefile_gate()
        gate["makefile_help"]["text"] = "make some-other-target - Test gate help line"
        with pytest.raises(SchemaValidationError, match="must name its own Make target"):
            _validate_registry(self._registry_with([gate]))

    def test_duplicate_orders_are_rejected(self) -> None:
        """Two local arms or Makefile help lines cannot share a position."""
        first = self._local_gate()
        second = self._local_gate(id="second-gate")
        second["bindings"] = {"make_target": "check-second", "ci_job": None, "local_ci_stage": 3}
        with pytest.raises(SchemaValidationError, match="already used"):
            _validate_registry(self._registry_with([first, second]))

        first = self._makefile_gate()
        second = self._makefile_gate(id="second-gate")
        second["bindings"] = {"make_target": "check-second", "ci_job": None, "local_ci_stage": 3}
        second["makefile_help"]["text"] = "make check-second - Second gate help line"
        with pytest.raises(SchemaValidationError, match="already used"):
            _validate_registry(self._registry_with([first, second]))


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
                        "make_target": f"make-target-{gate_id}",
                        "ci_job": None,
                        "local_ci_stage": 3,
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
# Stream behavior
# =========================================================================


class TestStreamBehavior:
    """Direct CLI stream behavior for exit 0/1/2."""

    def test_exit_zero_has_clean_streams(self) -> None:
        """Exit 0: stdout empty, stderr has the success message, no ERROR."""
        result = _run_checker()
        assert result.returncode == 0, (
            f"Expected exit 0, got {result.returncode}: stderr={result.stderr}"
        )
        assert not result.stdout.strip(), f"Expected empty stdout, got: {result.stdout}"
        assert "All generated gate wiring is current." in result.stderr
        assert "ERROR:" not in result.stderr

    def test_exit_one_prints_unified_diff_without_error_stream(self, tmp_path: Path) -> None:
        """Exit 1: a stale generated file prints its unified diff, no ERROR on stderr."""
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        for gate in data["gates"]:
            if gate["id"] == "check-core-compat":
                gate["make_recipe"] = [
                    *gate["make_recipe"],
                    "$(PYTHON) scripts/check_extra.py",
                ]
                break
        else:  # pragma: no cover - the real registry always carries this gate
            raise AssertionError("check-core-compat gate missing from the registry")
        reg_path = _make_registry_json(data["gates"], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        assert "--- scripts/gates.mk" in result.stdout
        assert "+++ scripts/gates.mk.generated" in result.stdout
        assert "check_extra.py" in result.stdout
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
        assert "All generated gate wiring is current." in result.stdout
        assert "ERROR:" not in result.stdout
        assert "ERROR:" not in result.stderr


class TestDiagnosticContract:
    """Failure diagnostics are one line, on stderr, with empty stdout."""

    def test_multiline_failure_is_one_error_line(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """A multi-line generator failure collapses to one physical ERROR line."""

        def explode(_registry_path: Path) -> list[tuple[str, str, str]]:
            raise ValueError("first line\nsecond line\nthird line")

        monkeypatch.setattr(check_gate_parity_module, "_load_registry", lambda path: [])
        monkeypatch.setattr(check_gate_parity_module, "_generated_drift", explode)
        assert check_gate_parity_module.main([]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        error_lines = [line for line in captured.err.splitlines() if line.startswith("ERROR:")]
        assert len(error_lines) == 1
        assert "first line second line third line" in error_lines[0]


class TestGeneratedWiringCurrency:
    """The checker detects drift in each generated surface and reports it."""

    def test_generated_docs_table_is_current(self) -> None:
        drift, expected = sync_ci_gate_jobs_module.sync_docs_table()
        assert not drift
        text = sync_ci_gate_jobs_module.DEFAULT_DOCS.read_text(encoding="utf-8")
        assert text == expected
        assert text.count(sync_ci_gate_jobs_module.DOCS_TABLE_BEGIN) == 1
        assert text.count(sync_ci_gate_jobs_module.DOCS_TABLE_END) == 1
        assert "| Gate | Make target | Contexts | Local stage | Hosted job |" in text

    def test_docs_stage_change_reports_docs_only_drift(self, tmp_path: Path) -> None:
        """A registry stage edit drifts the docs table and nothing else."""
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        for gate in data["gates"]:
            if gate["id"] == "check-core-compat":
                gate["bindings"]["local_ci_stage"] = 4
                break
        else:  # pragma: no cover - the real registry always carries this gate
            raise AssertionError("check-core-compat gate missing from the registry")
        reg_path = _make_registry_json(data["gates"], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 1
        assert "docs/technical/validation_policy.md" in result.stdout
        assert "scripts/gates.mk" not in result.stdout
        assert "ERROR:" not in result.stderr

    def test_docs_render_is_idempotent(self) -> None:
        gates = sync_ci_gate_jobs_module._parse_registry(DEFAULT_REGISTRY)
        current = sync_ci_gate_jobs_module.DEFAULT_DOCS.read_text(encoding="utf-8")
        once = sync_ci_gate_jobs_module.expected_docs_text(current, gates)
        assert sync_ci_gate_jobs_module.expected_docs_text(once, gates) == once

    def test_docs_missing_or_duplicate_markers_fail_closed(self, tmp_path: Path) -> None:
        gates = sync_ci_gate_jobs_module._parse_registry(DEFAULT_REGISTRY)
        current = sync_ci_gate_jobs_module.DEFAULT_DOCS.read_text(encoding="utf-8")
        missing = current.replace(sync_ci_gate_jobs_module.DOCS_TABLE_BEGIN + "\n", "", 1)
        with pytest.raises(sync_ci_gate_jobs_module.GeneratorError, match="marker pair"):
            sync_ci_gate_jobs_module.expected_docs_text(missing, gates)
        duplicated = current.replace(
            sync_ci_gate_jobs_module.DOCS_TABLE_BEGIN + "\n",
            sync_ci_gate_jobs_module.DOCS_TABLE_BEGIN
            + "\n"
            + sync_ci_gate_jobs_module.DOCS_TABLE_BEGIN
            + "\n",
            1,
        )
        with pytest.raises(sync_ci_gate_jobs_module.GeneratorError, match="marker pair"):
            sync_ci_gate_jobs_module.expected_docs_text(duplicated, gates)

    def test_docs_selector_check_write_and_clean_exit_contract(self, tmp_path: Path) -> None:
        """--docs defaults to check; --write refreshes a stale region; check then passes."""
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        for gate in data["gates"]:
            if gate["id"] == "check-core-compat":
                gate["bindings"]["local_ci_stage"] = 4
                break
        reg_path = _make_registry_json(data["gates"], tmp_path)
        docs_path = (
            Path(tempfile.mkdtemp(prefix=f".pytest-gate-parity-{tmp_path.name}-", dir=REPO_ROOT))
            / "validation_policy.md"
        )
        _REPO_FIXTURE_DIRS.add(docs_path.parent)
        docs_path.write_text(
            sync_ci_gate_jobs_module.DEFAULT_DOCS.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        command = [sys.executable, str(Path(sync_ci_gate_jobs_module.__file__))]
        args = ["--docs", str(docs_path), "--registry", str(reg_path)]
        check = subprocess.run(
            [*command, "--check", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert check.returncode == 1, check.stdout + check.stderr
        assert "docs/technical/validation_policy.md" in check.stdout
        written = subprocess.run(
            [*command, "--write", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert written.returncode == 0, written.stdout + written.stderr
        clean = subprocess.run(
            [*command, "--check", *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert clean.returncode == 0, clean.stdout + clean.stderr

    def test_registry_local_gate_without_stage_is_rejected_before_projection(
        self, tmp_path: Path
    ) -> None:
        """Regeneration cannot certify a local gate the runner would skip."""
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        for gate in data["gates"]:
            if gate["id"] == "check-core-compat":
                gate["bindings"]["local_ci_stage"] = None
                break
        else:  # pragma: no cover - the real registry always carries this gate
            raise AssertionError("check-core-compat gate missing from the registry")
        reg_path = _make_registry_json(data["gates"], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 2
        assert "SCHEMA_ERROR" in result.stderr
        assert "outside the executable stages" in result.stderr

    def test_duplicate_e2e_path_ownership_is_rejected_before_projection(
        self, tmp_path: Path
    ) -> None:
        """Regeneration cannot certify an ambiguous E2E allowlist partition."""
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        owner = next(
            gate
            for gate in data["gates"]
            if gate["id"] == "check-core-compat" and "e2e-trigger" in gate["required_contexts"]
        )
        claimant = next(
            gate
            for gate in data["gates"]
            if gate["id"] == "check-module-core-imports"
            and "e2e-trigger" in gate["required_contexts"]
        )
        claimant["trigger_inputs"] = [*claimant["trigger_inputs"], owner["trigger_inputs"][0]]
        reg_path = _make_registry_json(data["gates"], tmp_path)
        result = _run_checker(["--registry", str(reg_path)])
        assert result.returncode == 2
        assert "claimed by both" in result.stderr


class TestCanonicalPathBoundary:
    """Every accepted source is a canonical regular file in the repository."""

    def test_real_registry_is_accepted(self) -> None:
        registry = REPO_ROOT / "scripts" / "gate_registry.json"
        assert _canonical_input_path(registry, "registry") == registry

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
        assert "All generated gate wiring is current." in result.stderr
        assert "ERROR:" not in result.stderr


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
        assert jobs == _expected_ci_job_ids()
        expected_needs = _registry_generated_needs()
        assert needs["test"] == expected_needs["test"]
        for consumer in ("isolation-conformance", "lint-cli"):
            assert needs[consumer] == expected_needs[consumer]
        assert run_values["module-core-compat"][-1] == "make check-core-compat\n"
        assert expected_workflow_text(workflow_text, registry) == workflow_text

    def test_registry_needs_follow_hosted_order_not_registry_row_order(
        self, tmp_path: Path
    ) -> None:
        """Reordered registry rows cannot move the all-hosted consumer's needs."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"] = list(reversed(registry_data["gates"]))
        registry_path = tmp_path / "reversed-registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        by_hosted_order = sorted(
            (gate for gate in registry_data["gates"] if "hosted" in gate["required_contexts"]),
            key=lambda gate: gate["hosted"]["order"],
        )
        expected = sync_ci_gate_jobs_module.FIXED_NEEDS + tuple(
            gate["bindings"]["ci_job"] for gate in by_hosted_order
        )
        assert _registry_generated_needs(registry_path)["test"] == expected
        # The generator renders that same order for the reordered rows.
        generated = expected_workflow_text(
            DEFAULT_WORKFLOW.read_text(encoding="utf-8"), _parse_registry(registry_path)
        )
        expected_needs_line = (
            f"    needs: [{', '.join(_registry_generated_needs(registry_path)['test'])}]"
        )
        assert expected_needs_line in generated

    def test_generation_is_idempotent(self) -> None:
        """A generated workflow is stable under a second generation pass."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        generated = expected_workflow_text(workflow_text, registry)
        assert expected_workflow_text(generated, registry) == generated
        assert self._projection(generated) == self._projection(workflow_text)

    def test_stale_action_pin_is_projected_by_generation(self) -> None:
        """A pin one release behind the pinned refs is regenerated, not rejected."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        marker = workflow_text.index(JOB_BEGIN)
        stale = workflow_text[:marker] + workflow_text[marker:].replace(
            CHECKOUT_REF, f"actions/checkout@{'0' * 40}", 1
        )
        assert stale != workflow_text
        assert expected_workflow_text(stale, registry) == workflow_text

    def test_different_action_identity_still_fails_closed(self) -> None:
        """Pre-edit projection tolerates a stale SHA, never a different action."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        marker = workflow_text.index(JOB_BEGIN)
        wrong = workflow_text[:marker] + workflow_text[marker:].replace(
            CHECKOUT_REF, f"actions/cache@{'1' * 40}", 1
        )
        with pytest.raises(GeneratorError, match="action versions/ordering drifted"):
            expected_workflow_text(wrong, registry)

    def test_changed_step_shape_still_fails_closed(self) -> None:
        """A stale ref is tolerated pre-edit; a changed step shape is not."""
        workflow_text = DEFAULT_WORKFLOW.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        changed = workflow_text.replace("        fetch-depth: 0\n", "", 1)
        assert changed != workflow_text
        with pytest.raises(GeneratorError, match="checkout step drifted"):
            expected_workflow_text(changed, registry)

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

    def test_dropped_hosted_registry_gate_fails_closed(self, tmp_path: Path) -> None:
        """A hosted gate dropped from the registry leaves an unowned workflow job."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        registry_data["gates"] = registry_data["gates"][:4] + registry_data["gates"][5:]
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        with pytest.raises(GeneratorError, match="unsupported hosted job set"):
            expected_workflow_text(
                DEFAULT_WORKFLOW.read_text(encoding="utf-8"), _parse_registry(registry_path)
            )

    def test_registry_make_target_propagates_to_hosted_job(self, tmp_path: Path) -> None:
        """A registry target edit propagates only to its owned hosted run value."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        _rename_make_target(registry_data, "check-core-compat", "check-core-compat-renamed")
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
        expected_needs_line = (
            f"    needs: [{', '.join(_registry_generated_needs(registry_path)['test'])}]"
        )
        assert expected_needs_line in generated
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
        expected_needs_line = (
            f"    needs: [{', '.join(_registry_generated_needs(registry_path)['test'])}]"
        )
        assert expected_needs_line in generated
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
        expected_needs_line = (
            f"    needs: [{', '.join(_registry_generated_needs(registry_path)['test'])}]"
        )
        assert expected_needs_line in written

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
        _rename_make_target(registry_data, "check-core-compat", "check-core-compat-renamed")
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
            f"    needs: [{', '.join(_registry_generated_needs()['isolation-conformance'])}]\n"
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
        _rename_make_target(registry_data, "check-core-compat", "check-core-compat-renamed")
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
                        "make_target": f"make-target-{gate_id}",
                        "ci_job": None,
                        "local_ci_stage": 3,
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


class TestE2eWorkflowGeneration:
    """The E2E allowlist is projected from registry order and owned markers."""

    def test_duplicate_e2e_path_ownership_fails_closed(self) -> None:
        """Two gates may not claim the same E2E trigger path."""
        gate_a = {
            "id": "gate-a",
            "description": "First owner",
            "required_contexts": ["e2e-trigger"],
            "bindings": {"make_target": "gate-a", "ci_job": None, "local_ci_stage": None},
            "depends_on": [],
            "trigger_inputs": ["shared/path/**"],
        }
        gate_b = {
            "id": "gate-b",
            "description": "Second owner",
            "required_contexts": ["e2e-trigger"],
            "bindings": {"make_target": "gate-b", "ci_job": None, "local_ci_stage": None},
            "depends_on": [],
            "trigger_inputs": ["shared/path/**"],
        }
        with pytest.raises(GeneratorError, match="claimed by both"):
            sync_ci_gate_jobs_module._expected_e2e_paths([gate_a, gate_b])

    def test_installed_wheel_trigger_slice_is_exact_and_unique(self) -> None:
        """Generated E2E YAML retains the installed-wheel trigger slice exactly once."""
        expected = [
            "quickscale_cli/tests/test_e2e_installed_wheel_lifecycle.py",
            "scripts/smoke_install.sh",
            "scripts/_installed_wheel_venv.sh",
            "scripts/build_core_wheel.sh",
            "scripts/provision_installed_venv.sh",
            "scripts/_python_requirement.sh",
        ]
        workflow = yaml.load(E2E_YML.read_text(encoding="utf-8"), Loader=yaml.BaseLoader)
        paths = workflow["on"]["pull_request"]["paths"]
        anchor = paths.index("scripts/test_e2e_parallel.py")

        assert paths[anchor + 1 : anchor + 1 + len(expected)] == expected
        for path in expected:
            assert paths.count(path) == 1

    def test_markerless_exact_paths_check_write_and_clean_exit_contract(
        self, tmp_path: Path
    ) -> None:
        """Marker ownership drift is reported even when the path values match."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        markerless = DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8")
        for marker in (E2E_PATHS_BEGIN, E2E_PATHS_END):
            markerless = markerless.replace(marker + "\n", "", 1)
        workflow_path = tmp_path / "e2e.yml"
        workflow_path.write_text(markerless, encoding="utf-8")

        drift, expected = sync_ci_gate_jobs_module.sync_e2e_workflow(
            workflow_path, DEFAULT_REGISTRY
        )
        assert drift
        assert expected != markerless

        command = [sys.executable, str(Path(sync_ci_gate_jobs_module.__file__))]
        args = ["--e2e-workflow", str(workflow_path), "--registry", str(DEFAULT_REGISTRY)]
        check = subprocess.run(
            [*command, "--check", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert check.returncode == 1, check.stderr
        assert E2E_PATHS_BEGIN in check.stdout
        assert E2E_PATHS_END in check.stdout

        write = subprocess.run(
            [*command, "--write", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert write.returncode == 0, write.stderr
        written = workflow_path.read_text(encoding="utf-8")
        assert written.count(E2E_PATHS_BEGIN) == 1
        assert written.count(E2E_PATHS_END) == 1
        assert expected_e2e_workflow_text(written, registry) == written

        clean = subprocess.run(
            [*command, "--check", *args],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert clean.returncode == 0, clean.stderr

    def test_markerless_bootstrap_and_idempotence(self) -> None:
        registry = _parse_registry(DEFAULT_REGISTRY)
        current = DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8")
        generated = expected_e2e_workflow_text(current, registry)
        assert E2E_PATHS_BEGIN in generated
        assert E2E_PATHS_END in generated
        assert expected_e2e_workflow_text(generated, registry) == generated

    def test_registry_append_is_at_declared_position(self, tmp_path: Path) -> None:
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        data["gates"].insert(
            1,
            {
                "id": "inserted-e2e-gate",
                "description": "Inserted E2E gate",
                "required_contexts": ["e2e-trigger"],
                "bindings": {
                    "make_target": "inserted-e2e-gate",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "depends_on": [],
                "trigger_inputs": ["inserted/path/**"],
            },
        )
        path = tmp_path / "registry.json"
        path.write_text(json.dumps(data), encoding="utf-8")
        gates = _parse_registry(path)
        generated = expected_e2e_workflow_text(
            DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8"), gates
        )
        owned = generated.split(E2E_PATHS_BEGIN + "\n", 1)[1].split(E2E_PATHS_END + "\n", 1)[0]
        paths = [line.strip()[3:-1] for line in owned.splitlines() if line.startswith("      - '")]
        expected = list(_expected_e2e_paths(gates))
        assert paths == expected
        assert paths[1] == "inserted/path/**"

    @pytest.mark.parametrize(
        "mutation,match",
        [
            (lambda text: text.replace(E2E_PATHS_BEGIN + "\n", "", 1), "marker"),
            (
                lambda text: text.replace(
                    E2E_PATHS_END + "\n", E2E_PATHS_END + "\n" + E2E_PATHS_END + "\n", 1
                ),
                "marker",
            ),
            (lambda text: text.replace(E2E_PATHS_BEGIN + "\n", E2E_PATHS_END + "\n", 1), "marker"),
        ],
    )
    def test_malformed_marker_ownership_fails_closed(self, mutation: Any, match: str) -> None:
        registry = _parse_registry(DEFAULT_REGISTRY)
        valid = expected_e2e_workflow_text(
            DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8"), registry
        )
        with pytest.raises(GeneratorError, match=match):
            expected_e2e_workflow_text(mutation(valid), registry)

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda text: text.replace(E2E_PATHS_BEGIN + "\n", "", 1),
            lambda text: text.replace(
                E2E_PATHS_END + "\n", E2E_PATHS_END + "\n" + E2E_PATHS_END + "\n", 1
            ),
            lambda text: text.replace(
                "      - 'quickscale_modules/backups/**'\n",
                E2E_PATHS_BEGIN + "\n      - 'quickscale_modules/backups/**'\n",
                1,
            ),
        ],
    )
    def test_malformed_marker_cli_exits_two(self, tmp_path: Path, mutation: Any) -> None:
        """Partial, duplicate, and nested markers remain exit-2 input errors."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        valid = expected_e2e_workflow_text(
            DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8"), registry
        )
        workflow_path = tmp_path / "malformed-e2e.yml"
        workflow_path.write_text(mutation(valid), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(sync_ci_gate_jobs_module.__file__)),
                "--check",
                "--e2e-workflow",
                str(workflow_path),
                "--registry",
                str(DEFAULT_REGISTRY),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 2
        assert "ERROR: [CI_GATE_GENERATION]" in result.stderr
        assert not result.stdout

    def test_duplicate_yaml_key_fails_closed(self) -> None:
        registry = _parse_registry(DEFAULT_REGISTRY)
        malformed = DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8").replace(
            "name: E2E Tests\n", "name: E2E Tests\nname: Duplicate\n", 1
        )
        with pytest.raises(GeneratorError, match="Duplicate YAML key"):
            expected_e2e_workflow_text(malformed, registry)

    def test_unowned_bytes_are_preserved(self) -> None:
        registry = _parse_registry(DEFAULT_REGISTRY)
        current = DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8").replace(
            "name: E2E Tests\n", "name: E2E Tests\n# unowned sentinel\n", 1
        )
        generated = expected_e2e_workflow_text(current, registry)
        for marker in (E2E_PATHS_BEGIN, E2E_PATHS_END):
            current = current.replace(marker + "\n", "", 1)
            generated = generated.replace(marker + "\n", "", 1)
        assert generated.split("    paths:\n", 1)[0] == current.split("    paths:\n", 1)[0]
        assert "# unowned sentinel\n" in generated
        assert "  e2e-tests:\n" in generated

    def test_partial_and_nested_markers_fail_closed(self) -> None:
        registry = _parse_registry(DEFAULT_REGISTRY)
        valid = expected_e2e_workflow_text(
            DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8"), registry
        )
        nested = valid.replace(
            "      - 'quickscale_modules/backups/**'\n",
            E2E_PATHS_BEGIN + "\n      - 'quickscale_modules/backups/**'\n",
            1,
        )
        with pytest.raises(GeneratorError, match="marker"):
            expected_e2e_workflow_text(nested, registry)

    def test_selector_truth_table_is_hermetic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[tuple[str, Path]] = []

        def fake_registry(_path: Path) -> list[dict[str, Any]]:
            return []

        def fake_hosted(path: Path, _registry: Path) -> tuple[bool, str]:
            calls.append(("hosted", path))
            return False, ""

        def fake_e2e(path: Path, _registry: Path) -> tuple[bool, str]:
            calls.append(("e2e", path))
            return False, ""

        def fake_make_include(path: Path, _registry: Path) -> tuple[bool, str]:
            calls.append(("make", path))
            return False, ""

        def fake_publish(path: Path, _registry: Path) -> tuple[bool, str]:
            calls.append(("publish", path))
            return False, ""

        def fake_docs(path: Path, _registry: Path) -> tuple[bool, str]:
            calls.append(("docs", path))
            return False, ""

        def fake_local(path: Path, _registry: Path) -> tuple[bool, str]:
            calls.append(("local", path))
            return False, ""

        def fake_makefile(path: Path, _registry: Path) -> tuple[bool, str]:
            calls.append(("makefile", path))
            return False, ""

        monkeypatch.setattr(sync_ci_gate_jobs_module, "_parse_registry", fake_registry)
        monkeypatch.setattr(sync_ci_gate_jobs_module, "sync_workflow", fake_hosted)
        monkeypatch.setattr(sync_ci_gate_jobs_module, "sync_e2e_workflow", fake_e2e)
        monkeypatch.setattr(sync_ci_gate_jobs_module, "sync_make_include", fake_make_include)
        monkeypatch.setattr(sync_ci_gate_jobs_module, "sync_publish_workflow", fake_publish)
        monkeypatch.setattr(sync_ci_gate_jobs_module, "sync_docs_table", fake_docs)
        monkeypatch.setattr(sync_ci_gate_jobs_module, "sync_local_arms", fake_local)
        monkeypatch.setattr(sync_ci_gate_jobs_module, "sync_makefile_help", fake_makefile)
        assert sync_ci_gate_jobs_module.main(["--check", "--e2e-workflow", "custom-e2e.yml"]) == 0
        assert calls == [("e2e", Path("custom-e2e.yml"))]
        calls.clear()
        assert sync_ci_gate_jobs_module.main(["--check", "--workflow", "custom-ci.yml"]) == 0
        assert calls == [("hosted", Path("custom-ci.yml"))]
        calls.clear()
        assert sync_ci_gate_jobs_module.main(["--check", "--make-include", "custom-gates.mk"]) == 0
        assert calls == [("make", Path("custom-gates.mk"))]
        calls.clear()
        assert sync_ci_gate_jobs_module.main(["--check", "--docs", "custom-policy.md"]) == 0
        assert calls == [("docs", Path("custom-policy.md"))]
        calls.clear()
        assert (
            sync_ci_gate_jobs_module.main(["--check", "--publish-workflow", "custom-publish.yml"])
            == 0
        )
        assert calls == [("publish", Path("custom-publish.yml"))]
        calls.clear()
        assert sync_ci_gate_jobs_module.main(["--check", "--local-script", "custom-ci.sh"]) == 0
        assert calls == [("local", Path("custom-ci.sh"))]
        calls.clear()
        assert sync_ci_gate_jobs_module.main(["--check", "--makefile", "custom-Makefile"]) == 0
        assert calls == [("makefile", Path("custom-Makefile"))]
        calls.clear()
        assert (
            sync_ci_gate_jobs_module.main(
                ["--check", "--workflow", "custom-ci.yml", "--e2e-workflow", "custom-e2e.yml"]
            )
            == 0
        )
        assert calls == [("hosted", Path("custom-ci.yml")), ("e2e", Path("custom-e2e.yml"))]
        calls.clear()
        assert sync_ci_gate_jobs_module.main(["--check"]) == 0
        assert calls == [
            ("hosted", DEFAULT_WORKFLOW),
            ("e2e", DEFAULT_E2E_WORKFLOW),
            ("publish", DEFAULT_PUBLISH_WORKFLOW),
            ("make", DEFAULT_MAKE_INCLUDE),
            ("docs", sync_ci_gate_jobs_module.DEFAULT_DOCS),
            ("local", sync_ci_gate_jobs_module.DEFAULT_LOCAL_SCRIPT),
            ("makefile", sync_ci_gate_jobs_module.DEFAULT_MAKEFILE),
        ]


# =========================================================================
# SA259 — generated Makefile gate targets
# =========================================================================


class TestMakeIncludeGeneration:
    """The generated Makefile include is projected from the registry."""

    @staticmethod
    def _generated_pairs() -> list[tuple[str, str, tuple[str, ...], str]]:
        return sync_ci_gate_jobs_module._generated_make_targets(_parse_registry(DEFAULT_REGISTRY))

    def test_real_include_is_current_and_complete(self) -> None:
        """The committed include matches the renderer and names every target."""
        drift, expected = sync_ci_gate_jobs_module.sync_make_include(
            DEFAULT_MAKE_INCLUDE, DEFAULT_REGISTRY
        )
        assert drift is False
        assert expected == DEFAULT_MAKE_INCLUDE.read_text(encoding="utf-8")
        generated_targets = [target for _, target, _, _ in self._generated_pairs()]
        registry = _parse_registry(DEFAULT_REGISTRY)
        hand_owned_targets = {
            gate["bindings"]["make_target"]
            for gate in registry
            if gate["id"] in HAND_OWNED_MAKE_TARGETS
        }
        assert generated_targets
        assert hand_owned_targets
        assert not hand_owned_targets & set(generated_targets)
        for target in generated_targets:
            assert f"\n{target}:\n" in expected
        for target in hand_owned_targets:
            assert f"\n{target}:\n" not in expected
        assert f".PHONY: {' '.join(generated_targets)}\n" in expected

    def test_help_metadata_is_the_include_comment_with_description_fallback(self) -> None:
        """Curated comments live on their registry gates; a gate without one falls back."""
        gates = _parse_registry(DEFAULT_REGISTRY)
        include = sync_ci_gate_jobs_module._render_make_include(gates)
        helped = [gate for gate in gates if "help" in gate]
        fallback = [
            gate
            for gate in gates
            if "help" not in gate
            and gate.get("make_recipe")
            and gate["id"] not in HAND_OWNED_MAKE_TARGETS
        ]
        assert helped and fallback
        for gate in helped:
            comment = "\n".join(f"# {line}" for line in gate["help"].splitlines())
            assert comment in include, gate["id"]
        for gate in fallback:
            comment = "\n".join(f"# {line}" for line in gate["description"].splitlines())
            assert comment in include, gate["id"]

    def test_makefile_defines_no_generated_recipe(self) -> None:
        """The Makefile includes the fragment instead of holding the recipes."""
        makefile_text = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")
        assert "include $(MAKEFILE_ROOT)scripts/gates.mk" in makefile_text
        for _, target, _, _ in self._generated_pairs():
            assert f"{target}:" not in makefile_text

    def test_default_goal_stays_help_after_include(self) -> None:
        """Bare make prints help; the include's first target is not the goal."""
        result = subprocess.run(
            ["make", "-n"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert "QuickScale Development Commands" in result.stdout
        assert "check_module_core_compatibility" not in result.stdout

    def test_gate_with_target_but_no_recipe_fails_closed(self) -> None:
        """A new gate cannot ship without a recipe or an explicit exemption."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": "check-unowned", "ci_job": None, "local_ci_stage": None}
        with pytest.raises(GeneratorError, match="no make_recipe"):
            sync_ci_gate_jobs_module._generated_make_targets([gate])

    def test_hand_owned_gate_with_recipe_fails_closed(self) -> None:
        """A hand-owned exemption and a recipe on one gate contradict each other."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["id"] = "check-gate-suites"
        gate["make_recipe"] = ["@echo gate"]
        with pytest.raises(GeneratorError, match="both a make_recipe and a hand-owned"):
            sync_ci_gate_jobs_module._generated_make_targets([gate])

    def test_stale_hand_owned_exemption_fails_closed(self) -> None:
        """An exemption naming a removed gate is a generation error."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["make_recipe"] = ["@echo gate"]
        with pytest.raises(GeneratorError, match="unknown gate"):
            sync_ci_gate_jobs_module._generated_make_targets([gate])

    def test_recipe_without_make_target_fails_closed(self) -> None:
        """A recipe with no target to attach it to is rejected."""
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": None, "ci_job": None, "local_ci_stage": None}
        gate["make_recipe"] = ["@echo gate"]
        with pytest.raises(GeneratorError, match="requires a string make_target"):
            sync_ci_gate_jobs_module._generated_make_targets([gate])

    def test_schema_rejects_non_list_recipe(self) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["make_recipe"] = "@echo gate"
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="must be a list"):
            _validate_registry(data)

    def test_schema_rejects_empty_recipe(self) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["make_recipe"] = []
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="non-empty"):
            _validate_registry(data)

    def test_schema_rejects_non_string_recipe_line(self) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["make_recipe"] = [42]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="non-empty string"):
            _validate_registry(data)

    def test_schema_rejects_untrimmed_recipe_line(self) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["make_recipe"] = [" @echo gate "]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="whitespace-trimmed"):
            _validate_registry(data)

    def test_schema_rejects_recipe_without_make_target(self) -> None:
        gate = dict(_MINIMAL_VALID_GATE)
        gate["bindings"] = {"make_target": None, "ci_job": None, "local_ci_stage": None}
        gate["make_recipe"] = ["@echo gate"]
        data = dict(_MINIMAL_REGISTRY)
        data["gates"] = [gate]
        with pytest.raises(SchemaValidationError, match="requires a string make_target"):
            _validate_registry(data)

    def test_schema_accepts_missing_recipe(self) -> None:
        """A gate without make_recipe is valid; its recipe stays hand-written."""
        gates = _validate_registry(dict(_MINIMAL_REGISTRY))
        assert "make_recipe" not in gates[0]

    def test_cli_reports_writes_and_cleans_include_drift(self, tmp_path: Path) -> None:
        """Drift is reported, written, and then checks clean through the CLI."""
        expected = sync_ci_gate_jobs_module._render_make_include(_parse_registry(DEFAULT_REGISTRY))
        include_path = tmp_path / "gates.mk"
        include_path.write_text(
            expected.replace("check-core-compat:", "check-core-compat-broken:", 1),
            encoding="utf-8",
        )
        command = [sys.executable, str(Path(sync_ci_gate_jobs_module.__file__))]
        args = ["--make-include", str(include_path), "--registry", str(DEFAULT_REGISTRY)]

        check = subprocess.run(
            [*command, "--check", *args], capture_output=True, text=True, timeout=30
        )
        assert check.returncode == 1, check.stderr
        assert "check-core-compat-broken" in check.stdout

        write = subprocess.run(
            [*command, "--write", *args], capture_output=True, text=True, timeout=30
        )
        assert write.returncode == 0, write.stderr
        assert include_path.read_text(encoding="utf-8") == expected

        clean = subprocess.run(
            [*command, "--check", *args], capture_output=True, text=True, timeout=30
        )
        assert clean.returncode == 0, clean.stderr

    def test_write_creates_missing_include(self, tmp_path: Path) -> None:
        """A checkout without the fragment can bootstrap it with --write."""
        include_path = tmp_path / "new-gates.mk"
        result = subprocess.run(
            [
                sys.executable,
                str(Path(sync_ci_gate_jobs_module.__file__)),
                "--write",
                "--make-include",
                str(include_path),
                "--registry",
                str(DEFAULT_REGISTRY),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, result.stderr
        expected = sync_ci_gate_jobs_module._render_make_include(_parse_registry(DEFAULT_REGISTRY))
        assert include_path.read_text(encoding="utf-8") == expected

    def test_mandatory_check_plans_include_drift_gate(
        self, make_check_plan: subprocess.CompletedProcess
    ) -> None:
        """The make check recipe runs the direct generation gate over the include."""
        result = make_check_plan
        assert result.returncode == 0, result.stderr
        assert "scripts/sync_ci_gate_jobs.py --check" in result.stdout


# =========================================================================
# SA275b — generated local-CI arms and Makefile gate help
# =========================================================================


class TestLocalArmGeneration:
    """The local runner's display arms are projected from the registry."""

    def test_real_arm_region_is_current(self) -> None:
        """The committed local-CI script matches the arm renderer."""
        drift, expected = sync_ci_gate_jobs_module.sync_local_arms(
            DEFAULT_LOCAL_SCRIPT, DEFAULT_REGISTRY
        )
        assert drift is False
        assert expected == DEFAULT_LOCAL_SCRIPT.read_text(encoding="utf-8")

    def test_every_arm_projects_its_registry_row(self) -> None:
        """Each gate carrying local metadata renders its exact arm lines."""
        gates = _parse_registry(DEFAULT_REGISTRY)
        rendered = sync_ci_gate_jobs_module.expected_local_arms_text(
            DEFAULT_LOCAL_SCRIPT.read_text(encoding="utf-8"), gates
        )
        displayed = [gate for gate in gates if "local" in gate]
        assert displayed
        generated_arms = rendered.split(LOCAL_ARMS_BEGIN + "\n", 1)[1].split(
            LOCAL_ARMS_END + "\n", 1
        )[0]
        assert generated_arms.count("LOCAL_GATE_DESCRIPTION=") == len(displayed)
        for gate in displayed:
            metadata = gate["local"]
            assert f"        {gate['bindings']['make_target']})\n" in rendered
            assert f'            LOCAL_GATE_DESCRIPTION="{metadata["description"]}"\n' in rendered
            assert f'            LOCAL_GATE_SUCCESS="{metadata["success"]}"\n' in rendered
            assert (
                f'            LOCAL_GATE_FAILURE_LABEL="{metadata["failure_label"]}"\n' in rendered
            )

    def test_gate_without_local_metadata_keeps_the_generic_fallback(self) -> None:
        """A gate without local metadata stays addressable through the fallback arm."""
        gates = _parse_registry(DEFAULT_REGISTRY)
        fallback = [
            gate for gate in gates if "local" not in gate and gate["bindings"].get("make_target")
        ]
        assert fallback
        rendered = sync_ci_gate_jobs_module.expected_local_arms_text(
            DEFAULT_LOCAL_SCRIPT.read_text(encoding="utf-8"), gates
        )
        generated_arms = rendered.split(LOCAL_ARMS_BEGIN + "\n", 1)[1].split(
            LOCAL_ARMS_END + "\n", 1
        )[0]
        for gate in fallback:
            assert f"        {gate['bindings']['make_target']})\n" not in generated_arms
        assert '            LOCAL_GATE_DESCRIPTION="Running $target..."\n' in rendered

    def test_malformed_arm_markers_fail_closed(self) -> None:
        """Missing pairs and markers outside the describe case are invalid input."""
        current = DEFAULT_LOCAL_SCRIPT.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        partial = current.replace(LOCAL_ARMS_BEGIN + "\n", "", 1)
        with pytest.raises(GeneratorError, match="incomplete or duplicated"):
            sync_ci_gate_jobs_module.expected_local_arms_text(partial, registry)
        relocated = current.replace(LOCAL_ARMS_BEGIN + "\n", "", 1)
        relocated = relocated.replace(
            '    case "$target" in\n', LOCAL_ARMS_BEGIN + '\n    case "$target" in\n', 1
        )
        with pytest.raises(GeneratorError, match="not owned by the describe case"):
            sync_ci_gate_jobs_module.expected_local_arms_text(relocated, registry)


class TestMakefileHelpGeneration:
    """The Makefile's gate-help region is projected from the registry."""

    def test_real_makefile_help_is_current(self) -> None:
        """The committed Makefile matches the help renderer."""
        drift, expected = sync_ci_gate_jobs_module.sync_makefile_help(
            DEFAULT_MAKEFILE, DEFAULT_REGISTRY
        )
        assert drift is False
        assert expected == DEFAULT_MAKEFILE.read_text(encoding="utf-8")

    def test_every_help_line_projects_its_registry_row(self) -> None:
        """Each gate carrying help metadata renders its exact line, in order."""
        gates = _parse_registry(DEFAULT_REGISTRY)
        rendered = sync_ci_gate_jobs_module.expected_makefile_help_text(
            DEFAULT_MAKEFILE.read_text(encoding="utf-8"), gates
        )
        helped = [gate for gate in gates if "makefile_help" in gate]
        assert helped
        orders = sorted(gate["makefile_help"]["order"] for gate in helped)
        assert orders == list(range(1, len(helped) + 1))
        positions = []
        ordered = sorted(helped, key=lambda gate: gate["makefile_help"]["order"])
        for gate in ordered:
            line = f'\t@echo "  {gate["makefile_help"]["text"]}"\n'
            assert line in rendered
            positions.append(rendered.index(line))
        assert positions == sorted(positions)

    def test_help_recipe_emits_no_generated_markers(self) -> None:
        """The silenced marker lines never leak into ordinary `make help` output."""
        result = subprocess.run(
            ["make", "help"],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        assert "GENERATED" not in result.stdout
        assert "make check-core-compat" in result.stdout

    def test_malformed_help_markers_fail_closed(self) -> None:
        """Missing pairs and markers outside the help recipe are invalid input."""
        current = DEFAULT_MAKEFILE.read_text(encoding="utf-8")
        registry = _parse_registry(DEFAULT_REGISTRY)
        partial = current.replace(MAKEFILE_HELP_END + "\n", "", 1)
        with pytest.raises(GeneratorError, match="incomplete or duplicated"):
            sync_ci_gate_jobs_module.expected_makefile_help_text(partial, registry)
        relocated = current.replace(MAKEFILE_HELP_BEGIN + "\n", "", 1)
        relocated = relocated.replace("help:\n", MAKEFILE_HELP_BEGIN + "\nhelp:\n", 1)
        with pytest.raises(GeneratorError, match="not owned by the help recipe"):
            sync_ci_gate_jobs_module.expected_makefile_help_text(relocated, registry)


class TestOneStationFixtureProjection:
    """A fixture gate added to the registry alone reaches every generated station."""

    @staticmethod
    def _fixture_gates() -> tuple[list[dict[str, Any]], dict[str, Any]]:
        gates: list[dict[str, Any]] = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))[
            "gates"
        ]

        def next_order(key: str) -> int:
            return 1 + max((gate[key]["order"] for gate in gates if key in gate), default=0)

        fixture = {
            "id": "check-fixture-gate",
            "description": "One-station fixture gate",
            "required_contexts": [
                "local-serial",
                "local-parallel",
                "hosted",
                "publish",
                "e2e-trigger",
            ],
            "bindings": {
                "make_target": "check-fixture-gate",
                "ci_job": "fixture-gate",
                "local_ci_stage": 7,
            },
            "hosted": {
                "order": next_order("hosted"),
                "display_name": "Fixture Gate",
                "check_step_name": "Run fixture gate",
            },
            "publish": {"order": next_order("publish"), "step_name": "Run fixture gate step"},
            "help": "Fixture gate comment",
            "local": {
                "order": next_order("local"),
                "description": "Running fixture gate...",
                "success": "✓ Fixture gate passed",
                "failure_label": "Fixture Gate",
            },
            "makefile_help": {
                "order": next_order("makefile_help"),
                "text": "make check-fixture-gate - Fixture gate help line",
            },
            "make_recipe": ["@$(PYTHON) scripts/check_fixture_gate.py"],
            "depends_on": [],
            "trigger_inputs": ["scripts/check_fixture_gate.py"],
        }
        gates.append(fixture)
        return gates, fixture

    def test_fixture_gate_projects_into_every_generated_station(self) -> None:
        """
        One registry row projects into every generated station.

        The row is the only hand station a gate costs: the hosted job and the
        consumer needs, the E2E allowlist, the publish step, the generated Make
        include, the docs table, the local runner's display arm, and the
        Makefile help line all render from it.
        """
        gates, fixture = self._fixture_gates()
        target = fixture["bindings"]["make_target"]

        workflow = expected_workflow_text(DEFAULT_WORKFLOW.read_text(encoding="utf-8"), gates)
        assert "  fixture-gate:\n" in workflow
        assert "name: Fixture Gate\n" in workflow
        assert f"make {target}\n" in workflow
        parsed = _parse_workflow(workflow, "fixture ci.yml")
        assert "fixture-gate" in parsed["jobs"]["test"]["needs"]

        e2e = expected_e2e_workflow_text(DEFAULT_E2E_WORKFLOW.read_text(encoding="utf-8"), gates)
        assert "      - 'scripts/check_fixture_gate.py'\n" in e2e

        publish = expected_publish_workflow_text(
            DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8"), gates
        )
        assert "      - name: Run fixture gate step\n" in publish
        assert f"make {target}\n" in publish

        include = sync_ci_gate_jobs_module._render_make_include(gates)
        assert f"\n{target}:\n" in include
        assert "# Fixture gate comment\n" in include

        docs = expected_docs_text(DEFAULT_DOCS.read_text(encoding="utf-8"), gates)
        assert f"| `{fixture['id']}` | `make {target}` |" in docs

        arms = sync_ci_gate_jobs_module.expected_local_arms_text(
            DEFAULT_LOCAL_SCRIPT.read_text(encoding="utf-8"), gates
        )
        assert f"        {target})\n" in arms
        assert '            LOCAL_GATE_DESCRIPTION="Running fixture gate..."\n' in arms

        help_text = sync_ci_gate_jobs_module.expected_makefile_help_text(
            DEFAULT_MAKEFILE.read_text(encoding="utf-8"), gates
        )
        assert f"  make {target} - Fixture gate help line" in help_text

    def test_fixture_registry_passes_schema_validation(self) -> None:
        """The fixture row is self-sufficient: no station needs a companion edit."""
        gates, _fixture = self._fixture_gates()
        assert _validate_registry(
            {
                "schema_version": 1,
                "description": "fixture registry",
                "contexts": {
                    name: f"{name} context"
                    for name in (
                        "local-serial",
                        "local-parallel",
                        "hosted",
                        "publish",
                        "e2e-trigger",
                    )
                },
                "gates": gates,
            }
        )


# =========================================================================
# SA259 — generated publish workflow gate steps
# =========================================================================


class TestPublishWorkflowGeneration:
    """The publish gate-step region is projected from the registry."""

    def test_real_publish_workflow_is_current(self) -> None:
        """The committed publish workflow matches the renderer."""
        drift, expected = sync_ci_gate_jobs_module.sync_publish_workflow(
            DEFAULT_PUBLISH_WORKFLOW, DEFAULT_REGISTRY
        )
        assert drift is False
        assert expected == DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")

    def test_generation_is_idempotent_and_names_every_publish_gate(self) -> None:
        """A generated workflow is stable and carries one step per publish gate in order."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        generated = expected_publish_workflow_text(current, registry)
        assert expected_publish_workflow_text(generated, registry) == generated
        assert generated.count(PUBLISH_BEGIN) == 1
        assert generated.count(PUBLISH_END) == 1
        workflow = _parse_workflow(generated, "fixture publish.yml")
        steps = workflow["jobs"]["test"]["steps"]
        names = [step.get("name") for step in steps if isinstance(step, dict)]
        publish_gates = sorted(
            (gate for gate in registry if "publish" in gate["required_contexts"]),
            key=lambda gate: gate["publish"]["order"],
        )
        expected_names = [gate["publish"]["step_name"] for gate in publish_gates]
        for name in expected_names:
            assert names.count(name) == 1, f"expected exactly one {name!r} step"
        assert [name for name in names if name in set(expected_names)] == expected_names

    def test_registry_make_target_edit_projects_into_publish_region(self, tmp_path: Path) -> None:
        """A registry target edit propagates into its owned publish step."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        _rename_make_target(registry_data, "check-core-compat", "check-core-compat-renamed")
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        gates = _parse_registry(registry_path)
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")

        generated = expected_publish_workflow_text(current, gates)

        assert "make check-core-compat-renamed\n" in generated
        assert "make check-core-compat\n" not in generated
        assert expected_publish_workflow_text(generated, gates) == generated

    def test_markerless_publish_workflow_bootstraps_to_the_marked_file(self) -> None:
        """A marker-less workflow is bootstrapped around the existing gate steps."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        marked = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        markerless = marked
        for marker in (PUBLISH_BEGIN, PUBLISH_END):
            markerless = markerless.replace(marker + "\n", "", 1)
        assert markerless != marked
        assert expected_publish_workflow_text(markerless, registry) == marked

    def test_unowned_publish_bytes_are_preserved(self) -> None:
        """Generation preserves every byte outside the owned marker region."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8").replace(
            "name: Publish to PyPI\n", "name: Publish to PyPI\n# unowned sentinel\n", 1
        )
        generated = expected_publish_workflow_text(current, registry)

        assert (
            generated.split(PUBLISH_BEGIN + "\n", 1)[0] == current.split(PUBLISH_BEGIN + "\n", 1)[0]
        )
        assert generated.split(PUBLISH_END + "\n", 1)[1] == current.split(PUBLISH_END + "\n", 1)[1]

    def test_marker_region_moved_outside_test_steps_fails_closed(self) -> None:
        """A marker pair moved into another job cannot authorize rewriting that job."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        relocated = current.replace(PUBLISH_BEGIN + "\n", "", 1).replace(PUBLISH_END + "\n", "", 1)
        relocated = relocated.replace(
            "      - name: Checkout repository\n",
            PUBLISH_BEGIN + "\n      - name: Checkout repository\n",
            1,
        )
        relocated = relocated.replace(
            "      - name: Set up Python\n",
            PUBLISH_END + "\n      - name: Set up Python\n",
            1,
        )
        with pytest.raises(GeneratorError, match="outside the test job's steps"):
            expected_publish_workflow_text(relocated, registry)

    def test_step_content_after_end_marker_fails_closed(self, tmp_path: Path) -> None:
        """A step property after the end marker belongs to the last gate step."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        valid = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        injected = valid.replace(
            PUBLISH_END + "\n",
            PUBLISH_END + "\n        continue-on-error: true\n",
            1,
        )
        assert injected != valid
        with pytest.raises(GeneratorError, match="after the end marker belongs"):
            expected_publish_workflow_text(injected, registry)

        workflow_path = tmp_path / "publish.yml"
        workflow_path.write_text(injected, encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(Path(sync_ci_gate_jobs_module.__file__)),
                "--check",
                "--publish-workflow",
                str(workflow_path),
                "--registry",
                str(DEFAULT_REGISTRY),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 2
        assert not result.stdout.strip()

    def test_vintage_step_derives_its_target_from_the_registry(self, tmp_path: Path) -> None:
        """The vintage step keeps its env prefix while projecting the registry target."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        _rename_make_target(
            registry_data,
            "check-project-contract-vintage",
            "check-project-contract-vintage-renamed",
        )
        registry_path = tmp_path / "registry.json"
        registry_path.write_text(json.dumps(registry_data), encoding="utf-8")
        gates = _parse_registry(registry_path)
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")

        generated = expected_publish_workflow_text(current, gates)

        assert 'PROJECT_VINTAGE_BASE_REF="$(git describe' in generated
        assert "make check-project-contract-vintage-renamed\n" in generated
        assert "make check-project-contract-vintage\n" not in generated
        assert expected_publish_workflow_text(generated, gates) == generated

    @pytest.mark.parametrize(
        "mutation",
        [
            lambda text: text.replace(PUBLISH_BEGIN + "\n", "", 1),
            lambda text: text.replace(
                PUBLISH_END + "\n", PUBLISH_END + "\n" + PUBLISH_END + "\n", 1
            ),
            lambda text: text.replace(PUBLISH_BEGIN + "\n", PUBLISH_END + "\n", 1),
        ],
    )
    def test_malformed_marker_pairs_fail_closed(self, mutation: Any) -> None:
        """Partial, duplicate, and nested marker pairs are invalid input."""
        registry = _parse_registry(DEFAULT_REGISTRY)
        valid = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        with pytest.raises(GeneratorError, match="marker"):
            expected_publish_workflow_text(mutation(valid), registry)

    def test_registry_publish_removal_fails_closed(self, tmp_path: Path) -> None:
        """A publish-context removal the file does not project fails closed."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        for gate in registry_data["gates"]:
            if gate["id"] == "check-split-facade-imports":
                gate["required_contexts"] = [
                    context for context in gate["required_contexts"] if context != "publish"
                ]
                gate.pop("publish", None)
        removed_path = tmp_path / "removed.json"
        removed_path.write_text(json.dumps(registry_data), encoding="utf-8")
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        with pytest.raises(GeneratorError, match="contains non-gate steps"):
            expected_publish_workflow_text(current, _parse_registry(removed_path))

    def test_registry_publish_addition_projects_from_its_row_alone(self, tmp_path: Path) -> None:
        """A registry-only publish gate projects into the marked region in order."""
        registry_data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        next_publish_order = 1 + max(
            gate["publish"]["order"] for gate in registry_data["gates"] if "publish" in gate
        )
        registry_data["gates"].append(
            {
                "id": "fake-publish-gate",
                "description": "Fake publish gate",
                "required_contexts": ["publish"],
                "bindings": {
                    "make_target": "check-fake-publish",
                    "ci_job": None,
                    "local_ci_stage": None,
                },
                "publish": {"order": next_publish_order, "step_name": "Run fake publish gate"},
                "depends_on": [],
                "trigger_inputs": [],
            }
        )
        added_path = tmp_path / "added.json"
        added_path.write_text(json.dumps(registry_data), encoding="utf-8")
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        gates = _parse_registry(added_path)

        generated = expected_publish_workflow_text(current, gates)

        assert "      - name: Run fake publish gate\n" in generated
        assert "make check-fake-publish\n" in generated
        assert generated.index(PUBLISH_BEGIN) < generated.index("Run fake publish gate")
        assert generated.index("Run fake publish gate") < generated.index(PUBLISH_END)
        assert expected_publish_workflow_text(generated, gates) == generated

    def test_cli_check_write_and_clean_exit_contract(self, tmp_path: Path) -> None:
        """Drift is reported, written, and then checks clean through the CLI."""
        workflow_path = tmp_path / "publish.yml"
        current = DEFAULT_PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        workflow_path.write_text(
            current.replace("make smoke-install\n", "make smoke-install-stale\n", 1),
            encoding="utf-8",
        )
        command = [sys.executable, str(Path(sync_ci_gate_jobs_module.__file__))]
        args = ["--publish-workflow", str(workflow_path), "--registry", str(DEFAULT_REGISTRY)]

        check = subprocess.run(
            [*command, "--check", *args], capture_output=True, text=True, timeout=30
        )
        assert check.returncode == 1, check.stderr
        assert "smoke-install-stale" in check.stdout

        write = subprocess.run(
            [*command, "--write", *args], capture_output=True, text=True, timeout=30
        )
        assert write.returncode == 0, write.stderr
        assert workflow_path.read_text(encoding="utf-8") == current

        clean = subprocess.run(
            [*command, "--check", *args], capture_output=True, text=True, timeout=30
        )
        assert clean.returncode == 0, clean.stderr


# =========================================================================
# F-006 — mandatory generation drift gate
# =========================================================================


class TestMandatoryGenerationGate:
    """CI workflow generation drift fails mandatory ``make check`` (F-006)."""

    def test_mandatory_check_plans_generation_drift_gate(
        self, make_check_plan: subprocess.CompletedProcess
    ) -> None:
        """The real Makefile's check recipe plans the direct generation check."""
        result = make_check_plan
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
        """Write a pytest-managed registry fixture, optionally with a run drift."""
        data = json.loads(DEFAULT_REGISTRY.read_text(encoding="utf-8"))
        if renamed:
            _rename_make_target(data, "check-core-compat", "check-core-compat-renamed")
        fixture_dir = tmp_path / ("renamed" if renamed else "clean")
        fixture_dir.mkdir()
        path = fixture_dir / "custom_registry.json"
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
        result = _plan_make_check(f"GATE_REGISTRY={registry_path}")
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
