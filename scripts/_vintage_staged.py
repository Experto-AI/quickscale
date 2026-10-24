"""
Staged-index contract vintage checks for the SA267(d) split.

``--staged`` is the pre-commit path: there is no revision to execute, so the
emission-mapping comparison is unavailable and the index is the after side of
every check.  The facade imports these names from this defining sibling, never
through the facade (decisions.md, Split-Facade Seams).  Behavior is unchanged
from the pre-split module; SA316 added the staged runtime-watch controls.
"""

from __future__ import annotations

import subprocess

from _vintage_emission import (
    TEMPLATE_ROOT,
    _emitted_in_revisions,
    _revision_mappings_available,
    _runtime_contract_paths_staged,
    _template_contract_paths,
    _watched_template_paths,
)
from _vintage_git import _file_in_index, _git, _path_exists_in_index, _staged_paths
from _vintage_manifest import (
    DECLARATION_PATH,
    Violation,
    _foreign_declared_step_ids,
    _historical_manifest_ids,
    _historical_step_ids,
    _index_declared_module_ids,
    _index_declared_step_ids,
    _introduction_commit,
    _is_module_manifest_path,
    _manifest_identity_violation,
    _manifest_module_name,
    _manifest_vintage_at,
    _module_vintage,
    _runtime_watch_introduction,
)


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
    paths: tuple[str, ...],
    merge_head_sha: str,
    revisions: tuple[str, ...],
    runtime_watched: bool,
) -> list[Violation]:
    """Violations for a staged merge resolution, against both parents."""
    violations: list[Violation] = []

    # Only resolution edits matter: a path that differs from both parents.
    # A change inherited from one side is not this author's edit to declare.
    changed_vs_merge = set(_git("diff", "--cached", "--name-only", merge_head_sha).splitlines())
    resolution_paths = tuple(path for path in paths if path in changed_vs_merge)
    template_paths = _template_contract_paths(
        resolution_paths,
        emitted_before=lambda path: _emitted_in_revisions(path, revisions),
        emitted_after=lambda path: path in _watched_template_paths(),
        checked_out_fallback=any(path.startswith(TEMPLATE_ROOT) for path in resolution_paths)
        and not _revision_mappings_available(revisions),
    )
    runtime_paths = (
        _runtime_contract_paths_staged(resolution_paths, revisions) if runtime_watched else ()
    )
    contract_paths = template_paths + runtime_paths
    if contract_paths:
        if not _path_exists_in_index(DECLARATION_PATH):
            violations.append(
                Violation(
                    "index",
                    "staged changes",
                    contract_paths,
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
                        contract_paths,
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
    paths: tuple[str, ...],
    revisions: tuple[str, ...],
    runtime_watched: bool,
) -> list[Violation]:
    """Violations for a staged index change against the working parents."""
    violations: list[Violation] = []

    template_paths = _template_contract_paths(
        paths,
        emitted_before=lambda path: _emitted_in_revisions(path, revisions),
        emitted_after=lambda path: path in _watched_template_paths(),
        checked_out_fallback=any(path.startswith(TEMPLATE_ROOT) for path in paths)
        and not _revision_mappings_available(revisions),
    )
    runtime_paths = _runtime_contract_paths_staged(paths, revisions) if runtime_watched else ()
    contract_paths = template_paths + runtime_paths
    if contract_paths:
        if DECLARATION_PATH in paths:
            if not _path_exists_in_index(DECLARATION_PATH):
                violations.append(
                    Violation(
                        "index",
                        "staged changes",
                        contract_paths,
                        reason="the declaration is staged for deletion",
                    )
                )
            elif not _index_declared_step_ids() - _historical_step_ids("HEAD"):
                violations.append(
                    Violation(
                        "index",
                        "staged changes",
                        contract_paths,
                        reason="no new adoption step id",
                    )
                )
        else:
            violations.append(Violation("index", "staged changes", contract_paths))

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
    runtime_watched = _runtime_watch_introduction("HEAD") is not None

    if merge_head_sha is not None:
        return tuple(_staged_merge_violations(paths, merge_head_sha, revisions, runtime_watched))
    return tuple(_staged_ordinary_violations(paths, revisions, runtime_watched))
