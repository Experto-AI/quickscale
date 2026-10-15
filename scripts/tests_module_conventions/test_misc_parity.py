"""
Behavioral controls for the ``rules_misc`` split (SA267).

The statement-flow mechanics, the ready()-scope analysis, rule 10's error
homes, and rules 20/45/50 live in private siblings (``_misc_flow``,
``_misc_ready``, ``_misc_checks``, ``_misc_rules``) behind the ``rules_misc``
facade.  SA267 has closed, so SA279 retired the pre-split surface pins; these
controls keep the split's structural invariants and the exact ordered findings
of representative corpora captured from the pre-split module, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _misc_checks,
    _misc_flow,
    _misc_ready,
    _misc_rules,
    rules_misc,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_misc_checks": _misc_checks,
    "_misc_flow": _misc_flow,
    "_misc_ready": _misc_ready,
    "_misc_rules": _misc_rules,
}


def _apps(replacement: str) -> Module:
    """Build the golden module with its ready() registration replaced."""
    module = _golden_module()
    return _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            replacement,
        ),
    )


def _exceptions(source: str) -> Module:
    return _with_files(_golden_module(), exceptions=source)


def _views(source: str) -> Module:
    return _with_files(_golden_module(), views=source)


def _mypy_table() -> Module:
    module = _golden_module()
    return replace(
        module,
        root_files={
            **module.root_files,
            "pyproject.toml": module.root_files["pyproject.toml"]
            + "\n[tool.mypy]\ndisallow_untyped_defs = false\n",
        },
    )


def _stray_error() -> Module:
    module = _golden_module()
    without_exceptions = replace(
        module,
        files={key: value for key, value in module.files.items() if key != "exceptions.py"},
    )
    return _with_files(
        without_exceptions,
        services=(
            '"""Demo service surface."""\n\n\nclass DemoServiceError(Exception):\n    pass\n'
        ),
    )


CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    "no_registration": lambda: _corpus(_apps("        pass\n")),
    "inverted_registration": lambda: _corpus(
        _apps(
            "        register_module_checks(self, [check_demo])\n"
            "        register_module_settings_check(self, 'demo')\n"
        ),
    ),
    "ready_catches": lambda: _corpus(
        _apps(
            "        try:\n"
            "            register_module_checks(self, [check_demo])\n"
            "        except Exception:\n"
            "            pass\n"
        ),
    ),
    "ready_raises": lambda: _corpus(_apps("        raise RuntimeError('boom')\n")),
    "dead_branch": lambda: _corpus(
        _apps("        if False:\n            register_module_checks(self, [check_demo])\n"),
    ),
    "terminal_branch": lambda: _corpus(
        _apps(
            "        if True:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n"
        ),
    ),
    "loop_break_else": lambda: _corpus(
        _apps(
            "        for _ in [1]:\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n"
        ),
    ),
    "loop_no_break_else": lambda: _corpus(
        _apps(
            "        for _ in [1]:\n"
            "            pass\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n"
        ),
    ),
    "try_finally_override": lambda: _corpus(
        _apps(
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                return\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n"
        ),
    ),
    "short_circuit": lambda: _corpus(
        _apps("        True or register_module_checks(self, [check_demo])\n"),
    ),
    "lambda_default": lambda: _corpus(
        _apps("        unused = lambda x=register_module_checks(self, [check_demo]): x\n"),
    ),
    "lambda_body": lambda: _corpus(
        _apps("        unused = lambda: register_module_checks(self, [check_demo])\n"),
    ),
    "renamed_base": lambda: _corpus(
        _exceptions(
            "class DemoIssueError(Exception):\n    pass\n\n\n"
            "class DemoProblemError(DemoIssueError):\n    pass\n"
        ),
    ),
    "drf_base": lambda: _corpus(
        _exceptions(
            "from rest_framework.exceptions import APIException\n\n\n"
            "class DemoError(Exception):\n    pass\n\n\n"
            "class DemoProblemError(DemoError, APIException):\n    pass\n"
        ),
    ),
    "stray_error": lambda: _corpus(_stray_error()),
    "email_direct": lambda: _corpus(
        _views(
            "from django.core.mail import send_mail\n\n\n"
            "def index():\n    send_mail('a', 'b', 'c', ['d'])\n"
        ),
    ),
    "person_link_dict": lambda: _corpus(
        _views(
            "def invite(send_notification, user):\n"
            "    send_notification(context={'actor_user_id': str(user.pk)})\n"
        ),
    ),
    "mypy_table": lambda: _corpus(_mypy_table()),
}

#: (case, detector, expected findings) captured from the pre-split module; the
#: list is exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", "rule_10_checks_errors", ()),
    (
        "no_registration",
        "rule_10_checks_errors",
        ("rule 10: demo: checks.py exists but ready() registers nothing",),
    ),
    (
        "inverted_registration",
        "rule_10_checks_errors",
        ("rule 10: demo: ready() registers module checks before the generic settings check",),
    ),
    (
        "ready_catches",
        "rule_10_checks_errors",
        ("rule 10: demo: ready() catches a registration failure",),
    ),
    (
        "ready_raises",
        "rule_10_checks_errors",
        (
            "rule 10: demo: checks.py exists but ready() registers nothing",
            "rule 10: demo: ready() raises outside the shared helper",
        ),
    ),
    (
        "dead_branch",
        "rule_10_checks_errors",
        ("rule 10: demo: checks.py exists but ready() registers nothing",),
    ),
    (
        "terminal_branch",
        "rule_10_checks_errors",
        ("rule 10: demo: checks.py exists but ready() registers nothing",),
    ),
    ("loop_break_else", "rule_10_checks_errors", ()),
    (
        "loop_no_break_else",
        "rule_10_checks_errors",
        ("rule 10: demo: checks.py exists but ready() registers nothing",),
    ),
    (
        "try_finally_override",
        "rule_10_checks_errors",
        ("rule 10: demo: checks.py exists but ready() registers nothing",),
    ),
    (
        "short_circuit",
        "rule_10_checks_errors",
        ("rule 10: demo: checks.py exists but ready() registers nothing",),
    ),
    ("lambda_default", "rule_10_checks_errors", ()),
    (
        "lambda_body",
        "rule_10_checks_errors",
        ("rule 10: demo: checks.py exists but ready() registers nothing",),
    ),
    (
        "renamed_base",
        "rule_10_checks_errors",
        (
            "rule 10: demo: exceptions.py has no DemoError base; "
            "the base is named after the module as spelled",
            "rule 10: demo: DemoIssueError does not derive from the module error base",
            "rule 10: demo: DemoProblemError does not derive from the module error base",
        ),
    ),
    (
        "drf_base",
        "rule_10_checks_errors",
        (
            "rule 10: demo: exceptions.py defines DemoProblemError with base "
            "'APIException' outside Exception and the module's own classes; "
            "the module hierarchy derives from Exception alone",
        ),
    ),
    (
        "stray_error",
        "rule_10_checks_errors",
        (
            "rule 10: demo: services.py defines DemoServiceError but the module "
            "ships no exceptions.py",
        ),
    ),
    (
        "email_direct",
        "rule_20_email",
        ("rule 20: demo: views.py sends email directly",),
    ),
    (
        "person_link_dict",
        "rule_50_notification_links",
        (
            "rule 50: demo: views.py:2 writes the reserved notification person-link key "
            "'actor_user_id' in module source; pass send_notification(about_users=...) "
            "instead",
        ),
    ),
    (
        "mypy_table",
        "rule_45_stub_exemptions",
        ("rule 45: demo: pyproject.toml declares a per-module [tool.mypy] table",),
    ),
)


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world."""
    assert ("scripts", "module_conventions/rules_misc.py") in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
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
                assert node.module.split(".")[-1] not in {"rules_misc", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_misc", "registry"}, (
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
    corpus = CASE_BUILDERS[case]()
    assert getattr(rules_misc, detector)(corpus) == list(expected)
