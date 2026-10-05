"""Shared redaction helpers for account-anonymization handlers.

The account-anonymization handlers rewrite a person's identity inside stored
text and provider payloads.  They all need the same complete-address matcher,
the same word-bounded name matcher, and the same replacement sentinels, so
those live here and are re-exported through the ``quickscale_core.runtime``
facade (Module Conventions rules 47 and 48).

The helpers are pure string functions with no Django dependency: a module that
only scrubs text does not need the ORM to import them.
"""

from __future__ import annotations

import re

__all__ = ["DELETED_ADDRESS", "REDACTED", "redact_names", "replace_address"]

#: Replaces one name or username inside stored text or a provider payload.
REDACTED = "[redacted]"

#: Matches one complete email address.  A replacement is decided per complete
#: match, never per raw substring, so ``test@example.com`` found inside
#: ``protest@example.com`` cannot rewrite another person's address.
_ADDRESS_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+"
)

#: Quote delimiters an address is commonly wrapped in inside free text.
_QUOTE_CHARS = "'\""


def DELETED_ADDRESS(pk: object) -> str:
    """Return the deterministic address a scrubbed account leaves behind.

    Every handler writes the same sentinel for an email address, so a support
    reader or an export can tell which account a scrubbed row belonged to and
    that it was scrubbed.
    """
    return f"deleted-{pk}@invalid"


def replace_address(value: str, *, address: str, replacement: str) -> str:
    """Replace every complete occurrence of *address*, leaving other addresses.

    A token is compared as it stands first, so an address whose own local part
    starts with a quote (``'test@example.com``) still matches; then ordinary
    quote delimiters may be dropped one at a time, so a quoted occurrence
    (``''test@example.com'`` around such an address) matches with the dropped
    quotes preserved around the replacement.  An address merely containing the
    target (``protest@example.com``) never matches.
    """
    if not value:
        return value
    target = address.casefold()

    def replace(match: re.Match[str]) -> str:
        prefix = _identity_form(match.group(0), target)
        if prefix is None:
            return match.group(0)
        return f"{prefix}{replacement}"

    return _ADDRESS_PATTERN.sub(replace, value)


def redact_names(value: str, *, name: str = "", username: str = "") -> str:
    """Replace name and username spellings at word boundaries in *value*.

    A spelling is replaced only as a whole word, so a short name such as
    ``Bill`` never rewrites ``billing_details`` or ``Billing plan``, and never
    inside a complete address, so a name cannot corrupt another person's
    address.  Empty spellings are ignored.
    """
    if not name and not username:
        return value
    parts: list[str] = []
    last = 0
    for match in _ADDRESS_PATTERN.finditer(value):
        parts.append(
            _redact_name_spellings(
                value[last : match.start()], name=name, username=username
            )
        )
        parts.append(match.group(0))
        last = match.end()
    parts.append(_redact_name_spellings(value[last:], name=name, username=username))
    return "".join(parts)


def _redact_name_spellings(value: str, *, name: str, username: str) -> str:
    """Replace each non-empty identity spelling at word boundaries in *value*."""
    for spelling in (name, username):
        if spelling:
            value = re.sub(
                rf"(?<![A-Za-z0-9_]){re.escape(spelling)}(?![A-Za-z0-9_])",
                REDACTED,
                value,
                flags=re.IGNORECASE,
            )
    return value


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
