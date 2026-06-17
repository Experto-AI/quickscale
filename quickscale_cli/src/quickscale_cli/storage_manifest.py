"""Storage module manifest-driven configuration adapter.

Sources defaults from the storage ``module.yml`` manifest and routes
normalization and resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

Option set (including the cloud-provider fields used in the nested
STORAGES/AWS_* wiring):

* ``backend``               — string, choices ``{"local", "s3", "r2"}``, default ``"local"``
* ``media_url``             — string, default ``"/media/"`` (normalized)
* ``public_base_url``       — string, default ``""`` (strip)
* ``private_media_enabled`` — boolean (immutable), default ``False``

The remaining cloud-provider fields (``bucket_name``, ``endpoint_url``,
``region_name``, ``access_key_id``, ``secret_access_key``, ``default_acl``,
``querystring_auth``) are included in defaults/resolution but their wiring
into ``STORAGES`` / ``AWS_*`` settings is deferred to phase C11.

ADAPTER/OPTION-RESOLUTION ONLY — the nested STORAGES/AWS_* settings wiring
is handled by the manifest-driven wiring builder, not by this adapter.
This adapter is registered in ``MANIFEST_ADAPTER_REGISTRY`` via
``quickscale_core.manifest.entry_point``.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

from quickscale_core.manifest.derivation import (
    ModuleDerivationSchema,
    NormalizationRule,
    OptionDerivation,
    ValidationRule,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STORAGE_BACKEND_LOCAL = "local"
STORAGE_BACKEND_S3 = "s3"
STORAGE_BACKEND_R2 = "r2"
STORAGE_BACKENDS = (STORAGE_BACKEND_LOCAL, STORAGE_BACKEND_S3, STORAGE_BACKEND_R2)

DEFAULT_STORAGE_BACKEND = "local"
DEFAULT_STORAGE_MEDIA_URL = "/media/"
DEFAULT_STORAGE_PUBLIC_BASE_URL = ""
DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED = False

STORAGE_MODULE_OPTION_KEYS = frozenset(
    {
        "backend",
        "media_url",
        "public_base_url",
        "bucket_name",
        "endpoint_url",
        "region_name",
        "access_key_id",
        "secret_access_key",
        "default_acl",
        "querystring_auth",
        "private_media_enabled",
    }
)

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_STORAGE_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "storage" / "module.yml"


def _load_storage_manifest() -> Any:
    """Load the storage module manifest from ``module.yml``."""
    return load_manifest_from_path(_STORAGE_MANIFEST_PATH)


def _build_storage_derivation_schema() -> ModuleDerivationSchema:
    """Build a derivation schema for the storage module.

    ``backend``        — lowercase + choices validation (no strip — matches
    legacy ``_storage_wiring`` which only calls ``.lower()``).
    ``public_base_url`` — strip (legacy: ``str(...).strip()``).
    Other string fields (bucket_name, endpoint_url, etc.) — strip only.

    ``media_url`` normalization uses a domain-specific hook
    (:func:`_normalize_media_url`) that the generic resolver cannot express,
    so it is applied as a post-resolution step rather than in the schema.
    """
    _strip_keys = (
        "public_base_url",
        "bucket_name",
        "endpoint_url",
        "region_name",
        "access_key_id",
        "secret_access_key",
        "default_acl",
    )
    strip_derivations = {
        key: OptionDerivation(
            option_key=key,
            normalization_rules=[
                NormalizationRule(
                    source_key=key,
                    target_key=key,
                    rule_type="strip",
                ),
            ],
        )
        for key in _strip_keys
    }
    return ModuleDerivationSchema(
        module_name="storage",
        version="1",
        option_derivations={
            "backend": OptionDerivation(
                option_key="backend",
                normalization_rules=[
                    NormalizationRule(
                        source_key="backend",
                        target_key="backend",
                        rule_type="lowercase",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="backend",
                        rule_type="choices",
                        allowed_values=list(STORAGE_BACKENDS),
                        description=(
                            "modules.storage.backend must be one of: "
                            + ", ".join(STORAGE_BACKENDS)
                        ),
                    ),
                ],
            ),
            **strip_derivations,
        },
    )


# ---------------------------------------------------------------------------
# Media URL normalization
# ---------------------------------------------------------------------------


def _normalize_media_url(media_url: str) -> str:
    """Normalize a media URL to have a leading and trailing slash.

    * Strip whitespace.
    * Fall back to ``"/media/"`` if blank.
    * Prepend ``"/"`` when the value starts with neither ``"/"`` nor ``"http"``.
    * Append ``"/"`` if not already trailing.
    """
    normalized = (media_url or "/media/").strip()
    if not normalized.startswith("/") and not normalized.startswith("http"):
        normalized = "/" + normalized
    if not normalized.endswith("/"):
        normalized += "/"
    return normalized


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_storage_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for storage.

    Defaults are sourced from the storage ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults` (covers both mutable and immutable
    options, including ``private_media_enabled``).
    """
    manifest = _load_storage_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_storage_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return storage options with normalized field values.

    Mirrors the normalization applied in the legacy ``_storage_wiring``:

    * ``backend``         — lowercase (no strip — matches legacy
      ``_storage_wiring``); invalid values are NOT yet
      replaced here (that happens in :func:`resolve_storage_module_options`).
    * ``media_url``       — full ``_normalize_media_url`` normalization.
    * ``public_base_url`` — strip whitespace.
    * Other string fields — strip whitespace.
    """
    normalized = dict(options or {})

    if "backend" in normalized:
        normalized["backend"] = str(normalized["backend"]).lower()

    if "media_url" in normalized:
        normalized["media_url"] = _normalize_media_url(str(normalized["media_url"]))

    if "public_base_url" in normalized:
        normalized["public_base_url"] = str(normalized["public_base_url"]).strip()

    for key in (
        "bucket_name",
        "endpoint_url",
        "region_name",
        "access_key_id",
        "secret_access_key",
        "default_acl",
    ):
        if key in normalized:
            normalized[key] = str(normalized[key]).strip()

    return normalized


def resolve_storage_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge storage options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction and
    ``backend`` strip/lowercase normalization, then applies storage-specific
    post-resolution coercions that mirror ``_storage_wiring``:

    * ``backend``               — invalid value → ``"local"`` (fallback)
    * ``media_url``             — ``_normalize_media_url``
    * ``public_base_url``       — strip
    * ``private_media_enabled`` — ``bool()``
    * ``querystring_auth``      — ``bool()``
    * String cloud fields       — strip
    """
    manifest = _load_storage_manifest()
    schema = _build_storage_derivation_schema()

    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Backend: normalize + fallback (mirrors legacy _storage_wiring).
    backend = str(resolved.get("backend", "")).lower()
    if backend not in STORAGE_BACKENDS:
        backend = STORAGE_BACKEND_LOCAL
    resolved["backend"] = backend

    # Media URL: domain-specific normalization.
    resolved["media_url"] = _normalize_media_url(
        str(resolved.get("media_url", DEFAULT_STORAGE_MEDIA_URL))
    )

    # Public base URL: strip.
    resolved["public_base_url"] = str(resolved.get("public_base_url", "")).strip()

    # Boolean fields.
    resolved["private_media_enabled"] = bool(
        resolved.get("private_media_enabled", False)
    )
    resolved["querystring_auth"] = bool(resolved.get("querystring_auth", False))

    # Remaining string cloud-provider fields: strip.
    for key in (
        "bucket_name",
        "endpoint_url",
        "region_name",
        "access_key_id",
        "secret_access_key",
        "default_acl",
    ):
        resolved[key] = str(resolved.get(key, "")).strip()

    return resolved


def validate_storage_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for storage module options.

    An invalid backend value is reported as a validation issue (the resolver
    silently resets it to ``"local"`` in :func:`resolve_storage_module_options`,
    but this function surfaces the original normalized value so callers can
    provide user-facing feedback).
    """
    raw_normalized = normalize_storage_module_options(options)
    defaults = default_storage_module_options()
    merged: dict[str, Any] = {**defaults, **raw_normalized}

    issues: list[str] = []

    backend = str(merged.get("backend", "")).lower()
    if backend not in STORAGE_BACKENDS:
        issues.append(
            "modules.storage.backend must be one of: " + ", ".join(STORAGE_BACKENDS)
        )

    if not isinstance(merged.get("private_media_enabled"), bool):
        issues.append("modules.storage.private_media_enabled must be a boolean")

    return issues


__all__ = [
    "DEFAULT_STORAGE_BACKEND",
    "DEFAULT_STORAGE_MEDIA_URL",
    "DEFAULT_STORAGE_PRIVATE_MEDIA_ENABLED",
    "DEFAULT_STORAGE_PUBLIC_BASE_URL",
    "STORAGE_BACKEND_LOCAL",
    "STORAGE_BACKEND_R2",
    "STORAGE_BACKEND_S3",
    "STORAGE_BACKENDS",
    "STORAGE_MODULE_OPTION_KEYS",
    "default_storage_module_options",
    "normalize_storage_module_options",
    "resolve_storage_module_options",
    "validate_storage_module_options",
]
