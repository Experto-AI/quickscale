"""Snapshot verification and rollback-pin logic — Django-free DR engine foundation.

These are the platform-level snapshot verification contracts and rollback-pin
lifecycle helpers defined in docs/technical/decisions.md § Disaster Recovery
Engine Boundary Contract (F5 / M10), phase F5.2b. They have no Django
dependency and may be imported by the CLI layer, the embeddable backups
module, or any future consumer.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from quickscale_core.dr_engine.primitives import BackupConfigurationError

# ---------------------------------------------------------------------------
# Verification payload assembly
# ---------------------------------------------------------------------------


def _build_verification_payload(
    *,
    snapshot_id: str,
    project_slug: str,
    source_environment: str,
    captured_at: str,
    status: str,
    updated_at: str,
    full_backup_contract: dict[str, Any],
    existing_reports: list[dict[str, Any]],
    existing_notes: str,
    rollback_pin_active: bool,
    rollback_pin_expires_at: str | None,
    rollback_pin_reason: str,
    route: str,
    phase: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Build a promotion verification payload with one appended route report.

    This is the pure data-transformation core called by the Django-backed
    ``record_backup_snapshot_verification`` wrapper. All snapshot data must
    be resolved before calling this function.
    """
    report_entry: dict[str, Any] = {
        "route": route,
        "phase": phase,
        "status": status,
        "recorded_at": updated_at,
        "full_backup": full_backup_contract,
        "payload": payload,
    }

    return {
        "manifest_version": 1,
        "captured_at": captured_at,
        "snapshot_id": snapshot_id,
        "project_slug": project_slug,
        "source_environment": source_environment,
        "status": status,
        "updated_at": updated_at,
        "full_backup": full_backup_contract,
        "reports": [
            *existing_reports,
            report_entry,
        ],
        "notes": existing_notes or _DEFAULT_VERIFICATION_NOTES,
        "rollback_pin": {
            "active": rollback_pin_active,
            "expires_at": rollback_pin_expires_at,
            "reason": rollback_pin_reason,
        },
    }


_DEFAULT_VERIFICATION_NOTES: str = (
    "Reserved for route-specific plan and execute reports."
)


# ---------------------------------------------------------------------------
# Rollback-pin field computation
# ---------------------------------------------------------------------------


def _compute_rollback_pin_fields(
    *,
    ttl_hours: int,
    reason: str,
    now: datetime,
) -> dict[str, Any]:
    """Compute the rollback-pin field values for a set operation.

    Returns a dict with ``rollback_pin_expires_at`` (datetime) and
    ``rollback_pin_reason`` (str).  Raises ``BackupConfigurationError``
    for invalid inputs.

    This is the pure logic core called by the Django-backed
    ``set_backup_snapshot_rollback_pin`` wrapper.
    """
    if ttl_hours < 1:
        raise BackupConfigurationError("ttl_hours must be at least 1")

    resolved_reason = reason.strip()
    if not resolved_reason:
        raise BackupConfigurationError("reason cannot be blank")

    return {
        "rollback_pin_expires_at": now + timedelta(hours=ttl_hours),
        "rollback_pin_reason": resolved_reason,
    }


def _build_clear_rollback_pin_fields() -> dict[str, Any]:
    """Compute the rollback-pin field values for a clear operation.

    Returns a dict with ``rollback_pin_expires_at`` (None) and
    ``rollback_pin_reason`` (empty string).

    This is the pure logic core called by the Django-backed
    ``clear_backup_snapshot_rollback_pin`` wrapper.
    """
    return {
        "rollback_pin_expires_at": None,
        "rollback_pin_reason": "",
    }


# ---------------------------------------------------------------------------
# Route/phase/status validation (shared across verification seam)
# ---------------------------------------------------------------------------


def _validate_verification_inputs(
    *,
    route: str,
    phase: str,
    status: str,
) -> None:
    """Validate verification parameters before building the payload."""
    if not route.strip():
        raise BackupConfigurationError("route cannot be blank")
    if not phase.strip():
        raise BackupConfigurationError("phase cannot be blank")
    if not status.strip():
        raise BackupConfigurationError("status cannot be blank")
