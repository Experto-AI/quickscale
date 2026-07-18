"""Pure-mock orchestration coverage for the DR engine's A-I slice.

The module deliberately patches the persistence, Django, storage, and sidecar
seams.  It therefore exercises orchestration state transitions without Django
settings, a database, or a real storage backend.
"""

from __future__ import annotations

import json
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from quickscale_core.dr_engine import orchestration as orch
from quickscale_core.dr_engine.primitives import (
    BackupError,
    BackupPolicySnapshot,
)


_ORCH = "quickscale_core.dr_engine.orchestration"
_NOW = datetime(2026, 6, 15, 14, 30, tzinfo=timezone.utc)


def _policy(**overrides: object) -> BackupPolicySnapshot:
    values: dict[str, object] = {
        "retention_days": 30,
        "naming_prefix": "quickscale",
        "target_mode": "local",
        "local_directory": "/var/backups",
        "remote_bucket_name": "",
        "remote_prefix": "snapshots",
        "remote_endpoint_url": "",
        "remote_region_name": "",
        "remote_access_key_id_env_var": "ACCESS_KEY",
        "remote_secret_access_key_env_var": "SECRET_KEY",
        "automation_enabled": False,
        "schedule": "",
    }
    return BackupPolicySnapshot(**(values | overrides))  # type: ignore[arg-type]


def _artifact(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "pk": 17,
        "filename": "dump-001.json",
        "local_path": None,
        "remote_key": "",
        "remote_bucket_name": "",
        "remote_endpoint_url": "",
        "remote_region_name": "",
        "storage_target": "local",
        "status": "pending",
        "validation_notes": "",
        "metadata_json": {},
        "backup_format": "json",
        "database_engine": "sqlite",
        "database_name": "db.sqlite3",
        "checksum_sha256": "checksum",
        "size_bytes": 8,
        "created_at": _NOW,
        "deleted_at": None,
        "effective_restore_scope": lambda: "full",
        "restore_scope_label": lambda: "Full database",
    }
    return SimpleNamespace(**(values | overrides))


def _snapshot(**overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "snapshot_id": "snap-001",
        "status": "pending",
        "source_environment": "local",
        "local_root_path": "/var/backups/snapshots/snap-001",
        "remote_root_key": "",
        "child_descriptors_json": {"sidecars": {}},
        "authoritative_dump": None,
        "failure_note": "",
        "created_at": _NOW,
        "updated_at": _NOW,
        "rollback_pin_expires_at": None,
        "rollback_pin_reason": "",
        "has_active_rollback_pin": lambda now=None: False,
    }
    return SimpleNamespace(**(values | overrides))


def _db(engine: str = "django.db.backends.sqlite3") -> SimpleNamespace:
    return SimpleNamespace(
        connections={
            "default": SimpleNamespace(settings_dict={"ENGINE": engine, "NAME": "db"})
        }
    )


class TestMetadataOrchestration:
    def test_release_metadata_is_deterministic_and_provenanced(self) -> None:
        fake_settings = SimpleNamespace(QUICKSCALE_APP_VERSION="2.4.0")
        with (
            patch(f"{_ORCH}.settings", fake_settings),
            patch(f"{_ORCH}.django.get_version", return_value="5.2"),
            patch(f"{_ORCH}._get_project_slug", return_value="demo"),
            patch(f"{_ORCH}._get_source_environment", return_value="staging"),
            patch(
                f"{_ORCH}._collect_module_versions",
                return_value={"quickscale_modules_auth": "1.2"},
            ),
            patch(f"{_ORCH}._get_git_revision", return_value="abc123"),
        ):
            result = orch._build_release_metadata(captured_at=_NOW)

        assert result == {
            "manifest_version": 1,
            "captured_at": "2026-06-15T14:30:00+00:00",
            "project_slug": "demo",
            "source_environment": "staging",
            "status": "ready",
            "app_version": "2.4.0",
            "django_version": "5.2",
            "module_versions": {"quickscale_modules_auth": "1.2"},
            "git_sha": "abc123",
        }

    def test_backup_metadata_keeps_server_and_client_versions_separate(self) -> None:
        with (
            patch(f"{_ORCH}.django.get_version", return_value="5.2"),
            patch(f"{_ORCH}._collect_module_versions", return_value={}),
            patch(f"{_ORCH}._get_database_server_version", return_value="3.45"),
            patch(f"{_ORCH}.settings", SimpleNamespace(QUICKSCALE_APP_VERSION="dev")),
        ):
            result = orch._build_backup_metadata(
                created_at=_NOW,
                backup_format="json",
                database_engine="sqlite",
                database_name="db.sqlite3",
                target_mode="local",
                database_server_major=3,
                dump_client_version="unused",
                dump_client_major=18,
            )

        assert result["created_at"] == "2026-06-15T14:30:00+00:00"
        assert result["database_server_version"] == "3.45"
        assert result["database_server_major"] == 3
        assert result["pg_dump_version"] == "unused"
        assert result["dump_client_major"] == 18

    def test_json_dump_creation_returns_expected_artifact_metadata(
        self, tmp_path: Path
    ) -> None:
        policy = _policy()
        with (
            patch(f"{_ORCH}.build_backup_filename", return_value="backup.json"),
            patch(f"{_ORCH}._dump_database_as_json") as dump,
        ):
            result = orch._create_database_dump(
                "django.db.backends.sqlite3",
                policy,
                shell_runner=None,
                now=_NOW,
                database_directory=tmp_path,
            )

        assert result == (
            tmp_path / "backup.json",
            "json",
            "backup.json",
            None,
            None,
            None,
            None,
        )
        dump.assert_called_once_with(tmp_path / "backup.json")

    @pytest.mark.parametrize(
        ("overrides", "message"),
        [
            ({"retention_days": 0}, "retention_days"),
            ({"target_mode": "remote"}, "target_mode"),
            ({"local_directory": ""}, "local_directory"),
        ],
    )
    def test_invalid_policy_is_rejected_before_capture(
        self, overrides: dict[str, object], message: str
    ) -> None:
        issues = orch._validate_policy_snapshot_internal(_policy(**overrides))
        assert any(message in issue for issue in issues)


class TestCaptureResumeOrchestration:
    def test_create_backup_success_persists_snapshot_before_completion(
        self, tmp_path: Path
    ) -> None:
        snapshot = _snapshot(status="pending", local_root_path=str(tmp_path / "snap"))
        artifact = _artifact(
            local_path=str(tmp_path / "snap" / "database" / "dump.json")
        )
        dump_path = Path(artifact.local_path)
        dump_path.parent.mkdir(parents=True)
        dump_path.write_text("{}")
        dump_result = (dump_path, "json", artifact.filename, None, None, None, None)
        ordered = MagicMock()
        with (
            patch(f"{_ORCH}._validate_policy_snapshot_internal", return_value=[]),
            patch(f"{_ORCH}.get_local_backup_directory", return_value=tmp_path),
            patch(f"{_ORCH}._backup_creation_lock", return_value=nullcontext()),
            patch(f"{_ORCH}.django.db", _db()),
            patch(f"{_ORCH}._mint_snapshot_id", return_value="snap-001"),
            patch(
                f"{_ORCH}._build_snapshot_local_root", return_value=tmp_path / "snap"
            ),
            patch(f"{_ORCH}._create_database_dump", return_value=dump_result),
            patch(f"{_ORCH}._compute_sha256", return_value="checksum"),
            patch(f"{_ORCH}._build_backup_metadata", return_value={}),
            patch(f"{_ORCH}.create_snapshot", return_value=snapshot),
            patch(f"{_ORCH}.create_artifact", return_value=artifact),
            patch(
                f"{_ORCH}._build_snapshot_database_descriptor",
                return_value={"status": "ready"},
            ),
            patch(f"{_ORCH}.save_snapshot") as save_snapshot,
            patch(
                f"{_ORCH}._complete_capture_after_dump", return_value=artifact
            ) as complete,
        ):
            ordered.attach_mock(save_snapshot, "save_snapshot")
            ordered.attach_mock(complete, "complete")
            result = orch.create_backup(policy=_policy(), now=_NOW)

        assert result is artifact
        assert snapshot.authoritative_dump is artifact
        assert snapshot.child_descriptors_json == {
            "database": {"status": "ready"},
            "sidecars": {},
        }
        save_snapshot.assert_called_once_with(
            snapshot,
            update_fields=[
                "authoritative_dump",
                "child_descriptors_json",
                "updated_at",
            ],
        )
        complete.assert_called_once()
        assert complete.call_args.kwargs["now"] == _NOW
        assert [item[0] for item in ordered.mock_calls] == ["save_snapshot", "complete"]

    def test_create_backup_dump_failure_cleans_snapshot_root_and_marks_state(
        self, tmp_path: Path
    ) -> None:
        snapshot = _snapshot(local_root_path=str(tmp_path / "snap"))
        root = tmp_path / "snap"
        root.mkdir()
        with (
            patch(f"{_ORCH}._validate_policy_snapshot_internal", return_value=[]),
            patch(f"{_ORCH}.get_local_backup_directory", return_value=tmp_path),
            patch(f"{_ORCH}._backup_creation_lock", return_value=nullcontext()),
            patch(f"{_ORCH}.django.db", _db()),
            patch(f"{_ORCH}._mint_snapshot_id", return_value="snap-001"),
            patch(f"{_ORCH}._build_snapshot_local_root", return_value=root),
            patch(f"{_ORCH}.create_snapshot", return_value=snapshot),
            patch(f"{_ORCH}._create_database_dump", side_effect=OSError("dump failed")),
            patch(f"{_ORCH}.save_snapshot") as save_snapshot,
        ):
            with pytest.raises(BackupError, match="dump failed"):
                orch.create_backup(policy=_policy(), now=_NOW)

        assert not root.exists()
        assert snapshot.status == "failed"
        assert "snapshot preparation failed" in snapshot.failure_note
        save_snapshot.assert_called_once()

    def test_resume_success_reuses_valid_dump_and_clears_failure_state(
        self, tmp_path: Path
    ) -> None:
        dump = tmp_path / "snap" / "database" / "dump.json"
        dump.parent.mkdir(parents=True)
        dump.write_text("{}")
        artifact = _artifact(
            local_path=str(dump),
            status="failed",
            checksum_sha256="checksum",
            size_bytes=2,
        )
        snapshot = _snapshot(
            status="failed",
            local_root_path=str(tmp_path / "snap"),
            authoritative_dump=artifact,
            failure_note="old failure",
            child_descriptors_json={"database": {"status": "failed"}, "sidecars": {}},
        )
        with (
            patch(f"{_ORCH}.get_backup_snapshot", return_value=snapshot),
            patch(
                f"{_ORCH}._build_snapshot_capture_resume_policy", return_value=_policy()
            ),
            patch(f"{_ORCH}._validate_policy_snapshot_internal", return_value=[]),
            patch(f"{_ORCH}._build_snapshot_lock_directory", return_value=tmp_path),
            patch(f"{_ORCH}._backup_creation_lock", return_value=nullcontext()),
            patch(f"{_ORCH}._get_source_environment", return_value="local"),
            patch(f"{_ORCH}.refresh_snapshot"),
            patch(f"{_ORCH}.django.db", _db()),
            patch(f"{_ORCH}._compute_sha256", return_value="checksum"),
            patch(f"{_ORCH}._collect_local_backup_validation_issues", return_value=[]),
            patch(
                f"{_ORCH}._build_snapshot_database_descriptor",
                return_value={"status": "ready"},
            ),
            patch(f"{_ORCH}.save_artifact") as save_artifact,
            patch(f"{_ORCH}.save_snapshot") as save_snapshot,
            patch(
                f"{_ORCH}._complete_capture_after_dump", return_value=artifact
            ) as complete,
        ):
            result = orch.create_backup(
                policy=_policy(), now=_NOW, resume_snapshot_id="snap-001"
            )

        assert result is artifact
        assert artifact.status == "ready"
        save_artifact.assert_called_once_with(
            artifact, update_fields=["status", "updated_at"]
        )
        assert save_snapshot.call_args_list[0] == call(
            snapshot,
            update_fields=[
                "authoritative_dump",
                "child_descriptors_json",
                "updated_at",
            ],
        )
        complete.assert_called_once()

    @pytest.mark.parametrize(
        ("snapshot_status", "message"),
        [("deleted", "already been deleted"), ("ready", "already complete")],
    )
    def test_resume_rejects_terminal_snapshots_without_lock_or_dump(
        self, snapshot_status: str, message: str
    ) -> None:
        snapshot = _snapshot(
            status=snapshot_status, authoritative_dump=_artifact(status="ready")
        )
        with (
            patch(f"{_ORCH}.get_backup_snapshot", return_value=snapshot),
            patch(
                f"{_ORCH}._build_snapshot_capture_resume_policy", return_value=_policy()
            ),
            patch(f"{_ORCH}._validate_policy_snapshot_internal", return_value=[]),
            patch(
                f"{_ORCH}._snapshot_capture_is_complete",
                side_effect=lambda item: item.status == "ready",
            ),
            patch(f"{_ORCH}._get_source_environment", return_value="local"),
            patch(f"{_ORCH}._backup_creation_lock") as lock,
        ):
            with pytest.raises(BackupError, match=message):
                orch.create_backup(
                    policy=_policy(), resume_snapshot_id="snap-001", now=_NOW
                )

        lock.assert_not_called()

    def test_private_remote_upload_failure_marks_both_records_and_skips_sidecars(
        self, tmp_path: Path
    ) -> None:
        artifact = _artifact(local_path=str(tmp_path / "dump.json"))
        snapshot = _snapshot(
            remote_root_key="snapshots/snap-001", authoritative_dump=artifact
        )
        descriptors = {
            "database": {"relative_path": "database/dump.json"},
            "sidecars": {},
        }
        sidecars = MagicMock()
        with (
            patch(
                f"{_ORCH}._upload_snapshot_child_to_private_remote",
                side_effect=BackupError("offline"),
            ),
            patch(f"{_ORCH}._mark_remote_upload_failure") as mark_artifact,
            patch(f"{_ORCH}._mark_snapshot_failed") as mark_snapshot,
            patch(f"{_ORCH}._capture_snapshot_sidecars", sidecars),
            patch(f"{_ORCH}.prune_expired_backups") as prune,
        ):
            with pytest.raises(BackupError, match="offline"):
                orch._complete_capture_after_dump(
                    artifact,
                    snapshot,
                    resolved_policy=_policy(target_mode="private_remote"),
                    local_path=tmp_path / "dump.json",
                    remote_uploader=MagicMock(),
                    remote_deleter=None,
                    child_descriptors_json=descriptors,
                    previous_failure_note="",
                    now=_NOW,
                )

        assert descriptors["database"]["status"] == "failed"
        assert descriptors["database"]["error"] == "offline"
        mark_artifact.assert_called_once()
        mark_snapshot.assert_called_once()
        sidecars.assert_not_called()
        prune.assert_not_called()


class TestReportsAndProvenance:
    def _complete_snapshot(self, root: Path) -> SimpleNamespace:
        artifact_path = root / "database" / "dump.json"
        artifact_path.parent.mkdir(parents=True)
        artifact_path.write_text("payload")
        artifact = _artifact(
            local_path=str(artifact_path),
            status="ready",
            checksum_sha256="checksum",
            size_bytes=7,
        )
        sidecars: dict[str, dict[str, object]] = {}
        payloads: dict[str, dict[str, object]] = {
            "media-sync-manifest.json": {
                "status": "ready",
                "project_slug": "demo",
                "source_environment": "local",
                "captured_at": "t",
            },
            "env-var-manifest.json": {
                "status": "ready",
                "project_slug": "demo",
                "source_environment": "local",
                "captured_at": "t",
            },
            "release-metadata.json": {
                "status": "ready",
                "project_slug": "demo",
                "source_environment": "local",
                "captured_at": "t",
                "app_version": "1",
                "django_version": "5",
                "module_versions": {},
                "git_sha": "sha",
            },
            "promotion-verification.json": {
                "status": "reserved",
                "project_slug": "demo",
                "source_environment": "local",
                "captured_at": "t",
            },
        }
        for filename, payload in payloads.items():
            (root / filename).write_text(json.dumps(payload))
            sidecars[filename] = {
                "kind": "sidecar",
                "status": "ready",
                "local_path": str(root / filename),
                "metadata": {"manifest_status": payload["status"]},
            }
        return _snapshot(
            status="ready",
            local_root_path=str(root),
            authoritative_dump=artifact,
            child_descriptors_json={
                "database": {"status": "ready", "relative_path": "database/dump.json"},
                "sidecars": sidecars,
            },
        )

    def test_full_contract_reports_complete_and_consistent_provenance(
        self, tmp_path: Path
    ) -> None:
        snapshot = self._complete_snapshot(tmp_path)
        contract = orch._build_snapshot_full_backup_contract(snapshot, now=_NOW)

        assert contract["status"] == "complete"
        assert contract["completeness"]["status"] == "complete"
        assert contract["provenance"]["status"] == "consistent"
        assert contract["provenance"]["project_slug"] == "demo"
        assert contract["provenance"]["source_environment"] == "local"
        assert contract["provenance"]["release"]["git_sha"] == "sha"

        (tmp_path / "env-var-manifest.json").write_text(
            json.dumps(
                {
                    "status": "ready",
                    "project_slug": "other",
                    "source_environment": "local",
                }
            )
        )
        changed = orch._build_snapshot_full_backup_contract(snapshot, now=_NOW)
        assert changed["provenance"]["status"] == "inconsistent"
        assert any(
            "project_slug is inconsistent" in issue
            for issue in changed["provenance"]["issues"]
        )

    def test_report_contains_children_requested_payloads_and_load_errors(
        self, tmp_path: Path
    ) -> None:
        artifact = _artifact(local_path=str(tmp_path / "dump.json"), status="ready")
        snapshot = _snapshot(
            status="ready",
            local_root_path=str(tmp_path),
            authoritative_dump=artifact,
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "env.json": {
                        "kind": "env",
                        "status": "ready",
                        "metadata": {"manifest_status": "ready"},
                    }
                },
            },
        )
        with (
            patch(
                f"{_ORCH}._build_snapshot_full_backup_contract",
                return_value={"status": "complete"},
            ),
            patch(
                f"{_ORCH}._load_snapshot_sidecar_payload",
                side_effect=[{"name": "ok"}, BackupError("bad json")],
            ) as load,
        ):
            report = orch.build_backup_snapshot_report(
                snapshot,
                now=_NOW,
                sidecar_payloads=("env.json", "env.json", "bad.json"),
            )

        assert report["status"] == "ready"
        assert report["full_backup"] == {"status": "complete"}
        assert report["sidecar_payloads"] == {"env.json": {"name": "ok"}}
        assert report["sidecar_payload_errors"] == {"bad.json": "bad json"}
        assert load.call_count == 2

    def test_report_wrapper_resolves_snapshot_and_preserves_call_contract(self) -> None:
        snapshot = _snapshot()
        with (
            patch(
                f"{_ORCH}.get_backup_snapshot", return_value=snapshot
            ) as get_snapshot,
            patch(
                f"{_ORCH}.build_backup_snapshot_report",
                return_value={"snapshot_id": "snap-001"},
            ) as builder,
        ):
            result = orch.report_backup_snapshot(
                "snap-001", now=_NOW, sidecar_payloads=("env.json",)
            )

        assert result == {"snapshot_id": "snap-001"}
        get_snapshot.assert_called_once_with("snap-001")
        builder.assert_called_once_with(
            snapshot, now=_NOW, sidecar_payloads=("env.json",)
        )


class TestPruneAndDelete:
    def test_delete_linked_snapshot_removes_files_remote_keys_and_marks_children(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "snap"
        root.mkdir()
        dump = root / "database.dump"
        dump.write_text("dump")
        artifact = _artifact(local_path=str(dump), remote_key="z-key")
        snapshot = _snapshot(
            local_root_path=str(root),
            authoritative_dump=artifact,
            child_descriptors_json={
                "database": {"remote_key": "b-key", "status": "ready"},
                "sidecars": {"env": {"remote_key": "a-key", "status": "ready"}},
            },
        )
        deleter = MagicMock()
        with (
            patch(
                f"{_ORCH}._get_authoritative_snapshot_for_artifact",
                return_value=snapshot,
            ),
            patch(f"{_ORCH}.save_snapshot") as save_snapshot,
        ):
            orch.delete_artifact_files(
                artifact, policy=_policy(), remote_deleter=deleter
            )

        assert not root.exists()
        assert not dump.exists()
        assert [item.args[0] for item in deleter.call_args_list] == [
            "a-key",
            "b-key",
            "z-key",
        ]
        assert snapshot.status == "deleted"
        assert snapshot.child_descriptors_json["database"]["status"] == "deleted"
        assert snapshot.child_descriptors_json["sidecars"]["env"]["status"] == "deleted"
        save_snapshot.assert_called_once()

    def test_delete_unlinked_artifact_removes_local_and_remote_files(
        self, tmp_path: Path
    ) -> None:
        local_path = tmp_path / "orphan.dump"
        local_path.write_text("dump")
        artifact = _artifact(local_path=str(local_path), remote_key="orphan-key")
        deleter = MagicMock()
        with patch(
            f"{_ORCH}._get_authoritative_snapshot_for_artifact", return_value=None
        ):
            orch.delete_artifact_files(
                artifact, policy=_policy(), remote_deleter=deleter
            )

        assert not local_path.exists()
        deleter.assert_called_once_with("orphan-key", _policy())

    def test_prune_skips_pinned_snapshot_then_deletes_snapshot_and_orphan_in_order(
        self,
    ) -> None:
        pinned = _snapshot(
            snapshot_id="pinned", has_active_rollback_pin=lambda now=None: True
        )
        expired = _snapshot(
            snapshot_id="expired", has_active_rollback_pin=lambda now=None: False
        )
        expired.authoritative_dump = _artifact(deleted_at=None)
        orphan = _artifact(deleted_at=None)
        events: list[str] = []
        with (
            patch(
                f"{_ORCH}.iter_expired_snapshots", return_value=iter([pinned, expired])
            ),
            patch(
                f"{_ORCH}.iter_expired_unlinked_artifacts", return_value=iter([orphan])
            ),
            patch(
                f"{_ORCH}._delete_snapshot_storage",
                side_effect=lambda *_args, **_kwargs: events.append("snapshot"),
            ),
            patch(
                f"{_ORCH}.delete_artifact_files",
                side_effect=lambda *_args, **_kwargs: events.append("orphan"),
            ),
            patch(
                f"{_ORCH}.save_snapshot",
                side_effect=lambda *_args, **_kwargs: events.append("save-snapshot"),
            ),
            patch(
                f"{_ORCH}.save_artifact",
                side_effect=lambda *_args, **_kwargs: events.append("save-artifact"),
            ),
            patch(f"{_ORCH}.django_timezone.now", return_value=_NOW),
        ):
            count = orch.prune_expired_backups(policy=_policy(), now=_NOW)

        assert count == 2
        assert events == [
            "snapshot",
            "save-snapshot",
            "save-artifact",
            "orphan",
            "save-artifact",
        ]
        assert pinned.status == "pending"
        assert expired.status == "deleted"
        assert orphan.status == "deleted"
        assert expired.authoritative_dump.status == "deleted"

    def test_prune_uses_retention_cutoff_and_does_not_delete_pinned_remote(
        self,
    ) -> None:
        pinned = _snapshot(has_active_rollback_pin=lambda now=None: True)
        with (
            patch(
                f"{_ORCH}.iter_expired_snapshots", return_value=iter([pinned])
            ) as snapshots,
            patch(f"{_ORCH}.iter_expired_unlinked_artifacts", return_value=iter([])),
            patch(f"{_ORCH}.django_timezone.now", return_value=_NOW),
        ):
            assert (
                orch.prune_expired_backups(policy=_policy(retention_days=9), now=_NOW)
                == 0
            )

        snapshots.assert_called_once_with(_NOW - timedelta(days=9))
