"""Tests for the billing planner/apply contract on the manifest engine."""

from pathlib import Path

from quickscale_core.contracts.resolvers import (
    resolve_manifest_module_options,
)
from quickscale_core.manifest.loader import load_manifest_from_path
from quickscale_core.manifest.option_validation import validate_module_options

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULE_MANIFEST_PATH = REPO_ROOT / "quickscale_modules" / "billing" / "module.yml"


def test_billing_defaults_match_manifest_defaults() -> None:
    """Planner/apply defaults should stay aligned with the billing manifest."""
    manifest = load_manifest_from_path(MODULE_MANIFEST_PATH)

    assert resolve_manifest_module_options("billing") == {
        option_name: option.default
        for option_name, option in manifest.mutable_options.items()
    }


def test_resolved_billing_config_normalizes_and_is_stable() -> None:
    """Resolved billing config should normalize whitespace/case and round-trip."""
    resolved = resolve_manifest_module_options(
        "billing",
        {
            "publishable_key_env_var": "  OPS_STRIPE_PUBLISHABLE_KEY  ",
            "secret_key_env_var": " OPS_STRIPE_SECRET_KEY ",
            "webhook_secret_env_var": "  OPS_BILLING_WEBHOOK_SECRET ",
            "currency": " EUR ",
        },
    )

    assert resolved == {
        "enabled": True,
        "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
        "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
        "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
        "currency": "eur",
        "api_rate_limit": "30/hour",
    }
    assert resolve_manifest_module_options("billing", resolved) == resolved


def test_manifest_validation_rejects_invalid_env_var_names() -> None:
    """Malformed billing env-var references must fail validation."""
    manifest = load_manifest_from_path(MODULE_MANIFEST_PATH)
    issues = validate_module_options(
        manifest, {"publishable_key_env_var": "stripe-publishable-key"}
    )

    assert len(issues) == 1
    assert "modules.billing.publishable_key_env_var" in issues[0]
    assert "must match pattern" in issues[0]


def test_manifest_validation_rejects_invalid_currency() -> None:
    """Unsupported billing currency codes must fail validation."""
    manifest = load_manifest_from_path(MODULE_MANIFEST_PATH)
    issues = validate_module_options(manifest, {"currency": "credits"})

    assert len(issues) == 1
    assert "modules.billing.currency" in issues[0]
    assert "must be one of" in issues[0]


def test_apply_next_steps_name_the_required_stripe_endpoint_version(
    capsys,
    tmp_path,
) -> None:
    """The billing wiring output must state the required webhook endpoint version."""
    from unittest.mock import Mock

    from quickscale_cli.commands._finalize import _display_next_steps

    config = Mock()
    config.project.slug = "myapp"
    config.docker.start = False
    config.modules = {
        "billing": Mock(
            options={
                "enabled": True,
                "publishable_key_env_var": "STRIPE_PUBLISHABLE_KEY",
                "secret_key_env_var": "STRIPE_SECRET_KEY",
                "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
                "currency": "usd",
            }
        )
    }

    _display_next_steps(tmp_path, config, False)
    output = capsys.readouterr().out

    assert "# Billing setup" in output
    assert "2026-06-24.dahlia" in output
    assert "OPS_BILLING_WEBHOOK_SECRET" in output
    assert "/billing/webhooks/stripe/" in output
    assert "older API version stops processing" in output
