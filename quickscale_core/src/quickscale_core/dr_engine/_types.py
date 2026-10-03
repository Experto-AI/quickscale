"""Shared protocols and constants for DR orchestration."""

from __future__ import annotations


from pathlib import Path
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from typing import Any
from typing import Protocol


_ROUTE_KIND_KEY = "ROUTE_KIND"


class _RemoteUploader(Protocol):
    """Protocol used for optional private remote artifact offload."""

    def __call__(self, local_path: Path, policy: BackupPolicySnapshot) -> str: ...


class _RemoteDeleter(Protocol):
    """Protocol used for private remote artifact deletion."""

    def __call__(self, remote_key: str, policy: BackupPolicySnapshot) -> None: ...


class _StorageBackendSelectionLike(Protocol):
    """Typed shape used from the storage helper module."""

    backend: str
    django_backend: str
    use_s3_compatible: bool
    options: dict[str, Any]


class _StorageHelpersModule(Protocol):
    """Typed subset of storage's public service surface used by backups."""

    def list_s3_compatible_media_inventory(
        self,
        settings_obj: Any,
    ) -> list[dict[str, Any]]: ...

    def select_storage_backend(
        self,
        settings_obj: Any,
    ) -> _StorageBackendSelectionLike: ...
