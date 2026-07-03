#!/usr/bin/env python3
"""
SA16.1 — Manifest sync gate.

Compares each module's canonical manifest (``quickscale_modules/<name>/module.yml``)
against its core snapshot (``quickscale_core/src/quickscale_core/data/manifests/<name>/module.yml``)
and reports any drift.

Two modes:

  * ``--check`` (default): verify that every module-owned manifest and its core
    snapshot are byte-identical.  Exit 0 if all match, 1 if any drift is found.

  * ``--sync``: copy each module-owned manifest to the core snapshot path.
    Overwrites the snapshot with the source.  Use after intentionally updating
    a module's manifest to resync the snapshot.

When a module exists only on one side (source without snapshot or vice versa)
the script reports it as a configuration error (exit 2).

Exit codes:
    0 — all source manifests match their core snapshots (check mode) or sync
        completed successfully (sync mode)
    1 — one or more mismatches found (check mode only)
    2 — a configuration or filesystem error
"""

from __future__ import annotations

import argparse
import difflib
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPO_ROOT_ENV: str = "REPO_ROOT"
_DEFAULT_REPO_ROOT: Path = Path(os.environ.get(REPO_ROOT_ENV, os.getcwd())).resolve()

MODULES_DIR_RELATIVE: Path = Path("quickscale_modules")
MANIFESTS_DATA_RELATIVE: Path = Path("quickscale_core/src/quickscale_core/data/manifests")
MODULE_YML: str = "module.yml"


# ---------------------------------------------------------------------------
# Discovery
# ---------------------------------------------------------------------------


def _discover_module_dirs(modules_root: Path) -> list[Path]:
    """Return sorted list of subdirectories that contain a ``module.yml``."""
    return sorted(d for d in modules_root.iterdir() if d.is_dir() and (d / MODULE_YML).is_file())


def _find_orphan_snapshots(
    manifests_root: Path,
    modules_root: Path,
) -> bool:
    """
    Check for snapshot directories that have no corresponding source module.

    Returns ``True`` if any orphan is found.
    """
    orphan_found = False
    for entry in sorted(manifests_root.iterdir()):
        if not entry.is_dir():
            continue
        mod_name = entry.name
        source_yml = modules_root / mod_name / MODULE_YML
        if not source_yml.is_file():
            print(
                f"[{mod_name}] ORPHAN — snapshot exists but source module not found.",
                file=sys.stderr,
            )
            orphan_found = True
    return orphan_found


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------


def _check_manifest_sync(
    repo_root: Path,
    *,
    verbose: bool = False,
) -> int:
    """
    Compare each source manifest against its core snapshot.

    Returns an exit code (0 = all match, 1 = drift found, 2 = config error).
    """
    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()
    manifests_root = (repo_root / MANIFESTS_DATA_RELATIVE).resolve()

    if not modules_root.is_dir():
        print(
            f"ERROR: Modules directory not found: {modules_root}",
            file=sys.stderr,
        )
        return 2
    if not manifests_root.is_dir():
        print(
            f"ERROR: Core manifests directory not found: {manifests_root}",
            file=sys.stderr,
        )
        return 2

    module_dirs = _discover_module_dirs(modules_root)
    if not module_dirs:
        print("No module directories found — nothing to check.")
        # CR-SA16.1-001: scan orphans even when no source modules exist.
        if _find_orphan_snapshots(manifests_root, modules_root):
            print(
                "ERROR: Orphan snapshots found (no corresponding source module).",
                file=sys.stderr,
            )
            return 2
        return 0

    all_pass = True
    checked_count = 0
    missing_snapshot_count = 0
    mismatch_count = 0

    for mod_dir in module_dirs:
        mod_name = mod_dir.name
        source_path = mod_dir / MODULE_YML
        snapshot_path = manifests_root / mod_name / MODULE_YML

        if not snapshot_path.is_file():
            print(
                f"[{mod_name}] MISSING SNAPSHOT — source module has no core snapshot.",
                file=sys.stderr,
            )
            all_pass = False
            missing_snapshot_count += 1
            continue

        checked_count += 1
        source_text = source_path.read_bytes()
        snapshot_text = snapshot_path.read_bytes()

        if source_text == snapshot_text:
            if verbose:
                print(f"[{mod_name}] OK — source and snapshot match.")
            continue

        # Drift detected
        all_pass = False
        mismatch_count += 1
        print(f"[{mod_name}] MISMATCH — source and snapshot differ.")

        if verbose:
            source_lines = source_text.decode("utf-8").splitlines(keepends=True)
            snapshot_lines = snapshot_text.decode("utf-8").splitlines(keepends=True)
            diff = difflib.unified_diff(
                snapshot_lines,
                source_lines,
                fromfile=str(snapshot_path),
                tofile=str(source_path),
            )
            sys.stdout.writelines(diff)

    # Check for orphan snapshots (no corresponding source module)
    if _find_orphan_snapshots(manifests_root, modules_root):
        print(
            "ERROR: Orphan snapshots found (no corresponding source module).",
            file=sys.stderr,
        )
        return 2

    if missing_snapshot_count > 0:
        print(
            f"ERROR: {missing_snapshot_count} source module(s) missing core snapshot.",
            file=sys.stderr,
        )
        return 2

    if checked_count == 0:
        print("No modules with both source and snapshot found — nothing to check.")
        return 0

    if all_pass:
        print(f"\nAll {checked_count} module manifest(s) in sync.")
        return 0

    print(
        f"\n{mismatch_count} module manifest(s) out of sync.\n"
        f"Run `{Path(sys.argv[0]).name} --sync` to update snapshots from source.",
    )
    return 1


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


def _sync_manifests(repo_root: Path) -> int:
    """
    Copy each source manifest to its core snapshot path.

    Returns 0 on success, 2 on config error.
    """
    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()
    manifests_root = (repo_root / MANIFESTS_DATA_RELATIVE).resolve()

    if not modules_root.is_dir():
        print(
            f"ERROR: Modules directory not found: {modules_root}",
            file=sys.stderr,
        )
        return 2
    if not manifests_root.is_dir():
        print(
            f"ERROR: Core manifests directory not found: {manifests_root}",
            file=sys.stderr,
        )
        return 2

    module_dirs = _discover_module_dirs(modules_root)
    if not module_dirs:
        print("No module directories found — nothing to sync.")
        return 0

    synced = 0
    skipped = 0

    for mod_dir in module_dirs:
        mod_name = mod_dir.name
        source_path = mod_dir / MODULE_YML
        snapshot_dir = manifests_root / mod_name
        snapshot_path = snapshot_dir / MODULE_YML

        if not snapshot_dir.is_dir():
            print(f"[{mod_name}] Creating missing snapshot directory: {snapshot_dir}")

        source_text = source_path.read_bytes()

        if snapshot_path.is_file() and snapshot_path.read_bytes() == source_text:
            skipped += 1
            continue

        snapshot_dir.mkdir(parents=True, exist_ok=True)
        snapshot_path.write_bytes(source_text)
        print(f"[{mod_name}] SYNCED: {snapshot_path}")
        synced += 1

    total = synced + skipped
    if synced == 0:
        print(f"\nAll {total} snapshot(s) already in sync — nothing to do.")
    else:
        print(f"\nSynced {synced} manifest(s); {skipped} already in sync ({total} total).")

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Sync or check module-owned manifests against core snapshots.",
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Copy source manifests to core snapshot paths (default: check-only)",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Show per-module status and full diffs (check mode only)",
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=str,
        default=None,
        help="Repository root path (default: cwd or REPO_ROOT env)",
    )

    args = parser.parse_args(argv)

    repo_root: Path
    if args.repo_root:
        repo_root = Path(args.repo_root).resolve()
    else:
        repo_root = _DEFAULT_REPO_ROOT

    if args.sync:
        return _sync_manifests(repo_root)
    return _check_manifest_sync(repo_root, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
