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

``actionlint`` is not a Poetry dependency: the gate requires release
``ACTIONLINT_VERSION`` on ``PATH`` and fails closed with the release link when
the tool is absent or reports another version.  Provisioning it in the hosted
and local CI contexts, and this gate's registry row, are Track 2's surface
(SA306 handover); run the script directly until that row lands::

    poetry run python scripts/check_generated_workflow_lint.py

Exit codes:
    0 - actionlint accepts every rendered workflow
    1 - actionlint reported at least one finding
    2 - infrastructure failure: the render, the tool, or its output is unusable
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ACTIONLINT_VERSION = "1.7.12"
ACTIONLINT_RELEASES_URL = f"https://github.com/rhysd/actionlint/releases/tag/v{ACTIONLINT_VERSION}"
EXECUTABLE = "actionlint"
GENERATED_PROBE_SLUG = "generated-workflow-lint-probe"
COMMAND_TIMEOUT = 180.0
EXIT_FINDINGS = 1
EXIT_INFRASTRUCTURE = 2
WORKFLOW_SUFFIXES = (".yml", ".yaml")
_DIAGNOSTIC_LINE = re.compile(r"^.+?:\d+:\d+: .+$", re.MULTILINE)


class GateError(RuntimeError):
    """An expected gate failure, reported as infrastructure exit 2."""


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


def _require_executable() -> str:
    """Return the resolved actionlint path, or fail closed with the release link."""
    executable = shutil.which(EXECUTABLE)
    if executable is None:
        raise GateError(
            f"{EXECUTABLE} executable not found on PATH. The gate requires "
            f"{EXECUTABLE} {ACTIONLINT_VERSION} — install it from {ACTIONLINT_RELEASES_URL}"
        )
    return executable


def _require_version(executable: str) -> None:
    """Fail closed unless the resolved actionlint is the pinned release."""
    completed = _run_command([executable, "--version"])
    first_line = completed.stdout.splitlines()[0].strip() if completed.stdout else ""
    if completed.returncode != 0 or first_line != ACTIONLINT_VERSION:
        reported = first_line or "<no version>"
        raise GateError(
            f"{EXECUTABLE} must be {ACTIONLINT_VERSION}; {executable} reported "
            f"{reported!r}. Install it from {ACTIONLINT_RELEASES_URL}"
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
    _require_version(executable)
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
