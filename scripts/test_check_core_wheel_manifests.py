"""
Focused tests for ``scripts/check_core_wheel_manifests.py`` (SA284).

The checker content-checks the core wheel the publish workflow uploads; these
tests build synthetic wheels in the real member layout and prove the pass and
the fail-closed controls, including the required control wheel with one
manifest removed.
"""

from __future__ import annotations

import subprocess
import sys
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = Path(__file__).resolve().parent / "check_core_wheel_manifests.py"
MODULES_DIR = REPO_ROOT / "quickscale_modules"

#: The real wheel member layout: the core package's bundled package data.
MEMBER_PREFIX = "quickscale_core/data/manifests/"
WHEEL_NAME = "quickscale_core-0.0.0-py3-none-any.whl"


def _source_manifests() -> dict[str, bytes]:
    """Return the module manifests exactly as the built wheel must bundle them."""
    manifests = {
        entry.name: (entry / "module.yml").read_bytes()
        for entry in sorted(MODULES_DIR.iterdir())
        if entry.is_dir() and (entry / "module.yml").is_file()
    }
    assert manifests, "no module manifests discovered in the repository"
    return manifests


def _write_wheel(dist_dir: Path, manifests: dict[str, bytes], name: str = WHEEL_NAME) -> Path:
    """Write a synthetic core wheel carrying ``manifests`` at the real paths."""
    dist_dir.mkdir(parents=True, exist_ok=True)
    wheel = dist_dir / name
    with zipfile.ZipFile(wheel, "w") as archive:
        for module, payload in sorted(manifests.items()):
            archive.writestr(f"{MEMBER_PREFIX}{module}/module.yml", payload)
        archive.writestr("quickscale_core/__init__.py", b"# synthetic wheel\n")
    return wheel


def _run_check(dist_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(REPO_ROOT), "--dist-dir", str(dist_dir)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_wheel_with_every_module_manifest_passes(tmp_path: Path) -> None:
    sources = _source_manifests()
    _write_wheel(tmp_path, sources)

    result = _run_check(tmp_path)

    assert result.returncode == 0, result.stderr
    assert f"{len(sources)} bundled module manifest(s)" in result.stdout


def test_control_wheel_with_one_manifest_removed_fails(tmp_path: Path) -> None:
    sources = _source_manifests()
    assert len(sources) > 1, "need more than one module manifest to remove one"
    missing = sorted(sources)[0]
    payload = {module: sources[module] for module in sources if module != missing}
    _write_wheel(tmp_path, payload)

    result = _run_check(tmp_path)

    assert result.returncode == 1
    assert f"{missing}/module.yml: bundled manifest is missing from the wheel" in result.stdout


def test_changed_bundled_bytes_fail(tmp_path: Path) -> None:
    sources = _source_manifests()
    changed = sorted(sources)[0]
    payload = dict(sources)
    payload[changed] += b"\n# drift\n"
    _write_wheel(tmp_path, payload)

    result = _run_check(tmp_path)

    assert result.returncode == 1
    assert f"{changed}/module.yml: bundled manifest differs from the module source" in result.stdout


def test_extra_bundled_manifest_fails(tmp_path: Path) -> None:
    payload = dict(_source_manifests())
    payload["zzz-unshipped"] = b"name: zzz-unshipped\n"
    _write_wheel(tmp_path, payload)

    result = _run_check(tmp_path)

    assert result.returncode == 1
    assert "zzz-unshipped/module.yml: bundled manifest has no module source" in result.stdout


def test_missing_wheel_is_fail_closed(tmp_path: Path) -> None:
    result = _run_check(tmp_path)

    assert result.returncode == 2
    assert "no quickscale_core-*.whl wheel" in result.stderr


def test_multiple_core_wheels_are_fail_closed(tmp_path: Path) -> None:
    sources = _source_manifests()
    _write_wheel(tmp_path, sources, name=WHEEL_NAME)
    _write_wheel(tmp_path, sources, name="quickscale_core-0.0.1-py3-none-any.whl")

    result = _run_check(tmp_path)

    assert result.returncode == 2
    assert "expected exactly one core wheel" in result.stderr
