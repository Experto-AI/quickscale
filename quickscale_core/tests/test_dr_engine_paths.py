"""Tests for quickscale_core.dr_engine._paths — snapshot path helpers."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from quickscale_core.dr_engine._paths import (
    _build_snapshot_capture_resume_policy,
    _build_snapshot_database_descriptor,
    _build_snapshot_local_root,
    _build_snapshot_lock_directory,
    _build_snapshot_remote_root,
    _get_snapshot_report_children,
    _replace_policy_remote_prefix,
    _snapshot_capture_is_complete,
    _snapshot_sidecar_path,
    _snapshot_uses_private_remote,
    build_backup_filename,
    get_local_backup_directory,
)
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_SAMPLE_POLICY_KWARGS: dict[str, object] = {
    "retention_days": 30,
    "naming_prefix": "myapp-db",
    "target_mode": "local",
    "local_directory": "/var/backups",
    "remote_bucket_name": "",
    "remote_prefix": "myapp/snapshots",
    "remote_endpoint_url": "",
    "remote_region_name": "",
    "remote_access_key_id_env_var": "",
    "remote_secret_access_key_env_var": "",
    "automation_enabled": True,
    "schedule": "0 3 * * *",
}


def _make_policy(**overrides: object) -> BackupPolicySnapshot:
    return BackupPolicySnapshot(**_SAMPLE_POLICY_KWARGS | overrides)  # type: ignore[arg-type]


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
# build_backup_filename
# ---------------------------------------------------------------------------


class TestBuildBackupFilename:
    _SLUG_PATCH = "quickscale_core.dr_engine.orchestration._get_project_slug"

    def test_basic_format(self) -> None:
        """Produces a deterministic filename with naming-prefix, slug, env, timestamp."""
        policy = _make_policy()
        fixed_now = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        with patch(self._SLUG_PATCH, return_value="myproj"):
            name = build_backup_filename(policy, now=fixed_now)
        # Format: {prefix}-{slug}-{env}-{timestamp}.{suffix}
        assert "myproj" in name
        assert "20260615" in name
        assert name.endswith(".json")

    def test_custom_suffix(self) -> None:
        """Custom suffix overrides default 'json'."""
        policy = _make_policy()
        fixed_now = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        with patch(self._SLUG_PATCH, return_value="myproj"):
            name = build_backup_filename(policy, now=fixed_now, suffix="sql.gz")
        assert name.endswith(".sql.gz")

    def test_environment_from_env_var(self) -> None:
        """QUICKSCALE_ENVIRONMENT env var is reflected in the filename."""
        policy = _make_policy()
        fixed_now = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        env_patch = patch.dict(os.environ, {"QUICKSCALE_ENVIRONMENT": "staging"})
        slug_patch = patch(self._SLUG_PATCH, return_value="myproj")
        with env_patch, slug_patch:
            name = build_backup_filename(policy, now=fixed_now)
        assert "-staging-" in name

    def test_environment_fallback_to_local(self) -> None:
        """When QUICKSCALE_ENVIRONMENT is unset, fallback to 'local'."""
        policy = _make_policy()
        fixed_now = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        env_patch = patch.dict(os.environ, {}, clear=True)
        slug_patch = patch(self._SLUG_PATCH, return_value="myproj")
        with env_patch, slug_patch:
            name = build_backup_filename(policy, now=fixed_now)
        assert "-local-" in name

    def test_naming_prefix_stripped(self) -> None:
        """Whitespace around naming_prefix is stripped."""
        policy = _make_policy(naming_prefix="  myapp-prefix  ")
        fixed_now = datetime(2026, 6, 15, 14, 30, 0, tzinfo=timezone.utc)
        with patch(self._SLUG_PATCH, return_value="proj"):
            name = build_backup_filename(policy, now=fixed_now)
        assert name.startswith("myapp-prefix-")


# ---------------------------------------------------------------------------
# get_local_backup_directory
# ---------------------------------------------------------------------------


class TestGetLocalBackupDirectory:
    def test_absolute_directory(self) -> None:
        """An absolute path in policy is returned as-is."""
        policy = _make_policy(local_directory="/custom/backups")
        result = get_local_backup_directory(policy)
        assert result == Path("/custom/backups")

    def test_relative_directory_with_settings(self) -> None:
        """A relative path is resolved against settings.BASE_DIR."""
        policy = _make_policy(local_directory="backups/db")
        mock_settings = SimpleNamespace(BASE_DIR="/project")
        with patch("django.conf.settings", mock_settings):
            result = get_local_backup_directory(policy)
        assert result == Path("/project/backups/db")

    def test_relative_directory_no_settings(self) -> None:
        """Without settings.BASE_DIR, relative path falls back to cwd."""
        policy = _make_policy(local_directory="backups/db")
        # A settings object without BASE_DIR attribute
        mock_settings = SimpleNamespace()
        with patch("django.conf.settings", mock_settings):
            result = get_local_backup_directory(policy)
        expected = Path.cwd() / "backups/db"
        assert result == expected


# ---------------------------------------------------------------------------
# _build_snapshot_local_root
# ---------------------------------------------------------------------------


class TestBuildSnapshotLocalRoot:
    def test_builds_root_path(self) -> None:
        policy = _make_policy(local_directory="/data/backups")
        result = _build_snapshot_local_root(policy, "snap-001")
        assert result == Path("/data/backups/snapshots/snap-001")


# ---------------------------------------------------------------------------
# _build_snapshot_remote_root
# ---------------------------------------------------------------------------


class TestBuildSnapshotRemoteRoot:
    def test_with_remote_prefix(self) -> None:
        policy = _make_policy(remote_prefix="  myapp/snapshots  ")
        result = _build_snapshot_remote_root(policy, "snap-001")
        assert result == "myapp/snapshots/snapshots/snap-001"

    def test_without_remote_prefix(self) -> None:
        policy = _make_policy(remote_prefix="")
        result = _build_snapshot_remote_root(policy, "snap-002")
        assert result == "snapshots/snap-002"


# ---------------------------------------------------------------------------
# _replace_policy_remote_prefix
# ---------------------------------------------------------------------------


class TestReplacePolicyRemotePrefix:
    def test_returns_new_policy_with_updated_prefix(self) -> None:
        policy = _make_policy(remote_prefix="old/prefix")
        updated = _replace_policy_remote_prefix(policy, "new/prefix")
        assert updated.remote_prefix == "new/prefix"
        # Original should be unchanged
        assert policy.remote_prefix == "old/prefix"


# ---------------------------------------------------------------------------
# _snapshot_sidecar_path
# ---------------------------------------------------------------------------


class TestSnapshotSidecarPath:
    def test_resolves_sidecar_path(self) -> None:
        snapshot = _make_snapshot(local_root_path="/snap_root/snap1")
        result = _snapshot_sidecar_path(snapshot, "env-var-manifest.json")
        assert result == Path("/snap_root/snap1/env-var-manifest.json")


# ---------------------------------------------------------------------------
# _build_snapshot_database_descriptor
# ---------------------------------------------------------------------------


class TestBuildSnapshotDatabaseDescriptor:
    def test_with_local_path(self) -> None:
        snapshot = _make_snapshot(local_root_path="/snaps/s1")
        artifact = _make_artifact(
            local_path="/snaps/s1/database/dump.dump",
            filename="dump.dump",
            remote_key="r/key",
            size_bytes=2048,
            checksum_sha256="abc",
            backup_format="pg_dump_custom",
        )
        desc = _build_snapshot_database_descriptor(snapshot, artifact)
        assert desc["kind"] == "database_dump"
        assert desc["status"] == "ready"
        assert desc["relative_path"] == "database/dump.dump"
        assert desc["local_path"] == "/snaps/s1/database/dump.dump"
        assert desc["remote_key"] == "r/key"
        assert desc["size_bytes"] == 2048
        assert desc["checksum_sha256"] == "abc"
        assert desc["metadata"]["backup_format"] == "pg_dump_custom"

    def test_without_local_path(self) -> None:
        """When artifact.local_path is None, relative_path uses default segment."""
        snapshot = _make_snapshot(local_root_path="/snaps/s1")
        artifact = _make_artifact(
            local_path=None,
            filename="dump.dump",
        )
        desc = _build_snapshot_database_descriptor(snapshot, artifact)
        assert desc["relative_path"] == "database/dump.dump"
        assert desc["local_path"] == ""

    def test_value_error_fallback(self) -> None:
        """When _relative_snapshot_child_path raises ValueError, fallback used."""
        snapshot = _make_snapshot(local_root_path="/snaps/s1")
        artifact = _make_artifact(
            local_path="/outside/test.dump",
            filename="test.dump",
        )
        desc = _build_snapshot_database_descriptor(snapshot, artifact)
        # The artifact path is outside the snapshot root, so relative_to raises
        # ValueError. The fallback uses the default database/ segment.
        assert desc["relative_path"] == "database/test.dump"


# ---------------------------------------------------------------------------
# _get_snapshot_report_children
# ---------------------------------------------------------------------------


class TestGetSnapshotReportChildren:
    def test_all_children_present_and_correct_types(self) -> None:
        snapshot = _make_snapshot(
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {"manifest.json": {"status": "ready"}},
            }
        )
        children, db_desc, sidecars = _get_snapshot_report_children(snapshot)
        assert children["database"]["status"] == "ready"
        assert db_desc["status"] == "ready"
        assert sidecars["manifest.json"]["status"] == "ready"

    def test_non_dict_child_descriptors(self) -> None:
        """When child_descriptors_json is not a dict, returns empty dicts."""
        snapshot = _make_snapshot(child_descriptors_json=None)
        children, db_desc, sidecars = _get_snapshot_report_children(snapshot)
        assert children == {}
        assert db_desc == {}
        assert sidecars == {}

    def test_missing_database_key(self) -> None:
        """Missing 'database' key returns empty dict for db_desc."""
        snapshot = _make_snapshot(child_descriptors_json={"sidecars": {}})
        children, db_desc, sidecars = _get_snapshot_report_children(snapshot)
        assert "database" not in children
        assert db_desc == {}

    def test_non_dict_sidecars(self) -> None:
        """When sidecars value is not a dict, returns empty dict."""
        snapshot = _make_snapshot(
            child_descriptors_json={"database": {}, "sidecars": "not-a-dict"}
        )
        children, db_desc, sidecars = _get_snapshot_report_children(snapshot)
        assert sidecars == {}


# ---------------------------------------------------------------------------
# _build_snapshot_capture_resume_policy
# ---------------------------------------------------------------------------


class TestBuildSnapshotCaptureResumePolicy:
    def test_local_target_mode(self) -> None:
        """When snapshot does not use private remote, target_mode stays 'local'."""
        snapshot = _make_snapshot(remote_root_key="", authoritative_dump=None)
        policy = _make_policy(target_mode="local")
        result = _build_snapshot_capture_resume_policy(snapshot, policy)
        assert result.target_mode == "local"

    def test_private_remote_with_no_artifact(self) -> None:
        """Private remote but no authoritative_dump returns resolved policy."""
        snapshot = _make_snapshot(
            remote_root_key="some/root",
            authoritative_dump=None,
        )
        policy = _make_policy(target_mode="private_remote")
        result = _build_snapshot_capture_resume_policy(snapshot, policy)
        assert result.target_mode == "private_remote"

    def test_private_remote_with_artifact(self) -> None:
        """Private remote with artifact calls _resolve_artifact_remote_policy."""
        snapshot = _make_snapshot(
            remote_root_key="some/root",
            authoritative_dump=_make_artifact(storage_target="private_remote"),
        )
        policy = _make_policy(target_mode="private_remote")

        expected_policy = _make_policy(
            target_mode="private_remote", remote_bucket_name="resolved"
        )
        with patch(
            "quickscale_core.dr_engine.orchestration._resolve_artifact_remote_policy",
            return_value=expected_policy,
        ):
            result = _build_snapshot_capture_resume_policy(snapshot, policy)
        assert result.remote_bucket_name == "resolved"


# ---------------------------------------------------------------------------
# _snapshot_uses_private_remote
# ---------------------------------------------------------------------------


class TestSnapshotUsesPrivateRemote:
    def test_remote_root_key_set(self) -> None:
        """Non-empty remote_root_key returns True."""
        snapshot = _make_snapshot(remote_root_key="some/root")
        assert _snapshot_uses_private_remote(snapshot) is True

    def test_remote_root_key_empty_no_artifact(self) -> None:
        """Empty remote_root_key and no artifact returns False."""
        snapshot = _make_snapshot(remote_root_key="", authoritative_dump=None)
        assert _snapshot_uses_private_remote(snapshot) is False

    def test_remote_root_key_empty_with_private_remote_artifact(self) -> None:
        """Empty remote_root_key but artifact with private_remote target returns True."""
        snapshot = _make_snapshot(
            remote_root_key="",
            authoritative_dump=_make_artifact(storage_target="private_remote"),
        )
        assert _snapshot_uses_private_remote(snapshot) is True

    def test_artifact_local_storage_returns_false(self) -> None:
        """Empty remote_root_key and local storage artifact returns False."""
        snapshot = _make_snapshot(
            remote_root_key="",
            authoritative_dump=_make_artifact(storage_target="local"),
        )
        assert _snapshot_uses_private_remote(snapshot) is False


# ---------------------------------------------------------------------------
# _build_snapshot_lock_directory
# ---------------------------------------------------------------------------


class TestBuildSnapshotLockDirectory:
    def test_parent_is_snapshots_directory(self) -> None:
        """When snapshot_root parent name is 'snapshots', go up two levels."""
        snapshot = _make_snapshot(local_root_path="/data/backups/snapshots/snap1")
        result = _build_snapshot_lock_directory(snapshot)
        assert result == Path("/data/backups")

    def test_parent_is_not_snapshots_directory(self) -> None:
        """When parent name is not 'snapshots', go up one level."""
        snapshot = _make_snapshot(local_root_path="/data/storage/snap1")
        result = _build_snapshot_lock_directory(snapshot)
        assert result == Path("/data/storage")


# ---------------------------------------------------------------------------
# _snapshot_capture_is_complete
# ---------------------------------------------------------------------------


class TestSnapshotCaptureIsComplete:
    def test_status_not_ready_returns_false(self) -> None:
        """Snapshot with status != 'ready' returns False."""
        snapshot = _make_snapshot(status="failed")
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_no_authoritative_dump_returns_false(self) -> None:
        """Snapshot without authoritative_dump returns False."""
        snapshot = _make_snapshot(status="ready", authoritative_dump=None)
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_artifact_deleted_returns_false(self) -> None:
        """Artifact with status 'deleted' returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(status="deleted"),
        )
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_no_child_descriptors_returns_false(self) -> None:
        """Missing child_descriptors_json dict returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(local_path=None, remote_key="rk"),
            child_descriptors_json=None,
        )
        # With no child_descriptors_json, database_descriptor check fails
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_database_descriptor_not_ready_returns_false(self) -> None:
        """Database descriptor without 'ready' status returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(local_path=None, remote_key="rk"),
            child_descriptors_json={
                "database": {"status": "pending"},
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_no_local_and_no_remote_returns_false(self) -> None:
        """No local dump file and no remote_key returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(
                local_path="/nonexistent/dump.dump", remote_key=""
            ),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "media-sync-manifest.json": {"status": "ready"},
                    "env-var-manifest.json": {"status": "ready"},
                    "release-metadata.json": {"status": "ready"},
                    "promotion-verification.json": {"status": "ready"},
                },
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_sidecars_not_a_dict_returns_false(self) -> None:
        """Sidecars value that is not a dict returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(remote_key="rk"),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": "not-a-dict",
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_missing_required_sidecar_returns_false(self) -> None:
        """A required sidecar filename missing from the dict returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(remote_key="rk"),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "media-sync-manifest.json": {"status": "ready"},
                    # Missing env-var-manifest.json
                },
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_sidecar_not_a_dict_returns_false(self) -> None:
        """A sidecar descriptor that is not a dict returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(remote_key="rk"),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "media-sync-manifest.json": "string-not-dict",
                    "env-var-manifest.json": {"status": "ready"},
                    "release-metadata.json": {"status": "ready"},
                    "promotion-verification.json": {"status": "ready"},
                },
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_sidecar_status_not_ready_returns_false(self) -> None:
        """A sidecar with status != 'ready' returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(remote_key="rk"),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "media-sync-manifest.json": {"status": "failed"},
                    "env-var-manifest.json": {"status": "ready"},
                    "release-metadata.json": {"status": "ready"},
                    "promotion-verification.json": {"status": "ready"},
                },
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_sidecar_no_local_and_no_remote_returns_false(self) -> None:
        """A sidecar with no local_path and no remote_key returns False."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(remote_key="rk"),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "media-sync-manifest.json": {
                        "status": "ready",
                        "local_path": "",
                    },
                    "env-var-manifest.json": {"status": "ready"},
                    "release-metadata.json": {"status": "ready"},
                    "promotion-verification.json": {"status": "ready"},
                },
            },
        )
        # local_path is empty and no remote_key → returns False
        assert _snapshot_capture_is_complete(snapshot) is False

    def test_complete_with_local_path(self, tmp_path: Path) -> None:
        """All conditions met with local dump file returns True."""
        dump_path = tmp_path / "database" / "dump.dump"
        dump_path.parent.mkdir(parents=True)
        dump_path.write_text("dump data")

        manifest_path = tmp_path / "media-sync-manifest.json"
        manifest_path.write_text("{}")

        snapshot = _make_snapshot(
            local_root_path=str(tmp_path),
            status="ready",
            authoritative_dump=_make_artifact(
                local_path=str(dump_path),
                remote_key="",
            ),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "media-sync-manifest.json": {
                        "status": "ready",
                        "local_path": str(manifest_path),
                    },
                    "env-var-manifest.json": {
                        "status": "ready",
                        "local_path": str(manifest_path),
                    },
                    "release-metadata.json": {
                        "status": "ready",
                        "local_path": str(manifest_path),
                    },
                    "promotion-verification.json": {
                        "status": "ready",
                        "local_path": str(manifest_path),
                    },
                },
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is True

    def test_complete_with_remote_key(self) -> None:
        """Dump and sidecars with only remote_key (no local) returns True."""
        snapshot = _make_snapshot(
            status="ready",
            authoritative_dump=_make_artifact(
                local_path=None, remote_key="s3://bucket/key"
            ),
            child_descriptors_json={
                "database": {"status": "ready"},
                "sidecars": {
                    "media-sync-manifest.json": {
                        "status": "ready",
                        "local_path": "",
                        "remote_key": "s3://bucket/m1",
                    },
                    "env-var-manifest.json": {
                        "status": "ready",
                        "local_path": "",
                        "remote_key": "s3://bucket/m2",
                    },
                    "release-metadata.json": {
                        "status": "ready",
                        "local_path": "",
                        "remote_key": "s3://bucket/m3",
                    },
                    "promotion-verification.json": {
                        "status": "ready",
                        "local_path": "",
                        "remote_key": "s3://bucket/m4",
                    },
                },
            },
        )
        assert _snapshot_capture_is_complete(snapshot) is True
