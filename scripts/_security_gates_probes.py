"""
Negative-probe controls for the security gate facade.

Each probe drives a pinned scanner against a known-bad fixture and proves the
scanner reports the exact identity the gate depends on, so a scanner that
silently stops detecting cannot leave the gate green.  The probe contract is
preserved from the pre-split ``check_security_gates`` module; collaborators
resolve through the support and trivy siblings at call time
(decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import _security_gates_bandit as _bandit
import _security_gates_support as _support
import _security_gates_trivy as _trivy

PROBES_PATH = _support.ROOT / "scripts" / "security_probe_cases.json"

# A deliberately root-user Dockerfile: Trivy's dockerfile checks flag the last
# USER as root at high severity, so the negative probe proves the
# misconfiguration scan fails a known-bad file.
BAD_DOCKERFILE_PROBE = "FROM ubuntu:latest\nUSER root\n"


def _probe_lock(path: Path) -> None:
    probe_hash = "e20d4a9b0b8585fdf63b10d30066c7c94c5d7a7ec47c889a2d83a3caa93ff28e"
    path.write_text(
        "\n".join(
            [
                "[[package]]",
                'name = "sqlparse"',
                'version = "0.5.5"',
                'description = "A non-validating SQL parser."',
                "optional = false",
                'python-versions = ">=3.8"',
                'groups = ["main"]',
                (
                    'files = [{file = "sqlparse-0.5.5-py3-none-any.whl", '
                    f'hash = "sha256:{probe_hash}"}}]'
                ),
                "",
                "[metadata]",
                'lock-version = "2.1"',
                'python-versions = ">=3.14,<3.15"',
                'content-hash = "probe"',
                "",
            ]
        ),
        encoding="utf-8",
    )


def _load_probe_cases() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Load the probe case file and return its validated Trivy, config, and Bandit records."""
    probes = _support.strict_json(PROBES_PATH.read_text(encoding="utf-8"), source=str(PROBES_PATH))
    if not isinstance(probes, dict) or probes.get("schema_version") != 1:
        raise _support.GateError("invalid security probe case schema")
    trivy_probe = probes.get("trivy")
    trivy_config_probe = probes.get("trivy_config")
    bandit_probe = probes.get("bandit")
    if (
        not isinstance(trivy_probe, dict)
        or not isinstance(trivy_config_probe, dict)
        or not isinstance(bandit_probe, dict)
    ):
        raise _support.GateError(
            "security probe cases must contain Trivy, Trivy-config, and Bandit records"
        )
    required_trivy = {"scanner_version", "package", "version", "advisory"}
    required_trivy_config = {"scanner_version", "check_id", "severity"}
    required_bandit = {"version", "test_id", "line"}
    if (
        not required_trivy <= set(trivy_probe)
        or not required_trivy_config <= set(trivy_config_probe)
        or not required_bandit <= set(bandit_probe)
    ):
        raise _support.GateError("security probe cases omit required finding identities")
    if (
        trivy_probe.get("scanner_version") != _trivy.TRIVY_VERSION
        or trivy_config_probe.get("scanner_version") != _trivy.TRIVY_VERSION
        or bandit_probe.get("version") != _bandit.BANDIT_VERSION
    ):
        raise _support.GateError("security probe scanner versions do not match the pinned tools")
    if trivy_config_probe.get("severity") not in _trivy.MISCONFIG_SEVERITIES:
        raise _support.GateError("security probe misconfiguration severity is not blocking")
    return trivy_probe, trivy_config_probe, bandit_probe


def _probe_vulnerabilities(
    probe_results: list[Any],
) -> list[dict[str, Any]]:
    """Validate one probe report's results and flatten its vulnerability entries."""
    actual: list[dict[str, Any]] = []
    for result in probe_results:
        vulnerabilities = result.get("Vulnerabilities") or []
        if not isinstance(vulnerabilities, list) or any(
            not isinstance(item, dict) for item in vulnerabilities
        ):
            raise _support.GateError("Trivy negative probe JSON has invalid vulnerabilities")
        actual.extend(vulnerabilities)
    return actual


def _run_trivy_probe(trivy: Path, probe_dir: Path, probe: dict[str, Any]) -> None:
    """Run the Trivy vulnerability probe and prove the advisory identity appears."""
    lock_path = probe_dir / _trivy.LOCK_NAME
    _probe_lock(lock_path)
    trivy_result = _support.run_command(
        [
            str(trivy),
            "fs",
            "--scanners",
            "vuln",
            "--format",
            "json",
            "--exit-code",
            "1",
            "--include-dev-deps",
            "--skip-java-db-update",
            "--offline-scan",
            _trivy.LOCK_NAME,
        ],
        cwd=probe_dir,
    )
    if trivy_result.returncode != 1:
        raise _support.GateError(
            f"Trivy negative probe did not return findings exit 1: {trivy_result.returncode}"
        )
    trivy_report = _support.strict_json(trivy_result.stdout, source="Trivy negative probe")
    if not isinstance(trivy_report, dict):
        raise _support.GateError("Trivy negative probe JSON root must be an object")
    probe_results = trivy_report.get("Results")
    if not isinstance(probe_results, list) or any(
        not isinstance(result, dict) for result in probe_results
    ):
        raise _support.GateError("Trivy negative probe JSON has invalid results")
    actual = _probe_vulnerabilities(probe_results)
    if not any(
        item.get("VulnerabilityID") == probe["advisory"]
        and item.get("PkgName") == probe["package"]
        and item.get("InstalledVersion") == probe["version"]
        for item in actual
    ):
        raise _support.GateError("Trivy negative probe identity was not observed")


def _run_bandit_probe(probe_dir: Path, probe: dict[str, Any]) -> None:
    """Run the Bandit probe on a known-bad source and prove the test identity appears."""
    source = probe_dir / "bandit_probe.py"
    source.write_text('import subprocess\nsubprocess.run("id", shell=True)\n', encoding="utf-8")
    bandit_result = _support.run_command(
        ["bandit", "-q", str(source), "--format", "json", "--ignore-nosec", "--tests", "B602"]
    )
    if bandit_result.returncode != 1:
        raise _support.GateError(
            f"Bandit negative probe did not return findings exit 1: {bandit_result.returncode}"
        )
    bandit_report = _support.strict_json(bandit_result.stdout, source="Bandit negative probe")
    if not isinstance(bandit_report, dict) or not isinstance(bandit_report.get("results"), list):
        raise _support.GateError("Bandit negative probe JSON has invalid results")
    if not any(
        item.get("test_id") == probe["test_id"] for item in bandit_report.get("results", [])
    ):
        raise _support.GateError("Bandit negative probe identity was not observed")


def _assert_misconfig_probe(trivy: Path, probe_dir: Path, config_probe: dict[str, Any]) -> None:
    """Prove the known-bad Dockerfile fails the dependency gate on the pinned check."""
    bad_dockerfile = probe_dir / "Dockerfile"
    bad_dockerfile.write_text(BAD_DOCKERFILE_PROBE, encoding="utf-8")
    misconfig_result = _support.run_command(_trivy._misconfig_command(trivy, bad_dockerfile))
    if misconfig_result.returncode != 1:
        raise _support.GateError(
            "Trivy misconfiguration negative probe did not return findings exit 1: "
            f"{misconfig_result.returncode}"
        )
    try:
        _trivy._run_dependency_gate(trivy, bad_dockerfile)
    except _support.FindingsError as exc:
        observed = _support.strict_json(str(exc), source="dependency-gate negative probe")
        misconfigurations = (
            observed.get("misconfigurations") if isinstance(observed, dict) else None
        )
        if not isinstance(misconfigurations, list) or not any(
            item.get("finding_id") == config_probe["check_id"]
            and item.get("severity") == config_probe["severity"]
            for item in misconfigurations
            if isinstance(item, dict)
        ):
            raise _support.GateError(
                "Trivy misconfiguration negative probe identity was not observed"
            ) from exc
    else:
        raise _support.GateError("known-bad Dockerfile passed the dependency gate")


def negative_probes() -> int:
    trivy_probe, trivy_config_probe, bandit_probe = _load_probe_cases()
    trivy = _trivy.acquire_trivy()
    probe_dir = _support._new_temp_dir("quickscale-security-probes-")
    _run_trivy_probe(trivy, probe_dir, trivy_probe)
    _run_bandit_probe(probe_dir, bandit_probe)
    _assert_misconfig_probe(trivy, probe_dir, trivy_config_probe)
    print(
        json.dumps(
            {
                "gate": "negative-probes",
                "trivy_version": _trivy.TRIVY_VERSION,
                "trivy_advisory": trivy_probe["advisory"],
                "trivy_config_check_id": trivy_config_probe["check_id"],
                "bandit_version": _bandit.BANDIT_VERSION,
                "bandit_test_id": bandit_probe["test_id"],
                "underlying_exit_codes": {"trivy": 1, "trivy_config": 1, "bandit": 1},
                "cleanup": "armed-before-temporary-creation",
            },
            sort_keys=True,
        )
    )
    return 0
