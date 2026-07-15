"""Tests for quickscale_core.runtime — SA89b Phase 2 public re-export surface.

Verifies that all expected symbols are importable through the facade, that
the ``__all__`` export list matches the declared re-export surface, and that
the eagerly-imported DR surface satisfies the Caller-Parity Pass contract.
"""

from __future__ import annotations

from inspect import isclass, isfunction

import pytest

from quickscale_core import runtime
from quickscale_core.runtime import dr as runtime_dr


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
            "PersistedBackupPolicy",
            "PersistedBackupSnapshot",
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
            "_get_authoritative_snapshot_for_artifact",
            "_resolve_admin_uploaded_restore_artifact",
            "_stage_admin_restore_upload",
            "assemble_wiring_spec",
            "build_backup_filename",
            "build_backup_snapshot_report",
            "build_database_plan",
            "capture_snapshot",
            "clear_backup_snapshot_rollback_pin",
            "create_artifact",
            "create_backup",
            "create_snapshot",
            "delete_artifact_files",
            "download_backup_path",
            "ensure_default_policy",
            "execute_database_restore",
            "fetch_snapshot_report",
            "get_backup_artifact",
            "get_backup_snapshot",
            "get_authoritative_snapshot_for_artifact",
            "get_local_backup_directory",
            "has_any_policy",
            "iter_expired_snapshots",
            "iter_expired_unlinked_artifacts",
            "load_default_policy",
            "load_social_manifest",
            "prune_expired_backups",
            "refresh_snapshot",
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
            "save_artifact",
            "save_default_policy",
            "save_snapshot",
            "set_backup_snapshot_rollback_pin",
            "set_rollback_pin",
            "social_provider_supports_embeds",
            "sync_backup_snapshot_media",
            "sync_media",
            "update_artifact_after_restore",
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
            "iter_expired_snapshots",
            "iter_expired_unlinked_artifacts",
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
# dr sub-module — eager import surface / __dir__
# ===================================================================


class TestRuntimeDrEagerSurface:
    """SA89b Phase 2: dr sub-module uses direct eager imports — not lazy
    ``__getattr__``.

    All formerly-lazy symbols are now module-level names in
    ``runtime.dr`` via direct ``from X import Y`` statements.
    """

    def test_orchestration_symbols_are_module_attributes(self) -> None:
        """Key orchestration symbols exist as direct module attributes on dr."""
        for name in (
            "BackupLockError",
            "StagedAdminRestoreUpload",
            "create_backup",
            "build_backup_filename",
            "delete_artifact_files",
            "prune_expired_backups",
            "restore_backup_artifact",
            "restore_admin_uploaded_backup",
            "validate_backup_artifact",
        ):
            assert hasattr(runtime_dr, name), (
                f"runtime_dr.{name} is not a module attribute"
            )

    def test_primitives_symbols_are_module_attributes(self) -> None:
        for name in (
            "BackupConfigurationError",
            "BackupPolicySnapshot",
            "ShellCommandRunner",
        ):
            assert hasattr(runtime_dr, name), (
                f"runtime_dr.{name} is not a module attribute"
            )

    def test_recovery_symbols_are_module_attributes(self) -> None:
        for name in (
            "ArtifactLike",
            "BackupRestoreBlocked",
            "RemoteMaterializer",
            "ResolvedRestoreSource",
            "RestoreResult",
            "RestoreSourceResolutionMode",
            "RestoreWarning",
        ):
            assert hasattr(runtime_dr, name), (
                f"runtime_dr.{name} is not a module attribute"
            )

    def test_persistence_symbols_are_module_attributes(self) -> None:
        for name in (
            "BackupArtifactPersistence",
            "BackupPolicyPersistence",
            "PersistedBackupArtifact",
            "load_default_policy",
            "register_backup_persistence",
            "save_default_policy",
        ):
            assert hasattr(runtime_dr, name), (
                f"runtime_dr.{name} is not a module attribute"
            )

    def test_verification_symbols_are_module_attributes(self) -> None:
        for name in (
            "_build_clear_rollback_pin_fields",
            "_build_verification_payload",
            "_compute_rollback_pin_fields",
            "_validate_verification_inputs",
        ):
            assert hasattr(runtime_dr, name), (
                f"runtime_dr.{name} is not a module attribute"
            )

    def test_unknown_symbol_raises_attribute_error_on_module(self) -> None:
        with pytest.raises(AttributeError):
            _ = runtime_dr.nonexistent_symbol_xyz_789

    def test_dir_includes_all_exported_symbols(self) -> None:
        result = runtime_dr.__dir__()
        assert result == sorted(runtime_dr.__all__)


# ===================================================================
# SA89b Phase 2 — Caller-Parity Pass
# ===================================================================


class TestCallerParityPassEagerSurface:
    """Complete caller-parity verification that every eagerly-imported symbol
    satisfies its public contract:

    * Canonical identity: each dr- or runtime-exported symbol **is** the
      same object as the canonical definition in the engine sub-module.
    * ``from ... import`` works for all public and private symbols.
    * ``getattr`` / ``hasattr`` works through ``runtime.__getattr__``
      delegation.
    * ``dir()`` includes all exported symbols.
    * ``AttributeError`` is raised for unknown names.
    * The registration seam ``register_backup_persistence`` accepts the
      ``(artifacts, policies)`` signature.
    """

    # ------------------------------------------------------------------
    # Section 1: Canonical identity — every runtime.dr public name matches
    # its engine sub-module definition.
    # ------------------------------------------------------------------

    @pytest.mark.parametrize(
        "name, canonical_module",
        [
            # Orchestration
            ("BackupLockError", "quickscale_core.dr_engine.orchestration"),
            ("StagedAdminRestoreUpload", "quickscale_core.dr_engine.orchestration"),
            ("build_backup_filename", "quickscale_core.dr_engine.orchestration"),
            ("build_backup_snapshot_report", "quickscale_core.dr_engine.orchestration"),
            ("create_backup", "quickscale_core.dr_engine.orchestration"),
            ("delete_artifact_files", "quickscale_core.dr_engine.orchestration"),
            ("download_backup_path", "quickscale_core.dr_engine.orchestration"),
            ("get_backup_snapshot", "quickscale_core.dr_engine.orchestration"),
            ("get_local_backup_directory", "quickscale_core.dr_engine.orchestration"),
            ("prune_expired_backups", "quickscale_core.dr_engine.orchestration"),
            (
                "record_backup_snapshot_verification",
                "quickscale_core.dr_engine.orchestration",
            ),
            ("report_backup_snapshot", "quickscale_core.dr_engine.orchestration"),
            (
                "restore_admin_uploaded_backup",
                "quickscale_core.dr_engine.orchestration",
            ),
            ("restore_backup_artifact", "quickscale_core.dr_engine.orchestration"),
            ("restore_backup_source", "quickscale_core.dr_engine.orchestration"),
            (
                "set_backup_snapshot_rollback_pin",
                "quickscale_core.dr_engine.orchestration",
            ),
            ("sync_backup_snapshot_media", "quickscale_core.dr_engine.orchestration"),
            ("validate_backup_artifact", "quickscale_core.dr_engine.orchestration"),
            # Primitives
            ("BackupConfigurationError", "quickscale_core.dr_engine.primitives"),
            ("BackupPolicySnapshot", "quickscale_core.dr_engine.primitives"),
            ("ShellCommandRunner", "quickscale_core.dr_engine.primitives"),
            # Recovery
            ("ArtifactLike", "quickscale_core.dr_engine.recovery"),
            ("BackupRestoreBlocked", "quickscale_core.dr_engine.recovery"),
            ("RemoteMaterializer", "quickscale_core.dr_engine.recovery"),
            ("ResolvedRestoreSource", "quickscale_core.dr_engine.recovery"),
            ("RestoreResult", "quickscale_core.dr_engine.recovery"),
            ("RestoreSourceResolutionMode", "quickscale_core.dr_engine.recovery"),
            ("RestoreWarning", "quickscale_core.dr_engine.recovery"),
            # Persistence
            ("BackupArtifactPersistence", "quickscale_core.dr_engine.persistence"),
            ("BackupPolicyPersistence", "quickscale_core.dr_engine.persistence"),
            ("PersistedBackupArtifact", "quickscale_core.dr_engine.persistence"),
            ("load_default_policy", "quickscale_core.dr_engine.persistence"),
            ("register_backup_persistence", "quickscale_core.dr_engine.persistence"),
            ("save_default_policy", "quickscale_core.dr_engine.persistence"),
        ],
    )
    def test_canonical_identity_dr(self, name: str, canonical_module: str) -> None:
        """Symbol exported from runtime.dr **is** the same object as the
        canonical definition in the engine sub-module."""
        import importlib

        canonical = importlib.import_module(canonical_module)
        canonical_obj = getattr(canonical, name)

        dr_obj = getattr(runtime_dr, name)
        assert dr_obj is canonical_obj, (
            f"runtime_dr.{name} is not the same object as {canonical_module}.{name}"
        )

    # ------------------------------------------------------------------
    # Section 2: Root runtime identity — every DR export from
    # ``runtime`` **is** the same object as ``runtime.dr.<name>``.
    # ------------------------------------------------------------------

    def test_runtime_delegates_to_dr(self) -> None:
        """For a representative sample of DR symbols, runtime.<name>
        returns the same object as runtime.dr.<name>."""
        sample = [
            "BackupLockError",
            "BackupConfigurationError",
            "ArtifactLike",
            "BackupArtifactPersistence",
            "create_backup",
            "register_backup_persistence",
            "save_default_policy",
        ]
        for name in sample:
            dr_obj = getattr(runtime_dr, name)
            rt_obj = getattr(runtime, name)
            assert rt_obj is dr_obj, f"runtime.{name} is not runtime.dr.{name}"

    # ------------------------------------------------------------------
    # Section 3: ``from ... import`` works for public and private symbols.
    # ------------------------------------------------------------------

    def test_from_import_public_symbol(self) -> None:
        """from quickscale_core.runtime.dr import <public> works."""
        from quickscale_core.runtime.dr import (
            BackupLockError,
            create_backup,
            register_backup_persistence,
            save_default_policy,
        )

        assert BackupLockError is runtime_dr.BackupLockError
        assert create_backup is runtime_dr.create_backup
        assert register_backup_persistence is runtime_dr.register_backup_persistence
        assert save_default_policy is runtime_dr.save_default_policy

    def test_from_import_private_symbol(self) -> None:
        """from quickscale_core.runtime.dr import <private> works."""
        from quickscale_core.runtime.dr import (
            _build_env_var_manifest,
            _cleanup_admin_restore_upload_directory,
            _compute_sha256,
            _validate_verification_inputs,
        )

        assert _build_env_var_manifest is runtime_dr._build_env_var_manifest
        assert (
            _cleanup_admin_restore_upload_directory
            is runtime_dr._cleanup_admin_restore_upload_directory
        )
        assert _compute_sha256 is runtime_dr._compute_sha256
        assert _validate_verification_inputs is runtime_dr._validate_verification_inputs

    def test_from_import_private_symbol_from_runtime_facade(self) -> None:
        """from quickscale_core.runtime import <private> works through
        runtime.__getattr__ delegation."""
        from quickscale_core.runtime import (
            _build_env_var_manifest,
            _cleanup_admin_restore_upload_directory,
            _compute_sha256,
        )

        assert _build_env_var_manifest is runtime_dr._build_env_var_manifest
        assert (
            _cleanup_admin_restore_upload_directory
            is runtime_dr._cleanup_admin_restore_upload_directory
        )
        assert _compute_sha256 is runtime_dr._compute_sha256

    # ------------------------------------------------------------------
    # Section 4: ``getattr`` / ``hasattr`` through runtime delegation.
    # ------------------------------------------------------------------

    def test_getattr_public_symbols_via_runtime(self) -> None:
        for name in runtime_dr.__all__:
            assert hasattr(runtime, name), f"runtime has no attribute {name}"
            obj = getattr(runtime, name)
            assert obj is not None

    def test_getattr_unknown_raises_attribute_error(self) -> None:
        with pytest.raises(AttributeError):
            _ = runtime.nonexistent_symbol_xyz_789

    # ------------------------------------------------------------------
    # Section 5: ``dir()`` behavior.
    # ------------------------------------------------------------------

    def test_runtime_dir_includes_all_exported_symbols(self) -> None:
        result = runtime.__dir__()
        assert sorted(result) == sorted(runtime.__all__)

    def test_dr_dir_includes_all_exported_symbols(self) -> None:
        result = runtime_dr.__dir__()
        assert sorted(result) == sorted(runtime_dr.__all__)

    # ------------------------------------------------------------------
    # Section 6: ``register_backup_persistence`` accepts the
    # ``(artifacts, policies)`` signature — verifiable by introspection.
    # ------------------------------------------------------------------

    def test_register_backup_persistence_signature(self) -> None:
        """register_backup_persistence accepts (artifacts, policies)."""
        import inspect

        sig = inspect.signature(runtime_dr.register_backup_persistence)
        param_names = list(sig.parameters.keys())
        assert param_names == ["artifacts", "policies"], (
            f"Expected parameters (artifacts, policies), got {param_names}"
        )

    # ------------------------------------------------------------------
    # Section 7: Fresh subprocess proves eager imports do not require
    # the backups module.  Runs a subprocess with DJANGO_SETTINGS_MODULE
    # cleared and the backups source tree blocked, then imports a
    # representative subset of the DR runtime surface.
    # ------------------------------------------------------------------

    def test_subprocess_blocking_backups_module(self) -> None:
        """A fresh Python subprocess that cannot import
        quickscale_modules_backups can still import and access
        representative DR surface symbols.

        The subprocess clears DJANGO_SETTINGS_MODULE, prepends the
        workspace source directories for core, and blocks the backups
        module source to prove seam-level imports (orchestration,
        recovery, persistence, primitives, verification) do not require
        Django settings or the backups module at import time.
        """
        import os
        import subprocess
        import sys

        # Locate the workspace source directories for the subprocess
        core_src = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "src",
        )
        workspace_root = os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        modules_src = os.path.join(
            workspace_root, "quickscale_modules", "backups", "src"
        )

        code = (
            "import sys\n"
            "import os\n"
            "\n"
            f"_core_src = {core_src!r}\n"
            "if _core_src not in sys.path:\n"
            "    sys.path.insert(0, _core_src)\n"
            "\n"
            "sys.path = [p for p in sys.path if 'quickscale_modules_backups' not in p]\n"
            "\n"
            f"_backups_src = {modules_src!r}\n"
            "if _backups_src in sys.path:\n"
            "    sys.path.remove(_backups_src)\n"
            "sys.path = [p for p in sys.path if 'quickscale_modules' not in p or 'backups' not in p]\n"
            "\n"
            "os.environ.pop('DJANGO_SETTINGS_MODULE', None)\n"
            "\n"
            "from quickscale_core.runtime.dr import (\n"
            "    BackupConfigurationError,\n"
            "    BackupPolicySnapshot,\n"
            "    ShellCommandRunner,\n"
            "    ArtifactLike,\n"
            "    BackupRestoreBlocked,\n"
            "    RemoteMaterializer,\n"
            "    ResolvedRestoreSource,\n"
            "    RestoreResult,\n"
            "    RestoreSourceResolutionMode,\n"
            "    RestoreWarning,\n"
            "    BackupArtifactPersistence,\n"
            "    BackupPolicyPersistence,\n"
            "    PersistedBackupArtifact,\n"
            "    load_default_policy,\n"
            "    register_backup_persistence,\n"
            "    save_default_policy,\n"
            "    _build_clear_rollback_pin_fields,\n"
            "    _build_verification_payload,\n"
            "    _compute_rollback_pin_fields,\n"
            "    _validate_verification_inputs,\n"
            ")\n"
            "\n"
            "from quickscale_core.dr_engine.primitives import (\n"
            "    BackupConfigurationError as _canon_bc,\n"
            ")\n"
            "assert BackupConfigurationError is _canon_bc\n"
            "\n"
            "from quickscale_core.dr_engine.recovery import (\n"
            "    ArtifactLike as _canon_al,\n"
            ")\n"
            "assert ArtifactLike is _canon_al\n"
            "\n"
            "from quickscale_core.dr_engine.persistence import (\n"
            "    BackupArtifactPersistence as _canon_bap,\n"
            ")\n"
            "assert BackupArtifactPersistence is _canon_bap\n"
            "\n"
            "from quickscale_core.dr_engine.verification import (\n"
            "    _validate_verification_inputs as _canon_vvi,\n"
            ")\n"
            "assert _validate_verification_inputs is _canon_vvi\n"
            "\n"
            "import inspect\n"
            "sig = inspect.signature(register_backup_persistence)\n"
            "assert list(sig.parameters.keys()) == ['artifacts', 'policies']\n"
            "\n"
            "print('ALL CHECKS PASSED')\n"
        )
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
        assert "ALL CHECKS PASSED" in result.stdout, (
            f"Not all checks passed: {result.stdout}"
        )

    # ------------------------------------------------------------------
    # Section 8: Verify every symbol imported by services.py lines 20-128
    # is accessible through the facade.
    # ------------------------------------------------------------------

    def test_services_imports_accessible_via_runtime(self) -> None:
        """Every symbol imported by services.py lines 20-128 is accessible
        via quickscale_core.runtime."""
        # These are the complete set of imports from services.py lines 20-128
        services_imports = [
            "_DEFAULT_REMOTE_ACCESS_KEY_ID_ENV_VAR",
            "_DEFAULT_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
            "_ENV_VAR_MANIFEST_FILENAME",
            "_MEDIA_SYNC_MANIFEST_FILENAME",
            "_PROMOTION_VERIFICATION_FILENAME",
            "_RELEASE_METADATA_FILENAME",
            "_REQUIRED_POSTGRESQL_MAJOR",
            "_REQUIRED_SNAPSHOT_SIDECAR_FILENAMES",
            "_SNAPSHOT_DATABASE_DIRECTORY_NAME",
            "_SNAPSHOTS_DIRECTORY_NAME",
            "ArtifactLike",
            "BackupConfigurationError",
            "BackupError",
            "BackupLockError",
            "BackupPolicySnapshot",
            "BackupRestoreBlocked",
            "RemoteMaterializer",
            "ResolvedRestoreSource",
            "RestoreResult",
            "RestoreSourceResolutionMode",
            "RestoreWarning",
            "ShellCommandRunner",
            "StagedAdminRestoreUpload",
            "_build_clear_rollback_pin_fields",
            "_build_env_var_manifest",
            "_build_media_sync_manifest",
            "_build_pg_dump_command",
            "_build_pg_restore_command",
            "_build_policy_snapshot_from_model",
            "_build_policy_snapshot_from_settings",
            "_build_release_metadata",
            "_build_snapshot_child_descriptor",
            "_build_snapshot_full_backup_contract",
            "_build_snapshot_local_root",
            "_build_snapshot_remote_root",
            "_build_verification_payload",
            "_cleanup_admin_restore_upload_directory",
            "_cleanup_local_backup_file",
            "_clear_appended_artifact_note",
            "_collect_local_backup_validation_issues",
            "_collect_module_versions",
            "_compute_rollback_pin_fields",
            "_compute_sha256",
            "_database_engine_family",
            "_database_server_version_query",
            "_delete_private_remote_key",
            "_detect_restore_file_format",
            "_dump_postgresql_database",
            "_ensure_operator_supplied_custom_archive_valid",
            "_ensure_postgresql_18_restore_runtime",
            "_execute_restore_for_resolved_source",
            "_expected_backup_format_for_engine",
            "_extract_any_major_version",
            "_extract_leading_major_version",
            "_get_git_revision",
            "_get_postgresql_tool_version",
            "_get_project_slug",
            "_get_restore_compatibility_issues",
            "_get_restore_source_compatibility_issues",
            "_get_restore_source_validation_issues",
            "_get_source_environment",
            "_is_path_within_root",
            "_load_snapshot_sidecar_payload",
            "_materialize_private_remote_key",
            "_mint_snapshot_id",
            "_normalize_restore_file_path",
            "_path_uses_symlink_within_root",
            "_postgresql_18_client_tooling_guidance",
            "_read_setting_value",
            "_record_prune_failure_without_masking_success",
            "_relative_snapshot_child_path",
            "_release_backup_lock",
            "_replace_policy_remote_prefix",
            "_resolve_admin_uploaded_restore_artifact",
            "_resolve_private_remote_credentials",
            "_resolve_restore_source",
            "_restore_execution_allowed",
            "_rollback_remote_upload_after_persistence_failure",
            "_run_shell_command",
            "_snapshot_sidecar_path",
            "_stage_admin_restore_upload",
            "_upload_to_private_remote",
            "_validate_policy_snapshot_internal",
            "_validate_verification_inputs",
            "_write_json_file",
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
        ]
        for name in services_imports:
            assert hasattr(runtime, name), (
                f"runtime.{name} is not accessible — services.py imports it"
            )
            rt_obj = getattr(runtime, name)
            assert rt_obj is not None, f"runtime.{name} is None"
            # Verify delegation: runtime.<name> is runtime.dr.<name>
            dr_obj = getattr(runtime_dr, name)
            assert rt_obj is dr_obj, f"runtime.{name} is not runtime.dr.{name}"
