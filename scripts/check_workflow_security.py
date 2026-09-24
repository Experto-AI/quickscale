#!/usr/bin/env python3
"""
Blocking workflow-security gate for the publishing supply chain (SA202).

Runs ``zizmor`` over the GitHub Actions workflows and fails on every finding at
medium severity and medium confidence or above.  That floor is exactly the
SA202 contract:

* ``unpinned-uses`` (high severity, high confidence) -- every third-party
  ``uses:`` reference must be pinned to a full commit SHA, so a moved tag or
  branch cannot change what runs inside a job that holds a publishing identity.
* ``excessive-permissions`` (medium severity, medium confidence) -- a job that
  inherits an undeclared token scope.  That audit is satisfied by a job-level
  ``permissions:`` block, so the gate additionally requires a top-level
  ``permissions:`` declaration in every workflow it scans: the SA202 contract is
  a workflow-level block, not merely a bounded one somewhere in the file.

``--no-ignores`` disables zizmor's ignore mechanism -- inline
``# zizmor: ignore[...]`` comments and any ``zizmor.yml`` ignore rules -- so the
pinning and permissions contract cannot be suppressed from inside the
repository it governs.

Advisory findings below the floor (the low-confidence ``cache-poisoning`` and
``artipacked`` notes, the informational ``template-injection`` and
``superfluous-actions`` notes) do not fail this gate.

Failure policy: a missing ``zizmor`` executable, an unparseable report, or a
report that disagrees with the process exit status fails closed as
infrastructure exit 2.  Findings fail as exit 1.  A clean tree exits 0.

``zizmor`` is a Poetry dev dependency pinned to ``1.30.1``; a worktree whose
``.venv`` predates that pin (or was never re-synced after ``poetry.lock``
changed) is missing it. This gate itself fails immediately on that, before
running zizmor, with the exact remediation (``poetry install``) rather than a
bare "not found on PATH" -- and `make check` additionally preflights this same
resolution as its very first step, so an unsynced worktree fails before lint,
typecheck, or any of the other repository gates run. A resolved executable
outside the current Python environment (a stray global install shadowing the
unsynced Poetry env) is flagged as an advisory warning, since it may not be
the pinned version.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import sysconfig
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_WORKFLOWS = ROOT / ".github" / "workflows"
EXECUTABLE = "zizmor"
PINNED_VERSION = "1.30.1"  # Must track the `zizmor` pin in pyproject.toml.
INSTALL_REMEDIATION = "poetry install"
# The two named conditions of SA202 live at or above this floor; everything
# below it is advisory and must not block the pipeline.
FLOOR_ARGS = ("--min-severity", "medium", "--min-confidence", "medium")
# Inline `# zizmor: ignore[...]` comments must not be able to suppress the
# pinning or permissions contract.
IGNORE_ARGS = ("--no-ignores",)
COMMAND_TIMEOUT = 180.0
EXIT_FINDINGS = 1
EXIT_INFRASTRUCTURE = 2
WORKFLOW_SUFFIXES = (".yml", ".yaml")


class GateError(RuntimeError):
    """An expected gate failure, reported as infrastructure exit 2."""


def _finding_path(finding: dict[str, Any]) -> str:
    """Return the file a finding points at, or a stable placeholder."""
    for location in finding.get("locations", []):
        symbolic = location.get("symbolic") if isinstance(location, dict) else None
        key = symbolic.get("key") if isinstance(symbolic, dict) else None
        local = key.get("Local") if isinstance(key, dict) else None
        verbatim = local.get("verbatim_path") if isinstance(local, dict) else None
        if isinstance(verbatim, str) and verbatim:
            return verbatim
    return "<unknown file>"


def _finding_position(finding: dict[str, Any]) -> str:
    """Return ``row:column`` for a finding, or a stable placeholder."""
    for location in finding.get("locations", []):
        concrete = location.get("concrete") if isinstance(location, dict) else None
        point = (
            concrete.get("location", {}).get("start_point") if isinstance(concrete, dict) else None
        )
        if isinstance(point, dict) and "row" in point and "column" in point:
            return f"{point['row']}:{point['column']}"
    return "?"


def _workflow_files(target: Path) -> list[Path]:
    """Return the workflow files the gate must inspect."""
    if target.is_dir():
        files = sorted(
            path
            for path in target.rglob("*")
            if path.is_file() and path.suffix in WORKFLOW_SUFFIXES
        )
    else:
        files = [target]
    if not files:
        raise GateError(f"no workflow files found under {target}")
    return files


def _missing_top_level_permissions(target: Path) -> list[Path]:
    """
    Return workflows that declare no top-level ``permissions:`` block.

    zizmor's ``excessive-permissions`` audit is satisfied by a job-level block,
    so the workflow-level requirement SA202 states is enforced here instead.
    """
    missing: list[Path] = []
    for path in _workflow_files(target):
        try:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError) as exc:
            raise GateError(f"could not parse {path}: {exc}") from exc
        if not isinstance(document, dict):
            raise GateError(f"{path} is not a workflow mapping")
        if "permissions" not in document:
            missing.append(path)
    return missing


def _resolve_zizmor() -> str | None:
    """Locate ``zizmor`` on ``PATH``."""
    return shutil.which(EXECUTABLE)


def _warn_if_outside_project_environment(executable: str) -> None:
    """
    Flag a resolved ``zizmor`` that is not this interpreter's own environment.

    ``shutil.which`` returns the first ``PATH`` hit, which can silently be a
    stray global install (e.g. from ``pipx`` or a system package) rather than
    the pinned version from ``pyproject.toml``. That masks a Poetry
    environment that was never (re)installed with the pinned dependency --
    the run still succeeds, but against an unverified, potentially different
    zizmor version. This is advisory, not blocking: a correctly pinned
    non-Poetry environment (e.g. the repo-local ``.venv`` fallback used
    elsewhere in this repo) also resolves outside the environment's own
    scripts directory only when invoked without ``poetry run``.

    ``sysconfig.get_path("scripts")`` is used instead of
    ``Path(sys.executable).parent`` because the latter follows the
    interpreter symlink: a Poetry venv's ``python`` is typically a symlink to
    a pyenv/uv-managed base interpreter, so resolving it lands outside the
    venv entirely and this check would warn even for a correctly synced
    Poetry install with zizmor sitting right next to it in ``.venv/bin``.
    """
    project_scripts_dir = Path(sysconfig.get_path("scripts")).resolve()
    resolved = Path(executable).resolve()
    if resolved.parent != project_scripts_dir:
        print(
            f"⚠ zizmor resolved from {resolved}, outside this interpreter's "
            f"environment ({project_scripts_dir}). The {EXECUTABLE} "
            f"{PINNED_VERSION} pinned by pyproject.toml may not be installed "
            f"here — if findings look stale or wrong, run: {INSTALL_REMEDIATION}",
            file=sys.stderr,
        )


def _run_zizmor(executable: str, workflows: Path) -> tuple[int, str, str]:
    try:
        completed = subprocess.run(
            [
                executable,
                "--no-progress",
                "--format",
                "json",
                *FLOOR_ARGS,
                *IGNORE_ARGS,
                str(workflows),
            ],
            capture_output=True,
            text=True,
            timeout=COMMAND_TIMEOUT,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise GateError(f"could not run {EXECUTABLE}: {exc}") from exc
    return completed.returncode, completed.stdout, completed.stderr


def main(argv: list[str] | None = None) -> int:
    """Run the workflow-security gate and return its process exit code."""
    args = sys.argv[1:] if argv is None else argv
    preflight_only = "--preflight" in args
    if preflight_only:
        args = [arg for arg in args if arg != "--preflight"]
    executable = _resolve_zizmor()
    if executable is None:
        raise GateError(
            f"{EXECUTABLE} executable not found on PATH. pyproject.toml pins "
            f"{EXECUTABLE} {PINNED_VERSION} as a Poetry dev dependency — run: {INSTALL_REMEDIATION}"
        )
    if preflight_only:
        # `make check`'s first step: prove zizmor resolves before running any
        # other (slower) repository gate, so an unsynced worktree fails here
        # instead of after lint/typecheck/the other dozen check-* targets.
        _warn_if_outside_project_environment(executable)
        print(f"zizmor preflight ok: {executable}")
        return 0
    workflows = Path(args[0]) if args else DEFAULT_WORKFLOWS
    if not workflows.exists():
        raise GateError(f"workflow target not found: {workflows}")
    _warn_if_outside_project_environment(executable)
    returncode, stdout, stderr = _run_zizmor(executable, workflows)
    try:
        findings = json.loads(stdout)
    except json.JSONDecodeError as exc:
        detail = stderr.strip() or stdout.strip()[:200]
        raise GateError(f"unparseable {EXECUTABLE} report: {exc}; output: {detail}") from exc
    if not isinstance(findings, list):
        raise GateError(f"unexpected {EXECUTABLE} report shape: {type(findings).__name__}")
    if findings:
        for finding in findings:
            if not isinstance(finding, dict):
                raise GateError(f"unexpected {EXECUTABLE} finding shape")
            ident = finding.get("ident", "<unknown>")
            desc = str(finding.get("desc", "")).strip()
            location = f"{_finding_path(finding)}:{_finding_position(finding)}"
            print(f"{location}: {ident}: {desc}", file=sys.stderr)
        print(f"workflow security findings: {len(findings)}", file=sys.stderr)
        return EXIT_FINDINGS
    if returncode != 0:
        raise GateError(f"{EXECUTABLE} exited {returncode} with an empty report")
    missing = _missing_top_level_permissions(workflows)
    if missing:
        for path in missing:
            print(
                f"{path}: missing-top-level-permissions: no workflow-level permissions block",
                file=sys.stderr,
            )
        print(f"workflow security findings: {len(missing)}", file=sys.stderr)
        return EXIT_FINDINGS
    print(f"workflow security gate clean: {workflows}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except GateError as error:
        print(f"workflow security gate infrastructure failure: {error}", file=sys.stderr)
        raise SystemExit(EXIT_INFRASTRUCTURE) from None
