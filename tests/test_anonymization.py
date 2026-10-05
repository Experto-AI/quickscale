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
        "email": f"deleted-{user.pk}@invalid",
        "name": "[redacted]",
    }
    assert (
        event.payload["data"]["object"]["receipt_email"] == f"deleted-{user.pk}@invalid"
    )
    assert event.payload["data"]["object"]["metadata"] == {
        "note": "Contact [redacted] about renewal",
        "names": ["[redacted]"],
    }


@pytest.mark.django_db
def test_anonymize_never_rewrites_payload_keys(user) -> None:
    """Identity-shaped keys keep the payload's structure; only values change.

    An account named ``Bill`` must not turn ``billing_details`` into
    ``[redacted]ing_details``, and a whole-word match inside a value stays.
    """
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-keys",
        event_type="customer.updated",
        payload={
            "data": {
                "object": {
                    "email": user.email,
                    "billing_details": "Billing plan",
                    "customer_id": "cus_1",
                }
            }
        },
    )

    anonymize_account(user, user.email, "Bill", user.get_username())

    event.refresh_from_db()
    assert event.payload["data"]["object"] == {
        "email": f"deleted-{user.pk}@invalid",
        "billing_details": "Billing plan",
        "customer_id": "cus_1",
    }


@pytest.mark.django_db
def test_anonymize_keeps_the_sentinel_when_the_name_matches_it(user) -> None:
    """A name equal to the sentinel's stem cannot rewrite the written address."""
    event = WebhookEvent.objects.create(
        stripe_event_id="evt-sentinel-name",
        event_type="customer.updated",
        payload={
            "data": {
                "object": {
                    "email": user.email,
                    "note": f"Contact {user.email} (Deleted)",
                }
            }
        },
    )

    anonymize_account(user, user.email, "Deleted", user.get_username())

    event.refresh_from_db()
    assert event.payload["data"]["object"] == {
        "email": f"deleted-{user.pk}@invalid",
        "note": f"Contact deleted-{user.pk}@invalid ([redacted])",
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
        == f"Contact 'deleted-{user.pk}@invalid' now"
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
    deleted_address = f"deleted-{user.pk}@invalid"
    assert (
        event.payload["data"]["object"]["metadata"]["note"]
        == f"Contact {deleted_address} and '{deleted_address}' now"
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


@pytest.mark.django_db
def test_anonymize_prefilters_events_before_the_python_walk(user, monkeypatch) -> None:
    """Only rows whose payload mentions the address are loaded and examined."""
    from quickscale_modules_billing import _anonymization as billing_anonymization

    untouched_payload = {"data": {"object": {"customer": "cus_other", "amount": 1900}}}
    untouched = WebhookEvent.objects.create(
        stripe_event_id="evt-prefilter-untouched",
        event_type="charge.succeeded",
        payload=untouched_payload,
    )
    identified_payload = {
        "data": {"object": {"customer_details": {"email": user.email}}}
    }
    identified = WebhookEvent.objects.create(
        stripe_event_id="evt-prefilter-identified",
        event_type="customer.updated",
        payload=identified_payload,
    )
    examined: list[object] = []
    original = billing_anonymization._contains_email

    def spy(value: object, *, email: str) -> bool:
        examined.append(value)
        return original(value, email=email)

    monkeypatch.setattr(billing_anonymization, "_contains_email", spy)

    anonymize_account(user, user.email, "Test User", user.get_username())

    untouched.refresh_from_db()
    identified.refresh_from_db()
    assert untouched.payload == untouched_payload
    # The recursive matcher walks only the pre-filtered row's payload; the
    # untouched event never reaches it.
    assert untouched_payload not in examined
    assert identified_payload in examined


def test_app_config_declares_the_anonymize_handlers_capability() -> None:
    """Billing declares its handler through the core capability mechanism."""
    config = apps.get_app_config("quickscale_billing")

    assert config.anonymize_handlers() == (config,)
