"""Orgs module manifest-driven configuration adapter.

Sources defaults from the orgs ``module.yml`` manifest and routes
normalization and resolution through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

Option set mirrors the legacy ``_orgs_wiring`` function in
``module_wiring_specs.py``:

* ``mode`` — string, choices ``{"solo", "saas"}``, default ``"solo"``

ADAPTER/OPTION-RESOLUTION ONLY — conditional URL wiring is deferred to phase
C10.  Do NOT migrate the ``pre_home_url_includes`` / ``url_includes`` logic
here.  Do NOT register this adapter in ``MANIFEST_ADAPTER_REGISTRY`` until
the wiring migration is complete.
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

ORGS_MODE_SOLO = "solo"
ORGS_MODE_SAAS = "saas"
ORGS_MODES = (ORGS_MODE_SOLO, ORGS_MODE_SAAS)

DEFAULT_ORGS_MODE = "solo"

ORGS_MODULE_OPTION_KEYS = frozenset({"mode"})

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_ORGS_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "orgs" / "module.yml"


def _load_orgs_manifest() -> Any:
    """Load the orgs module manifest from ``module.yml``."""
    return load_manifest_from_path(_ORGS_MANIFEST_PATH)


def _build_orgs_derivation_schema() -> ModuleDerivationSchema:
    """Build a derivation schema for the orgs module.

    ``mode`` receives strip + lowercase normalization followed by a choices
    validation rule, mirroring the legacy ``_orgs_wiring`` coercion:
    ``str(...).strip().lower()`` with fallback to ``"solo"`` when the result
    is not in ``{\"solo\", \"saas\"}``.
    """
    return ModuleDerivationSchema(
        module_name="orgs",
        version="1",
        option_derivations={
            "mode": OptionDerivation(
                option_key="mode",
                normalization_rules=[
                    NormalizationRule(
                        source_key="mode",
                        target_key="mode",
                        rule_type="strip",
                    ),
                    NormalizationRule(
                        source_key="mode",
                        target_key="mode",
                        rule_type="lowercase",
                    ),
                ],
                validation_rules=[
                    ValidationRule(
                        option_key="mode",
                        rule_type="choices",
                        allowed_values=list(ORGS_MODES),
                        description=(
                            "modules.orgs.mode must be one of: " + ", ".join(ORGS_MODES)
                        ),
                    ),
                ],
            ),
        },
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_orgs_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for orgs.

    Defaults are sourced from the orgs ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.
    """
    manifest = _load_orgs_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_orgs_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return orgs options with normalized ``mode`` value.

    Mirrors the legacy ``_orgs_wiring`` coercion: strip whitespace and
    lowercase.  The fallback to ``"solo"`` when the value is not a valid
    choice is applied in :func:`resolve_orgs_module_options`.
    """
    normalized = dict(options or {})

    if "mode" in normalized:
        normalized["mode"] = str(normalized["mode"]).strip().lower()

    return normalized


def resolve_orgs_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge orgs options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction and
    ``mode`` strip/lowercase normalization, then applies the legacy fallback:
    if the resolved ``mode`` is not in ``ORGS_MODES``, it is reset to
    ``"solo"`` (matching the ``if mode not in {"solo", "saas"}: mode = "solo"``
    guard in ``_orgs_wiring``).
    """
    manifest = _load_orgs_manifest()
    schema = _build_orgs_derivation_schema()

    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Apply the legacy fallback: invalid mode → "solo".
    mode = str(resolved.get("mode", "")).strip().lower()
    if mode not in ORGS_MODES:
        mode = ORGS_MODE_SOLO
    resolved["mode"] = mode

    return resolved


def validate_orgs_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for orgs module options.

    An invalid mode value is reported as a validation issue.  The resolver
    also silently resets it to ``"solo"``; ``validate_orgs_module_options``
    surfaces the original value so callers can surface user-facing feedback.
    """
    # Validate against the *un-coerced* resolved value so that the choices
    # error is surfaced rather than silently swallowed by the fallback.
    raw_normalized = normalize_orgs_module_options(options)
    defaults = default_orgs_module_options()
    merged: dict[str, Any] = {**defaults, **raw_normalized}

    issues: list[str] = []
    mode = str(merged.get("mode", "")).strip().lower()
    if mode not in ORGS_MODES:
        issues.append("modules.orgs.mode must be one of: " + ", ".join(ORGS_MODES))

    return issues


__all__ = [
    "DEFAULT_ORGS_MODE",
    "ORGS_MODE_SAAS",
    "ORGS_MODE_SOLO",
    "ORGS_MODES",
    "ORGS_MODULE_OPTION_KEYS",
    "default_orgs_module_options",
    "normalize_orgs_module_options",
    "resolve_orgs_module_options",
    "validate_orgs_module_options",
]
