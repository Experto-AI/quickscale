"""
QuickScale runtime API facade — manifest / social re-export surface.

This sub-module exports only the manifest resolver, assembler, social-manifest
path constants, renderers, and wiring types that module-owned adapters
(notably ``quickscale_modules_social.adapter``) need.  By keeping DR-surface
imports in ``runtime.dr``, module-owned adapters avoid pulling in the
DR engine at import time, which previously caused circular-import failures.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Module wiring spec
# ---------------------------------------------------------------------------
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_core.contracts.module_options import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
    NOTIFICATIONS_LIVE_EMAIL_BACKEND,
)

# ---------------------------------------------------------------------------
# Social-manifest surface: path constants
# ---------------------------------------------------------------------------
from quickscale_core.contracts.module_options import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.contracts.module_options import (
    DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR,
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
)

# ---------------------------------------------------------------------------
# Social-manifest surface: resolver
# ---------------------------------------------------------------------------
from quickscale_core.contracts.resolvers import (
    resolve_auth_module_options,
    notifications_runtime_email_backend,
    resolve_backups_module_options,
    resolve_notifications_module_options,
    resolve_orgs_module_options,
    resolve_social_module_options,
    resolve_storage_module_options,
    validate_orgs_module_options,
    validate_storage_module_options,
)

# ---------------------------------------------------------------------------
# Manifest assembler and resolver
# ---------------------------------------------------------------------------
from quickscale_core.manifest.assembler import assemble_wiring_spec
from quickscale_core.manifest.entry_point import build_generic_manifest_spec
from quickscale_core.manifest.loader import ManifestError
from quickscale_core.manifest.resolver import ResolverResult

# ---------------------------------------------------------------------------
# Social-manifest surface: renderers and helpers
# ---------------------------------------------------------------------------
from quickscale_core.manifest.social_manifest import (
    load_social_manifest,
    render_social_managed_init_module,
    render_social_managed_urls_module,
    render_social_managed_views_module,
    social_provider_supports_embeds,
)

# ---------------------------------------------------------------------------
# Public API — manifest surface
# ---------------------------------------------------------------------------

__all__ = [
    # Module wiring spec
    "ModuleWiringSpec",
    "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    "DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR",
    "DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR",
    "DEFAULT_STORAGE_ACCESS_KEY_ID_ENV_VAR",
    "DEFAULT_STORAGE_SECRET_ACCESS_KEY_ENV_VAR",
    "NOTIFICATIONS_LIVE_EMAIL_BACKEND",
    "STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION",
    "STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION",
    # Manifest/resolver types
    "ResolverResult",
    "assemble_wiring_spec",
    "build_generic_manifest_spec",
    "ManifestError",
    "resolve_auth_module_options",
    "notifications_runtime_email_backend",
    "resolve_backups_module_options",
    "resolve_notifications_module_options",
    "resolve_orgs_module_options",
    "resolve_storage_module_options",
    "validate_orgs_module_options",
    "validate_storage_module_options",
    # Social-manifest path constants
    "SOCIAL_EMBEDS_PATH",
    "SOCIAL_INTEGRATION_BASE_PATH",
    "SOCIAL_INTEGRATION_EMBEDS_PATH",
    "SOCIAL_LINK_TREE_PATH",
    # Social-manifest surface
    "load_social_manifest",
    "render_social_managed_init_module",
    "render_social_managed_urls_module",
    "render_social_managed_views_module",
    "resolve_social_module_options",
    "social_provider_supports_embeds",
]
