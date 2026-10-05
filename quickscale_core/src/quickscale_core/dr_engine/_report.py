"""Snapshot report building, verification, rollback pins, and artifact validation."""

from __future__ import annotations


from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from pathlib import Path
from quickscale_core.dr_engine._types import _RemoteUploader
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from typing import Any


import quickscale_core.dr_engine.primitives as _primitives
import quickscale_core.dr_engine._paths as _paths
import quickscale_core.dr_engine._state as _state
import quickscale_core.dr_engine.verification as _verification
import quickscale_core.dr_engine._sidecar as _sidecar
import quickscale_core.dr_engine.recovery as _recovery
import quickscale_core.dr_engine.persistence as _persistence
import django.utils.timezone as _django_timezone
import quickscale_core.dr_engine._metadata as _metadata


def _resolve_snapshot_provenance_value(
    *,
    field_name: str,
    candidates: Sequence[tuple[str, str]],
    issues: list[str],
) -> str | None:
    """Resolve one provenance value and note mismatches across stored sources."""
    populated_candidates = [
        (source, value) for source, value in candidates if value.strip()
    ]
    if not populated_candidates:
        issues.append(f"{field_name} is not recorded on the snapshot seam")
        return None

    unique_values = {value for _, value in populated_candidates}
    if len(unique_values) > 1:
        mismatch_details = ", ".join(
            f"{source}={value}" for source, value in populated_candidates
        )
        issues.append(
            f"{field_name} is inconsistent across snapshot provenance sources: "
            f"{mismatch_details}"
        )

    return populated_candidates[0][1]


@dataclass(frozen=True)
class _SnapshotDatabaseContract:
    """The authoritative-dump portion of the full-backup contract."""

    status: str
    relative_path: str
    local_available: bool
    remote_available: bool
    payload: dict[str, Any] | None


def _snapshot_database_contract(
    snapshot: Any, database_descriptor: Any
) -> tuple[_SnapshotDatabaseContract, list[str]]:
    """Return the database contract fields and their completeness issues."""
    completeness_issues: list[str] = []
    database_status = str(database_descriptor.get("status", "")).strip() or "missing"
    database_relative_path = str(database_descriptor.get("relative_path", "")).strip()
    database_local_available = False
    database_remote_available = False
    database_remote_key = str(database_descriptor.get("remote_key", "")).strip()
    authoritative_dump = snapshot.authoritative_dump

    authoritative_dump_payload: dict[str, Any] | None = None
    if authoritative_dump is None:
        completeness_issues.append("authoritative database dump is missing")
    else:
        database_local_path = _state._resolve_snapshot_database_local_path(
            snapshot,
            authoritative_dump,
        )
        database_local_available = database_local_path.exists()
        database_remote_available = bool(
            database_remote_key or authoritative_dump.remote_key
        )
        if authoritative_dump.status == "deleted":
            completeness_issues.append("authoritative database dump has been deleted")
        if database_status != "ready":
            completeness_issues.append(f"database dump status is '{database_status}'")
        if not database_local_available and not database_remote_available:
            completeness_issues.append(
                "database dump is unavailable in both local and remote storage"
            )

        authoritative_dump_payload = {
            "artifact_id": authoritative_dump.pk,
            "filename": authoritative_dump.filename,
            "backup_format": authoritative_dump.backup_format,
            "database_engine": authoritative_dump.database_engine,
            "database_name": authoritative_dump.database_name,
            "checksum_sha256": authoritative_dump.checksum_sha256,
            "size_bytes": authoritative_dump.size_bytes,
            "module_versions": _recovery._collect_artifact_module_versions(
                authoritative_dump
            )
            or {},
        }

    return (
        _SnapshotDatabaseContract(
            status=database_status,
            relative_path=database_relative_path,
            local_available=database_local_available,
            remote_available=database_remote_available,
            payload=authoritative_dump_payload,
        ),
        completeness_issues,
    )


def _sidecar_descriptor_fields(
    snapshot: Any, filename: str, raw_descriptor: Any
) -> tuple[dict[str, Any], str, str, bool, bool]:
    """Return one sidecar's entry and (status, manifest, local, remote) fields."""
    descriptor = raw_descriptor if isinstance(raw_descriptor, dict) else {}
    sidecar_status = str(descriptor.get("status", "")).strip() or "missing"
    metadata = descriptor.get("metadata", {})
    manifest_status = ""
    if isinstance(metadata, dict):
        manifest_status = str(metadata.get("manifest_status", "")).strip()

    local_path_text = str(descriptor.get("local_path", "")).strip()
    local_path = (
        Path(local_path_text)
        if local_path_text
        else _paths._snapshot_sidecar_path(snapshot, filename)
    )
    local_available = local_path.exists()
    remote_available = bool(str(descriptor.get("remote_key", "")).strip())
    entry = {
        "status": sidecar_status,
        "manifest_status": manifest_status,
        "local_available": local_available,
        "remote_available": remote_available,
    }
    return entry, sidecar_status, manifest_status, local_available, remote_available


def _sidecar_completeness_issues(
    raw_descriptor: Any,
    filename: str,
    *,
    sidecar_status: str,
    manifest_status: str,
    local_available: bool,
    remote_available: bool,
    expected_manifest_status: str | None,
) -> list[str]:
    """Return one sidecar's completeness issues."""
    issues: list[str] = []
    if not isinstance(raw_descriptor, dict):
        issues.append(f"{filename} descriptor is missing")
    elif sidecar_status != "ready":
        issues.append(f"{filename} status is '{sidecar_status}'")
    if not local_available and not remote_available:
        issues.append(f"{filename} is unavailable in both local and remote storage")
    if (
        expected_manifest_status is not None
        and manifest_status != expected_manifest_status
    ):
        issues.append(f"{filename} manifest status is '{manifest_status or 'missing'}'")
    return issues


def _sidecar_payload(
    snapshot: Any, filename: str, *, local_available: bool, remote_available: bool
) -> tuple[dict[str, Any] | None, list[str]]:
    """Return one locally available sidecar's payload and provenance issues."""
    if local_available:
        try:
            return _sidecar._load_snapshot_sidecar_payload(snapshot, filename), []
        except _primitives.BackupError as exc:
            return None, [
                f"{filename} could not be loaded for provenance validation: {exc}"
            ]
    if not remote_available:
        return None, [f"{filename} provenance payload is unavailable for inspection"]
    return None, []


def _collect_sidecar_provenance(
    loaded_sidecar_payloads: dict[str, dict[str, Any]],
) -> tuple[
    list[tuple[str, str]],
    list[tuple[str, str]],
    list[str],
    dict[str, str | None],
]:
    """Collect per-sidecar provenance candidates, issues, and captured times."""
    project_slug_candidates: list[tuple[str, str]] = []
    source_environment_candidates: list[tuple[str, str]] = []
    provenance_issues: list[str] = []
    sidecar_captured_at: dict[str, str | None] = {}
    for filename, payload in loaded_sidecar_payloads.items():
        payload_project_slug = str(payload.get("project_slug", "")).strip()
        if payload_project_slug:
            project_slug_candidates.append((filename, payload_project_slug))
        else:
            provenance_issues.append(f"{filename} is missing project_slug")

        payload_source_environment = str(payload.get("source_environment", "")).strip()
        if payload_source_environment:
            source_environment_candidates.append((filename, payload_source_environment))
        else:
            provenance_issues.append(f"{filename} is missing source_environment")

        captured_at = payload.get("captured_at")
        sidecar_captured_at[filename] = (
            str(captured_at).strip() if captured_at is not None else None
        )
    return (
        project_slug_candidates,
        source_environment_candidates,
        provenance_issues,
        sidecar_captured_at,
    )


def _snapshot_release_summary(payload: dict[str, Any]) -> dict[str, Any]:
    """Return the release metadata summary carried in the contract."""
    module_versions = payload.get("module_versions", {})
    return {
        "app_version": payload.get("app_version"),
        "django_version": payload.get("django_version"),
        "module_versions": module_versions if isinstance(module_versions, dict) else {},
        "git_sha": payload.get("git_sha"),
    }


def _build_snapshot_full_backup_contract(
    snapshot: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the canonical full-backup completeness/provenance contract."""
    evaluated_at = now or _django_timezone.now()
    _, database_descriptor, sidecars = _paths._get_snapshot_report_children(snapshot)

    completeness_issues: list[str] = []
    provenance_issues: list[str] = []

    if snapshot.status != "ready":
        completeness_issues.append(f"snapshot status is '{snapshot.status}'")

    database_contract, database_issues = _snapshot_database_contract(
        snapshot, database_descriptor
    )
    completeness_issues.extend(database_issues)

    required_sidecars: dict[str, dict[str, Any]] = {}
    loaded_sidecar_payloads: dict[str, dict[str, Any]] = {}
    expected_manifest_statuses = {
        _primitives._MEDIA_SYNC_MANIFEST_FILENAME: "ready",
        _primitives._ENV_VAR_MANIFEST_FILENAME: "ready",
        _primitives._RELEASE_METADATA_FILENAME: "ready",
    }

    for filename in _primitives._REQUIRED_SNAPSHOT_SIDECAR_FILENAMES:
        raw_descriptor = sidecars.get(filename)
        entry, sidecar_status, manifest_status, local_available, remote_available = (
            _sidecar_descriptor_fields(snapshot, filename, raw_descriptor)
        )
        required_sidecars[filename] = entry
        completeness_issues.extend(
            _sidecar_completeness_issues(
                raw_descriptor,
                filename,
                sidecar_status=sidecar_status,
                manifest_status=manifest_status,
                local_available=local_available,
                remote_available=remote_available,
                expected_manifest_status=expected_manifest_statuses.get(filename),
            )
        )
        payload, sidecar_provenance = _sidecar_payload(
            snapshot,
            filename,
            local_available=local_available,
            remote_available=remote_available,
        )
        provenance_issues.extend(sidecar_provenance)
        if payload is not None:
            loaded_sidecar_payloads[filename] = payload

    (
        project_slug_candidates,
        source_environment_candidates,
        sidecar_provenance_issues,
        sidecar_captured_at,
    ) = _collect_sidecar_provenance(loaded_sidecar_payloads)
    provenance_issues.extend(sidecar_provenance_issues)
    source_environment_candidates.insert(
        0, ("snapshot", snapshot.source_environment.strip())
    )

    project_slug = _resolve_snapshot_provenance_value(
        field_name="project_slug",
        candidates=project_slug_candidates,
        issues=provenance_issues,
    )
    source_environment = _resolve_snapshot_provenance_value(
        field_name="source_environment",
        candidates=source_environment_candidates,
        issues=provenance_issues,
    )

    release_payload = loaded_sidecar_payloads.get(
        _primitives._RELEASE_METADATA_FILENAME, {}
    )
    release_summary = _snapshot_release_summary(release_payload)

    completeness_status = "complete" if not completeness_issues else "incomplete"
    provenance_status = "consistent" if not provenance_issues else "inconsistent"

    return {
        "status": (
            "complete"
            if completeness_status == "complete" and provenance_status == "consistent"
            else "incomplete"
        ),
        "validated_at": evaluated_at.astimezone(timezone.utc).isoformat(),
        "completeness": {
            "status": completeness_status,
            "issues": completeness_issues,
            "database": {
                "status": database_contract.status,
                "relative_path": database_contract.relative_path,
                "local_available": database_contract.local_available,
                "remote_available": database_contract.remote_available,
            },
            "required_sidecars": required_sidecars,
        },
        "provenance": {
            "status": provenance_status,
            "issues": provenance_issues,
            "snapshot_id": snapshot.snapshot_id,
            "project_slug": project_slug,
            "source_environment": source_environment,
            "captured_at": snapshot.created_at.astimezone(timezone.utc).isoformat(),
            "sidecar_captured_at": sidecar_captured_at,
            "authoritative_dump": database_contract.payload,
            "release": release_summary,
        },
    }


def build_backup_snapshot_report(
    snapshot: Any,
    *,
    now: datetime | None = None,
    sidecar_payloads: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Build a structured report for one stored snapshot."""
    report_time = now or _django_timezone.now()
    _, database_descriptor, sidecars = _paths._get_snapshot_report_children(snapshot)
    full_backup_contract = _build_snapshot_full_backup_contract(
        snapshot,
        now=report_time,
    )

    authoritative_dump = snapshot.authoritative_dump
    authoritative_dump_payload: dict[str, Any] | None = None
    if authoritative_dump is not None:
        authoritative_dump_payload = {
            "artifact_id": authoritative_dump.pk,
            "filename": authoritative_dump.filename,
            "status": authoritative_dump.status,
            "storage_target": authoritative_dump.storage_target,
            "backup_format": authoritative_dump.backup_format,
            "restore_scope": authoritative_dump.effective_restore_scope(),
            "restore_scope_label": authoritative_dump.restore_scope_label(),
            "local_path": authoritative_dump.local_path,
            "remote_key": authoritative_dump.remote_key,
            "checksum_sha256": authoritative_dump.checksum_sha256,
            "size_bytes": authoritative_dump.size_bytes,
            "module_versions": _recovery._collect_artifact_module_versions(
                authoritative_dump
            )
            or {},
            "created_at": authoritative_dump.created_at.astimezone(
                timezone.utc
            ).isoformat(),
        }

    sidecar_summary: dict[str, dict[str, str]] = {}
    for filename, descriptor in sorted(sidecars.items()):
        if not isinstance(descriptor, dict):
            continue
        sidecar_summary[filename] = {
            "kind": str(descriptor.get("kind", "")).strip(),
            "status": str(descriptor.get("status", "")).strip(),
            "manifest_status": str(
                descriptor.get("metadata", {}).get("manifest_status", "")
            ).strip(),
        }

    requested_sidecar_payloads = tuple(
        dict.fromkeys(
            filename.strip()
            for filename in (sidecar_payloads or ())
            if filename.strip()
        )
    )
    included_sidecar_payloads: dict[str, dict[str, Any]] = {}
    sidecar_payload_errors: dict[str, str] = {}
    for filename in requested_sidecar_payloads:
        try:
            included_sidecar_payloads[filename] = (
                _sidecar._load_snapshot_sidecar_payload(
                    snapshot,
                    filename,
                )
            )
        except _primitives.BackupError as exc:
            sidecar_payload_errors[filename] = str(exc)

    return {
        "snapshot_id": snapshot.snapshot_id,
        "status": snapshot.status,
        "source_environment": snapshot.source_environment,
        "created_at": snapshot.created_at.astimezone(timezone.utc).isoformat(),
        "updated_at": snapshot.updated_at.astimezone(timezone.utc).isoformat(),
        "failure_note": snapshot.failure_note,
        "confirmation_value": (
            authoritative_dump.filename if authoritative_dump is not None else ""
        ),
        "local_root_path": snapshot.local_root_path,
        "remote_root_key": snapshot.remote_root_key,
        "authoritative_dump": authoritative_dump_payload,
        "rollback_pin": {
            "active": snapshot.has_active_rollback_pin(now=report_time),
            "expires_at": (
                snapshot.rollback_pin_expires_at.astimezone(timezone.utc).isoformat()
                if snapshot.rollback_pin_expires_at is not None
                else None
            ),
            "reason": snapshot.rollback_pin_reason,
        },
        "children": {
            "database": database_descriptor,
            "sidecars": sidecars,
        },
        "full_backup": full_backup_contract,
        "sidecar_summary": sidecar_summary,
        "sidecar_payloads": included_sidecar_payloads,
        "sidecar_payload_errors": sidecar_payload_errors,
    }


def report_backup_snapshot(
    snapshot_id: str,
    *,
    now: datetime | None = None,
    sidecar_payloads: Sequence[str] | None = None,
) -> dict[str, Any]:
    """Return a structured report for one stored snapshot id."""
    snapshot = _state.get_backup_snapshot(snapshot_id)
    return build_backup_snapshot_report(
        snapshot,
        now=now,
        sidecar_payloads=sidecar_payloads,
    )


def record_backup_snapshot_verification(
    snapshot_id: str,
    *,
    route: str,
    phase: str,
    status: str,
    payload: dict[str, Any],
    now: datetime | None = None,
    policy: BackupPolicySnapshot | None = None,
    remote_uploader: _RemoteUploader | None = None,
) -> dict[str, Any]:
    """Append one route-specific report to the verification sidecar.

    This is a Django-facing wrapper.  The verification payload is assembled
    by ``_build_verification_payload`` in ``dr_engine.verification``.
    """
    normalized_route = route.strip()
    normalized_phase = phase.strip()
    normalized_status = status.strip()
    _verification._validate_verification_inputs(
        route=normalized_route,
        phase=normalized_phase,
        status=normalized_status,
    )

    snapshot = _state.get_backup_snapshot(snapshot_id)
    recorded_at = now or _django_timezone.now()
    full_backup_contract = _build_snapshot_full_backup_contract(
        snapshot,
        now=recorded_at,
    )
    try:
        verification_payload = _sidecar._load_snapshot_sidecar_payload(
            snapshot,
            _primitives._PROMOTION_VERIFICATION_FILENAME,
        )
    except _primitives.BackupError:
        verification_payload = {}

    existing_reports = verification_payload.get("reports")
    if not isinstance(existing_reports, list):
        existing_reports = []

    verification_payload = _verification._build_verification_payload(
        snapshot_id=snapshot.snapshot_id,
        project_slug=_metadata._get_project_slug(),
        source_environment=snapshot.source_environment,
        captured_at=verification_payload.get(
            "captured_at",
            snapshot.created_at.astimezone(timezone.utc).isoformat(),
        ),
        status=normalized_status,
        updated_at=recorded_at.astimezone(timezone.utc).isoformat(),
        full_backup_contract=full_backup_contract,
        existing_reports=existing_reports,
        existing_notes=verification_payload.get(
            "notes",
            "Reserved for route-specific plan and execute reports.",
        ),
        rollback_pin_active=snapshot.has_active_rollback_pin(now=recorded_at),
        rollback_pin_expires_at=(
            snapshot.rollback_pin_expires_at.astimezone(timezone.utc).isoformat()
            if snapshot.rollback_pin_expires_at is not None
            else None
        ),
        rollback_pin_reason=snapshot.rollback_pin_reason,
        route=normalized_route,
        phase=normalized_phase,
        payload=payload,
    )
    _sidecar._persist_snapshot_sidecar_payload(
        snapshot,
        filename=_primitives._PROMOTION_VERIFICATION_FILENAME,
        kind="promotion_verification",
        payload=verification_payload,
        policy=policy,
        remote_uploader=remote_uploader,
    )
    return build_backup_snapshot_report(
        snapshot,
        now=recorded_at,
        sidecar_payloads=[_primitives._PROMOTION_VERIFICATION_FILENAME],
    )


def validate_backup_artifact(artifact: Any) -> list[str]:
    """Validate artifact integrity and update its validation status."""
    local_path = Path(artifact.local_path) if artifact.local_path else None
    issues = _recovery._collect_local_backup_validation_issues(
        local_path,
        backup_format=artifact.backup_format,
        expected_checksum=artifact.checksum_sha256,
        expected_size=artifact.size_bytes,
    )

    artifact.validated_at = _django_timezone.now()
    artifact.validation_notes = "; ".join(issues)
    artifact.status = "failed" if issues else "validated"
    _persistence.save_artifact(
        artifact,
        update_fields=["validated_at", "validation_notes", "status", "updated_at"],
    )
    return issues


def set_backup_snapshot_rollback_pin(
    snapshot_id: str,
    *,
    ttl_hours: int,
    reason: str,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Set or refresh a time-bounded rollback pin on one stored snapshot."""
    snapshot = _state.get_backup_snapshot(snapshot_id)
    if snapshot.status == "deleted":
        raise _primitives.BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' has already been deleted"
        )
    if snapshot.authoritative_dump is None:
        raise _primitives.BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' does not have an authoritative dump"
        )

    pinned_at = now or _django_timezone.now()
    fields = _verification._compute_rollback_pin_fields(
        ttl_hours=ttl_hours,
        reason=reason,
        now=pinned_at,
    )
    snapshot.rollback_pin_expires_at = fields["rollback_pin_expires_at"]
    snapshot.rollback_pin_reason = fields["rollback_pin_reason"]
    _persistence.save_snapshot(
        snapshot,
        update_fields=[
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ],
    )
    return build_backup_snapshot_report(snapshot, now=pinned_at)


def clear_backup_snapshot_rollback_pin(
    snapshot_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Clear any active rollback pin on one stored snapshot."""
    snapshot = _state.get_backup_snapshot(snapshot_id)
    if snapshot.status == "deleted":
        raise _primitives.BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' has already been deleted"
        )

    cleared_at = now or _django_timezone.now()
    fields = _verification._build_clear_rollback_pin_fields()
    snapshot.rollback_pin_expires_at = fields["rollback_pin_expires_at"]
    snapshot.rollback_pin_reason = fields["rollback_pin_reason"]
    _persistence.save_snapshot(
        snapshot,
        update_fields=[
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ],
    )
    return build_backup_snapshot_report(snapshot, now=cleared_at)
