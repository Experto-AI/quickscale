"""Tests for quickscale_core.runtime — SA9.3/SA9.4 public re-export facade.

Verifies that all expected symbols are importable through the facade and
that the ``__all__`` export list matches the declared re-export surface.
"""

from __future__ import annotations

from inspect import isclass, isfunction
from typing import Any

import pytest

from quickscale_core import runtime


# ===================================================================
# Re-export completeness
# ===================================================================


class TestRuntimeAllExport:
    """Verify that ``runtime.__all__`` matches the expected public surface."""

    def test_all_is_defined(self) -> None:
        assert hasattr(runtime, "__all__")
        assert isinstance(runtime.__all__, list)

    def test_all_contains_dr_adapter_functions(self) -> None:
        dr_symbols = {
            "ADAPTER_FUNCTIONS",
            "BackupError",
            "build_database_plan",
            "capture_snapshot",
            "execute_database_restore",
            "fetch_snapshot_report",
            "record_verification",
            "set_rollback_pin",
            "sync_media",
        }
        assert dr_symbols.issubset(runtime.__all__), (
            f"Missing DR symbols: {dr_symbols - set(runtime.__all__)}"
        )

    def test_all_contains_backup_orchestration_surface(self) -> None:
        backup_symbols = {
            "BackupLockError",
            "StagedAdminRestoreUpload",
            "build_backup_filename",
            "build_backup_snapshot_report",
            "clear_backup_snapshot_rollback_pin",
            "create_backup",
            "delete_artifact_files",
            "download_backup_path",
            "get_backup_snapshot",
            "get_local_backup_directory",
            "prune_expired_backups",
            "record_backup_snapshot_verification",
            "report_backup_snapshot",
            "restore_admin_uploaded_backup",
            "restore_backup_artifact",
            "restore_backup_source",
            "set_backup_snapshot_rollback_pin",
            "sync_backup_snapshot_media",
            "validate_backup_artifact",
            "BackupConfigurationError",
            "BackupPolicySnapshot",
            "ShellCommandRunner",
            "ArtifactLike",
            "BackupRestoreBlocked",
            "RemoteMaterializer",
            "ResolvedRestoreSource",
            "RestoreResult",
            "RestoreSourceResolutionMode",
            "RestoreWarning",
        }
        assert backup_symbols.issubset(runtime.__all__), (
            f"Missing backup symbols: {backup_symbols - set(runtime.__all__)}"
        )

    def test_all_contains_persistence_surface(self) -> None:
        """DR persistence surface symbols are in __all__."""
        persistence_symbols = {
            "BackupArtifactPersistence",
            "BackupPolicyPersistence",
            "PersistedBackupArtifact",
            "load_default_policy",
            "register_backup_persistence",
            "resolve_admin_uploaded_restore_artifact",
            "save_default_policy",
        }
        assert persistence_symbols.issubset(runtime.__all__), (
            f"Missing persistence symbols: {persistence_symbols - set(runtime.__all__)}"
        )

    def test_all_contains_social_surface(self) -> None:
        social_symbols = {
            "SOCIAL_EMBEDS_PATH",
            "SOCIAL_INTEGRATION_BASE_PATH",
            "SOCIAL_INTEGRATION_EMBEDS_PATH",
            "SOCIAL_LINK_TREE_PATH",
            "ModuleWiringSpec",
            "ResolverResult",
            "assemble_wiring_spec",
            "load_social_manifest",
            "render_social_managed_init_module",
            "render_social_managed_urls_module",
            "render_social_managed_views_module",
            "resolve_social_module_options",
            "social_provider_supports_embeds",
        }
        assert social_symbols.issubset(runtime.__all__), (
            f"Missing social symbols: {social_symbols - set(runtime.__all__)}"
        )

    def test_all_no_unexpected_symbols(self) -> None:
        """Each symbol in ``__all__`` is accounted for in the known surface.

        If this test fails, a new symbol was added to ``__all__`` without
        being listed in the test — update the test's expected set.
        """
        expected = {
            "ADAPTER_FUNCTIONS",
            "ArtifactLike",
            "BackupArtifactPersistence",
            "BackupConfigurationError",
            "BackupError",
            "BackupLockError",
            "BackupPolicyPersistence",
            "BackupPolicySnapshot",
            "BackupRestoreBlocked",
            "ModuleWiringSpec",
            "PersistedBackupArtifact",
            "RemoteMaterializer",
            "ResolverResult",
            "ResolvedRestoreSource",
            "RestoreResult",
            "RestoreSourceResolutionMode",
            "RestoreWarning",
            "SOCIAL_EMBEDS_PATH",
            "SOCIAL_INTEGRATION_BASE_PATH",
            "SOCIAL_INTEGRATION_EMBEDS_PATH",
            "SOCIAL_LINK_TREE_PATH",
            "ShellCommandRunner",
            "StagedAdminRestoreUpload",
            "_cleanup_admin_restore_upload_directory",
            "_resolve_admin_uploaded_restore_artifact",
            "_stage_admin_restore_upload",
            "assemble_wiring_spec",
            "build_backup_filename",
            "build_backup_snapshot_report",
            "build_database_plan",
            "capture_snapshot",
            "clear_backup_snapshot_rollback_pin",
            "create_backup",
            "delete_artifact_files",
            "download_backup_path",
            "execute_database_restore",
            "fetch_snapshot_report",
            "get_backup_snapshot",
            "get_local_backup_directory",
            "load_default_policy",
            "load_social_manifest",
            "prune_expired_backups",
            "record_backup_snapshot_verification",
            "record_verification",
            "register_backup_persistence",
            "render_social_managed_init_module",
            "render_social_managed_urls_module",
            "render_social_managed_views_module",
            "report_backup_snapshot",
            "resolve_admin_uploaded_restore_artifact",
            "resolve_social_module_options",
            "restore_admin_uploaded_backup",
            "restore_backup_artifact",
            "restore_backup_source",
            "save_default_policy",
            "set_backup_snapshot_rollback_pin",
            "set_rollback_pin",
            "social_provider_supports_embeds",
            "sync_backup_snapshot_media",
            "sync_media",
            "validate_backup_artifact",
        }
        actual = set(runtime.__all__)
        assert actual == expected, (
            f"Unexpected difference: added={actual - expected}, "
            f"missing={expected - actual}"
        )


# ===================================================================
# Individual symbol type checks
# ===================================================================


class TestRuntimeSymbolTypes:
    """Verify that each re-exported symbol is the correct type."""

    def test_backup_error_is_exception_class(self) -> None:
        assert isclass(runtime.BackupError)
        assert issubclass(runtime.BackupError, Exception)

    def test_adapter_functions_is_dict(self) -> None:
        assert isinstance(runtime.ADAPTER_FUNCTIONS, dict)

    def test_dr_functions_are_callable(self) -> None:
        for name in (
            "capture_snapshot",
            "fetch_snapshot_report",
            "record_verification",
            "set_rollback_pin",
            "build_database_plan",
            "execute_database_restore",
            "sync_media",
        ):
            symbol = getattr(runtime, name, None)
            assert symbol is not None, f"runtime.{name} is None"
            assert callable(symbol), f"runtime.{name} is not callable"

    def test_social_paths_are_strings(self) -> None:
        for name in (
            "SOCIAL_LINK_TREE_PATH",
            "SOCIAL_EMBEDS_PATH",
            "SOCIAL_INTEGRATION_BASE_PATH",
            "SOCIAL_INTEGRATION_EMBEDS_PATH",
        ):
            symbol = getattr(runtime, name)
            assert isinstance(symbol, str), f"runtime.{name} is not a string"

    def test_resolver_result_is_class(self) -> None:
        assert isclass(runtime.ResolverResult)

    def test_module_wiring_spec_is_class(self) -> None:
        assert isclass(runtime.ModuleWiringSpec)

    def test_assemble_wiring_spec_is_callable(self) -> None:
        assert callable(runtime.assemble_wiring_spec)

    def test_load_social_manifest_is_callable(self) -> None:
        assert callable(runtime.load_social_manifest)

    def test_render_functions_are_callable(self) -> None:
        for name in (
            "render_social_managed_init_module",
            "render_social_managed_urls_module",
            "render_social_managed_views_module",
        ):
            symbol = getattr(runtime, name, None)
            assert symbol is not None, f"runtime.{name} is None"
            assert callable(symbol), f"runtime.{name} is not callable"

    def test_social_provider_supports_embeds_is_function(self) -> None:
        assert isfunction(runtime.social_provider_supports_embeds)

    def test_resolve_social_module_options_is_callable(self) -> None:
        assert callable(runtime.resolve_social_module_options)

    # ------------------------------------------------------------------
    # Persistence surface types
    # ------------------------------------------------------------------

    def test_persistence_protocols_are_classes(self) -> None:
        for name in (
            "BackupArtifactPersistence",
            "BackupPolicyPersistence",
            "PersistedBackupArtifact",
        ):
            symbol = getattr(runtime, name, None)
            assert symbol is not None, f"runtime.{name} is None"
            assert isclass(symbol), f"runtime.{name} is not a class"

    def test_persistence_functions_are_callable(self) -> None:
        for name in (
            "load_default_policy",
            "register_backup_persistence",
            "resolve_admin_uploaded_restore_artifact",
            "save_default_policy",
        ):
            symbol = getattr(runtime, name, None)
            assert symbol is not None, f"runtime.{name} is None"
            assert callable(symbol), f"runtime.{name} is not callable"


# ===================================================================
# Importable-by-name verification
# ===================================================================


class TestRuntimeImportable:
    """Each symbol in ``__all__`` can be accessed by name from the facade."""

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "ADAPTER_FUNCTIONS",
            "BackupArtifactPersistence",
            "BackupError",
            "BackupPolicyPersistence",
            "ModuleWiringSpec",
            "PersistedBackupArtifact",
            "ResolverResult",
            "SOCIAL_EMBEDS_PATH",
            "SOCIAL_INTEGRATION_BASE_PATH",
            "SOCIAL_INTEGRATION_EMBEDS_PATH",
            "SOCIAL_LINK_TREE_PATH",
            "assemble_wiring_spec",
            "build_database_plan",
            "capture_snapshot",
            "execute_database_restore",
            "fetch_snapshot_report",
            "load_default_policy",
            "load_social_manifest",
            "record_verification",
            "register_backup_persistence",
            "render_social_managed_init_module",
            "render_social_managed_urls_module",
            "render_social_managed_views_module",
            "resolve_admin_uploaded_restore_artifact",
            "resolve_social_module_options",
            "save_default_policy",
            "set_rollback_pin",
            "social_provider_supports_embeds",
            "sync_media",
        ],
    )
    def test_symbol_accessible(self, symbol_name: str) -> None:
        assert hasattr(runtime, symbol_name), f"runtime.{symbol_name} is not accessible"
        assert getattr(runtime, symbol_name) is not None, (
            f"runtime.{symbol_name} is None"
        )


# ===================================================================
# dr sub-module — __getattr__ / __dir__
# ===================================================================


class TestRuntimeDrGetAttrDir:
    """Lazy-loading via dr.__getattr__ and dr.__dir__.

    Tests the ``__getattr__`` dispatcher in ``runtime.dr`` for orchestration,
    primitives, recovery, and verification sub-modules, plus the error path
    for unknown symbols.  All sub-modules are mocked to avoid Django/model
    dependencies.
    """

    @staticmethod
    def _mock_modules(
        orchestration: dict[str, Any] | None = None,
        primitives: dict[str, Any] | None = None,
        recovery: dict[str, Any] | None = None,
        verification: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Build a ``sys.modules`` dict patch with mock sub-modules."""
        from unittest.mock import MagicMock

        patches: dict[str, Any] = {}

        if orchestration is not None:
            m = MagicMock()
            for k, v in orchestration.items():
                setattr(m, k, v)
            patches["quickscale_core.dr_engine.orchestration"] = m
        if primitives is not None:
            m = MagicMock()
            for k, v in primitives.items():
                setattr(m, k, v)
            patches["quickscale_core.dr_engine.primitives"] = m
        if recovery is not None:
            m = MagicMock()
            for k, v in recovery.items():
                setattr(m, k, v)
            patches["quickscale_core.dr_engine.recovery"] = m
        if verification is not None:
            m = MagicMock()
            for k, v in verification.items():
                setattr(m, k, v)
            patches["quickscale_core.dr_engine.verification"] = m

        return patches

    def test_getattr_orchestration_symbol(self) -> None:
        from unittest.mock import patch

        from quickscale_core.runtime import dr as _dr

        patches = self._mock_modules(orchestration={"create_backup": "mock_fn"})
        with patch.dict("sys.modules", patches):
            result = _dr.__getattr__("create_backup")
        assert result == "mock_fn"

    def test_getattr_primitives_additional_symbol(self) -> None:
        """Primitives is Django-free; the real module should resolve."""
        from quickscale_core.runtime import dr as _dr

        result = _dr.__getattr__("BackupConfigurationError")
        from quickscale_core.dr_engine.primitives import BackupConfigurationError

        assert result is BackupConfigurationError

    def test_getattr_recovery_symbol(self) -> None:
        """Recovery symbols resolve to the real objects."""
        from quickscale_core.runtime import dr as _dr

        result = _dr.__getattr__("ArtifactLike")
        from quickscale_core.dr_engine.recovery import ArtifactLike

        assert result is ArtifactLike

    def test_getattr_verification_symbol(self) -> None:
        """Verification symbols resolve to the real objects."""
        from quickscale_core.runtime import dr as _dr

        result = _dr.__getattr__("_validate_verification_inputs")
        from quickscale_core.dr_engine.verification import (
            _validate_verification_inputs,
        )

        assert result is _validate_verification_inputs

    def test_getattr_persistence_symbol(self) -> None:
        """Persistence is Django-free; the real module should resolve."""
        from quickscale_core.runtime import dr as _dr

        result = _dr.__getattr__("register_backup_persistence")
        from quickscale_core.dr_engine.persistence import (
            register_backup_persistence,
        )

        assert result is register_backup_persistence

    def test_getattr_unknown_raises_attribute_error(self) -> None:
        from quickscale_core.runtime import dr as _dr

        try:
            _dr.__getattr__("nonexistent_symbol_xyz")
            assert False, "Expected AttributeError"
        except AttributeError:
            pass

    def test_dir_includes_all_exported_symbols(self) -> None:
        from quickscale_core.runtime import dr as _dr

        result = _dr.__dir__()
        assert result == sorted(_dr.__all__)
