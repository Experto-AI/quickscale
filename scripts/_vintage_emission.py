"""
Emission-mapping and watched-template derivation for the SA267(d) split.

The watched template set is derived from the generator's authoritative emission
mapping, and each compared revision's own generator package is evaluated to
decide whether a commit started, stopped, or rerouted an emitted file.  The
facade imports these names from this defining sibling, never through the facade
(decisions.md, Split-Facade Seams).  Behavior is unchanged from the pre-split
module.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Callable
from pathlib import Path

from _vintage_git import (
    REPO_ROOT,
    VintageError,
    _first_parent,
    _git_bytes,
    _tree_entry_exists,
)

TEMPLATE_ROOT = "quickscale_core/src/quickscale_core/generator/templates/"
GENERATOR_PACKAGE_ROOT = "quickscale_core/src/quickscale_core/generator/"
PACKAGE_ROOT = "quickscale_core/src/quickscale_core"
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


def _generator_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    """Return the generator code paths: the package minus template sources."""
    return tuple(
        path
        for path in paths
        if path.startswith(GENERATOR_PACKAGE_ROOT) and not path.startswith(TEMPLATE_ROOT)
    )
