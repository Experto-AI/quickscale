#!/usr/bin/env python3
"""
Blocking secret-scanning gate for committed credentials (SA202).

Acquires a checksum-pinned ``gitleaks`` release and scans the repository
working tree for committed secrets.  The scan is scoped by
``scripts/gitleaks.toml``, which extends the default ruleset and records every
verified false positive with a reason and a value-scoped exemption: the theme's
``viteAssetRouting`` test fixture carries the RFC 6455 Sec-WebSocket-Key sample
nonce, the billing view tests assign the placeholder value
``PHASE_6A_PUBLISHABLE_KEY`` to a settings env-var name, and the generated
``.quickscale/`` scratch tree is never committed.

Failure policy: any unsuppressed finding fails the gate as exit 1.  A missing or
unsupported host, a download or checksum failure, an unsafe archive, an
unexpected tool version, or a report that disagrees with the process exit status
fails closed as infrastructure exit 2.  Secrets are never silently skipped.
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
COMMAND_TIMEOUT = 600.0
# Distinguishes "the scanner found leaks" from an infrastructure failure.
FINDINGS_EXIT_CODE = 7
EXIT_FINDINGS = 1
EXIT_INFRASTRUCTURE = 2


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


def scan(executable: Path, target: Path, config: Path) -> list[dict[str, Any]]:
    """Scan ``target`` and return the adjudicated finding records."""
    if not config.is_file():
        raise GateError(f"gitleaks config not found: {config}")
    completed = _run(
        [
            str(executable),
            "dir",
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


def main(argv: list[str] | None = None) -> int:
    """Run the secret-scanning gate and return its process exit code."""
    args = sys.argv[1:] if argv is None else argv
    target = Path(args[0]) if args else ROOT
    if not target.is_dir():
        raise GateError(f"scan target not found: {target}")
    report = scan(acquire_gitleaks(), target, CONFIG_PATH)
    if report:
        for finding in report:
            rule = finding.get("RuleID", "<unknown>")
            path = finding.get("File", "<unknown>")
            line = finding.get("StartLine", "?")
            print(f"{path}:{line}: {rule}", file=sys.stderr)
        print(f"secret scanning findings: {len(report)}", file=sys.stderr)
        return EXIT_FINDINGS
    print(f"secret scanning gate clean: {target}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as error:
        print(f"secret scanning gate infrastructure failure: {error}", file=sys.stderr)
        raise SystemExit(EXIT_INFRASTRUCTURE) from None
