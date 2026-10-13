"""
Manifest vintages, declaration ids, and identity rules for the SA267(d) split.

A module manifest's ``contract_vintage`` block and the project contract
declaration share one adopted-id namespace; this sibling parses both, keeps the
historical id sets, and decides when an edit lacks a fresh identity.  The facade
imports these names from this defining sibling, never through the facade
(decisions.md, Split-Facade Seams).  Behavior is unchanged from the pre-split
module.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml
from _vintage_git import (
    VintageError,
    _file_at_commit,
    _file_in_index,
    _first_parent,
    _git,
    _path_exists_at,
    _staged_paths,
)

MODULE_MANIFEST_ROOTS = (
    "quickscale_modules/",
    "quickscale_core/src/quickscale_core/data/manifests/",
)
MODULE_MANIFEST_FILENAME = "module.yml"
DECLARATION_PATH = "quickscale_core/src/quickscale_core/data/project_contract.yml"

_MANIFEST_VINTAGES_AT: dict[tuple[str, str], ModuleVintage | None] = {}
_MANIFEST_PATHS_AT: dict[str, tuple[str, ...]] = {}
_EVER_PRESENT_MANIFEST_PATHS: dict[str, tuple[str, ...]] = {}
_DECLARATION_IDS_AT: dict[str, frozenset[str]] = {}
_MODULE_DECLARED_IDS_AT: dict[tuple[str, str], frozenset[str]] = {}


@dataclass(frozen=True)
class Violation:
    commit: str
    subject: str
    template_paths: tuple[str, ...]
    reason: str = ""


@dataclass(frozen=True)
class ModuleVintage:
    """A module manifest's ``contract_vintage`` block, normalized for identity."""

    id: str | None
    minimum: str | None
    text: tuple[str, ...]


def _is_module_manifest_path(path: str) -> bool:
    """Return whether the path is a module manifest or its bundled snapshot."""
    return path.endswith(MODULE_MANIFEST_FILENAME) and path.startswith(MODULE_MANIFEST_ROOTS)


def _module_vintage(content: str, label: str) -> ModuleVintage | None:
    """Parse a manifest's ``contract_vintage`` block; a malformed block fails closed."""
    if not content:
        return None
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise VintageError(f"cannot parse module manifest {label}: {error}") from None
    if not isinstance(data, dict):
        raise VintageError(f"module manifest {label} must be a mapping")
    raw = data.get("contract_vintage")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise VintageError(f"module manifest {label} contract_vintage must be a mapping")
    minimum = raw.get("minimum")
    if minimum is not None and not isinstance(minimum, str):
        raise VintageError(f"module manifest {label} contract_vintage.minimum must be a string")
    steps_raw = raw.get("manual_adoption_steps", [])
    if steps_raw is None:
        steps_raw = []
    if not isinstance(steps_raw, list) or any(not isinstance(step, str) for step in steps_raw):
        raise VintageError(
            f"module manifest {label} contract_vintage.manual_adoption_steps "
            "must be a list of strings"
        )
    step_id = raw.get("id")
    if step_id is not None and (not isinstance(step_id, str) or not step_id):
        raise VintageError(
            f"module manifest {label} contract_vintage.id must be a non-empty string"
        )
    return ModuleVintage(id=step_id, minimum=minimum, text=tuple(steps_raw))


def _manifest_vintage_at(commit: str, path: str) -> ModuleVintage | None:
    # Memoized: the historical-id lookups revisit the same (commit, path)
    # pairs from several roots, and every miss costs a YAML parse.
    key = (commit, path)
    if key not in _MANIFEST_VINTAGES_AT:
        _MANIFEST_VINTAGES_AT[key] = _module_vintage(
            _file_at_commit(commit, path), f"{path} at {commit[:12]}"
        )
    return _MANIFEST_VINTAGES_AT[key]


def _manifest_ids_at(commit: str, path: str) -> set[str]:
    vintage = _manifest_vintage_at(commit, path)
    return {vintage.id} if vintage is not None and vintage.id is not None else set()


def _historical_manifest_ids(commit: str, path: str) -> set[str]:
    """Every step id the manifest has declared at or before ``commit``."""
    output = _git("log", "--full-history", "--format=%H", commit, "--", path)
    step_ids: set[str] = set()
    for sha in output.splitlines():
        if sha:
            step_ids |= _manifest_ids_at(sha, path)
    return step_ids


def _manifest_module_name(path: str) -> str:
    """Return the module a manifest path belongs to (source and snapshot share it)."""
    return Path(path).parent.name


def _manifest_paths_present_at(commit: str) -> tuple[str, ...]:
    cached = _MANIFEST_PATHS_AT.get(commit)
    if cached is None:
        output = _git("ls-tree", "-r", "--name-only", commit)
        cached = tuple(line for line in output.splitlines() if _is_module_manifest_path(line))
        _MANIFEST_PATHS_AT[commit] = cached
    return cached


def _manifest_paths_at(commit: str) -> tuple[str, ...]:
    """
    Return every manifest path the history at or before ``commit`` ever carried.

    A retired module's manifest still owns the ids projects adopted while it
    existed, so those historical paths stay in the collision lookup.
    """
    cached = _EVER_PRESENT_MANIFEST_PATHS.get(commit)
    if cached is None:
        output = _git(
            "log",
            "--format=",
            "--name-only",
            "--diff-filter=A",
            commit,
            "--",
            "quickscale_modules",
            "quickscale_core/src/quickscale_core/data/manifests",
        )
        paths = {line for line in output.splitlines() if _is_module_manifest_path(line)}
        paths.update(_manifest_paths_present_at(commit))
        cached = tuple(sorted(paths))
        _EVER_PRESENT_MANIFEST_PATHS[commit] = cached
    return cached


def _declaration_ids_at(commit: str) -> frozenset[str]:
    cached = _DECLARATION_IDS_AT.get(commit)
    if cached is None:
        cached = frozenset(_historical_step_ids(commit))
        _DECLARATION_IDS_AT[commit] = cached
    return cached


def _module_declared_ids_at(commit: str, module_name: str) -> frozenset[str]:
    """Every id a module's manifests have declared at or before ``commit``."""
    key = (commit, module_name)
    cached = _MODULE_DECLARED_IDS_AT.get(key)
    if cached is None:
        ids: set[str] = set()
        for manifest_path in _manifest_paths_at(commit):
            if _manifest_module_name(manifest_path) == module_name:
                ids |= _historical_manifest_ids(commit, manifest_path)
        cached = frozenset(ids)
        _MODULE_DECLARED_IDS_AT[key] = cached
    return cached


def _tree_declared_module_ids_at(
    commit: str, *, exclude_module: str | None = None
) -> frozenset[str]:
    """Return the module step ids declared by the manifests present at ``commit``."""
    ids: set[str] = set()
    for manifest_path in _manifest_paths_present_at(commit):
        if exclude_module is not None and _manifest_module_name(manifest_path) == exclude_module:
            continue
        vintage = _manifest_vintage_at(commit, manifest_path)
        if vintage is not None and vintage.id is not None:
            ids.add(vintage.id)
    return frozenset(ids)


def _index_declared_module_ids(*, exclude_module: str | None = None) -> frozenset[str]:
    """Return the module step ids declared by the manifests in the index."""
    ids: set[str] = set()
    paths = set(_manifest_paths_present_at("HEAD")) | {
        path for path in _staged_paths() if _is_module_manifest_path(path)
    }
    for manifest_path in sorted(paths):
        if exclude_module is not None and _manifest_module_name(manifest_path) == exclude_module:
            continue
        vintage = _module_vintage(_file_in_index(manifest_path), f"{manifest_path} in the index")
        if vintage is not None and vintage.id is not None:
            ids.add(vintage.id)
    return frozenset(ids)


def _foreign_declared_step_ids(commit: str, path: str) -> frozenset[str]:
    """
    Every step id another source has declared at or before ``commit``.

    Applied state records adopted ids in one namespace, so an id another
    declaration ever used cannot name a new step: a project that adopted the
    other step would pass the new one without doing it.
    """
    if path == DECLARATION_PATH:
        ids: set[str] = set()
        for module_name in {
            _manifest_module_name(manifest_path) for manifest_path in _manifest_paths_at(commit)
        }:
            ids |= _module_declared_ids_at(commit, module_name)
        return frozenset(ids)
    own_module = _manifest_module_name(path)
    ids = set(_declaration_ids_at(commit))
    for module_name in {
        _manifest_module_name(manifest_path) for manifest_path in _manifest_paths_at(commit)
    }:
        if module_name != own_module:
            ids |= _module_declared_ids_at(commit, module_name)
    return frozenset(ids)


def _manifest_identity_violation(
    *,
    parents: list[ModuleVintage | None],
    current: ModuleVintage | None,
    historical: set[str],
    foreign: frozenset[str],
    commit: str,
    subject: str,
    paths: tuple[str, ...],
) -> Violation | None:
    """
    Fail a manifest step edit that does not give the changed step a new identity.

    ``parents`` is every revision the edit is compared against: the first
    parent for an ordinary commit, every parent for a merge resolution, where
    taking one side's bytes unchanged is inherited rather than authored.
    """
    if any(parent == current for parent in parents):
        # Unchanged from one compared revision: inherited, not authored here.
        return None
    if current is None:
        return Violation(commit, subject, paths, reason="manifest contract_vintage removed")
    if current.id is None:
        reason = (
            "manifest step id removed"
            if any(parent is not None and parent.id is not None for parent in parents)
            else "manifest steps changed without a step id"
        )
        return Violation(commit, subject, paths, reason=reason)
    same_id_parents = [
        parent for parent in parents if parent is not None and parent.id == current.id
    ]
    if same_id_parents and current not in same_id_parents:
        return Violation(commit, subject, paths, reason="step text changed without a new id")
    if current.id in historical:
        return Violation(commit, subject, paths, reason="reintroduced step id")
    if current.id in foreign:
        return Violation(commit, subject, paths, reason="step id collides with another declaration")
    return None


def _module_manifest_violation(commit: str, path: str) -> Violation | None:
    parent = _first_parent(commit)
    if parent is None:
        return None
    if not _path_exists_at(commit, path):
        # A deleted or renamed manifest declares nothing; the new path, when
        # there is one, is gated as a fresh declaration of its own.
        return None
    parent_vintage = _manifest_vintage_at(parent, path)
    current_vintage = _manifest_vintage_at(commit, path)
    if parent_vintage == current_vintage:
        return None
    subject = _git("show", "-s", "--format=%s", commit).strip()
    return _manifest_identity_violation(
        parents=[parent_vintage],
        current=current_vintage,
        historical=_historical_manifest_ids(parent, path),
        foreign=_foreign_declared_step_ids(commit, path),
        commit=commit,
        subject=subject,
        paths=(path,),
    )


def _merge_manifest_violation(commit: str, path: str, parents: tuple[str, ...]) -> Violation | None:
    """Fail a merge resolution that rewrites an adopted step under its own id."""
    if not _path_exists_at(commit, path):
        return None
    parent_vintages = [_manifest_vintage_at(parent, path) for parent in parents]
    current_vintage = _manifest_vintage_at(commit, path)
    if all(vintage == current_vintage for vintage in parent_vintages):
        return None
    subject = _git("show", "-s", "--format=%s", commit).strip()
    historical: set[str] = set()
    for parent in parents:
        historical |= _historical_manifest_ids(parent, path)
    foreign = _tree_declared_module_ids_at(commit, exclude_module=_manifest_module_name(path))
    foreign |= frozenset(_declared_step_ids_at(commit))
    for parent in parents:
        foreign |= _foreign_declared_step_ids(parent, path)
    return _manifest_identity_violation(
        parents=parent_vintages,
        current=current_vintage,
        historical=historical,
        foreign=foreign,
        commit=commit,
        subject=subject,
        paths=(path,),
    )


def _declared_step_ids(content: str, label: str) -> set[str]:
    """Parse a declaration's step ids; a malformed declaration fails closed."""
    if not content:
        return set()
    try:
        data = yaml.safe_load(content)
    except yaml.YAMLError as error:
        raise VintageError(f"cannot parse {DECLARATION_PATH} {label}: {error}") from None
    if not isinstance(data, dict):
        raise VintageError(f"{DECLARATION_PATH} {label} must be a mapping")
    steps = data.get("steps")
    if not isinstance(steps, list):
        raise VintageError(f"{DECLARATION_PATH} {label} must declare a 'steps' list")

    step_ids: set[str] = set()
    for step in steps:
        if isinstance(step, dict) and isinstance(step.get("id"), str) and step["id"]:
            step_ids.add(step["id"])
    return step_ids


def _declared_step_ids_at(commit: str) -> set[str]:
    return _declared_step_ids(
        _file_at_commit(commit, DECLARATION_PATH),
        f"at {commit[:12]}",
    )


def _index_declared_step_ids() -> set[str]:
    result = subprocess.run(
        ["git", "show", f":{DECLARATION_PATH}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        return set()
    return _declared_step_ids(result.stdout, "in the index")


def _declares_vintage(commit: str, paths: tuple[str, ...]) -> bool:
    """Return True when the commit edits the declaration without deleting it."""
    return DECLARATION_PATH in paths and _path_exists_at(commit, DECLARATION_PATH)


def _historical_step_ids(commit: str) -> set[str]:
    """
    Every step id the declaration has declared at or before ``commit``.

    ``--full-history`` keeps declarations made and removed on a merged branch,
    which default path-history simplification can prune; reusing such an id
    must not count as a new step, or projects that recorded the old id would
    pass without adopting the changed contract.
    """
    output = _git(
        "log",
        "--full-history",
        "--format=%H",
        commit,
        "--",
        DECLARATION_PATH,
    )
    step_ids: set[str] = set()
    for sha in output.splitlines():
        if sha:
            step_ids |= _declared_step_ids_at(sha)
    return step_ids


def _declares_new_step(commit: str) -> bool:
    """Return True when the commit declares a step id never declared before it."""
    parent = _first_parent(commit)
    if parent is None:
        return True
    return bool(_declared_step_ids_at(commit) - _historical_step_ids(parent))


def _merge_declares_new_step(commit: str, parents: tuple[str, ...]) -> bool:
    """Return True when a merge resolution declares an id no parent's history ever declared."""
    historical: set[str] = set()
    for parent in parents:
        historical |= _historical_step_ids(parent)
    return bool(_declared_step_ids_at(commit) - historical)


def _introduction_commit(head: str) -> str | None:
    """
    Earliest commit reachable from ``head`` that added the declaration.

    The introduction is a monotonic baseline: everything before it predates
    the rule and is exempt, and deleting the declaration later cannot switch
    enforcement back off.
    """
    output = _git(
        "log",
        "--reverse",
        "--format=%H",
        "--diff-filter=A",
        head,
        "--",
        DECLARATION_PATH,
    )
    lines = [line for line in output.splitlines() if line]
    return lines[0] if lines else None


def _declaration_id_collision(commit: str) -> set[str]:
    """Return new declaration ids that another source has already declared."""
    parent = _first_parent(commit)
    if parent is None:
        return set()
    new_ids = _declared_step_ids_at(commit) - _historical_step_ids(parent)
    return new_ids & set(_foreign_declared_step_ids(commit, DECLARATION_PATH))


def _merged_tree_declared_ids(
    commit: str,
) -> dict[str, frozenset[str]]:
    """Return the current step ids per source in the revision's tree."""
    current: dict[str, set[str]] = {"": set(_declared_step_ids_at(commit))}
    for manifest_path in _manifest_paths_present_at(commit):
        vintage = _manifest_vintage_at(commit, manifest_path)
        if vintage is not None and vintage.id is not None:
            current.setdefault(_manifest_module_name(manifest_path), set()).add(vintage.id)
    return {source: frozenset(ids) for source, ids in current.items()}


def _source_reference_path(module_name: str) -> str:
    """Return the repo path that best names a declaration source."""
    if not module_name:
        return DECLARATION_PATH
    return f"quickscale_modules/{module_name}/{MODULE_MANIFEST_FILENAME}"


def _merge_combined_id_violations(commit: str, parents: tuple[str, ...]) -> list[Violation]:
    """
    Fail merged-tree ids another source declares or has ever declared.

    A clean merge can combine an id declared on one branch with the same id
    declared (or retired) on the other, so the namespace is checked over the
    whole merged tree, not only the resolution paths.
    """
    current = _merged_tree_declared_ids(commit)
    if all(_merged_tree_declared_ids(parent) == current for parent in parents):
        # The merge added and removed no declaration: nothing new to combine.
        return []
    collisions: set[tuple[str, str]] = set()
    for source, ids in current.items():
        foreign = _foreign_declared_step_ids(commit, _source_reference_path(source))
        for step_id in ids & foreign:
            collisions.add((step_id, source))
    if not collisions:
        return []
    subject = _git("show", "-s", "--format=%s", commit).strip()
    return [
        Violation(
            commit,
            subject,
            (_source_reference_path(source),),
            reason=f"step id collides with another declaration ({step_id})",
        )
        for step_id, source in sorted(collisions)
    ]


def _merge_declaration_id_collision(commit: str, parents: tuple[str, ...]) -> set[str]:
    """Return resolution-added declaration ids another source has declared."""
    historical: set[str] = set()
    foreign: set[str] = set(_tree_declared_module_ids_at(commit))
    for parent in parents:
        historical |= _historical_step_ids(parent)
        foreign |= set(_foreign_declared_step_ids(parent, DECLARATION_PATH))
    return (_declared_step_ids_at(commit) - historical) & foreign
