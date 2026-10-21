"""Detect local edits inside an embedded module before an update overwrites them.

An embedded module is imported from a module-split commit whose tree root is
the module content, and ``.quickscale/state.yml`` records that commit as
``commit_sha``.  This module compares ``modules/<module>/`` against that
recorded tree, so ``quickscale update`` can refuse to pull over a hand edit and
``quickscale status`` can report the same drift.

The comparison reads the recorded tree into a throwaway Git index with
``git read-tree --prefix=modules/<module>/`` and diffs it against the working
tree with ``git diff-files``.  When the fetched split commit has been pruned
from the project's object database, the subtree squash commit that Git created
for the import carries the same tree and is used instead.

The embed path rewrites an embedded module's ``pyproject.toml`` when it
declares a monorepo-local path dependency (for example
``quickscale-core = {path = "../../quickscale_core"}``): the dependency value
becomes a published spec or a local wheel path.  That rewrite is allowed by
comparing the documents semantically with those path dependencies removed.
The rewritten dependency's own value is environment-owned and is not compared
(QuickScale regenerates it), while every other difference is reported as a
changed path.
"""

from __future__ import annotations

import os
import re
import subprocess
import tempfile
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MODULE_PREFIX = "modules"
_FULL_SHA_PATTERN = re.compile(r"^[0-9a-fA-F]{40}(?:[0-9a-fA-F]{24})?$")
_SUBTREE_SPLIT_TRAILER = "git-subtree-split: "
_SUBTREE_DIR_TRAILER = "git-subtree-dir: "


@dataclass(frozen=True)
class ModuleContentDrift:
    """Observed difference between an embedded module and its recorded tree."""

    module: str
    commit_sha: str | None
    changed_paths: tuple[str, ...] = ()
    unverifiable_reason: str | None = None

    @property
    def has_changes(self) -> bool:
        """Return True when the working tree differs from the recorded tree."""
        return bool(self.changed_paths)

    @property
    def verifiable(self) -> bool:
        """Return True when the recorded tree could be read for comparison."""
        return self.unverifiable_reason is None


def _git_environment(index_file: Path | None) -> dict[str, str]:
    """Return an environment that optionally redirects Git's index file."""
    environment = dict(os.environ)
    if index_file is None:
        environment.pop("GIT_INDEX_FILE", None)
    else:
        environment["GIT_INDEX_FILE"] = str(index_file)
    return environment


def _run_git(
    project_path: Path,
    arguments: list[str],
    *,
    index_file: Path | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one read-only Git command and capture its raw output."""
    try:
        return subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
            ["git", *arguments],  # noqa: S607 - PATH-resolved executable by design
            cwd=project_path,
            capture_output=True,
            check=False,
            env=_git_environment(index_file),
        )
    except OSError as error:
        return subprocess.CompletedProcess(
            args=arguments,
            returncode=127,
            stdout=b"",
            stderr=str(error).encode(),
        )


def _nul_records(output: bytes) -> list[bytes]:
    """Split Git's ``-z`` output into its non-empty NUL-terminated records."""
    return [record for record in output.split(b"\0") if record]


def _is_git_repository(project_path: Path) -> bool:
    """Return whether *project_path* is inside a Git work tree."""
    result = _run_git(project_path, ["rev-parse", "--git-dir"])
    return result.returncode == 0


def _is_split_commit(project_path: Path, commit_sha: str) -> bool:
    """Return whether the recorded commit is present and shaped like a split.

    A module split commit stores the module content at the tree root, so its
    ``module.yml`` is directly addressable.  Checking that root file keeps a
    full-repository commit that happens to share the SHA from being compared
    as if it were the module tree.
    """
    commit_result = _run_git(
        project_path, ["cat-file", "-e", f"{commit_sha}^{{commit}}"]
    )
    if commit_result.returncode != 0:
        return False
    manifest_result = _run_git(
        project_path, ["cat-file", "-e", f"{commit_sha}:module.yml"]
    )
    return manifest_result.returncode == 0


def _find_subtree_squash_commit(
    project_path: Path,
    module_name: str,
    commit_sha: str,
) -> str | None:
    """Find the local subtree squash commit recorded for *commit_sha*.

    ``git subtree add|pull --squash`` keeps the imported module tree in a
    commit whose message carries the source split commit and the destination
    prefix.  That commit stays reachable from the project history after the
    fetched split object itself is pruned.
    """
    log_result = _run_git(
        project_path,
        [
            "log",
            "--format=%H",
            "--fixed-strings",
            f"--grep={_SUBTREE_SPLIT_TRAILER}{commit_sha}",
            "HEAD",
        ],
    )
    if log_result.returncode != 0:
        return None

    expected_directory = f"{_MODULE_PREFIX}/{module_name}"
    for candidate in log_result.stdout.decode("utf-8", "replace").splitlines():
        if not candidate.strip():
            continue
        message_result = _run_git(
            project_path, ["show", "-s", "--format=%B", candidate.strip()]
        )
        if message_result.returncode != 0:
            continue
        trailers = message_result.stdout.decode("utf-8", "replace").splitlines()
        split = next(
            (
                line[len(_SUBTREE_SPLIT_TRAILER) :].strip()
                for line in trailers
                if line.startswith(_SUBTREE_SPLIT_TRAILER)
            ),
            None,
        )
        directory = next(
            (
                line[len(_SUBTREE_DIR_TRAILER) :].strip()
                for line in trailers
                if line.startswith(_SUBTREE_DIR_TRAILER)
            ),
            None,
        )
        if split == commit_sha and directory == expected_directory:
            return candidate.strip()
    return None


def _resolve_baseline(
    project_path: Path,
    module_name: str,
    commit_sha: str,
) -> tuple[str | None, str | None]:
    """Return the tree-ish holding the recorded module content, or a reason."""
    if not _is_git_repository(project_path):
        return None, "the project is not a git repository"

    if _is_split_commit(project_path, commit_sha):
        return commit_sha, None

    squash_commit = _find_subtree_squash_commit(project_path, module_name, commit_sha)
    if squash_commit is not None:
        return squash_commit, None

    return (
        None,
        f"the recorded commit {commit_sha} is not in this project's git history",
    )


def _read_index_paths(
    project_path: Path,
    index_file: Path,
) -> tuple[dict[str, str] | None, str | None]:
    """Return the baseline index's ``path -> blob SHA`` mapping."""
    result = _run_git(project_path, ["ls-files", "-s", "-z"], index_file=index_file)
    if result.returncode != 0:
        return None, "the recorded module tree could not be read"

    entries: dict[str, str] = {}
    for record in _nul_records(result.stdout):
        metadata, separator, path = record.partition(b"\t")
        if not separator:
            continue
        fields = metadata.split()
        if len(fields) < 2:
            continue
        entries[os.fsdecode(path)] = fields[1].decode("ascii", "replace")
    return entries, None


def _read_local_paths(project_path: Path, prefix: str) -> tuple[set[str], str | None]:
    """Return working-tree paths under *prefix* that Git does not ignore."""
    result = _run_git(
        project_path,
        [
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
            "--",
            prefix,
        ],
    )
    if result.returncode != 0:
        return set(), "the embedded module files could not be listed"
    return {os.fsdecode(path) for path in _nul_records(result.stdout)}, None


def _read_changed_paths(
    project_path: Path,
    index_file: Path,
) -> tuple[dict[str, str] | None, str | None]:
    """Return ``path -> diff status`` for work-tree changes against the index."""
    result = _run_git(
        project_path,
        ["diff-files", "--name-status", "-z"],
        index_file=index_file,
    )
    if result.returncode != 0:
        return None, "the embedded module tree could not be compared"
    records = _nul_records(result.stdout)

    changes: dict[str, str] = {}
    for status_record, path_record in zip(records[::2], records[1::2]):
        changes[os.fsdecode(path_record)] = status_record.decode("ascii", "replace")
    return changes, None


def _is_path_dependency(value: Any) -> bool:
    """Return whether a Poetry dependency value declares a filesystem path."""
    return (
        isinstance(value, dict)
        and isinstance(value.get("path"), str)
        and bool(value["path"].strip())
    )


def _is_allowed_pyproject_rewrite(baseline: bytes, local: bytes) -> bool:
    """Return whether *local* is the embed rewrite of the *baseline* document.

    The embed path replaces an unresolvable path dependency with a published
    spec or a local wheel.  Both documents are compared as TOML after those
    path-dependency entries are removed, so any other edit stays visible.
    """
    try:
        baseline_document = tomllib.loads(baseline.decode("utf-8"))
        local_document = tomllib.loads(local.decode("utf-8"))
    except UnicodeDecodeError, tomllib.TOMLDecodeError:
        return False

    def dependencies(document: dict[str, Any]) -> dict[str, Any] | None:
        tool = document.get("tool")
        poetry = tool.get("poetry") if isinstance(tool, dict) else None
        dependencies = poetry.get("dependencies") if isinstance(poetry, dict) else None
        return dependencies if isinstance(dependencies, dict) else None

    baseline_dependencies = dependencies(baseline_document)
    local_dependencies = dependencies(local_document)
    if baseline_dependencies is None or local_dependencies is None:
        return baseline_document == local_document

    for dependency_name in [
        name
        for name, value in baseline_dependencies.items()
        if _is_path_dependency(value)
    ]:
        del baseline_dependencies[dependency_name]
        local_dependencies.pop(dependency_name, None)

    return baseline_document == local_document


def _read_baseline_blob(project_path: Path, blob_sha: str) -> bytes | None:
    """Read one baseline blob from the local object database."""
    result = _run_git(project_path, ["cat-file", "blob", blob_sha])
    if result.returncode != 0:
        return None
    return result.stdout


def detect_module_content_drift(
    project_path: Path,
    module_name: str,
    commit_sha: str | None,
) -> ModuleContentDrift:
    """Compare ``modules/<module>/`` with the tree at *commit_sha*.

    Returns the project-relative paths whose content, mode, or presence
    differs from the recorded tree.  When the recorded tree cannot be read —
    no recorded SHA, a non-git project, or a pruned object with no local
    subtree squash commit — the result carries an explicit
    :attr:`ModuleContentDrift.unverifiable_reason` instead of claiming
    cleanliness.
    """
    normalized_sha = commit_sha.strip() if isinstance(commit_sha, str) else ""
    if not _FULL_SHA_PATTERN.fullmatch(normalized_sha):
        return ModuleContentDrift(
            module=module_name,
            commit_sha=commit_sha if isinstance(commit_sha, str) else None,
            unverifiable_reason=(
                "the applied state does not record a commit_sha for this module"
            ),
        )
    normalized_sha = normalized_sha.lower()

    baseline, reason = _resolve_baseline(project_path, module_name, normalized_sha)
    if baseline is None:
        return ModuleContentDrift(
            module=module_name,
            commit_sha=normalized_sha,
            unverifiable_reason=reason,
        )

    prefix = f"{_MODULE_PREFIX}/{module_name}"
    with tempfile.TemporaryDirectory(prefix="quickscale-module-drift-") as temp_dir:
        index_file = Path(temp_dir) / "index"
        read_result = _run_git(
            project_path,
            ["read-tree", f"--prefix={prefix}/", baseline],
            index_file=index_file,
        )
        if read_result.returncode != 0:
            return ModuleContentDrift(
                module=module_name,
                commit_sha=normalized_sha,
                unverifiable_reason=(
                    f"the tree at the recorded commit {normalized_sha} could not be read"
                ),
            )

        baseline_blobs, reason = _read_index_paths(project_path, index_file)
        if baseline_blobs is None:
            return ModuleContentDrift(
                module=module_name,
                commit_sha=normalized_sha,
                unverifiable_reason=reason,
            )

        # ``diff-files`` compares the throwaway index to the work tree; the
        # refresh stores the work tree's stat data so unchanged files are not
        # reported.  Status 1 means at least one entry needs updating, which
        # is expected here; anything else leaves the comparison unreliable.
        refresh_result = _run_git(
            project_path, ["update-index", "--refresh"], index_file=index_file
        )
        if refresh_result.returncode not in (0, 1):
            return ModuleContentDrift(
                module=module_name,
                commit_sha=normalized_sha,
                unverifiable_reason=("the embedded module tree could not be compared"),
            )
        changes, reason = _read_changed_paths(project_path, index_file)
        if changes is None:
            return ModuleContentDrift(
                module=module_name,
                commit_sha=normalized_sha,
                unverifiable_reason=reason,
            )

        local_paths, reason = _read_local_paths(project_path, prefix)
        if reason is not None:
            return ModuleContentDrift(
                module=module_name,
                commit_sha=normalized_sha,
                unverifiable_reason=reason,
            )

    changed_paths: set[str] = {
        path for path, status in changes.items() if status in {"M", "D", "T"}
    }
    changed_paths.update(local_paths - set(baseline_blobs))

    for path in list(changed_paths):
        if changes.get(path) != "M" or Path(path).name != "pyproject.toml":
            continue
        baseline_blob = baseline_blobs.get(path)
        if baseline_blob is None:
            continue
        baseline_content = _read_baseline_blob(project_path, baseline_blob)
        try:
            local_content = (project_path / path).read_bytes()
        except OSError:
            continue
        if baseline_content is not None and _is_allowed_pyproject_rewrite(
            baseline_content, local_content
        ):
            changed_paths.discard(path)

    return ModuleContentDrift(
        module=module_name,
        commit_sha=normalized_sha,
        changed_paths=tuple(sorted(changed_paths)),
    )
