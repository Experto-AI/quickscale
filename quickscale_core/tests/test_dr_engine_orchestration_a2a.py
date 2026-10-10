"""Pure-mock A-II coverage for media sync and policy/path safety."""

from __future__ import annotations
import quickscale_core.dr_engine._media as _media
import quickscale_core.dr_engine._prune as _prune
import quickscale_core.dr_engine._policy as _policy_2

import os
import stat
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import IO
from unittest.mock import MagicMock, call, patch

import pytest

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
            result = _media._build_s3_storage_from_selection(selection)

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
            patch(
                "quickscale_core.dr_engine._metadata._load_storage_helpers"
            ) as load_helpers,
            patch(
                "quickscale_core.dr_engine._media._build_s3_storage_from_selection",
                return_value="storage",
            ),
        ):
            load_helpers.return_value.select_storage_backend.return_value = selection
            result = _media._resolve_media_runtime(SimpleNamespace(MEDIA_ROOT="unused"))

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
        with patch(
            "quickscale_core.dr_engine._metadata._load_storage_helpers"
        ) as load_helpers:
            load_helpers.return_value.select_storage_backend.return_value = selection
            with pytest.raises(BackupConfigurationError, match=message):
                _media._resolve_media_runtime(
                    settings_obj, require_s3_compatible=require_s3
                )

    def test_resolve_media_runtime_falls_back_when_storage_module_is_absent(
        self,
    ) -> None:
        with patch(
            "quickscale_core.dr_engine._metadata._load_storage_helpers",
            side_effect=ModuleNotFoundError(
                "storage", name="quickscale_modules_storage"
            ),
        ):
            result = _media._resolve_media_runtime(
                SimpleNamespace(MEDIA_ROOT=" /media ")
            )

        assert result == {
            "backend": "local",
            "use_s3_compatible": False,
            "media_root": Path("/media"),
        }

    def test_resolve_media_runtime_does_not_hide_helper_dependency_errors(self) -> None:
        with patch(
            "quickscale_core.dr_engine._metadata._load_storage_helpers",
            side_effect=ModuleNotFoundError("boto", name="boto3"),
        ):
            with pytest.raises(BackupConfigurationError, match="boto"):
                _media._resolve_media_runtime(SimpleNamespace(MEDIA_ROOT="/media"))

    def test_storage_object_key_normalizes_location_and_relative_path(self) -> None:
        assert _media._storage_object_key(
            SimpleNamespace(location=" /uploads/ "), "/a/b.jpg"
        ) == ("uploads/a/b.jpg")
        assert (
            _media._storage_object_key(SimpleNamespace(location=""), "a/b.jpg")
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

        copied = _media._copy_media_item(
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
        copied = _media._copy_media_item(
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

        assert _media._copy_media_item(
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

    def test_copy_media_s3_to_s3_relays_through_a_bounded_spool(self) -> None:
        """The relay never opens the spooling storage API on either side."""
        payload = b"y" * (1024 * 1024 + 1)
        read_sizes: list[int] = []
        uploaded: list[bytes] = []

        def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
            for offset in range(0, len(payload), 64 * 1024):
                fileobj.write(payload[offset : offset + 64 * 1024])

        def _upload_fileobj(fileobj: IO[bytes], bucket: str, key: str) -> None:
            while chunk := fileobj.read(64 * 1024):
                read_sizes.append(len(chunk))
                uploaded.append(chunk)

        source_client = MagicMock()
        source_client.download_fileobj.side_effect = _download_fileobj
        source_storage = MagicMock()
        source_storage.location = "media"
        source_storage.connection.meta.client = source_client
        target_client = MagicMock()
        target_client.upload_fileobj.side_effect = _upload_fileobj
        target_storage = SimpleNamespace(
            location="prefix",
            connection=SimpleNamespace(meta=SimpleNamespace(client=target_client)),
        )

        assert _media._copy_media_item(
            relative_path="file.dump",
            source_runtime={
                "use_s3_compatible": True,
                "storage": source_storage,
                "bucket_name": "source-bucket",
            },
            target_runtime={
                "use_s3_compatible": True,
                "storage": target_storage,
                "bucket_name": "target",
            },
        )

        assert b"".join(uploaded) == payload
        assert read_sizes and all(size <= 64 * 1024 for size in read_sizes)
        assert source_client.download_fileobj.call_args.args[:2] == (
            "source-bucket",
            "media/file.dump",
        )
        assert target_client.upload_fileobj.call_args.args[1:] == (
            "target",
            "prefix/file.dump",
        )
        source_storage.open.assert_not_called()

    def test_copy_media_s3_to_s3_bypasses_real_storage_open_on_both_sides(
        self,
    ) -> None:
        """Real S3Storage instances are never opened; only clients are used."""
        from storages.backends.s3 import S3Storage

        with patch(
            "storages.backends.s3.setting",
            side_effect=lambda name, default=None: default,
        ):
            source_storage = S3Storage(
                bucket_name="source-bucket",
                access_key="key",
                secret_key="secret",
                region_name="us-east-1",
            )
            target_storage = S3Storage(
                bucket_name="target-bucket",
                access_key="key",
                secret_key="secret",
                region_name="us-east-1",
            )
        payload = b"relayed-bytes"
        uploaded: list[bytes] = []

        def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
            assert (bucket, key) == ("source-bucket", "clip.mp4")
            fileobj.write(payload)

        def _upload_fileobj(fileobj: IO[bytes], bucket: str, key: str) -> None:
            assert (bucket, key) == ("target-bucket", "clip.mp4")
            uploaded.append(fileobj.read())

        source_client = source_storage.connection.meta.client
        target_client = target_storage.connection.meta.client
        with (
            patch.object(
                source_client, "download_fileobj", side_effect=_download_fileobj
            ),
            patch.object(target_client, "upload_fileobj", side_effect=_upload_fileobj),
            patch.object(
                S3Storage, "open", side_effect=AssertionError("spooling read path")
            ),
        ):
            assert _media._copy_media_item(
                relative_path="clip.mp4",
                source_runtime={
                    "use_s3_compatible": True,
                    "storage": source_storage,
                    "bucket_name": "source-bucket",
                },
                target_runtime={
                    "use_s3_compatible": True,
                    "storage": target_storage,
                    "bucket_name": "target-bucket",
                },
            )

        assert uploaded == [payload]

    def test_copy_media_s3_to_local_downloads_chunks_through_the_provider_client(
        self, tmp_path: Path
    ) -> None:
        """The copy streams through the provider client, never storage.open()."""
        payload = b"x" * (1024 * 1024 + 1)
        chunk_size = 64 * 1024
        writes: list[int] = []

        def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
            for offset in range(0, len(payload), chunk_size):
                chunk = payload[offset : offset + chunk_size]
                fileobj.write(chunk)
                writes.append(len(chunk))

        client = MagicMock()
        client.download_fileobj.side_effect = _download_fileobj
        source_storage = MagicMock()
        source_storage.location = "media"
        source_storage.connection.meta.client = client
        target_root = tmp_path / "target"

        assert _media._copy_media_item(
            relative_path="large/video.mp4",
            source_runtime={
                "use_s3_compatible": True,
                "storage": source_storage,
                "bucket_name": "source-bucket",
            },
            target_runtime={"use_s3_compatible": False, "media_root": target_root},
        )

        assert (target_root / "large/video.mp4").read_bytes() == payload
        source_storage.open.assert_not_called()
        args = client.download_fileobj.call_args.args
        assert args[0] == "source-bucket"
        assert args[1] == "media/large/video.mp4"
        assert writes and all(size <= chunk_size for size in writes)
        assert [
            path.relative_to(target_root).as_posix()
            for path in target_root.rglob("*")
            if path.is_file()
        ] == ["large/video.mp4"]

    def test_copy_media_s3_to_local_preserves_destination_when_download_fails(
        self, tmp_path: Path
    ) -> None:
        """A failed download must not destroy the destination or its siblings."""
        target_root = tmp_path / "target"
        target_path = target_root / "video.mp4"
        target_path.parent.mkdir(parents=True)
        target_path.write_bytes(b"previous good bytes")
        neighbor = target_root / "video.mp4.part"
        neighbor.write_bytes(b"unrelated operator file")

        def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
            fileobj.write(b"partial")
            raise TimeoutError("download interrupted")

        client = MagicMock()
        client.download_fileobj.side_effect = _download_fileobj
        source_storage = MagicMock()
        source_storage.location = ""
        source_storage.connection.meta.client = client

        with pytest.raises(TimeoutError):
            _media._copy_media_item(
                relative_path="video.mp4",
                source_runtime={
                    "use_s3_compatible": True,
                    "storage": source_storage,
                    "bucket_name": "source-bucket",
                },
                target_runtime={"use_s3_compatible": False, "media_root": target_root},
            )

        assert target_path.read_bytes() == b"previous good bytes"
        assert neighbor.read_bytes() == b"unrelated operator file"
        assert sorted(path.name for path in target_root.iterdir()) == [
            "video.mp4",
            "video.mp4.part",
        ]

    def test_copy_media_s3_to_local_leaves_an_existing_sibling_part_file_alone(
        self, tmp_path: Path
    ) -> None:
        """Staging files are uniquely owned; a real sibling `.part` file survives."""
        target_root = tmp_path / "target"
        target_root.mkdir(parents=True)
        neighbor = target_root / "video.mp4.part"
        neighbor.write_bytes(b"unrelated operator file")

        def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
            fileobj.write(b"downloaded bytes")

        client = MagicMock()
        client.download_fileobj.side_effect = _download_fileobj
        source_storage = MagicMock()
        source_storage.location = ""
        source_storage.connection.meta.client = client

        assert _media._copy_media_item(
            relative_path="video.mp4",
            source_runtime={
                "use_s3_compatible": True,
                "storage": source_storage,
                "bucket_name": "source-bucket",
            },
            target_runtime={"use_s3_compatible": False, "media_root": target_root},
        )

        assert (target_root / "video.mp4").read_bytes() == b"downloaded bytes"
        assert neighbor.read_bytes() == b"unrelated operator file"
        assert sorted(path.name for path in target_root.iterdir()) == [
            "video.mp4",
            "video.mp4.part",
        ]

    def test_copy_media_s3_to_local_keeps_existing_destination_permissions(
        self, tmp_path: Path
    ) -> None:
        """Refreshing a media file keeps the mode other processes rely on."""
        target_root = tmp_path / "target"
        target_path = target_root / "video.mp4"
        target_path.parent.mkdir(parents=True)
        target_path.write_bytes(b"old bytes")
        target_path.chmod(0o640)

        def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
            fileobj.write(b"new bytes")

        client = MagicMock()
        client.download_fileobj.side_effect = _download_fileobj
        source_storage = MagicMock()
        source_storage.location = ""
        source_storage.connection.meta.client = client

        assert _media._copy_media_item(
            relative_path="video.mp4",
            source_runtime={
                "use_s3_compatible": True,
                "storage": source_storage,
                "bucket_name": "source-bucket",
            },
            target_runtime={"use_s3_compatible": False, "media_root": target_root},
        )

        assert target_path.read_bytes() == b"new bytes"
        assert stat.S_IMODE(target_path.stat().st_mode) == 0o640

    def test_copy_media_s3_to_local_new_destination_gets_umask_default_permissions(
        self, tmp_path: Path
    ) -> None:
        """A new media file is as readable as a plain create would be."""
        previous_umask = os.umask(0o022)
        try:
            target_root = tmp_path / "target"

            def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
                fileobj.write(b"new bytes")

            client = MagicMock()
            client.download_fileobj.side_effect = _download_fileobj
            source_storage = MagicMock()
            source_storage.location = ""
            source_storage.connection.meta.client = client

            assert _media._copy_media_item(
                relative_path="video.mp4",
                source_runtime={
                    "use_s3_compatible": True,
                    "storage": source_storage,
                    "bucket_name": "source-bucket",
                },
                target_runtime={"use_s3_compatible": False, "media_root": target_root},
            )
        finally:
            os.umask(previous_umask)

        target_path = target_root / "video.mp4"
        assert target_path.read_bytes() == b"new bytes"
        assert stat.S_IMODE(target_path.stat().st_mode) == 0o644

    def test_copy_media_s3_to_local_bypasses_the_real_storage_spooling_read(
        self, tmp_path: Path
    ) -> None:
        """S3Storage.open() spools whole objects in memory; the copy must not call it."""
        from storages.backends.s3 import S3Storage

        with patch(
            "storages.backends.s3.setting",
            side_effect=lambda name, default=None: default,
        ):
            storage = S3Storage(
                bucket_name="source-bucket",
                access_key="key",
                secret_key="secret",
                region_name="us-east-1",
            )
        client = storage.connection.meta.client
        payload = b"remote-bytes"
        target_root = tmp_path / "target"

        def _download_fileobj(bucket: str, key: str, fileobj: IO[bytes]) -> None:
            fileobj.write(payload)

        with (
            patch.object(client, "download_fileobj", side_effect=_download_fileobj),
            patch.object(
                S3Storage, "open", side_effect=AssertionError("spooling read path")
            ),
        ):
            assert _media._copy_media_item(
                relative_path="clip.mp4",
                source_runtime={
                    "use_s3_compatible": True,
                    "storage": storage,
                    "bucket_name": "source-bucket",
                },
                target_runtime={"use_s3_compatible": False, "media_root": target_root},
            )

        assert (target_root / "clip.mp4").read_bytes() == payload


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
            patch(
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=snapshot,
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._load_snapshot_sidecar_payload",
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
                "quickscale_core.dr_engine._media._resolve_media_runtime",
                side_effect=[source_runtime, target_runtime],
            ),
            patch("quickscale_core.dr_engine._media._copy_media_item") as copier,
        ):
            result = _media.sync_backup_snapshot_media(
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
            patch(
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=snapshot,
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._load_snapshot_sidecar_payload",
                return_value={
                    "status": "ready",
                    "inventory": [{"relative_path": "a"}, {"relative_path": "b"}],
                },
            ),
            patch(
                "quickscale_core.dr_engine._media._resolve_media_runtime",
                side_effect=[source, target],
            ),
            patch(
                "quickscale_core.dr_engine._media._copy_media_item",
                side_effect=[True, False],
            ) as copier,
        ):
            result = _media.sync_backup_snapshot_media(
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
                "quickscale_core.dr_engine._state.get_backup_snapshot",
                return_value=_snapshot(Path("/snap")),
            ),
            patch(
                "quickscale_core.dr_engine._sidecar._load_snapshot_sidecar_payload",
                return_value=manifest,
            ),
        ):
            with pytest.raises(BackupError, match=message):
                _media.sync_backup_snapshot_media("snap-a2", target_runtime_settings={})


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
        assert _policy_2._build_policy_snapshot_from_model(model) == _policy(
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
            for issue in _policy_2._validate_policy_snapshot_internal(
                _policy(**overrides)
            )
        )

    def test_load_active_policy_uses_settings_and_ensures_existing_provider_policy(
        self,
    ) -> None:
        settings_policy = _policy(naming_prefix="settings")
        with (
            patch(
                "quickscale_core.dr_engine.persistence.settings_policy_snapshot",
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
            assert _policy_2._load_active_policy_snapshot() is settings_policy
        ensure.assert_called_once_with()

    def test_load_active_policy_can_skip_default_reconciliation(self) -> None:
        settings_policy = _policy(naming_prefix="settings")
        with (
            patch(
                "quickscale_core.dr_engine.persistence.settings_policy_snapshot",
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
            assert (
                _policy_2._load_active_policy_snapshot(ensure_default=False)
                is settings_policy
            )
        ensure.assert_not_called()

    def test_load_active_policy_does_not_touch_provider_when_empty(self) -> None:
        settings_policy = _policy(naming_prefix="settings")
        with (
            patch(
                "quickscale_core.dr_engine.persistence.settings_policy_snapshot",
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
            assert _policy_2._load_active_policy_snapshot() is settings_policy
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
        assert _prune._is_path_within_root(nested, root)
        assert not _prune._is_path_within_root(tmp_path / "other", root)
        assert not _prune._path_uses_symlink_within_root(nested, root)
        link = root / "link"
        link.symlink_to(nested.parent, target_is_directory=True)
        assert _prune._path_uses_symlink_within_root(link / "file.dump", root)

    def test_authoritative_roots_deduplicate_policy_and_snapshot_roots(
        self, tmp_path: Path
    ) -> None:
        artifact = SimpleNamespace()
        policy = _policy(local_directory=str(tmp_path))
        with (
            patch(
                "quickscale_core.dr_engine._state._get_authoritative_snapshot_for_artifact",
                return_value=_snapshot(tmp_path),
            ),
            patch(
                "quickscale_core.dr_engine._paths.get_local_backup_directory",
                return_value=tmp_path,
            ),
        ):
            roots = _prune._get_authoritative_local_backup_roots(artifact, policy)
        assert roots == (tmp_path,)

    def test_download_backup_path_accepts_authoritative_regular_file(
        self, tmp_path: Path
    ) -> None:
        file_path = tmp_path / "backup.dump"
        file_path.write_text("dump")
        artifact = SimpleNamespace(local_path=str(file_path))
        with (
            patch(
                "quickscale_core.dr_engine._paths.get_local_backup_directory",
                return_value=tmp_path,
            ),
            patch(
                "quickscale_core.dr_engine._state._get_authoritative_snapshot_for_artifact",
                return_value=None,
            ),
        ):
            assert _prune.download_backup_path(artifact, policy=_policy()) == file_path

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
            _prune.download_backup_path(
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
            patch(
                "quickscale_core.dr_engine._paths.get_local_backup_directory",
                return_value=root,
            ),
            patch(
                "quickscale_core.dr_engine._state._get_authoritative_snapshot_for_artifact",
                return_value=None,
            ),
        ):
            with pytest.raises(BackupError, match="authoritative"):
                _prune.download_backup_path(
                    SimpleNamespace(local_path=str(outside)), policy=_policy()
                )

        real = root / "real.dump"
        real.write_text("dump")
        link = root / "link.dump"
        link.symlink_to(real)
        with (
            patch(
                "quickscale_core.dr_engine._paths.get_local_backup_directory",
                return_value=root,
            ),
            patch(
                "quickscale_core.dr_engine._state._get_authoritative_snapshot_for_artifact",
                return_value=None,
            ),
        ):
            with pytest.raises(BackupError, match="symlinks"):
                _prune.download_backup_path(
                    SimpleNamespace(local_path=str(link)), policy=_policy()
                )

    def test_download_backup_path_rejects_directory_even_inside_authoritative_root(
        self, tmp_path: Path
    ) -> None:
        directory = tmp_path / "directory"
        directory.mkdir()
        with (
            patch(
                "quickscale_core.dr_engine._paths.get_local_backup_directory",
                return_value=tmp_path,
            ),
            patch(
                "quickscale_core.dr_engine._state._get_authoritative_snapshot_for_artifact",
                return_value=None,
            ),
        ):
            with pytest.raises(BackupError, match="regular file"):
                _prune.download_backup_path(
                    SimpleNamespace(local_path=str(directory)), policy=_policy()
                )
