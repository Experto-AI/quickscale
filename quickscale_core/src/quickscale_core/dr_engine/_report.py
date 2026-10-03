"""Snapshot report building, verification, rollback pins, and artifact validation."""

from __future__ import annotations


from collections.abc import Sequence
from datetime import datetime
from datetime import timezone
from pathlib import Path
from quickscale_core.dr_engine._types import _RemoteUploader
from quickscale_core.dr_engine.primitives import BackupPolicySnapshot
from typing import Any

import quickscale_core.dr_engine.orchestration as _orchestration


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


def _build_snapshot_full_backup_contract(
    snapshot: Any,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build the canonical full-backup completeness/provenance contract."""
    evaluated_at = now or _orchestration.django_timezone.now()
    _, database_descriptor, sidecars = _orchestration._get_snapshot_report_children(
        snapshot
    )

    completeness_issues: list[str] = []
    provenance_issues: list[str] = []

    if snapshot.status != "ready":
        completeness_issues.append(f"snapshot status is '{snapshot.status}'")

    authoritative_dump = snapshot.authoritative_dump
    database_status = str(database_descriptor.get("status", "")).strip() or "missing"
    database_relative_path = str(database_descriptor.get("relative_path", "")).strip()
    database_local_available = False
    database_remote_available = False
    database_remote_key = str(database_descriptor.get("remote_key", "")).strip()

    authoritative_dump_payload: dict[str, Any] | None = None
    if authoritative_dump is None:
        completeness_issues.append("authoritative database dump is missing")
    else:
        database_local_path = _orchestration._resolve_snapshot_database_local_path(
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
            "module_versions": _orchestration._collect_artifact_module_versions(
                authoritative_dump
            )
            or {},
        }

    required_sidecars: dict[str, dict[str, Any]] = {}
    loaded_sidecar_payloads: dict[str, dict[str, Any]] = {}
    expected_manifest_statuses = {
        _orchestration._MEDIA_SYNC_MANIFEST_FILENAME: "ready",
        _orchestration._ENV_VAR_MANIFEST_FILENAME: "ready",
        _orchestration._RELEASE_METADATA_FILENAME: "ready",
    }

    for filename in _orchestration._REQUIRED_SNAPSHOT_SIDECAR_FILENAMES:
        raw_descriptor = sidecars.get(filename)
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
            else _orchestration._snapshot_sidecar_path(snapshot, filename)
        )
        local_available = local_path.exists()
        remote_available = bool(str(descriptor.get("remote_key", "")).strip())

        required_sidecars[filename] = {
            "status": sidecar_status,
            "manifest_status": manifest_status,
            "local_available": local_available,
            "remote_available": remote_available,
        }

        if not isinstance(raw_descriptor, dict):
            completeness_issues.append(f"{filename} descriptor is missing")
        elif sidecar_status != "ready":
            completeness_issues.append(f"{filename} status is '{sidecar_status}'")
        if not local_available and not remote_available:
            completeness_issues.append(
                f"{filename} is unavailable in both local and remote storage"
            )

        expected_manifest_status = expected_manifest_statuses.get(filename)
        if (
            expected_manifest_status is not None
            and manifest_status != expected_manifest_status
        ):
            completeness_issues.append(
                f"{filename} manifest status is '{manifest_status or 'missing'}'"
            )

        if local_available:
            try:
                loaded_sidecar_payloads[filename] = (
                    _orchestration._load_snapshot_sidecar_payload(
                        snapshot,
                        filename,
                    )
                )
            except _orchestration.BackupError as exc:
                provenance_issues.append(
                    f"{filename} could not be loaded for provenance validation: {exc}"
                )
        elif not remote_available:
            provenance_issues.append(
                f"{filename} provenance payload is unavailable for inspection"
            )

    project_slug_candidates: list[tuple[str, str]] = []
    source_environment_candidates: list[tuple[str, str]] = [
        ("snapshot", snapshot.source_environment.strip())
    ]
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

    project_slug = _orchestration._resolve_snapshot_provenance_value(
        field_name="project_slug",
        candidates=project_slug_candidates,
        issues=provenance_issues,
    )
    source_environment = _orchestration._resolve_snapshot_provenance_value(
        field_name="source_environment",
        candidates=source_environment_candidates,
        issues=provenance_issues,
    )

    release_payload = loaded_sidecar_payloads.get(
        _orchestration._RELEASE_METADATA_FILENAME, {}
    )
    module_versions = release_payload.get("module_versions", {})
    release_summary = {
        "app_version": release_payload.get("app_version"),
        "django_version": release_payload.get("django_version"),
        "module_versions": module_versions if isinstance(module_versions, dict) else {},
        "git_sha": release_payload.get("git_sha"),
    }

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
                "status": database_status,
                "relative_path": database_relative_path,
                "local_available": database_local_available,
                "remote_available": database_remote_available,
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
            "authoritative_dump": authoritative_dump_payload,
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
    report_time = now or _orchestration.django_timezone.now()
    _, database_descriptor, sidecars = _orchestration._get_snapshot_report_children(
        snapshot
    )
    full_backup_contract = _orchestration._build_snapshot_full_backup_contract(
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
            "module_versions": _orchestration._collect_artifact_module_versions(
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
                _orchestration._load_snapshot_sidecar_payload(
                    snapshot,
                    filename,
                )
            )
        except _orchestration.BackupError as exc:
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
    snapshot = _orchestration.get_backup_snapshot(snapshot_id)
    return _orchestration.build_backup_snapshot_report(
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
    _orchestration._validate_verification_inputs(
        route=normalized_route,
        phase=normalized_phase,
        status=normalized_status,
    )

    snapshot = _orchestration.get_backup_snapshot(snapshot_id)
    recorded_at = now or _orchestration.django_timezone.now()
    full_backup_contract = _orchestration._build_snapshot_full_backup_contract(
        snapshot,
        now=recorded_at,
    )
    try:
        verification_payload = _orchestration._load_snapshot_sidecar_payload(
            snapshot,
            _orchestration._PROMOTION_VERIFICATION_FILENAME,
        )
    except _orchestration.BackupError:
        verification_payload = {}

    existing_reports = verification_payload.get("reports")
    if not isinstance(existing_reports, list):
        existing_reports = []

    verification_payload = _orchestration._build_verification_payload(
        snapshot_id=snapshot.snapshot_id,
        project_slug=_orchestration._get_project_slug(),
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
    _orchestration._persist_snapshot_sidecar_payload(
        snapshot,
        filename=_orchestration._PROMOTION_VERIFICATION_FILENAME,
        kind="promotion_verification",
        payload=verification_payload,
        policy=policy,
        remote_uploader=remote_uploader,
    )
    return _orchestration.build_backup_snapshot_report(
        snapshot,
        now=recorded_at,
        sidecar_payloads=[_orchestration._PROMOTION_VERIFICATION_FILENAME],
    )


def validate_backup_artifact(artifact: Any) -> list[str]:
    """Validate artifact integrity and update its validation status."""
    local_path = Path(artifact.local_path) if artifact.local_path else None
    issues = _orchestration._collect_local_backup_validation_issues(
        local_path,
        backup_format=artifact.backup_format,
        expected_checksum=artifact.checksum_sha256,
        expected_size=artifact.size_bytes,
    )

    artifact.validated_at = _orchestration.django_timezone.now()
    artifact.validation_notes = "; ".join(issues)
    artifact.status = "failed" if issues else "validated"
    _orchestration.save_artifact(
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
    snapshot = _orchestration.get_backup_snapshot(snapshot_id)
    if snapshot.status == "deleted":
        raise _orchestration.BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' has already been deleted"
        )
    if snapshot.authoritative_dump is None:
        raise _orchestration.BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' does not have an authoritative dump"
        )

    pinned_at = now or _orchestration.django_timezone.now()
    fields = _orchestration._compute_rollback_pin_fields(
        ttl_hours=ttl_hours,
        reason=reason,
        now=pinned_at,
    )
    snapshot.rollback_pin_expires_at = fields["rollback_pin_expires_at"]
    snapshot.rollback_pin_reason = fields["rollback_pin_reason"]
    _orchestration.save_snapshot(
        snapshot,
        update_fields=[
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ],
    )
    return _orchestration.build_backup_snapshot_report(snapshot, now=pinned_at)


def clear_backup_snapshot_rollback_pin(
    snapshot_id: str,
    *,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Clear any active rollback pin on one stored snapshot."""
    snapshot = _orchestration.get_backup_snapshot(snapshot_id)
    if snapshot.status == "deleted":
        raise _orchestration.BackupError(
            f"Backup snapshot '{snapshot.snapshot_id}' has already been deleted"
        )

    cleared_at = now or _orchestration.django_timezone.now()
    fields = _orchestration._build_clear_rollback_pin_fields()
    snapshot.rollback_pin_expires_at = fields["rollback_pin_expires_at"]
    snapshot.rollback_pin_reason = fields["rollback_pin_reason"]
    _orchestration.save_snapshot(
        snapshot,
        update_fields=[
            "rollback_pin_expires_at",
            "rollback_pin_reason",
            "updated_at",
        ],
    )
    return _orchestration.build_backup_snapshot_report(snapshot, now=cleared_at)
