"""
Repository-root pytest configuration.

SA280 (b): ``quickscale_core/data/manifests/`` is a build artifact, so a fresh
clone has no bundled manifests on disk.  Scripts and repository suites that
read the bundled tree (for example the publish-module and installed-wheel
suites) materialize it here exactly as a wheel build does.  ``quickscale_core``
tests carry the same bootstrap in their own conftest because their pytest
rootdir never loads this file.
"""

import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent


def _materialize_bundled_manifests() -> None:
    script = _REPO_ROOT / "scripts" / "sync_module_manifests.py"
    if not (_REPO_ROOT / "quickscale_modules").is_dir() or not script.is_file():
        return
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        [sys.executable, str(script), str(_REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "failed to materialize the bundled module manifests:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


_materialize_bundled_manifests()
