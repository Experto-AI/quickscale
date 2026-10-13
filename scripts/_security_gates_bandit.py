"""
Bandit static-analysis scanning for the security gate facade.

The scan contract is preserved from the pre-split ``check_security_gates``
module: the pinned Bandit version and category inventory are proven against
the installed tool, every shipped module's ``src`` root is discovered from its
manifest, and findings are normalized to an exact code identity before
adjudication.  Collaborators resolve through the support and adjudication
siblings at call time (decisions.md, Split-Facade Seams).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

import _security_gates_adjudication as _adjudication
import _security_gates_support as _support

BANDIT_VERSION = "1.9.4"

MODULES_ROOT = _support.ROOT / "quickscale_modules"

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


def _discover_module_source_roots() -> tuple[Path, ...]:
    """
    Return every shipped module's ``src`` root, discovered from its manifest.

    A module directory is one carrying a ``module.yml`` (Module Conventions
    rule 18); an incomplete directory fails closed instead of silently
    dropping out of the Bandit scan.
    """
    if not MODULES_ROOT.is_dir():
        raise _support.GateError(f"missing module workspace: {MODULES_ROOT}")
    roots: list[Path] = []
    for entry in sorted(MODULES_ROOT.iterdir()):
        if not entry.is_dir() or entry.name.startswith("."):
            continue
        if not (entry / "module.yml").is_file():
            raise _support.GateError(f"module directory without module.yml: {entry}")
        source_root = entry / "src"
        if not source_root.is_dir():
            raise _support.GateError(f"module directory without src: {entry}")
        roots.append(source_root)
    if not roots:
        raise _support.GateError(f"no shipped modules discovered under {MODULES_ROOT}")
    return tuple(roots)


def _source_roots() -> tuple[Path, ...]:
    """Return the Bandit scan roots: the fixed packages and every module's src."""
    return (
        _support.ROOT / "quickscale" / "src",
        _support.ROOT / "quickscale_cli" / "src",
        _support.ROOT / "quickscale_core" / "src",
        _support.ROOT / "quickscale_devtools" / "src",
        *_discover_module_source_roots(),
    )


def _bandit_project(path: Path) -> str:
    relative = path.relative_to(_support.ROOT)
    return relative.parts[0] if relative.parts else "root"


def _bandit_fingerprint(project: str, path: str, test_id: str, line: int) -> str:
    value = f"bandit|{project}|{path}|{test_id}|line={line}"
    return hashlib.sha256(value.encode()).hexdigest()


def _bandit_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("results")
    if not isinstance(findings, list) or any(not isinstance(item, dict) for item in findings):
        raise _support.GateError("Bandit JSON did not contain a valid results list")
    normalized: list[dict[str, Any]] = []
    for finding in findings:
        path = Path(str(finding.get("filename", ""))).resolve()
        try:
            relative = path.relative_to(_support.ROOT).as_posix()
        except ValueError as exc:
            raise _support.GateError(f"Bandit finding is outside the repository: {path}") from exc
        test_id = finding.get("test_id")
        line = finding.get("line_number")
        if not isinstance(test_id, str) or not isinstance(line, int):
            raise _support.GateError("Bandit finding lacks an exact code identity")
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
    for source_root in _source_roots():
        if not source_root.is_dir():
            raise _support.GateError(f"missing Bandit source root: {source_root}")
        for path in source_root.rglob("*.py"):
            if not EXCLUDED_PARTS.intersection(path.parts):
                files.append(path)
    if not files:
        raise _support.GateError("no Bandit source files were selected")
    return sorted(files)


def _bandit_scan() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    version = _support.run_command(["bandit", "--version"])
    if version.returncode != 0:
        raise _support.GateError(f"Bandit version command failed: {version.stderr.strip()}")
    match = re.search(r"bandit\s+([0-9]+\.[0-9]+\.[0-9]+)", version.stdout)
    if not match or match.group(1) != BANDIT_VERSION:
        raise _support.GateError(f"unexpected Bandit version: {version.stdout.strip()}")
    help_result = _support.run_command(["bandit", "--help"])
    if help_result.returncode != 0:
        raise _support.GateError(f"Bandit help command failed: {help_result.stderr.strip()}")
    help_output = help_result.stdout
    available = set(re.findall(r"\bB[0-9]{3}\b", help_output))
    missing = sorted(set(BANDIT_TESTS) - available)
    if missing:
        raise _support.GateError(f"Bandit plugin inventory is incomplete: {', '.join(missing)}")
    source_files = _source_files()
    command = [
        "bandit",
        "-q",
        "-r",
        *[str(root) for root in _source_roots()],
        "--format",
        "json",
        "--ignore-nosec",
        "--tests",
        ",".join(BANDIT_TESTS),
        "--exclude",
        ",".join(f"*/{part}/*" for part in sorted(EXCLUDED_PARTS)),
    ]
    result = _support.run_command(command)
    if result.returncode not in (0, 1):
        raise _support.GateError(
            f"Bandit infrastructure failure: exit {result.returncode}: {result.stderr.strip()}"
        )
    report = _support.strict_json(result.stdout, source="Bandit")
    if not isinstance(report, dict):
        raise _support.GateError("Bandit JSON root must be an object")
    findings = _bandit_findings(report)
    return findings, {
        "version": BANDIT_VERSION,
        "source_files": len(source_files),
        "tests": list(BANDIT_TESTS),
        "ignore_nosec": True,
    }


def static_gate() -> int:
    findings, evidence = _bandit_scan()
    unsuppressed, suppressed = _adjudication._adjudicate(findings, executed_scanners={"bandit"})
    if unsuppressed:
        raise _support.FindingsError(json.dumps({"unsuppressed": unsuppressed}, sort_keys=True))
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
