"""Tests for billing's account-anonymization executor."""

from __future__ import annotations

import pytest
from django.apps import apps

from quickscale_modules_billing._anonymization import anonymize_account
from quickscale_modules_billing.models import WebhookEvent


@pytest.mark.django_db
def test_anonymize_redacts_the_identity_in_an_identified_payload(user) -> None:
    """The customer's email and name are replaced wherever they appear."""
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-identity",
        event_type="customer.updated",
        payload={
            "data": {
                "object": {
                    "customer_details": {"email": user.email, "name": "Test User"},
                    "receipt_email": user.email.upper(),
                    "metadata": {
                        "note": "Contact Test User about renewal",
                        "names": ["Test User"],
                    },
                }
            }
        },
    )

    anonymize_account(user, user.email, "Test User", user.get_username())

    event.refresh_from_db()
    assert event.payload["data"]["object"]["customer_details"] == {
        "email": "[redacted]",
        "name": "[redacted]",
    }
    assert event.payload["data"]["object"]["receipt_email"] == "[redacted]"
    assert event.payload["data"]["object"]["metadata"] == {
        "note": "Contact [redacted] about renewal",
        "names": ["[redacted]"],
    }


@pytest.mark.django_db
def test_anonymize_leaves_events_without_the_address_untouched(user) -> None:
    """An event that never carried the person's address keeps its record."""
    payload = {"data": {"object": {"customer": "cus_other", "amount": 1900}}}
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-other",
        event_type="charge.succeeded",
        payload=payload,
    )

    anonymize_account(user, user.email, "Test User", user.get_username())

    event.refresh_from_db()
    assert event.payload == payload


@pytest.mark.django_db
def test_anonymize_leaves_a_namesakes_payload_untouched(user) -> None:
    """A same-named customer with a different address is not rewritten."""
    namesake_payload = {
        "data": {
            "object": {
                "customer_details": {
                    "email": "namesake@example.com",
                    "name": "Test User",
                }
            }
        }
    }
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-namesake",
        event_type="customer.updated",
        payload=namesake_payload,
    )

    anonymize_account(user, user.email, "Test User", user.get_username())

    event.refresh_from_db()
    assert event.payload == namesake_payload


@pytest.mark.django_db
def test_anonymize_leaves_an_overlapping_address_untouched(user) -> None:
    """An address merely containing the person's address is not theirs."""
    overlapping_payload = {
        "data": {
            "object": {
                "customer_details": {
                    "email": f"pro{user.email}",
                    "name": "Test User",
                }
            }
        }
    }
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-overlapping",
        event_type="customer.updated",
        payload=overlapping_payload,
    )

    anonymize_account(user, user.email, "Test User", user.get_username())

    event.refresh_from_db()
    assert event.payload == overlapping_payload


@pytest.mark.django_db
def test_anonymize_redacts_a_quoted_address_in_free_text(user) -> None:
    """Quoting in free text does not hide the person's address."""
    payload = {
        "data": {
            "object": {
                "metadata": {"note": f"Contact '{user.email}' now"},
            }
        }
    }
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-quoted",
        event_type="customer.updated",
        payload=payload,
    )

    anonymize_account(user, user.email, "Test User", user.get_username())

    event.refresh_from_db()
    assert (
        event.payload["data"]["object"]["metadata"]["note"]
        == "Contact '[redacted]' now"
    )


@pytest.mark.django_db
def test_anonymize_redacts_an_address_whose_local_part_starts_with_a_quote(
    user,
) -> None:
    """A quote that belongs to the address is not treated as surrounding text."""
    address = f"'{user.username}@example.com"
    payload = {
        "data": {
            "object": {"metadata": {"note": f"Contact {address} and '{address}' now"}}
        }
    }
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-apostrophe-address",
        event_type="customer.updated",
        payload=payload,
    )

    anonymize_account(user, address, "Test User", user.get_username())

    event.refresh_from_db()
    assert (
        event.payload["data"]["object"]["metadata"]["note"]
        == "Contact [redacted] and '[redacted]' now"
    )


@pytest.mark.django_db
def test_anonymize_without_an_address_is_a_no_op(user) -> None:
    """Without the pre-scrub address no event can be identified."""
    payload = {"data": {"object": {"email": user.email}}}
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-empty-identity",
        event_type="customer.updated",
        payload=payload,
    )

    anonymize_account(user, "   ", "Test User", user.get_username())

    event.refresh_from_db()
    assert event.payload == payload


def test_app_config_declares_the_anonymize_handlers_capability() -> None:
    """Billing declares its handler through the core capability mechanism."""
    config = apps.get_app_config("quickscale_billing")

    assert config.anonymize_handlers() == (config,)


@pytest.mark.django_db
def test_declared_treatments_hold_on_a_populated_user(
    user, organization, org_context
) -> None:
    """Every declared treatment matches what the executor does to populated rows."""
    from quickscale_core.runtime import PersonalDataField, PersonalDataTreatment
    from quickscale_modules_billing.models import (
        CreditBalance,
        CreditTransaction,
        Plan,
        PurchaseCheckout,
        Subscription,
    )

    config = apps.get_app_config("quickscale_billing")
    declared = {
        (entry.model_name, entry.field_name): entry.treatment
        for entry in config.personal_data_declarations()
        if isinstance(entry, PersonalDataField)
    }
    assert declared == {
        ("Subscription", "user"): PersonalDataTreatment.KEEP_LINK,
        ("CreditBalance", "user"): PersonalDataTreatment.KEEP_LINK,
        ("CreditTransaction", "user"): PersonalDataTreatment.KEEP_LINK,
        ("PurchaseCheckout", "user"): PersonalDataTreatment.KEEP_LINK,
        ("WebhookEvent", "payload"): PersonalDataTreatment.SCRUB,
    }

    plan = Plan.objects.create(
        name="Anonymization Plan",
        slug="anonymization-plan",
        stripe_price_id="price_anonymization",
        credits_per_period=10,
        price_cents=1000,
    )
    subscription = Subscription.objects.create(
        organization=organization, plan=plan, user=user
    )
    balance = CreditBalance.objects.create(organization=organization, user=user)
    transaction = CreditTransaction.objects.create(
        organization=organization,
        user=user,
        amount=100,
        balance_after=100,
        transaction_type=CreditTransaction.TransactionType.PURCHASE,
    )
    checkout = PurchaseCheckout.objects.create(
        organization=organization, plan=plan, user=user
    )
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-declared-treatments",
        event_type="customer.updated",
        payload={"data": {"object": {"customer_details": {"email": user.email}}}},
    )

    anonymize_account(user, user.email, "Test User", user.get_username())

    for row in (subscription, balance, transaction, checkout):
        row.refresh_from_db()
        assert row.user_id == user.pk
    event.refresh_from_db()
    assert user.email not in str(event.payload)
