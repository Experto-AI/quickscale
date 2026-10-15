"""
Behavioral controls for the ``rules_redaction`` split (SA268).

Rules 47 and 48's anonymization-handler mechanics live in the private sibling
(``_redaction_handlers``) behind the ``rules_redaction`` facade.  SA268 has
closed, so SA279 retired the pre-split surface pins; these controls keep the
split's structural invariants and the exact ordered findings of representative
corpora captured from the pre-split module, so a later change cannot silently
drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _redaction_handlers,
    rules_redaction,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_redaction_handlers": _redaction_handlers,
}


CLEAN_HANDLER = '''\
"""Demo anonymization handler."""

from typing import Any

from quickscale_core.runtime import DELETED_ADDRESS, REDACTED


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    user.email = DELETED_ADDRESS(user.pk)
    user.name = REDACTED
    del original_email, original_name, original_username
'''

BILLING_HANDLER = '''\
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

ESCAPED_ADDRESS_HANDLER = '''\
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

USERNAME_HANDLER = '''\
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

DELETED_ADDRESS_HANDLER = """\
def anonymize_account(user: object, *args: object) -> None:
    address = f"deleted-{user.pk}@invalid"
    del address, args
"""

MISSING_ENTRY_POINT_HANDLER = '''\
"""Handler without the entry point."""

from typing import Any


def scrub_account(user: Any, *args: Any) -> None:
    del user, args
'''

SENTINEL_DOCSTRING_HANDLER = '''\
"""[redacted]"""

from typing import Any


def anonymize_account(user: Any, *args: Any) -> None:
    del user, args
'''

SUBSTITUTION_TWICE_HANDLER = '''\
"""Handler with two substring substitutions."""

import re
from typing import Any


def anonymize_account(
    user: Any,
    original_email: str,
    original_name: str,
    original_username: str,
) -> None:
    value = "Contact Test User"
    value = re.sub(re.escape(original_name), "RED", value, flags=re.IGNORECASE)
    value = re.sub(re.escape(original_email), "RED", value, flags=re.IGNORECASE)
'''

ENTITY_PATTERN_ONLY_HANDLER = '''\
"""Handler with only an entity-aware module-level pattern."""

import re
from typing import Any

_ESCAPED = re.compile(r"(?:&[A-Za-z0-9#]+;)+@")


def anonymize_account(user: Any, *args: Any) -> None:
    del user, args
'''

NON_ADDRESS_PATTERN_HANDLER = '''\
"""Handler whose module-level pattern is not an address pattern."""

import re
from typing import Any

_DIGITS = re.compile(r"[0-9]+")


def anonymize_account(user: Any, *args: Any) -> None:
    del user, args
'''

ANNOTATED_PATTERN_HANDLER = '''\
"""Handler with an annotated module-level complete-address pattern."""

import re
from typing import Any

_ADDRESS_PATTERN: re.Pattern[str] = re.compile(r"[^@]+@[^@]+")


def anonymize_account(user: Any, *args: Any) -> None:
    del user, args
'''

CLEAN_APPS_IMPORT = '''\
"""App config delegating through the package import."""

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

        _anonymization.anonymize_account(
            user, original_email, original_name, original_username
        )
'''

PLAIN_IMPORT_INSIDE_METHOD = '''\
"""App config delegating through a plain module import inside the method."""

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
        import quickscale_modules_demo._anonymization as scrubber

        scrubber.anonymize_account(
            user, original_email, original_name, original_username
        )
'''

WRONG_NAME_PLAIN_IMPORT = '''\
"""App config delegating through a plain import to the wrong name."""

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
        import quickscale_modules_demo._anonymization as scrubber

        scrubber.scrub_account(user, original_email, original_name, original_username)
'''

MODULE_LEVEL_PLAIN_IMPORT = '''\
"""App config delegating through a module-level plain import."""

from typing import Any

from django.apps import AppConfig

import quickscale_modules_demo._anonymization as scrubber


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
        scrubber.anonymize_account(
            user, original_email, original_name, original_username
        )
'''

SCRUB_APPS = '''\
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


def _handler(source: str, name: str = "demo") -> Module:
    return _with_files(_golden_module(name), **{"_anonymization.py": source})


def _apps(source: str, name: str = "demo") -> Module:
    return _with_files(_golden_module(name), apps=source)


def _without_apps(name: str = "demo") -> Module:
    module = _golden_module(name)
    return replace(
        module,
        files={key: value for key, value in module.files.items() if key != "apps.py"},
    )


def _two_anonymization_modules() -> tuple[Module, Module]:
    return (
        _with_files(_golden_module("demo"), **{"_anonymization.py": BILLING_HANDLER}),
        _with_files(
            _golden_module("blog"),
            **{"_anonymization.py": DELETED_ADDRESS_HANDLER},
            apps=SCRUB_APPS.replace("demo", "blog"),
        ),
    )


CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    "clean_handler": lambda: _corpus(_handler(CLEAN_HANDLER)),
    "billing_handler": lambda: _corpus(_handler(BILLING_HANDLER)),
    "escaped_address_handler": lambda: _corpus(_handler(ESCAPED_ADDRESS_HANDLER)),
    "username_handler": lambda: _corpus(_handler(USERNAME_HANDLER)),
    "deleted_address_handler": lambda: _corpus(_handler(DELETED_ADDRESS_HANDLER)),
    "missing_entry_point": lambda: _corpus(_handler(MISSING_ENTRY_POINT_HANDLER)),
    "sentinel_docstring": lambda: _corpus(_handler(SENTINEL_DOCSTRING_HANDLER)),
    "substitution_twice": lambda: _corpus(_handler(SUBSTITUTION_TWICE_HANDLER)),
    "entity_pattern_only": lambda: _corpus(_handler(ENTITY_PATTERN_ONLY_HANDLER)),
    "non_address_pattern": lambda: _corpus(_handler(NON_ADDRESS_PATTERN_HANDLER)),
    "annotated_pattern": lambda: _corpus(_handler(ANNOTATED_PATTERN_HANDLER)),
    "clean_apps_import": lambda: _corpus(_apps(CLEAN_APPS_IMPORT)),
    "plain_import_inside_method": lambda: _corpus(_apps(PLAIN_IMPORT_INSIDE_METHOD)),
    "wrong_name_plain_import": lambda: _corpus(_apps(WRONG_NAME_PLAIN_IMPORT)),
    "module_level_plain_import": lambda: _corpus(_apps(MODULE_LEVEL_PLAIN_IMPORT)),
    "scrub_apps": lambda: _corpus(_apps(SCRUB_APPS)),
    "no_apps": lambda: _corpus(_without_apps()),
    "two_modules_order": lambda: _corpus(*_two_anonymization_modules()),
}

#: (case, detector, expected findings) captured from the pre-split module;
#: each list is exact, so order, wording, and duplicate findings are all
#: pinned.
EXACT_FINDINGS = (
    ("clean", "rule_47_redaction", ()),
    ("clean", "rule_48_replacement_values", ()),
    ("clean_handler", "rule_47_redaction", ()),
    ("clean_handler", "rule_48_replacement_values", ()),
    (
        "billing_handler",
        "rule_47_redaction",
        (
            "rule 47: demo: _anonymization.py:20: substitutes an identity with re.escape and no "
            "word boundary",
            "rule 47: demo: _anonymization.py:8: declares a module-level complete-address pattern "
            "instead of using core's matcher",
        ),
    ),
    (
        "billing_handler",
        "rule_48_replacement_values",
        (
            "rule 48: demo: _anonymization.py:6: spells a replacement sentinel instead of "
            "importing it from core",
        ),
    ),
    ("escaped_address_handler", "rule_47_redaction", ()),
    ("escaped_address_handler", "rule_48_replacement_values", ()),
    ("username_handler", "rule_47_redaction", ()),
    ("username_handler", "rule_48_replacement_values", ()),
    ("deleted_address_handler", "rule_47_redaction", ()),
    (
        "deleted_address_handler",
        "rule_48_replacement_values",
        (
            "rule 48: demo: _anonymization.py:2: spells a replacement sentinel instead of "
            "importing it from core",
        ),
    ),
    ("missing_entry_point", "rule_47_redaction", ()),
    (
        "missing_entry_point",
        "rule_48_replacement_values",
        ("rule 48: demo: _anonymization.py has no anonymize_account entry point",),
    ),
    ("sentinel_docstring", "rule_47_redaction", ()),
    ("sentinel_docstring", "rule_48_replacement_values", ()),
    (
        "substitution_twice",
        "rule_47_redaction",
        (
            "rule 47: demo: _anonymization.py:14: substitutes an identity with re.escape and no "
            "word boundary",
            "rule 47: demo: _anonymization.py:15: substitutes an identity with re.escape and no "
            "word boundary",
        ),
    ),
    ("substitution_twice", "rule_48_replacement_values", ()),
    ("entity_pattern_only", "rule_47_redaction", ()),
    ("entity_pattern_only", "rule_48_replacement_values", ()),
    ("non_address_pattern", "rule_47_redaction", ()),
    ("non_address_pattern", "rule_48_replacement_values", ()),
    (
        "annotated_pattern",
        "rule_47_redaction",
        (
            "rule 47: demo: _anonymization.py:6: declares a module-level complete-address pattern "
            "instead of using core's matcher",
        ),
    ),
    ("annotated_pattern", "rule_48_replacement_values", ()),
    ("clean_apps_import", "rule_47_redaction", ()),
    ("clean_apps_import", "rule_48_replacement_values", ()),
    ("plain_import_inside_method", "rule_47_redaction", ()),
    ("plain_import_inside_method", "rule_48_replacement_values", ()),
    ("wrong_name_plain_import", "rule_47_redaction", ()),
    (
        "wrong_name_plain_import",
        "rule_48_replacement_values",
        (
            "rule 48: demo: apps.py:12: anonymize_account must delegate to "
            "_anonymization.anonymize_account",
        ),
    ),
    ("module_level_plain_import", "rule_47_redaction", ()),
    (
        "module_level_plain_import",
        "rule_48_replacement_values",
        (
            "rule 48: demo: apps.py:14: anonymize_account must delegate to "
            "_anonymization.anonymize_account",
        ),
    ),
    ("scrub_apps", "rule_47_redaction", ()),
    (
        "scrub_apps",
        "rule_48_replacement_values",
        (
            "rule 48: demo: apps.py:12: anonymize_account must delegate to "
            "_anonymization.anonymize_account",
        ),
    ),
    ("no_apps", "rule_47_redaction", ()),
    ("no_apps", "rule_48_replacement_values", ()),
    (
        "two_modules_order",
        "rule_47_redaction",
        (
            "rule 47: demo: _anonymization.py:20: substitutes an identity with re.escape and no "
            "word boundary",
            "rule 47: demo: _anonymization.py:8: declares a module-level complete-address pattern "
            "instead of using core's matcher",
        ),
    ),
    (
        "two_modules_order",
        "rule_48_replacement_values",
        (
            "rule 48: demo: _anonymization.py:6: spells a replacement sentinel instead of "
            "importing it from core",
            "rule 48: blog: _anonymization.py:2: spells a replacement sentinel instead of "
            "importing it from core",
            "rule 48: blog: apps.py:12: anonymize_account must delegate to "
            "_anonymization.anonymize_account",
        ),
    ),
)


def test_rule_37_exempts_neither_module() -> None:
    """The split adds no rule 37 exemption; neither module names modules."""
    for name in ("rules_redaction", *SPLIT_SIBLINGS):
        assert (
            "scripts",
            f"module_conventions/{name}.py",
        ) not in RULE_37_ALLOWED_LITERAL_FILES


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rules_redaction", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_redaction", "registry"}, (
                        name,
                        node.lineno,
                    )


@pytest.mark.parametrize(
    ("case", "detector", "expected"),
    EXACT_FINDINGS,
    ids=[f"{case}-{detector}" for case, detector, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(
    case: str, detector: str, expected: tuple[str, ...]
) -> None:
    assert getattr(rules_redaction, detector)(CASE_BUILDERS[case]()) == list(expected)
