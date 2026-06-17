"""Blog module manifest-driven configuration adapter.

Sources defaults from the blog ``module.yml`` manifest and routes
normalization and resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

Option set:

* ``posts_per_page`` — integer, default ``10``
* ``enable_rss``     — boolean, default ``True``
* ``api_rate_limit`` — string, default ``"5/hour"``
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from quickscale_core.manifest.derivation import (
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

# ---------------------------------------------------------------------------
# Constants
#
# DEFAULT_BLOG_API_RATE_LIMIT is re-declared here so callers that reference
# it by name can import it directly from this adapter.  The value must
# match the module.yml default.
# ---------------------------------------------------------------------------

DEFAULT_BLOG_POSTS_PER_PAGE = 10
DEFAULT_BLOG_ENABLE_RSS = True
DEFAULT_BLOG_API_RATE_LIMIT = "5/hour"

BLOG_MODULE_OPTION_KEYS = frozenset(
    {
        "posts_per_page",
        "enable_rss",
        "api_rate_limit",
    }
)

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BLOG_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "blog" / "module.yml"


def _load_blog_manifest() -> Any:
    """Load the blog module manifest from ``module.yml``."""
    return load_manifest_from_path(_BLOG_MANIFEST_PATH)


def _build_blog_derivation_schema() -> ModuleDerivationSchema:
    """Build a derivation schema for the blog module.

    The ``api_rate_limit`` field receives a strip normalization so that
    whitespace-padded user input is cleaned before use, matching the legacy
    ``str(...).strip()`` applied in ``_blog_wiring``.
    """
    return ModuleDerivationSchema(
        module_name="blog",
        version="1",
        option_derivations={
            "api_rate_limit": OptionDerivation(
                option_key="api_rate_limit",
                normalization_rules=[
                    NormalizationRule(
                        source_key="api_rate_limit",
                        target_key="api_rate_limit",
                        rule_type="strip",
                    ),
                ],
            ),
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_blog_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for blog.

    Defaults are sourced from the blog ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.
    """
    manifest = _load_blog_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_blog_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return blog options with normalized field values.

    Mirrors the legacy ``_blog_wiring`` normalization:

    * ``api_rate_limit`` — strip whitespace; fall back to default when blank.
    * ``posts_per_page`` — passed through (coercion happens in resolution).
    * ``enable_rss``     — passed through (coercion happens in resolution).
    """
    normalized = dict(options or {})

    if "api_rate_limit" in normalized:
        stripped = str(normalized["api_rate_limit"]).strip()
        normalized["api_rate_limit"] = (
            stripped if stripped else DEFAULT_BLOG_API_RATE_LIMIT
        )

    return normalized


def resolve_blog_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge blog options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction and
    ``api_rate_limit`` strip normalization, then applies blog-specific
    post-resolution coercions that mirror ``_blog_wiring``:

    * ``posts_per_page`` — ``int()``
    * ``enable_rss``     — ``bool()``
    * ``api_rate_limit`` — strip + fallback to default when blank
    """
    manifest = _load_blog_manifest()
    schema = _build_blog_derivation_schema()

    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Apply blog-specific post-resolution coercions (mirrors _blog_wiring).
    resolved["posts_per_page"] = int(resolved["posts_per_page"])
    resolved["enable_rss"] = bool(resolved["enable_rss"])
    stripped_rate = str(resolved.get("api_rate_limit", "")).strip()
    resolved["api_rate_limit"] = (
        stripped_rate if stripped_rate else DEFAULT_BLOG_API_RATE_LIMIT
    )

    return resolved


def validate_blog_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for blog module options."""
    resolved = resolve_blog_module_options(options)
    issues: list[str] = []

    posts = resolved.get("posts_per_page")
    try:
        if int(posts) <= 0:  # type: ignore[arg-type]
            issues.append("modules.blog.posts_per_page must be a positive integer")
    except (TypeError, ValueError):
        issues.append("modules.blog.posts_per_page must be a positive integer")

    if not isinstance(resolved.get("enable_rss"), bool):
        issues.append("modules.blog.enable_rss must be a boolean")

    rate = str(resolved.get("api_rate_limit", "")).strip()
    if not rate:
        issues.append("modules.blog.api_rate_limit cannot be blank")

    return issues


__all__ = [
    "BLOG_MODULE_OPTION_KEYS",
    "DEFAULT_BLOG_API_RATE_LIMIT",
    "DEFAULT_BLOG_ENABLE_RSS",
    "DEFAULT_BLOG_POSTS_PER_PAGE",
    "default_blog_module_options",
    "normalize_blog_module_options",
    "resolve_blog_module_options",
    "validate_blog_module_options",
]
