"""Tests for the shared runtime redaction helpers (Module Conventions rules 47-48).

One table pins the matcher behaviour both anonymization handlers rely on:
namesake and overlapping addresses, quoted addresses, word-bounded names,
untouched keys, and the single set of replacement sentinels.  The rendered
HTML-escaped spellings are notifications' opt-in and are not the core matcher's.
"""

from __future__ import annotations

import pytest

from quickscale_core.runtime import (
    DELETED_ADDRESS,
    REDACTED,
    redact_names,
    replace_address,
)


def test_replacement_values_are_the_one_set() -> None:
    """Every identity scrub shares the one name sentinel and address factory."""
    assert REDACTED == "[redacted]"
    assert DELETED_ADDRESS(42) == "deleted-42@invalid"
    assert DELETED_ADDRESS("pk-1") == "deleted-pk-1@invalid"


@pytest.mark.parametrize(
    ("value", "address", "expected"),
    [
        ("", "test@example.com", ""),
        ("nothing to redact", "test@example.com", "nothing to redact"),
        # a namesake address merely containing the target is never rewritten
        ("namesake@example.com", "test@example.com", "namesake@example.com"),
        ("protest@example.com", "test@example.com", "protest@example.com"),
        # the complete address is replaced wherever it occurs, case-insensitively
        ("Contact test@example.com now", "test@example.com", "Contact deleted@ now"),
        ("TEST@EXAMPLE.COM", "test@example.com", "deleted@"),
        # internationalized addresses match whole, in any case, and never as a substring
        ("ÉLODIE@EXÄMPLE.COM", "élodie@exämple.com", "deleted@"),
        ("josé.élodie@example.com", "élodie@example.com", "josé.élodie@example.com"),
        # a quoted occurrence keeps its delimiter around the replacement
        ("Reach 'test@example.com' now", "test@example.com", "Reach 'deleted@' now"),
        # a quote that belongs to the address's own local part is not a delimiter
        (
            "Contact 'test@example.com now",
            "'test@example.com",
            "Contact deleted@ now",
        ),
        (
            "Contact ''test@example.com now",
            "'test@example.com",
            "Contact 'deleted@ now",
        ),
    ],
)
def test_replace_address_keeps_other_addresses(
    value: str, address: str, expected: str
) -> None:
    assert replace_address(value, address=address, replacement="deleted@") == expected


@pytest.mark.parametrize(
    ("value", "name", "username", "expected"),
    [
        # word-bounded: a name inside a longer word or a payload key stays put
        ("Billing plan", "Bill", "", "Billing plan"),
        ("billing_details", "Bill", "", "billing_details"),
        # a whole-word name is replaced, case-insensitively
        ("Bill called billing", "Bill", "", "[redacted] called billing"),
        ("BILL", "Bill", "", "[redacted]"),
        # a name is never replaced inside a complete address
        ("bill@example.com", "Bill", "", "bill@example.com"),
        (
            "Ann wrote to ann.smith@example.com",
            "Ann",
            "",
            "[redacted] wrote to ann.smith@example.com",
        ),
        # usernames follow the same word-bounded matcher
        (
            "helios invited invitee@example.com",
            "",
            "helios",
            "[redacted] invited invitee@example.com",
        ),
        ("Ann (ann) Smith", "Ann", "ann", "[redacted] ([redacted]) Smith"),
        # word boundaries are Unicode-aware: a name inside a longer word stays
        ("Anaïs and Ana", "Ana", "", "Anaïs and [redacted]"),
        ("José Pérez", "José", "", "[redacted] Pérez"),
        # empty spellings change nothing
        ("unchanged", "", "", "unchanged"),
        # HTML-escaped spellings are notifications' rendered-store opt-in
        ("Anne O&#x27;Connor", "Anne O'Connor", "", "Anne O&#x27;Connor"),
    ],
)
def test_redact_names_is_word_bounded(
    value: str, name: str, username: str, expected: str
) -> None:
    assert redact_names(value, name=name, username=username) == expected
