#!/usr/bin/env python3
"""
Run QuickScale's fail-closed dependency and static-security gates.

The wrapper intentionally owns scanner acquisition and adjudication.  Callers
must not need to know how Trivy is downloaded, which files are scanned, or how
the accountable suppression ledger is interpreted.
"""

from __future__ import annotations

import argparse
import atexit
import hashlib
import json
import os
import platform
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TRIVY_VERSION = "0.74.0"
TRIVY_ARCHIVE = "trivy_0.74.0_Linux-64bit.tar.gz"
TRIVY_URL = f"https://github.com/aquasecurity/trivy/releases/download/v0.74.0/{TRIVY_ARCHIVE}"
TRIVY_SHA256 = "2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a"
BANDIT_VERSION = "1.9.4"
LOCK_NAME = "poetry.lock"
SUPPRESSIONS_PATH = ROOT / "scripts" / "security_suppressions.json"
PROBES_PATH = ROOT / "scripts" / "security_probe_cases.json"
COMMAND_TIMEOUT = 180.0

SOURCE_ROOTS = (
    ROOT / "quickscale" / "src",
    ROOT / "quickscale_cli" / "src",
    ROOT / "quickscale_core" / "src",
    ROOT / "quickscale_devtools" / "src",
    *(
        ROOT / "quickscale_modules" / name / "src"
        for name in (
            "analytics",
            "auth",
            "backups",
            "billing",
            "blog",
            "crm",
            "forms",
            "listings",
            "notifications",
            "orgs",
            "social",
            "storage",
        )
    ),
)

CATEGORY_TESTS: dict[str, tuple[str, ...]] = {
    "subprocess-shell": ("B602",),
    "unsafe-deserialization": ("B301", "B302", "B506"),
    "tls-verification": ("B323", "B501", "B503", "B504"),
    "django-sinks": ("B308", "B611", "B703"),
    "committed-credentials": ("B105", "B106", "B107"),
}
BANDIT_TESTS = tuple(test_id for ids in CATEGORY_TESTS.values() for test_id in ids)
EXCLUDED_PARTS = frozenset(
    {
        ".git",
        ".venv",
        "__pycache__",
        "build",
        "dist",
        "fixtures",
        "migrations",
        "tests",
    }
)


class GateError(RuntimeError):
    """An expected gate failure, reported as infrastructure exit 2."""


class FindingsError(GateError):
    """The scanner returned findings which were not accountable."""


@dataclass(frozen=True)
class Completed:
    returncode: int
    stdout: str
    stderr: str


_temporary_paths: list[Path] = []
_active_processes: set[subprocess.Popen[str]] = set()
_cleanup_started = False


def _terminate_process_group(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=2)
    except ProcessLookupError, subprocess.TimeoutExpired:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=2)
        except ProcessLookupError, subprocess.TimeoutExpired:
            pass


def _cleanup() -> None:
    global _cleanup_started
    if _cleanup_started:
        return
    _cleanup_started = True
    for process in tuple(_active_processes):
        _terminate_process_group(process)
    _active_processes.clear()
    for path in reversed(_temporary_paths):
        shutil.rmtree(path, ignore_errors=True)
    _temporary_paths.clear()


def _signal_handler(signum: int, _frame: Any) -> None:
    _cleanup()
    raise SystemExit(128 + signum)


atexit.register(_cleanup)
for _signal in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
    signal.signal(_signal, _signal_handler)


def run_command(
    argv: list[str], *, cwd: Path | None = None, timeout: float = COMMAND_TIMEOUT
) -> Completed:
    """Run a command in its own process group and fail closed on timeout."""
    process: subprocess.Popen[str] | None = None
    try:
        process = subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            start_new_session=True,
            close_fds=True,
        )
        _active_processes.add(process)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            _terminate_process_group(process)
            raise GateError(f"command timed out after {timeout:g}s: {' '.join(argv)}") from exc
        return Completed(process.returncode, stdout, stderr)
    except OSError as exc:
        raise GateError(f"could not execute {' '.join(argv)}: {exc}") from exc
    finally:
        if process is not None:
            _active_processes.discard(process)


def strict_json(text: str, *, source: str) -> Any:
    """Decode JSON while rejecting duplicate object keys and trailing data."""

    def reject_duplicates(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise GateError(f"duplicate JSON key {key!r} in {source}")
            result[key] = value
        return result

    try:
        return json.loads(text, object_pairs_hook=reject_duplicates)
    except (json.JSONDecodeError, TypeError) as exc:
        raise GateError(f"malformed JSON from {source}: {exc}") from exc


def _new_temp_dir(prefix: str) -> Path:
    path = Path(tempfile.mkdtemp(prefix=prefix))
    _temporary_paths.append(path)
    return path


def _assert_supported_platform() -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise GateError("Trivy v0.74.0 native acquisition supports Linux amd64 only")


def _download(url: str, destination: Path) -> None:
    if urlparse(url).scheme != "https":
        raise GateError("scanner acquisition URL must use HTTPS")
    try:
        request = Request(url, headers={"User-Agent": "quickscale-security-gate/1"})
        with (
            urlopen(request, timeout=COMMAND_TIMEOUT) as response,
            destination.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    except OSError as exc:
        raise GateError(f"scanner download failed: {exc}") from exc


def _safe_archive_members(archive: tarfile.TarFile, destination: Path) -> list[tarfile.TarInfo]:
    safe: list[tarfile.TarInfo] = []
    destination = destination.resolve()
    for member in archive.getmembers():
        if member.issym() or member.islnk() or not member.isfile():
            raise GateError(f"unsafe Trivy archive member: {member.name}")
        member_path = (destination / member.name).resolve()
        try:
            member_path.relative_to(destination)
        except ValueError as exc:
            raise GateError(
                f"Trivy archive path escapes extraction directory: {member.name}"
            ) from exc
        safe.append(member)
    return safe


def acquire_trivy() -> Path:
    _assert_supported_platform()
    run_dir = _new_temp_dir("quickscale-trivy-")
    archive_path = run_dir / TRIVY_ARCHIVE
    _download(TRIVY_URL, archive_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != TRIVY_SHA256:
        raise GateError(f"Trivy archive checksum mismatch: expected {TRIVY_SHA256}, got {digest}")
    extract_dir = run_dir / "extract"
    extract_dir.mkdir()
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in _safe_archive_members(archive, extract_dir):
                archive.extract(member, extract_dir)
    except (OSError, tarfile.TarError) as exc:
        raise GateError(f"Trivy archive extraction failed: {exc}") from exc
    executable = extract_dir / "trivy"
    if not executable.is_file() or executable.is_symlink():
        raise GateError("Trivy archive did not contain a regular trivy executable")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    version = run_command([str(executable), "--version"]).stdout
    match = re.search(r"Version:\s*([0-9]+\.[0-9]+\.[0-9]+)", version)
    if not match or match.group(1) != TRIVY_VERSION:
        raise GateError(f"unexpected Trivy version output: {version.strip()}")
    return executable


def _load_toml(path: Path) -> dict[str, Any]:
    import tomllib

    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise GateError(f"could not parse {path}: {exc}") from exc


def _lock_inventory(lock_path: Path) -> tuple[set[tuple[str, str]], str, bool]:
    document = _load_toml(lock_path)
    packages = document.get("package")
    if not isinstance(packages, list) or not packages:
        raise GateError(f"{lock_path} has no Poetry package inventory")
    inventory: set[tuple[str, str]] = set()
    dev_packages: list[str] = []
    for package in packages:
        if (
            not isinstance(package, dict)
            or not isinstance(package.get("name"), str)
            or not isinstance(package.get("version"), str)
        ):
            raise GateError(f"invalid package entry in {lock_path}")
        inventory.add((package["name"].lower(), package["version"]))
        if "dev" in package.get("groups", []) and "main" not in package.get("groups", []):
            dev_packages.append(package["name"].lower())
    if dev_packages:
        return inventory, sorted(dev_packages)[0], True
    return inventory, sorted(inventory)[0][0], False


def _trivy_scan(
    trivy: Path, project: str, lock_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected, sentinel, expects_dev = _lock_inventory(lock_path)
    result = run_command(
        [
            str(trivy),
            "fs",
            "--scanners",
            "vuln",
            "--format",
            "json",
            "--include-dev-deps",
            "--skip-java-db-update",
            "--offline-scan",
            LOCK_NAME,
        ],
        cwd=lock_path.parent,
    )
    if result.returncode not in (0, 1):
        raise GateError(
            f"Trivy infrastructure failure for {project}: exit {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    report = strict_json(result.stdout, source=f"Trivy {project}")
    if not isinstance(report, dict) or report.get("SchemaVersion") != 2:
        raise GateError(f"unexpected Trivy JSON schema for {project}")
    trivy_metadata = report.get("Trivy")
    if not isinstance(trivy_metadata, dict) or trivy_metadata.get("Version") != TRIVY_VERSION:
        raise GateError(f"Trivy JSON version mismatch for {project}")
    if report.get("ArtifactName") != LOCK_NAME:
        raise GateError(f"Trivy scanned the wrong artifact for {project}")
    results = report.get("Results")
    if (
        not isinstance(results, list)
        or len(results) != 1
        or not isinstance(results[0], dict)
        or results[0].get("Target") != LOCK_NAME
        or results[0].get("Type") != "poetry"
    ):
        raise GateError(f"Trivy report contains an unexpected target for {project}")
    packages = results[0].get("Packages")
    if not isinstance(packages, list):
        raise GateError(f"Trivy report has no package inventory for {project}")
    if any(not isinstance(item, dict) for item in packages):
        raise GateError(f"Trivy package inventory contains an invalid entry for {project}")
    observed = {(item.get("Name", "").lower(), item.get("Version", "")) for item in packages}
    if observed != expected:
        raise GateError(f"Trivy package inventory does not exactly match {lock_path}")
    sentinel_items = [item for item in packages if item.get("Name", "").lower() == sentinel]
    if len(sentinel_items) != 1 or (expects_dev and sentinel_items[0].get("Dev") is not True):
        raise GateError(f"Trivy dev/package sentinel is missing for {project}: {sentinel}")
    vulnerabilities = results[0].get("Vulnerabilities") or []
    if not isinstance(vulnerabilities, list) or any(
        not isinstance(item, dict) for item in vulnerabilities
    ):
        raise GateError(f"invalid Trivy findings for {project}")
    return vulnerabilities, {
        "project": project,
        "target": LOCK_NAME,
        "include_dev_deps": True,
        "sentinel": sentinel,
        "expects_dev": expects_dev,
    }


def _bandit_project(path: Path) -> str:
    relative = path.relative_to(ROOT)
    return relative.parts[0] if relative.parts else "root"


def _bandit_fingerprint(project: str, path: str, test_id: str, line: int) -> str:
    value = f"bandit|{project}|{path}|{test_id}|line={line}"
    return hashlib.sha256(value.encode()).hexdigest()


def _bandit_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("results")
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise GateError("Bandit JSON did not contain a valid results list")
    normalized: list[dict[str, Any]] = []
    for finding in findings:
        path = Path(str(finding.get("filename", ""))).resolve()
        try:
            relative = path.relative_to(ROOT).as_posix()
        except ValueError as exc:
            raise GateError(f"Bandit finding is outside the repository: {path}") from exc
        test_id = finding.get("test_id")
        line = finding.get("line_number")
        if not isinstance(test_id, str) or not isinstance(line, int):
            raise GateError("Bandit finding lacks an exact code identity")
        project = _bandit_project(path)
        normalized.append(
            {
                "scanner": "bandit",
                "finding_id": test_id,
                "project": project,
                "path": relative,
                "code_identity": f"line={line}",
                "fingerprint": _bandit_fingerprint(project, relative, test_id, line),
                "finding": finding,
            }
        )
    return normalized


def _source_files() -> list[Path]:
    files: list[Path] = []
    for source_root in SOURCE_ROOTS:
        if not source_root.is_dir():
            raise GateError(f"missing Bandit source root: {source_root}")
        for path in source_root.rglob("*.py"):
            if not EXCLUDED_PARTS.intersection(path.parts):
                files.append(path)
    if not files:
        raise GateError("no Bandit source files were selected")
    return sorted(files)


def _bandit_scan() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    version = run_command(["bandit", "--version"])
    if version.returncode != 0:
        raise GateError(f"Bandit version command failed: {version.stderr.strip()}")
    match = re.search(r"bandit\s+([0-9]+\.[0-9]+\.[0-9]+)", version.stdout)
    if not match or match.group(1) != BANDIT_VERSION:
        raise GateError(f"unexpected Bandit version: {version.stdout.strip()}")
    help_result = run_command(["bandit", "--help"])
    if help_result.returncode != 0:
        raise GateError(f"Bandit help command failed: {help_result.stderr.strip()}")
    help_output = help_result.stdout
    available = set(re.findall(r"\bB[0-9]{3}\b", help_output))
    missing = sorted(set(BANDIT_TESTS) - available)
    if missing:
        raise GateError(f"Bandit plugin inventory is incomplete: {', '.join(missing)}")
    source_files = _source_files()
    command = [
        "bandit",
        "-q",
        "-r",
        *[str(root) for root in SOURCE_ROOTS],
        "--format",
        "json",
        "--ignore-nosec",
        "--tests",
        ",".join(BANDIT_TESTS),
        "--exclude",
        ",".join(f"*/{part}/*" for part in sorted(EXCLUDED_PARTS)),
    ]
    result = run_command(command)
    if result.returncode not in (0, 1):
        raise GateError(
            f"Bandit infrastructure failure: exit {result.returncode}: {result.stderr.strip()}"
        )
    report = strict_json(result.stdout, source="Bandit")
    if not isinstance(report, dict):
        raise GateError("Bandit JSON root must be an object")
    findings = _bandit_findings(report)
    return findings, {
        "version": BANDIT_VERSION,
        "source_files": len(source_files),
        "tests": list(BANDIT_TESTS),
        "ignore_nosec": True,
    }


SUPPRESSION_KEYS = frozenset(
    {
        "scanner",
        "finding_id",
        "project",
        "path",
        "package",
        "installed_version",
        "code_identity",
        "fingerprint",
        "owner",
        "rationale",
        "decision_ref",
        "expires",
    }
)


def _load_suppressions() -> list[dict[str, Any]]:
    try:
        text = SUPPRESSIONS_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise GateError(f"could not read suppression ledger: {exc}") from exc
    document = strict_json(text, source=str(SUPPRESSIONS_PATH))
    if (
        not isinstance(document, dict)
        or set(document) != {"schema_version", "description", "suppressions"}
        or document.get("schema_version") != 1
    ):
        raise GateError("invalid suppression ledger schema")
    entries = document.get("suppressions")
    if not isinstance(entries, list):
        raise GateError("suppression ledger must contain a list")
    seen: set[str] = set()
    for entry in entries:
        if (
            not isinstance(entry, dict)
            or set(entry) - SUPPRESSION_KEYS
            or SUPPRESSION_KEYS - set(entry)
        ):
            raise GateError("suppression entries have unknown or missing fields")
        if any(
            not isinstance(entry[key], str) or not entry[key].strip() for key in SUPPRESSION_KEYS
        ):
            raise GateError("suppression entries may not contain empty fields")
        if entry["fingerprint"] in seen:
            raise GateError(f"duplicate suppression fingerprint: {entry['fingerprint']}")
        seen.add(entry["fingerprint"])
        try:
            expiry = date.fromisoformat(entry["expires"])
        except ValueError as exc:
            raise GateError(f"invalid suppression expiry: {entry['expires']}") from exc
        if expiry < date.today():
            raise GateError(f"expired suppression: {entry['fingerprint']}")
        if entry["scanner"] not in {"trivy", "bandit"}:
            raise GateError(f"unknown suppression scanner: {entry['scanner']}")
        if entry["finding_id"].lower() in {"all", "*", "any", "category"}:
            raise GateError("broad scanner/category suppressions are forbidden")
    return entries


def _adjudicate(
    findings: list[dict[str, Any]],
    *,
    executed_scanners: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    finding_scanners = {finding["scanner"] for finding in findings}
    if not finding_scanners <= executed_scanners:
        raise GateError("findings include a scanner that was not executed")
    suppressions = [
        entry for entry in _load_suppressions() if entry["scanner"] in executed_scanners
    ]
    matches: dict[str, int] = {entry["fingerprint"]: 0 for entry in suppressions}
    unsuppressed: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for finding in findings:
        candidates: list[dict[str, Any]] = []
        for entry in suppressions:
            if (
                finding["scanner"] != entry["scanner"]
                or finding["finding_id"] != entry["finding_id"]
                or finding["project"] != entry["project"]
                or finding["path"] != entry["path"]
            ):
                continue
            if finding["scanner"] == "trivy":
                if finding.get("package") != entry.get("package") or finding.get(
                    "installed_version"
                ) != entry.get("installed_version"):
                    continue
            else:
                if finding.get("code_identity") != entry.get("code_identity"):
                    continue
            if finding["fingerprint"] == entry["fingerprint"]:
                candidates.append(entry)
        if len(candidates) == 1:
            matches[candidates[0]["fingerprint"]] += 1
            suppressed.append(finding)
        else:
            unsuppressed.append(finding)
    stale = [fingerprint for fingerprint, count in matches.items() if count != 1]
    if stale:
        raise GateError(
            f"suppression cardinality failure (zero or multiple matches): {', '.join(stale)}"
        )
    return unsuppressed, suppressed


def _trivy_finding(item: dict[str, Any], project: str) -> dict[str, Any]:
    return {
        "scanner": "trivy",
        "finding_id": str(item.get("VulnerabilityID", "")),
        "project": project,
        "path": LOCK_NAME,
        "package": str(item.get("PkgName", "")),
        "installed_version": str(item.get("InstalledVersion", "")),
        "fingerprint": str(item.get("Fingerprint", "")),
        "finding": item,
    }


def dependency_gate() -> int:
    trivy = acquire_trivy()
    findings: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    for project, lock_path in (
        ("root", ROOT / LOCK_NAME),
        ("quickscale_core", ROOT / "quickscale_core" / LOCK_NAME),
    ):
        project_findings, scan_evidence = _trivy_scan(trivy, project, lock_path)
        findings.extend(_trivy_finding(item, project) for item in project_findings)
        evidence.append(scan_evidence)
    unsuppressed, suppressed = _adjudicate(findings, executed_scanners={"trivy"})
    if unsuppressed:
        raise FindingsError(json.dumps({"unsuppressed": unsuppressed}, sort_keys=True))
    print(
        json.dumps(
            {
                "gate": "dependency",
                "trivy_version": TRIVY_VERSION,
                "scans": evidence,
                "suppressed_findings": len(suppressed),
                "unsuppressed_findings": 0,
            },
            sort_keys=True,
        )
    )
    return 0


def static_gate() -> int:
    findings, evidence = _bandit_scan()
    unsuppressed, suppressed = _adjudicate(findings, executed_scanners={"bandit"})
    if unsuppressed:
        raise FindingsError(json.dumps({"unsuppressed": unsuppressed}, sort_keys=True))
    print(
        json.dumps(
            {
                "gate": "static-analysis",
                "bandit": evidence,
                "suppressed_findings": len(suppressed),
                "unsuppressed_findings": 0,
            },
            sort_keys=True,
        )
    )
    return 0


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


def negative_probes() -> int:
    probes = strict_json(PROBES_PATH.read_text(encoding="utf-8"), source=str(PROBES_PATH))
    if not isinstance(probes, dict) or probes.get("schema_version") != 1:
        raise GateError("invalid security probe case schema")
    trivy_probe = probes.get("trivy")
    bandit_probe = probes.get("bandit")
    if not isinstance(trivy_probe, dict) or not isinstance(bandit_probe, dict):
        raise GateError("security probe cases must contain Trivy and Bandit records")
    required_trivy = {"scanner_version", "package", "version", "advisory"}
    required_bandit = {"version", "test_id", "line"}
    if not required_trivy <= set(trivy_probe) or not required_bandit <= set(bandit_probe):
        raise GateError("security probe cases omit required finding identities")
    if (
        trivy_probe.get("scanner_version") != TRIVY_VERSION
        or bandit_probe.get("version") != BANDIT_VERSION
    ):
        raise GateError("security probe scanner versions do not match the pinned tools")
    trivy = acquire_trivy()
    probe_dir = _new_temp_dir("quickscale-security-probes-")
    lock_path = probe_dir / LOCK_NAME
    _probe_lock(lock_path)
    trivy_result = run_command(
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
            LOCK_NAME,
        ],
        cwd=probe_dir,
    )
    if trivy_result.returncode != 1:
        raise GateError(
            f"Trivy negative probe did not return findings exit 1: {trivy_result.returncode}"
        )
    trivy_report = strict_json(trivy_result.stdout, source="Trivy negative probe")
    if not isinstance(trivy_report, dict):
        raise GateError("Trivy negative probe JSON root must be an object")
    probe_results = trivy_report.get("Results")
    if not isinstance(probe_results, list) or any(
        not isinstance(result, dict) for result in probe_results
    ):
        raise GateError("Trivy negative probe JSON has invalid results")
    actual: list[dict[str, Any]] = []
    for result in probe_results:
        vulnerabilities = result.get("Vulnerabilities") or []
        if not isinstance(vulnerabilities, list) or any(
            not isinstance(item, dict) for item in vulnerabilities
        ):
            raise GateError("Trivy negative probe JSON has invalid vulnerabilities")
        actual.extend(vulnerabilities)
    if not any(
        item.get("VulnerabilityID") == trivy_probe["advisory"]
        and item.get("PkgName") == trivy_probe["package"]
        and item.get("InstalledVersion") == trivy_probe["version"]
        for item in actual
    ):
        raise GateError("Trivy negative probe identity was not observed")
    source = probe_dir / "bandit_probe.py"
    source.write_text('import subprocess\nsubprocess.run("id", shell=True)\n', encoding="utf-8")
    bandit_result = run_command(
        ["bandit", "-q", str(source), "--format", "json", "--ignore-nosec", "--tests", "B602"]
    )
    if bandit_result.returncode != 1:
        raise GateError(
            f"Bandit negative probe did not return findings exit 1: {bandit_result.returncode}"
        )
    bandit_report = strict_json(bandit_result.stdout, source="Bandit negative probe")
    if not isinstance(bandit_report, dict) or not isinstance(bandit_report.get("results"), list):
        raise GateError("Bandit negative probe JSON has invalid results")
    if not any(
        item.get("test_id") == bandit_probe["test_id"] for item in bandit_report.get("results", [])
    ):
        raise GateError("Bandit negative probe identity was not observed")
    print(
        json.dumps(
            {
                "gate": "negative-probes",
                "trivy_version": TRIVY_VERSION,
                "trivy_advisory": trivy_probe["advisory"],
                "bandit_version": BANDIT_VERSION,
                "bandit_test_id": bandit_probe["test_id"],
                "underlying_exit_codes": {"trivy": 1, "bandit": 1},
                "cleanup": "armed-before-temporary-creation",
            },
            sort_keys=True,
        )
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "mode",
        nargs="?",
        choices=(
            "dependency",
            "dependency-vulnerabilities",
            "static",
            "static-analysis",
            "security-static-analysis",
            "negative-probes",
            "security-negative-probes",
        ),
    )
    parser.add_argument(
        "--mode",
        dest="mode_option",
        choices=(
            "dependency",
            "dependency-vulnerabilities",
            "static",
            "static-analysis",
            "security-static-analysis",
            "negative-probes",
            "security-negative-probes",
        ),
    )
    args = parser.parse_args(argv)
    if args.mode and args.mode_option and args.mode != args.mode_option:
        parser.error("positional mode and --mode must agree")
    mode = args.mode_option or args.mode
    if mode in {"dependency", "dependency-vulnerabilities"}:
        return dependency_gate()
    if mode in {"static", "static-analysis", "security-static-analysis"}:
        return static_gate()
    if mode in {"negative-probes", "security-negative-probes"}:
        return negative_probes()
    parser.error("a scanner mode is required")
    return 2


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except FindingsError as exc:
        print(f"security findings: {exc}", file=sys.stderr)
        raise SystemExit(1)
    except GateError as exc:
        print(f"security gate infrastructure failure: {exc}", file=sys.stderr)
        raise SystemExit(2)
