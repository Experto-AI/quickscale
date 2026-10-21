#!/usr/bin/env python3
"""
Fail when a module changed after its immutable split tag was sealed.

This is the seal-freshness lane of the publish quality check
(``docs/technical/publish_procedure.md`` Part 1.2).  For every shipped module
it compares the peeled commit of ``splits/<module>-module/<VERSION>`` on
``origin`` with the module's current subtree split.  Freshness follows content
identity: the seal commit's tree must match the current split's tree, so a
seal that reuses a prior release commit for unchanged content still passes
(release_gates_policy.md Rule 6).  The seal commit must be present locally; a
normal tag fetch supplies it, and a missing object fails closed.

A module with no seal tag is unsealed and passes.  A tag whose tree differs
from the current split's tree is **sealed but stale**: the immutable tag no
longer names the module's current content, so publishing the core release
would ship a module that cannot be reproduced from its seal.  The check names
the module and points at the Phase 5 reseal path.

Exit codes:
    0 - every seal tag matches its current split, or the module is unsealed
    1 - at least one seal tag is sealed but stale
    2 - a module's split or seal tag could not be inspected
"""

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent
_CORE_SRC = _SCRIPTS_DIR.parent / "quickscale_core" / "src"
for _import_root in (_CORE_SRC, _SCRIPTS_DIR):
    if str(_import_root) not in sys.path:
        sys.path.insert(0, str(_import_root))
del _import_root

import _publish_module_core as _core
import _publish_module_git as _git
import _publish_module_status as _status

RESEAL_PATH = "docs/technical/publish_procedure.md#phase-5--seal-the-split-tags"


def _read_version(repo_root: Path) -> str:
    version_path = repo_root / "VERSION"
    try:
        version = version_path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise _git.GitError(f"Could not read {version_path}: {exc}") from exc
    if not version:
        raise _git.GitError(f"{version_path} is empty")
    return version


def _inspect(
    repo_root: Path,
    version: str,
    modules: list[str],
    runner: _git.GitRunner,
) -> tuple[list[_status.ModuleSealInspection], list[tuple[str, str]]]:
    """Return inspectable seals and the modules whose seal could not be checked."""
    inspectable: list[_status.ModuleSealInspection] = []
    failures: list[tuple[str, str]] = []
    for module in modules:
        try:
            module_path = _git.resolve_module_path(module)
        except _git.GitError as exc:
            failures.append((module, str(exc)))
            continue
        split_sha = _git._get_local_split_sha(module_path, runner, repo_root=repo_root)
        if split_sha is None:
            failures.append((module, "could not compute the current subtree split"))
            continue
        inspection = _status._inspect_module_seal(
            module, version, split_sha, runner, repo_root=repo_root
        )
        if inspection.state == "unobservable":
            failures.append((module, inspection.error or "seal tag unobservable"))
            continue
        inspectable.append(inspection)
    return inspectable, failures


def _print_inspection(inspection: _status.ModuleSealInspection) -> None:
    if inspection.state == "sealed":
        print(f"  {inspection.module:<16} sealed ({inspection.tag})")
        return
    if inspection.state == "unsealed":
        print(f"  {inspection.module:<16} unsealed ({inspection.tag} absent)")
        return
    print(
        f"  {inspection.module:<16} sealed but stale "
        f"({inspection.tag} -> {inspection.tag_sha[:12]}, "
        f"current split {inspection.split_sha[:12]})"
    )


def _print_failures(failures: list[tuple[str, str]]) -> None:
    print("\nSeal check could not inspect every module:")
    for module, error in failures:
        print(f"  {module}: {error}")
    print(f"\nReseal path: {RESEAL_PATH}")


def run_check(
    repo_root: Path,
    *,
    version: str | None = None,
    modules: list[str] | None = None,
    runner: _git.GitRunner | None = None,
) -> int:
    """Run the seal-freshness check, returning a process exit code."""
    runner = runner or _git.build_publication_git_runner()
    if not _git.is_git_repo(repo_root, runner=runner):
        print(f"ERROR: not a git repository: {repo_root}", file=sys.stderr)
        return 2
    version = version or _read_version(repo_root)
    module_names = list(_core._list_modules() if modules is None else modules)

    print(f"Inspecting module seal tags for QuickScale {version}...")
    inspectable, failures = _inspect(repo_root, version, module_names, runner)
    for inspection in inspectable:
        _print_inspection(inspection)
    stale = [item.module for item in inspectable if item.state == "stale"]

    if failures:
        _print_failures(failures)
        return 1 if stale else 2
    if stale:
        print(f"\nSealed module check FAILED: {' '.join(stale)}")
        print(
            "  A module changed after its seal. Delete each stale remote and local "
            "split tag,\n  republish the split branch, then reseal."
        )
        print(f"  Reseal path: {RESEAL_PATH}")
        return 1
    print("\nEvery seal tag matches its module's current split (or is unsealed).")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=_SCRIPTS_DIR.parent,
        help="Repository root (defaults to the checkout containing this script)",
    )
    args = parser.parse_args(argv)
    try:
        return run_check(args.repo_root.resolve())
    except (_git.GitError, OSError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
