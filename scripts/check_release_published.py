#!/usr/bin/env python3
"""
Verify that every QuickScale distribution a generated project pins is published.

Generated projects receive a bounded ``quickscale-core`` constraint derived
from the module manifests (e.g. ``quickscale-core>=0.87.0,<0.88.0``).  If the
CLI is published while ``quickscale-core`` for that version is missing from
PyPI, every ``quickscale apply`` that embeds a core-dependent module dies at
``poetry lock`` with "which doesn't match any versions".

This gate closes that hole: for the repository's current ``VERSION`` it
checks that each published distribution exists on the index, and that every
``quickscale-core`` constraint declared in ``quickscale_modules/*/module.yml``
is satisfied by at least one published release.

Usage:
    python scripts/check_release_published.py [--repo-root DIR] [--index-url URL]

Exit codes:
    0 — every pinned distribution is published
    1 — one or more distributions or constraints are unpublished
    2 — configuration/filesystem/network error
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DEFAULT_INDEX = "https://pypi.org/pypi"
PUBLISHED_DISTRIBUTIONS = ("quickscale-core", "quickscale-cli", "quickscale")
_CORE_REQUIREMENT = re.compile(r"^quickscale-core\s*(?P<spec>.*)$")
_CLAUSE = re.compile(r"(?P<op>>=|<=|==|!=|<|>|~=|\^)\s*(?P<version>[0-9][0-9.]*)")


class CheckError(Exception):
    """Raised when the check cannot be completed."""


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split(".") if part.isdigit())


def fetch_released_versions(distribution: str, index_url: str) -> list[str]:
    """Return every version published for *distribution* on the index."""
    url = f"{index_url.rstrip('/')}/{distribution}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 404:
            return []
        raise CheckError(f"Index lookup failed for {distribution}: {error}") from error
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
        raise CheckError(f"Index lookup failed for {distribution}: {error}") from error

    releases = payload.get("releases", {})
    if not isinstance(releases, dict):
        raise CheckError(f"Unexpected index payload for {distribution}")
    return [version for version, files in releases.items() if files and _version_tuple(version)]


def constraint_is_satisfied(spec: str, versions: list[str]) -> bool:
    """Return whether any of *versions* satisfies the Poetry constraint *spec*."""
    clauses = _CLAUSE.findall(spec)
    if not clauses:
        return bool(versions)

    for version in versions:
        candidate = _version_tuple(version)
        if not candidate:
            continue
        if all(_clause_holds(candidate, op, bound) for op, bound in clauses):
            return True
    return False


def _clause_holds(candidate: tuple[int, ...], op: str, bound: str) -> bool:
    target = _version_tuple(bound)
    if op == ">=":
        return candidate >= target
    if op == ">":
        return candidate > target
    if op == "<=":
        return candidate <= target
    if op == "<":
        return candidate < target
    if op == "==":
        return candidate == target
    if op == "!=":
        return candidate != target
    if op in {"~=", "^"}:
        return candidate >= target and candidate[:1] == target[:1]
    raise CheckError(f"Unsupported version operator: {op!r}")


def collect_core_constraints(repo_root: Path) -> dict[str, str]:
    """Return ``{module_name: quickscale-core spec}`` from module manifests."""
    constraints: dict[str, str] = {}
    modules_dir = repo_root / "quickscale_modules"
    if not modules_dir.is_dir():
        raise CheckError(f"Modules directory not found: {modules_dir}")

    for manifest_path in sorted(modules_dir.glob("*/module.yml")):
        for raw_line in manifest_path.read_text(encoding="utf-8").splitlines():
            stripped = raw_line.strip()
            if not stripped.startswith("- quickscale-core"):
                continue
            match = _CORE_REQUIREMENT.match(stripped[2:].strip())
            if match is None:
                continue
            constraints[manifest_path.parent.name] = match.group("spec").strip()
    return constraints


def read_version(repo_root: Path) -> str:
    version_file = repo_root / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError as error:
        raise CheckError(f"Unable to read {version_file}: {error}") from error


def run_check_with_retries(
    repo_root: Path, index_url: str, retries: int, retry_delay: float
) -> int:
    """Run the check, retrying while the index catches up after a publish."""
    for attempt in range(retries + 1):
        status = run_check(repo_root, index_url)
        if status == 0 or attempt == retries:
            return status
        print(
            f"\nIndex may not have caught up yet; retrying in "
            f"{retry_delay:.0f}s ({attempt + 1}/{retries})\n"
        )
        time.sleep(retry_delay)
    return 1


def run_check(repo_root: Path, index_url: str) -> int:
    """Run the published-release check, returning a process exit code."""
    version = read_version(repo_root)
    failures: list[str] = []

    print(f"Checking published releases for QuickScale {version} on {index_url}")

    core_versions: list[str] = []
    for distribution in PUBLISHED_DISTRIBUTIONS:
        versions = fetch_released_versions(distribution, index_url)
        if distribution == "quickscale-core":
            core_versions = versions
        if version in versions:
            print(f"  OK      {distribution}=={version}")
        else:
            print(f"  MISSING {distribution}=={version}")
            failures.append(f"{distribution}=={version} is not published")

    for module_name, spec in sorted(collect_core_constraints(repo_root).items()):
        if constraint_is_satisfied(spec, core_versions):
            print(f"  OK      {module_name}: quickscale-core{spec}")
        else:
            print(f"  MISSING {module_name}: quickscale-core{spec}")
            failures.append(
                f"module '{module_name}' pins quickscale-core{spec}, which no "
                "published release satisfies; generated projects cannot lock"
            )

    if failures:
        print("\nRelease publication check FAILED:")
        for failure in failures:
            print(f"  - {failure}")
        print(
            "\nPublish the missing distributions (scripts/publish.sh prod) before "
            "shipping the CLI; a locally built CLI must be installed with "
            "scripts/install_global.sh so it resolves its own staged wheels."
        )
        return 1

    print("\nAll pinned QuickScale distributions are published.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parent.parent,
        help="Repository root (defaults to the checkout containing this script)",
    )
    parser.add_argument(
        "--index-url",
        default=DEFAULT_INDEX,
        help=f"PyPI JSON API base URL (default: {DEFAULT_INDEX})",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=0,
        help="Retries while the index catches up after a publish (default: 0)",
    )
    parser.add_argument(
        "--retry-delay",
        type=float,
        default=20.0,
        help="Seconds between retries (default: 20)",
    )
    args = parser.parse_args(argv)

    try:
        return run_check_with_retries(
            args.repo_root.resolve(),
            args.index_url,
            max(args.retries, 0),
            max(args.retry_delay, 0.0),
        )
    except CheckError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
