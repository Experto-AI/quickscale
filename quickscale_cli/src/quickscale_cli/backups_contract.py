"""Backward-compatible shim for ``quickscale_cli.backups_contract``.

The canonical module options normalization, validation, and dispatcher
helpers live in ``quickscale_core.contracts.module_options`` as part of
the shared contract surface owned by ``quickscale_core``. This module
re-exports the backups-specific names so existing CLI consumers continue
to work without modification.

Phase 0 of the QuickScale Phase 3 architecture improvements moved the
``sanitize_module_options`` dispatcher and the ``normalize_*_module_options``
helpers out of the CLI package. The original symbols are preserved here
as thin re-exports.
"""

from quickscale_core.contracts.module_options import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    has_legacy_backups_secret_values,
    normalize_backups_module_options,
    sanitize_module_options,
    validate_backups_env_var_reference,
)

__all__ = [
    "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    "DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR",
    "DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
    "has_legacy_backups_secret_values",
    "normalize_backups_module_options",
    "sanitize_module_options",
    "validate_backups_env_var_reference",
]
