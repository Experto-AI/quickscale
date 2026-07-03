"""QuickScale runtime API facade — public re-export surface for generated-project code.

SA9.3: Pure re-export layer. No behavior change. All symbols are imported from
their canonical internal locations and re-exported so that module code imports
only from ``quickscale_core.runtime`` instead of reaching directly into
``dr_engine``, ``contracts``, or ``manifest`` internals.

Future SA9.4 and SA9.5 will repoint the backups and social module imports here.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# DR adapter surface
# ---------------------------------------------------------------------------
from quickscale_core.dr_engine.adapter import (
    ADAPTER_FUNCTIONS,
    build_database_plan,
    capture_snapshot,
    execute_database_restore,
    fetch_snapshot_report,
    record_verification,
    set_rollback_pin,
    sync_media,
)
from quickscale_core.dr_engine.primitives import BackupError

# ---------------------------------------------------------------------------
# Social-manifest surface: path constants
# ---------------------------------------------------------------------------
from quickscale_core.contracts.module_options import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)

# ---------------------------------------------------------------------------
# Social-manifest surface: resolver
# ---------------------------------------------------------------------------
from quickscale_core.contracts.resolvers import resolve_social_module_options

# ---------------------------------------------------------------------------
# Manifest assembler and resolver
# ---------------------------------------------------------------------------
from quickscale_core.manifest.assembler import assemble_wiring_spec
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
# Module wiring spec
# ---------------------------------------------------------------------------
from quickscale_core.module_wiring import ModuleWiringSpec

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

__all__ = [
    # DR adapter surface
    "ADAPTER_FUNCTIONS",
    "BackupError",
    "build_database_plan",
    "capture_snapshot",
    "execute_database_restore",
    "fetch_snapshot_report",
    "record_verification",
    "set_rollback_pin",
    "sync_media",
    # Manifest/resolver types
    "ModuleWiringSpec",
    "ResolverResult",
    "assemble_wiring_spec",
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
