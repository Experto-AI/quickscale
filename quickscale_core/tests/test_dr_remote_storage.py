"""Behavior tests for quickscale_core._dr_remote_storage.

Covers:
* ``upload_file_to_s3`` — file open/close, Django ``File`` wrapping, chunk
  consumption, key/options passthrough, exception propagation, no
  ``read_bytes()``/``read(-1)`` traps.
* ``delete_s3_key`` — construction, call, exception propagation.
* Lazy import proof — fresh subprocess confirms module-level imports do not
  require Django settings or the storages package.
"""

from __future__ import annotations

import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core._dr_remote_storage import (
    delete_s3_key,
    upload_file_to_s3,
)


# ---------------------------------------------------------------------------
# Autouse fixture — make S3Storage mockable without django-storages installed
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_s3storage() -> MagicMock:
    """Install a mock ``S3Storage`` so tests do not require django-storages."""
    # Ensure the module hierarchy exists so the function-local import resolves
    for mod_name in ("storages", "storages.backends", "storages.backends.s3"):
        if mod_name not in sys.modules:
            sys.modules[mod_name] = types.ModuleType(mod_name)
    s3_mod = sys.modules["storages.backends.s3"]
    if not hasattr(sys.modules.get("storages", None), "__path__"):
        sys.modules["storages"].__path__ = []  # type: ignore[attr-defined]
    if not hasattr(sys.modules.get("storages.backends", None), "__path__"):
        sys.modules["storages.backends"].__path__ = []  # type: ignore[attr-defined]

    # Directly set S3Storage as a module attribute so the function-local
    # ``from storages.backends.s3 import S3Storage`` resolves to our mock.
    original = getattr(s3_mod, "S3Storage", None)
    mock_cls = MagicMock()
    s3_mod.S3Storage = mock_cls  # type: ignore[attr-defined]

    yield mock_cls

    # Restore the original if there was one
    if original is not None:
        s3_mod.S3Storage = original  # type: ignore[attr-defined]
    else:
        del s3_mod.S3Storage


# ===================================================================
# upload_file_to_s3 — behavior, safety, edge cases
# ===================================================================


class TestUploadFileToS3:
    """``upload_file_to_s3`` behavior and contract enforcement."""

    # ------------------------------------------------------------------
    # Basic passthrough
    # ------------------------------------------------------------------

    def test_returns_requested_key(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """Returns ``requested_key`` unchanged, ignoring the backend return value."""
        local_path = tmp_path / "backup.dump"
        local_path.write_bytes(b"x" * 1024)
        mock_instance = MagicMock()
        mock_instance.save.return_value = "backend-returned-key"
        _patch_s3storage.return_value = mock_instance

        result = upload_file_to_s3(local_path, "my/custom/key", {"bucket": "b"})

        assert result == "my/custom/key"

    def test_passes_correct_key_and_options(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """``S3Storage`` is constructed from a copy of *storage_options*."""
        local_path = tmp_path / "backup.dump"
        local_path.write_bytes(b"content")
        mock_instance = MagicMock()
        _patch_s3storage.return_value = mock_instance

        upload_file_to_s3(
            local_path, "some/key", {"bucket": "b", "region": "us-east-1"}
        )

        _patch_s3storage.assert_called_once_with(bucket="b", region="us-east-1")
        mock_instance.save.assert_called_once()
        save_key = mock_instance.save.call_args[0][0]
        assert save_key == "some/key"

    def test_does_not_mutate_caller_options_dict(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """The caller's *storage_options* dict is not mutated."""
        local_path = tmp_path / "backup.dump"
        local_path.write_bytes(b"data")
        mock_instance = MagicMock()
        _patch_s3storage.return_value = mock_instance

        original: dict[str, object] = {"bucket": "b", "region": "us-east-1"}
        original_copy = dict(original)
        upload_file_to_s3(local_path, "key", original)
        assert original == original_copy, "caller dict was mutated"

    # ------------------------------------------------------------------
    # File handling
    # ------------------------------------------------------------------

    def test_opens_file_as_binary_read(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """File is opened in binary read mode and wrapped in Django ``File``."""
        local_path = tmp_path / "backup.dump"
        local_path.write_bytes(b"binary\x00data")
        mock_instance = MagicMock()

        # Verify inside the side_effect that the File handle is open during save
        file_was_open = False

        def _capture_save(key: str, django_file: object) -> str:
            nonlocal file_was_open
            from django.core.files import File

            assert isinstance(django_file, File)
            assert django_file.name == "backup.dump"
            file_was_open = not django_file.closed
            return "ok"

        mock_instance.save.side_effect = _capture_save
        _patch_s3storage.return_value = mock_instance

        upload_file_to_s3(local_path, "key", {"bucket": "b"})

        mock_instance.save.assert_called_once()
        assert file_was_open, (
            "File handle was already closed when storage.save() received it"
        )

    def test_multi_megabyte_file(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """A multi-MB file is uploaded without error (no full-buffer pattern)."""
        local_path = tmp_path / "large.dump"
        local_path.write_bytes(b"x" * (2 * 1024 * 1024 + 1))  # >2 MB
        mock_instance = MagicMock()
        _patch_s3storage.return_value = mock_instance

        result = upload_file_to_s3(local_path, "large/key", {"bucket": "b"})

        assert result == "large/key"
        mock_instance.save.assert_called_once()

    def test_file_content_via_chunks(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """The Django ``File.chunks()`` method correctly iterates the handle.

        This proves the adapter's ``File(handle, name=...)`` construction
        allows bounded chunk consumption without materialising the full
        file in memory.
        """
        content = b"hello\nworld\n" * 1000
        local_path = tmp_path / "content.dump"
        local_path.write_bytes(content)
        mock_instance = MagicMock()

        def _mock_save(key: str, django_file: object) -> str:
            from django.core.files import File as DjangoFile

            assert isinstance(django_file, DjangoFile)
            consumed = b"".join(django_file.chunks())
            assert consumed == content, "chunked content does not match source"
            return "saved"

        mock_instance.save.side_effect = _mock_save
        _patch_s3storage.return_value = mock_instance

        result = upload_file_to_s3(local_path, "content/key", {"bucket": "b"})
        assert result == "content/key"

    def test_no_read_bytes_or_read_all_trap(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """The adapter never calls ``read_bytes()`` or ``read(-1)`` on the handle.

        We verify by spying on both ``Path.read_bytes`` (flags if called)
        and the ``read()`` method of the opened file handle (flags
        unbounded ``read(-1)``). After the adapter runs, neither trap
        should have fired.
        """
        local_path = tmp_path / "safe.dump"
        local_path.write_bytes(b"data")
        mock_instance = MagicMock()

        original_open = Path.open
        unbounded_read_detected = False
        read_bytes_detected = False

        def _spying_open(self_ptr: Path, mode: str = "r") -> object:
            handle = original_open(self_ptr, mode)
            original_read = handle.read

            def _spy_read(size: int = -1) -> bytes:
                nonlocal unbounded_read_detected
                if size == -1:
                    unbounded_read_detected = True
                return original_read(size)

            handle.read = _spy_read  # type: ignore[method-assign]
            return handle

        original_read_bytes = Path.read_bytes

        def _spy_read_bytes(self_ptr: Path) -> bytes:
            nonlocal read_bytes_detected
            read_bytes_detected = True
            return original_read_bytes(self_ptr)

        with (
            patch.object(Path, "open", _spying_open),
            patch.object(Path, "read_bytes", _spy_read_bytes),
        ):
            _patch_s3storage.return_value = mock_instance
            upload_file_to_s3(local_path, "key", {"bucket": "b"})

        mock_instance.save.assert_called_once()
        assert not unbounded_read_detected, (
            "adapter called read(-1) on file handle — unbounded read detected"
        )
        assert not read_bytes_detected, (
            "adapter called Path.read_bytes() — use open() + chunks() instead"
        )

    # ------------------------------------------------------------------
    # Positive controls — trap mechanisms work when intentionally invoked
    # ------------------------------------------------------------------

    def test_read_bytes_trap_fires_when_invoked(self, tmp_path: Path) -> None:
        """Positive control: ``Path.read_bytes`` trap flags the forbidden call.

        If the adapter ever calls ``Path.read_bytes()``, the trap in
        ``test_no_read_bytes_or_read_all_trap`` would detect it.
        """
        local_path = tmp_path / "read_bytes_control.dump"
        local_path.write_bytes(b"data")

        read_bytes_detected = False
        original = Path.read_bytes

        def _spy(self_ptr: Path) -> bytes:
            nonlocal read_bytes_detected
            read_bytes_detected = True
            return original(self_ptr)

        with patch.object(Path, "read_bytes", _spy):
            _ = local_path.read_bytes()  # intentionally trigger

        assert read_bytes_detected, "read_bytes trap did not fire"

    def test_read_neg1_trap_fires_when_invoked(self, tmp_path: Path) -> None:
        """Positive control: ``read(-1)`` trap flags the unbounded call.

        If the adapter ever calls ``read(-1)`` on an open file handle,
        the trap in ``test_no_read_bytes_or_read_all_trap`` would detect it.
        """
        local_path = tmp_path / "read_neg1_control.dump"
        local_path.write_bytes(b"data")

        unbounded_detected = False
        original_open = Path.open

        def _spying_open(self_ptr: Path, mode: str = "r") -> object:
            handle = original_open(self_ptr, mode)
            original_read = handle.read

            def _spy_read(size: int = -1) -> bytes:
                nonlocal unbounded_detected
                if size == -1:
                    unbounded_detected = True
                return original_read(size)

            handle.read = _spy_read  # type: ignore[method-assign]
            return handle

        with patch.object(Path, "open", _spying_open):
            with local_path.open() as f:
                f.read(-1)  # intentionally unbounded

        assert unbounded_detected, "read(-1) trap did not fire"

    # ------------------------------------------------------------------
    # Exception propagation
    # ------------------------------------------------------------------

    def test_propagates_file_not_found(self, _patch_s3storage: MagicMock) -> None:
        """``FileNotFoundError`` from opening a missing file propagates unchanged."""
        missing = Path("/nonexistent/backup.dump")
        with pytest.raises(FileNotFoundError):
            upload_file_to_s3(missing, "key", {"bucket": "b"})

    def test_propagates_s3storage_constructor_error(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """``S3Storage`` constructor exception propagates unchanged (object identity)."""
        local_path = tmp_path / "x.dump"
        local_path.write_bytes(b"x")
        _patch_s3storage.side_effect = ValueError("bad config")

        with pytest.raises(ValueError, match="bad config"):
            upload_file_to_s3(local_path, "key", {"bucket": "b"})

    def test_propagates_save_error(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """``storage.save()`` exception propagates unchanged."""
        local_path = tmp_path / "x.dump"
        local_path.write_bytes(b"x")
        mock_instance = MagicMock()
        mock_instance.save.side_effect = RuntimeError("backend failure")
        _patch_s3storage.return_value = mock_instance

        with pytest.raises(RuntimeError, match="backend failure"):
            upload_file_to_s3(local_path, "key", {"bucket": "b"})

    def test_propagates_file_constructor_error(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """``File`` constructor exception propagates unchanged."""
        local_path = tmp_path / "x.dump"
        local_path.write_bytes(b"x")
        mock_instance = MagicMock()
        _patch_s3storage.return_value = mock_instance

        with patch(
            "django.core.files.File",
            side_effect=TypeError("file construction failed"),
        ):
            with pytest.raises(TypeError, match="file construction failed"):
                upload_file_to_s3(local_path, "key", {"bucket": "b"})

    # ------------------------------------------------------------------
    # Exception object identity — same exception object propagates
    # ------------------------------------------------------------------

    def test_exception_object_identity(
        self, tmp_path: Path, _patch_s3storage: MagicMock
    ) -> None:
        """The exact exception object raised by the backend propagates."""
        local_path = tmp_path / "x.dump"
        local_path.write_bytes(b"x")
        mock_instance = MagicMock()
        original_exc = RuntimeError("exact object")
        mock_instance.save.side_effect = original_exc
        _patch_s3storage.return_value = mock_instance

        with pytest.raises(RuntimeError) as exc_info:
            upload_file_to_s3(local_path, "key", {"bucket": "b"})
        assert exc_info.value is original_exc


# ===================================================================
# delete_s3_key — behavior, safety, edge cases
# ===================================================================


class TestDeleteS3Key:
    """``delete_s3_key`` behavior and contract enforcement."""

    def test_deletes_correct_key(self, _patch_s3storage: MagicMock) -> None:
        """``storage.delete()`` is called with the exact *requested_key*."""
        mock_instance = MagicMock()
        _patch_s3storage.return_value = mock_instance

        delete_s3_key("target/key", {"bucket": "b"})

        _patch_s3storage.assert_called_once_with(bucket="b")
        mock_instance.delete.assert_called_once_with("target/key")

    def test_does_not_mutate_caller_options(self, _patch_s3storage: MagicMock) -> None:
        """The caller's *storage_options* dict is not mutated."""
        mock_instance = MagicMock()
        _patch_s3storage.return_value = mock_instance

        original: dict[str, object] = {"bucket": "b", "region": "us-east-1"}
        original_copy = dict(original)
        delete_s3_key("key", original)
        assert original == original_copy, "caller dict was mutated"

    def test_propagates_constructor_error(self, _patch_s3storage: MagicMock) -> None:
        """``S3Storage`` constructor exception propagates unchanged."""
        _patch_s3storage.side_effect = ValueError("bad config")
        with pytest.raises(ValueError, match="bad config"):
            delete_s3_key("key", {"bucket": "b"})

    def test_propagates_delete_error(self, _patch_s3storage: MagicMock) -> None:
        """``storage.delete()`` exception propagates unchanged."""
        mock_instance = MagicMock()
        mock_instance.delete.side_effect = RuntimeError("delete failed")
        _patch_s3storage.return_value = mock_instance

        with pytest.raises(RuntimeError, match="delete failed"):
            delete_s3_key("key", {"bucket": "b"})

    def test_exception_object_identity(self, _patch_s3storage: MagicMock) -> None:
        """The exact exception object from the backend propagates."""
        mock_instance = MagicMock()
        original_exc = OSError("exact delete error")
        mock_instance.delete.side_effect = original_exc
        _patch_s3storage.return_value = mock_instance

        with pytest.raises(OSError) as exc_info:
            delete_s3_key("key", {"bucket": "b"})
        assert exc_info.value is original_exc

    def test_returns_none(self, _patch_s3storage: MagicMock) -> None:
        """``delete_s3_key`` returns ``None`` (no return value)."""
        mock_instance = MagicMock()
        _patch_s3storage.return_value = mock_instance

        result = delete_s3_key("key", {"bucket": "b"})
        assert result is None


# ===================================================================
# Lazy import proof — module-level imports do not require storages
# ===================================================================


class TestLazyImport:
    """Module-level import does not require the storages or Django settings."""

    def test_subprocess_no_django_settings(self) -> None:
        """A fresh Python subprocess can import the module without Django settings."""
        core_src = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src",
        )

        code_lines = [
            "import sys, os",
            "import inspect",
            "",
            f"_core_src = {core_src!r}",
            "if _core_src not in sys.path:",
            "    sys.path.insert(0, _core_src)",
            "",
            "os.environ.pop('DJANGO_SETTINGS_MODULE', None)",
            "",
            "# Module-level import must succeed without storages or Django settings",
            "from quickscale_core._dr_remote_storage import (",
            "    upload_file_to_s3,",
            "    delete_s3_key,",
            ")",
            "",
            "# Verify exact signatures",
            "sig = inspect.signature(upload_file_to_s3)",
            "params = list(sig.parameters.keys())",
            "assert params == ['local_path', 'requested_key', 'storage_options'], (",
            "    'Unexpected upload params: ' + str(params)",
            ")",
            "",
            "sig2 = inspect.signature(delete_s3_key)",
            "params2 = list(sig2.parameters.keys())",
            "assert params2 == ['requested_key', 'storage_options'], (",
            "    'Unexpected delete params: ' + str(params2)",
            ")",
            "",
            "# Verify no __all__ and no class exports",
            "import quickscale_core._dr_remote_storage as _mod",
            "assert not hasattr(_mod, '__all__'), 'Module should not export __all__'",
            "assert not hasattr(_mod, 'S3Storage'), 'Module should not re-export S3Storage'",
            "",
            "# Verify no classes defined at module level",
            "_classes = [",
            "    name for name, obj in inspect.getmembers(_mod)",
            "    if inspect.isclass(obj) and obj.__module__ == _mod.__name__",
            "]",
            "assert not _classes, 'Module defines unexpected classes: ' + str(_classes)",
            "",
            "print('ALL CHECKS PASSED')",
        ]
        code = "\n".join(code_lines)
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Subprocess failed (rc={result.returncode}):\n"
            f"stdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )
        assert "ALL CHECKS PASSED" in result.stdout
