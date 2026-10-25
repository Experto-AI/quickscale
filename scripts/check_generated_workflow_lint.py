#!/usr/bin/env python3
"""
Blocking actionlint gate over the generated GitHub workflows (SA306).

The gate renders one fresh ``showcase_react`` project offline (the direct
generator API with ``QS_SKIP_POETRY_LOCK=1``, the same path the sibling
generated-project stations use) and runs ``actionlint`` over every emitted
``.github/workflows/*.yml``.  GitHub validates a workflow's syntax and
expression contexts before it schedules any job, so a workflow actionlint
rejects never starts: the generated ``ci.yml``'s former job-level
``hashFiles(...)`` guard made every generated project's push fail in zero
seconds with no jobs.  ``zizmor`` (``check_workflow_security.py``) owns action
pinning and workflow permissions; this gate owns the workflow-language
contract actionlint defines.

``actionlint`` is not a Poetry dependency: the gate uses the pinned release on
``PATH`` when one is present (its version must match exactly), and otherwise
downloads and checksum-verifies that release into a temporary directory.
Provisioning is therefore automatic in hosted and local CI; an unsupported
host fails closed with the release link::

    poetry run python scripts/check_generated_workflow_lint.py

Exit codes:
    0 - actionlint accepts every rendered workflow
    1 - actionlint reported at least one finding
    2 - infrastructure failure: the render, the tool, or its output is unusable
"""

from __future__ import annotations

import hashlib
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

ACTIONLINT_VERSION = "1.7.12"
ACTIONLINT_RELEASE_URL = f"https://github.com/rhysd/actionlint/releases/tag/v{ACTIONLINT_VERSION}"
ACTIONLINT_DOWNLOAD_URL = (
    f"https://github.com/rhysd/actionlint/releases/download/v{ACTIONLINT_VERSION}"
)
# Official v1.7.12 release-manifest digests for the contributor host contract.
ACTIONLINT_ASSETS: dict[tuple[str, str], tuple[str, str]] = {
    ("Linux", "x86_64"): (
        "actionlint_1.7.12_linux_amd64.tar.gz",
        "8aca8db96f1b94770f1b0d72b6dddcb1ebb8123cb3712530b08cc387b349a3d8",
    ),
    ("Linux", "arm64"): (
        "actionlint_1.7.12_linux_arm64.tar.gz",
        "325e971b6ba9bfa504672e29be93c24981eeb1c07576d730e9f7c8805afff0c6",
    ),
    ("Darwin", "x86_64"): (
        "actionlint_1.7.12_darwin_amd64.tar.gz",
        "5b44c3bc2255115c9b69e30efc0fecdf498fdb63c5d58e17084fd5f16324c644",
    ),
    ("Darwin", "arm64"): (
        "actionlint_1.7.12_darwin_arm64.tar.gz",
        "aba9ced2dee8d27fecca3dc7feb1a7f9a52caefa1eb46f3271ea66b6e0e6953f",
    ),
}
EXECUTABLE = "actionlint"
GENERATED_PROBE_SLUG = "generated-workflow-lint-probe"
COMMAND_TIMEOUT = 180.0
EXIT_FINDINGS = 1
EXIT_INFRASTRUCTURE = 2
WORKFLOW_SUFFIXES = (".yml", ".yaml")
_DIAGNOSTIC_LINE = re.compile(r"^.+?:\d+:\d+: .+$", re.MULTILINE)
_VERSION_LINE = re.compile(r"v?([0-9]+\.[0-9]+\.[0-9]+)")


class GateError(RuntimeError):
    """An expected gate failure, reported as infrastructure exit 2."""


def _asset() -> tuple[str, str]:
    """Return the pinned archive name and digest for this host."""
    system = platform.system()
    machine = platform.machine().lower()
    architecture = {
        "amd64": "x86_64",
        "x86_64": "x86_64",
        "aarch64": "arm64",
        "arm64": "arm64",
    }.get(machine, machine)
    try:
        return ACTIONLINT_ASSETS[(system, architecture)]
    except KeyError as exc:
        raise GateError(
            "unsupported actionlint host "
            f"{system}/{machine}; supported native hosts are "
            "Linux x86_64/arm64 and macOS x86_64/arm64 (Windows uses WSL). "
            f"Install it from {ACTIONLINT_RELEASE_URL}"
        ) from exc


def _download(url: str, destination: Path) -> None:
    """Download one pinned release asset over HTTPS."""
    if urlparse(url).scheme != "https":
        raise GateError("actionlint acquisition URL must use HTTPS")
    try:
        request = Request(url, headers={"User-Agent": "quickscale-actionlint-gate/1"})
        with (
            urlopen(request, timeout=COMMAND_TIMEOUT) as response,
            destination.open("wb") as output,
        ):
            while chunk := response.read(1024 * 1024):
                output.write(chunk)
    except OSError as exc:
        raise GateError(f"actionlint download failed: {exc}") from exc


def _safe_archive_members(archive: tarfile.TarFile, destination: Path) -> list[tarfile.TarInfo]:
    """Reject symlink, link, non-file, and escaping archive members."""
    safe: list[tarfile.TarInfo] = []
    destination = destination.resolve()
    for member in archive.getmembers():
        if member.issym() or member.islnk() or not member.isfile():
            raise GateError(f"unsafe actionlint archive member: {member.name}")
        member_path = (destination / member.name).resolve()
        try:
            member_path.relative_to(destination)
        except ValueError as exc:
            raise GateError(
                f"actionlint archive path escapes extraction directory: {member.name}"
            ) from exc
        safe.append(member)
    return safe


def acquire_actionlint() -> str:
    """Download, verify, extract, and return the pinned actionlint executable."""
    archive_name, expected_sha256 = _asset()
    run_dir = Path(tempfile.mkdtemp(prefix="quickscale-actionlint-"))
    archive_path = run_dir / archive_name
    _download(f"{ACTIONLINT_DOWNLOAD_URL}/{archive_name}", archive_path)
    digest = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if digest != expected_sha256:
        raise GateError(
            f"actionlint archive checksum mismatch: expected {expected_sha256}, got {digest}"
        )
    extract_dir = run_dir / "extract"
    extract_dir.mkdir()
    try:
        with tarfile.open(archive_path, mode="r:gz") as archive:
            for member in _safe_archive_members(archive, extract_dir):
                archive.extract(member, extract_dir)
    except (OSError, tarfile.TarError) as exc:
        raise GateError(f"actionlint archive extraction failed: {exc}") from exc
    executable = extract_dir / EXECUTABLE
    if not executable.is_file() or executable.is_symlink():
        raise GateError("actionlint archive did not contain a regular executable")
    executable.chmod(executable.stat().st_mode | stat.S_IXUSR)
    _require_version(str(executable))
    return str(executable)


def _require_executable() -> str:
    """Return the pinned actionlint, acquiring it when no PATH install exists."""
    executable = shutil.which(EXECUTABLE)
    if executable is None:
        return acquire_actionlint()
    _require_version(executable)
    return executable


def _run_command(
    arguments: list[str], *, cwd: Path | None = None
) -> subprocess.CompletedProcess[str]:
    """Run one actionlint command, translating an execution failure to a GateError."""
    try:
        return subprocess.run(
            arguments,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateError(f"could not run {EXECUTABLE}: {exc}") from exc


def _require_version(executable: str) -> None:
    """Fail closed unless the resolved actionlint is the pinned release."""
    completed = _run_command([executable, "--version"])
    first_line = completed.stdout.splitlines()[0].strip() if completed.stdout else ""
    match = _VERSION_LINE.fullmatch(first_line)
    if completed.returncode != 0 or not match or match.group(1) != ACTIONLINT_VERSION:
        reported = first_line or "<no version>"
        raise GateError(
            f"{EXECUTABLE} must be {ACTIONLINT_VERSION}; {executable} reported "
            f"{reported!r}. Install it from {ACTIONLINT_RELEASE_URL}"
        )


def _render_generated_project(destination: Path) -> Path:
    """Render one fresh showcase_react project offline and return its root."""
    from quickscale_core.generator import ProjectGenerator

    previous = os.environ.get("QS_SKIP_POETRY_LOCK")
    os.environ["QS_SKIP_POETRY_LOCK"] = "1"
    try:
        project = destination / GENERATED_PROBE_SLUG
        ProjectGenerator(theme="showcase_react").generate(GENERATED_PROBE_SLUG, project)
    except Exception as exc:
        raise GateError(f"could not render a generated project: {exc}") from exc
    finally:
        if previous is None:
            os.environ.pop("QS_SKIP_POETRY_LOCK", None)
        else:
            os.environ["QS_SKIP_POETRY_LOCK"] = previous
    return project


def _workflow_files(project: Path) -> list[Path]:
    """Return the workflow files a fresh generated project emitted."""
    workflows = project / ".github" / "workflows"
    if not workflows.is_dir():
        raise GateError("the generated project emitted no .github/workflows directory")
    files = sorted(
        path for path in workflows.iterdir() if path.is_file() and path.suffix in WORKFLOW_SUFFIXES
    )
    if not files:
        raise GateError("the generated project emitted no workflow files")
    return files


def _lint(executable: str, files: list[Path]) -> int:
    """Lint the rendered workflows; return 0 when clean and 1 on findings."""
    completed = _run_command([executable, "-no-color", "-oneline", *(str(path) for path in files)])
    if completed.returncode == 0:
        return 0
    if completed.returncode == 1:
        diagnostics = completed.stdout.strip() or completed.stderr.strip()
        if not diagnostics:
            raise GateError(f"{EXECUTABLE} exited 1 without a diagnostic")
        print(diagnostics, file=sys.stderr)
        print(
            f"generated workflow lint findings: {len(_DIAGNOSTIC_LINE.findall(diagnostics))}",
            file=sys.stderr,
        )
        return EXIT_FINDINGS
    detail = completed.stderr.strip() or completed.stdout.strip()
    raise GateError(f"{EXECUTABLE} exited {completed.returncode}: {detail or 'no output'}")


def main(argv: list[str] | None = None) -> int:
    """Run the generated-workflow actionlint gate and return its exit code."""
    arguments = sys.argv[1:] if argv is None else argv
    if arguments:
        print(f"usage: {Path(__file__).name}", file=sys.stderr)
        return EXIT_INFRASTRUCTURE
    executable = _require_executable()
    with tempfile.TemporaryDirectory(prefix="quickscale-workflow-lint-") as temporary:
        project = _render_generated_project(Path(temporary))
        files = _workflow_files(project)
        if _lint(executable, files):
            return EXIT_FINDINGS
        print(f"generated workflow lint clean: {', '.join(str(path) for path in files)}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as error:
        print(f"generated workflow lint infrastructure failure: {error}", file=sys.stderr)
        raise SystemExit(EXIT_INFRASTRUCTURE) from None
