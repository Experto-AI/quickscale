"""Module-owned backups manifest adapter."""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime.manifest import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    ModuleWiringSpec,
    build_generic_manifest_spec,
    resolve_backups_module_options,
)


def _backups_manifest_adapter(
    options: dict[str, Any],
    *,
    project_package: str | None = None,
) -> ModuleWiringSpec:
    """Build a ModuleWiringSpec for backups from its manifest contract."""
    del project_package

    resolved = resolve_backups_module_options(options)
    retention_days = int(resolved["retention_days"])
    naming_prefix = str(resolved["naming_prefix"]).strip() or "db"
    target_mode = str(resolved["target_mode"]).strip().lower()
    if target_mode not in {"local", "private_remote"}:
        raise ValueError(
            "modules.backups.target_mode must be one of: local, private_remote"
        )

    access_key_id_env_var = str(
        resolved[BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION]
    ).strip()
    secret_access_key_env_var = str(
        resolved[BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION]
    ).strip()
    if target_mode == "private_remote" and not access_key_id_env_var:
        access_key_id_env_var = DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
    if target_mode == "private_remote" and not secret_access_key_env_var:
        secret_access_key_env_var = DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR

    manifest_spec = build_generic_manifest_spec("backups", options)
    settings = dict(manifest_spec.settings)
    settings.update(
        {
            "QUICKSCALE_BACKUPS_RETENTION_DAYS": retention_days,
            "QUICKSCALE_BACKUPS_NAMING_PREFIX": naming_prefix,
            "QUICKSCALE_BACKUPS_TARGET_MODE": target_mode,
            "QUICKSCALE_BACKUPS_LOCAL_DIRECTORY": str(
                resolved["local_directory"]
            ).strip()
            or ".quickscale/backups",
            "QUICKSCALE_BACKUPS_AUTOMATION_ENABLED": bool(
                resolved["automation_enabled"]
            ),
            "QUICKSCALE_BACKUPS_SCHEDULE": str(resolved["schedule"]),
            "QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME": str(
                resolved["remote_bucket_name"]
            ).strip(),
            "QUICKSCALE_BACKUPS_REMOTE_PREFIX": str(resolved["remote_prefix"]).strip()
            or "backups/private",
            "QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL": str(
                resolved["remote_endpoint_url"]
            ).strip(),
            "QUICKSCALE_BACKUPS_REMOTE_REGION_NAME": str(
                resolved["remote_region_name"]
            ).strip(),
            "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR": access_key_id_env_var,
            "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR": secret_access_key_env_var,
        }
    )

    return ModuleWiringSpec(
        apps=manifest_spec.apps,
        middleware=manifest_spec.middleware,
        settings=settings,
        url_includes=manifest_spec.url_includes,
        pre_home_url_includes=manifest_spec.pre_home_url_includes,
        managed_files=manifest_spec.managed_files,
    )


def get_manifest_adapter() -> Any:
    """Return the backups module's manifest adapter callable."""
    return _backups_manifest_adapter
