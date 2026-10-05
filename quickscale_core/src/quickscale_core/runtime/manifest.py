"""
QuickScale runtime API facade — manifest / social re-export surface.

This sub-module exports only the manifest resolver, assembler, social-manifest
surface, renderers, and wiring types that module-owned adapters (notably
``quickscale_modules_social.adapter``) need.  By keeping DR-surface imports in
``runtime.dr``, module-owned adapters avoid pulling in the DR engine at import
time, which previously caused circular-import failures.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Module wiring spec
# ---------------------------------------------------------------------------
from quickscale_core.module_wiring import ModuleWiringSpec as ModuleWiringSpec
from quickscale_core.contracts.module_options import (
    BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION as BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION as BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
)

# ---------------------------------------------------------------------------
# Social-manifest surface: path constants
# ---------------------------------------------------------------------------
from quickscale_core.contracts.module_options import (
    SOCIAL_EMBEDS_PATH as SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH as SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH as SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH as SOCIAL_LINK_TREE_PATH,
)
from quickscale_core.contracts.module_options import (
    STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION as STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION,
    STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION as STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION,
)

# ---------------------------------------------------------------------------
# Manifest resolution surface
# ---------------------------------------------------------------------------
from quickscale_core.contracts.resolvers import (
    resolve_manifest_module_options as resolve_manifest_module_options,
)

# ---------------------------------------------------------------------------
# Manifest assembler and resolver
# ---------------------------------------------------------------------------
from quickscale_core.manifest.assembler import (
    assemble_wiring_spec as assemble_wiring_spec,
)
from quickscale_core.manifest.entry_point import (
    build_generic_manifest_spec as build_generic_manifest_spec,
    load_module_manifest as load_module_manifest,
)
from quickscale_core.manifest.loader import ManifestError as ManifestError
from quickscale_core.manifest.option_validation import (
    validate_module_options as validate_module_options,
)
from quickscale_core.manifest.resolver import ResolverResult as ResolverResult

# ---------------------------------------------------------------------------
# Social-manifest surface: renderers and helpers
# ---------------------------------------------------------------------------
from quickscale_core.manifest.social_manifest import (
    DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST as DEFAULT_SOCIAL_EMBED_PROVIDER_ALLOWLIST,
    DEFAULT_SOCIAL_PROVIDER_ALLOWLIST as DEFAULT_SOCIAL_PROVIDER_ALLOWLIST,
    SOCIAL_LAYOUT_VARIANTS as SOCIAL_LAYOUT_VARIANTS,
    SOCIAL_PAYLOAD_HTTP_STATUS as SOCIAL_PAYLOAD_HTTP_STATUS,
    SOCIAL_PAYLOAD_STATUSES as SOCIAL_PAYLOAD_STATUSES,
    SOCIAL_PROVIDER_CATALOG as SOCIAL_PROVIDER_CATALOG,
    SOCIAL_STATUS_DISABLED as SOCIAL_STATUS_DISABLED,
    SOCIAL_STATUS_EMPTY as SOCIAL_STATUS_EMPTY,
    SOCIAL_STATUS_ENABLED as SOCIAL_STATUS_ENABLED,
    SOCIAL_STATUS_ERROR as SOCIAL_STATUS_ERROR,
    ResolvedSocialTarget as ResolvedSocialTarget,
    SocialProviderMetadata as SocialProviderMetadata,
    get_social_provider_metadata as get_social_provider_metadata,
    load_social_manifest as load_social_manifest,
    normalize_social_provider as normalize_social_provider,
    normalize_social_url as normalize_social_url,
    render_social_managed_init_module as render_social_managed_init_module,
    render_social_managed_urls_module as render_social_managed_urls_module,
    render_social_managed_views_module as render_social_managed_views_module,
    resolve_social_target as resolve_social_target,
    social_payload_status_code as social_payload_status_code,
    social_provider_supports_embeds as social_provider_supports_embeds,
)

# NOTE: this sub-module deliberately declares no ``__all__``.  The combined
# ``quickscale_core.runtime`` facade owns the single hardcoded public-surface
# literal that the SA9.2 compatibility checker resolves; duplicating it here
# would only create a second list to keep in sync.  The repeated ``X as X``
# imports keep every re-export explicitly public for linters.
