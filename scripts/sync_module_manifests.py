#!/usr/bin/env python3
"""
SA280 (b) — materialize the bundled module manifests for a build.

The bundled copies under
``quickscale_core/src/quickscale_core/data/manifests/<name>/module.yml`` are
build artifacts, not tracked sources.  The repository's build entrypoints
(``make build``, ``scripts/publish.sh``, the publish workflow,
``scripts/install_global.sh``, and the installed-wheel provisioner) run this
before each ``quickscale-core`` wheel build, and the test conftests run it
before a manifest-reading suite, so an installed ``quickscale-core`` carries
the manifests its runtime reads (the ``contracts/resolvers.py`` fallback,
``contracts/module_discovery.py`` discovery, and every module's startup
retired-setting refusal).

The step is idempotent: a file whose bytes already match its source is left
untouched.  Snapshot directories with no corresponding source module are
removed, so a renamed or deleted module cannot leak a stale manifest into the
wheel.

Usage:
    python scripts/sync_module_manifests.py [--dest PATH] [REPO_ROOT]

``--dest`` overrides the destination directory (tests use a temporary
directory); by default it is the core package's ``data/manifests`` directory.

Exit codes:
    0 — every module manifest was materialized (or already current)
    2 — a configuration or filesystem error
"""

from __future__ import annotations

import argparse
import contextlib
import os
import shutil
import sys
import tempfile
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


def _remove_orphan_snapshots(manifests_root: Path, modules_root: Path) -> list[str]:
    """
    Remove snapshot directories that have no corresponding source module.

    Returns the sorted names of the removed orphans.
    """
    removed: list[str] = []
    for entry in sorted(manifests_root.iterdir()):
        if not entry.is_dir() or not (entry / MODULE_YML).is_file():
            continue
        if (modules_root / entry.name / MODULE_YML).is_file():
            continue
        try:
            shutil.rmtree(entry)
        except FileNotFoundError:
            # A concurrent materialization already removed it.
            continue
        removed.append(entry.name)
    return removed


def _atomic_write_bytes(path: Path, payload: bytes) -> None:
    """Write bytes atomically so concurrent materializations cannot interleave."""
    fd, temp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
        os.replace(temp_name, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp_name)
        raise


# ---------------------------------------------------------------------------
# Materialize
# ---------------------------------------------------------------------------


def _materialize(
    repo_root: Path,
    *,
    dest: Path | None = None,
) -> int:
    """
    Copy each source manifest to its bundled destination path.

    Returns 0 on success, 2 on config error.
    """
    modules_root = (repo_root / MODULES_DIR_RELATIVE).resolve()
    manifests_root = (
        dest.resolve() if dest is not None else (repo_root / MANIFESTS_DATA_RELATIVE).resolve()
    )

    if not modules_root.is_dir():
        print(
            f"ERROR: Modules directory not found: {modules_root}",
            file=sys.stderr,
        )
        return 2

    module_dirs = _discover_module_dirs(modules_root)
    if not module_dirs:
        print("ERROR: No module directories found — nothing to materialize.", file=sys.stderr)
        return 2

    manifests_root.mkdir(parents=True, exist_ok=True)

    written = 0
    current = 0

    for mod_dir in module_dirs:
        mod_name = mod_dir.name
        source_text = (mod_dir / MODULE_YML).read_bytes()
        dest_path = manifests_root / mod_name / MODULE_YML

        if dest_path.is_file() and dest_path.read_bytes() == source_text:
            current += 1
            continue

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_bytes(dest_path, source_text)
        print(f"[{mod_name}] materialized: {dest_path}")
        written += 1

    for orphan in _remove_orphan_snapshots(manifests_root, modules_root):
        print(f"[{orphan}] removed orphan snapshot directory")

    total = written + current
    print(f"\nMaterialized {written} manifest(s); {current} already current ({total} total).")

    return 0


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    """Parse arguments and dispatch."""
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        description="Materialize the bundled module manifests from the module sources.",
    )
    parser.add_argument(
        "--dest",
        type=str,
        default=None,
        help="Destination manifests directory (default: the core package data dir)",
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

    dest = Path(args.dest) if args.dest else None
    return _materialize(repo_root, dest=dest)


if __name__ == "__main__":
    raise SystemExit(main())
