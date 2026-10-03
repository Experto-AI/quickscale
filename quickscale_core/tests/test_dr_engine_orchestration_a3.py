"""Pure-mock A-II verification and rollback-pin coverage."""

from __future__ import annotations
import quickscale_core.dr_engine._report as _report
import quickscale_core.dr_engine.primitives as _primitives
import quickscale_core.dr_engine._state as _state
import quickscale_core.dr_engine._metadata as _metadata

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.dr_engine.primitives import BackupConfigurationError, BackupError


_ORCH = "quickscale_core.dr_engine.orchestration"
_NOW = datetime(2026, 6, 22, 12, 0, tzinfo=timezone.utc)


def _artifact(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "filename": "trusted.dump",
        "local_path": "/tmp/trusted.dump",
        "backup_format": "pg_dump_custom",
        "database_engine": "django.db.backends.postgresql",
        "checksum_sha256": "checksum",
        "size_bytes": 8,
        "remote_key": "",
        "status": "validated",
        "restore_started_at": None,
        "validated_at": None,
        "validation_notes": "",
        "restored_at": None,
        "is_export_only": lambda: False,
    }
    return SimpleNamespace(**(values | overrides))


def _snapshot(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "snapshot_id": "snap-b2",
        "status": "ready",
        "source_environment": "local",
        "authoritative_dump": _artifact(),
        "created_at": _NOW - timedelta(hours=1),
        "rollback_pin_expires_at": None,
        "rollback_pin_reason": "",
        "has_active_rollback_pin": lambda now=None: False,
    }
    return SimpleNamespace(**(values | overrides))


class TestVerificationAndPins:
    def test_record_verification_normalizes_inputs_loads_existing_reports_and_persists_in_order(
        self,
    ) -> None:
        snapshot = _snapshot(
            created_at=_NOW - timedelta(days=1),
            rollback_pin_expires_at=_NOW + timedelta(hours=2),
            rollback_pin_reason="window",
            has_active_rollback_pin=lambda now=None: True,
        )
        existing = {
            "status": "reserved",
            "reports": [{"route": "old"}],
            "notes": "keep me",
            "captured_at": "captured",
        }
        ordered = MagicMock()
        with (
            patch(
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=snapshot,
            ),
            patch(
                "quickscale_core.dr_engine._report._build_snapshot_full_backup_contract",
                return_value={"status": "complete"},
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._load_snapshot_sidecar_payload",
                return_value=existing,
            ),
            patch(
                "quickscale_core.dr_engine._metadata._get_project_slug",
                return_value="project",
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._persist_snapshot_sidecar_payload"
            ) as persist,
            patch(
                "quickscale_core.dr_engine._report.build_backup_snapshot_report",
                return_value={"status": "ready"},
            ) as report,
        ):
            ordered.attach_mock(persist, "persist")
            ordered.attach_mock(report, "report")
            result = _report.record_backup_snapshot_verification(
                "snap-b2",
                route=" route ",
                phase=" plan ",
                status=" ready ",
                payload={"check": True},
                now=_NOW,
            )
        assert result == {"status": "ready"}
        payload = persist.call_args.kwargs["payload"]
        assert payload["reports"][0] == {"route": "old"}
        assert payload["reports"][1]["route"] == "route"
        assert payload["reports"][1]["phase"] == "plan"
        assert payload["reports"][1]["recorded_at"] == _NOW.isoformat()
        persist.assert_called_once_with(
            snapshot,
            filename=_primitives._PROMOTION_VERIFICATION_FILENAME,
            kind="promotion_verification",
            payload=payload,
            policy=None,
            remote_uploader=None,
        )
        report.assert_called_once_with(
            snapshot,
            now=_NOW,
            sidecar_payloads=[_primitives._PROMOTION_VERIFICATION_FILENAME],
        )
        assert [item[0] for item in ordered.mock_calls] == ["persist", "report"]

    def test_record_verification_uses_empty_payload_when_sidecar_is_missing(
        self,
    ) -> None:
        snapshot = _snapshot()
        with (
            patch(
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=snapshot,
            ),
            patch(
                "quickscale_core.dr_engine._report._build_snapshot_full_backup_contract",
                return_value={},
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._load_snapshot_sidecar_payload",
                side_effect=BackupError("missing"),
            ),
            patch(
                "quickscale_core.dr_engine._metadata._get_project_slug",
                return_value="project",
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._persist_snapshot_sidecar_payload"
            ) as persist,
            patch(
                "quickscale_core.dr_engine._report.build_backup_snapshot_report",
                return_value={},
            ),
        ):
            _report.record_backup_snapshot_verification(
                "snap-b2",
                route="route",
                phase="execute",
                status="failed",
                payload={},
                now=_NOW,
            )
        assert persist.call_args.kwargs["payload"]["reports"]
        assert persist.call_args.kwargs["payload"]["notes"] == (
            "Reserved for route-specific plan and execute reports."
        )

    def test_record_verification_rejects_blank_inputs_before_snapshot_lookup(
        self,
    ) -> None:
        with patch(
            "quickscale_core.dr_engine._state.get_backup_snapshot"
        ) as get_snapshot:
            with pytest.raises(BackupConfigurationError, match="route"):
                _report.record_backup_snapshot_verification(
                    "snap-b2", route=" ", phase="plan", status="ready", payload={}
                )
        get_snapshot.assert_not_called()

    def test_validate_backup_artifact_updates_validated_state_and_notes(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "backup.json"
        path.write_text("{}")
        artifact = _artifact(
            local_path=str(path),
            backup_format="json",
            checksum_sha256=None,
            size_bytes=None,
        )
        with (
            patch("django.utils.timezone.now", return_value=_NOW),
            patch("quickscale_core.dr_engine.persistence.save_artifact") as save,
        ):
            assert _report.validate_backup_artifact(artifact) == []
        assert artifact.status == "validated"
        assert artifact.validation_notes == ""
        save.assert_called_once_with(
            artifact,
            update_fields=["validated_at", "validation_notes", "status", "updated_at"],
        )

    def test_validate_backup_artifact_marks_integrity_failure(
        self, tmp_path: Path
    ) -> None:
        path = tmp_path / "backup.json"
        path.write_text("not json")
        artifact = _artifact(
            local_path=str(path),
            backup_format="json",
            checksum_sha256=None,
            size_bytes=None,
        )
        with (
            patch("django.utils.timezone.now", return_value=_NOW),
            patch("quickscale_core.dr_engine.persistence.save_artifact"),
        ):
            issues = _report.validate_backup_artifact(artifact)
        assert issues == ["json backup payload is not valid JSON"]
        assert artifact.status == "failed"
        assert artifact.validation_notes == issues[0]

    @pytest.mark.parametrize(
        ("snapshot", "message"),
        [
            (_snapshot(status="deleted"), "already been deleted"),
            (_snapshot(authoritative_dump=None), "does not have an authoritative"),
        ],
    )
    def test_set_pin_rejects_deleted_or_dumpless_snapshot(
        self, snapshot: SimpleNamespace, message: str
    ) -> None:
        with patch(
            "quickscale_core.dr_engine._state.get_backup_snapshot",
            return_value=snapshot,
        ):
            with pytest.raises(BackupError, match=message):
                _report.set_backup_snapshot_rollback_pin(
                    "snap-b2", ttl_hours=2, reason="window"
                )

    def test_set_pin_computes_persists_and_reports_expiry(self) -> None:
        snapshot = _snapshot()
        with (
            patch(
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=snapshot,
            ),
            patch("quickscale_core.dr_engine.persistence.save_snapshot") as save,
            patch(
                "quickscale_core.dr_engine._report.build_backup_snapshot_report",
                return_value={"status": "ready"},
            ) as report,
        ):
            result = _report.set_backup_snapshot_rollback_pin(
                "snap-b2", ttl_hours=2, reason="  release window  ", now=_NOW
            )
        assert result == {"status": "ready"}
        assert snapshot.rollback_pin_expires_at == _NOW + timedelta(hours=2)
        assert snapshot.rollback_pin_reason == "release window"
        save.assert_called_once()
        assert save.call_args.kwargs["update_fields"] == [
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ]
        report.assert_called_once_with(snapshot, now=_NOW)

    def test_set_pin_invalid_ttl_is_rejected_without_persistence(self) -> None:
        snapshot = _snapshot()
        with (
            patch(
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=snapshot,
            ),
            patch("quickscale_core.dr_engine.persistence.save_snapshot") as save,
        ):
            with pytest.raises(BackupConfigurationError, match="ttl_hours"):
                _report.set_backup_snapshot_rollback_pin(
                    "snap-b2", ttl_hours=0, reason="window", now=_NOW
                )
        save.assert_not_called()

    def test_clear_pin_rejects_deleted_snapshot_and_clears_active_pin(self) -> None:
        deleted = _snapshot(status="deleted")
        with patch(
            "quickscale_core.dr_engine._state.get_backup_snapshot", return_value=deleted
        ):
            with pytest.raises(BackupError, match="already been deleted"):
                _report.clear_backup_snapshot_rollback_pin("snap-b2")

        snapshot = _snapshot(
            rollback_pin_expires_at=_NOW + timedelta(hours=2),
            rollback_pin_reason="window",
        )
        with (
            patch(
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=snapshot,
            ),
            patch("quickscale_core.dr_engine.persistence.save_snapshot") as save,
            patch(
                "quickscale_core.dr_engine._report.build_backup_snapshot_report",
                return_value={"status": "cleared"},
            ) as report,
        ):
            _report.clear_backup_snapshot_rollback_pin("snap-b2", now=_NOW)
        assert snapshot.rollback_pin_expires_at is None
        assert snapshot.rollback_pin_reason == ""
        save.assert_called_once()
        assert save.call_args.kwargs["update_fields"] == [
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ]
        report.assert_called_once_with(snapshot, now=_NOW)


class TestArtifactSnapshotMetadataHelpers:
    @pytest.mark.parametrize(
        ("existing_notes", "note"),
        [("", "failure"), ("existing", "")],
    )
    def test_clear_appended_note_ignores_blank_inputs_without_mutation(
        self, existing_notes: str, note: str
    ) -> None:
        artifact = _artifact(validation_notes=existing_notes)

        assert _state._clear_appended_artifact_note(artifact, note) is False
        assert artifact.validation_notes == existing_notes

    def test_clear_appended_note_removes_exact_note(self) -> None:
        artifact = _artifact(validation_notes="snapshot capture failed")

        assert (
            _state._clear_appended_artifact_note(
                artifact, "  snapshot capture failed  "
            )
            is True
        )
        assert artifact.validation_notes == ""

    def test_clear_appended_note_removes_only_trailing_appended_note(self) -> None:
        artifact = _artifact(validation_notes="keep this; snapshot capture failed")

        assert (
            _state._clear_appended_artifact_note(artifact, " snapshot capture failed ")
            is True
        )
        assert artifact.validation_notes == "keep this"

    def test_clear_appended_note_leaves_unrelated_notes_unchanged(self) -> None:
        artifact = _artifact(validation_notes="keep this; different failure")

        assert (
            _state._clear_appended_artifact_note(artifact, "snapshot capture failed")
            is False
        )
        assert artifact.validation_notes == "keep this; different failure"

    def test_persist_snapshot_metadata_preserves_metadata_and_appends_note(
        self,
    ) -> None:
        artifact = _artifact(
            metadata_json={"existing": "value"}, validation_notes="prior note"
        )
        snapshot = _snapshot(status="failed", remote_root_key="snapshots/snap-b2")
        with patch("quickscale_core.dr_engine.persistence.save_artifact") as save:
            _state._persist_snapshot_metadata_on_artifact(
                artifact, snapshot, note="sidecar capture failed"
            )

        assert artifact.metadata_json == {
            "existing": "value",
            "snapshot_id": "snap-b2",
            "snapshot_status": "failed",
            "snapshot_remote_root_key": "snapshots/snap-b2",
        }
        assert artifact.validation_notes == "prior note; sidecar capture failed"
        save.assert_called_once_with(
            artifact,
            update_fields=["metadata_json", "updated_at", "validation_notes"],
        )

    def test_persist_snapshot_metadata_without_remote_root_or_note(self) -> None:
        artifact = _artifact(
            metadata_json={"existing": "value"}, validation_notes="keep this"
        )
        snapshot = _snapshot(status="ready", remote_root_key="")
        with patch("quickscale_core.dr_engine.persistence.save_artifact") as save:
            _state._persist_snapshot_metadata_on_artifact(artifact, snapshot)

        assert artifact.metadata_json == {
            "existing": "value",
            "snapshot_id": "snap-b2",
            "snapshot_status": "ready",
        }
        assert artifact.validation_notes == "keep this"
        save.assert_called_once_with(
            artifact, update_fields=["metadata_json", "updated_at"]
        )


class TestReleaseIdentityHelpers:
    def test_get_project_slug_uses_nonempty_base_directory_name(self) -> None:
        base_dir = Path("/srv/example-project")
        with patch(
            "django.conf.settings",
            SimpleNamespace(BASE_DIR=base_dir, ROOT_URLCONF="fallback.urls"),
        ):
            assert _metadata._get_project_slug() == "example-project"

    def test_get_project_slug_falls_back_to_root_urlconf(self) -> None:
        with patch(
            "django.conf.settings",
            SimpleNamespace(BASE_DIR=Path("/"), ROOT_URLCONF="fallback.urls"),
        ):
            assert _metadata._get_project_slug() == "fallback"

    def test_get_git_revision_returns_stripped_sha_and_uses_base_directory(
        self,
    ) -> None:
        base_dir = Path("/srv/example-project")
        completed = SimpleNamespace(returncode=0, stdout="  abc123  \n")
        with (
            patch(
                "django.conf.settings",
                SimpleNamespace(BASE_DIR=base_dir),
            ),
            patch("subprocess.run", return_value=completed) as run,
        ):
            assert _metadata._get_git_revision() == "abc123"

        run.assert_called_once_with(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            cwd=base_dir,
        )

    @pytest.mark.parametrize(
        ("return_value", "side_effect"),
        [
            (SimpleNamespace(returncode=1, stdout="ignored"), None),
            (None, OSError("git unavailable")),
        ],
    )
    def test_get_git_revision_returns_none_for_command_failure(
        self, return_value: SimpleNamespace | None, side_effect: OSError | None
    ) -> None:
        base_dir = Path("/srv/example-project")
        with (
            patch(
                "django.conf.settings",
                SimpleNamespace(BASE_DIR=base_dir),
            ),
            patch(
                "subprocess.run",
                return_value=return_value,
                side_effect=side_effect,
            ) as run,
        ):
            assert _metadata._get_git_revision() is None

        run.assert_called_once_with(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            check=False,
            text=True,
            cwd=base_dir,
        )
