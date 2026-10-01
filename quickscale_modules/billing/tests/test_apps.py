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


def test_billing_settings_check_reports_missing_secret_key(
    settings, monkeypatch
) -> None:
    """An enabled billing runtime needs its Stripe secret key."""
    from quickscale_modules_billing.checks import check_billing_settings

    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

    messages = check_billing_settings()

    assert messages
    assert "QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR" in messages[0].msg


def test_billing_settings_check_reports_missing_webhook_secret(
    settings, monkeypatch
) -> None:
    """An enabled billing runtime needs its Stripe webhook signing secret."""
    from quickscale_modules_billing.checks import check_billing_settings

    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.delenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", raising=False)

    messages = check_billing_settings()

    assert messages
    assert "QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR" in messages[0].msg


def test_billing_settings_check_passes_when_disabled(settings, monkeypatch) -> None:
    """A disabled billing runtime needs no Stripe secrets."""
    from quickscale_modules_billing.checks import check_billing_settings

    settings.QUICKSCALE_BILLING_ENABLED = False
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", raising=False)

    assert check_billing_settings() == []


@pytest.mark.django_db
def test_missing_setting_fails_check_migrate_and_runserver(settings) -> None:
    """The registered check fails check, migrate, and runserver alike."""
    from django.core.management import call_command
    from django.core.management.base import SystemCheckError
    from django.core.management.commands import migrate, runserver

    del settings.QUICKSCALE_BILLING_ENABLED

    with pytest.raises(SystemCheckError, match="QUICKSCALE_BILLING_ENABLED"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_BILLING_ENABLED"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_BILLING_ENABLED"):
        runserver.Command().check()


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


def test_app_config_declares_account_deletion_handler_capability() -> None:
    """Rule 4: billing declares its account-deletion handler on its config."""
    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    assert config.account_deletion_handlers() == (config,)
    assert config.account_deletion_handled_app_labels() == ("quickscale_billing",)
    assert config.account_deletion_reconcile_scope() == "cancellation"


def test_app_config_declares_account_deletion_fail_closed_errors() -> None:
    """Account deletion sees BillingError as the blocking error surface."""
    from quickscale_modules_billing.apps import QuickscaleBillingConfig
    from quickscale_modules_billing.exceptions import BillingError

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    assert config.account_deletion_fail_closed_errors() == (BillingError,)


def test_account_deletion_handler_is_collected_by_the_capability_reader() -> None:
    """The declared handler is what account deletion collects and drives."""
    from django.apps import apps

    from quickscale_core.runtime import collect_capabilities

    config = apps.get_app_config("quickscale_billing")

    assert config in collect_capabilities("account_deletion_handlers")


def test_account_deletion_adapter_delegates_mutation_lock() -> None:
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with patch(
        "quickscale_modules_billing.services.subscription_provider_mutation_lock",
        return_value="lock",
    ) as lock:
        result = config.account_deletion_subscription_mutation_lock("org-1")

    assert result == "lock"
    lock.assert_called_once_with("org-1")


def test_account_deletion_adapter_delegates_cancellation() -> None:
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with patch(
        "quickscale_modules_billing.services.cancel_current_subscription",
        return_value="transition",
    ) as cancel:
        result = config.cancel_account_deletion_subscription("user-1", "org-1")

    assert result == "transition"
    cancel.assert_called_once_with(
        "user-1",
        organization="org-1",
        capture_transition=True,
    )


def test_app_config_declares_organization_pricing_url_capability() -> None:
    """Rule 4: billing declares the org-creation pricing URL on its config."""
    from quickscale_core.runtime import collect_capabilities
    from quickscale_modules_billing.apps import QuickscaleBillingConfig
    from quickscale_modules_billing.services import organization_pricing_page_url

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    assert config.organization_pricing_url_hooks() == (organization_pricing_page_url,)
    assert organization_pricing_page_url in collect_capabilities(
        "organization_pricing_url_hooks"
    )


def test_app_config_declares_no_pricing_url_when_switched_off(settings) -> None:
    """A switched-off billing declares no handoff; the consumer falls back."""
    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    settings.QUICKSCALE_BILLING_ENABLED = False
    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    assert config.organization_pricing_url_hooks() == ()


def test_organization_pricing_page_url_resolves_the_pricing_route() -> None:
    """The published hook answers billing's real flat pricing route."""
    from quickscale_modules_billing.services import organization_pricing_page_url

    assert organization_pricing_page_url(None) == "/billing/pricing/"


@pytest.mark.urls("tests.urls_without_billing")
def test_organization_pricing_page_url_raises_when_route_is_not_mounted() -> None:
    """Rule 23: an enabled billing that cannot answer raises, never ``None``."""
    from quickscale_modules_billing.exceptions import BillingConfigurationError
    from quickscale_modules_billing.services import organization_pricing_page_url

    with pytest.raises(BillingConfigurationError, match="pricing route"):
        organization_pricing_page_url(None)


def test_account_deletion_adapter_delegates_resumption() -> None:
    from unittest.mock import patch

    from quickscale_modules_billing.apps import QuickscaleBillingConfig

    config = QuickscaleBillingConfig(
        "quickscale_modules_billing",
        import_module("quickscale_modules_billing"),
    )

    with patch(
        "quickscale_modules_billing.services.resume_current_subscription",
        return_value="subscription",
    ) as resume:
        result = config.resume_account_deletion_subscription(
            "user-1",
            "org-1",
            "transition",
        )

    assert result == "subscription"
    resume.assert_called_once_with(
        "user-1",
        organization="org-1",
        transition="transition",
    )
