"""Backups module manifest-driven configuration adapter.

Replaces the legacy ``backups_contract.py`` shim by sourcing module defaults
from the backups ``module.yml`` manifest while deliberately keeping the
security-sensitive helpers delegating to ``quickscale_core``.

Design rationale
----------------
Unlike the analytics, auth, or billing manifests, this adapter uses a
**narrower** manifest scope by design:

* **Defaults from manifest**: ``default_backups_module_options()`` reads
  ``module.yml`` via the manifest loader, giving the same manifest-driven
  pattern used elsewhere.

* **DR-secret helpers delegated to core**: ``normalize_backups_module_options``,
  ``has_legacy_backups_secret_values``, and ``validate_backups_env_var_reference``
  are thin re-exports from ``quickscale_core.contracts.module_options``.
  The raw-secret detection and env-var normalization logic (disaster-recovery
  sensitive) MUST NOT be duplicated or reimplemented here.

* **Core-sourced constants for DEFAULT_BACKUPS_REMOTE_***: The
  ``DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR`` and
  ``DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR`` constants represent
  real environment-variable *names* (e.g. ``QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID``).
  They are re-exported from core, NOT derived from ``module.yml`` defaults —
  ``module.yml`` stores ``""`` for the env-var option defaults intentionally,
  because the project operator must supply or confirm them at configure time.

* **sanitize_module_options intentionally absent**: ``sanitize_module_options``
  is a cross-module dispatcher owned by ``quickscale_core.contracts.module_options``.
  Call sites that previously imported it from ``backups_contract`` must import
  it directly from ``quickscale_core.contracts.module_options`` instead.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from quickscale_core.contracts.module_options import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    has_legacy_backups_secret_values,
    normalize_backups_module_options,
    validate_backups_env_var_reference,
)
from quickscale_core.manifest.loader import load_manifest_from_path

# Re-export security-sensitive helpers and constants so callers that used
# ``backups_contract`` continue to work without modification.
__all__ = [
    "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    "DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR",
    "DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
    "default_backups_module_options",
    "has_legacy_backups_secret_values",
    "normalize_backups_module_options",
    "validate_backups_env_var_reference",
]

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BACKUPS_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "backups" / "module.yml"


def _load_backups_manifest() -> Any:
    """Load the backups module manifest from ``module.yml``."""
    return load_manifest_from_path(_BACKUPS_MANIFEST_PATH)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_backups_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for backups.

    Defaults are sourced from the backups ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.

    Note: ``remote_access_key_id_env_var`` and ``remote_secret_access_key_env_var``
    will be ``""`` in the manifest defaults — that is intentional.  The
    real fallback env-var names (``QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID``
    and ``QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY``) are captured by
    ``DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR`` and
    ``DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR`` which are sourced
    from ``quickscale_core.contracts.module_options``.
    """
    manifest = _load_backups_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


# Explicit re-exports so ``from quickscale_cli.backups_manifest import ...``
# works for all 7 public symbols without star-import gymnastics.
#
# The functions and constants below are imported at module scope (above) and
# added to ``__all__``.  Python resolves them from the import bindings already
# established — no additional assignment is needed.  They are listed here as
# documentation anchors only.
#
#   normalize_backups_module_options   <- quickscale_core.contracts.module_options
#   validate_backups_env_var_reference <- quickscale_core.contracts.module_options
#   has_legacy_backups_secret_values   <- quickscale_core.contracts.module_options
#   BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION       <- core
#   BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION   <- core
#   DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR      <- core
#   DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR  <- core


def resolve_backups_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge backups options with manifest defaults and normalize overrides.

    Uses the manifest for defaults, then applies the core
    ``normalize_backups_module_options`` helper that handles legacy
    raw-secret key removal.
    """
    defaults = default_backups_module_options()
    normalized = normalize_backups_module_options(options)
    merged = dict(defaults)
    merged.update(normalized)
    return merged
