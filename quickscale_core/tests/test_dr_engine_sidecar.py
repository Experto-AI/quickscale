"""Tests for quickscale_core.dr_engine._sidecar — sidecar building and lifecycle."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from quickscale_core.dr_engine.primitives import BackupError
from quickscale_core.dr_engine._sidecar import (
    _build_env_var_manifest,
    _build_media_sync_manifest,
    _build_promotion_verification_placeholder,
    _capture_snapshot_sidecars,
    _load_snapshot_sidecar_payload,
    _persist_snapshot_sidecar_payload,
    _upload_to_private_remote,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAKE_NOW = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)

# Patch target prefixes
# Module-level imports in _sidecar.py — patch the _sidecar namespace directly.
_SIDE = "quickscale_core.dr_engine._sidecar"
# Lazy imports inside _sidecar functions — patch the orchestration module.
_ORCH = "quickscale_core.dr_engine.orchestration"
# Primitives (module-level import in _sidecar)
_PRIMS = "quickscale_core.dr_engine.primitives"


def _make_snapshot(**attrs: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "local_root_path": str(Path("/tmp/snapshots/snap123")),
        "remote_root_key": "",
        "child_descriptors_json": None,
        "authoritative_dump": None,
        "status": "ready",
    }
    merged = {**defaults, **attrs}
    return SimpleNamespace(**merged)


def _make_artifact(**attrs: object) -> SimpleNamespace:
    defaults: dict[str, object] = {
        "local_path": None,
        "filename": "dump.dump",
        "remote_key": "",
        "size_bytes": 0,
        "checksum_sha256": "",
        "backup_format": "pg_dump_custom",
        "status": "ready",
        "storage_target": "local",
    }
    merged = {**defaults, **attrs}
    return SimpleNamespace(**merged)


# ---------------------------------------------------------------------------
# _build_env_var_manifest
# ---------------------------------------------------------------------------


class TestBuildEnvVarManifest:
    def test_basic_structure(self) -> None:
        """Returns a manifest with version, captured_at, status, and env var names."""
        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="staging",
            ),
            patch.dict(os.environ, {"PATH": "/usr/bin", "HOME": "/root"}, clear=True),
        ):
            manifest = _build_env_var_manifest(captured_at=_FAKE_NOW)

        assert manifest["manifest_version"] == 1
        assert manifest["project_slug"] == "myproj"
        assert manifest["source_environment"] == "staging"
        assert manifest["status"] == "ready"
        assert manifest["count"] == 2
        assert manifest["names"] == ["HOME", "PATH"]
        assert "captured_at" in manifest

    def test_empty_environment(self) -> None:
        """No env vars returns count 0 with empty list."""
        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="test",
            ),
            patch.dict(os.environ, {}, clear=True),
        ):
            manifest = _build_env_var_manifest(captured_at=_FAKE_NOW)

        assert manifest["count"] == 0
        assert manifest["names"] == []


# ---------------------------------------------------------------------------
# _build_promotion_verification_placeholder
# ---------------------------------------------------------------------------


class TestBuildPromotionVerificationPlaceholder:
    def test_basic_structure(self) -> None:
        """Placeholder has reserved status, empty reports, and rollback_pin."""
        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="production",
            ),
        ):
            placeholder = _build_promotion_verification_placeholder(
                captured_at=_FAKE_NOW
            )

        assert placeholder["manifest_version"] == 1
        assert placeholder["project_slug"] == "myproj"
        assert placeholder["source_environment"] == "production"
        assert placeholder["status"] == "reserved"
        assert placeholder["reports"] == []
        assert placeholder["rollback_pin"] == {"expires_at": None, "reason": ""}
        assert "notes" in placeholder


# ---------------------------------------------------------------------------
# _load_snapshot_sidecar_payload
# ---------------------------------------------------------------------------


class TestLoadSnapshotSidecarPayload:
    def test_loads_valid_json(self, tmp_path: Path) -> None:
        """Loads a valid JSON sidecar payload."""
        sidecar_path = tmp_path / "manifest.json"
        payload = {"key": "value", "count": 42}
        sidecar_path.write_text(json.dumps(payload))
        snapshot = _make_snapshot(local_root_path=str(tmp_path))
        result = _load_snapshot_sidecar_payload(snapshot, "manifest.json")
        assert result == payload

    def test_file_not_found_raises(self, tmp_path: Path) -> None:
        """Missing sidecar file raises BackupError."""
        snapshot = _make_snapshot(local_root_path=str(tmp_path))
        with pytest.raises(BackupError, match="Snapshot sidecar not found"):
            _load_snapshot_sidecar_payload(snapshot, "nonexistent.json")

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        """Malformed JSON raises BackupError."""
        sidecar_path = tmp_path / "bad.json"
        sidecar_path.write_text("{invalid json}")
        snapshot = _make_snapshot(local_root_path=str(tmp_path))
        with pytest.raises(BackupError, match="not valid JSON"):
            _load_snapshot_sidecar_payload(snapshot, "bad.json")

    def test_not_a_dict_raises(self, tmp_path: Path) -> None:
        """A JSON array is not a valid sidecar payload."""
        sidecar_path = tmp_path / "array.json"
        sidecar_path.write_text("[1, 2, 3]")
        snapshot = _make_snapshot(local_root_path=str(tmp_path))
        with pytest.raises(BackupError, match="must contain a JSON object"):
            _load_snapshot_sidecar_payload(snapshot, "array.json")


# ---------------------------------------------------------------------------
# _build_media_sync_manifest — local storage path
# ---------------------------------------------------------------------------


class TestBuildMediaSyncManifest:
    def test_local_storage_fallback(self, tmp_path: Path) -> None:
        """When _load_storage_helpers raises ModuleNotFoundError for storage module,
        falls back to local storage with media_root inventory."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()
        (media_dir / "file1.txt").write_text("hello")
        (media_dir / "sub").mkdir()
        (media_dir / "sub" / "file2.txt").write_text("world")

        class FakeSettings:
            MEDIA_ROOT = str(media_dir)

        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="staging",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=ModuleNotFoundError(
                    "No module named 'quickscale_modules_storage'",
                    name="quickscale_modules_storage",
                ),
            ),
            patch(f"{_SIDE}.settings", FakeSettings()),
            patch(
                f"{_SIDE}._compute_sha256",
                return_value="fake-sha",
            ),
        ):
            manifest = _build_media_sync_manifest(captured_at=_FAKE_NOW)

        assert manifest["status"] == "ready"
        assert manifest["storage"]["backend"] == "local"
        assert manifest["storage"]["media_root"] == str(media_dir)
        assert len(manifest["inventory"]) == 2
        paths = {item["relative_path"] for item in manifest["inventory"]}
        assert paths == {"file1.txt", "sub/file2.txt"}

    def test_missing_media_root_fallback(self) -> None:
        """When MEDIA_ROOT is empty string, returns missing_media_root status."""

        class FakeSettings:
            MEDIA_ROOT = ""

        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="staging",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=ModuleNotFoundError(
                    "No module named 'quickscale_modules_storage'",
                    name="quickscale_modules_storage",
                ),
            ),
            patch(f"{_SIDE}.settings", FakeSettings()),
        ):
            manifest = _build_media_sync_manifest(captured_at=_FAKE_NOW)

        assert manifest["status"] == "missing_media_root"
        assert manifest["inventory"] == []

    def test_media_root_does_not_exist(self, tmp_path: Path) -> None:
        """When MEDIA_ROOT path does not exist, returns missing_local_root."""

        class FakeSettings:
            MEDIA_ROOT = str(tmp_path / "nonexistent")

        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="staging",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=ModuleNotFoundError(
                    "No module named 'quickscale_modules_storage'",
                    name="quickscale_modules_storage",
                ),
            ),
            patch(f"{_SIDE}.settings", FakeSettings()),
        ):
            manifest = _build_media_sync_manifest(captured_at=_FAKE_NOW)

        assert manifest["status"] == "missing_local_root"
        assert manifest["inventory"] == []

    def test_media_root_not_a_directory(self, tmp_path: Path) -> None:
        """When MEDIA_ROOT is a file, returns invalid_local_root."""
        media_file = tmp_path / "not_a_dir.txt"
        media_file.write_text("data")

        class FakeSettings:
            MEDIA_ROOT = str(media_file)

        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="staging",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=ModuleNotFoundError(
                    "No module named 'quickscale_modules_storage'",
                    name="quickscale_modules_storage",
                ),
            ),
            patch(f"{_SIDE}.settings", FakeSettings()),
        ):
            manifest = _build_media_sync_manifest(captured_at=_FAKE_NOW)

        assert manifest["status"] == "invalid_local_root"
        assert manifest["inventory"] == []

    def test_local_storage_with_empty_media(self, tmp_path: Path) -> None:
        """Empty media directory returns ready status with empty inventory."""
        media_dir = tmp_path / "media"
        media_dir.mkdir()

        class FakeSettings:
            MEDIA_ROOT = str(media_dir)

        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="staging",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=ModuleNotFoundError(
                    "No module named 'quickscale_modules_storage'",
                    name="quickscale_modules_storage",
                ),
            ),
            patch(f"{_SIDE}.settings", FakeSettings()),
        ):
            manifest = _build_media_sync_manifest(captured_at=_FAKE_NOW)

        assert manifest["status"] == "ready"
        assert manifest["storage"]["backend"] == "local"
        assert manifest["inventory"] == []


# ---------------------------------------------------------------------------
# _persist_snapshot_sidecar_payload — basic success
# ---------------------------------------------------------------------------


class TestPersistSnapshotSidecarPayload:
    def test_persist_basic_success(self, tmp_path: Path) -> None:
        """Writes payload, builds descriptor, saves snapshot, returns descriptor."""
        snapshot = _make_snapshot(local_root_path=str(tmp_path))
        payload = {"status": "ready", "data": "test"}

        # _load_active_policy_snapshot is a lazy import (inside function body)
        # save_snapshot is a module-level import in _sidecar.py
        with (
            patch(f"{_ORCH}._load_active_policy_snapshot") as mock_load,
            patch(
                f"{_SIDE}.save_snapshot",
            ) as mock_save,
        ):
            mock_load.return_value = SimpleNamespace(target_mode="local")
            descriptor = _persist_snapshot_sidecar_payload(
                snapshot,
                filename="test-manifest.json",
                kind="test_kind",
                payload=payload,
            )

        # Verify the sidecar file was written
        sidecar_path = tmp_path / "test-manifest.json"
        assert sidecar_path.exists()
        written = json.loads(sidecar_path.read_text())
        assert written == payload

        # Verify descriptor was built and saved
        assert descriptor["kind"] == "test_kind"
        assert descriptor["status"] == "ready"
        assert descriptor["relative_path"] == "test-manifest.json"
        assert "size_bytes" in descriptor
        assert "checksum_sha256" in descriptor
        assert descriptor["metadata"]["manifest_status"] == "ready"

        # Verify snapshot was saved
        mock_save.assert_called_once()
        assert snapshot.child_descriptors_json is not None
        assert "test-manifest.json" in snapshot.child_descriptors_json["sidecars"]

    def test_persist_with_existing_sidecars(self, tmp_path: Path) -> None:
        """Appends new sidecar descriptor to existing sidecars dict."""
        snapshot = _make_snapshot(
            local_root_path=str(tmp_path),
            child_descriptors_json={
                "sidecars": {"existing.json": {"status": "ready"}},
            },
        )
        payload = {"status": "ready"}

        with (
            patch(f"{_ORCH}._load_active_policy_snapshot") as mock_load,
            patch(
                f"{_SIDE}.save_snapshot",
            ),
        ):
            mock_load.return_value = SimpleNamespace(target_mode="local")
            _persist_snapshot_sidecar_payload(
                snapshot,
                filename="new.json",
                kind="new",
                payload=payload,
            )

        assert "existing.json" in snapshot.child_descriptors_json["sidecars"]
        assert "new.json" in snapshot.child_descriptors_json["sidecars"]

    def test_persist_preserves_existing_remote_key(self, tmp_path: Path) -> None:
        """Existing sidecar remote_key is preserved in the new descriptor."""
        snapshot = _make_snapshot(
            local_root_path=str(tmp_path),
            child_descriptors_json={
                "sidecars": {
                    "re-upload.json": {
                        "status": "ready",
                        "remote_key": "s3://existing-key",
                    },
                },
            },
        )
        payload = {"status": "ready"}

        with (
            patch(f"{_ORCH}._load_active_policy_snapshot") as mock_load,
            patch(
                f"{_SIDE}.save_snapshot",
            ),
        ):
            mock_load.return_value = SimpleNamespace(target_mode="local")
            descriptor = _persist_snapshot_sidecar_payload(
                snapshot,
                filename="re-upload.json",
                kind="sidecar",
                payload=payload,
            )

        assert descriptor["remote_key"] == "s3://existing-key"

    def test_persist_with_remote_upload(self, tmp_path: Path) -> None:
        """When snapshot has remote_root_key and policy is private_remote,
        upload is attempted and remote_key is recorded."""
        snapshot = _make_snapshot(
            local_root_path=str(tmp_path),
            remote_root_key="snapshots/snap1",
        )
        payload = {"status": "ready"}

        with (
            patch(f"{_ORCH}._load_active_policy_snapshot") as mock_load,
            patch(
                f"{_SIDE}.save_snapshot",
            ),
            patch(
                f"{_ORCH}._upload_snapshot_child_to_private_remote",
                return_value="s3://new-remote-key",
            ),
        ):
            mock_load.return_value = SimpleNamespace(target_mode="private_remote")
            descriptor = _persist_snapshot_sidecar_payload(
                snapshot,
                filename="remote.json",
                kind="sidecar",
                payload=payload,
                policy=SimpleNamespace(target_mode="private_remote"),
            )

        assert descriptor["remote_key"] == "s3://new-remote-key"
        assert descriptor["status"] == "ready"

    def test_persist_upload_backup_error(self, tmp_path: Path) -> None:
        """BackupError during upload sets descriptor status to 'failed' and re-raises."""
        snapshot = _make_snapshot(
            local_root_path=str(tmp_path),
            remote_root_key="snapshots/snap1",
        )
        payload = {"status": "ready"}

        with (
            patch(f"{_ORCH}._load_active_policy_snapshot") as mock_load,
            patch(
                f"{_SIDE}.save_snapshot",
            ),
            patch(
                f"{_ORCH}._upload_snapshot_child_to_private_remote",
                side_effect=BackupError("upload failed"),
            ),
        ):
            mock_load.return_value = SimpleNamespace(target_mode="private_remote")
            with pytest.raises(BackupError, match="upload failed"):
                _persist_snapshot_sidecar_payload(
                    snapshot,
                    filename="fail.json",
                    kind="sidecar",
                    payload=payload,
                    policy=SimpleNamespace(target_mode="private_remote"),
                )

        # Descriptor should be written with failed status before re-raise
        assert snapshot.child_descriptors_json is not None
        desc = snapshot.child_descriptors_json["sidecars"]["fail.json"]
        assert desc["status"] == "failed"
        assert "upload failed" in desc["error"]

    def test_persist_upload_generic_exception(self, tmp_path: Path) -> None:
        """Non-BackupError exception during upload wraps in BackupError."""
        snapshot = _make_snapshot(
            local_root_path=str(tmp_path),
            remote_root_key="snapshots/snap1",
        )
        payload = {"status": "ready"}

        with (
            patch(f"{_ORCH}._load_active_policy_snapshot") as mock_load,
            patch(
                f"{_SIDE}.save_snapshot",
            ),
            patch(
                f"{_ORCH}._upload_snapshot_child_to_private_remote",
                side_effect=ValueError("unexpected"),
            ),
        ):
            mock_load.return_value = SimpleNamespace(target_mode="private_remote")
            with pytest.raises(BackupError, match="Private remote upload failed"):
                _persist_snapshot_sidecar_payload(
                    snapshot,
                    filename="gen-exc.json",
                    kind="sidecar",
                    payload=payload,
                    policy=SimpleNamespace(target_mode="private_remote"),
                )

        # Descriptor should be marked failed before re-raise
        desc = snapshot.child_descriptors_json["sidecars"]["gen-exc.json"]
        assert desc["status"] == "failed"


# ---------------------------------------------------------------------------
# _capture_snapshot_sidecars — basic coverage
# ---------------------------------------------------------------------------


class TestCaptureSnapshotSidecars:
    def test_basic_capture_success(self, tmp_path: Path) -> None:
        """Captures all four sidecars successfully with local target_mode."""
        snapshot_root = tmp_path / "snap_root"
        snapshot_root.mkdir(parents=True)

        snapshot = _make_snapshot(local_root_path=str(snapshot_root))
        policy = SimpleNamespace(target_mode="local")

        class FakeSettings:
            MEDIA_ROOT = ""

        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="test",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=ModuleNotFoundError(
                    "No module named 'quickscale_modules_storage'",
                    name="quickscale_modules_storage",
                ),
            ),
            patch(f"{_SIDE}.settings", FakeSettings()),
            patch(
                f"{_ORCH}._build_release_metadata",
                return_value={"manifest_version": 1, "status": "ready"},
            ),
            patch(f"{_SIDE}._compute_sha256", return_value="abc"),
        ):
            descriptors, failures = _capture_snapshot_sidecars(
                snapshot=snapshot,
                policy=policy,
                captured_at=_FAKE_NOW,
                remote_uploader=None,
            )

        assert failures == []
        assert "sidecars" in descriptors
        sidecar_keys = set(descriptors["sidecars"].keys())
        expected_keys = {
            "media-sync-manifest.json",
            "env-var-manifest.json",
            "release-metadata.json",
            "promotion-verification.json",
        }
        assert sidecar_keys == expected_keys

        # Verify each sidecar file was actually written to disk
        for key in expected_keys:
            assert (snapshot_root / key).exists(), f"Missing sidecar: {key}"


# ---------------------------------------------------------------------------
# _build_media_sync_manifest — storage helper exception
# ---------------------------------------------------------------------------


class TestBuildMediaSyncManifestExceptions:
    def test_generic_exception_from_storage_helpers(self) -> None:
        """A generic Exception (non-ModuleNotFound) returns unsupported status."""
        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="staging",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=Exception("unexpected error"),
            ),
            patch(f"{_SIDE}.settings", type("Fake", (), {})()),
        ):
            manifest = _build_media_sync_manifest(captured_at=_FAKE_NOW)

        assert manifest["status"] == "unsupported"
        assert "unexpected error" in manifest["reason"]


class TestCaptureSnapshotSidecarsPrivateRemote:
    def test_private_remote_upload_failure(self, tmp_path: Path) -> None:
        """When target_mode is private_remote and upload fails, the failure is
        recorded and the descriptor status is set to 'failed'."""
        snapshot_root = tmp_path / "snap_root"
        snapshot_root.mkdir(parents=True)

        snapshot = _make_snapshot(
            local_root_path=str(snapshot_root),
            remote_root_key="snapshots/snap1",
        )
        policy = SimpleNamespace(target_mode="private_remote")

        with (
            patch(f"{_ORCH}._get_project_slug", return_value="myproj"),
            patch(
                f"{_ORCH}._get_source_environment",
                return_value="test",
            ),
            patch(
                f"{_ORCH}._load_storage_helpers",
                side_effect=ModuleNotFoundError(
                    "No module named 'quickscale_modules_storage'",
                    name="quickscale_modules_storage",
                ),
            ),
            patch(f"{_SIDE}.settings", type("FakeSettings", (), {"MEDIA_ROOT": ""})()),
            patch(
                f"{_ORCH}._build_release_metadata",
                return_value={"manifest_version": 1, "status": "ready"},
            ),
            patch(f"{_SIDE}._compute_sha256", return_value="abc"),
            patch(
                f"{_ORCH}._upload_snapshot_child_to_private_remote",
                side_effect=BackupError("upload failed"),
            ),
        ):
            descriptors, failures = _capture_snapshot_sidecars(
                snapshot=snapshot,
                policy=policy,
                captured_at=_FAKE_NOW,
                remote_uploader=None,
            )

        assert len(failures) > 0
        assert any("upload failed" in f for f in failures)
        sidecars = descriptors["sidecars"]
        for name, desc in sidecars.items():
            if desc["status"] == "failed":
                assert "upload failed" in desc.get("error", "")


# ---------------------------------------------------------------------------
# _upload_to_private_remote — delegation path
# ---------------------------------------------------------------------------


class TestUploadToPrivateRemote:
    def test_delegates_to_core_upload(self, tmp_path: Path) -> None:
        """_upload_to_private_remote delegates to orchestration._upload_to_private_remote."""
        local_path = tmp_path / "test.txt"
        local_path.write_text("data")
        policy = SimpleNamespace(target_mode="private_remote")

        with patch(
            f"{_ORCH}._upload_to_private_remote",
            return_value="s3://bucket/key",
        ):
            result = _upload_to_private_remote(local_path, policy)

        assert result == "s3://bucket/key"
