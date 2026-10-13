#!/usr/bin/env python3
"""
Require an adoption step for generated-project contract changes.

The watched template set is derived from the generator's authoritative emission
mapping (:func:`quickscale_core.generator.get_generator_emission_mapping`), not
from a hand-listed path set, so every template the generator emits into a
generated project — settings templates, ``pyproject.toml.j2``,
``OPERATIONS.md.j2``, ``start.sh.j2``, ``Dockerfile.j2``, theme files — joins
the rule without a second edit here.  A deleted emitted template stays watched
while it is gone, because removing a generated file is also a contract change.

Every non-merge commit in the selected range that changes a watched template
must also change the project contract declaration
``quickscale_core/src/quickscale_core/data/project_contract.yml`` and declare a
step id the parent did not declare, so a template contract change can never
ship without a fresh adoption step (editing existing prose, or the declaration
alone, would leave already-adopted projects passing enforcement).  A commit
that changes the generator package is evaluated with that revision's own
generator code, so a code change that starts, stops, or reroutes an emitted
file is a watched contract change even when no template path changed.

A commit that changes a module manifest's ``contract_vintage`` block must give
the changed step a new id: the same id with changed text (or a removed id) is a
violation, while a fresh id is a new identity.  Module manifests are the
authoritative source manifests, ``quickscale_modules/<name>/module.yml``, and
their bundled snapshots under ``quickscale_core/src/.../data/manifests/``.  A
new id must also be unused by every other declaration: adopted ids share one
namespace in applied state, so a colliding id would let a project that adopted
the other step pass the new text.  Merge resolutions are compared against
every parent.

The rule applies from the commit that introduces the declaration onward: the
introduction is a monotonic baseline, so a commit that predates it is exempt
(historical template changes do not block a release pull request) and deleting
the declaration later cannot switch enforcement back off.  Merge commits are
checked where the resolution changed a template against every parent, so a
change inherited from one side is not blamed on the merge author; a
reintroduced id never counts as new.  Every merge is also checked for ids the
merged tree declares in two sources, because a clean merge can combine a
collision that neither branch introduced on its own.

The range base is selected, in order, from ``--base-ref``,
``PROJECT_VINTAGE_BASE_REF``, the GitHub event payload, ``GITHUB_BASE_REF``, or
``HEAD^`` for a local one-commit check.  ``--head-ref`` defaults to ``HEAD``.
``--staged`` checks the index instead of a commit range, for pre-commit; it
covers the same template and manifest rules but does not compare the emission
mapping (a staged tree has no revision to execute), so the range check is the
binding one for generator-code changes.

Exit codes:
    0 - every relevant commit declares a fresh adoption step id where required
    1 - a generated-project contract change lacks a fresh step id (the project
        declaration for emitted templates and emission-mapping changes, or the
        changed module manifest for a module step)
    2 - Git or input failure; the gate fails closed
"""

# The implementation lives in private ``_vintage_*`` siblings (SA267):
# ``_vintage_git`` (git plumbing, ref selection, and ancestry),
# ``_vintage_emission`` (the emission mapping and watched-template
# derivation), and ``_vintage_manifest`` (manifest vintages, declaration ids,
# and the identity rules).  This module owns the violation walkers, the
# staged-index walkers, the report, and the CLI, and re-exports the pre-split
# surface for unchanged import paths, so a test's seam is the sibling that
# defines the name (decisions.md, Split-Facade Seams).

# ruff: noqa: E402 — the sys.path bootstrap must precede the sibling imports.

from __future__ import annotations

import argparse as argparse
import io as io
import json as json
import os as os
import re as re
import subprocess as subprocess
import sys
import tarfile as tarfile
import tempfile as tempfile
from collections.abc import Callable as Callable
from dataclasses import dataclass as dataclass
from pathlib import Path

import yaml as yaml

# Ensure the private siblings are importable whether this file is executed
# directly (``sys.path[0]`` is ``scripts/``) or imported with only the
# repository root on ``sys.path`` (``scripts.check_project_contract_vintage``).
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

from _vintage_emission import (
    _EMIT_SOURCES_SNIPPET as _EMIT_SOURCES_SNIPPET,
)
from _vintage_emission import (
    _EMITTED_TEMPLATE_SOURCES_AT as _EMITTED_TEMPLATE_SOURCES_AT,
)
from _vintage_emission import (
    _REVISION_EMISSION_MAPPINGS as _REVISION_EMISSION_MAPPINGS,
)
from _vintage_emission import (
    _WATCHED_TEMPLATE_PATHS as _WATCHED_TEMPLATE_PATHS,
)
from _vintage_emission import (
    GENERATOR_PACKAGE_ROOT as GENERATOR_PACKAGE_ROOT,
)
from _vintage_emission import (
    PACKAGE_ROOT as PACKAGE_ROOT,
)
from _vintage_emission import (
    TEMPLATE_ROOT as TEMPLATE_ROOT,
)
from _vintage_emission import (
    _emitted_sources_from_mapping as _emitted_sources_from_mapping,
)
from _vintage_emission import (
    _emitted_template_sources_at as _emitted_template_sources_at,
)
from _vintage_emission import (
    _generator_emission_mapping as _generator_emission_mapping,
)
from _vintage_emission import (
    _generator_paths as _generator_paths,
)
from _vintage_emission import (
    _revision_emission_mapping as _revision_emission_mapping,
)
from _vintage_emission import (
    _revision_emission_mapping_changed as _revision_emission_mapping_changed,
)
from _vintage_emission import (
    _revision_emitted_sources as _revision_emitted_sources,
)
from _vintage_emission import (
    _revision_mappings_available as _revision_mappings_available,
)
from _vintage_emission import (
    _template_contract_paths as _template_contract_paths,
)
from _vintage_emission import (
    _watched_template_paths as _watched_template_paths,
)
from _vintage_git import (
    _FILES_AT_COMMIT as _FILES_AT_COMMIT,
)
from _vintage_git import (
    REPO_ROOT as REPO_ROOT,
)
from _vintage_git import (
    ZERO_SHA_RE as ZERO_SHA_RE,
)
from _vintage_git import (
    VintageError as VintageError,
)
from _vintage_git import (
    _commit_paths as _commit_paths,
)
from _vintage_git import (
    _event_base_ref as _event_base_ref,
)
from _vintage_git import (
    _file_at_commit as _file_at_commit,
)
from _vintage_git import (
    _file_in_index as _file_in_index,
)
from _vintage_git import (
    _first_parent as _first_parent,
)
from _vintage_git import (
    _git as _git,
)
from _vintage_git import (
    _git_bytes as _git_bytes,
)
from _vintage_git import (
    _is_ancestor as _is_ancestor,
)
from _vintage_git import (
    _merge_resolution_paths as _merge_resolution_paths,
)
from _vintage_git import (
    _parents as _parents,
)
from _vintage_git import (
    _path_exists_at as _path_exists_at,
)
from _vintage_git import (
    _path_exists_in_index as _path_exists_in_index,
)
from _vintage_git import (
    _range_base as _range_base,
)
from _vintage_git import (
    _resolve_commit as _resolve_commit,
)
from _vintage_git import (
    _select_base_ref as _select_base_ref,
)
from _vintage_git import (
    _staged_paths as _staged_paths,
)
from _vintage_git import (
    _tree_entry_exists as _tree_entry_exists,
)
from _vintage_manifest import (
    _DECLARATION_IDS_AT as _DECLARATION_IDS_AT,
)
from _vintage_manifest import (
    _EVER_PRESENT_MANIFEST_PATHS as _EVER_PRESENT_MANIFEST_PATHS,
)
from _vintage_manifest import (
    _MANIFEST_PATHS_AT as _MANIFEST_PATHS_AT,
)
from _vintage_manifest import (
    _MANIFEST_VINTAGES_AT as _MANIFEST_VINTAGES_AT,
)
from _vintage_manifest import (
    _MODULE_DECLARED_IDS_AT as _MODULE_DECLARED_IDS_AT,
)
from _vintage_manifest import (
    DECLARATION_PATH as DECLARATION_PATH,
)
from _vintage_manifest import (
    MODULE_MANIFEST_FILENAME as MODULE_MANIFEST_FILENAME,
)
from _vintage_manifest import (
    MODULE_MANIFEST_ROOTS as MODULE_MANIFEST_ROOTS,
)
from _vintage_manifest import (
    ModuleVintage as ModuleVintage,
)
from _vintage_manifest import (
    Violation as Violation,
)
from _vintage_manifest import (
    _declaration_id_collision as _declaration_id_collision,
)
from _vintage_manifest import (
    _declaration_ids_at as _declaration_ids_at,
)
from _vintage_manifest import (
    _declared_step_ids as _declared_step_ids,
)
from _vintage_manifest import (
    _declared_step_ids_at as _declared_step_ids_at,
)
from _vintage_manifest import (
    _declares_new_step as _declares_new_step,
)
from _vintage_manifest import (
    _declares_vintage as _declares_vintage,
)
from _vintage_manifest import (
    _foreign_declared_step_ids as _foreign_declared_step_ids,
)
from _vintage_manifest import (
    _historical_manifest_ids as _historical_manifest_ids,
)
from _vintage_manifest import (
    _historical_step_ids as _historical_step_ids,
)
from _vintage_manifest import (
    _index_declared_module_ids as _index_declared_module_ids,
)
from _vintage_manifest import (
    _index_declared_step_ids as _index_declared_step_ids,
)
from _vintage_manifest import (
    _introduction_commit as _introduction_commit,
)
from _vintage_manifest import (
    _is_module_manifest_path as _is_module_manifest_path,
)
from _vintage_manifest import (
    _manifest_identity_violation as _manifest_identity_violation,
)
from _vintage_manifest import (
    _manifest_ids_at as _manifest_ids_at,
)
from _vintage_manifest import (
    _manifest_module_name as _manifest_module_name,
)
from _vintage_manifest import (
    _manifest_paths_at as _manifest_paths_at,
)
from _vintage_manifest import (
    _manifest_paths_present_at as _manifest_paths_present_at,
)
from _vintage_manifest import (
    _manifest_vintage_at as _manifest_vintage_at,
)
from _vintage_manifest import (
    _merge_combined_id_violations as _merge_combined_id_violations,
)
from _vintage_manifest import (
    _merge_declaration_id_collision as _merge_declaration_id_collision,
)
from _vintage_manifest import (
    _merge_declares_new_step as _merge_declares_new_step,
)
from _vintage_manifest import (
    _merge_manifest_violation as _merge_manifest_violation,
)
from _vintage_manifest import (
    _merged_tree_declared_ids as _merged_tree_declared_ids,
)
from _vintage_manifest import (
    _module_declared_ids_at as _module_declared_ids_at,
)
from _vintage_manifest import (
    _module_manifest_violation as _module_manifest_violation,
)
from _vintage_manifest import (
    _module_vintage as _module_vintage,
)
from _vintage_manifest import (
    _source_reference_path as _source_reference_path,
)
from _vintage_manifest import (
    _tree_declared_module_ids_at as _tree_declared_module_ids_at,
)

#: Every name the facade re-exports.  Per decisions.md § Split-Facade Seams a
#: facade re-exports public names only: incidental imported bindings
#: (``argparse``, ``io``, ``Path``, ...) stay module attributes but are
#: deliberately not part of the wildcard surface.
__all__ = [
    "DECLARATION_PATH",
    "GENERATOR_PACKAGE_ROOT",
    "MODULE_MANIFEST_FILENAME",
    "MODULE_MANIFEST_ROOTS",
    "ModuleVintage",
    "PACKAGE_ROOT",
    "REPO_ROOT",
    "TEMPLATE_ROOT",
    "VintageError",
    "Violation",
    "ZERO_SHA_RE",
    "main",
]


def _merge_commit_violations(
    commit: str, parents: tuple[str, ...], pre_baseline: bool
) -> list[Violation]:
    """Violations for one merge commit, against every parent."""
    violations: list[Violation] = []
    # A merge resolution can introduce contract bytes that no
    # non-merge commit carries; inherited changes are not resolutions.
    resolution_paths = _merge_resolution_paths(commit)
    template_candidates = any(path.startswith(TEMPLATE_ROOT) for path in resolution_paths)
    template_paths = _template_contract_paths(
        resolution_paths,
        emitted_before=lambda path: any(
            path in _revision_emitted_sources(parent) for parent in parents
        ),
        emitted_after=lambda path: path in _revision_emitted_sources(commit),
        checked_out_fallback=template_candidates
        and not _revision_mappings_available((*parents, commit)),
    )
    mapping_changed = bool(_generator_paths(resolution_paths)) and (
        _revision_emission_mapping_changed(commit)
    )
    if (
        (template_paths or mapping_changed)
        and not _merge_declares_new_step(commit, parents)
        and not pre_baseline
    ):
        subject = _git("show", "-s", "--format=%s", commit).strip()
        violations.append(
            Violation(
                commit,
                subject,
                template_paths or _generator_paths(resolution_paths),
                reason="merge resolution with no new adoption step id",
            )
        )
    if not pre_baseline:
        violations.extend(_merge_combined_id_violations(commit, parents))
    if not pre_baseline and DECLARATION_PATH in resolution_paths:
        collision = _merge_declaration_id_collision(commit, parents)
        if collision:
            subject = _git("show", "-s", "--format=%s", commit).strip()
            violations.append(
                Violation(
                    commit,
                    subject,
                    (DECLARATION_PATH,),
                    reason="step id collides with another declaration",
                )
            )
    if not pre_baseline:
        for path in resolution_paths:
            if _is_module_manifest_path(path):
                violation = _merge_manifest_violation(commit, path, parents)
                if violation is not None:
                    violations.append(violation)
    return violations


def _contract_change_violation(
    commit: str,
    paths: tuple[str, ...],
    template_paths: tuple[str, ...],
    mapping_changed: bool,
    pre_baseline: bool,
) -> Violation | None:
    """Return the missing-adoption-step violation for one changed contract commit."""
    if not (template_paths or mapping_changed):
        return None
    declared = _declares_vintage(commit, paths)
    if declared and _declares_new_step(commit):
        return None
    if pre_baseline:
        return None
    # Editing the declaration is not enough: a changed contract must declare a
    # new step id, or projects that already recorded the old ids would keep
    # passing enforcement.
    reported = template_paths or _generator_paths(paths)
    if declared:
        reason = "no new adoption step id"
    elif mapping_changed and not template_paths:
        reason = "generator emission mapping changed without a new adoption step id"
    else:
        reason = ""
    subject = _git("show", "-s", "--format=%s", commit).strip()
    return Violation(commit, subject, reported, reason=reason)


def _declaration_collision_violation(
    commit: str, paths: tuple[str, ...], pre_baseline: bool
) -> Violation | None:
    """Return the id-collision violation for a commit that edits the declaration."""
    if pre_baseline or DECLARATION_PATH not in paths:
        return None
    if not _declaration_id_collision(commit):
        return None
    subject = _git("show", "-s", "--format=%s", commit).strip()
    return Violation(
        commit,
        subject,
        (DECLARATION_PATH,),
        reason="step id collides with another declaration",
    )


def _manifest_path_violations(
    commit: str, paths: tuple[str, ...], pre_baseline: bool
) -> list[Violation]:
    """Return the manifest-identity violations among a commit's changed paths."""
    if pre_baseline:
        return []
    violations: list[Violation] = []
    for path in paths:
        if _is_module_manifest_path(path):
            violation = _module_manifest_violation(commit, path)
            if violation is not None:
                violations.append(violation)
    return violations


def _ordinary_commit_violations(
    commit: str, parent: str | None, pre_baseline: bool
) -> list[Violation]:
    """Violations for one non-merge commit, against its first parent."""
    violations: list[Violation] = []
    paths = _commit_paths(commit)
    template_candidates = any(path.startswith(TEMPLATE_ROOT) for path in paths)
    template_paths = _template_contract_paths(
        paths,
        emitted_before=lambda path: (
            parent is not None and path in _revision_emitted_sources(parent)
        ),
        emitted_after=lambda path: path in _revision_emitted_sources(commit),
        checked_out_fallback=template_candidates
        and not _revision_mappings_available((parent, commit)),
    )
    mapping_changed = bool(_generator_paths(paths)) and _revision_emission_mapping_changed(commit)
    contract_violation = _contract_change_violation(
        commit, paths, template_paths, mapping_changed, pre_baseline
    )
    if contract_violation is not None:
        violations.append(contract_violation)
    collision_violation = _declaration_collision_violation(commit, paths, pre_baseline)
    if collision_violation is not None:
        violations.append(collision_violation)
    violations.extend(_manifest_path_violations(commit, paths, pre_baseline))
    return violations


def _violations(base: str, head: str) -> tuple[Violation, ...]:
    commits = tuple(
        line for line in _git("rev-list", "--reverse", f"{base}..{head}").splitlines() if line
    )
    baseline = _introduction_commit(head)
    violations: list[Violation] = []
    for commit in commits:
        pre_baseline = baseline is None or _is_ancestor(commit, baseline)
        parents = _parents(commit)
        if len(parents) > 1:
            violations.extend(_merge_commit_violations(commit, parents, pre_baseline))
        else:
            parent = _first_parent(commit)
            violations.extend(_ordinary_commit_violations(commit, parent, pre_baseline))
    return tuple(violations)


def _staged_manifest_violation(
    path: str,
    *,
    revisions: tuple[str, ...],
    foreign_extra: frozenset[str] = frozenset(),
) -> Violation | None:
    """Fail a staged manifest edit that does not give a changed step a new identity."""
    if not _path_exists_in_index(path):
        return None
    parents = [_manifest_vintage_at(revision, path) for revision in revisions]
    current = _module_vintage(_file_in_index(path), f"{path} in the index")
    if all(parent == current for parent in parents):
        return None
    historical: set[str] = set()
    foreign: frozenset[str] = frozenset()
    foreign |= foreign_extra
    for revision in revisions:
        historical |= _historical_manifest_ids(revision, path)
        foreign |= _foreign_declared_step_ids(revision, path)
    return _manifest_identity_violation(
        parents=parents,
        current=current,
        historical=historical,
        foreign=foreign,
        commit="index",
        subject="staged changes",
        paths=(path,),
    )


def _staged_merge_violations(
    paths: tuple[str, ...], merge_head_sha: str, revisions: tuple[str, ...]
) -> list[Violation]:
    """Violations for a staged merge resolution, against both parents."""
    violations: list[Violation] = []

    def emitted_in_a_compared_revision(path: str) -> bool:
        return any(
            path in _revision_emitted_sources(revision)
            for revision in revisions
            if revision is not None
        )

    # Only resolution edits matter: a path that differs from both parents.
    # A change inherited from one side is not this author's edit to declare.
    changed_vs_merge = set(_git("diff", "--cached", "--name-only", merge_head_sha).splitlines())
    resolution_paths = tuple(path for path in paths if path in changed_vs_merge)
    template_paths = _template_contract_paths(
        resolution_paths,
        emitted_before=emitted_in_a_compared_revision,
        emitted_after=lambda path: path in _watched_template_paths(),
        checked_out_fallback=any(path.startswith(TEMPLATE_ROOT) for path in resolution_paths)
        and not _revision_mappings_available(revisions),
    )
    if template_paths:
        if not _path_exists_in_index(DECLARATION_PATH):
            violations.append(
                Violation(
                    "index",
                    "staged changes",
                    template_paths,
                    reason="the declaration is absent from the merge resolution",
                )
            )
        else:
            historical = _historical_step_ids("HEAD") | _historical_step_ids(merge_head_sha)
            if not _index_declared_step_ids() - historical:
                violations.append(
                    Violation(
                        "index",
                        "staged changes",
                        template_paths,
                        reason="no new adoption step id",
                    )
                )
    if DECLARATION_PATH in resolution_paths and _path_exists_in_index(DECLARATION_PATH):
        historical = set()
        foreign = set(_index_declared_module_ids())
        for revision in revisions:
            historical |= _historical_step_ids(revision)
            foreign |= set(_foreign_declared_step_ids(revision, DECLARATION_PATH))
        if (_index_declared_step_ids() - historical) & foreign:
            violations.append(
                Violation(
                    "index",
                    "staged changes",
                    (DECLARATION_PATH,),
                    reason="step id collides with another declaration",
                )
            )
    for path in resolution_paths:
        if _is_module_manifest_path(path):
            violation = _staged_manifest_violation(
                path,
                revisions=revisions,
                foreign_extra=frozenset(_index_declared_step_ids())
                | _index_declared_module_ids(exclude_module=_manifest_module_name(path)),
            )
            if violation is not None:
                violations.append(violation)
    return violations


def _staged_ordinary_violations(
    paths: tuple[str, ...], revisions: tuple[str, ...]
) -> list[Violation]:
    """Violations for a staged index change against the working parents."""
    violations: list[Violation] = []

    def emitted_in_a_compared_revision(path: str) -> bool:
        return any(
            path in _revision_emitted_sources(revision)
            for revision in revisions
            if revision is not None
        )

    template_paths = _template_contract_paths(
        paths,
        emitted_before=emitted_in_a_compared_revision,
        emitted_after=lambda path: path in _watched_template_paths(),
        checked_out_fallback=any(path.startswith(TEMPLATE_ROOT) for path in paths)
        and not _revision_mappings_available(revisions),
    )
    if template_paths:
        if DECLARATION_PATH in paths:
            if not _path_exists_in_index(DECLARATION_PATH):
                violations.append(
                    Violation(
                        "index",
                        "staged changes",
                        template_paths,
                        reason="the declaration is staged for deletion",
                    )
                )
            elif not _index_declared_step_ids() - _historical_step_ids("HEAD"):
                violations.append(
                    Violation(
                        "index",
                        "staged changes",
                        template_paths,
                        reason="no new adoption step id",
                    )
                )
        else:
            violations.append(Violation("index", "staged changes", template_paths))

    if DECLARATION_PATH in paths and _path_exists_in_index(DECLARATION_PATH):
        collision = (_index_declared_step_ids() - _historical_step_ids("HEAD")) & (
            set(_foreign_declared_step_ids("HEAD", DECLARATION_PATH))
            | set(_index_declared_module_ids())
        )
        if collision:
            violations.append(
                Violation(
                    "index",
                    "staged changes",
                    (DECLARATION_PATH,),
                    reason="step id collides with another declaration",
                )
            )

    for path in paths:
        if _is_module_manifest_path(path):
            violation = _staged_manifest_violation(
                path,
                revisions=revisions,
                foreign_extra=frozenset(_index_declared_step_ids())
                | _index_declared_module_ids(exclude_module=_manifest_module_name(path)),
            )
            if violation is not None:
                violations.append(violation)
    return violations


def _staged_violation() -> tuple[Violation, ...]:
    merge_head = subprocess.run(
        ["git", "rev-parse", "-q", "--verify", "MERGE_HEAD"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    merge_head_sha = merge_head.stdout.strip() if merge_head.returncode == 0 else None

    if _introduction_commit("HEAD") is None:
        # The history predates the declaration; the rule does not apply yet.
        return ()

    paths = _staged_paths()
    revisions = ("HEAD", merge_head_sha) if merge_head_sha is not None else ("HEAD",)

    if merge_head_sha is not None:
        return tuple(_staged_merge_violations(paths, merge_head_sha, revisions))
    return tuple(_staged_ordinary_violations(paths, revisions))


def _report(violations: tuple[Violation, ...]) -> None:
    print(
        "ERROR: [PROJECT_CONTRACT_VINTAGE] generated-project contract changes "
        "without a new adoption step id:",
        file=sys.stderr,
    )
    for violation in violations:
        reason = f" ({violation.reason})" if violation.reason else ""
        print(
            f"  {violation.commit[:12]} {violation.subject}{reason}",
            file=sys.stderr,
        )
        for path in violation.template_paths:
            print(f"    {path}", file=sys.stderr)
    print(
        f"\nDeclare the change in {DECLARATION_PATH} under a new adoption step id "
        "in the same commit, or give the changed module manifest step a new id "
        "(see the SA207/SA211 declaration blocks).",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when a generated-project contract template or a module "
            "manifest adoption step changes without a new step id."
        )
    )
    parser.add_argument("--base-ref", help="Commit or ref to diff from")
    parser.add_argument("--head-ref", default="HEAD", help="Commit or ref to diff to")
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check the staged index instead of a commit range (pre-commit)",
    )
    args = parser.parse_args(argv)

    try:
        if args.staged:
            violations = _staged_violation()
        else:
            base = _resolve_commit(_select_base_ref(args.base_ref))
            head = _resolve_commit(args.head_ref)
            violations = _violations(_range_base(base, head), head)
    except VintageError as error:
        print(f"ERROR: [PROJECT_CONTRACT_VINTAGE] {error}", file=sys.stderr)
        return 2

    if not violations:
        return 0
    _report(violations)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
