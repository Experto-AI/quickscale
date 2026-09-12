#!/usr/bin/env python3
"""
Require testimony for commits that change behavioural repository controls.

Every non-merge commit in the selected range that changes a GitHub workflow,
the gate registry, or an existing PostgreSQL provisioning station must carry a
``vNN`` roadmap reference in its message, either bare (``v88``) or dotted
(``v0.88.0``). No other form of testimony is accepted.

The range base is selected, in order, from ``--base-ref``,
``TESTIMONY_BASE_REF``, the GitHub event payload, ``GITHUB_BASE_REF``, or
``HEAD^`` for a local one-commit check. ``--head-ref`` defaults to ``HEAD``.

Exit codes:
    0 - every relevant commit has testimony
    1 - one or more relevant commits lack testimony
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

ROADMAP_REFERENCE_RE = re.compile(
    r"(?<![A-Za-z0-9.])v\d+(?:\.\d+)*(?![A-Za-z0-9.])",
    re.IGNORECASE,
)
DIRECTLY_PROTECTED = (".github/workflows/", "scripts/gate_registry.json")
PROVISIONING_STATION_PATHS = (
    "Makefile",
    "scripts/check_ci_locally.sh",
    "scripts/test_integration.sh",
    "scripts/test_isolation_conformance.sh",
)
PROVISIONING_MARKER = "provision_ci_postgres.sh"
ZERO_SHA_RE = re.compile(r"^0+$")


class TestimonyError(RuntimeError):
    """A deterministic input, environment, or Git failure."""


@dataclass(frozen=True)
class Violation:
    commit: str
    subject: str
    protected_surfaces: tuple[str, ...]


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
        raise TestimonyError(f"git {' '.join(args)!r} failed: {detail}")
    return result.stdout


def _event_base_ref() -> str | None:
    event_path_text = os.environ.get("GITHUB_EVENT_PATH", "").strip()
    if not event_path_text:
        return None
    event_path = Path(event_path_text)
    try:
        event = json.loads(event_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise TestimonyError(f"cannot read GitHub event payload {event_path}: {exc}") from None
    if not isinstance(event, dict):
        raise TestimonyError(f"GitHub event payload {event_path} must be a JSON object")

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
    override = os.environ.get("TESTIMONY_BASE_REF", "").strip()
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
            except TestimonyError:
                continue
            return candidate
        raise TestimonyError(
            f"GITHUB_BASE_REF {github_base!r} is unavailable; use a full-history checkout"
        )
    return "HEAD^"


def _resolve_commit(ref: str) -> str:
    if not ref or ref.startswith("-"):
        raise TestimonyError(f"unsafe or empty Git ref: {ref!r}")
    resolved = _git("rev-parse", "--verify", "--end-of-options", f"{ref}^{{commit}}").strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", resolved):
        raise TestimonyError(f"Git ref {ref!r} did not resolve to a full commit SHA")
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
        raise TestimonyError(f"cannot compare selected commits: {detail}")
    merged = _git("merge-base", base, head).strip()
    if not re.fullmatch(r"[0-9a-f]{40,64}", merged):
        raise TestimonyError("selected base and head have no valid merge base")
    return merged


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


def _file_at_commit(commit: str, path: str) -> str:
    matching_paths = _git("ls-tree", "--name-only", commit, "--", path).splitlines()
    if path not in matching_paths:
        return ""
    return _git("show", f"{commit}:{path}")


def _provisioning_station_blocks(content: str) -> tuple[str, ...]:
    lines = content.splitlines()
    blocks: list[str] = []
    seen_ranges: set[tuple[int, int]] = set()
    for marker_index, line in enumerate(lines):
        if PROVISIONING_MARKER not in line or line.lstrip().startswith("#"):
            continue

        start = marker_index
        while start > 0 and lines[start - 1].rstrip().endswith("\\"):
            start -= 1
        end = marker_index
        while end < len(lines) - 1 and lines[end].rstrip().endswith("\\"):
            end += 1

        station_range = (start, end)
        if station_range not in seen_ranges:
            blocks.append("\n".join(lines[start : end + 1]))
            seen_ranges.add(station_range)
    return tuple(blocks)


def _touches_provisioning_station(commit: str, path: str) -> bool:
    patch = _git(
        "show",
        "--format=",
        "--no-ext-diff",
        "--unified=0",
        commit,
        "--",
        path,
    )
    if any(
        line.startswith(("+", "-"))
        and not line.startswith(("+++", "---"))
        and PROVISIONING_MARKER in line
        for line in patch.splitlines()
    ):
        return True

    commit_record = _git("rev-list", "--parents", "-n", "1", commit).split()
    parent = commit_record[1] if len(commit_record) > 1 else None
    before = _file_at_commit(parent, path) if parent else ""
    after = _file_at_commit(commit, path)
    return _provisioning_station_blocks(before) != _provisioning_station_blocks(after)


def _protected_surfaces(commit: str, paths: tuple[str, ...]) -> tuple[str, ...]:
    protected: list[str] = []
    for path in paths:
        if path.startswith(DIRECTLY_PROTECTED[0]) or path == DIRECTLY_PROTECTED[1]:
            protected.append(path)
        elif path in PROVISIONING_STATION_PATHS and _touches_provisioning_station(commit, path):
            protected.append(f"{path} (provisioning station)")
    return tuple(protected)


def _violations(base: str, head: str) -> tuple[Violation, ...]:
    commits = tuple(
        line
        for line in _git("rev-list", "--reverse", "--no-merges", f"{base}..{head}").splitlines()
        if line
    )
    violations: list[Violation] = []
    for commit in commits:
        paths = _commit_paths(commit)
        protected = _protected_surfaces(commit, paths)
        if not protected:
            continue
        message = _git("show", "-s", "--format=%B", commit)
        if ROADMAP_REFERENCE_RE.search(message):
            continue
        subject = message.splitlines()[0] if message.splitlines() else "<empty commit message>"
        violations.append(Violation(commit, subject, protected))
    return tuple(violations)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ref", default=None)
    parser.add_argument("--head-ref", default="HEAD")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        base_ref = _select_base_ref(args.base_ref)
        base = _resolve_commit(base_ref)
        head = _resolve_commit(args.head_ref)
        comparison_base = _range_base(base, head)
        violations = _violations(comparison_base, head)
        if violations:
            print(
                "ERROR: [COMMIT_TESTIMONY] behavioural commits require a vNN "
                "roadmap reference in the commit message:",
                file=sys.stderr,
            )
            for violation in violations:
                print(
                    f"  {violation.commit[:12]} {violation.subject}: "
                    f"{', '.join(violation.protected_surfaces)}",
                    file=sys.stderr,
                )
            return 1
        checked = _git("rev-list", "--count", "--no-merges", f"{comparison_base}..{head}").strip()
        print(f"Commit testimony passed ({checked} non-merge commit(s) checked).")
        return 0
    except TestimonyError as exc:
        print(f"ERROR: [COMMIT_TESTIMONY] {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # pragma: no cover - last-resort fail-closed guard
        print(
            f"ERROR: [COMMIT_TESTIMONY] {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
