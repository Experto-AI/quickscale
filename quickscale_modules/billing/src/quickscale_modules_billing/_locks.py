"""Advisory locks serializing billing mutations and webhook events.

Implementation detail of :mod:`quickscale_modules_billing.services`;
that module re-exports every name defined here (Module Conventions
rule 28), so existing import paths and test patch targets keep working.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from django.apps import apps
from django.db import connection

from quickscale_modules_billing.exceptions import (
    BillingError,
    BillingWebhookError,
)


def _subscription_provider_mutation_lock_key(organization: Any) -> int:
    organization_pk = getattr(organization, "pk", organization)
    digest = hashlib.sha256(
        f"quickscale_billing:subscription:{organization_pk}".encode()
    ).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@contextmanager
def subscription_provider_mutation_lock(organization: Any) -> Iterator[None]:
    """Serialize app-owned Stripe subscription mutations without a DB transaction."""
    if connection.vendor != "postgresql":
        yield
        return

    lock_key = _subscription_provider_mutation_lock_key(organization)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [lock_key])
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_key])
            (released,) = cursor.fetchone()
        if not released:
            raise BillingError(
                "The Stripe subscription mutation lock was not held at release."
            )


def _webhook_event_processing_lock_key(event_id: str) -> int:
    digest = hashlib.sha256(
        f"quickscale_billing:webhook-event:{event_id}".encode()
    ).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=True)


@contextmanager
def _webhook_event_processing_lock(event_id: str) -> Iterator[None]:
    """Serialize one Stripe event without spanning provider I/O in an atomic."""
    if connection.vendor != "postgresql":
        yield
        return

    lock_key = _webhook_event_processing_lock_key(event_id)
    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_lock(%s)", [lock_key])
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_unlock(%s)", [lock_key])
            (released,) = cursor.fetchone()
        if not released:
            raise BillingWebhookError(
                "The Stripe webhook event processing lock was not held at release."
            )


def _lock_organization_for_billing_mutation(organization: Any) -> Any:
    """Lock the organization row that serializes billing writes with purge."""
    organization_pk = getattr(organization, "pk", organization)
    if organization_pk is None:
        raise BillingWebhookError(
            "Could not resolve an organization for the billing mutation."
        )
    organization_model = apps.get_model(
        "quickscale_orgs",
        "Organization",
    )
    locked_organization = (
        organization_model._default_manager.select_for_update()
        .filter(pk=organization_pk)
        .first()
    )
    if locked_organization is None:
        raise BillingWebhookError(
            "The billing organization no longer exists; the mutation was refused."
        )
    return locked_organization
