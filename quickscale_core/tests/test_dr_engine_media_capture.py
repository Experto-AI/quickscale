"""Tests for captured media sets in DR snapshots (SA322 (c))."""

from __future__ import annotations

import json
import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

from quickscale_core.dr_engine import _media
from quickscale_core.dr_engine._sidecar import _build_media_sync_manifest
from quickscale_core.dr_engine.primitives import BackupError, _compute_sha256


_FAKE_NOW = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)


def _compute_sha256_bytes(payload: bytes) -> str:
    import hashlib

    return hashlib.sha256(payload).hexdigest()


def _snapshot(root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        snapshot_id="snap-media",
        local_root_path=str(root),
        child_descriptors_json={},
    )


def _missing_storage_helpers() -> ModuleNotFoundError:
    error = ModuleNotFoundError("storage is not installed")
    error.name = "quickscale_modules_storage"
    return error


class TestNormalizeMediaRelativePath:
    def test_accepts_nested_relative_path(self) -> None:
        assert (
            _media._normalize_media_relative_path("blog/uploads/hero.png")
            == "blog/uploads/hero.png"
        )

    def test_strips_leading_slash_and_backslashes(self) -> None:
        assert (
            _media._normalize_media_relative_path("//blog\\uploads\\hero.png")
            == "blog/uploads/hero.png"
        )

    @pytest.mark.parametrize(
        "relative_path",
        ["", "   ", "../escape.png", "blog/../../escape.png"],
    )
    def test_refuses_empty_or_traversal_paths(self, relative_path: str) -> None:
        with pytest.raises(BackupError):
            _media._normalize_media_relative_path(relative_path)

    def test_leading_slash_stays_inside_the_snapshot_root(self) -> None:
        assert _media._normalize_media_relative_path("/absolute.png") == "absolute.png"


class TestCaptureMediaObjects:
    def test_copies_and_records_each_object(self, tmp_path: Path) -> None:
        source_root = tmp_path / "source-media"
        source_file = source_root / "blog" / "hero.png"
        source_file.parent.mkdir(parents=True)
        source_file.write_bytes(b"image-bytes")
        inventory = [
            {
                "relative_path": "blog/hero.png",
                "size_bytes": len(b"image-bytes"),
                "checksum_sha256": _compute_sha256(source_file),
            }
        ]

        capture, captured_inventory = _media._capture_media_objects(
            inventory=inventory,
            snapshot_root=tmp_path / "snapshot",
            source_runtime={
                "backend": "local",
                "use_s3_compatible": False,
                "media_root": source_root,
            },
        )

        captured_path = tmp_path / "snapshot" / "media" / "blog" / "hero.png"
        assert captured_path.read_bytes() == b"image-bytes"
        assert stat.S_IMODE(captured_path.stat().st_mode) == 0o600
        assert capture == {
            "status": "captured",
            "relative_root": "media",
            "file_count": 1,
            "total_bytes": len(b"image-bytes"),
        }
        assert captured_inventory[0]["snapshot_relative_path"] == (
            "media/blog/hero.png"
        )
        assert captured_inventory[0]["snapshot_checksum_sha256"] == (
            _compute_sha256(captured_path)
        )

    def test_empty_inventory_records_an_empty_capture(self, tmp_path: Path) -> None:
        capture, captured_inventory = _media._capture_media_objects(
            inventory=[],
            snapshot_root=tmp_path / "snapshot",
            source_runtime={
                "backend": "local",
                "use_s3_compatible": False,
                "media_root": tmp_path / "source",
            },
        )

        assert capture["status"] == "empty"
        assert captured_inventory == []
        assert (tmp_path / "snapshot" / "media").is_dir()

    def test_refuses_a_missing_source_object(self, tmp_path: Path) -> None:
        with pytest.raises(BackupError, match="could not read"):
            _media._capture_media_objects(
                inventory=[{"relative_path": "missing.png"}],
                snapshot_root=tmp_path / "snapshot",
                source_runtime={
                    "backend": "local",
                    "use_s3_compatible": False,
                    "media_root": tmp_path / "source",
                },
            )

    def test_refuses_changed_source_content(self, tmp_path: Path) -> None:
        source_root = tmp_path / "source-media"
        source_root.mkdir()
        (source_root / "hero.png").write_bytes(b"new-bytes")

        with pytest.raises(BackupError, match="changed content"):
            _media._capture_media_objects(
                inventory=[
                    {
                        "relative_path": "hero.png",
                        "checksum_sha256": "stale-checksum",
                    }
                ],
                snapshot_root=tmp_path / "snapshot",
                source_runtime={
                    "backend": "local",
                    "use_s3_compatible": False,
                    "media_root": source_root,
                },
            )

    def test_refuses_a_changed_source_size(self, tmp_path: Path) -> None:
        source_root = tmp_path / "source-media"
        source_root.mkdir()
        (source_root / "hero.png").write_bytes(b"new-bytes")

        with pytest.raises(BackupError, match="changed size"):
            _media._capture_media_objects(
                inventory=[{"relative_path": "hero.png", "size_bytes": 3}],
                snapshot_root=tmp_path / "snapshot",
                source_runtime={
                    "backend": "local",
                    "use_s3_compatible": False,
                    "media_root": source_root,
                },
            )

    def test_refuses_an_unsafe_inventory_path(self, tmp_path: Path) -> None:
        with pytest.raises(BackupError, match="not a safe relative path"):
            _media._capture_media_objects(
                inventory=[{"relative_path": "../escape.png"}],
                snapshot_root=tmp_path / "snapshot",
                source_runtime={
                    "backend": "local",
                    "use_s3_compatible": False,
                    "media_root": tmp_path / "source",
                },
            )


class TestBuildMediaSyncManifestCapture:
    def test_captures_local_media_and_records_the_manifest(
        self, tmp_path: Path
    ) -> None:
        media_root = tmp_path / "media"
        media_file = media_root / "blog" / "hero.png"
        media_file.parent.mkdir(parents=True)
        media_file.write_bytes(b"image-bytes")

        with (
            patch(
                "quickscale_core.dr_engine._metadata._get_project_slug",
                return_value="media-project",
            ),
            patch(
                "quickscale_core.dr_engine._metadata._get_source_environment",
                return_value="local",
            ),
            patch(
                "quickscale_core.dr_engine._metadata._load_storage_helpers",
                side_effect=_missing_storage_helpers(),
            ),
            patch(
                "quickscale_core.dr_engine._sidecar.settings",
                SimpleNamespace(MEDIA_ROOT=str(media_root)),
            ),
        ):
            manifest = _build_media_sync_manifest(
                captured_at=_FAKE_NOW,
                snapshot_root=tmp_path / "snapshot",
            )

        assert manifest["manifest_version"] == 2
        assert manifest["status"] == "ready"
        assert manifest["capture"]["status"] == "captured"
        assert manifest["inventory"][0]["relative_path"] == "blog/hero.png"
        assert manifest["inventory"][0]["snapshot_relative_path"] == (
            "media/blog/hero.png"
        )
        assert (tmp_path / "snapshot" / "media" / "blog" / "hero.png").exists()

    def test_missing_media_root_records_an_explicit_empty_capture(
        self, tmp_path: Path
    ) -> None:
        with (
            patch(
                "quickscale_core.dr_engine._metadata._get_project_slug",
                return_value="media-project",
            ),
            patch(
                "quickscale_core.dr_engine._metadata._get_source_environment",
                return_value="local",
            ),
            patch(
                "quickscale_core.dr_engine._metadata._load_storage_helpers",
                side_effect=_missing_storage_helpers(),
            ),
            patch(
                "quickscale_core.dr_engine._sidecar.settings",
                SimpleNamespace(MEDIA_ROOT=""),
            ),
        ):
            manifest = _build_media_sync_manifest(
                captured_at=_FAKE_NOW,
                snapshot_root=tmp_path / "snapshot",
            )

        assert manifest["status"] == "ready"
        assert manifest["source_status"] == "missing_media_root"
        assert manifest["capture"]["status"] == "empty"
        assert manifest["capture"]["reason"] == "missing_media_root"
        assert (tmp_path / "snapshot" / "media").is_dir()

    def test_invalid_media_source_fails_the_capture(self, tmp_path: Path) -> None:
        invalid_root = tmp_path / "not-a-directory"
        invalid_root.write_text("x", encoding="utf-8")

        with (
            patch(
                "quickscale_core.dr_engine._metadata._get_project_slug",
                return_value="media-project",
            ),
            patch(
                "quickscale_core.dr_engine._metadata._get_source_environment",
                return_value="local",
            ),
            patch(
                "quickscale_core.dr_engine._metadata._load_storage_helpers",
                side_effect=_missing_storage_helpers(),
            ),
            patch(
                "quickscale_core.dr_engine._sidecar.settings",
                SimpleNamespace(MEDIA_ROOT=str(invalid_root)),
            ),
        ):
            with pytest.raises(BackupError, match="media source is unavailable"):
                _build_media_sync_manifest(
                    captured_at=_FAKE_NOW,
                    snapshot_root=tmp_path / "snapshot",
                )


class TestCopyMediaItemPermissions:
    def test_preserves_an_existing_destination_mode(self, tmp_path: Path) -> None:
        source_root = tmp_path / "source"
        target_root = tmp_path / "target"
        source = source_root / "hero.png"
        target = target_root / "hero.png"
        source.parent.mkdir()
        target.parent.mkdir()
        source.write_bytes(b"image-bytes")
        target.write_bytes(b"old-bytes")
        source.chmod(0o644)
        target.chmod(0o640)

        copied = _media._copy_media_item(
            relative_path="hero.png",
            source_runtime={
                "backend": "local",
                "use_s3_compatible": False,
                "media_root": source_root,
            },
            target_runtime={
                "backend": "local",
                "use_s3_compatible": False,
                "media_root": target_root,
            },
        )

        assert copied is True
        assert target.read_bytes() == b"image-bytes"
        assert stat.S_IMODE(target.stat().st_mode) == 0o640

    def test_new_destination_gets_the_process_default_mode(
        self, tmp_path: Path
    ) -> None:
        source_root = tmp_path / "source"
        target_root = tmp_path / "target"
        source = source_root / "hero.png"
        source.parent.mkdir()
        source.write_bytes(b"image-bytes")
        source.chmod(0o600)

        copied = _media._copy_media_item(
            relative_path="hero.png",
            source_runtime={
                "backend": "local",
                "use_s3_compatible": False,
                "media_root": source_root,
            },
            target_runtime={
                "backend": "local",
                "use_s3_compatible": False,
                "media_root": target_root,
            },
        )

        assert copied is True
        current_umask = os.umask(0)
        os.umask(current_umask)
        assert stat.S_IMODE((target_root / "hero.png").stat().st_mode) == (
            0o666 & ~current_umask
        )


class TestSnapshotMediaCaptureIssues:
    def _write_manifest(
        self, snapshot: SimpleNamespace, payload: dict[str, object]
    ) -> None:
        root = Path(snapshot.local_root_path)
        root.mkdir(parents=True, exist_ok=True)
        (root / "media-sync-manifest.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def test_legacy_snapshot_reports_no_issue(self, tmp_path: Path) -> None:
        snapshot = _snapshot(tmp_path / "snapshot")
        self._write_manifest(
            snapshot,
            {
                "manifest_version": 1,
                "status": "ready",
                "inventory": [{"relative_path": "hero.png"}],
            },
        )

        assert (
            _media._collect_snapshot_media_capture_issues(
                snapshot,
                verify_checksums=True,
            )
            == []
        )

    def test_missing_captured_file_is_an_issue(self, tmp_path: Path) -> None:
        snapshot = _snapshot(tmp_path / "snapshot")
        self._write_manifest(
            snapshot,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                },
                "inventory": [{"relative_path": "hero.png"}],
            },
        )

        issues = _media._collect_snapshot_media_capture_issues(
            snapshot,
            verify_checksums=True,
        )

        assert issues == ["captured media file is missing: hero.png"]

    def test_changed_captured_checksum_is_an_issue(self, tmp_path: Path) -> None:
        snapshot = _snapshot(tmp_path / "snapshot")
        captured_file = Path(snapshot.local_root_path) / "media" / "hero.png"
        captured_file.parent.mkdir(parents=True)
        captured_file.write_bytes(b"image-bytes")
        self._write_manifest(
            snapshot,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                },
                "inventory": [
                    {
                        "relative_path": "hero.png",
                        "snapshot_checksum_sha256": "stale-checksum",
                    }
                ],
            },
        )

        issues = _media._collect_snapshot_media_capture_issues(
            snapshot,
            verify_checksums=True,
        )

        assert issues == ["captured media file changed content: hero.png"]

    def test_empty_capture_is_trusted(self, tmp_path: Path) -> None:
        snapshot = _snapshot(tmp_path / "snapshot")
        self._write_manifest(
            snapshot,
            {
                "manifest_version": 2,
                "status": "missing_media_root",
                "capture": {
                    "status": "empty",
                    "relative_root": "media",
                    "file_count": 0,
                },
                "inventory": [],
            },
        )

        assert (
            _media._collect_snapshot_media_capture_issues(
                snapshot,
                verify_checksums=True,
            )
            == []
        )


class TestResumeMediaIssue:
    def _write_manifest(self, root: Path, payload: dict[str, object]) -> None:
        root.mkdir(parents=True, exist_ok=True)
        (root / "media-sync-manifest.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )

    def _resume_snapshot(self, root: Path) -> SimpleNamespace:
        return SimpleNamespace(
            snapshot_id="snap-resume",
            status="failed",
            source_environment="local",
            remote_root_key="",
            local_root_path=str(root),
            authoritative_dump=None,
            child_descriptors_json={},
        )

    def test_damaged_captured_set_is_reported(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = self._resume_snapshot(tmp_path)
        self._write_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                },
                "inventory": [{"relative_path": "hero.png"}],
            },
        )

        issue = _capture._get_resume_media_issue(snapshot)

        assert issue is not None
        assert "captured media set is incomplete" in issue

    def test_version_two_manifest_without_capture_is_reported(
        self, tmp_path: Path
    ) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = self._resume_snapshot(tmp_path)
        self._write_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "inventory": [],
            },
        )

        issue = _capture._get_resume_media_issue(snapshot)

        assert issue == "its version 2 media manifest records no captured set"

    def test_version_one_manifest_remains_resumable(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = self._resume_snapshot(tmp_path)
        self._write_manifest(
            tmp_path,
            {
                "manifest_version": 1,
                "status": "ready",
                "inventory": [],
            },
        )

        assert _capture._get_resume_media_issue(snapshot) is None

    def test_empty_capture_remains_resumable(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = self._resume_snapshot(tmp_path)
        self._write_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "empty",
                    "relative_root": "media",
                    "file_count": 0,
                },
                "inventory": [],
            },
        )

        assert _capture._get_resume_media_issue(snapshot) is None

    def test_healthy_captured_set_remains_resumable(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = self._resume_snapshot(tmp_path)
        captured_file = tmp_path / "media" / "hero.png"
        captured_file.parent.mkdir()
        captured_file.write_bytes(b"image-bytes")
        self._write_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                },
                "inventory": [
                    {
                        "relative_path": "hero.png",
                        "snapshot_checksum_sha256": _compute_sha256(captured_file),
                        "snapshot_size_bytes": captured_file.stat().st_size,
                    }
                ],
            },
        )

        assert _capture._get_resume_media_issue(snapshot) is None

    def test_validate_resume_preconditions_refuses_a_damaged_capture(
        self, tmp_path: Path
    ) -> None:
        from quickscale_core.dr_engine import _capture as capture_module
        from quickscale_core.dr_engine.primitives import BackupPolicySnapshot

        snapshot = self._resume_snapshot(tmp_path)
        self._write_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                },
                "inventory": [{"relative_path": "hero.png"}],
            },
        )
        policy = BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode="local",
            local_directory=str(tmp_path / "backups"),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="ACCESS",
            remote_secret_access_key_env_var="SECRET",
            automation_enabled=False,
            schedule="",
        )

        with (
            patch(
                "quickscale_core.dr_engine._paths._build_snapshot_capture_resume_policy",
                return_value=policy,
            ),
            patch(
                "quickscale_core.dr_engine._policy._validate_policy_snapshot_internal",
                return_value=[],
            ),
            patch(
                "quickscale_core.dr_engine._metadata._get_source_environment",
                return_value="local",
            ),
        ):
            with pytest.raises(
                BackupError,
                match="captured media set is incomplete",
            ):
                capture_module._validate_resume_preconditions(snapshot, policy)


class TestResumePreservation:
    def _policy(self, tmp_path: Path) -> Any:
        from quickscale_core.dr_engine.primitives import BackupPolicySnapshot

        return BackupPolicySnapshot(
            retention_days=14,
            naming_prefix="db",
            target_mode="local",
            local_directory=str(tmp_path / "backups"),
            remote_bucket_name="",
            remote_prefix="backups/private",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="ACCESS",
            remote_secret_access_key_env_var="SECRET",
            automation_enabled=False,
            schedule="",
        )

    def _snapshot_with_manifest(
        self, tmp_path: Path, payload: dict[str, object]
    ) -> Any:
        snapshot_root = tmp_path / "snapshot"
        _media._primitives._ensure_private_directory(snapshot_root)
        (snapshot_root / "media-sync-manifest.json").write_text(
            json.dumps(payload),
            encoding="utf-8",
        )
        return SimpleNamespace(
            snapshot_id="snap-preserve",
            local_root_path=str(snapshot_root),
            remote_root_key="",
            child_descriptors_json={},
            authoritative_dump=None,
            status="failed",
        )

    def test_healthy_captured_media_is_not_recaptured(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine._sidecar import _capture_snapshot_sidecars

        snapshot = self._snapshot_with_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "captured_at": "2026-01-01T00:00:00+00:00",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                    "total_bytes": 11,
                },
                "inventory": [
                    {
                        "relative_path": "hero.png",
                        "snapshot_relative_path": "media/hero.png",
                        "snapshot_size_bytes": 11,
                    }
                ],
            },
        )
        captured_file = Path(snapshot.local_root_path) / "media" / "hero.png"
        captured_file.parent.mkdir()
        captured_file.write_bytes(b"image-bytes")

        with (
            patch(
                "quickscale_core.dr_engine._sidecar._build_media_sync_manifest",
                side_effect=AssertionError("media must not be recaptured"),
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._build_env_var_manifest",
                return_value={"status": "ready"},
            ),
            patch(
                "quickscale_core.dr_engine._metadata._build_release_metadata",
                return_value={"status": "ready"},
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._build_promotion_verification_placeholder",
                return_value={"status": "reserved"},
            ),
        ):
            descriptors, failures = _capture_snapshot_sidecars(
                snapshot=snapshot,
                policy=self._policy(tmp_path),
                captured_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
                remote_uploader=None,
            )

        assert failures == []
        preserved = json.loads(
            (Path(snapshot.local_root_path) / "media-sync-manifest.json").read_text(
                encoding="utf-8"
            )
        )
        assert preserved["captured_at"] == "2026-01-01T00:00:00+00:00"
        assert descriptors["media"]["metadata"]["capture_status"] == "captured"

    def test_empty_capture_is_not_recaptured(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine._sidecar import _capture_snapshot_sidecars

        snapshot = self._snapshot_with_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "captured_at": "2026-01-01T00:00:00+00:00",
                "capture": {
                    "status": "empty",
                    "relative_root": "media",
                    "file_count": 0,
                    "total_bytes": 0,
                },
                "inventory": [],
            },
        )

        with (
            patch(
                "quickscale_core.dr_engine._sidecar._build_media_sync_manifest",
                side_effect=AssertionError("media must not be recaptured"),
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._build_env_var_manifest",
                return_value={"status": "ready"},
            ),
            patch(
                "quickscale_core.dr_engine._metadata._build_release_metadata",
                return_value={"status": "ready"},
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._build_promotion_verification_placeholder",
                return_value={"status": "reserved"},
            ),
        ):
            descriptors, failures = _capture_snapshot_sidecars(
                snapshot=snapshot,
                policy=self._policy(tmp_path),
                captured_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
                remote_uploader=None,
            )

        assert failures == []
        assert descriptors["media"]["metadata"]["capture_status"] == "empty"

    def test_resume_refuses_a_missing_captured_manifest(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = SimpleNamespace(
            snapshot_id="snap-missing-manifest",
            local_root_path=str(tmp_path / "snapshot"),
            remote_root_key="",
            child_descriptors_json={
                "media": {
                    "status": "ready",
                    "metadata": {"capture_status": "captured"},
                }
            },
            authoritative_dump=None,
            status="failed",
        )

        issue = _capture._get_resume_media_issue(snapshot)

        assert issue == "its captured media manifest is missing"

    def test_upload_failure_still_records_the_completed_capture(
        self, tmp_path: Path
    ) -> None:
        from dataclasses import replace

        from quickscale_core.dr_engine import _capture
        from quickscale_core.dr_engine._sidecar import _capture_snapshot_sidecars

        snapshot = self._snapshot_with_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "captured_at": "2026-01-01T00:00:00+00:00",
                "capture": {
                    "status": "empty",
                    "relative_root": "media",
                    "file_count": 0,
                    "total_bytes": 0,
                },
                "inventory": [],
            },
        )
        snapshot.child_descriptors_json = {}
        policy = replace(
            self._policy(tmp_path),
            target_mode="private_remote",
            remote_bucket_name="bucket",
        )

        def failing_uploader(_local_path: Path, _policy: Any) -> str:
            raise BackupError("offline")

        with (
            patch(
                "quickscale_core.dr_engine._sidecar._build_env_var_manifest",
                return_value={"status": "ready"},
            ),
            patch(
                "quickscale_core.dr_engine._metadata._build_release_metadata",
                return_value={"status": "ready"},
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._build_promotion_verification_placeholder",
                return_value={"status": "reserved"},
            ),
        ):
            descriptors, failures = _capture_snapshot_sidecars(
                snapshot=snapshot,
                policy=policy,
                captured_at=datetime(2026, 6, 15, tzinfo=timezone.utc),
                remote_uploader=failing_uploader,
            )

        assert failures
        assert descriptors["media"]["metadata"]["capture_status"] == "empty"
        snapshot.child_descriptors_json = descriptors

        (Path(snapshot.local_root_path) / "media-sync-manifest.json").unlink()
        assert _capture._get_resume_media_issue(snapshot) == (
            "its recorded empty media manifest is missing"
        )

    def test_same_size_corruption_is_reported(self, tmp_path: Path) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = self._snapshot_with_manifest(
            tmp_path,
            {
                "manifest_version": 2,
                "status": "ready",
                "capture": {
                    "status": "captured",
                    "relative_root": "media",
                    "file_count": 1,
                },
                "inventory": [
                    {
                        "relative_path": "hero.png",
                        "snapshot_size_bytes": 3,
                        "snapshot_checksum_sha256": _compute_sha256_bytes(b"OLD"),
                    }
                ],
            },
        )
        captured_file = Path(snapshot.local_root_path) / "media" / "hero.png"
        captured_file.parent.mkdir()
        captured_file.write_bytes(b"BAD")

        issue = _capture._get_resume_media_issue(snapshot)

        assert issue is not None
        assert "changed content: hero.png" in issue

    def test_resume_refuses_a_missing_empty_capture_manifest(
        self, tmp_path: Path
    ) -> None:
        from quickscale_core.dr_engine import _capture

        snapshot = SimpleNamespace(
            snapshot_id="snap-missing-empty-manifest",
            local_root_path=str(tmp_path / "snapshot"),
            remote_root_key="",
            child_descriptors_json={
                "media": {
                    "status": "ready",
                    "metadata": {"capture_status": "empty"},
                }
            },
            authoritative_dump=None,
            status="failed",
        )

        issue = _capture._get_resume_media_issue(snapshot)

        assert issue == "its recorded empty media manifest is missing"
