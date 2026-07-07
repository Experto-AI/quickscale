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
# Public API — manifest surface
# ---------------------------------------------------------------------------

__all__ = [
    # Module wiring spec
    "ModuleWiringSpec",
    # Manifest/resolver types
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
