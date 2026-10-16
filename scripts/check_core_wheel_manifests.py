#!/usr/bin/env python3
"""
SA284 — content-check the built quickscale-core wheel's bundled manifests.

The wheel the publish workflow uploads must carry every module manifest the
installed runtime reads, at ``quickscale_core/data/manifests/<name>/module.yml``
for each ``quickscale_modules/<name>/module.yml``.  The release build
materializes those copies before ``poetry build``
(``scripts/sync_module_manifests.py``), but nothing inspected the artifact that
is actually published, so a dropped or stale copy would ship a broken core to
every installed project.

The check opens the built wheel and compares its bundled manifest members with
the module sources byte-for-byte; a missing, extra, or changed member fails.
The expected set is derived from ``quickscale_modules/*/module.yml``, never
from the materializer's copy, so the check stays independent of the step it
verifies.

Usage:
    python scripts/check_core_wheel_manifests.py [--dist-dir PATH] [REPO_ROOT]

The publish workflow's build job copies every package's distributions into
``<REPO_ROOT>/dist``; ``--dist-dir`` overrides that location for other callers.

Exit codes:
    0 — the wheel carries exactly the module manifests, byte-identical
    1 — one or more bundled manifests are missing, extra, or changed
    2 — the distribution directory, the module sources, or the wheel could not
        be inspected (fail closed)
"""

from __future__ import annotations

import argparse
import os
import sys
import zipfile
from pathlib import Path

MODULES_DIR_RELATIVE: Path = Path("quickscale_modules")
DIST_DIR_RELATIVE: Path = Path("dist")
MODULE_YML: str = "module.yml"
CORE_WHEEL_GLOB: str = "quickscale_core-*.whl"

#: Wheel member prefix for the bundled package data; mirrors the include in
#: ``quickscale_core/pyproject.toml`` and the core build-and-inspect test.
MEMBER_PREFIX: str = "quickscale_core/data/manifests/"


class _InspectionError(Exception):
    """The distribution, the module sources, or the wheel could not be read."""


def _find_core_wheel(dist_dir: Path) -> Path:
    """Return the one built core wheel in ``dist_dir`` or fail closed."""
    if not dist_dir.is_dir():
        raise _InspectionError(f"distribution directory not found: {dist_dir}")
    wheels = sorted(dist_dir.glob(CORE_WHEEL_GLOB))
    if not wheels:
        raise _InspectionError(
            f"no {CORE_WHEEL_GLOB} wheel in {dist_dir}: the core package must be built first"
        )
    if len(wheels) > 1:
        names = ", ".join(wheel.name for wheel in wheels)
        raise _InspectionError(f"expected exactly one core wheel in {dist_dir}, found: {names}")
    return wheels[0]


def _source_manifests(modules_root: Path) -> dict[str, bytes]:
    """Return each module manifest as ``<name>/module.yml`` -> bytes."""
    if not modules_root.is_dir():
        raise _InspectionError(f"modules directory not found: {modules_root}")
    manifests = {
        f"{entry.name}/{MODULE_YML}": (entry / MODULE_YML).read_bytes()
        for entry in sorted(modules_root.iterdir())
        if entry.is_dir() and (entry / MODULE_YML).is_file()
    }
    if not manifests:
        raise _InspectionError(f"no module manifests found under {modules_root}")
    return manifests


def _wheel_manifests(wheel_path: Path) -> dict[str, bytes]:
    """Return the wheel's bundled manifests as ``<name>/module.yml`` -> bytes."""
    try:
        with zipfile.ZipFile(wheel_path) as archive:
            return {
                name[len(MEMBER_PREFIX) :]: archive.read(name)
                for name in archive.namelist()
                if name.startswith(MEMBER_PREFIX) and name.endswith(f"/{MODULE_YML}")
            }
    except (OSError, zipfile.BadZipFile) as exc:
        raise _InspectionError(f"cannot read wheel {wheel_path}: {exc}") from exc


def _collect_violations(
    source_manifests: dict[str, bytes],
    wheel_manifests: dict[str, bytes],
) -> list[str]:
    """Return deterministic violation messages for the two manifest maps."""
    violations = [
        f"{key}: bundled manifest is missing from the wheel"
        for key in sorted(set(source_manifests) - set(wheel_manifests))
    ]
    violations.extend(
        f"{key}: bundled manifest has no module source"
        for key in sorted(set(wheel_manifests) - set(source_manifests))
    )
    violations.extend(
        f"{key}: bundled manifest differs from the module source"
        for key in sorted(set(source_manifests) & set(wheel_manifests))
        if source_manifests[key] != wheel_manifests[key]
    )
    return violations


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Check a built quickscale-core wheel's bundled module manifests.",
    )
    parser.add_argument(
        "--dist-dir",
        type=str,
        default=None,
        help="Directory holding the built wheel (default: <REPO_ROOT>/dist)",
    )
    parser.add_argument(
        "repo_root",
        nargs="?",
        type=str,
        default=None,
        help="Repository root path (default: cwd or REPO_ROOT env)",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Run the wheel-manifest check and return an exit code."""
    args = _parse_args(argv)
    repo_root = (
        Path(args.repo_root).resolve()
        if args.repo_root
        else Path(os.environ.get("REPO_ROOT", os.getcwd())).resolve()
    )
    dist_dir = Path(args.dist_dir).resolve() if args.dist_dir else repo_root / DIST_DIR_RELATIVE

    try:
        wheel = _find_core_wheel(dist_dir)
        source_manifests = _source_manifests(repo_root / MODULES_DIR_RELATIVE)
        wheel_manifests = _wheel_manifests(wheel)
    except _InspectionError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"ERROR: I/O error: {exc}", file=sys.stderr)
        return 2

    violations = _collect_violations(source_manifests, wheel_manifests)
    if violations:
        print(f"Bundled manifest violations in {wheel.name}:")
        for violation in violations:
            print(f"  {violation}")
        print(
            f"\n{len(violations)} violation(s) found.\n"
            "The wheel must carry every module manifest byte-identical to its "
            "quickscale_modules source; run scripts/sync_module_manifests.py before "
            "the wheel build."
        )
        return 1

    print(
        f"{wheel.name} carries {len(source_manifests)} bundled module manifest(s) "
        "byte-identical to the module sources."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
