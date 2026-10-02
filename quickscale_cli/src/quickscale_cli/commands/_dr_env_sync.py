"""Environment-variable classification and sync planning for DR commands.

Implementation detail of :mod:`quickscale_cli.commands.dr_commands`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

from typing import Any

from quickscale_cli.commands._dr_context import DisasterRecoveryContext
import quickscale_cli.commands.dr_commands as _dr_commands


def _classify_env_var(name: str) -> tuple[str, str]:
    """Backward-compatible wrapper around the centralized helper.

    The classification rules live in
    :func:`quickscale_core.contracts.module_options.get_env_var_portability`
    so that the schema layer and any future caller can reuse them. This
    thin shim preserves the original private name and signature so any
    caller that still reaches into ``dr_commands._classify_env_var`` —
    including the legacy test suite — continues to receive the same
    ``(category, reason)`` tuple with the same reason strings.
    """
    return _dr_commands.get_env_var_portability(name)


def _build_env_sync_plan(
    context: DisasterRecoveryContext,
    snapshot_report: dict[str, Any],
) -> dict[str, Any]:
    payloads = snapshot_report.get("sidecar_payloads") or {}
    env_manifest = payloads.get(_dr_commands._ENV_MANIFEST_FILENAME)
    if not isinstance(env_manifest, dict):
        return {
            "status": "unavailable",
            "portable_candidates": [],
            "portable_conflicts": [],
            "portable_existing": [],
            "manual_requirements": [],
            "ignored_count": 0,
            "reason": "env-var sidecar payload was not requested or could not be parsed",
        }

    if str(env_manifest.get("status", "")).strip() != "ready":
        return {
            "status": "unavailable",
            "portable_candidates": [],
            "portable_conflicts": [],
            "portable_existing": [],
            "manual_requirements": [],
            "ignored_count": 0,
            "reason": str(env_manifest.get("reason", "env-var manifest is not ready")),
        }

    source_live_variables = _dr_commands._load_source_live_variables(context)
    target_live_variables = context.target_runtime_variables
    portable_candidates: list[str] = []
    portable_existing: list[str] = []
    portable_conflicts: list[dict[str, str]] = []
    manual_requirements: list[dict[str, Any]] = []
    ignored_count = 0

    raw_names = env_manifest.get("names", [])
    source_names = [name for name in raw_names if isinstance(name, str)]
    for name in sorted(source_names):
        category, reason = _dr_commands._classify_env_var(name)
        if category == "ignored":
            ignored_count += 1
            continue

        source_value = str(source_live_variables.get(name, "")).strip()
        target_value = str(target_live_variables.get(name, "")).strip()

        if category == "portable":
            if not source_value:
                continue
            if not target_value:
                portable_candidates.append(name)
                continue
            if target_value == source_value:
                portable_existing.append(name)
                continue
            portable_conflicts.append(
                {
                    "name": name,
                    "reason": "target already defines a different value",
                }
            )
            continue

        manual_requirements.append(
            {
                "name": name,
                "reason": reason,
                "target_has_value": bool(target_value),
            }
        )

    status = "ready"
    if portable_conflicts or manual_requirements:
        status = "manual_required"

    return {
        "status": status,
        "portable_candidates": portable_candidates,
        "portable_existing": portable_existing,
        "portable_conflicts": portable_conflicts,
        "manual_requirements": manual_requirements,
        "ignored_count": ignored_count,
    }


def _execute_portable_env_sync(
    context: DisasterRecoveryContext,
    env_sync_plan: dict[str, Any],
) -> dict[str, Any]:
    source_live_variables = _dr_commands._load_source_live_variables(context)
    variables_to_copy = {
        name: source_live_variables[name]
        for name in env_sync_plan.get("portable_candidates", [])
        if str(source_live_variables.get(name, "")).strip()
    }
    if not variables_to_copy:
        status = "skipped"
        if env_sync_plan.get("manual_requirements") or env_sync_plan.get(
            "portable_conflicts"
        ):
            status = "manual_required"
        return {
            "status": status,
            "copied": [],
            "failed": [],
            "manual_requirements": env_sync_plan.get("manual_requirements", []),
            "portable_conflicts": env_sync_plan.get("portable_conflicts", []),
        }

    success, failed_keys = _dr_commands.set_railway_variables_batch(
        variables_to_copy,
        service=context.target_service,
        environment=context.target_railway_environment,
    )
    copied = sorted(set(variables_to_copy) - set(failed_keys))
    status = "completed" if success else "partial"
    return {
        "status": status,
        "copied": copied,
        "failed": sorted(failed_keys),
        "manual_requirements": env_sync_plan.get("manual_requirements", []),
        "portable_conflicts": env_sync_plan.get("portable_conflicts", []),
    }
