"""Wiring-parity tests for the manifest-driven billing path (C1).

Compares the legacy ``_billing_wiring`` builder output against the manifest-driven
``build_manifest_wiring_spec("billing", ...)`` for every option case, asserting
full :class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

This module also proves the shared :func:`~wiring_parity.assert_wiring_parity`
harness (C1 deliverable) by using it as the sole assertion mechanism.

Scope
-----
* Default options (empty dict / None)
* Currency override
* Disabled flag
* Custom env-var names
* Combined override case
"""

from __future__ import annotations

import pytest

from wiring_parity import assert_wiring_parity


class TestBillingWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("billing", [{}])

    def test_none_treated_as_empty(self) -> None:
        # None and {} must both yield the same spec as the legacy default.
        assert_wiring_parity("billing", [{}])


class TestBillingWiringParityOverrides:
    """Overridden options must produce equal specs from both paths."""

    def test_currency_eur(self) -> None:
        assert_wiring_parity("billing", [{"billing_currency": "eur"}])

    def test_currency_gbp(self) -> None:
        assert_wiring_parity("billing", [{"billing_currency": "gbp"}])

    def test_currency_jpy(self) -> None:
        assert_wiring_parity("billing", [{"billing_currency": "jpy"}])

    def test_disabled_flag(self) -> None:
        assert_wiring_parity("billing", [{"enabled": False}])

    def test_custom_publishable_key_env_var(self) -> None:
        assert_wiring_parity(
            "billing",
            [{"publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY"}],
        )

    def test_custom_secret_key_env_var(self) -> None:
        assert_wiring_parity(
            "billing",
            [{"secret_key_env_var": "OPS_STRIPE_SECRET_KEY"}],
        )

    def test_custom_webhook_secret_env_var(self) -> None:
        assert_wiring_parity(
            "billing",
            [{"webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET"}],
        )

    def test_combined_overrides(self) -> None:
        assert_wiring_parity(
            "billing",
            [
                {
                    "enabled": False,
                    "billing_currency": "eur",
                    "publishable_key_env_var": "OPS_STRIPE_PUBLISHABLE_KEY",
                    "secret_key_env_var": "OPS_STRIPE_SECRET_KEY",
                    "webhook_secret_env_var": "OPS_BILLING_WEBHOOK_SECRET",
                }
            ],
        )

    @pytest.mark.parametrize(
        "currency",
        [
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
        ],
    )
    def test_every_supported_currency(self, currency: str) -> None:
        """Each supported currency must produce equal specs from both paths."""
        assert_wiring_parity("billing", [{"billing_currency": currency}])


class TestBillingWiringParityBatchCases:
    """Run multiple option cases through the harness in a single call."""

    def test_multiple_cases_in_one_call(self) -> None:
        assert_wiring_parity(
            "billing",
            [
                {},
                {"billing_currency": "eur"},
                {"enabled": False},
                {"enabled": True, "billing_currency": "jpy"},
            ],
        )
