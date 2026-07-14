"""Tests for quickscale_core.dr_engine.persistence — SA89a Phase 1.

Covers:
* ``register_backup_persistence`` — idempotent re-registration, different
  provider rejection.
* ``resolve_admin_uploaded_restore_artifact`` — delegation to registered
  artifact provider.
* ``load_default_policy`` — delegation to registered policy provider.
* ``save_default_policy`` — delegation to registered policy provider.
* Pre-registration error — calling a getter before registering raises
  ``BackupConfigurationError``.
* ``_reset_backup_persistence_for_tests`` — correctly resets module state.

These tests are Django-free and run entirely with mock provider instances.
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
from quickscale_core.dr_engine.primitives import (
    BackupConfigurationError,
    BackupPolicySnapshot,
)


# ===================================================================
# Fixtures — fresh provider doubles per test
# ===================================================================


@pytest.fixture(autouse=True)
def _reset_persistence() -> None:
    """Ensure clean module state before each test.

    After the test completes, reset again so we don't leak state between
    tests.  Since the fixture is function-scoped and autouse, this runs
    before and after every test in this module.
    """
    _reset_backup_persistence_for_tests()
    yield
    _reset_backup_persistence_for_tests()


@pytest.fixture
def mock_artifact_provider() -> MagicMock:
    """Return a fresh MagicMock conforming to BackupArtifactPersistence."""
    provider = MagicMock()
    provider.resolve_admin_uploaded_restore_artifact.return_value = MagicMock(
        status="available",
        restore_started_at=None,
    )
    return provider


@pytest.fixture
def mock_policy_provider() -> MagicMock:
    """Return a fresh MagicMock conforming to BackupPolicyPersistence."""
    provider = MagicMock()
    provider.load_default_policy.return_value = BackupPolicySnapshot(
        retention_days=30,
        naming_prefix="test",
        target_mode="local",
        local_directory="/tmp/backups",
        remote_bucket_name="",
        remote_prefix="",
        remote_endpoint_url="",
        remote_region_name="",
        remote_access_key_id_env_var="",
        remote_secret_access_key_env_var="",
        automation_enabled=False,
        schedule="0 3 * * *",
    )
    return provider


# ===================================================================
# Registration lifecycle
# ===================================================================


class TestRegisterBackupPersistence:
    """register_backup_persistence — atomic registration and guards."""

    def test_register_initial_providers(self) -> None:
        """Registering fresh providers stores them successfully."""
        artifact_prov = MagicMock()
        policy_prov = MagicMock()

        register_backup_persistence(artifact_prov, policy_prov)
        # No exception means success; subsequent delegation verifies storage.

    def test_resolve_artifact_delegates_to_registered_provider(
        self,
        mock_artifact_provider: MagicMock,
        mock_policy_provider: MagicMock,
    ) -> None:
        """resolve_admin_uploaded_restore_artifact delegates to the provider."""
        register_backup_persistence(mock_artifact_provider, mock_policy_provider)

        result = resolve_admin_uploaded_restore_artifact(
            checksum_sha256="abc123",
            size_bytes=4096,
        )

        assert (
            result
            is mock_artifact_provider.resolve_admin_uploaded_restore_artifact.return_value
        )
        mock_artifact_provider.resolve_admin_uploaded_restore_artifact.assert_called_once_with(
            checksum_sha256="abc123",
            size_bytes=4096,
        )

    def test_load_default_policy_delegates_to_registered_provider(
        self,
        mock_artifact_provider: MagicMock,
        mock_policy_provider: MagicMock,
    ) -> None:
        """load_default_policy delegates to the policy provider."""
        register_backup_persistence(mock_artifact_provider, mock_policy_provider)

        result = load_default_policy()

        assert result is mock_policy_provider.load_default_policy.return_value
        mock_policy_provider.load_default_policy.assert_called_once_with()

    def test_save_default_policy_delegates_to_registered_provider(
        self,
        mock_artifact_provider: MagicMock,
        mock_policy_provider: MagicMock,
    ) -> None:
        """save_default_policy delegates to the policy provider."""
        register_backup_persistence(mock_artifact_provider, mock_policy_provider)

        policy = BackupPolicySnapshot(
            retention_days=60,
            naming_prefix="test",
            target_mode="remote",
            local_directory="/tmp/backups",
            remote_bucket_name="my-bucket",
            remote_prefix="backups/",
            remote_endpoint_url="https://s3.amazonaws.com",
            remote_region_name="us-east-1",
            remote_access_key_id_env_var="AWS_ACCESS_KEY_ID",
            remote_secret_access_key_env_var="AWS_SECRET_ACCESS_KEY",
            automation_enabled=True,
            schedule="0 2 * * *",
        )
        save_default_policy(policy)

        mock_policy_provider.save_default_policy.assert_called_once_with(policy)

    def test_re_registration_with_same_instances_is_idempotent(
        self,
        mock_artifact_provider: MagicMock,
        mock_policy_provider: MagicMock,
    ) -> None:
        """Re-registering the exact same provider instances is a no-op."""
        register_backup_persistence(mock_artifact_provider, mock_policy_provider)
        register_backup_persistence(mock_artifact_provider, mock_policy_provider)
        # No exception — idempotent.

    def test_re_registration_with_different_instances_raises(
        self,
        mock_artifact_provider: MagicMock,
    ) -> None:
        """Re-registering with different provider instances raises."""
        register_backup_persistence(mock_artifact_provider, MagicMock())

        with pytest.raises(BackupConfigurationError, match="already configured"):
            register_backup_persistence(MagicMock(), MagicMock())

    def test_resolve_without_registration_raises(self) -> None:
        """Calling resolve before registering raises BackupConfigurationError."""
        with pytest.raises(BackupConfigurationError, match="not configured"):
            resolve_admin_uploaded_restore_artifact(
                checksum_sha256="abc",
                size_bytes=100,
            )

    def test_load_policy_without_registration_raises(self) -> None:
        """Calling load_default_policy before registering raises."""
        with pytest.raises(BackupConfigurationError, match="not configured"):
            load_default_policy()

    def test_save_policy_without_registration_raises(self) -> None:
        """Calling save_default_policy before registering raises."""
        policy = BackupPolicySnapshot(
            retention_days=30,
            naming_prefix="test",
            target_mode="local",
            local_directory="/tmp/backups",
            remote_bucket_name="",
            remote_prefix="",
            remote_endpoint_url="",
            remote_region_name="",
            remote_access_key_id_env_var="",
            remote_secret_access_key_env_var="",
            automation_enabled=False,
            schedule="0 3 * * *",
        )
        with pytest.raises(BackupConfigurationError, match="not configured"):
            save_default_policy(policy)
