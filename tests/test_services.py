"""Tests for billing runtime services."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest
from django.test import override_settings

from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    Subscription,
    WebhookEvent,
)
from quickscale_modules_billing import services as billing_services
from quickscale_modules_billing.services import (
    BillingConfigurationError,
    BillingDisabledError,
    BillingSettingsSnapshot,
    BillingValidationError,
    BillingWebhookError,
    BillingWebhookSignatureError,
    StripeClient,
    credit_user,
    get_or_create_stripe_customer,
    get_stripe_client,
    handle_stripe_event,
)


def _create_plan(*, price_id: str = "price_starter") -> Plan:
    return Plan.objects.create(
        name="Starter",
        slug=f"starter-{price_id}",
        stripe_price_id=price_id,
        credits_per_period=100,
        price_cents=1900,
        currency="usd",
        billing_interval=Plan.BillingInterval.MONTHLY,
    )


def _user_reference(user: Any) -> str:
    return f"{user._meta.label_lower}:{user.pk}"


def _invoice_paid_event(
    *,
    event_id: str,
    invoice_id: str,
    customer_id: str,
    price_id: str,
    billing_reason: str | None = "subscription_cycle",
    user_reference: str | None = None,
) -> dict[str, Any]:
    metadata = {}
    if user_reference:
        metadata["quickscale_user_reference"] = user_reference
    invoice_object: dict[str, Any] = {
        "id": invoice_id,
        "customer": customer_id,
        "subscription": "sub_123",
        "metadata": metadata,
        "lines": {
            "data": [
                {
                    "price": {
                        "id": price_id,
                    }
                }
            ]
        },
    }
    if billing_reason is not None:
        invoice_object["billing_reason"] = billing_reason
    return {
        "id": event_id,
        "type": "invoice.paid",
        "data": {"object": invoice_object},
    }


@dataclass
class FakeStripeClient:
    """Minimal fake Stripe client for billing service tests."""

    customers: list[dict[str, Any]] = field(default_factory=list)
    event: dict[str, Any] | None = None
    construct_error: Exception | None = None
    searched_references: list[str] = field(default_factory=list)
    created_payloads: list[dict[str, Any]] = field(default_factory=list)
    created_customers_by_idempotency_key: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )
    create_requests_by_idempotency_key: dict[str, dict[str, Any]] = field(
        default_factory=dict
    )
    reject_changed_idempotent_payload: bool = False
    construct_calls: list[dict[str, Any]] = field(default_factory=list)

    def search_customers(self, *, user_reference: str) -> list[dict[str, Any]]:
        self.searched_references.append(user_reference)
        return list(self.customers)

    def create_customer(
        self,
        *,
        email: str,
        name: str,
        metadata: dict[str, str],
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        request_payload = {
            "email": email,
            "name": name,
            "metadata": dict(metadata),
        }
        if idempotency_key:
            previous_request_payload = self.create_requests_by_idempotency_key.get(
                idempotency_key
            )
            if (
                self.reject_changed_idempotent_payload
                and previous_request_payload is not None
                and previous_request_payload != request_payload
            ):
                raise BillingWebhookError(
                    "Stripe rejected the changed idempotent create payload."
                )
            self.create_requests_by_idempotency_key.setdefault(
                idempotency_key,
                dict(request_payload),
            )

        if (
            idempotency_key
            and idempotency_key in self.created_customers_by_idempotency_key
        ):
            created_customer = dict(
                self.created_customers_by_idempotency_key[idempotency_key]
            )
        else:
            created_index = len(self.created_payloads) + 1
            customer_id = "cus_created"
            if created_index > 1:
                customer_id = f"cus_created_{created_index}"
            created_customer = {
                "id": customer_id,
                "email": email,
                "name": name,
                "metadata": dict(metadata),
            }
            if idempotency_key:
                self.created_customers_by_idempotency_key[idempotency_key] = dict(
                    created_customer
                )

        self.created_payloads.append(
            {
                **created_customer,
                "idempotency_key": idempotency_key or "",
            }
        )
        return created_customer

    def construct_event(
        self,
        *,
        body: bytes,
        signature: str,
        webhook_secret: str,
    ) -> dict[str, Any]:
        self.construct_calls.append(
            {
                "body": body,
                "signature": signature,
                "webhook_secret": webhook_secret,
            }
        )
        if self.construct_error is not None:
            raise self.construct_error
        assert self.event is not None
        return self.event


def test_billing_settings_snapshot_reads_defaults_and_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("BILLING_PUBLISHABLE", "pk_test_123")
    monkeypatch.setenv("BILLING_SECRET", "sk_test_123")
    monkeypatch.setenv("BILLING_WEBHOOK_SECRET", "whsec_123")

    with override_settings(
        QUICKSCALE_BILLING_ENABLED=False,
        QUICKSCALE_BILLING_PUBLISHABLE_KEY_ENV_VAR="BILLING_PUBLISHABLE",
        QUICKSCALE_BILLING_SECRET_KEY_ENV_VAR="BILLING_SECRET",
        QUICKSCALE_BILLING_WEBHOOK_SECRET_ENV_VAR="BILLING_WEBHOOK_SECRET",
        QUICKSCALE_BILLING_CURRENCY="eur",
    ):
        snapshot = BillingSettingsSnapshot.from_settings()

    assert snapshot.enabled is False
    assert snapshot.billing_currency == "eur"
    assert snapshot.resolve_publishable_key() == "pk_test_123"
    assert snapshot.resolve_secret_key() == "sk_test_123"
    assert snapshot.resolve_webhook_secret() == "whsec_123"


def test_get_stripe_client_requires_secret_key_configuration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)

    with pytest.raises(BillingConfigurationError, match="secret key"):
        get_stripe_client()


def test_get_stripe_client_wraps_missing_sdk(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(
        "quickscale_modules_billing.services.import_module",
        lambda module_name: (_ for _ in ()).throw(ImportError(module_name)),
    )

    with pytest.raises(BillingConfigurationError, match="not installed"):
        get_stripe_client()


def test_get_stripe_client_returns_configured_wrapper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_module = SimpleNamespace(
        api_key="",
        Customer=SimpleNamespace(
            search=lambda **kwargs: {"data": []},
            create=lambda **kwargs: {"id": "cus_created", **kwargs},
        ),
        Webhook=SimpleNamespace(construct_event=lambda **kwargs: {"id": "evt_123"}),
    )
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_123")
    monkeypatch.setattr(
        "quickscale_modules_billing.services.import_module",
        lambda module_name: fake_module,
    )

    stripe_client = get_stripe_client()

    created_customer = stripe_client.create_customer(
        email="",
        name="",
        metadata={"quickscale_user_reference": "auth.user:1"},
        idempotency_key="customer-key",
    )

    assert isinstance(stripe_client, StripeClient)
    assert fake_module.api_key == "sk_test_123"
    assert created_customer == {
        "id": "cus_created",
        "idempotency_key": "customer-key",
        "metadata": {"quickscale_user_reference": "auth.user:1"},
    }


@pytest.mark.django_db
def test_get_or_create_stripe_customer_prefers_existing_subscription(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan()
    Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_existing",
        status=Subscription.Status.ACTIVE,
    )
    monkeypatch.setattr(
        "quickscale_modules_billing.services.get_stripe_client",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError(kwargs)),
    )

    customer_id, created = get_or_create_stripe_customer(user)

    assert customer_id == "cus_existing"
    assert created is False


@pytest.mark.django_db
def test_get_or_create_stripe_customer_searches_remote_metadata_before_create(
    user,
) -> None:
    fake_client = FakeStripeClient(customers=[{"id": "cus_remote"}])

    customer_id, created = get_or_create_stripe_customer(
        user,
        stripe_client=fake_client,
    )

    assert customer_id == "cus_remote"
    assert created is False
    assert fake_client.searched_references == [_user_reference(user)]
    assert fake_client.created_payloads == []


@pytest.mark.django_db
def test_get_or_create_stripe_customer_creates_remote_customer_when_missing(
    user,
) -> None:
    fake_client = FakeStripeClient()

    customer_id, created = get_or_create_stripe_customer(
        user,
        stripe_client=fake_client,
    )

    assert customer_id == "cus_created"
    assert created is True
    assert len(fake_client.created_payloads) == 1
    assert fake_client.created_payloads[0] == {
        "id": "cus_created",
        "email": "",
        "name": "",
        "metadata": {
            "quickscale_user_reference": _user_reference(user),
            "quickscale_user_model": user._meta.label_lower,
            "quickscale_user_pk": str(user.pk),
        },
        "idempotency_key": fake_client.created_payloads[0]["idempotency_key"],
    }
    assert fake_client.created_payloads[0]["idempotency_key"]


@pytest.mark.django_db
def test_get_or_create_stripe_customer_omits_mutable_fields_from_idempotent_create(
    user,
) -> None:
    user.first_name = "Billing"
    user.last_name = "User"
    user.email = "billing-renamed@example.com"
    user.save(update_fields=["first_name", "last_name", "email"])
    fake_client = FakeStripeClient()

    _, created = get_or_create_stripe_customer(
        user,
        stripe_client=fake_client,
    )

    assert created is True
    assert fake_client.created_payloads[0]["email"] == ""
    assert fake_client.created_payloads[0]["name"] == ""
    assert fake_client.created_payloads[0]["metadata"] == {
        "quickscale_user_reference": _user_reference(user),
        "quickscale_user_model": user._meta.label_lower,
        "quickscale_user_pk": str(user.pk),
    }


@pytest.mark.django_db
def test_get_or_create_stripe_customer_reuses_idempotent_create_when_search_stays_stale_after_mutable_fields_change(
    user,
) -> None:
    fake_client = FakeStripeClient(reject_changed_idempotent_payload=True)

    first_customer_id, first_created = get_or_create_stripe_customer(
        user,
        stripe_client=fake_client,
    )
    user.email = "billing-user-renamed@example.com"
    user.first_name = "Renamed"
    user.last_name = "Customer"
    user.username = "billing-user-renamed"
    user.save(update_fields=["email", "first_name", "last_name", "username"])
    second_customer_id, second_created = get_or_create_stripe_customer(
        user,
        stripe_client=fake_client,
    )

    assert first_customer_id == "cus_created"
    assert second_customer_id == first_customer_id
    assert first_created is True
    assert second_created is True
    assert fake_client.searched_references == [
        _user_reference(user),
        _user_reference(user),
    ]
    assert len(fake_client.created_payloads) == 2
    assert {payload["id"] for payload in fake_client.created_payloads} == {
        "cus_created"
    }
    assert {payload["email"] for payload in fake_client.created_payloads} == {""}
    assert {payload["name"] for payload in fake_client.created_payloads} == {""}
    assert (
        fake_client.created_payloads[0]["metadata"]
        == fake_client.created_payloads[1]["metadata"]
    )
    assert fake_client.created_payloads[0]["idempotency_key"]
    assert (
        fake_client.created_payloads[0]["idempotency_key"]
        == fake_client.created_payloads[1]["idempotency_key"]
    )


@pytest.mark.django_db
def test_get_or_create_stripe_customer_rejects_disabled_runtime(user) -> None:
    with override_settings(QUICKSCALE_BILLING_ENABLED=False):
        with pytest.raises(BillingDisabledError, match="disabled"):
            get_or_create_stripe_customer(user, stripe_client=FakeStripeClient())


@pytest.mark.django_db
def test_get_or_create_stripe_customer_rejects_remote_customer_without_id(user) -> None:
    fake_client = FakeStripeClient(customers=[{}])

    with pytest.raises(BillingWebhookError, match="without an id"):
        get_or_create_stripe_customer(user, stripe_client=fake_client)


@pytest.mark.django_db
def test_get_or_create_stripe_customer_rejects_created_customer_without_id(
    user,
) -> None:
    fake_client = FakeStripeClient()
    fake_client.create_customer = lambda **kwargs: {}  # type: ignore[method-assign]

    with pytest.raises(BillingWebhookError, match="did not return an id"):
        get_or_create_stripe_customer(user, stripe_client=fake_client)


@pytest.mark.django_db
def test_credit_user_updates_balance_and_suppresses_duplicate_business_object(
    user,
) -> None:
    first_transaction = credit_user(
        user,
        amount=100,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        description="First credit",
        stripe_event_id="evt_123",
        stripe_object_id="in_123",
        stripe_reference_data={"invoice_id": "in_123"},
    )
    duplicate_transaction = credit_user(
        user,
        amount=100,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        description="Duplicate credit",
        stripe_event_id="evt_456",
        stripe_object_id="in_123",
        stripe_reference_data={"invoice_id": "in_123"},
    )

    balance = CreditBalance.objects.get(user=user)

    assert duplicate_transaction.pk == first_transaction.pk
    assert balance.balance == 100
    assert CreditTransaction.objects.filter(user=user).count() == 1


@pytest.mark.django_db
def test_credit_user_rejects_non_positive_amount(user) -> None:
    with pytest.raises(BillingValidationError, match="greater than zero"):
        credit_user(
            user,
            amount=0,
            transaction_type=CreditTransaction.TransactionType.PLAN,
        )


@pytest.mark.django_db
def test_credit_user_suppresses_duplicate_reference_data_without_object_id(
    user,
) -> None:
    first_transaction = credit_user(
        user,
        amount=75,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_reference_data={"invoice_id": "in_reference"},
    )
    duplicate_transaction = credit_user(
        user,
        amount=75,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_reference_data={"invoice_id": "in_reference"},
    )

    assert duplicate_transaction.pk == first_transaction.pk
    assert CreditBalance.objects.get(user=user).balance == 75


@pytest.mark.django_db
def test_credit_user_records_distinct_invoice_ids_for_same_subscription(user) -> None:
    first_transaction = credit_user(
        user,
        amount=75,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_event_id="evt_invoice_one",
        stripe_object_id="in_invoice_one",
        stripe_reference_data={
            "invoice_id": "in_invoice_one",
            "stripe_customer_id": "cus_same_subscription",
            "stripe_price_id": "price_same_subscription",
            "stripe_subscription_id": "sub_same_subscription",
        },
    )
    second_transaction = credit_user(
        user,
        amount=75,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_event_id="evt_invoice_two",
        stripe_object_id="in_invoice_two",
        stripe_reference_data={
            "invoice_id": "in_invoice_two",
            "stripe_customer_id": "cus_same_subscription",
            "stripe_price_id": "price_same_subscription",
            "stripe_subscription_id": "sub_same_subscription",
        },
    )

    transactions = list(CreditTransaction.objects.filter(user=user).order_by("pk"))

    assert second_transaction.pk != first_transaction.pk
    assert [transaction.stripe_object_id for transaction in transactions] == [
        "in_invoice_one",
        "in_invoice_two",
    ]
    assert CreditBalance.objects.get(user=user).balance == 150


@pytest.mark.django_db
def test_credit_user_suppresses_replayed_reference_data_after_many_intervening_credits(
    user,
) -> None:
    first_transaction = credit_user(
        user,
        amount=75,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_reference_data={"invoice_id": "in_reference_replay"},
    )

    for index in range(26):
        credit_user(
            user,
            amount=5,
            transaction_type=CreditTransaction.TransactionType.PLAN,
            stripe_reference_data={"invoice_id": f"in_intervening_{index}"},
        )

    duplicate_transaction = credit_user(
        user,
        amount=75,
        transaction_type=CreditTransaction.TransactionType.PLAN,
        stripe_reference_data={"invoice_id": "in_reference_replay"},
    )

    assert duplicate_transaction.pk == first_transaction.pk
    assert CreditTransaction.objects.filter(user=user).count() == 27
    assert CreditBalance.objects.get(user=user).balance == 205


@pytest.mark.django_db
def test_handle_stripe_event_credits_subscription_user_and_records_event(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_runtime")
    Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_123",
        stripe_customer_id="cus_runtime",
        status=Subscription.Status.ACTIVE,
    )
    fake_client = FakeStripeClient(
        event=_invoice_paid_event(
            event_id="evt_runtime",
            invoice_id="in_runtime",
            customer_id="cus_runtime",
            price_id=plan.stripe_price_id,
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_runtime")

    result = handle_stripe_event(
        body=b'{"id":"evt_runtime"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    balance = CreditBalance.objects.get(user=user)
    transaction_row = CreditTransaction.objects.get(user=user)
    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_runtime")

    assert result.duplicate is False
    assert result.event_type == "invoice.paid"
    assert result.status == "processed"
    assert balance.balance == 100
    assert transaction_row.stripe_object_id == "in_runtime"
    assert transaction_row.stripe_reference_data == {
        "invoice_id": "in_runtime",
        "stripe_customer_id": "cus_runtime",
        "stripe_price_id": "price_runtime",
        "stripe_subscription_id": "sub_123",
    }
    assert webhook_event.event_type == "invoice.paid"
    assert webhook_event.processed is True
    assert webhook_event.processing_error == ""
    assert fake_client.construct_calls == [
        {
            "body": b'{"id":"evt_runtime"}',
            "signature": "t=1,v1=test-signature",
            "webhook_secret": "whsec_runtime",
        }
    ]


@pytest.mark.django_db
def test_handle_stripe_event_uses_metadata_user_reference_without_subscription(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_metadata")
    fake_client = FakeStripeClient(
        event=_invoice_paid_event(
            event_id="evt_metadata",
            invoice_id="in_metadata",
            customer_id="cus_metadata",
            price_id=plan.stripe_price_id,
            user_reference=_user_reference(user),
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_metadata")

    result = handle_stripe_event(
        body=b'{"id":"evt_metadata"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    transaction_row = CreditTransaction.objects.get(user=user)

    assert result.status == "processed"
    assert transaction_row.stripe_object_id == "in_metadata"
    assert CreditBalance.objects.get(user=user).balance == 100


@pytest.mark.django_db
def test_handle_stripe_event_returns_duplicate_without_second_credit(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_duplicate")
    Subscription.objects.create(
        user=user,
        plan=plan,
        stripe_subscription_id="sub_duplicate",
        stripe_customer_id="cus_duplicate",
        status=Subscription.Status.ACTIVE,
    )
    fake_client = FakeStripeClient(
        event=_invoice_paid_event(
            event_id="evt_duplicate",
            invoice_id="in_duplicate",
            customer_id="cus_duplicate",
            price_id=plan.stripe_price_id,
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_duplicate")

    first_result = handle_stripe_event(
        body=b'{"id":"evt_duplicate"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )
    second_result = handle_stripe_event(
        body=b'{"id":"evt_duplicate"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    assert first_result.status == "processed"
    assert second_result.duplicate is True
    assert second_result.status == "duplicate"
    assert CreditTransaction.objects.filter(user=user).count() == 1
    assert CreditBalance.objects.get(user=user).balance == 100


@pytest.mark.django_db
def test_handle_stripe_event_marks_unknown_types_as_processed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeStripeClient(
        event={
            "id": "evt_unknown",
            "type": "customer.created",
            "data": {"object": {"id": "cus_unknown"}},
        }
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_unknown")

    result = handle_stripe_event(
        body=b'{"id":"evt_unknown"}',
        signature="t=1,v1=test-signature",
        stripe_client=fake_client,
    )

    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_unknown")

    assert result.duplicate is False
    assert result.status == "ignored"
    assert webhook_event.processed is True
    assert CreditTransaction.objects.count() == 0


@pytest.mark.django_db
def test_handle_stripe_event_records_processing_errors_for_retry(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeStripeClient(
        event=_invoice_paid_event(
            event_id="evt_error",
            invoice_id="in_error",
            customer_id="cus_error",
            price_id="price_missing",
            user_reference=_user_reference(user),
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_error")

    with pytest.raises(Exception, match="No billing plan matches Stripe price"):
        handle_stripe_event(
            body=b'{"id":"evt_error"}',
            signature="t=1,v1=test-signature",
            stripe_client=fake_client,
        )

    webhook_event = WebhookEvent.objects.get(stripe_event_id="evt_error")

    assert webhook_event.processed is False
    assert "No billing plan matches Stripe price price_missing." == (
        webhook_event.processing_error
    )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_missing_webhook_secret(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", raising=False)

    with pytest.raises(BillingConfigurationError, match="webhook secret"):
        handle_stripe_event(
            body=b'{"id":"evt_missing_secret"}',
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(
                event={"id": "evt_missing_secret", "type": "invoice.paid"}
            ),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_missing_event_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_missing_id")

    with pytest.raises(BillingWebhookError, match="missing an id"):
        handle_stripe_event(
            body=b"{}",
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(event={"type": "invoice.paid"}),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_missing_event_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_missing_type")

    with pytest.raises(BillingWebhookError, match="missing a type"):
        handle_stripe_event(
            body=b"{}",
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(event={"id": "evt_missing_type"}),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_missing_event_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_missing_object")

    with pytest.raises(BillingWebhookError, match="data.object"):
        handle_stripe_event(
            body=b"{}",
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(
                event={
                    "id": "evt_missing_object",
                    "type": "invoice.paid",
                    "data": {},
                }
            ),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_missing_event_data(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_missing_data")

    with pytest.raises(BillingWebhookError, match="data.object"):
        handle_stripe_event(
            body=b"{}",
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(
                event={
                    "id": "evt_missing_data",
                    "type": "invoice.paid",
                }
            ),
        )


@pytest.mark.django_db
def test_handle_stripe_event_uses_metadata_price_fallback(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_fallback")
    fallback_event = _invoice_paid_event(
        event_id="evt_fallback",
        invoice_id="in_fallback",
        customer_id="cus_fallback",
        price_id=plan.stripe_price_id,
        user_reference=_user_reference(user),
    )
    fallback_event["data"]["object"]["lines"] = {"data": []}
    fallback_event["data"]["object"]["metadata"]["stripe_price_id"] = (
        plan.stripe_price_id
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_fallback")

    result = handle_stripe_event(
        body=b'{"id":"evt_fallback"}',
        signature="t=1,v1=test-signature",
        stripe_client=FakeStripeClient(event=fallback_event),
    )

    assert result.status == "processed"
    assert CreditBalance.objects.get(user=user).balance == 100


@pytest.mark.django_db
def test_handle_stripe_event_rejects_invoice_without_id(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_missing_invoice_id")
    event = _invoice_paid_event(
        event_id="evt_missing_invoice_id",
        invoice_id="in_missing_invoice_id",
        customer_id="",
        price_id=plan.stripe_price_id,
        user_reference=_user_reference(user),
    )
    event["data"]["object"].pop("id")
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_missing_invoice_id",
    )

    with pytest.raises(BillingWebhookError, match="invoice payload is missing an id"):
        handle_stripe_event(
            body=b"{}",
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(event=event),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_missing_billing_price_id(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _invoice_paid_event(
        event_id="evt_missing_price_id",
        invoice_id="in_missing_price_id",
        customer_id="",
        price_id="price_unused",
        user_reference=_user_reference(user),
    )
    event["data"]["object"]["lines"] = {"data": []}
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_missing_price_id")

    with pytest.raises(BillingWebhookError, match="missing a billing price id"):
        handle_stripe_event(
            body=b"{}",
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(event=event),
        )


@pytest.mark.django_db
def test_handle_stripe_event_uses_subscription_details_user_reference(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    plan = _create_plan(price_id="price_subscription_details")
    event = _invoice_paid_event(
        event_id="evt_subscription_details",
        invoice_id="in_subscription_details",
        customer_id="",
        price_id=plan.stripe_price_id,
    )
    event["data"]["object"]["subscription"] = ""
    event["data"]["object"]["subscription_details"] = {
        "metadata": {"quickscale_user_reference": _user_reference(user)}
    }
    monkeypatch.setenv(
        "QUICKSCALE_BILLING_WEBHOOK_SECRET",
        "whsec_subscription_details",
    )

    result = handle_stripe_event(
        body=b'{"id":"evt_subscription_details"}',
        signature="t=1,v1=test-signature",
        stripe_client=FakeStripeClient(event=event),
    )

    transaction_row = CreditTransaction.objects.get(user=user)

    assert result.status == "processed"
    assert transaction_row.stripe_reference_data == {
        "invoice_id": "in_subscription_details",
        "stripe_customer_id": "",
        "stripe_price_id": plan.stripe_price_id,
    }


@pytest.mark.django_db
def test_handle_stripe_event_rejects_multiple_price_ids(
    user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event = _invoice_paid_event(
        event_id="evt_many_prices",
        invoice_id="in_many_prices",
        customer_id="cus_many_prices",
        price_id="price_one",
        user_reference=_user_reference(user),
    )
    event["data"]["object"]["lines"] = {
        "data": [
            {"price": {"id": "price_one"}},
            {"price": {"id": "price_two"}},
        ]
    }
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_many_prices")

    with pytest.raises(BillingWebhookError, match="multiple billing price ids"):
        handle_stripe_event(
            body=b'{"id":"evt_many_prices"}',
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(event=event),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_unresolvable_user_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_plan(price_id="price_unresolvable")
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_unresolvable")

    with pytest.raises(BillingWebhookError, match="Could not resolve a local user"):
        handle_stripe_event(
            body=b'{"id":"evt_unresolvable"}',
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(
                event=_invoice_paid_event(
                    event_id="evt_unresolvable",
                    invoice_id="in_unresolvable",
                    customer_id="cus_unresolvable",
                    price_id="price_unresolvable",
                    user_reference="bad-reference",
                )
            ),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_unknown_model_user_reference(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _create_plan(price_id="price_unknown_model")
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_unknown_model")

    with pytest.raises(BillingWebhookError, match="Could not resolve a local user"):
        handle_stripe_event(
            body=b'{"id":"evt_unknown_model"}',
            signature="t=1,v1=test-signature",
            stripe_client=FakeStripeClient(
                event=_invoice_paid_event(
                    event_id="evt_unknown_model",
                    invoice_id="in_unknown_model",
                    customer_id="",
                    price_id="price_unknown_model",
                    user_reference="missing.user:1",
                )
            ),
        )


@pytest.mark.django_db
def test_handle_stripe_event_rejects_invalid_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeStripeClient(
        construct_error=BillingWebhookSignatureError("Webhook signature is invalid.")
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_invalid")

    with pytest.raises(BillingWebhookSignatureError, match="invalid"):
        handle_stripe_event(
            body=b'{"id":"evt_invalid"}',
            signature="t=1,v1=invalid",
            stripe_client=fake_client,
        )

    assert WebhookEvent.objects.count() == 0


@pytest.mark.django_db
def test_handle_stripe_event_rejects_disabled_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_client = FakeStripeClient(
        event=_invoice_paid_event(
            event_id="evt_disabled",
            invoice_id="in_disabled",
            customer_id="cus_disabled",
            price_id="price_disabled",
        )
    )
    monkeypatch.setenv("QUICKSCALE_BILLING_WEBHOOK_SECRET", "whsec_disabled")

    with override_settings(QUICKSCALE_BILLING_ENABLED=False):
        with pytest.raises(BillingDisabledError, match="disabled"):
            handle_stripe_event(
                body=b'{"id":"evt_disabled"}',
                signature="t=1,v1=test-signature",
                stripe_client=fake_client,
            )

    assert WebhookEvent.objects.count() == 0


def test_stripe_client_construct_event_maps_signature_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stripe_module = SimpleNamespace(
        Webhook=SimpleNamespace(
            construct_event=lambda **kwargs: (_ for _ in ()).throw(
                ValueError("invalid payload")
            )
        )
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")
    monkeypatch.delenv("unused", raising=False)

    with pytest.raises(Exception, match="Webhook payload is invalid"):
        stripe_client.construct_event(
            body=b"{}",
            signature="t=1,v1=test-signature",
            webhook_secret="whsec_test",
        )


def test_stripe_client_search_customers_uses_mapping_response() -> None:
    stripe_module = SimpleNamespace(
        api_key="",
        Customer=SimpleNamespace(
            search=lambda **kwargs: {"data": [{"id": "cus_search"}]},
            create=lambda **kwargs: {"id": "unused"},
        ),
        Webhook=SimpleNamespace(construct_event=lambda **kwargs: {"id": "unused"}),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")

    customers = stripe_client.search_customers(user_reference="auth.user:1")

    assert customers == [{"id": "cus_search"}]
    assert stripe_module.api_key == "sk_test"


def test_stripe_client_create_customer_includes_name_and_email() -> None:
    stripe_module = SimpleNamespace(
        api_key="",
        Customer=SimpleNamespace(
            search=lambda **kwargs: {"data": []},
            create=lambda **kwargs: {"id": "cus_created", **kwargs},
        ),
        Webhook=SimpleNamespace(construct_event=lambda **kwargs: {"id": "unused"}),
    )
    stripe_client = StripeClient(stripe_module=stripe_module, api_key="sk_test")

    created_customer = stripe_client.create_customer(
        email="billing-user@example.com",
        name="Billing User",
        metadata={"quickscale_user_reference": "auth.user:1"},
        idempotency_key="customer-key",
    )

    assert created_customer == {
        "id": "cus_created",
        "email": "billing-user@example.com",
        "name": "Billing User",
        "idempotency_key": "customer-key",
        "metadata": {"quickscale_user_reference": "auth.user:1"},
    }
    assert stripe_module.api_key == "sk_test"


def test_display_name_for_user_prefers_full_name_when_available() -> None:
    user = SimpleNamespace(
        username="billing-user",
        email="billing-user@example.com",
        get_full_name=lambda: "Billing User",
    )

    assert billing_services._display_name_for_user(user) == "Billing User"


def test_display_name_for_user_falls_back_to_email_when_full_name_is_blank() -> None:
    user = SimpleNamespace(
        username="",
        email="fallback@example.com",
        get_full_name=lambda: "",
    )

    assert billing_services._display_name_for_user(user) == "fallback@example.com"


def test_stripe_client_construct_event_returns_normalized_mapping() -> None:
    stripe_client = StripeClient(
        stripe_module=SimpleNamespace(
            Webhook=SimpleNamespace(
                construct_event=lambda **kwargs: {
                    "id": "evt_constructed",
                    "type": "invoice.paid",
                }
            )
        ),
        api_key="sk_test",
    )

    event = stripe_client.construct_event(
        body=b"{}",
        signature="t=1,v1=test-signature",
        webhook_secret="whsec_test",
    )

    assert event == {
        "id": "evt_constructed",
        "type": "invoice.paid",
    }


def test_stripe_client_construct_event_rejects_blank_signature() -> None:
    stripe_client = StripeClient(
        stripe_module=SimpleNamespace(
            Webhook=SimpleNamespace(construct_event=lambda **kwargs: {"id": "unused"})
        ),
        api_key="sk_test",
    )

    with pytest.raises(BillingWebhookSignatureError, match="invalid"):
        stripe_client.construct_event(
            body=b"{}",
            signature="",
            webhook_secret="whsec_test",
        )


def test_stripe_client_construct_event_maps_signature_verification_exception() -> None:
    class SignatureVerificationError(Exception):
        pass

    stripe_client = StripeClient(
        stripe_module=SimpleNamespace(
            Webhook=SimpleNamespace(
                construct_event=lambda **kwargs: (_ for _ in ()).throw(
                    SignatureVerificationError("bad sig")
                )
            )
        ),
        api_key="sk_test",
    )

    with pytest.raises(BillingWebhookSignatureError, match="invalid"):
        stripe_client.construct_event(
            body=b"{}",
            signature="t=1,v1=bad",
            webhook_secret="whsec_test",
        )


def test_stripe_client_construct_event_maps_generic_sdk_errors() -> None:
    stripe_client = StripeClient(
        stripe_module=SimpleNamespace(
            Webhook=SimpleNamespace(
                construct_event=lambda **kwargs: (_ for _ in ()).throw(
                    RuntimeError("provider exploded")
                )
            )
        ),
        api_key="sk_test",
    )

    with pytest.raises(BillingWebhookError, match="provider exploded"):
        stripe_client.construct_event(
            body=b"{}",
            signature="t=1,v1=bad",
            webhook_secret="whsec_test",
        )
