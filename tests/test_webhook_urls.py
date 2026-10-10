"""The billing webhook-only URLconf kept mounted while billing is off."""

from __future__ import annotations

from quickscale_modules_billing import webhook_urls


def test_webhook_only_urlconf_mounts_the_stripe_webhook() -> None:
    """Rule 1 (D3): a switched-off billing module keeps this mount."""
    assert webhook_urls.app_name == "quickscale_billing"
    assert [pattern.name for pattern in webhook_urls.urlpatterns] == ["stripe_webhook"]
    assert str(webhook_urls.urlpatterns[0].pattern) == "webhooks/stripe/"
