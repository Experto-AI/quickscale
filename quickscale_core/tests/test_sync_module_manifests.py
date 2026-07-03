"""Regression tests for ``scripts/sync_module_manifests.py``.

Covers the SA16.1 manifest-sync gate contract:

  * CR-SA16.1-001 — one-sided source↔snapshot pairs must fail ``--check``
    (exit 2), and ``--sync`` must create missing snapshot paths from source
    rather than silently skipping.
  * CR-SA16.1-002 — the mismatch-summary count must be correct when multiple
    modules are out of sync.
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

# Expose the two internal functions under test.
_check_manifest_sync = _sync_mod._check_manifest_sync
_sync_manifests = _sync_mod._sync_manifests
MODULE_YML = _sync_mod.MODULE_YML
MODULES_DIR_RELATIVE = _sync_mod.MODULES_DIR_RELATIVE
MANIFESTS_DATA_RELATIVE = _sync_mod.MANIFESTS_DATA_RELATIVE

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_source_module(
    repo_root: Path,
    name: str,
    content: str = "name: test\ndescription: test\nversion: 1.0.0\n",
) -> None:
    """Create a source module directory with a ``module.yml``."""
    mod_dir = repo_root / MODULES_DIR_RELATIVE / name
    mod_dir.mkdir(parents=True, exist_ok=True)
    (mod_dir / MODULE_YML).write_text(content)


def _create_snapshot(
    repo_root: Path,
    name: str,
    content: str = "name: test\ndescription: test\nversion: 1.0.0\n",
) -> None:
    """Create a core snapshot directory with a ``module.yml``."""
    snap_dir = repo_root / MANIFESTS_DATA_RELATIVE / name
    snap_dir.mkdir(parents=True, exist_ok=True)
    (snap_dir / MODULE_YML).write_text(content)


# ---------------------------------------------------------------------------
# _check_manifest_sync
# ---------------------------------------------------------------------------


class TestCheckAllMatch:
    """Baseline: matching source and snapshot must pass."""

    def test_single_module_in_sync(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a")
        _create_snapshot(tmp_path, "mod_a")
        assert _check_manifest_sync(tmp_path) == 0

    def test_multiple_modules_all_in_sync(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a")
        _create_source_module(tmp_path, "mod_b")
        _create_snapshot(tmp_path, "mod_a")
        _create_snapshot(tmp_path, "mod_b")
        assert _check_manifest_sync(tmp_path) == 0


class TestCheckMismatchContent:
    """Source/snapshot content divergence must fail with exit 1."""

    def test_single_mismatch(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a", "source content")
        _create_snapshot(tmp_path, "mod_a", "snapshot content")
        assert _check_manifest_sync(tmp_path) == 1

    def test_multiple_mismatches_reports_correct_count(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Regression for CR-SA16.1-002: mismatch count must be > 1."""
        _create_source_module(tmp_path, "mod_a", "source a")
        _create_source_module(tmp_path, "mod_b", "source b")
        _create_source_module(tmp_path, "mod_c", "source c")
        _create_snapshot(tmp_path, "mod_a", "snapshot a")
        _create_snapshot(tmp_path, "mod_b", "snapshot b")
        _create_snapshot(tmp_path, "mod_c", "snapshot c")

        rc = _check_manifest_sync(tmp_path)
        assert rc == 1

        captured = capsys.readouterr()
        # The summary line should say "3 module manifest(s) out of sync"
        assert "3 module manifest(s) out of sync" in captured.out, (
            f"Expected '3 module manifest(s) out of sync' in output, got:\n{captured.out}"
        )

    def test_mismatch_and_missing_snapshot(self, tmp_path: Path) -> None:
        """Missing snapshot takes precedence (exit 2) even alongside mismatches."""
        _create_source_module(tmp_path, "mod_a", "source a")
        _create_source_module(tmp_path, "mod_b", "source b")
        _create_snapshot(tmp_path, "mod_a", "snapshot a")
        # mod_b has no snapshot
        assert _check_manifest_sync(tmp_path) == 2


class TestCheckMissingSnapshot:
    """Regression for CR-SA16.1-001: source without snapshot must fail."""

    def test_single_module_missing_snapshot(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a")
        assert _check_manifest_sync(tmp_path) == 2

    def test_multiple_modules_missing_snapshots(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a")
        _create_source_module(tmp_path, "mod_b")
        assert _check_manifest_sync(tmp_path) == 2

    def test_some_missing_some_in_sync(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a")
        _create_source_module(tmp_path, "mod_b")
        _create_snapshot(tmp_path, "mod_a")
        assert _check_manifest_sync(tmp_path) == 2


class TestCheckOrphanSnapshot:
    """Snapshot without source module must fail."""

    def test_orphan_snapshot(self, tmp_path: Path) -> None:
        _create_snapshot(tmp_path, "orphan_mod")
        assert _check_manifest_sync(tmp_path) == 2

    def test_orphan_and_missing_snapshot(self, tmp_path: Path) -> None:
        """Both one-sided patterns produce exit 2."""
        _create_source_module(tmp_path, "orphan_source")
        _create_snapshot(tmp_path, "orphan_snap")
        assert _check_manifest_sync(tmp_path) == 2

    # ------------------------------------------------------------------
    # CR-SA16.1-001 regression: empty source tree + orphan snapshots
    # ------------------------------------------------------------------

    def test_empty_modules_dir_with_orphan_snapshot(self, tmp_path: Path) -> None:
        """Empty modules dir but orphan snapshot exists → exit 2."""
        (tmp_path / MODULES_DIR_RELATIVE).mkdir(parents=True)
        _create_snapshot(tmp_path, "orphan_mod")
        assert _check_manifest_sync(tmp_path) == 2

    def test_empty_modules_dir_multiple_orphans(self, tmp_path: Path) -> None:
        """Empty modules dir with multiple orphan snapshots → exit 2."""
        (tmp_path / MODULES_DIR_RELATIVE).mkdir(parents=True)
        _create_snapshot(tmp_path, "orphan_a")
        _create_snapshot(tmp_path, "orphan_b")
        _create_snapshot(tmp_path, "orphan_c")
        assert _check_manifest_sync(tmp_path) == 2


class TestCheckEdgeCases:
    """Edge cases for the check path."""

    def test_no_modules_at_all(self, tmp_path: Path) -> None:
        """No source module directories → pass (nothing to check)."""
        (tmp_path / MODULES_DIR_RELATIVE).mkdir(parents=True)
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True)
        assert _check_manifest_sync(tmp_path) == 0

    def test_missing_modules_dir(self, tmp_path: Path) -> None:
        """Missing modules directory → exit 2."""
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True)
        assert _check_manifest_sync(tmp_path) == 2

    def test_missing_manifests_dir(self, tmp_path: Path) -> None:
        """Missing manifests directory → exit 2."""
        (tmp_path / MODULES_DIR_RELATIVE).mkdir(parents=True)
        assert _check_manifest_sync(tmp_path) == 2


# ---------------------------------------------------------------------------
# _sync_manifests
# ---------------------------------------------------------------------------


class TestSyncBaseline:
    """Sync must pass when everything is already in sync."""

    def test_all_already_in_sync(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a")
        _create_snapshot(tmp_path, "mod_a")
        assert _sync_manifests(tmp_path) == 0

    def test_no_modules(self, tmp_path: Path) -> None:
        (tmp_path / MODULES_DIR_RELATIVE).mkdir(parents=True)
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True)
        assert _sync_manifests(tmp_path) == 0


class TestSyncCreatesMissingSnapshot:
    """Regression for CR-SA16.1-001: --sync must create missing snapshot dirs."""

    def test_creates_single_missing_snapshot(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a", "shared content")
        # The manifests root exists (it's the core data/manifests directory),
        # but no per-module snapshot directory is present.
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True, exist_ok=True)
        rc = _sync_manifests(tmp_path)
        assert rc == 0

        snapshot_path = tmp_path / MANIFESTS_DATA_RELATIVE / "mod_a" / MODULE_YML
        assert snapshot_path.is_file(), (
            f"Snapshot should have been created at {snapshot_path}"
        )
        assert snapshot_path.read_text() == "shared content"

    def test_creates_multiple_missing_snapshots(self, tmp_path: Path) -> None:
        _create_source_module(tmp_path, "mod_a", "content a")
        _create_source_module(tmp_path, "mod_b", "content b")
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True, exist_ok=True)

        rc = _sync_manifests(tmp_path)
        assert rc == 0

        for name in ("mod_a", "mod_b"):
            snapshot_path = tmp_path / MANIFESTS_DATA_RELATIVE / name / MODULE_YML
            assert snapshot_path.is_file(), (
                f"Snapshot should exist for {name} at {snapshot_path}"
            )

    def test_existing_snapshot_is_overwritten(self, tmp_path: Path) -> None:
        """Sync overwrites stale snapshot with current source."""
        _create_source_module(tmp_path, "mod_a", "newer source")
        _create_snapshot(tmp_path, "mod_a", "older snapshot")
        rc = _sync_manifests(tmp_path)
        assert rc == 0

        snapshot_path = tmp_path / MANIFESTS_DATA_RELATIVE / "mod_a" / MODULE_YML
        assert snapshot_path.read_text() == "newer source"


class TestSyncEdgeCases:
    """Edge cases for the sync path."""

    def test_missing_modules_dir(self, tmp_path: Path) -> None:
        (tmp_path / MANIFESTS_DATA_RELATIVE).mkdir(parents=True)
        assert _sync_manifests(tmp_path) == 2

    def test_missing_manifests_dir(self, tmp_path: Path) -> None:
        (tmp_path / MODULES_DIR_RELATIVE).mkdir(parents=True)
        assert _sync_manifests(tmp_path) == 2
