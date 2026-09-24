#!/usr/bin/env python3
"""
Require a project-vintage declaration edit for generated-template contract changes.

Every non-merge commit in the selected range that changes a generated-project
contract template — ``templates/project_name/settings/*``, ``start.sh.j2``, or
``Dockerfile.j2`` — must also change the project contract declaration
``quickscale_core/src/quickscale_core/data/project_contract.yml`` and declare a
step id the parent did not declare, so a template contract change can never
ship without a fresh adoption step (editing existing prose, or the declaration
alone, would leave already-adopted projects passing enforcement).

The rule applies from the commit that introduces the declaration onward: the
introduction is a monotonic baseline, so a commit that predates it is exempt
(historical template changes do not block a release pull request) and deleting
the declaration later cannot switch enforcement back off.  Merge commits are
checked only where the resolution changed a template against every parent, so
a change inherited from one side is not blamed on the merge author; a
reintroduced id never counts as new.

The range base is selected, in order, from ``--base-ref``,
``PROJECT_VINTAGE_BASE_REF``, the GitHub event payload, ``GITHUB_BASE_REF``, or
``HEAD^`` for a local one-commit check.  ``--head-ref`` defaults to ``HEAD``.
``--staged`` checks the index instead of a commit range, for pre-commit.

Exit codes:
    0 - every relevant commit declares a project-vintage edit
    1 - one or more relevant commits lack the declaration edit
    2 - Git or input failure; the gate fails closed
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

TEMPLATE_ROOT = "quickscale_core/src/quickscale_core/generator/templates/"
SETTINGS_TEMPLATE_PREFIX = f"{TEMPLATE_ROOT}project_name/settings/"
CONTRACT_TEMPLATE_PATHS = frozenset(
    {
        f"{TEMPLATE_ROOT}start.sh.j2",
        f"{TEMPLATE_ROOT}Dockerfile.j2",
    }
)
DECLARATION_PATH = "quickscale_core/src/quickscale_core/data/project_contract.yml"
ZERO_SHA_RE = re.compile(r"^0+$")


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


def _is_template_contract_path(path: str) -> bool:
    return path.startswith(SETTINGS_TEMPLATE_PREFIX) or path in CONTRACT_TEMPLATE_PATHS


def _template_contract_paths(paths: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(path for path in paths if _is_template_contract_path(path))


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


def _violations(base: str, head: str) -> tuple[Violation, ...]:
    commits = tuple(
        line for line in _git("rev-list", "--reverse", f"{base}..{head}").splitlines() if line
    )
    baseline = _introduction_commit(head)
    violations: list[Violation] = []
    for commit in commits:
        parents = _parents(commit)
        if len(parents) > 1:
            # A merge resolution can introduce contract bytes that no
            # non-merge commit carries; inherited changes are not resolutions.
            template_paths = _template_contract_paths(_merge_resolution_paths(commit))
            if not template_paths:
                continue
            if _merge_declares_new_step(commit, parents):
                continue
            if baseline is None or _is_ancestor(commit, baseline):
                continue
            subject = _git("show", "-s", "--format=%s", commit).strip()
            violations.append(
                Violation(
                    commit,
                    subject,
                    template_paths,
                    reason="merge resolution with no new adoption step id",
                )
            )
            continue

        paths = _commit_paths(commit)
        template_paths = _template_contract_paths(paths)
        if not template_paths:
            continue
        if _declares_vintage(commit, paths):
            # Editing the declaration is not enough: a changed template must
            # declare a new step id, or projects that already recorded the
            # old ids would keep passing enforcement.
            if _declares_new_step(commit):
                continue
            subject = _git("show", "-s", "--format=%s", commit).strip()
            violations.append(
                Violation(
                    commit,
                    subject,
                    template_paths,
                    reason="no new adoption step id",
                )
            )
            continue
        if baseline is None or _is_ancestor(commit, baseline):
            continue
        subject = _git("show", "-s", "--format=%s", commit).strip()
        violations.append(Violation(commit, subject, template_paths))
    return tuple(violations)


def _staged_paths() -> tuple[str, ...]:
    output = _git("diff", "--cached", "--name-only")
    return tuple(line for line in output.splitlines() if line)


def _staged_violation() -> Violation | None:
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
        return None

    paths = _staged_paths()

    if merge_head_sha is not None:
        # Only resolution edits matter: a path that differs from both parents.
        # A change inherited from one side is not this author's edit to declare.
        changed_vs_merge = set(_git("diff", "--cached", "--name-only", merge_head_sha).splitlines())
        resolution_paths = tuple(path for path in paths if path in changed_vs_merge)
        template_paths = _template_contract_paths(resolution_paths)
        if not template_paths:
            return None
        if not _path_exists_in_index(DECLARATION_PATH):
            return Violation(
                "index",
                "staged changes",
                template_paths,
                reason="the declaration is absent from the merge resolution",
            )
        historical = _historical_step_ids("HEAD") | _historical_step_ids(merge_head_sha)
        if _index_declared_step_ids() - historical:
            return None
        return Violation(
            "index",
            "staged changes",
            template_paths,
            reason="no new adoption step id",
        )

    template_paths = _template_contract_paths(paths)
    if not template_paths:
        return None
    if DECLARATION_PATH in paths:
        if not _path_exists_in_index(DECLARATION_PATH):
            return Violation(
                "index",
                "staged changes",
                template_paths,
                reason="the declaration is staged for deletion",
            )
        if _index_declared_step_ids() - _historical_step_ids("HEAD"):
            return None
        return Violation(
            "index",
            "staged changes",
            template_paths,
            reason="no new adoption step id",
        )
    return Violation("index", "staged changes", template_paths)


def _report(violations: tuple[Violation, ...]) -> None:
    print(
        "ERROR: [PROJECT_CONTRACT_VINTAGE] generated-project contract templates "
        "changed without a project-vintage edit:",
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
        "in the same commit (see the SA207 declaration block).",
        file=sys.stderr,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Fail when a generated-project contract template changes without a "
            "project-vintage declaration edit."
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
            violation = _staged_violation()
            violations = (violation,) if violation is not None else ()
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
