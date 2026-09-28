"""Startup checks for the QuickScale backups module.

Rule 10: these functions are run from ``AppConfig.ready()`` through
``quickscale_core.runtime.register_module_checks``, so a failure refuses
``runserver``, ``migrate``, and ``manage.py check`` alike.  Rule 35: the
credentials a switched-on feature needs must not be empty.
"""

from __future__ import annotations

from django.core.checks import CheckMessage, Error

#: The target mode whose backup operations upload through the remote provider.
_REMOTE_TARGET_MODE = "private_remote"

#: The environment-variable names the backup policy falls back to when its
#: own ``_ENV_VAR`` settings are blank (the manifest's documented defaults).
_DEFAULT_ACCESS_KEY_ID_ENV_VAR = "QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID"
_DEFAULT_SECRET_ACCESS_KEY_ENV_VAR = "QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY"  # noqa: S105 - name constant, not a credential


def check_private_remote_credentials(
    app_configs: object = None,
    **kwargs: object,
) -> list[CheckMessage]:
    """Fail startup when private_remote backups lack their credentials.

    The credentials are resolved through the same core policy snapshot the
    backup commands use, so the check and the command agree on which
    environment variable an empty value comes from.
    """
    from quickscale_core.runtime import _build_policy_snapshot_from_settings

    snapshot = _build_policy_snapshot_from_settings()
    if snapshot.target_mode != _REMOTE_TARGET_MODE:
        return []

    messages: list[CheckMessage] = []
    if not snapshot.resolve_remote_access_key_id():
        env_var_name = (
            snapshot.remote_access_key_id_env_var.strip()
            or _DEFAULT_ACCESS_KEY_ID_ENV_VAR
        )
        messages.append(
            Error(
                "QUICKSCALE_BACKUPS_TARGET_MODE is 'private_remote' but the "
                f"remote access key id environment variable {env_var_name!r} "
                "is empty. Set the credential or switch the target mode.",
                id="quickscale_backups.E001",
            )
        )
    if not snapshot.resolve_remote_secret_access_key():
        env_var_name = (
            snapshot.remote_secret_access_key_env_var.strip()
            or _DEFAULT_SECRET_ACCESS_KEY_ENV_VAR
        )
        messages.append(
            Error(
                "QUICKSCALE_BACKUPS_TARGET_MODE is 'private_remote' but the "
                f"remote secret access key environment variable {env_var_name!r} "
                "is empty. Set the credential or switch the target mode.",
                id="quickscale_backups.E002",
            )
        )
    return messages
