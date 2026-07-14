"""Tests for backups module AppConfig.ready() persistence registration (SA89a Phase 2).

Covers:
* ``QuickscaleBackupsConfig.ready()`` registers module-level singleton
  provider instances with the core persistence seam.
* Re-registration of the same singletons is identity-idempotent.
* After ``ready()``, the public API functions delegate through the
  registered providers.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from quickscale_core.dr_engine.persistence import (
    _reset_backup_persistence_for_tests,
    load_default_policy,
    register_backup_persistence,
    resolve_admin_uploaded_restore_artifact,
    save_default_policy,
)
from quickscale_core.dr_engine.primitives import BackupConfigurationError


# ===================================================================
# Fixtures — clean persistence state per test
# ===================================================================


@pytest.fixture
def _reset_persistence_state() -> None:
    """Reset registered providers and restore after the test.

    Request this fixture in tests that need to control registration state
    independent of the bootstrap-ready registration.
    """
    # Reset providers so the test starts with clean state
    _reset_backup_persistence_for_tests()
    yield
    # Restore: re-register by calling ready() again.
    # This is safe because the providers are identity-idempotent.
    from django.apps import apps

    try:
        config = apps.get_app_config("quickscale_modules_backups")
    except LookupError:
        pass
    else:
        config.ready()


# ===================================================================
# ready() registration tests
# ===================================================================


class TestAppConfigReady:
    """Verify that ready() registers providers correctly."""

    def test_ready_registers_providers(
        self, db: None, _reset_persistence_state: None
    ) -> None:
        """ready() registers the persistence providers.

        Uses the app config from Django's registry (which already called
        ready() during setup).  The autouse ``_reset_persistence_state``
        clears state before each test, so we call ready() again to
        verify registration.
        """
        from django.apps import apps

        config = apps.get_app_config("quickscale_modules_backups")
        config.ready()

        # After ready(), the persistence getters should not raise.
        # Since there's no default policy row, load_default_policy will
        # return a settings-built snapshot, but it should not raise
        # BackupConfigurationError.
        snapshot = load_default_policy()
        assert snapshot is not None
        assert snapshot.retention_days > 0

    def test_ready_is_identity_idempotent(
        self, db: None, _reset_persistence_state: None
    ) -> None:
        """Calling ready() twice with the same config is a no-op."""
        from django.apps import apps

        config = apps.get_app_config("quickscale_modules_backups")
        config.ready()

        # Second call should not raise.
        config.ready()

        # Verify state is still valid.
        snapshot = load_default_policy()
        assert snapshot is not None

    def test_resolve_still_fails_when_no_artifact_persistence_configured(
        self, _reset_persistence_state: None
    ) -> None:
        """reset + no ready() → resolve raises BackupConfigurationError."""
        # Since _reset_persistence_state runs before this test, we
        # verify that without ready(), resolve raises.
        with pytest.raises(BackupConfigurationError, match="not configured"):
            resolve_admin_uploaded_restore_artifact(
                checksum_sha256="abc",
                size_bytes=100,
            )


# ===================================================================
# Registration identity checks (integration-level)
# ===================================================================


class TestRegistrationIdentity:
    """Identity-idempotent and conflict guards through runtime."""

    def test_register_twice_same_instances_is_idempotent(
        self, _reset_persistence_state: None
    ) -> None:
        """Re-registering same provider instances is a no-op."""
        from quickscale_modules_backups.persistence import (
            artifact_persistence,
            policy_persistence,
        )

        # First registration
        register_backup_persistence(artifact_persistence, policy_persistence)

        # Second registration with same instances
        register_backup_persistence(artifact_persistence, policy_persistence)

        # No exception — idempotent.

    def test_register_different_instances_raises(
        self, _reset_persistence_state: None
    ) -> None:
        """Re-registering with different instances fails hard."""
        from quickscale_modules_backups.persistence import (
            artifact_persistence,
            policy_persistence,
        )

        register_backup_persistence(artifact_persistence, policy_persistence)

        with pytest.raises(
            BackupConfigurationError,
            match="already configured with a different provider",
        ):
            register_backup_persistence(MagicMock(), MagicMock())

    def test_save_default_policy_works_after_registration(
        self, db: None, _reset_persistence_state: None
    ) -> None:
        """After registration, save_default_policy succeeds."""
        from quickscale_modules_backups.persistence import (
            artifact_persistence,
            policy_persistence,
        )
        from quickscale_core.dr_engine.primitives import BackupPolicySnapshot

        register_backup_persistence(artifact_persistence, policy_persistence)

        policy = BackupPolicySnapshot(
            retention_days=30,
            naming_prefix="test",
            target_mode="local",
            local_directory="/tmp/test",
            remote_bucket_name="",
            remote_prefix="",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 3 * * *",
        )
        save_default_policy(policy)
        # No exception means success.
