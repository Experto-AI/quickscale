"""Regression tests for ``scripts/sync_module_manifests.py``.

SA280 (b): the bundled manifests under
``quickscale_core/src/quickscale_core/data/manifests/`` are build artifacts
materialized from the module manifests.  These tests cover the materializer's
contract:

  * every source manifest is copied byte-identical to its destination,
    creating missing directories;
  * a stale destination is overwritten and a current one is left untouched
    (idempotence);
  * snapshot-shaped orphan directories are removed;
  * a missing or empty module workspace fails closed (exit 2);
  * ``--dest`` redirects the output for hermetic use.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Load the script module
# ---------------------------------------------------------------------------

_SCRIPT_PATH = (
    Path(__file__).resolve().parents[2] / "scripts" / "sync_module_manifests.py"
)

_spec = importlib.util.spec_from_file_location(
    "sync_module_manifests",
    _SCRIPT_PATH,
)
assert _spec is not None, f"Cannot find spec for {_SCRIPT_PATH}"
_sync_mod = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_sync_mod)

_materialize = _sync_mod._materialize
MODULE_YML = _sync_mod.MODULE_YML
MODULES_DIR_RELATIVE = _sync_mod.MODULES_DIR_RELATIVE
MANIFESTS_DATA_RELATIVE = _sync_mod.MANIFESTS_DATA_RELATIVE

_REPO_ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write_source_module(
    repo_root: Path,
    name: str,
    content: str = "name: test\ndescription: test\nversion: 1.0.0\n",
) -> None:
    """Create a source module directory with a ``module.yml``."""
    mod_dir = repo_root / MODULES_DIR_RELATIVE / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / MODULE_YML).write_text(content)


def _dest_path(repo_root: Path, name: str) -> Path:
    return repo_root / MANIFESTS_DATA_RELATIVE / name / MODULE_YML


# ---------------------------------------------------------------------------
# Materialize
# ---------------------------------------------------------------------------


class TestMaterialize:
    """The materializer copies sources to the bundled destination."""

    def test_creates_missing_snapshot_directories(self, tmp_path: Path) -> None:
        _write_source_module(tmp_path, "mod_a", "shared content")
        # The manifests root exists (it is the core data/manifests directory),
        # but no per-module destination directory is present.
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True, exist_ok=True)

        assert _materialize(tmp_path) == 0

        dest = _dest_path(tmp_path, "mod_a")
        assert dest.is_file(), f"Manifest should have been materialized at {dest}"
        assert dest.read_text() == "shared content"

    def test_creates_multiple_missing_snapshots(self, tmp_path: Path) -> None:
        _write_source_module(tmp_path, "mod_a", "content a")
        _write_source_module(tmp_path, "mod_b", "content b")
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True, exist_ok=True)

        assert _materialize(tmp_path) == 0

        assert _dest_path(tmp_path, "mod_a").read_text() == "content a"
        assert _dest_path(tmp_path, "mod_b").read_text() == "content b"

    def test_existing_snapshot_is_overwritten(self, tmp_path: Path) -> None:
        """A stale destination is replaced with the current source bytes."""
        _write_source_module(tmp_path, "mod_a", "newer source")
        stale = _dest_path(tmp_path, "mod_a")
        stale.parent.mkdir(parents=True)
        stale.write_text("older snapshot")

        assert _materialize(tmp_path) == 0

        assert stale.read_text() == "newer source"

    def test_second_run_is_idempotent(self, tmp_path: Path) -> None:
        """A current destination keeps its bytes and mtime on a second run."""
        _write_source_module(tmp_path, "mod_a", "stable content")
        assert _materialize(tmp_path) == 0
        dest = _dest_path(tmp_path, "mod_a")
        first_mtime = dest.stat().st_mtime_ns

        assert _materialize(tmp_path) == 0

        assert dest.read_text() == "stable content"
        assert dest.stat().st_mtime_ns == first_mtime

    def test_orphan_snapshot_directory_is_removed(self, tmp_path: Path) -> None:
        """A snapshot-shaped directory without a source module is removed."""
        _write_source_module(tmp_path, "mod_a", "content a")
        orphan = tmp_path / MANIFESTS_DATA_RELATIVE / "orphan_mod"
        orphan.mkdir(parents=True)
        (orphan / MODULE_YML).write_text("name: orphan\n")

        assert _materialize(tmp_path) == 0

        assert not orphan.exists()
        assert _dest_path(tmp_path, "mod_a").read_text() == "content a"

    def test_cache_directory_without_manifest_is_kept(self, tmp_path: Path) -> None:
        """A cache directory (no ``module.yml``) is not an orphan snapshot."""
        _write_source_module(tmp_path, "mod_a", "content a")
        cache_dir = tmp_path / MANIFESTS_DATA_RELATIVE / "__pycache__"
        cache_dir.mkdir(parents=True)
        (cache_dir / "module.cpython-314.pyc").write_bytes(b"generated cache")

        assert _materialize(tmp_path) == 0

        assert cache_dir.is_dir()

    def test_dest_override_is_used(self, tmp_path: Path) -> None:
        """``--dest`` (the ``dest`` argument) redirects the output."""
        _write_source_module(tmp_path, "mod_a", "content a")
        destination = tmp_path / "elsewhere" / "manifests"

        assert _materialize(tmp_path, dest=destination) == 0

        assert (destination / "mod_a" / MODULE_YML).read_text() == "content a"
        assert not (tmp_path / MANIFESTS_DATA_RELATIVE).exists()


class TestMaterializeFailures:
    """A missing or empty module workspace fails closed."""

    def test_missing_modules_dir(self, tmp_path: Path) -> None:
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True)
        assert _materialize(tmp_path) == 2

    def test_empty_modules_dir(self, tmp_path: Path) -> None:
        """No module directories means nothing to materialize; exit 2."""
        (tmp_path / MODULES_DIR_RELATIVE).mkdir(parents=True)
        assert _materialize(tmp_path) == 2

    def test_non_module_entries_are_ignored(self, tmp_path: Path) -> None:
        """A directory without ``module.yml`` is not a module workspace."""
        (tmp_path / MODULES_DIR_RELATIVE / "not_a_module").mkdir(parents=True)
        assert _materialize(tmp_path) == 2


class TestRepositoryMaterialization:
    """The real repository derives the bundled tree from the module manifests."""

    def test_bundled_tree_matches_every_module_manifest(self) -> None:
        assert _materialize(_REPO_ROOT) == 0
        modules_root = _REPO_ROOT / MODULES_DIR_RELATIVE
        sources = sorted(
            entry.name
            for entry in modules_root.iterdir()
            if entry.is_dir() and (entry / MODULE_YML).is_file()
        )
        assert sources, "no module manifests discovered in the repository"
        for name in sources:
            bundled = _dest_path(_REPO_ROOT, name)
            assert bundled.is_file(), f"missing materialized manifest for {name}"
            assert (
                bundled.read_bytes() == (modules_root / name / MODULE_YML).read_bytes()
            )


@pytest.mark.parametrize("mode", [0, 2])
def test_main_returns_documented_exit_codes(tmp_path: Path, mode: int) -> None:
    """``main()`` maps the materializer result onto its exit code."""
    if mode == 0:
        _write_source_module(tmp_path, "mod_a", "content a")
    assert _sync_mod.main([str(tmp_path)]) == mode
