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

A sealed module's published split branch must also still carry the seal's
tree.  The branch is the update transport, so a branch tip that moved after
sealing would make two projects with the same recorded version run different
code; the gate samples the branch tip and compares its tree with the tag's.
A sealed tag without its split branch is equally stale.

A module with no seal tag is unsealed and passes.  A tag whose tree differs
from the current split's tree is **sealed but stale**: the immutable tag no
longer names the module's current content, so publishing the core release
would ship a module that cannot be reproduced from its seal.  The check names
the module and points at the Phase 5 reseal path.

Exit codes:
    0 - every seal tag matches its split branch and current split, or is unsealed
    1 - at least one seal tag is stale or its split branch moved from the seal
    2 - a module's split, branch, or seal tag could not be inspected
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


def _ensure_commit_local(
    repo_root: Path,
    commit: str,
    runner: _git.GitRunner,
) -> None:
    """Make *commit* readable locally, fetching it when the clone lacks it."""
    present = runner.run(
        ["cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if present.returncode == 0:
        return
    fetched = runner.run(
        ["fetch", "--no-tags", "origin", commit],
        cwd=repo_root,
        capture_output=True,
        text=True,
    )
    if fetched.returncode != 0:
        detail = (fetched.stderr or "").strip() or "git fetch failed"
        raise _git.GitError(f"could not fetch commit {commit}: {detail}")


def _inspect_split_branch(
    repo_root: Path,
    inspection: _status.ModuleSealInspection,
    runner: _git.GitRunner,
) -> tuple[str, str | None]:
    """
    Compare a sealed module's published split branch tip with its seal.

    Returns ``("ok", None)``, ``("moved", reason)`` when the branch tip's tree
    differs from the seal, or ``("unobservable", reason)`` when the branch
    cannot be resolved or read.
    """
    branch = _git.resolve_split_branch(inspection.module)
    try:
        branch_sha = _git.resolve_remote_ref("origin", branch, path=repo_root, runner=runner)
    except _git.RemoteBranchAbsentError:
        return (
            "moved",
            f"sealed tag {inspection.tag} has no split branch {branch}",
        )
    except (_git.GitError, ModuleNotFoundError) as exc:
        return ("unobservable", f"could not resolve split branch {branch}: {exc}")

    try:
        _ensure_commit_local(repo_root, branch_sha, runner)
        branch_tree_sha = _git.get_tree_sha(branch_sha, path=repo_root, runner=runner)
    except (_git.GitError, OSError) as exc:
        return ("unobservable", f"could not read split branch {branch} tip: {exc}")

    if branch_tree_sha != inspection.tag_tree_sha:
        return (
            "moved",
            f"split branch {branch} moved from seal {inspection.tag} "
            f"(branch tree {branch_tree_sha[:12]} != tag tree "
            f"{inspection.tag_tree_sha[:12]})",
        )
    return ("ok", None)


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

    branch_moved: list[tuple[str, str]] = []
    for inspection in inspectable:
        if inspection.state == "unsealed":
            continue
        branch_state, branch_reason = _inspect_split_branch(repo_root, inspection, runner)
        if branch_state == "ok":
            continue
        if branch_reason is None:
            branch_reason = "split branch could not be inspected"
        if branch_state == "moved":
            branch_moved.append((inspection.module, branch_reason))
        else:
            failures.append((inspection.module, branch_reason))

    if failures:
        _print_failures(failures)
        return 1 if stale or branch_moved else 2
    if stale or branch_moved:
        failed_modules = sorted({*stale, *(module for module, _ in branch_moved)})
        print(f"\nSealed module check FAILED: {' '.join(failed_modules)}")
        for _module, reason in branch_moved:
            print(f"  {reason}")
        if stale:
            print(
                "  A module changed after its seal. Delete each stale remote and "
                "local split tag,\n  republish the split branch, then reseal."
            )
        else:
            print(
                "  A split branch changed after its seal. Republish the sealed "
                "content or reseal the moved branch."
            )
        print(f"  Reseal path: {RESEAL_PATH}")
        return 1
    print("\nEvery seal tag matches its split branch and current split (or is unsealed).")
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
