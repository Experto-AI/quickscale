"""SA280 (b): a built quickscale-core wheel carries the bundled manifests.

The bundled manifests under ``quickscale_core/data/manifests/`` are not
tracked sources; the wheel build materializes them from
``quickscale_modules/*/module.yml``.  This test builds a real wheel from the
repository tree and inspects its members, so a build that stops materializing
them (or ships a stale set) fails here instead of at a generated project's
startup retired-setting refusal.

The build deliberately runs inside the repository's Git work tree: Poetry
applies the repository's VCS ignore rules to wheel contents, so a source copy
outside Git would not exercise the same filtering a maintainer's build sees.
"""

from __future__ import annotations

import os
import subprocess
import sys
import zipfile
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PACKAGE_DIR = _REPO_ROOT / "quickscale_core"
_MODULES_DIR = _REPO_ROOT / "quickscale_modules"
_MATERIALIZER = _REPO_ROOT / "scripts" / "sync_module_manifests.py"

#: Wheel member prefix for the bundled package data.
_MEMBER_PREFIX = "quickscale_core/data/manifests/"


def _materialize_bundled_manifests() -> None:
    result = subprocess.run(
        [sys.executable, str(_MATERIALIZER), str(_REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, (
        "manifest materialization failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )


def _build_core_wheel(output_dir: Path) -> Path:
    """Build one real wheel of the repository package as it stands."""
    output_dir.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.pop("PYTHONPATH", None)
    result = subprocess.run(
        ["poetry", "build", "--format", "wheel", "--output", str(output_dir)],
        cwd=_PACKAGE_DIR,
        capture_output=True,
        text=True,
        timeout=180,
        env=environment,
    )
    assert result.returncode == 0, (
        "quickscale-core wheel build failed:\n"
        f"stdout: {result.stdout}\nstderr: {result.stderr}"
    )
    wheels = sorted(output_dir.glob("quickscale_core-*.whl"))
    assert len(wheels) == 1, (
        "expected exactly one quickscale-core wheel, got "
        f"{[wheel.name for wheel in wheels]}"
    )
    return wheels[0]


def test_built_wheel_carries_the_materialized_manifests(tmp_path: Path) -> None:
    """The wheel's bundled manifests equal the module manifests at build time."""
    _materialize_bundled_manifests()
    wheel = _build_core_wheel(tmp_path / "wheelhouse")

    with zipfile.ZipFile(wheel) as archive:
        members = {
            name[len(_MEMBER_PREFIX) :]: archive.read(name)
            for name in archive.namelist()
            if name.startswith(_MEMBER_PREFIX) and name.endswith("/module.yml")
        }

    source_manifests = {
        f"{entry.name}/module.yml": (entry / "module.yml").read_bytes()
        for entry in sorted(_MODULES_DIR.iterdir())
        if entry.is_dir() and (entry / "module.yml").is_file()
    }
    assert source_manifests, "no module manifests discovered in the repository"
    assert members == source_manifests
