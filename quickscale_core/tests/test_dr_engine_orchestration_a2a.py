"""Pure-mock A-II coverage for media sync and policy/path safety."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

import pytest

from quickscale_core.dr_engine import orchestration as orch
from quickscale_core.dr_engine.primitives import BackupConfigurationError, BackupError
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot


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


def _snapshot(root: Path, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "snapshot_id": "snap-a2",
        "local_root_path": str(root),
        "status": "ready",
        "child_descriptors_json": {},
        "authoritative_dump": None,
    }
    return SimpleNamespace(**(values | overrides))


def _selection(
    *,
    backend: str = "local",
    use_s3_compatible: bool = False,
    options: dict[str, object] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        backend=backend,
        django_backend="storages.backends.s3.S3Storage",
        use_s3_compatible=use_s3_compatible,
        options=options or {},
    )


class TestMediaRuntimeAndCopy:
    def test_build_s3_storage_maps_options_and_omits_blank_optional_values(
        self,
    ) -> None:
        selection = _selection(
            backend="railway",
            use_s3_compatible=True,
            options={
                "bucket_name": " bucket ",
                "querystring_auth": True,
                "default_acl": " private ",
                "endpoint_url": " https://s3.example ",
                "region_name": " us-east-1 ",
                "access_key_id": " key ",
                "secret_access_key": " secret ",
            },
        )
        with patch("storages.backends.s3.S3Storage") as storage_cls:
            result = orch._build_s3_storage_from_selection(selection)

        assert result is storage_cls.return_value
        storage_cls.assert_called_once_with(
            bucket_name="bucket",
            querystring_auth=True,
            default_acl="private",
            endpoint_url="https://s3.example",
            region_name="us-east-1",
            access_key="key",
            secret_key="secret",
        )

    def test_resolve_media_runtime_uses_s3_selection(self) -> None:
        selection = _selection(
            backend="railway",
            use_s3_compatible=True,
            options={"bucket_name": "media"},
        )
        with (
            patch(f"{_ORCH}._load_storage_helpers") as load_helpers,
            patch(f"{_ORCH}._build_s3_storage_from_selection", return_value="storage"),
        ):
            load_helpers.return_value.select_storage_backend.return_value = selection
            result = orch._resolve_media_runtime(SimpleNamespace(MEDIA_ROOT="unused"))

        assert result == {
            "backend": "railway",
            "use_s3_compatible": True,
            "storage": "storage",
            "bucket_name": "media",
        }

    @pytest.mark.parametrize(
        ("selection", "settings_obj", "require_s3", "message"),
        [
            (None, SimpleNamespace(MEDIA_ROOT=""), False, "MEDIA_ROOT"),
            (
                _selection(use_s3_compatible=False),
                SimpleNamespace(MEDIA_ROOT="/media"),
                True,
                "s3-compatible",
            ),
            (
                _selection(use_s3_compatible=True, options={"bucket_name": ""}),
                SimpleNamespace(MEDIA_ROOT="/media"),
                False,
                "AWS_STORAGE_BUCKET_NAME",
            ),
        ],
    )
    def test_resolve_media_runtime_rejects_unsupported_configuration(
        self,
        selection: SimpleNamespace | None,
        settings_obj: SimpleNamespace,
        require_s3: bool,
        message: str,
    ) -> None:
        with patch(f"{_ORCH}._load_storage_helpers") as load_helpers:
            load_helpers.return_value.select_storage_backend.return_value = selection
            with pytest.raises(BackupConfigurationError, match=message):
                orch._resolve_media_runtime(
                    settings_obj, require_s3_compatible=require_s3
                )

    def test_resolve_media_runtime_falls_back_when_storage_module_is_absent(
        self,
    ) -> None:
        with patch(
            f"{_ORCH}._load_storage_helpers",
            side_effect=ModuleNotFoundError(
                "storage", name="quickscale_modules_storage"
            ),
        ):
            result = orch._resolve_media_runtime(SimpleNamespace(MEDIA_ROOT=" /media "))

        assert result == {
            "backend": "local",
            "use_s3_compatible": False,
            "media_root": Path("/media"),
        }

    def test_resolve_media_runtime_does_not_hide_helper_dependency_errors(self) -> None:
        with patch(
            f"{_ORCH}._load_storage_helpers",
            side_effect=ModuleNotFoundError("boto", name="boto3"),
        ):
            with pytest.raises(BackupConfigurationError, match="boto"):
                orch._resolve_media_runtime(SimpleNamespace(MEDIA_ROOT="/media"))

    def test_storage_object_key_normalizes_location_and_relative_path(self) -> None:
        assert orch._storage_object_key(
            SimpleNamespace(location=" /uploads/ "), "/a/b.jpg"
        ) == ("uploads/a/b.jpg")
        assert (
            orch._storage_object_key(SimpleNamespace(location=""), "a/b.jpg")
            == "a/b.jpg"
        )

    def test_copy_media_local_to_local_creates_parent_and_preserves_bytes(
        self, tmp_path: Path
    ) -> None:
        source_root = tmp_path / "source"
        target_root = tmp_path / "target"
        source = source_root / "nested" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"media")

        copied = orch._copy_media_item(
            relative_path="nested/photo.jpg",
            source_runtime={"use_s3_compatible": False, "media_root": source_root},
            target_runtime={"use_s3_compatible": False, "media_root": target_root},
        )

        assert copied is True
        assert (target_root / "nested/photo.jpg").read_bytes() == b"media"

    def test_copy_media_missing_local_source_is_negative_without_target_call(
        self, tmp_path: Path
    ) -> None:
        target = MagicMock()
        copied = orch._copy_media_item(
            relative_path="missing.jpg",
            source_runtime={"use_s3_compatible": False, "media_root": tmp_path},
            target_runtime={
                "use_s3_compatible": True,
                "storage": target,
                "bucket_name": "b",
            },
        )

        assert copied is False
        target.connection.meta.client.upload_file.assert_not_called()

    def test_copy_media_local_to_s3_uses_provider_key(self, tmp_path: Path) -> None:
        source = tmp_path / "photo.jpg"
        source.write_bytes(b"media")
        client = MagicMock()
        storage = SimpleNamespace(
            location="media",
            connection=SimpleNamespace(meta=SimpleNamespace(client=client)),
        )

        assert orch._copy_media_item(
            relative_path="photo.jpg",
            source_runtime={"use_s3_compatible": False, "media_root": tmp_path},
            target_runtime={
                "use_s3_compatible": True,
                "storage": storage,
                "bucket_name": "bucket",
            },
        )
        client.upload_file.assert_called_once_with(
            str(source), "bucket", "media/photo.jpg"
        )

    def test_copy_media_s3_to_local_and_s3_to_s3_cover_read_and_fileobj_paths(
        self, tmp_path: Path
    ) -> None:
        source_handle = MagicMock()
        source_handle.__enter__.return_value = source_handle
        source_handle.read.return_value = b"remote"
        source_storage = MagicMock()
        source_storage.open.return_value = source_handle
        local_target = tmp_path / "local"
        assert orch._copy_media_item(
            relative_path="nested/file.dump",
            source_runtime={"use_s3_compatible": True, "storage": source_storage},
            target_runtime={"use_s3_compatible": False, "media_root": local_target},
        )
        assert (local_target / "nested/file.dump").read_bytes() == b"remote"
        source_storage.open.assert_called_once_with("nested/file.dump", mode="rb")

        source_storage.open.reset_mock()
        target_client = MagicMock()
        target_storage = SimpleNamespace(
            location="prefix",
            connection=SimpleNamespace(meta=SimpleNamespace(client=target_client)),
        )
        assert orch._copy_media_item(
            relative_path="file.dump",
            source_runtime={"use_s3_compatible": True, "storage": source_storage},
            target_runtime={
                "use_s3_compatible": True,
                "storage": target_storage,
                "bucket_name": "target",
            },
        )
        target_client.upload_fileobj.assert_called_once_with(
            source_handle, "target", "prefix/file.dump"
        )


class TestMediaSyncOrchestration:
    def test_sync_dry_run_reports_missing_paths_and_skips_copy(
        self, tmp_path: Path
    ) -> None:
        present = tmp_path / "present.jpg"
        present.write_bytes(b"x")
        snapshot = _snapshot(tmp_path)
        source_runtime = {
            "backend": "local",
            "use_s3_compatible": False,
            "media_root": tmp_path,
        }
        target_runtime = {"backend": "railway", "use_s3_compatible": True}
        with (
            patch(f"{_ORCH}.get_backup_snapshot", return_value=snapshot),
            patch(
                f"{_ORCH}._load_snapshot_sidecar_payload",
                return_value={
                    "status": "ready",
                    "inventory": [
                        {"relative_path": "/present.jpg"},
                        {"relative_path": "missing.jpg"},
                        {"relative_path": ""},
                        "not-a-dict",
                    ],
                },
            ),
            patch(
                f"{_ORCH}._resolve_media_runtime",
                side_effect=[source_runtime, target_runtime],
            ),
            patch(f"{_ORCH}._copy_media_item") as copier,
        ):
            result = orch.sync_backup_snapshot_media(
                "snap-a2",
                dry_run=True,
                target_runtime_settings={"ROUTE_KIND": "railway"},
            )

        assert result == {
            "snapshot_id": "snap-a2",
            "status": "partial",
            "dry_run": True,
            "strategy": "local_to_railway",
            "source_backend": "local",
            "target_backend": "railway",
            "planned_count": 2,
            "copied_count": 0,
            "missing_paths": ["missing.jpg"],
        }
        copier.assert_not_called()

    def test_sync_execute_counts_copies_and_missing_entries(
        self, tmp_path: Path
    ) -> None:
        snapshot = _snapshot(tmp_path)
        source = {
            "backend": "source",
            "use_s3_compatible": True,
            "storage": MagicMock(),
        }
        target = {
            "backend": "target",
            "use_s3_compatible": True,
            "storage": MagicMock(),
        }
        with (
            patch(f"{_ORCH}.get_backup_snapshot", return_value=snapshot),
            patch(
                f"{_ORCH}._load_snapshot_sidecar_payload",
                return_value={
                    "status": "ready",
                    "inventory": [{"relative_path": "a"}, {"relative_path": "b"}],
                },
            ),
            patch(f"{_ORCH}._resolve_media_runtime", side_effect=[source, target]),
            patch(f"{_ORCH}._copy_media_item", side_effect=[True, False]) as copier,
        ):
            result = orch.sync_backup_snapshot_media(
                "snap-a2", target_runtime_settings={"ROUTE_KIND": "other"}
            )

        assert result["status"] == "partial"
        assert result["planned_count"] == 2
        assert result["copied_count"] == 1
        assert result["missing_paths"] == ["b"]
        assert copier.call_args_list == [
            call(relative_path="a", source_runtime=source, target_runtime=target),
            call(relative_path="b", source_runtime=source, target_runtime=target),
        ]

    @pytest.mark.parametrize(
        ("manifest", "message"),
        [
            ({"status": "unsupported"}, "unsupported"),
            ({"status": "ready", "inventory": "bad"}, "inventory must be a list"),
        ],
    )
    def test_sync_rejects_unusable_manifest(
        self, manifest: dict[str, object], message: str
    ) -> None:
        with (
            patch(
                f"{_ORCH}.get_backup_snapshot", return_value=_snapshot(Path("/snap"))
            ),
            patch(f"{_ORCH}._load_snapshot_sidecar_payload", return_value=manifest),
        ):
            with pytest.raises(BackupError, match=message):
                orch.sync_backup_snapshot_media("snap-a2", target_runtime_settings={})


class TestPolicySnapshotOrchestration:
    def test_build_policy_snapshot_from_model_copies_all_fields(self) -> None:
        model = SimpleNamespace(
            retention_days=9,
            naming_prefix="model",
            target_mode="private_remote",
            local_directory="local",
            remote_bucket_name="bucket",
            remote_prefix="prefix",
            remote_endpoint_url="endpoint",
            remote_region_name="region",
            remote_access_key_id_env_var="ACCESS",
            remote_secret_access_key_env_var="SECRET",
            automation_enabled=True,
            schedule="0 2 * * *",
        )
        assert orch._build_policy_snapshot_from_model(model) == _policy(
            retention_days=9,
            naming_prefix="model",
            target_mode="private_remote",
            local_directory="local",
            remote_bucket_name="bucket",
            remote_prefix="prefix",
            remote_endpoint_url="endpoint",
            remote_region_name="region",
            remote_access_key_id_env_var="ACCESS",
            remote_secret_access_key_env_var="SECRET",
            automation_enabled=True,
            schedule="0 2 * * *",
        )

    def test_build_policy_snapshot_from_settings_applies_defaults_and_strings(
        self,
    ) -> None:
        fake_settings = SimpleNamespace(
            QUICKSCALE_BACKUPS_RETENTION_DAYS="7",
            QUICKSCALE_BACKUPS_NAMING_PREFIX=" app ",
            QUICKSCALE_BACKUPS_TARGET_MODE="private_remote",
            QUICKSCALE_BACKUPS_LOCAL_DIRECTORY="backups",
            QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME="bucket",
            QUICKSCALE_BACKUPS_REMOTE_PREFIX="prefix",
            QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL="endpoint",
            QUICKSCALE_BACKUPS_REMOTE_REGION_NAME="",
            QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR="ACCESS",
            QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR="SECRET",
            QUICKSCALE_BACKUPS_AUTOMATION_ENABLED=True,
            QUICKSCALE_BACKUPS_SCHEDULE="schedule",
        )
        with patch(f"{_ORCH}.settings", fake_settings):
            result = orch._build_policy_snapshot_from_settings()
        assert result.retention_days == 7
        assert result.naming_prefix == " app "
        assert result.target_mode == "private_remote"
        assert result.schedule == "schedule"

    @pytest.mark.parametrize(
        ("overrides", "expected"),
        [
            ({"retention_days": 0}, "retention_days"),
            ({"naming_prefix": " "}, "naming_prefix"),
            ({"target_mode": "remote"}, "target_mode"),
            ({"local_directory": " "}, "local_directory"),
            ({"automation_enabled": True, "schedule": ""}, "schedule"),
            (
                {"target_mode": "private_remote", "remote_bucket_name": ""},
                "remote_bucket_name",
            ),
            (
                {"target_mode": "private_remote", "remote_access_key_id_env_var": ""},
                "access_key",
            ),
            (
                {
                    "target_mode": "private_remote",
                    "remote_secret_access_key_env_var": "",
                },
                "secret_access_key",
            ),
            (
                {
                    "target_mode": "private_remote",
                    "remote_region_name": "",
                    "remote_endpoint_url": "",
                },
                "region_name",
            ),
        ],
    )
    def test_policy_validation_reports_each_invalid_contract(
        self, overrides: dict[str, object], expected: str
    ) -> None:
        assert any(
            expected in issue
            for issue in orch._validate_policy_snapshot_internal(_policy(**overrides))
        )

    def test_load_active_policy_uses_settings_and_ensures_existing_provider_policy(
        self,
    ) -> None:
        settings_policy = _policy(naming_prefix="settings")
        with (
            patch(
                f"{_ORCH}._build_policy_snapshot_from_settings",
                return_value=settings_policy,
            ),
            patch(
                "quickscale_core.dr_engine.persistence.has_any_policy",
                return_value=True,
            ),
            patch(
                "quickscale_core.dr_engine.persistence.ensure_default_policy"
            ) as ensure,
        ):
            assert orch._load_active_policy_snapshot() is settings_policy
        ensure.assert_called_once_with()

    def test_load_active_policy_does_not_touch_provider_when_empty(self) -> None:
        settings_policy = _policy(naming_prefix="settings")
        with (
            patch(
                f"{_ORCH}._build_policy_snapshot_from_settings",
                return_value=settings_policy,
            ),
            patch(
                "quickscale_core.dr_engine.persistence.has_any_policy",
                return_value=False,
            ),
            patch(
                "quickscale_core.dr_engine.persistence.ensure_default_policy"
            ) as ensure,
        ):
            assert orch._load_active_policy_snapshot() is settings_policy
        ensure.assert_not_called()


class TestPathSafetyAndDownloads:
    def test_path_within_root_and_symlink_detection_are_boundary_aware(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "backups"
        root.mkdir()
        nested = root / "nested" / "file.dump"
        nested.parent.mkdir()
        nested.write_text("dump")
        assert orch._is_path_within_root(nested, root)
        assert not orch._is_path_within_root(tmp_path / "other", root)
        assert not orch._path_uses_symlink_within_root(nested, root)
        link = root / "link"
        link.symlink_to(nested.parent, target_is_directory=True)
        assert orch._path_uses_symlink_within_root(link / "file.dump", root)

    def test_authoritative_roots_deduplicate_policy_and_snapshot_roots(
        self, tmp_path: Path
    ) -> None:
        artifact = SimpleNamespace()
        policy = _policy(local_directory=str(tmp_path))
        with (
            patch(
                f"{_ORCH}._get_authoritative_snapshot_for_artifact",
                return_value=_snapshot(tmp_path),
            ),
            patch(f"{_ORCH}.get_local_backup_directory", return_value=tmp_path),
        ):
            roots = orch._get_authoritative_local_backup_roots(artifact, policy)
        assert roots == (tmp_path,)

    def test_download_backup_path_accepts_authoritative_regular_file(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "backup.dump"
        file_path.write_text("dump")
        artifact = SimpleNamespace(local_path=str(file_path))
        with (
            patch(f"{_ORCH}.get_local_backup_directory", return_value=tmp_path),
            patch(
                f"{_ORCH}._get_authoritative_snapshot_for_artifact", return_value=None
            ),
        ):
            assert orch.download_backup_path(artifact, policy=_policy()) == file_path

    @pytest.mark.parametrize(
        ("artifact_path", "root", "message"),
        [
            (None, "/tmp", "does not have"),
            ("/tmp/missing.dump", "/tmp", "not found"),
        ],
    )
    def test_download_backup_path_rejects_missing_artifacts(
        self, artifact_path: str | None, root: str, message: str
    ) -> None:
        with pytest.raises(BackupError, match=message):
            orch.download_backup_path(
                SimpleNamespace(local_path=artifact_path),
                policy=_policy(local_directory=root),
            )

    def test_download_backup_path_rejects_outside_and_symlink_paths(
        self, tmp_path: Path
    ) -> None:
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside.dump"
        outside.write_text("dump")
        with (
            patch(f"{_ORCH}.get_local_backup_directory", return_value=root),
            patch(
                f"{_ORCH}._get_authoritative_snapshot_for_artifact", return_value=None
            ),
        ):
            with pytest.raises(BackupError, match="authoritative"):
                orch.download_backup_path(
                    SimpleNamespace(local_path=str(outside)), policy=_policy()
                )

        real = root / "real.dump"
        real.write_text("dump")
        link = root / "link.dump"
        link.symlink_to(real)
        with (
            patch(f"{_ORCH}.get_local_backup_directory", return_value=root),
            patch(
                f"{_ORCH}._get_authoritative_snapshot_for_artifact", return_value=None
            ),
        ):
            with pytest.raises(BackupError, match="symlinks"):
                orch.download_backup_path(
                    SimpleNamespace(local_path=str(link)), policy=_policy()
                )

    def test_download_backup_path_rejects_directory_even_inside_authoritative_root(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / "directory"
        directory.mkdir()
        with (
            patch(f"{_ORCH}.get_local_backup_directory", return_value=tmp_path),
            patch(
                f"{_ORCH}._get_authoritative_snapshot_for_artifact", return_value=None
            ),
        ):
            with pytest.raises(BackupError, match="regular file"):
                orch.download_backup_path(
                    SimpleNamespace(local_path=str(directory)), policy=_policy()
                )
