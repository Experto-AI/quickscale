"""Backup policy validation, loading, and model conversion."""

from __future__ import annotations


from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from typing import Any

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from quickscale_core.dr_engine.persistence import PersistedBackupPolicy

import quickscale_core.dr_engine.orchestration as _orchestration


def _validate_policy_snapshot_internal(policy: BackupPolicySnapshot) -> list[str]:
    """Return human-readable validation issues for a backup policy snapshot."""
    issues: list[str] = []

    if policy.retention_days < 1:
        issues.append("retention_days must be at least 1 day")

    prefix = policy.naming_prefix.strip()
    if not prefix:
        issues.append("naming_prefix cannot be blank")

    if policy.target_mode not in {
        "local",
        "private_remote",
    }:
        issues.append("target_mode must be 'local' or 'private_remote'")

    if not policy.local_directory.strip():
        issues.append("local_directory cannot be blank")

    if policy.automation_enabled and not policy.schedule.strip():
        issues.append("schedule is required when automation_enabled is true")

    if policy.target_mode == "private_remote":
        if not policy.remote_bucket_name.strip():
            issues.append(
                "remote_bucket_name is required when target_mode is private_remote"
            )
        if not policy.remote_access_key_id_env_var.strip():
            issues.append(
                "remote_access_key_id_env_var is required when target_mode is private_remote"
            )
        if not policy.remote_secret_access_key_env_var.strip():
            issues.append(
                "remote_secret_access_key_env_var is required when target_mode is private_remote"
            )
        if not (
            policy.remote_region_name.strip() or policy.remote_endpoint_url.strip()
        ):
            issues.append(
                "private_remote mode requires remote_region_name or remote_endpoint_url"
            )

    return issues


def _load_active_policy_snapshot(
    *, ensure_default: bool = True
) -> BackupPolicySnapshot:
    """Load the active runtime policy snapshot with managed settings precedence.

    SA89b Phase 1: policy introspection is routed through the persistence
    provider seam; the settings-derived snapshot comes from the registered
    policy provider, which owns reading its own module's settings, so core
    names none of them.  ``ensure_default=False`` skips the default-policy
    reconciliation so a dry run can resolve the policy without writing.
    """
    from quickscale_core.dr_engine.persistence import (
        ensure_default_policy,
        has_any_policy,
    )

    settings_snapshot = _orchestration.settings_policy_snapshot()
    if not has_any_policy():
        return settings_snapshot

    if ensure_default:
        ensure_default_policy()
    return settings_snapshot


def _ensure_default_policy_internal() -> PersistedBackupPolicy:
    """Ensure a default policy row exists for admin-driven workflows.

    Delegates the create/update to the persistence provider which returns
    the persisted policy through the ``PersistedBackupPolicy`` contract.
    """
    from quickscale_core.dr_engine.persistence import ensure_default_policy

    return ensure_default_policy()


def _build_policy_snapshot_from_model(policy: Any) -> BackupPolicySnapshot:
    """Create a BackupPolicySnapshot from a database policy record."""
    return _orchestration.BackupPolicySnapshot(
        retention_days=policy.retention_days,
        naming_prefix=policy.naming_prefix,
        target_mode=policy.target_mode,
        local_directory=policy.local_directory,
        remote_bucket_name=policy.remote_bucket_name,
        remote_prefix=policy.remote_prefix,
        remote_endpoint_url=policy.remote_endpoint_url,
        remote_region_name=policy.remote_region_name,
        remote_access_key_id_env_var=policy.remote_access_key_id_env_var,
        remote_secret_access_key_env_var=policy.remote_secret_access_key_env_var,
        automation_enabled=policy.automation_enabled,
        schedule=policy.schedule,
    )
