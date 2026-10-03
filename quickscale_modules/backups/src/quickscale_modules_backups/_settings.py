"""Private settings snapshot for the backups module.

Rule 42: the settings-derived policy snapshot is built here, from backups'
own declared settings, with no defaults and no coercion.  The DR engine
obtains it through the persistence seam registered in ``AppConfig.ready()``
and never reads a backups setting.  ``services.py`` re-exports the builder
(Module Conventions rule 28) so existing imports and patch targets keep
working; it stays out of ``services.__all__``.
"""

from __future__ import annotations

from django.conf import settings

from quickscale_core.runtime import BackupPolicySnapshot


def build_policy_snapshot_from_settings() -> BackupPolicySnapshot:
    """Build the active policy snapshot from backups' own declared settings.

    Rule 3: these values belong to backups and are read only here; the DR
    engine obtains this snapshot through the policy provider registered in
    ``AppConfig.ready()`` rather than naming a backups setting itself.
    """
    return BackupPolicySnapshot(
        retention_days=int(settings.QUICKSCALE_BACKUPS_RETENTION_DAYS),
        naming_prefix=str(settings.QUICKSCALE_BACKUPS_NAMING_PREFIX),
        target_mode=str(settings.QUICKSCALE_BACKUPS_TARGET_MODE),
        local_directory=str(settings.QUICKSCALE_BACKUPS_LOCAL_DIRECTORY),
        remote_bucket_name=str(settings.QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME),
        remote_prefix=str(settings.QUICKSCALE_BACKUPS_REMOTE_PREFIX),
        remote_endpoint_url=str(settings.QUICKSCALE_BACKUPS_REMOTE_ENDPOINT_URL),
        remote_region_name=str(settings.QUICKSCALE_BACKUPS_REMOTE_REGION_NAME),
        remote_access_key_id_env_var=str(
            settings.QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        ),
        remote_secret_access_key_env_var=str(
            settings.QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        ),
        automation_enabled=bool(settings.QUICKSCALE_BACKUPS_AUTOMATION_ENABLED),
        schedule=str(settings.QUICKSCALE_BACKUPS_SCHEDULE),
    )
