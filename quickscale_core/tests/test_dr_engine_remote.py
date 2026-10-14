"""Behavior and source-contract tests for the private-remote DR materializer.

``_materialize_private_remote_key`` must stream a remote object through the
provider client's chunked ``download_fileobj`` transfer. The storage API's
``open()`` spools each whole object in memory (``AWS_S3_MAX_MEMORY_SIZE``
defaults to unbounded), so a dump larger than the container's memory OOM-kills
the restore. A source scan keeps that spooling call out of ``dr_engine``.
"""

from __future__ import annotations

import ast
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import patch

import pytest

import quickscale_core.dr_engine._remote as _remote
from quickscale_core.dr_engine.primitives import BackupError
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot

_REMOTE_KEY = "ops/backups/snapshots/snap-1/database/artifact.dump"


def _private_remote_policy() -> BackupPolicySnapshot:
    return BackupPolicySnapshot(
        retention_days=14,
        naming_prefix="db",
        target_mode="private_remote",
        local_directory=".quickscale/backups",
        remote_bucket_name="private-backups",
        remote_prefix="ops/backups",
        remote_endpoint_url="https://object-storage.example.invalid",
        remote_region_name="us-east-1",
        remote_access_key_id_env_var="TEST_REMOTE_ACCESS_KEY",
        remote_secret_access_key_env_var="TEST_REMOTE_SECRET_KEY",
        automation_enabled=False,
        schedule="0 2 * * *",
    )


class _ChunkedClient:
    """Provider-client double that writes the payload in bounded chunks."""

    def __init__(self, payload: bytes, chunk_size: int) -> None:
        self.payload = payload
        self.chunk_size = chunk_size
        self.calls: list[tuple[str, str]] = []
        self.write_sizes: list[int] = []

    def download_fileobj(self, bucket_name: str, remote_key: str, fileobj: Any) -> None:
        self.calls.append((bucket_name, remote_key))
        for offset in range(0, len(self.payload), self.chunk_size):
            chunk = self.payload[offset : offset + self.chunk_size]
            fileobj.write(chunk)
            self.write_sizes.append(len(chunk))


class _InterruptedClient:
    """Provider-client double whose download fails partway through."""

    def download_fileobj(self, bucket_name: str, remote_key: str, fileobj: Any) -> None:
        del bucket_name, remote_key
        fileobj.write(b"partial remote bytes")
        raise TimeoutError("download interrupted")


def _fake_storage_class(client: Any) -> tuple[type, list[Any]]:
    """Build an ``S3Storage`` replacement wired to *client*; also collect made instances."""
    instances: list[Any] = []

    class _FakeS3Storage:
        def __init__(self, **options: Any) -> None:
            self.options = options
            self.open_calls: list[tuple[str, str]] = []
            self.connection = _client_connection(client)
            instances.append(self)

        def _normalize_name(self, name: str) -> str:
            return name

        def open(self, name: str, mode: str = "rb") -> Any:
            self.open_calls.append((name, mode))
            raise AssertionError("storage.open() must not read remote objects")

    return _FakeS3Storage, instances


def _client_connection(client: Any) -> SimpleNamespace:
    return SimpleNamespace(meta=SimpleNamespace(client=client))


def _storage_class_with_connection(connection: Any) -> type:
    """Real ``S3Storage`` normalization with the provider connection replaced."""
    from storages.backends.s3 import S3Storage

    class _StorageWithConnection(S3Storage):
        @property
        def connection(self) -> Any:
            return connection

    return _StorageWithConnection


class _StoredObject:
    """S3 resource-object double that records one uploaded object by key."""

    def __init__(self, objects: dict[str, bytes], key: str) -> None:
        self._objects = objects
        self._key = key

    def upload_fileobj(self, fileobj: Any, **kwargs: Any) -> None:
        del kwargs
        self._objects[self._key] = fileobj.read()


class _RoundTripProvider:
    """In-memory provider double that stores uploads under their normalized key."""

    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.downloads: list[tuple[str, str]] = []
        self.meta = SimpleNamespace(client=self)

    def Bucket(self, bucket_name: str) -> Any:  # noqa: N802 - boto3 resource API name
        del bucket_name
        provider = self

        class _Bucket:
            def Object(self, key: str) -> Any:  # noqa: N802 - boto3 resource API name
                return _StoredObject(provider.objects, key)

        return _Bucket()

    def download_fileobj(self, bucket_name: str, key: str, fileobj: Any) -> None:
        self.downloads.append((bucket_name, key))
        fileobj.write(self.objects[key])


def _default_setting(name: str, default: Any = None) -> Any:
    del name
    return default


def _aws_location_setting(name: str, default: Any = None) -> Any:
    return "media" if name == "AWS_LOCATION" else default


class _BoundedStream:
    """Response-body stand-in that refuses an unbounded whole-object read."""

    def __init__(self, payload: bytes, max_read: int) -> None:
        self._stream = BytesIO(payload)
        self.max_read = max_read
        self.reads: list[int | None] = []

    def read(self, amt: int | None = None) -> bytes:
        self.reads.append(amt)
        if amt is None or amt <= 0 or amt > self.max_read:
            raise AssertionError(f"unbounded object read requested: {amt}")
        return self._stream.read(amt)


def _stubbed_provider_client(payload: bytes) -> tuple[Any, _BoundedStream]:
    """Real boto3 client whose S3 transport is stubbed and whose body is instrumented."""
    import boto3

    from botocore.stub import Stubber

    body = _BoundedStream(payload, max_read=8 * 1024 * 1024)
    client = boto3.client(
        "s3",
        region_name="us-east-1",
        aws_access_key_id="stub-access-key",
        aws_secret_access_key="stub-secret-key",
    )
    stubber = Stubber(client)
    stubber.add_response(
        "head_object",
        {
            "ContentLength": len(payload),
            "ETag": '"stub-etag"',
            "ResponseMetadata": {},
        },
        {"Bucket": "private-backups", "Key": _REMOTE_KEY},
    )
    stubber.add_response(
        "get_object",
        {"Body": body, "ContentLength": len(payload), "ResponseMetadata": {}},
        {"Bucket": "private-backups", "Key": _REMOTE_KEY},
    )
    stubber.activate()
    return client, body


class TestMaterializePrivateRemoteKey:
    """The materializer streams the object and cleans up after failure."""

    def test_streams_chunks_through_the_provider_client(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_REMOTE_ACCESS_KEY", "access-key")
        monkeypatch.setenv("TEST_REMOTE_SECRET_KEY", "secret-key")
        payload = b"x" * (1024 * 1024 + 1)
        chunk_size = 64 * 1024
        client = _ChunkedClient(payload, chunk_size)
        storage_class, storages = _fake_storage_class(client)
        destination = tmp_path / "materialized" / "artifact.dump"

        with patch("storages.backends.s3.S3Storage", storage_class):
            _remote._materialize_private_remote_key(
                _REMOTE_KEY,
                _private_remote_policy(),
                destination,
            )

        assert destination.read_bytes() == payload
        assert destination.parent.is_dir()
        assert client.calls == [("private-backups", _REMOTE_KEY)]
        assert client.write_sizes
        assert all(size <= chunk_size for size in client.write_sizes)
        assert storages and storages[0].open_calls == []
        assert storages[0].options["access_key"] == "access-key"

    def test_download_uses_the_storage_location_prefix(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A nonempty AWS_LOCATION applies to the download, as it does to the upload."""
        monkeypatch.setenv("TEST_REMOTE_ACCESS_KEY", "access-key")
        monkeypatch.setenv("TEST_REMOTE_SECRET_KEY", "secret-key")
        payload = b"remote payload"
        client = _ChunkedClient(payload, 64 * 1024)
        storage_class = _storage_class_with_connection(_client_connection(client))
        destination = tmp_path / "materialized" / "artifact.dump"

        with (
            patch("storages.backends.s3.setting", side_effect=_aws_location_setting),
            patch("storages.backends.s3.S3Storage", storage_class),
        ):
            _remote._materialize_private_remote_key(
                _REMOTE_KEY,
                _private_remote_policy(),
                destination,
            )

        assert client.calls == [("private-backups", f"media/{_REMOTE_KEY}")]
        assert destination.read_bytes() == payload

    def test_upload_and_download_agree_on_the_provider_object_key(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """With AWS_LOCATION set, the restore fetches the object the uploader stored."""
        monkeypatch.setenv("TEST_REMOTE_ACCESS_KEY", "access-key")
        monkeypatch.setenv("TEST_REMOTE_SECRET_KEY", "secret-key")
        payload = b"uploaded artifact bytes"
        local_path = tmp_path / "artifact.dump"
        local_path.write_bytes(payload)
        destination = tmp_path / "materialized" / "artifact.dump"
        provider = _RoundTripProvider()
        storage_class = _storage_class_with_connection(provider)

        with (
            patch("storages.backends.s3.setting", side_effect=_aws_location_setting),
            patch("storages.backends.s3.S3Storage", storage_class),
        ):
            remote_key = _remote._upload_to_private_remote(
                local_path,
                _private_remote_policy(),
            )
            _remote._materialize_private_remote_key(
                remote_key,
                _private_remote_policy(),
                destination,
            )

        expected_object_key = f"media/{remote_key}"
        assert remote_key == "ops/backups/artifact.dump"
        assert list(provider.objects) == [expected_object_key]
        assert provider.downloads == [("private-backups", expected_object_key)]
        assert destination.read_bytes() == payload

    def test_real_provider_transfer_reads_the_object_in_bounded_chunks(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The real provider transfer never asks the body for the whole object."""
        monkeypatch.setenv("TEST_REMOTE_ACCESS_KEY", "access-key")
        monkeypatch.setenv("TEST_REMOTE_SECRET_KEY", "secret-key")
        payload = b"x" * (1024 * 1024 + 1)
        client, body = _stubbed_provider_client(payload)
        storage_class = _storage_class_with_connection(_client_connection(client))
        destination = tmp_path / "materialized" / "artifact.dump"

        with (
            patch("storages.backends.s3.setting", side_effect=_default_setting),
            patch("storages.backends.s3.S3Storage", storage_class),
        ):
            _remote._materialize_private_remote_key(
                _REMOTE_KEY,
                _private_remote_policy(),
                destination,
            )

        assert destination.read_bytes() == payload
        assert body.reads
        assert all(amt is not None and 0 < amt <= body.max_read for amt in body.reads)

    def test_failure_removes_the_partial_destination(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("TEST_REMOTE_ACCESS_KEY", "access-key")
        monkeypatch.setenv("TEST_REMOTE_SECRET_KEY", "secret-key")
        storage_class, _ = _fake_storage_class(_InterruptedClient())
        destination = tmp_path / "materialized" / "artifact.dump"

        with patch("storages.backends.s3.S3Storage", storage_class):
            with pytest.raises(
                BackupError, match="Private remote materialization failed"
            ) as exc_info:
                _remote._materialize_private_remote_key(
                    _REMOTE_KEY,
                    _private_remote_policy(),
                    destination,
                )

        assert isinstance(exc_info.value.__cause__, TimeoutError)
        assert not destination.exists()


def _dotted_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _storage_open_calls(source: str) -> list[str]:
    """List ``<receiver>.open(...)`` calls whose receiver names a storage object."""
    offenders: list[str] = []
    for node in ast.walk(ast.parse(source)):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "open"
        ):
            continue
        receiver = _dotted_name(node.func.value)
        if "storage" in receiver.lower():
            offenders.append(f"{receiver}.open (line {node.lineno})")
    return offenders


class TestNoRemoteStorageOpenInDrEngine:
    """``dr_engine`` streams remote objects; the spooling storage API is banned."""

    def test_detector_flags_storage_open_calls(self) -> None:
        """Positive control: the scan rejects the ``storage.open()`` call forms."""
        source = (
            "def probe(storage, S3Storage, destination):\n"
            "    storage.open('key', mode='rb')\n"
            "    S3Storage.open('key')\n"
            "    destination.open('wb')\n"
        )

        assert _storage_open_calls(source) == [
            "storage.open (line 2)",
            "S3Storage.open (line 3)",
        ]

    def test_dr_engine_sources_never_open_a_storage_object(self) -> None:
        package_root = Path(_remote.__file__).parent
        offenders: list[str] = []
        for path in sorted(package_root.rglob("*.py")):
            for offender in _storage_open_calls(path.read_text(encoding="utf-8")):
                offenders.append(f"{path.relative_to(package_root)}: {offender}")

        assert offenders == [], (
            "dr_engine must stream remote objects through the provider client; "
            f"storage.open() calls found: {offenders}"
        )
