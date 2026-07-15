"""Tests for quickscale_core.dr_engine.adapter.

Covers:
* ``ADAPTER_FUNCTIONS`` registry and ``_register`` decorator.
* ``build_database_plan`` — metadata validation, success path.
* ``execute_database_restore`` — metadata validation.
* ``capture_snapshot`` — missing snapshot error, BackupError passthrough.
* ``restore_backup`` — artifact-not-found error.
* ``validate_artifact`` — artifact-not-found error.
* ``prune_backups`` — delegation to orchestration.
* ``sync_media`` — delegation to orchestration.
* ``clear_rollback_pin`` — delegation to orchestration.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.dr_engine.adapter import (
    ADAPTER_FUNCTIONS,
    _register,
    build_database_plan,
    capture_snapshot,
    clear_rollback_pin,
    execute_database_restore,
    prune_backups,
    restore_backup,
    sync_media,
    validate_artifact,
)
from quickscale_core.dr_engine.primitives import BackupError


# ---------------------------------------------------------------------------
# Autouse fixture — mock orchestration to avoid Django/model import chains
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _mock_orch_and_backups() -> MagicMock:
    """Pre-populate sys.modules so lazy imports resolve cleanly.

    Adapter functions lazily import from
    ``quickscale_core.dr_engine.orchestration`` (which at module level
    used to import ``quickscale_modules_backups.models``, requiring Django).
    SA89b Phase 1: orchestration no longer imports models at module level;
    adapter functions import ``get_backup_artifact`` from the Django-free
    ``quickscale_core.dr_engine.persistence``, so we mock persistence too.
    """
    mock_orch = MagicMock()
    mock_persistence = MagicMock()
    mock_backups = MagicMock()
    with patch.dict(
        "sys.modules",
        {
            "quickscale_core.dr_engine.orchestration": mock_orch,
            "quickscale_core.dr_engine.persistence": mock_persistence,
            "quickscale_modules_backups": MagicMock(),
            "quickscale_modules_backups.models": mock_backups,
        },
    ):
        # Provide a real exception type for DoesNotExist so except
        # clauses that catch BackupArtifact.DoesNotExist work (legacy).
        mock_backups.BackupArtifact.DoesNotExist = type(
            "DoesNotExist", (Exception,), {}
        )
        yield (mock_orch, mock_persistence, mock_backups)


# ===================================================================
# Registry
# ===================================================================


class TestAdapterRegistry:
    """ADAPTER_FUNCTIONS dict and _register decorator."""

    _EXPECTED_KEYS = {
        "capture_snapshot",
        "fetch_snapshot_report",
        "record_verification",
        "set_rollback_pin",
        "build_database_plan",
        "execute_database_restore",
        "sync_media",
        "prune_backups",
        "validate_artifact",
        "clear_rollback_pin",
        "restore_backup",
    }

    def test_adapter_functions_is_dict(self) -> None:
        assert isinstance(ADAPTER_FUNCTIONS, dict)

    def test_registry_contains_all_expected_keys(self) -> None:
        assert self._EXPECTED_KEYS.issubset(ADAPTER_FUNCTIONS.keys()), (
            f"Missing: {self._EXPECTED_KEYS - set(ADAPTER_FUNCTIONS.keys())}"
        )

    def test_registry_values_are_callable(self) -> None:
        for name, fn in ADAPTER_FUNCTIONS.items():
            assert callable(fn), f"ADAPTER_FUNCTIONS[{name!r}] is not callable"

    def test_register_decorator_adds_to_dict(self) -> None:
        @_register
        def _test_fn() -> str:
            return "ok"

        assert _test_fn.__name__ in ADAPTER_FUNCTIONS
        assert ADAPTER_FUNCTIONS[_test_fn.__name__] is _test_fn

    def test_no_unexpected_registry_keys(self) -> None:
        """Fail fast if a new function is registered without updating this test.

        ``_test_fn`` is registered by ``test_register_decorator_adds_to_dict``
        and is cleaned up here to prevent test-order interference.
        """
        ADAPTER_FUNCTIONS.pop("_test_fn", None)
        unexpected = set(ADAPTER_FUNCTIONS.keys()) - self._EXPECTED_KEYS
        assert not unexpected, f"Unexpected registry entries: {unexpected}"


# ===================================================================
# build_database_plan
# ===================================================================


class TestBuildDatabasePlan:
    """build_database_plan — metadata validation and delegation."""

    @staticmethod
    def _valid_report() -> dict[str, object]:
        return {
            "snapshot_id": "snap-001",
            "authoritative_dump": {
                "local_path": "/tmp/dumps/snap-001.dump",
                "restore_scope": "full",
                "restore_scope_label": "Full database",
            },
            "confirmation_value": "snap-001",
        }

    @pytest.mark.parametrize(
        ("report", "desc"),
        [
            (
                {"snapshot_id": "s1", "confirmation_value": "s1"},
                "missing authoritative_dump",
            ),
            (
                {
                    "snapshot_id": "s1",
                    "authoritative_dump": {"local_path": ""},
                    "confirmation_value": "s1",
                },
                "empty local_path",
            ),
            (
                {"snapshot_id": "s1", "authoritative_dump": {"local_path": "/d/dump"}},
                "missing confirmation_value",
            ),
            (
                {
                    "snapshot_id": "s1",
                    "authoritative_dump": {"local_path": "/d/dump"},
                    "confirmation_value": "",
                },
                "empty confirmation_value",
            ),
        ],
    )
    def test_missing_or_empty_metadata_raises(
        self, report: dict[str, object], desc: str
    ) -> None:
        with pytest.raises(BackupError, match="missing its authoritative restore file"):
            build_database_plan(report)

    def test_success_delegates_to_restore_backup_source(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.restore_backup_source.return_value = MagicMock(message="Plan ready")

        result = build_database_plan(self._valid_report())

        assert result["status"] == "ready"
        assert result["message"] == "Plan ready"
        assert result["restore_file"] == "/tmp/dumps/snap-001.dump"
        assert result["confirmation_value"] == "snap-001"
        assert result["restore_scope"] == "full"
        assert result["restore_scope_label"] == "Full database"
        mock_orch.restore_backup_source.assert_called_once_with(
            file_path="/tmp/dumps/snap-001.dump",
            confirmation="snap-001",
            dry_run=True,
        )


# ===================================================================
# execute_database_restore
# ===================================================================


class TestExecuteDatabaseRestore:
    """execute_database_restore — metadata validation error paths.

    The success path requires Django (call_command, migrate, check) which
    is beyond the scope of these unit tests.
    """

    @pytest.mark.parametrize(
        ("report", "desc"),
        [
            (
                {"snapshot_id": "s1", "confirmation_value": "s1"},
                "missing authoritative_dump",
            ),
            (
                {
                    "snapshot_id": "s1",
                    "authoritative_dump": {"local_path": ""},
                    "confirmation_value": "s1",
                },
                "empty local_path",
            ),
            (
                {"snapshot_id": "s1", "authoritative_dump": {"local_path": "/d/dump"}},
                "missing confirmation_value",
            ),
        ],
    )
    def test_missing_or_empty_metadata_raises(
        self, report: dict[str, object], desc: str
    ) -> None:
        with pytest.raises(BackupError, match="missing its authoritative restore file"):
            execute_database_restore(report)


# ===================================================================
# capture_snapshot
# ===================================================================


class TestCaptureSnapshot:
    """capture_snapshot — error paths."""

    def test_missing_authoritative_snapshot_raises(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.create_backup.return_value = MagicMock(authoritative_snapshot=None)

        with pytest.raises(BackupError, match="missing its stored snapshot record"):
            capture_snapshot(trigger="manual")

        mock_orch.create_backup.assert_called_once_with(
            trigger="manual", resume_snapshot_id=None
        )

    def test_passes_resume_snapshot_id(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.create_backup.return_value = MagicMock(authoritative_snapshot=None)

        with pytest.raises(BackupError):
            capture_snapshot(trigger="scheduled", resume_snapshot_id="res-001")

        mock_orch.create_backup.assert_called_once_with(
            trigger="scheduled", resume_snapshot_id="res-001"
        )

    def test_create_backup_failure_re_raised(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.create_backup.side_effect = BackupError("storage full")

        with pytest.raises(BackupError, match="storage full"):
            capture_snapshot(trigger="manual")


# ===================================================================
# restore_backup
# ===================================================================


class TestRestoreBackup:
    """restore_backup — artifact-not-found error path."""

    def test_artifact_id_not_found_raises(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, mock_persistence, _ = _mock_orch_and_backups
        # Make get_backup_artifact raise BackupError
        from quickscale_core.dr_engine.primitives import BackupError

        mock_persistence.get_backup_artifact.side_effect = BackupError(
            "Backup artifact not found: 999"
        )

        with pytest.raises(BackupError, match="Backup artifact not found"):
            restore_backup(artifact_id=999, confirmation="snap-001")


# ===================================================================
# validate_artifact
# ===================================================================


class TestValidateArtifact:
    """validate_artifact — artifact-not-found error path."""

    def test_artifact_not_found_raises(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        _, mock_persistence, _ = _mock_orch_and_backups
        from quickscale_core.dr_engine.primitives import BackupError

        mock_persistence.get_backup_artifact.side_effect = BackupError(
            "Backup artifact not found: 999"
        )

        with pytest.raises(BackupError, match="Backup artifact not found"):
            validate_artifact(artifact_id=999)


# ===================================================================
# prune_backups
# ===================================================================


class TestPruneBackups:
    """prune_backups — delegation to orchestration."""

    def test_delegates_to_prune_expired_backups(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.prune_expired_backups.return_value = 3

        result = prune_backups()
        assert result == {"deleted_count": 3}
        mock_orch.prune_expired_backups.assert_called_once_with()

    def test_zero_deleted(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.prune_expired_backups.return_value = 0

        result = prune_backups()
        assert result == {"deleted_count": 0}


# ===================================================================
# sync_media
# ===================================================================


class TestSyncMedia:
    """sync_media — delegation to orchestration."""

    def test_delegates_to_sync_backup_snapshot_media(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.sync_backup_snapshot_media.return_value = {
            "synced": True,
            "files": 5,
        }

        result = sync_media(
            snapshot_id="snap-001",
            dry_run=True,
            target_runtime_settings={"bucket": "my-bucket"},
        )
        assert result == {"synced": True, "files": 5}
        mock_orch.sync_backup_snapshot_media.assert_called_once_with(
            "snap-001",
            dry_run=True,
            target_runtime_settings={"bucket": "my-bucket"},
        )


# ===================================================================
# clear_rollback_pin
# ===================================================================


# ===================================================================
# fetch_snapshot_report
# ===================================================================


class TestFetchSnapshotReport:
    """fetch_snapshot_report — delegation to orchestration."""

    def test_delegates_to_report_backup_snapshot(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.report_backup_snapshot.return_value = {
            "snapshot_id": "snap-001",
            "status": "complete",
        }

        from quickscale_core.dr_engine.adapter import fetch_snapshot_report

        result = fetch_snapshot_report(
            snapshot_id="snap-001",
            sidecar_payloads=("env-vars",),
        )
        assert result == {"snapshot_id": "snap-001", "status": "complete"}
        mock_orch.report_backup_snapshot.assert_called_once_with(
            "snap-001",
            sidecar_payloads=("env-vars",),
        )


# ===================================================================
# record_verification
# ===================================================================


class TestRecordVerification:
    """record_verification — delegation to orchestration."""

    def test_delegates_to_record_backup_snapshot_verification(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.record_backup_snapshot_verification.return_value = {
            "recorded": True,
        }

        from quickscale_core.dr_engine.adapter import record_verification

        result = record_verification(
            snapshot_id="snap-001",
            route="restore",
            phase="plan",
            status="pass",
            payload={"check": "ok"},
        )
        assert result == {"recorded": True}
        mock_orch.record_backup_snapshot_verification.assert_called_once_with(
            "snap-001",
            route="restore",
            phase="plan",
            status="pass",
            payload={"check": "ok"},
        )


# ===================================================================
# set_rollback_pin
# ===================================================================


class TestSetRollbackPin:
    """set_rollback_pin — delegation to orchestration."""

    def test_delegates_to_set_backup_snapshot_rollback_pin(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.set_backup_snapshot_rollback_pin.return_value = {
            "pinned": True,
        }

        from quickscale_core.dr_engine.adapter import set_rollback_pin

        result = set_rollback_pin(
            snapshot_id="snap-001",
            hours=48,
            reason="pre-deployment",
        )
        assert result == {"pinned": True}
        mock_orch.set_backup_snapshot_rollback_pin.assert_called_once_with(
            "snap-001",
            ttl_hours=48,
            reason="pre-deployment",
        )


class TestClearRollbackPin:
    """clear_rollback_pin — delegation to orchestration."""

    def test_delegates_to_clear_backup_snapshot_rollback_pin(
        self, _mock_orch_and_backups: tuple[MagicMock, MagicMock, MagicMock]
    ) -> None:
        mock_orch, _, _ = _mock_orch_and_backups
        mock_orch.clear_backup_snapshot_rollback_pin.return_value = {"cleared": True}

        result = clear_rollback_pin(snapshot_id="snap-001")
        assert result == {"cleared": True}
        mock_orch.clear_backup_snapshot_rollback_pin.assert_called_once_with("snap-001")
