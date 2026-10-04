"""Account-anonymization executor for billing's personal data.

``QuickscaleBillingConfig.anonymize_account`` delegates here.  Billing's
provenance rows stay attributed to the deleted account (Module Conventions
rule 27), but the stored Stripe webhook payloads are transport records that
can echo the customer's email and name, so the inventory scrubs those values
from the payloads that belong to the person.

An event is the person's only when its stored payload carries the person's
address: the address is unique to one customer, so a namesake customer's event
with the same name and a different address is left untouched.  Inside an
identified payload the address is replaced wherever it occurs and the name is
replaced wherever it occurs, including inside longer free-text values.
"""

from __future__ import annotations

import re
from typing import Any

from quickscale_modules_billing.models import WebhookEvent

#: Replaces one identity value inside a stored provider payload.
REDACTED = "[redacted]"

#: Matches one complete email address.  A replacement is decided per complete
#: match, never per raw substring, so ``test@example.com`` found inside
#: ``protest@example.com`` cannot rewrite the other customer's address.
_ADDRESS_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
)

#: Quote delimiters an address is commonly wrapped in inside free text.
_QUOTE_CHARS = "'\""


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    """Redact the person's email and name from the stored Stripe payloads.

    Only payloads that carry the pre-scrub address are rewritten, so another
    customer's event is never touched — including a customer whose address
    merely contains the person's address as a substring.  ``user`` and
    ``original_username`` are unused: the payload, not a user link or username,
    is the record searched.
    """
    del user, original_username
    email = original_email.strip()
    if not email:
        return
    name = original_name.strip()
    for event in WebhookEvent.objects.all().iterator():
        if not _contains_email(event.payload, email=email):
            continue
        redacted = _redact_identity(event.payload, email=email, name=name)
        if redacted != event.payload:
            event.payload = redacted
            event.save(update_fields=["payload"])


def _complete_addresses(value: str) -> list[str]:
    """Return every complete email address inside one stored string."""
    return _ADDRESS_PATTERN.findall(value)


def _identity_form(token: str, target: str) -> str | None:
    """Return the quote prefix under which *token* is *target*, or ``None``.

    A quoted occurrence adds a delimiter quote in front of the address, and an
    address may itself start with a quote, so the token is compared after
    dropping zero, one, or more leading quote delimiters; the dropped prefix
    is returned so a replacement can keep the quoting.  Trailing quotes are
    outside the domain-ending token and stay in the surrounding text.
    """
    for count in range(len(token) + 1):
        prefix = token[:count]
        if any(char not in _QUOTE_CHARS for char in prefix):
            return None
        if token[count:].casefold() == target:
            return prefix
    return None


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
        target = email.casefold()
        return any(
            _identity_form(address, target) is not None
            for address in _complete_addresses(value)
        )
    return False


def _replace_addresses(value: str, *, email: str, replacement: str) -> str:
    """Replace every complete occurrence of *email*, leaving other addresses.

    A token is compared as it stands first, so an address whose own local part
    starts with a quote (``'test@example.com``) still matches; then ordinary
    quote delimiters may be dropped one at a time, so a quoted occurrence
    (``''test@example.com'`` around such an address) matches with the dropped
    quotes preserved around the replacement.  An address merely containing the
    target (``protest@example.com``) never matches.
    """
    if not value:
        return value
    target = email.casefold()

    def replace(match: re.Match[str]) -> str:
        prefix = _identity_form(match.group(0), target)
        if prefix is None:
            return match.group(0)
        return f"{prefix}{replacement}"

    return _ADDRESS_PATTERN.sub(replace, value)


def _redact_identity(value: Any, *, email: str, name: str) -> Any:
    """Return *value* with identity strings replaced, structure preserved."""
    if isinstance(value, dict):
        return {
            _redact_string(str(key), email=email, name=name): _redact_identity(
                item, email=email, name=name
            )
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_identity(item, email=email, name=name) for item in value]
    if isinstance(value, str):
        return _redact_string(value, email=email, name=name)
    return value


def _redact_string(value: str, *, email: str, name: str) -> str:
    """Replace the address and the full name inside one string."""
    value = _replace_addresses(value, email=email, replacement=REDACTED)
    if name:
        value = re.sub(re.escape(name), REDACTED, value, flags=re.IGNORECASE)
    return value
