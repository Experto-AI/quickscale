#!/usr/bin/env python3
"""
SA117 scope and lock-drift checks.

The ``worktree``, ``emit``, and path-set ``lock`` modes are retained for the
existing scope workflow.  ``lock-diff`` is the sole lock-drift route: it
validates the complete version inventory on both sides and compares complete
Poetry lock structures after normalising only the twelve approved module
``package.version`` leaves.
"""

# The implementation lives in private ``_sa117_*`` siblings (SA267):
# ``_sa117_scope_contract`` (the fact document and its strict contract),
# ``_sa117_lock_parse`` (version/lock parsing and inventory reads), and
# ``_sa117_lock_diff`` (lock normalisation, structural diffing, and evidence
# writing).  This module owns the mode dispatch, the lock-diff orchestration,
# and the CLI, and re-exports the pre-split surface for unchanged import
# paths, so a test's seam is the sibling that defines the name (decisions.md,
# Split-Facade Seams).

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import argparse as argparse
import ast as ast
import copy as copy
import datetime as datetime
import hashlib as hashlib
import json as json
import os as os
import re as re
import shlex as shlex
import stat as stat
import subprocess as subprocess
import sys
import tempfile as tempfile
import tomllib as tomllib
from collections.abc import Hashable as Hashable
from collections.abc import Mapping as Mapping
from pathlib import Path
from typing import Any as Any
from typing import Final

import yaml as yaml
from yaml.events import AliasEvent as AliasEvent
from yaml.nodes import MappingNode as MappingNode

# Ensure the private siblings are importable whether this file is executed
# directly (``sys.path[0]`` is ``scripts/``) or imported with only the
# repository root on ``sys.path`` (``scripts.check_sa117_scope``).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _sa117_lock_diff import (
    _collect_differences as _collect_differences,
)
from _sa117_lock_diff import (
    _normalise_lock as _normalise_lock,
)
from _sa117_lock_diff import (
    _remove_evidence as _remove_evidence,
)
from _sa117_lock_diff import (
    _write_evidence_atomic as _write_evidence_atomic,
)
from _sa117_lock_parse import (
    _LOCK_VERSION_SENTINEL as _LOCK_VERSION_SENTINEL,
)
from _sa117_lock_parse import (
    _LOCKED_MODULE_PACKAGES as _LOCKED_MODULE_PACKAGES,
)
from _sa117_lock_parse import (
    _MODULE_DISCOVERY_RELATIVE_PATH as _MODULE_DISCOVERY_RELATIVE_PATH,
)
from _sa117_lock_parse import (
    LockDiffError as LockDiffError,
)
from _sa117_lock_parse import (
    _authoritative_module_names as _authoritative_module_names,
)
from _sa117_lock_parse import (
    _candidate_contents as _candidate_contents,
)
from _sa117_lock_parse import (
    _expected_inventory as _expected_inventory,
)
from _sa117_lock_parse import (
    _git_baseline_contents as _git_baseline_contents,
)
from _sa117_lock_parse import (
    _git_top_level as _git_top_level,
)
from _sa117_lock_parse import (
    _inventory_digest as _inventory_digest,
)
from _sa117_lock_parse import (
    _locked_module_packages as _locked_module_packages,
)
from _sa117_lock_parse import (
    _parse_canonical_version as _parse_canonical_version,
)
from _sa117_lock_parse import (
    _parse_inventory as _parse_inventory,
)
from _sa117_lock_parse import (
    _parse_lock_data as _parse_lock_data,
)
from _sa117_lock_parse import (
    _parse_manifest as _parse_manifest,
)
from _sa117_lock_parse import (
    _parse_project_version as _parse_project_version,
)
from _sa117_lock_parse import (
    _parse_python_version as _parse_python_version,
)
from _sa117_lock_parse import (
    _parse_toml as _parse_toml,
)
from _sa117_lock_parse import (
    _parse_version_file as _parse_version_file,
)
from _sa117_lock_parse import (
    _reject_toml_temporal_values as _reject_toml_temporal_values,
)
from _sa117_lock_parse import (
    _resolve_git_ref as _resolve_git_ref,
)
from _sa117_lock_parse import (
    _sha256 as _sha256,
)
from _sa117_lock_parse import (
    _StrictYamlLoader as _StrictYamlLoader,
)
from _sa117_scope_contract import (
    DEFAULT_SCOPE_PATH as DEFAULT_SCOPE_PATH,
)
from _sa117_scope_contract import (
    SCOPE_DIR as SCOPE_DIR,
)
from _sa117_scope_contract import (
    _contract_mode as _contract_mode,
)
from _sa117_scope_contract import (
    _filter_scope_paths as _filter_scope_paths,
)
from _sa117_scope_contract import (
    _json_without_duplicate_keys as _json_without_duplicate_keys,
)
from _sa117_scope_contract import (
    _load_scope_document as _load_scope_document,
)
from _sa117_scope_contract import (
    _normalise as _normalise,
)
from _sa117_scope_contract import (
    _normalise_candidate as _normalise_candidate,
)
from _sa117_scope_contract import (
    _required_inputs as _required_inputs,
)
from _sa117_scope_contract import (
    _tokenise_make_paths as _tokenise_make_paths,
)
from _sa117_scope_contract import (
    _validate_contract as _validate_contract,
)
from _sa117_scope_contract import (
    _validate_no_nul as _validate_no_nul,
)
from _sa117_scope_contract import (
    build_allowlist as build_allowlist,
)
from _sa117_scope_contract import (
    load_scope as load_scope,
)

#: Every name the facade re-exports.  Per decisions.md § Split-Facade Seams a
#: facade re-exports public names only: incidental imported bindings
#: (``argparse``, ``ast``, ``Path``, ...) stay module attributes but are
#: deliberately not part of the wildcard surface.
__all__ = [
    "DEFAULT_EVIDENCE_PATH",
    "DEFAULT_SCOPE_PATH",
    "LockDiffError",
    "SCOPE_DIR",
    "build_allowlist",
    "load_scope",
    "main",
    "mode_emit",
    "mode_lock",
    "mode_verify_lock_diff",
    "mode_worktree",
]

DEFAULT_EVIDENCE_PATH: Final[Path] = Path("/tmp/sa117-lock-diff-evidence.json")


def _read_git_tracked_files(repo_root: Path) -> list[str]:
    """Return tracked paths from a repository."""
    result = subprocess.run(
        ["git", "ls-files"], cwd=repo_root, capture_output=True, text=True, timeout=30
    )
    if result.returncode:
        raise RuntimeError(f"git ls-files failed (exit {result.returncode}): {result.stderr}")
    return [line for line in result.stdout.splitlines() if line]


def mode_worktree(
    scope_path: Path,
    *,
    paths: list[str] | None = None,
    repo_root: Path | None = None,
    allow_untracked: bool = False,
    scripts_only: bool = False,
    profile: str = "direct",
) -> int:
    """Check that candidate paths are members of the allowlist."""
    del repo_root
    try:
        _required_inputs(
            scope_path,
            "worktree",
            profile,
            {
                "paths": paths,
                "allow_untracked": allow_untracked,
                "scripts_only": scripts_only,
            },
        )
        if profile == "make":
            paths = _tokenise_make_paths(paths)
        if not paths:
            raise ValueError(f"paths is required for {profile} worktree mode")
        allowed = build_allowlist(load_scope(scope_path))
        current = {_normalise_candidate(path) for path in paths}
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    violations = sorted(
        _filter_scope_paths(current, scripts_only=scripts_only)
        - _filter_scope_paths(set(allowed), scripts_only=scripts_only)
    )
    if violations:
        print("SA117 scope violations (paths not in allowlist):", file=sys.stderr)
        print("\n".join(f"  {path}" for path in violations), file=sys.stderr)
        return 1
    print("SA117 worktree check: all paths are in the allowlist.")
    return 0


def mode_emit(scope_path: Path, *, phase: str | None = None, profile: str = "direct") -> int:
    """Emit allowlisted paths, optionally filtered by phase."""
    try:
        _required_inputs(scope_path, "emit", profile, {"phase": phase})
        entries = load_scope(scope_path)
        for entry in entries:
            if phase is None or entry.get("phase") == phase:
                print(_normalise(entry["path"]))
    except (FileNotFoundError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def mode_lock(
    scope_path: Path,
    *,
    paths: list[str] | None = None,
    repo_root: Path | None = None,
    scripts_only: bool = False,
    profile: str = "direct",
) -> int:
    """Check that a candidate path set exactly matches the allowlist."""
    try:
        _required_inputs(
            scope_path,
            "lock",
            profile,
            {"paths": paths, "scripts_only": scripts_only},
        )
        if profile == "make":
            paths = _tokenise_make_paths(paths)
        allowed = build_allowlist(load_scope(scope_path))
        current_paths = (
            paths if paths is not None else _read_git_tracked_files(repo_root or SCOPE_DIR.parent)
        )
        current = _filter_scope_paths(
            {_normalise_candidate(path) for path in current_paths}, scripts_only=scripts_only
        )
        expected = _filter_scope_paths(set(allowed), scripts_only=scripts_only)
    except (FileNotFoundError, RuntimeError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    missing = sorted(expected - current)
    extra = sorted(current - expected)
    if missing or extra:
        if missing:
            print("LOCK MISMATCH — missing from worktree:", file=sys.stderr)
            print("\n".join(f"  {path}" for path in missing), file=sys.stderr)
        if extra:
            print("LOCK MISMATCH — extra in worktree:", file=sys.stderr)
            print("\n".join(f"  {path}" for path in extra), file=sys.stderr)
        return 1
    print("SA117 lock check: paths match allowlist exactly.")
    return 0


def mode_verify_lock_diff(
    candidate_path: Path,
    *,
    baseline_ref: str,
    expected_version: str | None = None,
    output_path: Path | None = None,
) -> int:
    """Run the complete fail-closed SA117c lock-diff proof."""
    output = (output_path or DEFAULT_EVIDENCE_PATH).expanduser()
    output_safe_to_remove = False
    try:
        candidate_path = candidate_path.expanduser()
        if candidate_path.name != "poetry.lock":
            raise LockDiffError("candidate must be the repository-root poetry.lock")
        if expected_version is None:
            raise LockDiffError("expected-version is required")
        _parse_canonical_version(expected_version)
        root = candidate_path.parent.resolve()
        module_names = _authoritative_module_names(root)
        module_packages = _locked_module_packages(module_names)
        paths = _expected_inventory(root, module_names)
        output_resolved = output.resolve()
        for path in paths:
            if output_resolved == (root / path).resolve():
                raise LockDiffError(
                    f"evidence output must not resolve to candidate inventory input: {path}"
                )
        output_safe_to_remove = True
        _remove_evidence(output)
        if candidate_path.is_symlink() or not candidate_path.is_file():
            raise LockDiffError("candidate poetry.lock must be a regular non-symlink file")
        git_root = _git_top_level(root)
        if git_root is None:
            raise LockDiffError("candidate root is not a Git repository")
        if git_root != root:
            raise LockDiffError(
                f"candidate root must be the Git top-level repository: {root} != {git_root}"
            )
        resolved_sha = _resolve_git_ref(baseline_ref, repo_path=root)
        if resolved_sha is None:
            raise LockDiffError(
                f"baseline ref {baseline_ref!r} did not resolve to a full commit SHA"
            )
        baseline_contents = _git_baseline_contents(root, resolved_sha, paths)
        candidate_contents = _candidate_contents(root, paths)
        baseline = _parse_inventory(baseline_contents, "baseline", module_names)
        candidate = _parse_inventory(candidate_contents, "candidate", module_names)
        if candidate["values"]["VERSION"] != expected_version:
            raise LockDiffError(
                f"expected-version {expected_version!r} disagrees with candidate VERSION "
                f"{candidate['values']['VERSION']!r}"
            )
        baseline_lock, baseline_leaves = _normalise_lock(baseline["lock"], module_packages)
        candidate_lock, candidate_leaves = _normalise_lock(candidate["lock"], module_packages)
        if baseline_leaves != candidate_leaves:
            raise LockDiffError("baseline and candidate lock leaf inventories differ")
        differences = _collect_differences(baseline_lock, candidate_lock)
        baseline_lock_bytes = baseline_contents["poetry.lock"]
        candidate_lock_bytes = candidate_contents["poetry.lock"]
        baseline_root_digest = _inventory_digest(baseline_contents, paths)
        candidate_root_digest = _inventory_digest(candidate_contents, paths)
        clean = not differences
        evidence: dict[str, Any] = {
            "schema_version": 1,
            "tool": "check_sa117_scope.py lock-diff",
            "status": "clean" if clean else "drift",
            "exit_code": 0 if clean else 1,
            "expected_version": expected_version,
            "baseline": {
                "ref": baseline_ref,
                "resolved_sha": resolved_sha,
                "root": str(root),
                "root_digest": baseline_root_digest,
                "lock_digest": _sha256(baseline_lock_bytes),
                "version": baseline["values"]["VERSION"],
            },
            "candidate": {
                "path": str(candidate_path),
                "root": str(root),
                "root_digest": candidate_root_digest,
                "lock_digest": _sha256(candidate_lock_bytes),
                "version": candidate["values"]["VERSION"],
            },
            "inventory": {
                "files_expected": len(paths),
                "files_parsed": len(candidate_contents),
                "values_expected": len(candidate["values"]),
                "values_parsed": len(candidate["values"]),
                "expected_file_count": len(paths),
                "expected_version_value_count": len(candidate["values"]),
                "baseline_file_count": len(baseline_contents),
                "candidate_file_count": len(candidate_contents),
                "baseline_version_value_count": len(baseline["values"]),
                "candidate_version_value_count": len(candidate["values"]),
                "paths": paths,
            },
            "lock_comparison": {
                "raw_equal": baseline["lock"] == candidate["lock"],
                "normalized_equal": clean,
                "allowed_version_leaves": baseline_leaves,
                "allowed_version_leaf_count": len(baseline_leaves),
                "baseline_package_count": len(baseline["lock"]["package"]),
                "candidate_package_count": len(candidate["lock"]["package"]),
            },
            "differences": differences,
        }
        _write_evidence_atomic(output, evidence)
        if clean:
            print("SA117 lock-diff: clean; normalized lock structures match.")
        else:
            print("SA117 lock-diff: unauthorized lock structure drift detected.", file=sys.stderr)
        print(f"Evidence written to {output}")
        return 0 if clean else 1
    except Exception as exc:  # noqa: BLE001 - command-line checker must never traceback
        print(f"ERROR: {exc}", file=sys.stderr)
        if output_safe_to_remove:
            try:
                output.unlink(missing_ok=True)
            except OSError:
                pass
        return 2


def _build_parser(scope_path: Path = DEFAULT_SCOPE_PATH) -> argparse.ArgumentParser:
    """Build the CLI from the strict JSON mode/option declaration."""
    contract = _load_scope_document(scope_path)["contract"]
    parser = argparse.ArgumentParser(prog="check_sa117_scope.py")
    parser.add_argument("--scope", type=Path, default=scope_path)
    parser.add_argument("--profile", default="direct", help="Caller profile (direct or make).")
    parser.add_argument(
        "--render-make-help",
        action="store_true",
        help="Render the SA117 section consumed by the root Makefile help target.",
    )
    subparsers = parser.add_subparsers(dest="mode", required=False)
    for mode_name, mode in contract["modes"].items():
        subparser = subparsers.add_parser(mode_name, help=mode["help"])
        for option_name, option in mode["options"].items():
            kwargs: dict[str, Any] = {"dest": option_name.replace("-", "_")}
            if option["kind"] == "store_true":
                kwargs["action"] = "store_true"
            elif option["kind"] == "paths":
                kwargs.update(nargs="*", default=None)
            elif option["kind"] == "path":
                kwargs["type"] = Path
                if "default" in option:
                    kwargs["default"] = Path(option["default"])
            else:
                if "default" in option:
                    kwargs["default"] = option["default"]
            subparser.add_argument(option["flag"], help=option["help"], **kwargs)
    return parser


def _requested_scope_path(argv: list[str]) -> Path:
    """Select the fact document before building the parser it defines."""
    selected = DEFAULT_SCOPE_PATH
    for index, argument in enumerate(argv):
        if argument == "--scope":
            if index + 1 >= len(argv):
                raise ValueError("--scope requires a path")
            selected = Path(argv[index + 1])
        elif argument.startswith("--scope="):
            selected = Path(argument.partition("=")[2])
    return selected


def _render_make_help(scope_path: Path = DEFAULT_SCOPE_PATH) -> None:
    """Render only the SA117 help block; Make owns placement in its help text."""
    contract = _load_scope_document(scope_path)["contract"]
    modes = contract["modes"]
    print("SA117 scope / publication gates:")
    print("  make sa117-check PATHS='...'      - " + modes["worktree"]["help"])
    print("  make sa117-emit                   - " + modes["emit"]["help"])
    print("  make sa117-lock PATHS='...'       - " + modes["lock"]["help"])
    print("  make sa117-lock-diff              - " + modes["lock-diff"]["help"])
    print("  make sa117-capture VERSION=X PHASE=Y - Capture publication evidence")
    print("  make sa117-verify EVIDENCE=path   - Verify publication evidence")
    print("  make sa117-authorize VERSION=X DIGEST=D - Authorize a publication")
    print("  make sa117-rollback TOKEN=T DIGEST=D - Roll back a prior authorization")
    print("  make sa117-apply MODULE=M TARGET=T EXEC=E ARGV=A - Execute and verify a module apply")
    print("  make sa117-check-origin MODULE=M DECLARED=O EXPECTED=E - Check origin map consistency")
    print("  make sa117-check-containers TARGET=T - Check for zero container/volume configuration")


def main(argv: list[str] | None = None) -> int:
    try:
        arguments = list(sys.argv[1:] if argv is None else argv)
        scope_path = _requested_scope_path(arguments)
        args = _build_parser(scope_path).parse_args(arguments)
        if args.render_make_help:
            _render_make_help(args.scope)
            return 0
        if args.mode is None:
            raise ValueError("a checker mode is required")
        profile_values = vars(args)
        _required_inputs(args.scope, args.mode, args.profile, profile_values)
        if args.mode == "worktree":
            return mode_worktree(
                args.scope,
                paths=args.paths,
                allow_untracked=args.allow_untracked,
                scripts_only=args.scripts_only,
                profile=args.profile,
            )
        if args.mode == "emit":
            return mode_emit(args.scope, phase=args.phase, profile=args.profile)
        if args.mode == "lock":
            return mode_lock(
                args.scope, paths=args.paths, scripts_only=args.scripts_only, profile=args.profile
            )
        if args.mode == "lock-diff":
            return mode_verify_lock_diff(
                args.candidate,
                baseline_ref=args.baseline_ref,
                expected_version=args.expected_version,
                output_path=args.output,
            )
        raise ValueError(f"unsupported checker mode: {args.mode!r}")
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
