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
    assert QuickscaleBillingConfig.label == "quickscale_billing"
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


@pytest.mark.parametrize(
    ("provider_status", "expected_checkout_id"),
    [("expired", "cs_expired"), ("open", "")],
)
def test_org_removal_adapter_returns_only_provider_expired_checkout(
    provider_status: str,
    expected_checkout_id: str,
) -> None:
    from types import SimpleNamespace
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )
    result = SimpleNamespace(
        provider_status=provider_status,
        checkout_session_id="cs_expired",
    )

    with (
        patch(
            "quickscale_modules_billing.services."
            "reconcile_purchase_checkouts_for_removal"
        ) as reconcile_purchases,
        patch(
            "quickscale_modules_billing.services."
            "reconcile_organization_removal_subscription_checkout",
            return_value=result,
        ) as reconcile,
    ):
        checkout_id = config.reconcile_organization_removal_provider_state(
            "org-1",
            persist=False,
        )

    assert checkout_id == expected_checkout_id
    reconcile_purchases.assert_called_once_with("org-1", persist=False)
    reconcile.assert_called_once_with("org-1", persist=False)


def test_account_deletion_adapter_delegates_provider_reconciliation() -> None:
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with patch(
        "quickscale_modules_billing.services."
        "reconcile_account_deletion_subscription_checkout"
    ) as reconcile:
        result = config.reconcile_account_deletion_provider_state("org-2")

    assert result is None
    reconcile.assert_called_once_with("org-2")


def test_account_deletion_adapter_delegates_purchase_reconciliation() -> None:
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with patch(
        "quickscale_modules_billing.services.reconcile_purchase_checkouts_for_removal"
    ) as reconcile:
        result = config.reconcile_account_deletion_purchase_provider_state(
            "org-2",
            "user-1",
        )

    assert result is None
    reconcile.assert_called_once_with(
        "org-2",
        user_id="user-1",
        persist=True,
    )


def test_account_deletion_adapter_delegates_user_reference_detachment() -> None:
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with patch(
        "quickscale_modules_billing.services.detach_account_deletion_user_references",
        return_value=2,
    ) as detach:
        result = config.detach_account_deletion_user_references(
            "user-1",
            ["org-1", "org-2"],
        )

    assert result == 2
    detach.assert_called_once_with("user-1", ["org-1", "org-2"])


def test_account_deletion_adapter_delegates_user_reference_discovery() -> None:
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with patch(
        "quickscale_modules_billing.services."
        "account_deletion_user_reference_organization_ids",
        return_value=["org-1", "org-2"],
    ) as discover:
        result = config.account_deletion_user_reference_organization_ids("user-1")

    assert result == ["org-1", "org-2"]
    discover.assert_called_once_with("user-1")
