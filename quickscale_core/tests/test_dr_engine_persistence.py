"""Tests for quickscale_core.dr_engine.persistence — SA89a Phase 1 + SA89b Phase 1.

SA89a Phase 1 covers:
* ``register_backup_persistence`` — idempotent re-registration, different
  provider rejection.
* ``resolve_admin_uploaded_restore_artifact`` — delegation to registered
  artifact provider.
* ``load_default_policy`` — delegation to registered policy provider.
* ``save_default_policy`` — delegation to registered policy provider.
* Pre-registration error — calling a getter before registering raises
  ``BackupConfigurationError``.
* ``_reset_backup_persistence_for_tests`` — correctly resets module state.

SA89b Phase 1 covers:
* New delegator wrappers (get_backup_artifact, create_artifact, save_artifact,
  update_artifact_after_restore, iter_expired_unlinked_artifacts,
  get_authoritative_snapshot_for_artifact, get_backup_snapshot, create_snapshot,
  save_snapshot, refresh_snapshot, iter_expired_snapshots, has_any_policy,
  ensure_default_policy) — delegation and unregistered fail-hard.
* Argument identity between wrapper and provider.
* Not-found/exception parity.
* Reverse-snapshot absence.
* Iterator behavior.
* Re-registration identity and reset.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from quickscale_core.dr_engine.persistence import (
    _reset_backup_persistence_for_tests,
    create_artifact,
    create_snapshot,
    ensure_default_policy,
    get_authoritative_snapshot_for_artifact,
    get_backup_artifact,
    get_backup_snapshot,
    has_any_policy,
    iter_expired_snapshots,
    iter_expired_unlinked_artifacts,
    load_default_policy,
    refresh_snapshot,
    register_backup_persistence,
    resolve_admin_uploaded_restore_artifact,
    save_artifact,
    save_default_policy,
    save_snapshot,
    update_artifact_after_restore,
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


# ===================================================================
# SA89b Phase 1 — delegator wrappers and provider edge coverage
# ===================================================================


class TestSharedFixture:
    """Shared fixture for SA89b Phase 1 tests — registered mock providers."""

    @pytest.fixture
    def registered_providers(self) -> tuple[MagicMock, MagicMock]:
        artifact_prov = MagicMock()
        policy_prov = MagicMock()
        register_backup_persistence(artifact_prov, policy_prov)
        return (artifact_prov, policy_prov)


class TestSa89bUnregisteredFailHard(TestSharedFixture):
    """All SA89b Phase 1 methods raise BackupConfigurationError before registration."""

    def test_get_backup_artifact_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            get_backup_artifact(1)

    def test_create_artifact_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            create_artifact(filename="test")

    def test_save_artifact_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            save_artifact(MagicMock(), update_fields=["status"])

    def test_update_artifact_after_restore_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            update_artifact_after_restore(
                MagicMock(), restored_at=datetime.now(timezone.utc)
            )

    def test_iter_expired_unlinked_artifacts_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            for _ in iter_expired_unlinked_artifacts(datetime.now(timezone.utc)):
                pass

    def test_get_authoritative_snapshot_for_artifact_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            get_authoritative_snapshot_for_artifact(MagicMock())

    def test_get_backup_snapshot_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            get_backup_snapshot("snap-001")

    def test_create_snapshot_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            create_snapshot(snapshot_id="snap-001")

    def test_save_snapshot_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            save_snapshot(MagicMock(), update_fields=["status"])

    def test_refresh_snapshot_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            refresh_snapshot(MagicMock())

    def test_iter_expired_snapshots_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            for _ in iter_expired_snapshots(datetime.now(timezone.utc)):
                pass

    def test_has_any_policy_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            has_any_policy()

    def test_ensure_default_policy_unregistered(self) -> None:
        with pytest.raises(BackupConfigurationError, match="not configured"):
            ensure_default_policy()


class TestSa89bDelegation(TestSharedFixture):
    """Delegate identity — each wrapper forwards exact arguments to the provider."""

    def test_get_backup_artifact_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        result = get_backup_artifact(42)
        assert result is artifact_prov.get_backup_artifact.return_value
        artifact_prov.get_backup_artifact.assert_called_once_with(42)

    def test_create_artifact_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        result = create_artifact(filename="test.dump", size_bytes=1024)
        assert result is artifact_prov.create_artifact.return_value
        artifact_prov.create_artifact.assert_called_once_with(
            filename="test.dump", size_bytes=1024
        )

    def test_save_artifact_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        mock_art = MagicMock()
        save_artifact(mock_art, update_fields=["status", "updated_at"])
        artifact_prov.save_artifact.assert_called_once_with(
            mock_art, ["status", "updated_at"]
        )

    def test_update_artifact_after_restore_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        mock_art = MagicMock()
        restored_at = datetime.now(timezone.utc)
        result = update_artifact_after_restore(mock_art, restored_at=restored_at)
        assert result is artifact_prov.update_artifact_after_restore.return_value
        artifact_prov.update_artifact_after_restore.assert_called_once_with(
            mock_art, restored_at=restored_at
        )

    def test_iter_expired_unlinked_artifacts_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        list(iter_expired_unlinked_artifacts(cutoff))
        artifact_prov.iter_expired_unlinked_artifacts.assert_called_once_with(cutoff)

    def test_get_authoritative_snapshot_for_artifact_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        mock_art = MagicMock()
        result = get_authoritative_snapshot_for_artifact(mock_art)
        assert (
            result is artifact_prov.get_authoritative_snapshot_for_artifact.return_value
        )
        artifact_prov.get_authoritative_snapshot_for_artifact.assert_called_once_with(
            mock_art
        )

    def test_get_backup_snapshot_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        result = get_backup_snapshot("snap-abc")
        assert result is artifact_prov.get_backup_snapshot.return_value
        artifact_prov.get_backup_snapshot.assert_called_once_with("snap-abc")

    def test_create_snapshot_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        result = create_snapshot(snapshot_id="snap-001", status="pending")
        assert result is artifact_prov.create_snapshot.return_value
        artifact_prov.create_snapshot.assert_called_once_with(
            snapshot_id="snap-001", status="pending"
        )

    def test_save_snapshot_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        mock_snap = MagicMock()
        save_snapshot(mock_snap, update_fields=["status", "updated_at"])
        artifact_prov.save_snapshot.assert_called_once_with(
            mock_snap, ["status", "updated_at"]
        )

    def test_refresh_snapshot_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        mock_snap = MagicMock()
        refresh_snapshot(mock_snap)
        artifact_prov.refresh_snapshot.assert_called_once_with(mock_snap)

    def test_iter_expired_snapshots_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        artifact_prov, _ = registered_providers
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        list(iter_expired_snapshots(cutoff))
        artifact_prov.iter_expired_snapshots.assert_called_once_with(cutoff)

    def test_has_any_policy_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        _, policy_prov = registered_providers
        policy_prov.has_any_policy.return_value = True
        result = has_any_policy()
        assert result is True
        policy_prov.has_any_policy.assert_called_once_with()

    def test_ensure_default_policy_delegates(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        _, policy_prov = registered_providers
        mock_result = MagicMock()
        policy_prov.ensure_default_policy.return_value = mock_result
        result = ensure_default_policy()
        assert result is mock_result
        policy_prov.ensure_default_policy.assert_called_once_with()


class TestSa89bEdgeCases(TestSharedFixture):
    """Edge-case coverage for provider argument identity, iteration, and reset."""

    def test_registration_identity_re_register_same_is_idempotent(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        art, pol = registered_providers
        register_backup_persistence(art, pol)  # same instances — no error

    def test_registration_identity_different_raises(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        art, pol = registered_providers
        with pytest.raises(BackupConfigurationError, match="already configured"):
            register_backup_persistence(MagicMock(), MagicMock())

    def test_reset_clears_and_permits_re_register(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        _reset_backup_persistence_for_tests()
        fresh_art = MagicMock()
        fresh_pol = MagicMock()
        register_backup_persistence(fresh_art, fresh_pol)
        # After reset + re-register, delegation should work
        result = get_backup_artifact(99)
        assert result is fresh_art.get_backup_artifact.return_value

    def test_get_backup_artifact_not_found_exception(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        """Provider raises BackupError when artifact not found."""
        from quickscale_core.dr_engine.primitives import BackupError

        artifact_prov, _ = registered_providers
        artifact_prov.get_backup_artifact.side_effect = BackupError("not found: 42")
        with pytest.raises(BackupError, match="not found"):
            get_backup_artifact(42)

    def test_get_backup_snapshot_not_found_exception(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        """Provider raises BackupError when snapshot not found."""
        from quickscale_core.dr_engine.primitives import BackupError

        artifact_prov, _ = registered_providers
        artifact_prov.get_backup_snapshot.side_effect = BackupError(
            "not found: snap-001"
        )
        with pytest.raises(BackupError, match="not found"):
            get_backup_snapshot("snap-001")

    def test_get_authoritative_snapshot_absent_returns_none(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        """Reverse-snapshot absence returns None, does not raise."""
        artifact_prov, _ = registered_providers
        artifact_prov.get_authoritative_snapshot_for_artifact.return_value = None
        result = get_authoritative_snapshot_for_artifact(MagicMock())
        assert result is None

    def test_iter_expired_unlinked_artifacts_yields_provider_items(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        """Iterator forwards provider results."""
        artifact_prov, _ = registered_providers
        mock_item = MagicMock()
        artifact_prov.iter_expired_unlinked_artifacts.return_value = iter([mock_item])
        cutoff = datetime.now(timezone.utc) - timedelta(days=30)
        results = list(iter_expired_unlinked_artifacts(cutoff))
        assert results == [mock_item]

    def test_iter_expired_snapshots_yields_provider_items(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        """Iterator forwards provider results."""
        artifact_prov, _ = registered_providers
        mock_item = MagicMock()
        artifact_prov.iter_expired_snapshots.return_value = iter([mock_item])
        cutoff = datetime.now(timezone.utc) - timedelta(days=14)
        results = list(iter_expired_snapshots(cutoff))
        assert results == [mock_item]

    def test_update_artifact_after_restore_returns_warnings(
        self, registered_providers: tuple[MagicMock, MagicMock]
    ) -> None:
        """Provider can return empty or populated warnings tuple."""
        from quickscale_core.dr_engine.recovery import RestoreWarning

        artifact_prov, _ = registered_providers
        mock_art = MagicMock()
        sample_warning = RestoreWarning(code="test_warning", message="test", details={})
        artifact_prov.update_artifact_after_restore.return_value = (sample_warning,)
        restored_at = datetime.now(timezone.utc)
        result = update_artifact_after_restore(mock_art, restored_at=restored_at)
        assert result == (sample_warning,)
        # Also test empty case
        artifact_prov.update_artifact_after_restore.return_value = ()
        result_empty = update_artifact_after_restore(mock_art, restored_at=restored_at)
        assert result_empty == ()
