#!/usr/bin/env python3
"""
Blocking secret-scanning gate for committed credentials (SA202, SA326).

Acquires a checksum-pinned ``gitleaks`` release and scans two surfaces:

* the repository working tree (``gitleaks dir``), and
* the full commit history reachable from ``HEAD`` (``gitleaks git``), so a
  credential deleted from the tree stays visible.

``scripts/gitleaks.toml`` extends the default ruleset with structural
exclusions only (generated scratch trees and non-source directories).  Every
value-level exemption lives in ``scripts/secret_scan_suppressions.json``: each
entry names one finding fingerprint, its owner, a rationale, a decision
reference, and an ISO expiry.  An entry that matches no finding, an expired
entry, and a finding with no entry all fail the gate.  A shallow clone fails
closed because ``gitleaks git`` would silently scan only the fetched depth.

Failure policy: any unsuppressed finding fails the gate as exit 1.  A missing or
unsupported host, a download or checksum failure, an unsafe archive, an
unexpected tool version, a shallow clone, a malformed or stale suppression
ledger, or a report that disagrees with the process exit status fails closed as
infrastructure exit 2.  Secrets are never silently skipped.
"""

from __future__ import annotations

import hashlib
import json
import platform
import re
import stat
import subprocess
import sys
import tarfile
import tempfile
from datetime import date
from pathlib import Path
from typing import Any
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
GITLEAKS_VERSION = "8.30.1"
GITLEAKS_RELEASE_URL = f"https://github.com/gitleaks/gitleaks/releases/download/v{GITLEAKS_VERSION}"
# Official v8.30.1 release-manifest digests for every native host supported by
# the contributor contract. WSL reports Linux and therefore uses a Linux asset.
GITLEAKS_ASSETS: dict[tuple[str, str], tuple[str, str]] = {
    ("Linux", "x86_64"): (
        "gitleaks_8.30.1_linux_x64.tar.gz",
        "551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb",
    ),
    ("Linux", "arm64"): (
        "gitleaks_8.30.1_linux_arm64.tar.gz",
        "e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080",
    ),
    ("Darwin", "x86_64"): (
        "gitleaks_8.30.1_darwin_x64.tar.gz",
        "dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709",
    ),
    ("Darwin", "arm64"): (
        "gitleaks_8.30.1_darwin_arm64.tar.gz",
        "b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5",
    ),
}
CONFIG_PATH = ROOT / "scripts" / "gitleaks.toml"
SUPPRESSIONS_PATH = ROOT / "scripts" / "secret_scan_suppressions.json"
COMMAND_TIMEOUT = 600.0
# Distinguishes "the scanner found leaks" from an infrastructure failure.
FINDINGS_EXIT_CODE = 7
EXIT_FINDINGS = 1
EXIT_INFRASTRUCTURE = 2
SCAN_MODES = frozenset({"tree", "history"})
SUPPRESSION_KEYS = frozenset(
    {
        "scanner",
        "rule_id",
        "path",
        "mode",
        "fingerprints",
        "owner",
        "rationale",
        "decision_ref",
        "expires",
    }
)
LEDGER_KEYS = frozenset({"schema_version", "description", "suppressions"})


class GateError(RuntimeError):
    """An expected gate failure, reported as infrastructure exit 2."""


def _asset() -> tuple[str, str]:
    system = platform.system()
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine, machine)
    try:
        return GITLEAKS_ASSETS[(system, architecture)]
    except KeyError as exc:
        raise GateError(
            "unsupported gitleaks host "
            f"{system}/{machine}; supported native hosts are "
            "Linux x86_64/arm64 and macOS x86_64/arm64 (Windows uses WSL)"
        ) from exc


def _download(url: str, destination: Path) -> None:
    if urlparse(url).scheme != "https":
        raise GateError("scanner acquisition URL must use HTTPS")
    try:
        request = Request(url, headers={"User-Agent": "quickscale-secret-gate/1"})
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
            raise GateError(f"unsafe gitleaks archive member: {member.name}")
        member_path = (destination / member.name).resolve()
        try:
            member_path.relative_to(destination)
        except ValueError as exc:
            raise GateError(
                f"gitleaks archive path escapes extraction directory: {member.name}"
            ) from exc
        safe.append(member)
    return safe


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateError(f"could not run {command[0]}: {exc}") from exc


def acquire_gitleaks() -> Path:
    """Download, verify, and extract the pinned gitleaks executable."""
    archive_name, expected_sha256 = _asset()
    run_dir = Path(tempfile.mkdtemp(prefix="quickscale-gitleaks-"))
    archive_path = run_dir / archive_name
    _download(f"{GITLEAKS_RELEASE_URL}/{archive_name}", archive_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise GateError(
            f"gitleaks archive checksum mismatch: expected {expected_sha256}, got {digest}"
        )
    extract_dir = run_dir / "extract"
    extract_dir.mkdir()
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in _safe_archive_members(archive, extract_dir):
                archive.extract(member, extract_dir)
    except (OSError, tarfile.TarError) as exc:
        raise GateError(f"gitleaks archive extraction failed: {exc}") from exc
    executable = extract_dir / "gitleaks"
    if not executable.is_file() or executable.is_symlink():
        raise GateError("gitleaks archive did not contain a regular gitleaks executable")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    version = _run([str(executable), "version"]).stdout.strip()
    match = re.fullmatch(r"v?([0-9]+\.[0-9]+\.[0-9]+)", version)
    if not match or match.group(1) != GITLEAKS_VERSION:
        raise GateError(f"unexpected gitleaks version output: {version!r}")
    return executable


def _run_scan(executable: Path, mode: str, target: Path, config: Path) -> list[dict[str, Any]]:
    """Run one gitleaks scan mode and return its adjudicated finding records."""
    if not config.is_file():
        raise GateError(f"gitleaks config not found: {config}")
    completed = _run(
        [
            str(executable),
            mode,
            str(target),
            "--config",
            str(config),
            "--no-banner",
            "--redact",
            "--report-format",
            "json",
            "--report-path",
            "-",
            "--exit-code",
            str(FINDINGS_EXIT_CODE),
        ]
    )
    if completed.returncode not in (0, FINDINGS_EXIT_CODE):
        detail = completed.stderr.strip().splitlines()
        raise GateError(
            f"gitleaks exited {completed.returncode}: {detail[-1] if detail else 'no stderr'}"
        )
    if not completed.stdout.strip():
        raise GateError("gitleaks produced no report on stdout")
    try:
        report = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise GateError(f"unparseable gitleaks report: {exc}") from exc
    if not isinstance(report, list):
        raise GateError(f"unexpected gitleaks report shape: {type(report).__name__}")
    for finding in report:
        if not isinstance(finding, dict):
            raise GateError("unexpected gitleaks finding shape")
    if completed.returncode == 0 and report:
        raise GateError("gitleaks reported findings with a clean exit status")
    if completed.returncode == FINDINGS_EXIT_CODE and not report:
        raise GateError("gitleaks reported a findings exit status with an empty report")
    return report


def scan(executable: Path, target: Path, config: Path) -> list[dict[str, Any]]:
    """Scan the working tree at *target*."""
    return _run_scan(executable, "dir", target, config)


def scan_history(executable: Path, repo_root: Path, config: Path) -> list[dict[str, Any]]:
    """Scan every commit reachable from ``HEAD`` in *repo_root*."""
    _ensure_full_history(repo_root)
    return _run_scan(executable, "git", repo_root, config)


def _ensure_full_history(repo_root: Path) -> None:
    """Fail closed when the clone is shallow: gitleaks would scan only its depth."""
    completed = _run(["git", "-C", str(repo_root), "rev-parse", "--is-shallow-repository"])
    if completed.returncode != 0:
        detail = completed.stderr.strip().splitlines()
        raise GateError(
            "could not determine whether the clone is shallow: "
            f"{detail[-1] if detail else 'git rev-parse failed'}"
        )
    if completed.stdout.strip() == "true":
        raise GateError(
            "secret history scan needs a full-history clone; "
            f"run `git -C {repo_root} fetch --unshallow` and retry"
        )


def _read_ledger(path: Path) -> list[Any]:
    """Read the ledger document and return its raw suppression entries."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise GateError(f"could not read secret suppressions {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise GateError(f"unparseable secret suppressions {path}: {exc}") from exc
    if not isinstance(document, dict) or set(document) != LEDGER_KEYS:
        raise GateError(f"secret suppressions {path} must declare exactly {sorted(LEDGER_KEYS)}")
    if document.get("schema_version") != 1:
        raise GateError("secret suppressions schema_version must be 1")
    if not isinstance(document.get("description"), str) or not document["description"]:
        raise GateError("secret suppressions description must be a non-empty string")
    entries = document.get("suppressions")
    if not isinstance(entries, list):
        raise GateError("secret suppressions entries must be a list")
    return entries


def _require_entry_text(entry: dict[str, Any], label: str) -> None:
    """Require the entry's accountability fields to be non-empty strings."""
    for key in ("rule_id", "path", "owner", "rationale", "decision_ref"):
        if not isinstance(entry[key], str) or not entry[key]:
            raise GateError(f"{label}.{key} must be a non-empty string")


def _validate_expiry(entry: dict[str, Any], label: str) -> None:
    """Reject a malformed or passed expiry."""
    try:
        expires = date.fromisoformat(entry["expires"])
    except (TypeError, ValueError) as exc:
        raise GateError(f"{label}.expires must be an ISO date: {exc}") from exc
    if expires <= date.today():
        raise GateError(f"{label} expired on {entry['expires']}; re-review or remove it")


def _validate_fingerprints(entry: dict[str, Any], label: str, seen_fingerprints: set[str]) -> None:
    """Require a non-empty, globally unique fingerprint list."""
    fingerprints = entry["fingerprints"]
    if not isinstance(fingerprints, list) or not fingerprints:
        raise GateError(f"{label}.fingerprints must be a non-empty list")
    for fingerprint in fingerprints:
        if not isinstance(fingerprint, str) or not fingerprint:
            raise GateError(f"{label}.fingerprints entries must be non-empty strings")
        if fingerprint in seen_fingerprints:
            raise GateError(f"duplicate secret suppression fingerprint: {fingerprint}")
        seen_fingerprints.add(fingerprint)


def _validate_suppression(entry: Any, index: int, seen_fingerprints: set[str]) -> dict[str, Any]:
    """Validate one suppression entry and return it unchanged."""
    label = f"secret suppressions[{index}]"
    if not isinstance(entry, dict) or set(entry) != SUPPRESSION_KEYS:
        raise GateError(f"{label} must declare exactly {sorted(SUPPRESSION_KEYS)}")
    if entry["scanner"] != "gitleaks":
        raise GateError(f"{label}.scanner must be 'gitleaks'")
    _require_entry_text(entry, label)
    mode = entry["mode"]
    if not isinstance(mode, str) or (mode not in SCAN_MODES and mode != "any"):
        raise GateError(f"{label}.mode must be one of tree, history, any")
    _validate_expiry(entry, label)
    _validate_fingerprints(entry, label, seen_fingerprints)
    return entry


def _load_suppressions(path: Path) -> list[dict[str, Any]]:
    """Load and validate the expiring suppression ledger."""
    seen_fingerprints: set[str] = set()
    return [
        _validate_suppression(entry, index, seen_fingerprints)
        for index, entry in enumerate(_read_ledger(path))
    ]


def _finding_identity(finding: dict[str, Any]) -> tuple[str, str, str]:
    """Return ``(fingerprint, rule_id, path)`` for a finding, failing closed."""
    fingerprint = finding.get("Fingerprint")
    rule = finding.get("RuleID")
    path = finding.get("File")
    if not all(isinstance(value, str) and value for value in (fingerprint, rule, path)):
        raise GateError("gitleaks finding is missing Fingerprint, RuleID, or File")
    return _repo_relative_fingerprint(fingerprint), rule, _repo_relative_path(path)


def _repo_relative_fingerprint(value: str) -> str:
    """Strip an absolute scan-target prefix from a gitleaks fingerprint."""
    root = ROOT.as_posix()
    if value.startswith(f"{root}/"):
        value = value[len(root) + 1 :]
    return value.replace(f":{root}/", ":")


def _repo_relative_path(value: str) -> str:
    """Normalize an absolute finding path to its repository-relative spelling."""
    candidate = Path(value)
    if not candidate.is_absolute():
        return value
    try:
        return candidate.relative_to(ROOT).as_posix()
    except ValueError:
        return candidate.as_posix()


def _suppression_matches(
    entry: dict[str, Any], mode: str, rule: str, path: str, fingerprint: str
) -> bool:
    """Return whether *entry* suppresses this finding."""
    return (
        entry["mode"] in (mode, "any")
        and entry["rule_id"] == rule
        and entry["path"] == path
        and fingerprint in entry["fingerprints"]
    )


def adjudicate(
    findings_by_mode: dict[str, list[dict[str, Any]]],
    suppressions: list[dict[str, Any]],
) -> tuple[list[tuple[str, dict[str, Any]]], list[dict[str, Any]]]:
    """Return unsuppressed findings and suppressions that matched nothing."""
    matched: set[int] = set()
    unsuppressed: list[tuple[str, dict[str, Any]]] = []
    for mode, findings in findings_by_mode.items():
        for finding in findings:
            fingerprint, rule, path = _finding_identity(finding)
            match = next(
                (
                    index
                    for index, entry in enumerate(suppressions)
                    if _suppression_matches(entry, mode, rule, path, fingerprint)
                ),
                None,
            )
            if match is None:
                unsuppressed.append((mode, finding))
            else:
                matched.add(match)
    stale = [entry for index, entry in enumerate(suppressions) if index not in matched]
    return unsuppressed, stale


def main(argv: list[str] | None = None) -> int:
    """Run the secret-scanning gate and return its process exit code."""
    args = sys.argv[1:] if argv is None else argv
    target = Path(args[0]) if args else ROOT
    if not target.is_dir():
        raise GateError(f"scan target not found: {target}")
    executable = acquire_gitleaks()
    tree_findings = scan(executable, target, CONFIG_PATH)
    history_findings = scan_history(executable, ROOT, CONFIG_PATH)
    suppressions = _load_suppressions(SUPPRESSIONS_PATH)
    unsuppressed, stale = adjudicate(
        {"tree": tree_findings, "history": history_findings}, suppressions
    )
    if stale:
        for entry in stale:
            print(
                f"stale secret suppression: {entry['path']} ({entry['rule_id']}) "
                "matched no finding",
                file=sys.stderr,
            )
        print(f"stale secret suppressions: {len(stale)}", file=sys.stderr)
        return EXIT_INFRASTRUCTURE
    if unsuppressed:
        for mode, finding in unsuppressed:
            rule = finding.get("RuleID", "<unknown>")
            path = _repo_relative_path(finding.get("File", "<unknown>"))
            line = finding.get("StartLine", "?")
            print(f"{mode} {path}:{line}: {rule}", file=sys.stderr)
        print(f"secret scanning findings: {len(unsuppressed)}", file=sys.stderr)
        return EXIT_FINDINGS
    print(
        "secret scanning gate clean: "
        f"tree={len(tree_findings)} history={len(history_findings)} "
        f"suppressed={len(suppressions)}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as error:
        print(f"secret scanning gate infrastructure failure: {error}", file=sys.stderr)
        raise SystemExit(EXIT_INFRASTRUCTURE) from None
