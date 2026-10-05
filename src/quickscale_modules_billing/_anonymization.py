"""Account-anonymization executor for billing's personal data.

``QuickscaleBillingConfig.anonymize_account`` delegates here.  Billing's
provenance rows stay attributed to the deleted account (Module Conventions
rule 27), but the stored Stripe webhook payloads are transport records that
can echo the customer's email and name, so the inventory scrubs those values
from the payloads that belong to the person.

An event is the person's only when its stored payload carries the person's
address: the address is unique to one customer, so a namesake customer's event
with the same name and a different address is left untouched.  Inside an
identified payload the address is replaced with the shared
``DELETED_ADDRESS(pk)`` sentinel and the name at word boundaries with the
shared name matcher.  Only values are scrubbed: payload keys are never
rewritten, so an identity-shaped key cannot destroy the payload's structure.
"""

from __future__ import annotations

from typing import Any

from quickscale_core.runtime import DELETED_ADDRESS, redact_names, replace_address

from quickscale_modules_billing.models import WebhookEvent


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    """Redact the person's email and name from the stored Stripe payloads.

    Only payloads that carry the pre-scrub address are rewritten, so another
    customer's event is never touched — including a customer whose address
    merely contains the person's address as a substring.  The rows are
    pre-filtered in SQL on the address before the Python walk, so an event
    that never mentions it is never loaded.  ``original_username`` is unused:
    billing's inventory does not list the username as a stored personal field.
    """
    del original_username
    email = original_email.strip()
    if not email:
        return
    name = original_name.strip()
    replacement = DELETED_ADDRESS(user.pk)
    for event in WebhookEvent.objects.filter(payload__icontains=email).iterator():
        if not _contains_email(event.payload, email=email):
            continue
        redacted = _redact_identity(
            event.payload, email=email, name=name, replacement=replacement
        )
        if redacted != event.payload:
            event.payload = redacted
            event.save(update_fields=["payload"])


def _contains_email(value: Any, *, email: str) -> bool:
    """Return whether a stored payload carries the person's complete address."""
    if isinstance(value, dict):
        return any(
            _contains_email(str(key), email=email) or _contains_email(item, email=email)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_email(item, email=email) for item in value)
    if isinstance(value, str):
        return replace_address(value, address=email, replacement="") != value
    return False


def _redact_identity(value: Any, *, email: str, name: str, replacement: str) -> Any:
    """Return *value* with identity strings replaced, structure preserved.

    Dict keys are part of the payload's schema, so only values are scrubbed;
    an identity-shaped key survives exactly as stored.
    """
    if isinstance(value, dict):
        return {
            key: _redact_identity(item, email=email, name=name, replacement=replacement)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [
            _redact_identity(item, email=email, name=name, replacement=replacement)
            for item in value
        ]
    if isinstance(value, str):
        return _redact_string(value, email=email, name=name, replacement=replacement)
    return value


def _redact_string(value: str, *, email: str, name: str, replacement: str) -> str:
    """Replace the address and the full name inside one string."""
    value = replace_address(value, address=email, replacement=replacement)
    if name:
        value = redact_names(value, name=name)
    return value
