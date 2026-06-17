"""Billing module manifest-driven configuration adapter.

Replaces the legacy ``billing_contract.py`` by sourcing defaults from the
billing ``module.yml`` manifest and routing normalization and resolution
through the manifest-driven resolver
(:mod:`quickscale_core.manifest.resolver`).

The public API is a drop-in replacement for the old contract file so that
callers in ``apply_command.py`` and ``module_config.py`` can use it without
rewriting their logic.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
from typing import Any

from quickscale_core.manifest.derivation import (
    ModuleDerivationSchema,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.resolver import resolve_module_config

# ---------------------------------------------------------------------------
# Constants
#
# BILLING_SUPPORTED_CURRENCIES is NOT enumerated in module.yml and must remain
# as a module-level Python constant.  The DEFAULT_BILLING_* values match the
# module.yml defaults but are re-declared here so that callers that import
# them by name continue to work without changes.
# ---------------------------------------------------------------------------

DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR = "STRIPE_PUBLISHABLE_KEY"
DEFAULT_BILLING_SECRET_KEY_ENV_VAR = "STRIPE_SECRET_KEY"
DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR = "QUICKSCALE_BILLING_WEBHOOK_SECRET"
DEFAULT_BILLING_CURRENCY = "usd"

BILLING_ENV_VAR_OPTION_NAMES = (
    "publishable_key_env_var",
    "secret_key_env_var",
    "webhook_secret_env_var",
)
BILLING_MODULE_OPTION_KEYS = frozenset(
    {
        "enabled",
        *BILLING_ENV_VAR_OPTION_NAMES,
        "billing_currency",
    }
)

# The ~25-currency tuple is not in module.yml; keep it as a Python constant.
BILLING_SUPPORTED_CURRENCIES = (
    "aud",
    "brl",
    "cad",
    "chf",
    "czk",
    "dkk",
    "eur",
    "gbp",
    "hkd",
    "huf",
    "inr",
    "jpy",
    "mxn",
    "myr",
    "nok",
    "nzd",
    "php",
    "pln",
    "ron",
    "sek",
    "sgd",
    "thb",
    "try",
    "usd",
    "zar",
)

_BILLING_ENV_VAR_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")

# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[3]
_BILLING_MANIFEST_PATH = _REPO_ROOT / "quickscale_modules" / "billing" / "module.yml"


def _load_billing_manifest() -> Any:
    """Load the billing module manifest from ``module.yml``."""
    return load_manifest_from_path(_BILLING_MANIFEST_PATH)


def _build_billing_derivation_schema() -> ModuleDerivationSchema:
    """Build a minimal derivation schema for the billing module.

    Billing has no special normalization or derived settings that the generic
    resolver needs to express — all billing-specific logic (env-var strip,
    currency strip+lowercase) is applied as adapter-level post-steps in the
    functions below.
    """
    return ModuleDerivationSchema(
        module_name="billing",
        version="1",
        option_derivations={},
    )


# ---------------------------------------------------------------------------
# Public API — drop-in replacement for billing_contract.py
# ---------------------------------------------------------------------------


def default_billing_module_options() -> dict[str, Any]:
    """Return the default planner/apply contract for billing.

    Defaults are sourced from the billing ``module.yml`` manifest via
    :meth:`ModuleManifest.get_defaults`.
    """
    manifest = _load_billing_manifest()
    result: dict[str, Any] = manifest.get_defaults()
    return result


def normalize_billing_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Return billing options with normalized env-var and currency values."""
    normalized = dict(options or {})

    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        if option_name in normalized:
            normalized[option_name] = str(normalized[option_name]).strip()

    if "billing_currency" in normalized:
        normalized["billing_currency"] = (
            str(normalized["billing_currency"]).strip().lower()
        )

    return normalized


def resolve_billing_module_options(
    options: Mapping[str, Any] | None,
) -> dict[str, Any]:
    """Merge billing options with defaults and normalized overrides.

    Routes through the manifest-driven resolver for defaults extraction,
    then applies the billing-specific env-var and currency normalization
    that the generic resolver does not cover.
    """
    manifest = _load_billing_manifest()
    schema = _build_billing_derivation_schema()

    result = resolve_module_config(manifest, schema, overrides=dict(options or {}))
    resolved = dict(result.resolved)

    # Apply billing-specific post-resolution normalization (identical to
    # legacy contract behaviour).
    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        resolved[option_name] = str(resolved[option_name]).strip()
    resolved["billing_currency"] = str(resolved["billing_currency"]).strip().lower()

    return resolved


def validate_billing_env_var_reference(option_name: str, value: Any) -> str | None:
    """Validate a billing env-var reference field."""
    candidate = str(value).strip()
    if not candidate:
        return None

    qualified_option = f"modules.billing.{option_name}"
    if not _BILLING_ENV_VAR_NAME_PATTERN.fullmatch(candidate):
        return (
            f"{qualified_option} must be an environment variable name matching "
            "^[A-Z][A-Z0-9_]*$"
        )
    return None


def validate_billing_currency(value: Any) -> str | None:
    """Validate the configured billing currency code."""
    candidate = str(value).strip().lower()
    if not candidate:
        return "modules.billing.billing_currency cannot be blank"

    if candidate not in BILLING_SUPPORTED_CURRENCIES:
        return (
            "modules.billing.billing_currency must be one of the supported "
            "QuickScale billing currency codes: "
            + ", ".join(BILLING_SUPPORTED_CURRENCIES)
        )
    return None


def validate_billing_module_options(options: Mapping[str, Any] | None) -> list[str]:
    """Return validation issues for billing module options."""
    resolved = resolve_billing_module_options(options)
    issues: list[str] = []

    if not isinstance(resolved.get("enabled", True), bool):
        issues.append("modules.billing.enabled must be a boolean")

    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        issue = validate_billing_env_var_reference(
            option_name,
            resolved.get(option_name, ""),
        )
        if issue:
            issues.append(issue)

    currency_issue = validate_billing_currency(resolved.get("billing_currency", ""))
    if currency_issue:
        issues.append(currency_issue)

    return issues


def billing_production_targeted(options: Mapping[str, Any] | None) -> bool:
    """Return whether billing is configured for live runtime ownership."""
    resolved = resolve_billing_module_options(options)
    if not bool(resolved.get("enabled", True)):
        return False

    if validate_billing_currency(resolved.get("billing_currency", "")):
        return False

    for option_name in BILLING_ENV_VAR_OPTION_NAMES:
        candidate = str(resolved.get(option_name, "")).strip()
        if not candidate or validate_billing_env_var_reference(option_name, candidate):
            return False

    return True


__all__ = [
    "BILLING_ENV_VAR_OPTION_NAMES",
    "BILLING_MODULE_OPTION_KEYS",
    "BILLING_SUPPORTED_CURRENCIES",
    "DEFAULT_BILLING_CURRENCY",
    "DEFAULT_BILLING_PUBLISHABLE_KEY_ENV_VAR",
    "DEFAULT_BILLING_SECRET_KEY_ENV_VAR",
    "DEFAULT_BILLING_WEBHOOK_SECRET_ENV_VAR",
    "billing_production_targeted",
    "default_billing_module_options",
    "normalize_billing_module_options",
    "resolve_billing_module_options",
    "validate_billing_currency",
    "validate_billing_env_var_reference",
    "validate_billing_module_options",
]
