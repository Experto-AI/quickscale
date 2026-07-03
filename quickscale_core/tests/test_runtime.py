"""Tests for quickscale_core.runtime — SA9.3/SA9.4 public re-export facade.

Verifies that all expected symbols are importable through the facade and
that the ``__all__`` export list matches the declared re-export surface.
"""

from __future__ import annotations

from inspect import isclass, isfunction

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
            "BackupConfigurationError",
            "BackupError",
            "BackupLockError",
            "BackupPolicySnapshot",
            "BackupRestoreBlocked",
            "ModuleWiringSpec",
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
            "load_social_manifest",
            "prune_expired_backups",
            "record_backup_snapshot_verification",
            "record_verification",
            "render_social_managed_init_module",
            "render_social_managed_urls_module",
            "render_social_managed_views_module",
            "report_backup_snapshot",
            "resolve_social_module_options",
            "restore_admin_uploaded_backup",
            "restore_backup_artifact",
            "restore_backup_source",
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


# ===================================================================
# Importable-by-name verification
# ===================================================================


class TestRuntimeImportable:
    """Each symbol in ``__all__`` can be accessed by name from the facade."""

    @pytest.mark.parametrize(
        "symbol_name",
        [
            "ADAPTER_FUNCTIONS",
            "BackupError",
            "ModuleWiringSpec",
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
            "load_social_manifest",
            "record_verification",
            "render_social_managed_init_module",
            "render_social_managed_urls_module",
            "render_social_managed_views_module",
            "resolve_social_module_options",
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
