"""Tests for the billing planner/apply contract helper."""

from pathlib import Path

from quickscale_core.contracts.resolvers import (
    billing_production_targeted,
    default_billing_module_options,
    resolve_billing_module_options,
    validate_billing_module_options,
)
from quickscale_core.manifest.loader import load_manifest_from_path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_MANIFEST_PATH = REPO_ROOT / "quickscale_modules" / "billing" / "module.yml"


def test_default_billing_module_options_match_manifest_defaults() -> None:
    """Planner/apply defaults should stay aligned with the billing manifest."""
    manifest = load_manifest_from_path(MODULE_MANIFEST_PATH)

    assert default_billing_module_options() == {
        option_name: option.default
        for option_name, option in manifest.mutable_options.items()
    }


def test_resolve_billing_module_options_normalizes_and_is_stable() -> None:
    """Resolved billing config should normalize whitespace/case and round-trip."""
    resolved = resolve_billing_module_options(
        {
            "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
            "secret_key_env_var": " OPS_STRIPE_SECRET_KEY ",
            "webhook_secret_env_var": "  OPS_BILLING_WEBHOOK_SECRET ",
            "billing_currency": " EUR ",
        }
    )

    assert resolved == {
        "enabled": True,
        "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
        "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
        "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
        "billing_currency": "eur",
    }
    assert resolve_billing_module_options(resolved) == resolved


def test_validate_billing_module_options_rejects_invalid_env_var_names() -> None:
    """Malformed billing env-var references must fail validation."""
    issues = validate_billing_module_options(
        {"publishable_key_env_var": "stripe-publishable-key"}
    )

    assert issues == [
        "modules.billing.publishable_key_env_var must be an environment variable "
        "name matching ^[A-Z][A-Z0-9_]*$"
    ]


def test_validate_billing_module_options_rejects_invalid_currency() -> None:
    """Unsupported billing currency codes must fail validation."""
    issues = validate_billing_module_options({"billing_currency": "credits"})

    assert len(issues) == 1
    assert "modules.billing.billing_currency" in issues[0]
    assert "supported QuickScale billing currency codes" in issues[0]


def test_billing_production_targeted_requires_valid_runtime_contract() -> None:
    """Production targeting should drop to false when the contract is malformed."""
    assert billing_production_targeted(default_billing_module_options()) is True
    assert billing_production_targeted({"enabled": False}) is False
    assert (
        billing_production_targeted(
            {"publishable_key_env_var": "stripe-publishable-key"}
        )
        is False
    )
