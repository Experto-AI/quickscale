"""Control cases for rules 47 and 48 (anonymization redaction)."""

from __future__ import annotations

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _golden_module,
    _violations,
    _with_files,
)

_BILLING_HANDLER = '''\
"""Billing-style anonymization handler."""

import re
from typing import Any

REDACTED = "[redacted]"

_ADDRESS_PATTERN = re.compile(
    r"[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+"
)


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    value = "Contact Test User"
    value = re.sub(re.escape(original_name), REDACTED, value, flags=re.IGNORECASE)
'''

_ESCAPED_ADDRESS_HANDLER = '''\
"""Handler whose module-level pattern is the entity-aware escaped tokenizer."""

import re
from typing import Any

_ADDRESS_OR_ESCAPED_PATTERN = re.compile(
    r"(?:(?:&[A-Za-z0-9#]+;)|[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-])+"
    r"@[A-Za-z0-9-]+(?:\\.[A-Za-z0-9-]+)+"
)


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    del user, original_email, original_name, original_username
'''

_USERNAME_HANDLER = '''\
"""Handler holding the unique username candidate, not an address sentinel."""

from typing import Any


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    candidate = f"deleted-{user.pk}"
    candidate = f"deleted-{user.pk}-1"
    del candidate, original_email, original_name, original_username
'''

_SCRUB_APPS = '''\
"""App config delegating to the old entry-point name."""

from typing import Any

from django.apps import AppConfig


class QuickscaleDemoConfig(AppConfig):
    name = "quickscale_modules_demo"
    label = "quickscale_demo"

    def anonymize_account(
        self,
        user: Any,
        original_email: str,
        original_name: str,
        original_username: str,
    ) -> None:
        from quickscale_modules_demo import _anonymization

        _anonymization.scrub_account(
            user, original_email, original_name, original_username
        )
'''


def test_rule_47_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_47_redaction, module) == []

    billing_style = _with_files(module, **{"_anonymization.py": _BILLING_HANDLER})
    messages = _violations(checker.rule_47_redaction, billing_style)
    assert any("no word boundary" in message for message in messages)
    assert any("complete-address pattern" in message for message in messages)

    entity_aware = _with_files(module, **{"_anonymization.py": _ESCAPED_ADDRESS_HANDLER})
    assert _violations(checker.rule_47_redaction, entity_aware) == []


def test_rule_48_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_48_replacement_values, module) == []

    sentinel = _with_files(module, **{"_anonymization.py": _BILLING_HANDLER})
    sentinel_messages = _violations(checker.rule_48_replacement_values, sentinel)
    assert any("sentinel" in message for message in sentinel_messages)

    deleted = _with_files(
        module,
        **{
            "_anonymization.py": (
                "def anonymize_account(user: object, *args: object) -> None:\n"
                '    address = f"deleted-{user.pk}@invalid"\n'
                "    del address, args\n"
            )
        },
    )
    assert any(
        "sentinel" in message
        for message in _violations(checker.rule_48_replacement_values, deleted)
    )

    username = _with_files(module, **{"_anonymization.py": _USERNAME_HANDLER})
    assert _violations(checker.rule_48_replacement_values, username) == []

    scrub_apps = _with_files(module, apps=_SCRUB_APPS)
    assert any(
        "delegate to _anonymization.anonymize_account" in message
        for message in _violations(checker.rule_48_replacement_values, scrub_apps)
    )
