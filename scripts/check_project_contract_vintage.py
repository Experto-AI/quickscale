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

from __future__ import annotations

import argparse
import io
import json
import os
import re
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE_ROOT = "quickscale_core/src/quickscale_core/generator/templates/"
GENERATOR_PACKAGE_ROOT = "quickscale_core/src/quickscale_core/generator/"
PACKAGE_ROOT = "quickscale_core/src/quickscale_core"
MODULE_MANIFEST_ROOTS = (
    "quickscale_modules/",
    "quickscale_core/src/quickscale_core/data/manifests/",
)
MODULE_MANIFEST_FILENAME = "module.yml"
DECLARATION_PATH = "quickscale_core/src/quickscale_core/data/project_contract.yml"
ZERO_SHA_RE = re.compile(r"^0+$")
_EMIT_SOURCES_SNIPPET = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "import quickscale_core\n"
    "from quickscale_core.generator import get_generator_emission_mapping\n"
    "mapping = get_generator_emission_mapping(Path(sys.argv[1]))\n"
    "print(json.dumps({'package': quickscale_core.__file__, 'mapping': mapping}))\n"
)
_WATCHED_TEMPLATE_PATHS: frozenset[str] | None = None
_EMITTED_TEMPLATE_SOURCES_AT: dict[str, frozenset[str]] = {}
_REVISION_EMISSION_MAPPINGS: dict[str, dict[str, str] | None] = {}
_MANIFEST_PATHS_AT: dict[str, tuple[str, ...]] = {}
_EVER_PRESENT_MANIFEST_PATHS: dict[str, tuple[str, ...]] = {}
_DECLARATION_IDS_AT: dict[str, frozenset[str]] = {}
_MODULE_DECLARED_IDS_AT: dict[tuple[str, str], frozenset[str]] = {}


class VintageError(RuntimeError):
    """A deterministic input, environment, or Git failure."""


@dataclass(frozen=True)
class Violation:
    commit: str
    subject: str
    template_paths: tuple[str, ...]
    reason: str = ""


def _git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
        raise VintageError(f"git {' '.join(args)!r} failed: {detail}")
    return result.stdout


def _git_bytes(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        capture_output=True,
        timeout=120,
        check=False,
    )
    if result.returncode != 0:
        detail = result.stderr.decode("utf-8", "replace").strip() or f"exit {result.returncode}"
        raise VintageError(f"git {' '.join(args)!r} failed: {detail}")
    return result.stdout


def _event_base_ref() -> str | None:
    event_path_text = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path_text:
        return None
    event_path = Path(event_path_text)
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VintageError(f"cannot read GitHub event payload {event_path}: {exc}") from None
    if not isinstance(event, dict):
        raise VintageError(f"GitHub event payload {event_path} must be a JSON object")

    pull_request = event.get("pull_request")
    if isinstance(pull_request, dict):
        base = pull_request.get("base")
        if isinstance(base, dict):
            sha = base.get("sha")
            if isinstance(sha, str) and sha:
                return sha
    before = event.get("before")
    if isinstance(before, str) and before and not ZERO_SHA_RE.fullmatch(before):
        return before
    return None


def _select_base_ref(explicit: str | None) -> str:
    if explicit:
        return explicit
    override = os.environ.get("PROJECT_VINTAGE_BASE_REF", "").strip()
    if override:
        return override
    event_ref = _event_base_ref()
    if event_ref:
        return event_ref
    github_base = os.environ.get("GITHUB_BASE_REF", "").strip()
    if github_base:
        for candidate in (f"origin/{github_base}", github_base):
            try:
                _resolve_commit(candidate)
            except VintageError:
                continue
            return candidate
        raise VintageError(
            f"GITHUB_BASE_REF {github_base!r} is unavailable; use a full-history checkout"
        )
    return "HEAD^"


def _resolve_commit(ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise VintageError(f"unsafe or empty Git ref: {ref!r}")
    resolved = _git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", resolved):
        raise VintageError(f"Git ref {ref!r} did not resolve to a full commit SHA")
    return resolved


def _range_base(base: str, head: str) -> str:
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", base, head],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if ancestor.returncode == 0:
        return base
    if ancestor.returncode != 1:
        detail = ancestor.stderr.strip() or ancestor.stdout.strip() or f"exit {ancestor.returncode}"
        raise VintageError(f"cannot compare selected commits: {detail}")
    merged = _git("merge-base", base, head).strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", merged):
        raise VintageError("selected base and head have no valid merge base")
    return merged


def _emitted_sources_from_mapping(mapping: dict[str, str]) -> frozenset[str]:
    """Watched template-source paths for an emission mapping."""
    return frozenset(
        f"{TEMPLATE_ROOT}{template_rel}"
        for template_rel in mapping.values()
        if not template_rel.startswith("<dynamic:")
    )


def _generator_emission_mapping(template_root: Path) -> dict[str, str]:
    """Return the authoritative ``{emitted_path: template_rel_path}`` mapping."""
    try:
        from quickscale_core.generator import get_generator_emission_mapping

        return get_generator_emission_mapping(template_root)
    except VintageError:
        raise
    except Exception as error:
        raise VintageError(f"cannot read the generator emission mapping: {error}") from None


def _watched_template_paths() -> frozenset[str]:
    """
    Repo-relative template sources the generator emits into projects.

    Derived from the authoritative emission mapping (SA211), not a path list,
    so a template that joins the generated project joins the rule without a
    second edit here.  A derivation failure is a gate input error, never a
    pass.
    """
    global _WATCHED_TEMPLATE_PATHS
    if _WATCHED_TEMPLATE_PATHS is None:
        template_root = REPO_ROOT / TEMPLATE_ROOT
        if not template_root.is_dir():
            raise VintageError(
                f"the generator templates root {TEMPLATE_ROOT!r} is missing; "
                "cannot derive the watched template set"
            )
        mapping = _generator_emission_mapping(template_root)
        if not mapping:
            raise VintageError(
                "the generator emission mapping is empty; cannot derive the watched template set"
            )
        _WATCHED_TEMPLATE_PATHS = _emitted_sources_from_mapping(mapping)
    return _WATCHED_TEMPLATE_PATHS


def _tree_entry_exists(commit: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{path.rstrip('/')}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.returncode == 0


def _emitted_template_sources_at(commit: str) -> frozenset[str]:
    """
    Repo-relative template sources emitted as of ``commit``'s template tree.

    Uses the checked-out generator code (the revision's own code is evaluated
    separately when a commit touches the generator package), so this answers
    tree questions: which templates the current mapping would emit from the
    revision's tree.
    """
    cached = _EMITTED_TEMPLATE_SOURCES_AT.get(commit)
    if cached is not None:
        return cached
    sources: frozenset[str] = frozenset()
    if _tree_entry_exists(commit, TEMPLATE_ROOT):
        archive = _git_bytes("archive", "--format=tar", commit, "--", TEMPLATE_ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                tar.extractall(tmp, filter="data")
            archived_root = Path(tmp) / TEMPLATE_ROOT
            if archived_root.is_dir():
                sources = _emitted_sources_from_mapping(_generator_emission_mapping(archived_root))
    _EMITTED_TEMPLATE_SOURCES_AT[commit] = sources
    return sources


def _revision_emission_mapping(commit: str) -> dict[str, str] | None:
    """
    Return the emission mapping the revision's own generator package produces.

    The whole ``{emitted_path: template_rel_path}`` mapping is compared, not
    just its source side, so a code change that routes an unchanged template
    to a different generated path is a contract change too.  ``None`` when
    that package cannot be archived, imported, or read: the caller decides the
    fail direction rather than the revision blocking on a tool failure it
    cannot fix from the outside.
    """
    if commit in _REVISION_EMISSION_MAPPINGS:
        return _REVISION_EMISSION_MAPPINGS[commit]
    result: dict[str, str] | None = None
    if _tree_entry_exists(commit, PACKAGE_ROOT):
        try:
            archive = _git_bytes("archive", "--format=tar", commit, "--", PACKAGE_ROOT)
        except VintageError:
            result = None
        else:
            try:
                with tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    with tarfile.open(fileobj=io.BytesIO(archive), mode="r:") as tar:
                        tar.extractall(root, filter="data")
                    package_src = root / PACKAGE_ROOT
                    templates_root = package_src / "generator" / "templates"
                    if templates_root.is_dir():
                        env = dict(os.environ)
                        env["PYTHONPATH"] = str(package_src.parent)
                        completed = subprocess.run(
                            [
                                sys.executable,
                                "-c",
                                _EMIT_SOURCES_SNIPPET,
                                str(templates_root),
                            ],
                            cwd=tmp,
                            env=env,
                            capture_output=True,
                            text=True,
                            timeout=120,
                            check=False,
                        )
                        if completed.returncode == 0:
                            payload = json.loads(completed.stdout)
                            mapping = payload.get("mapping") if isinstance(payload, dict) else None
                            resolved = payload.get("package") if isinstance(payload, dict) else None
                            # The extraction must be the package that ran: a
                            # namespace fallback to an installed copy would
                            # compare the wrong generator.
                            if (
                                isinstance(mapping, dict)
                                and isinstance(resolved, str)
                                and Path(resolved).resolve().is_relative_to(root.resolve())
                                and all(
                                    isinstance(key, str) and isinstance(value, str)
                                    for key, value in mapping.items()
                                )
                            ):
                                result = {
                                    emitted: template_rel
                                    for emitted, template_rel in mapping.items()
                                    if not template_rel.startswith("<dynamic:")
                                }
            except OSError, subprocess.SubprocessError, json.JSONDecodeError:
                result = None
    _REVISION_EMISSION_MAPPINGS[commit] = result
    return result


def _revision_emitted_sources(commit: str) -> frozenset[str]:
    """
    Return the emitted template sources the revision's own generator produces.

    Falls back to the checked-out mapping over the revision's tree when that
    package cannot be executed, so a deletion is judged against the compared
    revision wherever its code is runnable.
    """
    mapping = _revision_emission_mapping(commit)
    if mapping is None:
        return _emitted_template_sources_at(commit)
    return _emitted_sources_from_mapping(mapping)


def _revision_emission_mapping_changed(commit: str) -> bool:
    """
    Return whether the revision's own generator emits a different file set.

    Both revisions are evaluated with their own generator package, so a code
    change that adds, removes, or reroutes an emitted output is a contract
    change even when no template path changed.  A revision whose package
    cannot be executed falls back to comparing template trees with the
    checked-out mapping, so an unrelated commit cannot be blocked by a tool
    failure.
    """
    parent = _first_parent(commit)
    if parent is None:
        return False
    before = _revision_emission_mapping(parent)
    after = _revision_emission_mapping(commit)
    if before is None or after is None:
        return _emitted_template_sources_at(parent) != _emitted_template_sources_at(commit)
    return before != after


def _revision_mappings_available(revisions: tuple[str | None, ...]) -> bool:
    """Return whether every compared revision's own generator could be read."""
    return all(
        revision is None or _revision_emission_mapping(revision) is not None
        for revision in revisions
    )


def _template_contract_paths(
    paths: tuple[str, ...],
    *,
    emitted_before: Callable[[str], bool],
    emitted_after: Callable[[str], bool],
    checked_out_fallback: bool,
) -> tuple[str, ...]:
    """
    Watched emitted templates among ``paths``.

    Membership is judged against the compared revisions' own emission
    mappings, so an edit is watched when the generator emitted the path then
    and a deletion is watched because the prior revision emitted it — even
    when a later commit in the same range stops emitting it.  A template-tree
    path no compared revision emitted (a repo-tracking placeholder, or one
    the generator did not emit yet) is not a contract change.

    The checked-out mapping is consulted only when a compared revision's own
    generator cannot be evaluated, where it is the best available guess.
    """
    watched_now = _watched_template_paths() if checked_out_fallback else frozenset()
    return tuple(
        path
        for path in paths
        if path in watched_now
        or (path.startswith(TEMPLATE_ROOT) and (emitted_before(path) or emitted_after(path)))
    )


def _is_module_manifest_path(path: str) -> bool:
    """Return whether the path is a module manifest or its bundled snapshot."""
    return path.endswith(MODULE_MANIFEST_FILENAME) and path.startswith(MODULE_MANIFEST_ROOTS)


@dataclass(frozen=True)
class ModuleVintage:
    """A module manifest's ``contract_vintage`` block, normalized for identity."""

    id: str | None
    minimum: str | None
    text: tuple[str, ...]


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
    return _module_vintage(_file_at_commit(commit, path), f"{path} at {commit[:12]}")


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


def _commit_paths(commit: str) -> tuple[str, ...]:
    output = _git(
        "diff-tree",
        "--root",
        "--no-commit-id",
        "--name-only",
        "-r",
        commit,
    )
    return tuple(line for line in output.splitlines() if line)


def _path_exists_at(commit: str, path: str) -> bool:
    output = _git("ls-tree", "--name-only", commit, "--", path)
    return path in output.splitlines()


def _path_exists_in_index(path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f":{path}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.returncode == 0


def _file_at_commit(commit: str, path: str) -> str:
    if not _path_exists_at(commit, path):
        return ""
    return _git("show", f"{commit}:{path}")


def _file_in_index(path: str) -> str:
    if not _path_exists_in_index(path):
        return ""
    return _git("show", f":{path}")


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


def _parents(commit: str) -> tuple[str, ...]:
    fields = _git("rev-list", "--parents", "-n", "1", commit).split()
    return tuple(fields[1:])


def _first_parent(commit: str) -> str | None:
    parents = _parents(commit)
    return parents[0] if parents else None


def _merge_resolution_paths(commit: str) -> tuple[str, ...]:
    """Paths a merge commit changed against every parent (combined diff)."""
    output = _git("diff-tree", "-r", "-c", "--name-only", "--no-commit-id", commit)
    return tuple(line for line in output.splitlines() if line)


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


def _first_parent(commit: str) -> str | None:
    parents = _git("rev-list", "--parents", "-n", "1", commit).split()
    return parents[1] if len(parents) > 1 else None


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


def _is_ancestor(commit: str, descendant: str) -> bool:
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, descendant],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    detail = result.stderr.strip() or result.stdout.strip() or f"exit {result.returncode}"
    raise VintageError(f"cannot compare selected commits: {detail}")


def _declaration_id_collision(commit: str) -> set[str]:
    """Return new declaration ids that another source has already declared."""
    parent = _first_parent(commit)
    if parent is None:
        return set()
    new_ids = _declared_step_ids_at(commit) - _historical_step_ids(parent)
    return new_ids & set(_foreign_declared_step_ids(commit, DECLARATION_PATH))


def _source_reference_path(module_name: str) -> str:
    """Return the repo path that best names a declaration source."""
    if not module_name:
        return DECLARATION_PATH
    return f"quickscale_modules/{module_name}/{MODULE_MANIFEST_FILENAME}"


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


def _generator_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Return the generator code paths: the package minus template sources."""
    return tuple(
        path
        for path in paths
        if path.startswith(GENERATOR_PACKAGE_ROOT) and not path.startswith(TEMPLATE_ROOT)
    )


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
            continue

        paths = _commit_paths(commit)
        parent = _first_parent(commit)
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
        mapping_changed = bool(_generator_paths(paths)) and _revision_emission_mapping_changed(
            commit
        )
        if template_paths or mapping_changed:
            declared = _declares_vintage(commit, paths)
            if declared and _declares_new_step(commit):
                pass
            elif pre_baseline:
                pass
            else:
                # Editing the declaration is not enough: a changed contract
                # must declare a new step id, or projects that already
                # recorded the old ids would keep passing enforcement.
                reported = template_paths or _generator_paths(paths)
                if declared:
                    reason = "no new adoption step id"
                elif mapping_changed and not template_paths:
                    reason = "generator emission mapping changed without a new adoption step id"
                else:
                    reason = ""
                subject = _git("show", "-s", "--format=%s", commit).strip()
                violations.append(Violation(commit, subject, reported, reason=reason))
        if not pre_baseline and DECLARATION_PATH in paths:
            collision = _declaration_id_collision(commit)
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
            for path in paths:
                if _is_module_manifest_path(path):
                    violation = _module_manifest_violation(commit, path)
                    if violation is not None:
                        violations.append(violation)
    return tuple(violations)


def _staged_paths() -> tuple[str, ...]:
    output = _git("diff", "--cached", "--name-only")
    return tuple(line for line in output.splitlines() if line)


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

    def emitted_in_a_compared_revision(path: str) -> bool:
        return any(
            path in _revision_emitted_sources(revision)
            for revision in revisions
            if revision is not None
        )

    violations: list[Violation] = []

    if merge_head_sha is not None:
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
        return tuple(violations)

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
    return tuple(violations)


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
