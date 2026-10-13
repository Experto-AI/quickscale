"""
Trivy acquisition, dependency scanning, and misconfiguration scanning.

The scanner contract is preserved from the pre-split ``check_security_gates``
module: a checksum-pinned Trivy release is acquired from the official GitHub
release, the committed lockfile is scanned with an exact package-inventory and
dev-sentinel proof, and one freshly rendered generated Dockerfile is judged
for blocking misconfigurations.  Collaborators resolve through the support
and adjudication siblings at call time (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import stat
import tarfile
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import _security_gates_adjudication as _adjudication
import _security_gates_support as _support

TRIVY_VERSION = "0.74.0"
TRIVY_RELEASE_URL = f"https://github.com/aquasecurity/trivy/releases/download/v{TRIVY_VERSION}"
# Official v0.74.0 release-manifest digests for every native host supported by
# the contributor contract. WSL reports Linux and therefore uses a Linux asset.
TRIVY_ASSETS: dict[tuple[str, str], tuple[str, str]] = {
    ("Linux", "x86_64"): (
        "trivy_0.74.0_Linux-64bit.tar.gz",
        "2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a",
    ),
    ("Linux", "arm64"): (
        "trivy_0.74.0_Linux-ARM64.tar.gz",
        "b94ce1976bbf3c15b514b605ee88be7c6d94a29be2302847ff01cb794d47aad5",
    ),
    ("Darwin", "x86_64"): (
        "trivy_0.74.0_macOS-64bit.tar.gz",
        "472816f6888dda689d075c30254d4210b4d1035acf365aa72332f584c2f60485",
    ),
    ("Darwin", "arm64"): (
        "trivy_0.74.0_macOS-ARM64.tar.gz",
        "1caada5e0e2091909357c7525d3aa76f4b660b13821bc143b190c7483e31cc11",
    ),
}
LOCK_NAME = "poetry.lock"
# The generated Dockerfile only; the generated project's other config files are
# outside this gate's surface.
GENERATED_PROJECT_SLUG = "generated-dockerfile-probe"
# "High-severity findings" means high and above.
MISCONFIG_SEVERITIES = ("HIGH", "CRITICAL")


def _trivy_asset() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine, machine)
    try:
        return TRIVY_ASSETS[(system, architecture)]
    except KeyError as exc:
        raise _support.GateError(
            "unsupported Trivy host "
            f"{system}/{machine}; supported native hosts are "
            "Linux x86_64/arm64 and macOS x86_64/arm64 (Windows uses WSL)"
        ) from exc


def _download(url: str, destination: Path) -> None:
    if urlparse(url).scheme != "https":
        raise _support.GateError("scanner acquisition URL must use HTTPS")
    try:
        request = Request(url, headers={"User-Agent": "quickscale-security-gate/1"})
        with (
            urlopen(request, timeout=_support.COMMAND_TIMEOUT) as response,
            destination.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    except OSError as exc:
        raise _support.GateError(f"scanner download failed: {exc}") from exc


def _safe_archive_members(archive: tarfile.TarFile, destination: Path) -> list[tarfile.TarInfo]:
    safe: list[tarfile.TarInfo] = []
    destination = destination.resolve()
    for member in archive.getmembers():
        if member.issym() or member.islnk() or not member.isfile():
            raise _support.GateError(f"unsafe Trivy archive member: {member.name}")
        member_path = (destination / member.name).resolve()
        try:
            member_path.relative_to(destination)
        except ValueError as exc:
            raise _support.GateError(
                f"Trivy archive path escapes extraction directory: {member.name}"
            ) from exc
        safe.append(member)
    return safe


def acquire_trivy() -> Path:
    archive_name, expected_sha256 = _trivy_asset()
    run_dir = _support._new_temp_dir("quickscale-trivy-")
    archive_path = run_dir / archive_name
    _download(f"{TRIVY_RELEASE_URL}/{archive_name}", archive_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise _support.GateError(
            f"Trivy archive checksum mismatch: expected {expected_sha256}, got {digest}"
        )
    extract_dir = run_dir / "extract"
    extract_dir.mkdir()
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in _safe_archive_members(archive, extract_dir):
                archive.extract(member, extract_dir)
    except (OSError, tarfile.TarError) as exc:
        raise _support.GateError(f"Trivy archive extraction failed: {exc}") from exc
    executable = extract_dir / "trivy"
    if not executable.is_file() or executable.is_symlink():
        raise _support.GateError("Trivy archive did not contain a regular trivy executable")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    version = _support.run_command([str(executable), "--version"]).stdout
    match = re.search(r"Version:\s*([0-9]+\.[0-9]+\.[0-9]+)", version)
    if not match or match.group(1) != TRIVY_VERSION:
        raise _support.GateError(f"unexpected Trivy version output: {version.strip()}")
    return executable


def _load_toml(path: Path) -> dict[str, Any]:
    import tomllib

    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise _support.GateError(f"could not parse {path}: {exc}") from exc


def _lock_inventory(lock_path: Path) -> tuple[set[tuple[str, str]], str, bool]:
    document = _load_toml(lock_path)
    packages = document.get("package")
    if not isinstance(packages, list) or not packages:
        raise _support.GateError(f"{lock_path} has no Poetry package inventory")
    inventory: set[tuple[str, str]] = set()
    dev_packages: list[str] = []
    for package in packages:
        if (
            not isinstance(package, dict)
            or not isinstance(package.get("name"), str)
            or not isinstance(package.get("version"), str)
        ):
            raise _support.GateError(f"invalid package entry in {lock_path}")
        inventory.add((package["name"].lower(), package["version"]))
        if "dev" in package.get("groups", []) and "main" not in package.get("groups", []):
            dev_packages.append(package["name"].lower())
    if dev_packages:
        return inventory, sorted(dev_packages)[0], True
    return inventory, sorted(inventory)[0][0], False


def _validated_trivy_report(stdout: str, *, project: str) -> dict[str, Any]:
    """Parse one Trivy JSON report and validate its schema and version."""
    report = _support.strict_json(stdout, source=f"Trivy {project}")
    if not isinstance(report, dict) or report.get("SchemaVersion") != 2:
        raise _support.GateError(f"unexpected Trivy JSON schema for {project}")
    trivy_metadata = report.get("Trivy")
    if not isinstance(trivy_metadata, dict) or trivy_metadata.get("Version") != TRIVY_VERSION:
        raise _support.GateError(f"Trivy JSON version mismatch for {project}")
    return report


def _validated_trivy_results(
    report: dict[str, Any], *, project: str
) -> tuple[dict[str, Any], list[Any]]:
    """Validate the single-poetry-target shape and return its package entries."""
    if report.get("ArtifactName") != LOCK_NAME:
        raise _support.GateError(f"Trivy scanned the wrong artifact for {project}")
    results = report.get("Results")
    if (
        not isinstance(results, list)
        or len(results) != 1
        or not isinstance(results[0], dict)
        or results[0].get("Target") != LOCK_NAME
        or results[0].get("Type") != "poetry"
    ):
        raise _support.GateError(f"Trivy report contains an unexpected target for {project}")
    packages = results[0].get("Packages")
    if not isinstance(packages, list):
        raise _support.GateError(f"Trivy report has no package inventory for {project}")
    if any(not isinstance(item, dict) for item in packages):
        raise _support.GateError(f"Trivy package inventory contains an invalid entry for {project}")
    return results[0], packages


def _verified_lock_inventory(
    packages: list[dict[str, Any]],
    *,
    expected: set[tuple[str, str]],
    sentinel: str,
    expects_dev: bool,
    project: str,
    lock_path: Path,
) -> None:
    """Require the scanned inventory to match the lock exactly, sentinel included."""
    observed = {(item.get("Name", "").lower(), item.get("Version", "")) for item in packages}
    if observed != expected:
        raise _support.GateError(f"Trivy package inventory does not exactly match {lock_path}")
    sentinel_items = [item for item in packages if item.get("Name", "").lower() == sentinel]
    if len(sentinel_items) != 1 or (expects_dev and sentinel_items[0].get("Dev") is not True):
        raise _support.GateError(f"Trivy dev/package sentinel is missing for {project}: {sentinel}")


def _validated_vulnerabilities(result: dict[str, Any], *, project: str) -> list[dict[str, Any]]:
    """Return the vulnerability entries, rejecting a malformed findings list."""
    vulnerabilities = result.get("Vulnerabilities") or []
    if not isinstance(vulnerabilities, list) or any(
        not isinstance(item, dict) for item in vulnerabilities
    ):
        raise _support.GateError(f"invalid Trivy findings for {project}")
    return vulnerabilities


def _trivy_scan(
    trivy: Path, project: str, lock_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected, sentinel, expects_dev = _lock_inventory(lock_path)
    result = _support.run_command(
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
        raise _support.GateError(
            f"Trivy infrastructure failure for {project}: exit {result.returncode}: "
            f"{result.stderr.strip()}"
        )
    report = _validated_trivy_report(result.stdout, project=project)
    first_result, packages = _validated_trivy_results(report, project=project)
    _verified_lock_inventory(
        packages,
        expected=expected,
        sentinel=sentinel,
        expects_dev=expects_dev,
        project=project,
        lock_path=lock_path,
    )
    vulnerabilities = _validated_vulnerabilities(first_result, project=project)
    return vulnerabilities, {
        "project": project,
        "target": LOCK_NAME,
        "include_dev_deps": True,
        "sentinel": sentinel,
        "expects_dev": expects_dev,
    }


def _generated_dockerfile(destination: Path) -> Path:
    """
    Render one fresh generated project and return its Dockerfile path.

    The misconfiguration scan judges the artifact a generated project ships,
    not the Jinja source: rendering through the generator keeps the scanned
    file on the generator's own context and emission mapping.
    """
    try:
        from quickscale_core.generator import ProjectGenerator
    except ImportError as exc:
        raise _support.GateError(f"quickscale_core is not importable: {exc}") from exc
    previous_skip = os.environ.get("QS_SKIP_POETRY_LOCK")
    os.environ["QS_SKIP_POETRY_LOCK"] = "1"
    try:
        project = destination / GENERATED_PROJECT_SLUG
        ProjectGenerator(theme="showcase_react").generate(GENERATED_PROJECT_SLUG, project)
    except (OSError, RuntimeError, ValueError) as exc:
        raise _support.GateError(f"could not generate the Dockerfile fixture: {exc}") from exc
    finally:
        if previous_skip is None:
            os.environ.pop("QS_SKIP_POETRY_LOCK", None)
        else:
            os.environ["QS_SKIP_POETRY_LOCK"] = previous_skip
    dockerfile = project / "Dockerfile"
    if not dockerfile.is_file():
        raise _support.GateError(f"generated project did not emit a Dockerfile: {dockerfile}")
    return dockerfile


def _misconfig_command(trivy: Path, dockerfile: Path) -> list[str]:
    """Return the pinned Trivy misconfiguration command for one Dockerfile."""
    return [
        str(trivy),
        "config",
        "--misconfig-scanners",
        "dockerfile",
        # Embedded checks keep the scan deterministic: the gate must not
        # drift with a downloaded checks bundle.
        "--skip-check-update",
        "--severity",
        ",".join(MISCONFIG_SEVERITIES),
        "--format",
        "json",
        "--exit-code",
        "1",
        str(dockerfile),
    ]


def _validated_misconfig_results(stdout: str, *, dockerfile: Path) -> list[dict[str, Any]]:
    """Parse one misconfiguration report and validate its schema, version, artifact, results."""
    report = _support.strict_json(stdout, source="Trivy misconfiguration scan")
    if not isinstance(report, dict) or report.get("SchemaVersion") != 2:
        raise _support.GateError("unexpected Trivy misconfiguration JSON schema")
    metadata = report.get("Trivy")
    if not isinstance(metadata, dict) or metadata.get("Version") != TRIVY_VERSION:
        raise _support.GateError("Trivy misconfiguration JSON version mismatch")
    artifact = report.get("ArtifactName")
    if not isinstance(artifact, str) or Path(artifact).resolve() != dockerfile.resolve():
        raise _support.GateError(
            f"Trivy misconfiguration scan read the wrong artifact: {artifact!r}"
        )
    results = report.get("Results")
    if (
        not isinstance(results, list)
        or not results
        or any(not isinstance(item, dict) for item in results)
    ):
        raise _support.GateError("Trivy misconfiguration report contains no valid results")
    return results


def _item_checks_evaluated(item: dict[str, Any]) -> int:
    """Return the number of checks one result item evaluated, fail-closed."""
    summary = item.get("MisconfSummary")
    if not isinstance(summary, dict):
        raise _support.GateError("Trivy misconfiguration report has no check summary")
    evaluated = 0
    for key in ("Successes", "Failures"):
        count = summary.get(key)
        if not isinstance(count, int) or isinstance(count, bool) or count < 0:
            raise _support.GateError(f"Trivy misconfiguration summary has an invalid {key}")
        evaluated += count
    return evaluated


def _item_misconfigurations(item: dict[str, Any], *, dockerfile: Path) -> list[dict[str, Any]]:
    """Return the blocking misconfiguration findings of one result item."""
    entries = item.get("Misconfigurations") or []
    if not isinstance(entries, list) or any(not isinstance(entry, dict) for entry in entries):
        raise _support.GateError("Trivy misconfiguration report has invalid entries")
    findings: list[dict[str, Any]] = []
    for entry in entries:
        severity = entry.get("Severity")
        if entry.get("Status") != "FAIL" or severity not in MISCONFIG_SEVERITIES:
            continue
        findings.append(
            {
                "scanner": "trivy",
                "project": "generated-dockerfile",
                "target": Path(str(item.get("Target", dockerfile.name))).name,
                "finding_id": str(entry.get("ID", "")),
                "severity": str(severity),
                "title": str(entry.get("Title", "")),
            }
        )
    return findings


def _trivy_misconfig_scan(
    trivy: Path, dockerfile: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Scan one generated Dockerfile and return blocking findings plus evidence."""
    result = _support.run_command(_misconfig_command(trivy, dockerfile))
    if result.returncode not in (0, 1):
        raise _support.GateError(
            "Trivy misconfiguration scan infrastructure failure: exit "
            f"{result.returncode}: {result.stderr.strip()}"
        )
    results = _validated_misconfig_results(result.stdout, dockerfile=dockerfile)
    evaluated = 0
    findings: list[dict[str, Any]] = []
    for item in results:
        evaluated += _item_checks_evaluated(item)
        findings.extend(_item_misconfigurations(item, dockerfile=dockerfile))
    if evaluated <= 0:
        raise _support.GateError("Trivy misconfiguration scan evaluated no checks")
    if (result.returncode == 1) != bool(findings):
        raise _support.GateError("Trivy misconfiguration exit status disagrees with its report")
    return findings, {
        "project": "generated-dockerfile",
        "target": str(dockerfile),
        "checks_evaluated": evaluated,
        "blocking_findings": len(findings),
    }


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


def _run_dependency_gate(trivy: Path, dockerfile: Path) -> int:
    """
    Run the dependency gate against one acquired Trivy and one Dockerfile.

    Split from :func:`dependency_gate` so the negative-probe control can drive
    the same adjudication with a known-bad Dockerfile.
    """
    findings: list[dict[str, Any]] = []
    evidence: list[dict[str, Any]] = []
    # The root lock is the only committed lockfile; it resolves every package
    # (core, CLI, modules) through path dependencies.
    for project, lock_path in (("root", _support.ROOT / LOCK_NAME),):
        project_findings, scan_evidence = _trivy_scan(trivy, project, lock_path)
        findings.extend(_trivy_finding(item, project) for item in project_findings)
        evidence.append(scan_evidence)
    unsuppressed, suppressed = _adjudication._adjudicate(findings, executed_scanners={"trivy"})
    misconfigurations, misconfiguration_evidence = _trivy_misconfig_scan(trivy, dockerfile)
    if unsuppressed or misconfigurations:
        raise _support.FindingsError(
            json.dumps(
                {"unsuppressed": unsuppressed, "misconfigurations": misconfigurations},
                sort_keys=True,
            )
        )
    print(
        json.dumps(
            {
                "gate": "dependency",
                "trivy_version": TRIVY_VERSION,
                "scans": evidence,
                "misconfiguration_scan": misconfiguration_evidence,
                "suppressed_findings": len(suppressed),
                "unsuppressed_findings": 0,
            },
            sort_keys=True,
        )
    )
    return 0


def dependency_gate() -> int:
    dockerfile = _generated_dockerfile(_support._new_temp_dir("quickscale-generated-dockerfile-"))
    return _run_dependency_gate(acquire_trivy(), dockerfile)
