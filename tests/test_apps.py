"""Tests for billing app registration."""

from importlib import import_module
from pathlib import Path
import sys

import pytest
from django.core.exceptions import ImproperlyConfigured

MODULE_SRC = Path(__file__).resolve().parents[1] / "src"

if str(MODULE_SRC) not in sys.path:
    sys.path.insert(0, str(MODULE_SRC))


def test_app_config_exposes_expected_metadata() -> None:
    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    assert QuickscaleBillingConfig.name == "quickscale_modules_billing"
    assert QuickscaleBillingConfig.label == "quickscale_modules_billing"
    assert QuickscaleBillingConfig.verbose_name == "QuickScale Billing"
    assert QuickscaleBillingConfig.default_auto_field == "django.db.models.BigAutoField"


def test_app_config_ready_is_safe_to_call() -> None:
    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    assert config.ready() is None


def test_app_config_ready_raises_improperly_configured_when_enabled_setting_missing(
    settings,
) -> None:
    """Missing QUICKSCALE_BILLING_ENABLED must raise at startup."""
    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    # Remove the setting to simulate a misconfigured project
    del settings.QUICKSCALE_BILLING_ENABLED

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with pytest.raises(
        ImproperlyConfigured,
        match="QUICKSCALE_BILLING_ENABLED",
    ):
        config.ready()
