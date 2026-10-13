"""
Git plumbing and ref selection for the SA267(d) ``check_project_contract_vintage`` split.

Every revision question the vintage gate asks — tree existence, file contents
at a commit or in the index, parents, merge resolutions, ancestry, and the
selected range base — resolves here.  The facade and the other siblings import
these names from this defining sibling, never through the facade
(decisions.md, Split-Facade Seams).  Behavior is unchanged from the pre-split
module.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ZERO_SHA_RE = re.compile(r"^0+$")

_FILES_AT_COMMIT: dict[tuple[str, str], str] = {}


class VintageError(RuntimeError):
    """A deterministic input, environment, or Git failure."""


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


def _tree_entry_exists(commit: str, path: str) -> bool:
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}:{path.rstrip('/')}"],
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    return result.returncode == 0


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
    # Memoized: each miss runs two git subprocesses, and the manifest
    # walkers ask for the same revisions from several roots.
    key = (commit, path)
    cached = _FILES_AT_COMMIT.get(key)
    if cached is None:
        if not _path_exists_at(commit, path):
            cached = ""
        else:
            cached = _git("show", f"{commit}:{path}")
        _FILES_AT_COMMIT[key] = cached
    return cached


def _file_in_index(path: str) -> str:
    if not _path_exists_in_index(path):
        return ""
    return _git("show", f":{path}")


def _staged_paths() -> tuple[str, ...]:
    output = _git("diff", "--cached", "--name-only")
    return tuple(line for line in output.splitlines() if line)


def _parents(commit: str) -> tuple[str, ...]:
    fields = _git("rev-list", "--parents", "-n", "1", commit).split()
    return tuple(fields[1:])


def _first_parent(commit: str) -> str | None:
    parents = _git("rev-list", "--parents", "-n", "1", commit).split()
    return parents[1] if len(parents) > 1 else None


def _merge_resolution_paths(commit: str) -> tuple[str, ...]:
    """Paths a merge commit changed against every parent (combined diff)."""
    output = _git("diff-tree", "-r", "-c", "--name-only", "--no-commit-id", commit)
    return tuple(line for line in output.splitlines() if line)


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
