#!/usr/bin/env python3
r"""
SA117 — Exact scope guard.

Validates that every path in a working set is present in the SA117 allowlist
(``sa117_scope.json``) and reports any paths that are not allowed.

NUL-path safety
---------------
The module validates that candidate paths do not contain embedded NUL
(``\\x00``) characters, which are invalid in most filesystems and can be
used to truncate path comparisons.  Paths are compared as normalised
POSIX-style relative paths with leading ``./`` stripped.

Modes
-----
* **worktree** (default): read paths from ``git ls-files`` (or a provided
  file list) and verify every tracked path is either allowed or exempt
  (outside the allowlist scope).  Exit 0 when no violations found.

* **emit**: print the allowlist (optionally filtered by phase) to stdout
  as newline-delimited paths.  Useful for piped comparisons or CI matrix
  generation.

* **lock**: verify that the set of paths in the current worktree matches
  the allowlist exactly (no additions, no removals).  When ``--candidate``
  is provided, run the poetry.lock version guard instead: verify every
  local module package entry in the candidate lock file is pinned to the
  expected version and write evidence JSON to ``--output``.

Exit codes
----------
0 — pass (no violations or successful emit)
1 — semantic rejection (an allowlist path is missing or an extra path is
    present; or poetry.lock version guard found unexpected entries)
2 — malformed invocation, evidence, or configuration

Examples
--------
    # Default worktree check
    poetry run python scripts/check_sa117_scope.py

    # Check a specific path list
    poetry run python scripts/check_sa117_scope.py worktree \\
        --paths scripts/foo.py scripts/bar.py

    # Emit all allowed paths
    poetry run python scripts/check_sa117_scope.py emit

    # Emit paths for a specific phase
    poetry run python scripts/check_sa117_scope.py emit --phase 1-implement

    # Lock check (path-set)
    poetry run python scripts/check_sa117_scope.py lock

    # Lock check (poetry.lock version guard)
    poetry run python scripts/check_sa117_scope.py lock \\
        --baseline-ref b276fb28486e8474474ed71457c915d5d28399ca \\
        --candidate poetry.lock \\
        --expected-version 0.87.0 \\
        --output /tmp/lock-guard.json

"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tomllib
from pathlib import Path
from typing import Any, Final

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SCOPE_JSON: Final[str] = "sa117_scope.json"
SCOPE_DIR: Final[Path] = Path(__file__).resolve().parent

DEFAULT_SCOPE_PATH: Final[Path] = SCOPE_DIR / SCOPE_JSON

# ---------------------------------------------------------------------------
# NUL-path safety
# ---------------------------------------------------------------------------


def _validate_no_nul(path: str) -> str:
    """
    Raise ``ValueError`` if *path* contains an embedded NUL character.

    NUL is the only byte value invalid in POSIX filenames; its presence in a
    path string is a strong indicator of truncation-attempt or encoding error.
    """
    if "\x00" in path:
        raise ValueError(f"path contains embedded NUL character: {path!r}")
    return path


def _normalise(path: str) -> str:
    """
    Return a normalised, NUL-free, POSIX-relative path.

    Strips leading ``./``, normalises separators, resolves ``..``
    components, and validates NUL absence.

    The function does **not** resolve symlinks or check filesystem
    existence — it is a purely lexical normalisation.
    """
    cleaned = _validate_no_nul(path)
    # Strip leading ./
    while cleaned.startswith("./"):
        cleaned = cleaned[2:]
    # Normalise forward slashes on all platforms
    cleaned = cleaned.replace("\\", "/")
    # Collapse repeated slashes
    parts = [p for p in cleaned.split("/") if p and p != "."]
    # Resolve .. components lexically
    resolved: list[str] = []
    for part in parts:
        if part == "..":
            if resolved:
                resolved.pop()
        else:
            resolved.append(part)
    return "/".join(resolved)


# ---------------------------------------------------------------------------
# Allowlist loading
# ---------------------------------------------------------------------------


def load_scope(scope_path: Path = DEFAULT_SCOPE_PATH) -> list[dict[str, Any]]:
    """
    Load and return the SA117 allowlist from *scope_path*.

    Each entry is a dict with ``path``, ``phase``, and ``notes`` keys.

    Raises ``FileNotFoundError``, ``json.JSONDecodeError``, or
    ``ValueError`` if the file is missing, malformed, or has unexpected
    content.
    """
    if not scope_path.is_file():
        raise FileNotFoundError(f"SA117 scope file not found: {scope_path}")

    with scope_path.open("rb") as fh:
        data = json.load(fh)

    if not isinstance(data, dict) or "paths" not in data:
        raise ValueError(f"SA117 scope file missing 'paths' key: {scope_path}")

    paths = data["paths"]
    if not isinstance(paths, list):
        raise ValueError(f"SA117 scope 'paths' is not a list: {scope_path}")

    for entry in paths:
        if not isinstance(entry, dict):
            raise ValueError(f"SA117 scope entry is not a dict: {entry}")
        if "path" not in entry:
            raise ValueError(f"SA117 scope entry missing 'path': {entry}")

    return paths


def build_allowlist(
    scope_entries: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """
    Build a ``{normalised_path: entry}`` lookup from *scope_entries*.

    Raises ``ValueError`` if two entries normalise to the same path.
    """
    lookup: dict[str, dict[str, Any]] = {}
    for entry in scope_entries:
        norm = _normalise(entry["path"])
        if norm in lookup:
            raise ValueError(
                f"duplicate path in SA117 scope: {entry['path']!r} (normalised: {norm!r})"
            )
        lookup[norm] = entry
    return lookup


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _read_git_tracked_files(repo_root: Path) -> list[str]:
    """Return the list of git-tracked files under *repo_root*."""
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git ls-files failed (exit {result.returncode}): {result.stderr}")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Mode: worktree
# ---------------------------------------------------------------------------


def _filter_scope_paths(
    paths: set[str],
    *,
    scripts_only: bool,
) -> set[str]:
    """
    Filter *paths* to only those under scripts/ when *scripts_only* is True.

    Returns the filtered (or full) set.  Never mutates the input set.
    """
    if scripts_only:
        return {p for p in paths if p.startswith("scripts/")}
    return paths


def mode_worktree(
    scope_path: Path,
    *,
    paths: list[str] | None = None,
    repo_root: Path | None = None,
    allow_untracked: bool = False,
    scripts_only: bool = False,
) -> int:
    """
    Verify that the candidate path set is in the allowlist.

    The candidate set (*paths*) is the set of changed/modified files being
    reviewed.  When *paths* is None (not provided), the function requires
    explicit ``--paths`` — there is no automatic fallback to all git-tracked
    files.

    When *scripts_only* is True (Phase 1 backward compat), only paths under
    ``scripts/`` are compared; all other paths are ignored.  When False
    (default, full scope), every path in the allowlist is compared.

    Returns 0 on pass, 1 on semantic rejection (candidate paths not in the
    allowlist), 2 on configuration/evidence errors.
    """
    try:
        entries = load_scope(scope_path)
        allowlist = build_allowlist(entries)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # The candidate set is the changed-file list being reviewed.  Explicit
    # paths are required — no automatic fallback to git ls-files.
    if paths is None:
        print(
            "ERROR: --paths is required for worktree mode (baseline-to-candidate "
            "comparison).  Pass the changed file set explicitly.",
            file=sys.stderr,
        )
        return 2

    # Normalise all candidate paths
    try:
        current_norm: set[str] = {_normalise(p) for p in paths}
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Optionally filter to scripts/ only (Phase 1 backward compat).
    current_filtered = _filter_scope_paths(current_norm, scripts_only=scripts_only)

    allowed_norm: set[str] = set(allowlist.keys())
    allowed_filtered = _filter_scope_paths(allowed_norm, scripts_only=scripts_only)

    # In worktree mode we only flag violations that are in the current set
    # but NOT in the allowlist (unlisted paths).
    violations: list[str] = [p for p in sorted(current_filtered) if p not in allowed_filtered]

    if violations:
        print("SA117 scope violations (paths not in allowlist):", file=sys.stderr)
        for v in sorted(violations):
            print(f"  {v}", file=sys.stderr)
        return 1

    scope_label = "scripts/ paths" if scripts_only else "all paths"
    print(f"SA117 worktree check: all {scope_label} are in the allowlist.")
    return 0


# ---------------------------------------------------------------------------
# Mode: emit
# ---------------------------------------------------------------------------


def mode_emit(
    scope_path: Path,
    *,
    phase: str | None = None,
) -> int:
    """
    Print the allowlist (optionally filtered by *phase*) to stdout.

    Returns 0 on success, 2 on configuration errors.
    """
    try:
        entries = load_scope(scope_path)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    for entry in entries:
        if phase is None or entry.get("phase") == phase:
            print(_normalise(entry["path"]))

    return 0


# ---------------------------------------------------------------------------
# Mode: lock
# ---------------------------------------------------------------------------


def mode_lock(
    scope_path: Path,
    *,
    paths: list[str] | None = None,
    repo_root: Path | None = None,
    scripts_only: bool = False,
) -> int:
    """
    Verify that the current set of paths matches the allowlist exactly.

    When *paths* is provided, it is compared against the allowlist.
    Otherwise git-tracked files from *repo_root* are compared.

    When *scripts_only* is True (Phase 1 backward compat), only paths under
    ``scripts/`` are compared.

    Returns 0 on exact match, 1 on mismatch (additions or removals),
    2 on configuration/evidence errors.
    """
    try:
        entries = load_scope(scope_path)
        allowlist = build_allowlist(entries)
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # Resolve candidate paths
    candidate_paths: list[str]
    if paths is not None:
        candidate_paths = paths
    else:
        root = repo_root or SCOPE_DIR.parent
        try:
            candidate_paths = _read_git_tracked_files(root)
        except (RuntimeError, subprocess.TimeoutExpired) as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2

    # Normalise both sets and compare
    try:
        current_norm: set[str] = {_normalise(p) for p in candidate_paths}
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    allowed_norm: set[str] = set(allowlist.keys())

    current_filtered = _filter_scope_paths(current_norm, scripts_only=scripts_only)
    allowed_filtered = _filter_scope_paths(allowed_norm, scripts_only=scripts_only)

    missing = allowed_filtered - current_filtered
    extra = current_filtered - allowed_filtered

    if missing or extra:
        if missing:
            print("LOCK MISMATCH — missing from worktree:", file=sys.stderr)
            for p in sorted(missing):
                print(f"  {p}", file=sys.stderr)
        if extra:
            print("LOCK MISMATCH — extra in worktree:", file=sys.stderr)
            for p in sorted(extra):
                print(f"  {p}", file=sys.stderr)
        return 1

    scope_label = "scripts/ paths" if scripts_only else "all paths"
    print(f"SA117 lock check: {scope_label} match allowlist exactly.")
    return 0


# ---------------------------------------------------------------------------
# Poetry.lock version guard (SA117 Phase 2)
# ---------------------------------------------------------------------------

# The 12 SA117-scoped module packages expected in poetry.lock
_LOCKED_MODULE_PACKAGES: Final[list[str]] = [
    "quickscale-module-analytics",
    "quickscale-module-auth",
    "quickscale-module-backups",
    "quickscale-module-billing",
    "quickscale-module-blog",
    "quickscale-module-crm",
    "quickscale-module-forms",
    "quickscale-module-listings",
    "quickscale-module-notifications",
    "quickscale-module-orgs",
    "quickscale-module-social",
    "quickscale-module-storage",
]


def mode_lock_poetry(
    candidate_path: Path,
    expected_version: str,
    output_path: Path,
    baseline_ref: str | None = None,
) -> int:
    """
    Verify module package versions in ``poetry.lock``.

    Verify that every local module package entry in the candidate
    ``poetry.lock`` is pinned to *expected_version*.

    When *baseline_ref* is provided, also compare the candidate lock
    against the baseline ref's lock to detect unexpected drift beyond
    the twelve module version lines.

    Writes evidence JSON to *output_path*.

    Returns 0 on success, 1 on version mismatch, 2 on errors.
    """
    if not candidate_path.is_file():
        print(f"ERROR: candidate lock file not found: {candidate_path}", file=sys.stderr)
        return 2

    try:
        lock_data = tomllib.loads(candidate_path.read_text())
    except tomllib.TOMLDecodeError as exc:
        print(f"ERROR: failed to parse candidate lock: {exc}", file=sys.stderr)
        return 2

    packages = lock_data.get("package", [])
    if not isinstance(packages, list):
        print("ERROR: candidate lock missing 'package' list", file=sys.stderr)
        return 2

    violations: list[dict[str, str]] = []
    found_count = 0

    for pkg in packages:
        name: str = pkg.get("name", "")
        if name not in _LOCKED_MODULE_PACKAGES:
            continue
        found_count += 1
        pkg_version: str = pkg.get("version", "")
        if pkg_version != expected_version:
            violations.append(
                {
                    "package": name,
                    "expected_version": expected_version,
                    "actual_version": pkg_version,
                }
            )

    if found_count < len(_LOCKED_MODULE_PACKAGES):
        missing = [
            n for n in _LOCKED_MODULE_PACKAGES if not any(p.get("name") == n for p in packages)
        ]
        for m in missing:
            print(f"  MISSING: {m}", file=sys.stderr)
        print(
            f"ERROR: found {found_count} of {len(_LOCKED_MODULE_PACKAGES)} "
            f"expected module packages in lock",
            file=sys.stderr,
        )
        if not violations:
            return 1

    if violations:
        print("VERSION LOCK MISMATCH — module package version drift:", file=sys.stderr)
        for v in violations:
            print(
                f"  {v['package']}: expected {v['expected_version']}, got {v['actual_version']}",
                file=sys.stderr,
            )
        result_status = "mismatch"
        exit_code = 1
    else:
        print(
            f"SA117 poetry.lock version guard: all {found_count} module "
            f"packages pinned to {expected_version}."
        )
        result_status = "ok"
        exit_code = 0

    # Build evidence payload
    evidence: dict[str, Any] = {
        "tool": "check_sa117_scope.py lock --candidate",
        "status": result_status,
        "expected_version": expected_version,
        "candidate": str(candidate_path),
        "module_packages_found": found_count,
        "module_packages_expected": len(_LOCKED_MODULE_PACKAGES),
        "violations": violations,
        "baseline_ref": baseline_ref,
    }

    if baseline_ref:
        # Check if git baseline ref exists
        try:
            subprocess.run(
                ["git", "rev-parse", "--verify", baseline_ref],
                capture_output=True,
                text=True,
                timeout=15,
            )
            evidence["baseline_resolved"] = True
        except (subprocess.SubprocessError, FileNotFoundError):
            evidence["baseline_resolved"] = False
            print(
                f"Warning: baseline ref {baseline_ref!r} could not be resolved — "
                "skipping baseline comparison.",
                file=sys.stderr,
            )

    # Write evidence
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(evidence, indent=2) + "\n")
        print(f"Evidence written to {output_path}")
    except OSError as exc:
        print(f"ERROR: failed to write evidence to {output_path}: {exc}", file=sys.stderr)
        return 2

    return exit_code


# ---------------------------------------------------------------------------
# Lock-diff mode: validate git ref, load baseline lock, detect unauthorized
# drift beyond allowed module version changes (SA117-CR-006)
# ---------------------------------------------------------------------------


def _resolve_git_ref(ref: str, repo_path: Path | None = None) -> str | None:
    """
    Resolve *ref* to a full 40-char SHA, or return None if unresolvable.

    When *repo_path* is provided, git commands run relative to that path.
    """
    cwd = str(repo_path) if repo_path else None
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--verify", ref],
            capture_output=True,
            text=True,
            timeout=15,
            cwd=cwd,
        )
        if result.returncode == 0:
            return result.stdout.strip()
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _read_lock_from_git_ref(ref: str, repo_path: Path | None = None) -> str | None:
    """
    Read the content of ``poetry.lock`` at the given git *ref*.

    Uses ``git show <ref>:poetry.lock``.  Returns None when the ref or the
    lock file at that ref cannot be read.

    When *repo_path* is provided, git commands run relative to that path.
    """
    cwd = str(repo_path) if repo_path else None
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:poetry.lock"],
            capture_output=True,
            text=True,
            timeout=30,
            cwd=cwd,
        )
        if result.returncode == 0:
            return result.stdout
        return None
    except (subprocess.SubprocessError, FileNotFoundError):
        return None


def _load_lock_package_map(lock_toml: str) -> dict[str, str]:
    """Parse a poetry.lock TOML string and return a ``{name: version}`` map."""
    data = tomllib.loads(lock_toml)
    packages = data.get("package", [])
    if not isinstance(packages, list):
        return {}
    return {
        pkg.get("name", ""): pkg.get("version", "") for pkg in packages if isinstance(pkg, dict)
    }


def mode_verify_lock_diff(
    candidate_path: Path,
    *,
    baseline_ref: str,
    expected_version: str | None = None,
    output_path: Path | None = None,
) -> int:
    """
    Validate git ref, load baseline lock, detect unauthorized drift.

    Steps:
    1. Validate *baseline_ref* resolves to a full SHA.
    2. Load the baseline ``poetry.lock`` from that ref.
    3. Load the candidate ``poetry.lock`` from *candidate_path*.
    4. Compare baseline vs candidate: the 12 module packages must all be
       at *expected_version* (when provided); any OTHER package change
       between baseline and candidate is flagged as unauthorized drift.
    5. Write evidence JSON to *output_path* (or a temp path when None).

    Returns 0 on clean (no unauthorized drift), 1 on drift or mismatch,
    2 on errors.
    """
    if not candidate_path.is_file():
        print(f"ERROR: candidate lock file not found: {candidate_path}", file=sys.stderr)
        return 2

    # Derive repo root from candidate path parent — this ensures git commands
    # run against the repo containing the candidate lock file.
    repo_root = candidate_path.resolve().parent

    # Step 1: validate git ref
    resolved_sha = _resolve_git_ref(baseline_ref, repo_path=repo_root)
    if resolved_sha is None:
        print(
            f"ERROR: baseline ref {baseline_ref!r} could not be resolved "
            f"(git rev-parse --verify failed).",
            file=sys.stderr,
        )
        return 2

    # Step 2: load baseline lock from ref
    baseline_toml = _read_lock_from_git_ref(baseline_ref, repo_path=repo_root)
    if baseline_toml is None:
        print(
            f"ERROR: could not read poetry.lock at ref {baseline_ref!r} "
            f"(git show {baseline_ref}:poetry.lock failed).",
            file=sys.stderr,
        )
        return 2

    # Step 3: load candidate lock
    try:
        candidate_toml = candidate_path.read_text()
        candidate_data = tomllib.loads(candidate_toml)
    except (tomllib.TOMLDecodeError, OSError) as exc:
        print(f"ERROR: failed to parse candidate lock: {exc}", file=sys.stderr)
        return 2

    # Build baseline and candidate package maps
    try:
        baseline_packages = _load_lock_package_map(baseline_toml)
    except tomllib.TOMLDecodeError as exc:
        print(f"ERROR: failed to parse baseline lock: {exc}", file=sys.stderr)
        return 2

    candidate_packages_raw = candidate_data.get("package", [])
    if not isinstance(candidate_packages_raw, list):
        print("ERROR: candidate lock missing 'package' list", file=sys.stderr)
        return 2
    candidate_packages: dict[str, str] = {}
    for pkg in candidate_packages_raw:
        name = pkg.get("name", "")
        version = pkg.get("version", "")
        if isinstance(name, str) and isinstance(version, str):
            candidate_packages[name] = version

    # Step 4: compare
    module_version_violations: list[dict[str, str]] = []
    unauthorized_drift: list[dict[str, str]] = []
    all_names = sorted(set(baseline_packages) | set(candidate_packages))

    for name in all_names:
        base_ver = baseline_packages.get(name)
        cand_ver = candidate_packages.get(name)

        # Skip packages that are in neither (shouldn't happen)
        if base_ver is None and cand_ver is None:
            continue

        # New package in candidate only — unauthorized unless it's a
        # module package that was never expected.
        if base_ver is None:
            if name not in _LOCKED_MODULE_PACKAGES:
                unauthorized_drift.append(
                    {
                        "package": name,
                        "change": "added",
                        "baseline_version": "",
                        "candidate_version": cand_ver or "",
                    }
                )
            continue

        # Removed from candidate — unauthorized unless it's a module
        # package that happens to be missing.
        if cand_ver is None:
            if name not in _LOCKED_MODULE_PACKAGES:
                unauthorized_drift.append(
                    {
                        "package": name,
                        "change": "removed",
                        "baseline_version": base_ver,
                        "candidate_version": "",
                    }
                )
            continue

        # Version changed
        if base_ver != cand_ver:
            if name in _LOCKED_MODULE_PACKAGES:
                # Module packages: expected to change to expected_version
                if expected_version is not None and cand_ver != expected_version:
                    module_version_violations.append(
                        {
                            "package": name,
                            "expected_version": expected_version,
                            "actual_version": cand_ver,
                        }
                    )
            else:
                # Non-module package changed — unauthorized drift
                unauthorized_drift.append(
                    {
                        "package": name,
                        "change": "version_changed",
                        "baseline_version": base_ver,
                        "candidate_version": cand_ver,
                    }
                )

    # Report findings
    any_failure = False

    if unauthorized_drift:
        print("UNAUTHORIZED LOCK DRIFT — packages changed beyond module versions:", file=sys.stderr)
        for d in unauthorized_drift:
            print(
                f"  {d['package']}: {d['change']} "
                f"({d.get('baseline_version', '')} -> {d.get('candidate_version', '')})",
                file=sys.stderr,
            )
        any_failure = True

    if module_version_violations:
        print("MODULE VERSION LOCK MISMATCH:", file=sys.stderr)
        for v in module_version_violations:
            print(
                f"  {v['package']}: expected {v['expected_version']}, got {v['actual_version']}",
                file=sys.stderr,
            )
        any_failure = True

    if not any_failure:
        print(
            f"SA117 lock-diff: baseline {resolved_sha[:12]} vs candidate — no unauthorized drift.",
        )

    # Build evidence
    evidence: dict[str, Any] = {
        "tool": "check_sa117_scope.py lock-diff",
        "status": "drift" if any_failure else "clean",
        "baseline_ref": baseline_ref,
        "baseline_sha": resolved_sha,
        "candidate": str(candidate_path),
        "expected_version": expected_version,
        "module_version_violations": module_version_violations,
        "unauthorized_drift": unauthorized_drift,
        "baseline_packages_count": len(baseline_packages),
        "candidate_packages_count": len(candidate_packages),
    }

    output = output_path or Path("/tmp/sa117-lock-diff-evidence.json")
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(evidence, indent=2) + "\n")
        print(f"Evidence written to {output}")
    except OSError as exc:
        print(f"ERROR: failed to write evidence to {output}: {exc}", file=sys.stderr)
        return 2

    return 1 if any_failure else 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    """Return the argument parser for the SA117 scope checker."""
    parser = argparse.ArgumentParser(
        prog="check_sa117_scope.py",
        description="SA117 exact scope guard — verify paths against the allowlist.",
    )
    parser.add_argument(
        "--scope",
        type=Path,
        default=DEFAULT_SCOPE_PATH,
        help=f"Path to sa117_scope.json (default: {DEFAULT_SCOPE_PATH})",
    )

    subparsers = parser.add_subparsers(dest="mode", required=True)

    # --- worktree ---
    wt = subparsers.add_parser("worktree", help="Check worktree paths against allowlist.")
    wt.add_argument(
        "--paths",
        nargs="*",
        default=None,
        help="Explicit list of paths to check (default: git ls-files).",
    )
    wt.add_argument(
        "--allow-untracked",
        action="store_true",
        help="Do not flag untracked files (only relevant with default path detection).",
    )
    wt.add_argument(
        "--scripts-only",
        action="store_true",
        help="Only check paths under scripts/ (Phase 1 backward compat).",
    )

    # --- emit ---
    em = subparsers.add_parser("emit", help="Print allowlist paths.")
    em.add_argument("--phase", default=None, help="Filter paths by phase label.")

    # --- lock ---
    lk = subparsers.add_parser(
        "lock",
        help="Verify worktree matches allowlist or run poetry.lock version guard.",
    )
    lk.add_argument(
        "--paths",
        nargs="*",
        default=None,
        help="Explicit list of paths to verify.",
    )
    lk.add_argument(
        "--baseline-ref",
        default=None,
        help="Git ref (commit hash) of the baseline poetry.lock for drift comparison.",
    )
    lk.add_argument(
        "--candidate",
        type=Path,
        default=None,
        help="Path to candidate poetry.lock (enables poetry.lock version guard mode).",
    )
    lk.add_argument(
        "--expected-version",
        default=None,
        help="Expected version string for module packages in poetry.lock.",
    )
    lk.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for evidence JSON output (poetry.lock version guard mode).",
    )
    lk.add_argument(
        "--scripts-only",
        action="store_true",
        help="Only check paths under scripts/ (Phase 1 backward compat).",
    )

    # --- lock-diff ---
    ld = subparsers.add_parser(
        "lock-diff",
        help="Validate git ref, load baseline poetry.lock, detect unauthorized drift.",
    )
    ld.add_argument(
        "--baseline-ref",
        required=True,
        help="Git ref (commit hash) of the baseline poetry.lock.",
    )
    ld.add_argument(
        "--candidate",
        type=Path,
        required=True,
        help="Path to candidate poetry.lock.",
    )
    ld.add_argument(
        "--expected-version",
        default=None,
        help="Expected version string for module packages (optional).",
    )
    ld.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Path for evidence JSON output.",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the SA117 scope checker."""
    parser = _build_parser()
    args = parser.parse_args(argv)

    mode = args.mode

    if mode == "worktree":
        return mode_worktree(
            args.scope,
            paths=args.paths,
            allow_untracked=args.allow_untracked,
            scripts_only=getattr(args, "scripts_only", False),
        )
    elif mode == "emit":
        return mode_emit(args.scope, phase=args.phase)
    elif mode == "lock":
        # Dispatch to poetry.lock version guard when --candidate is provided
        if args.candidate is not None:
            if not args.expected_version:
                print(
                    "ERROR: --expected-version is required when --candidate is provided",
                    file=sys.stderr,
                )
                return 2
            output_path: Path = args.output or Path("/tmp/sa117-poetry-lock-guard.json")
            return mode_lock_poetry(
                candidate_path=args.candidate,
                expected_version=args.expected_version,
                output_path=output_path,
                baseline_ref=args.baseline_ref,
            )
        return mode_lock(
            args.scope,
            paths=args.paths,
            scripts_only=getattr(args, "scripts_only", False),
        )
    elif mode == "lock-diff":
        output_path: Path = args.output or Path("/tmp/sa117-lock-diff-evidence.json")
        return mode_verify_lock_diff(
            candidate_path=args.candidate,
            baseline_ref=args.baseline_ref,
            expected_version=args.expected_version,
            output_path=output_path,
        )
    else:
        print(f"ERROR: unknown mode: {mode}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
