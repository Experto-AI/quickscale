"""
Behavioral controls for the ``rules_identity`` split (SA267).

The identity detectors' mechanics live in private siblings
(``_identity_names``, ``_identity_conventions``, ``_identity_tests``,
``_identity_stems``, ``_identity_references``, ``_identity_files``,
``_identity_module_lists``) behind the ``rules_identity`` facade.  SA267 has
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

from scripts.check_module_conventions import Corpus
from scripts.module_conventions import (
    _identity_conventions,
    _identity_files,
    _identity_module_lists,
    _identity_names,
    _identity_references,
    _identity_stems,
    _identity_tests,
    rules_identity,
)
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_identity_conventions": _identity_conventions,
    "_identity_files": _identity_files,
    "_identity_module_lists": _identity_module_lists,
    "_identity_names": _identity_names,
    "_identity_references": _identity_references,
    "_identity_stems": _identity_stems,
    "_identity_tests": _identity_tests,
}


#: Rule 37's and rule 28's module-name exception tables stay defined in the
#: facade: rule 37's allowlist exempts only ``rules_identity.py``.  The
#: enumeration threshold is not a module-name table and lives with the scan
#: mechanics; the facade re-exports it.
RULE_37_TABLES = (
    "RULE_28_LISTED_EXTRA_FILES",
    "RULE_37_ALLOWED_BRANCHES",
    "RULE_37_ALLOWED_CONSTANTS",
    "RULE_37_ALLOWED_LITERALS",
    "RULE_37_ALLOWED_LITERAL_FILES",
)


def _clean_corpus() -> Corpus:
    return _corpus(_golden_module())


def _rule2_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            apps=module.files["apps.py"].replace(
                'label = "quickscale_demo"', 'label = "quickscale_demoo"'
            ),
            urls=module.files["urls.py"].replace(
                'app_name = "quickscale_demo"', 'app_name = "demo_app"'
            ),
            **{
                "templates/other/page.html": "<html></html>\n",
                "management/commands/run.py": "x = 1\n",
                "models.py": (
                    "from django.db import models\n\n\n"
                    "class Widget(models.Model):\n"
                    "    class Meta:\n        db_table = 'widgets'\n"
                ),
            },
        )
    )


def _rule24_corpus() -> Corpus:
    module = _golden_module()
    without_py_typed = replace(
        module, files={key: value for key, value in module.files.items() if key != "py.typed"}
    )
    return _corpus(
        _with_files(
            without_py_typed,
            views=(
                "import datetime\n"
                "from django.core.cache import cache\n\n"
                "WIDGET_CACHE_KEY = 'widgets:all'\n\n"
                "def index(now=datetime.datetime.now()):\n"
                "    cache.set('other:key', 1)\n"
                "    return now\n"
            ),
        )
    )


def _rule28_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            views="from ._helpers import helper\n",
            **{
                "_helpers.py": "import logging\n\nlogger = logging.getLogger(__name__)\n",
                "utils.py": "x = 1\n",
            },
        )
    )


def _rule29_corpus() -> Corpus:
    module = _golden_module()
    broken = replace(
        module,
        tests={
            **module.tests,
            "helpers.py": "VALUE = 1\n",
            "test_widget.py": (
                '"""SA999 widget."""\n\n\ndef test_widget():\n    pass\n# SA998 note\n'
            ),
        },
    )
    broken = replace(broken, manifest_text="# Manifest rules (T2.3 Phase 3)\n")
    broken = _with_files(broken, models=broken.files["models.py"] + "\n# SA999 legacy note\n")
    return _corpus(broken)


def _rule33_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            views=(
                "def _lock_key(value):\n"
                "    return f'widget:lock:{value}'\n\n"
                "FUNC_NAME = 'widget_equality'\n"
                "DEMO_SESSION_KEY = 'quickscale_modules_demo.demo_state'\n\n"
                "def index(request):\n"
                "    request.session['demokey'] = 'x'\n"
            ),
        )
    )


def _rule34_corpus() -> Corpus:
    orgs = _golden_module("orgs")
    notifications = _golden_module("notifications")
    upward = _with_files(
        orgs,
        services=(
            "from django.apps import apps\n\nPLAN = apps.get_model('quickscale_billing', 'Plan')\n"
        ),
    )
    cycle_orgs = _with_files(
        orgs,
        services=(
            "from django.apps import apps\n\n"
            'X = apps.is_installed("quickscale_modules_notifications")\n'
        ),
    )
    cycle_notifications = _with_files(
        notifications,
        services=(
            'from django.apps import apps\n\nX = apps.is_installed("quickscale_modules_orgs")\n'
        ),
    )
    return _corpus(upward, cycle_orgs, cycle_notifications)


def _rule37_corpus() -> Corpus:
    corpus = _corpus(_golden_module("alpha"), _golden_module("beta"), _golden_module("gamma"))
    return replace(
        corpus,
        core_files={
            "contracts/registry.py": "REGISTRY = ('alpha', 'beta', 'gamma')\n",
            "generator/templates/project_name/sample.j2": (
                "{% for m in ['alpha', 'beta'] %}{{ m }}{% endfor %}\n"
            ),
        },
        cli_files={
            "commands/select.py": "def pick(module_name):\n    return module_name == 'alpha'\n",
            "commands/const.py": "ALPHA_STATE = 'x'\n",
            "commands/other.py": "NAMES = ['alpha', 'beta']\n",
        },
    )


def _rule37_allowed_corpus() -> Corpus:
    corpus = _corpus(_golden_module("alpha"), _golden_module("beta"))
    return replace(
        corpus,
        core_files={
            "contracts/module_catalog.py": "MODULE_CATALOG = ('alpha', 'beta')\n",
            "runtime/seam.py": "_NON_SEAM_MODULES = frozenset({'alpha'})\n",
        },
    )


def _rule37_seam_corpus() -> Corpus:
    corpus = _corpus(_golden_module("blog"), _golden_module("listings"))
    return replace(
        corpus,
        core_files={
            "runtime/urls.py": (
                "PATTERNS = [re_path(r'^orgs/(?!api(?:/|$))[^/]+/"
                "(blog|listings|members|settings)/?$', view)]\n"
            )
        },
    )


CASE_BUILDERS = {
    "clean": _clean_corpus,
    "rule2": _rule2_corpus,
    "rule24": _rule24_corpus,
    "rule28": _rule28_corpus,
    "rule29": _rule29_corpus,
    "rule33": _rule33_corpus,
    "rule34": _rule34_corpus,
    "rule37": _rule37_corpus,
    "rule37_allowed": _rule37_allowed_corpus,
    "rule37_seam": _rule37_seam_corpus,
}

#: (case, detector, expected findings) captured from the pre-split module; the
#: list is exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", "rule_2_identity_names", ()),
    ("clean", "rule_24_small_conventions", ()),
    ("clean", "rule_28_file_names", ()),
    ("clean", "rule_29_test_names", ()),
    ("clean", "rule_33_shared_stems", ()),
    ("clean", "rule_34_name_references", ()),
    ("clean", "rule_37_module_lists", ()),
    (
        "rule2",
        "rule_2_identity_names",
        (
            "rule 2: demo: apps.py label is 'quickscale_demoo', expected 'quickscale_demo'",
            "rule 2: demo: urls.py app_name is 'demo_app', expected 'quickscale_demo'",
            "rule 2: demo: template directory 'other' in templates/other/page.html",
            "rule 2: demo: command 'run' lacks the quickscale_demo_ prefix",
            "rule 2: demo: models.py sets db_table on Meta",
        ),
    ),
    (
        "rule24",
        "rule_24_small_conventions",
        (
            "rule 24: demo: py.typed is missing",
            "rule 24: demo: views.py calls datetime.now()",
            "rule 24: demo: cache key WIDGET_CACHE_KEY lacks the quickscale_demo: stem",
            "rule 24: demo: views.py cache key 'other:key' lacks the module prefix",
        ),
    ),
    (
        "rule28",
        "rule_28_file_names",
        (
            "rule 28: demo: utils.py is not an allowed package file name",
            "rule 28: demo: _helpers.py:3 calls getLogger(__name__); a private file with a "
            "facade logs on the facade's channel (rule 46)",
        ),
    ),
    (
        "rule29",
        "rule_29_test_names",
        (
            "rule 29: demo: helpers.py is outside rule 29's tests file set",
            "rule 29: demo: models.py:20 carries a ticket id in shipped source",
            "rule 29: demo: module.yml:1 carries a ticket id",
            "rule 29: demo: test_widget.py docstring carries a ticket id",
            "rule 29: demo: test_widget.py comment carries a ticket id",
        ),
    ),
    (
        "rule33",
        "rule_33_shared_stems",
        (
            "rule 33: demo: database function FUNC_NAME lacks the quickscale_demo_ stem",
            "rule 33: demo: session key DEMO_SESSION_KEY lacks the quickscale_demo: stem",
            "rule 33: demo: views.py:8 session key 'demokey' lacks the quickscale_demo: stem",
            "rule 33: demo: advisory-lock key prefix 'widget:lock:' lacks the "
            "quickscale_demo: stem",
        ),
    ),
    (
        "rule34",
        "rule_34_name_references",
        (
            "rule 34: orgs: services.py:3 references billing by name upward "
            "(layer 3 above layer 1)",
            "rule 34: same-layer name-reference cycle: notifications -> orgs -> notifications",
        ),
    ),
    (
        "rule37",
        "rule_37_module_lists",
        (
            "rule 37: core/contracts/registry.py:1 literal REGISTRY lists 3 module names: "
            "alpha, beta, gamma",
            "rule 37: core/generator/templates/project_name/sample.j2:1 literal "
            "<template literal> lists 2 module names: alpha, beta",
            "rule 37: cli/commands/select.py:2 branches on module name 'alpha': "
            "module_name == 'alpha'",
            "rule 37: cli/commands/const.py:1 declares module-prefixed constant ALPHA_STATE",
            "rule 37: cli/commands/other.py:1 literal NAMES lists 2 module names: alpha, beta",
        ),
    ),
    ("rule37_allowed", "rule_37_module_lists", ()),
    ("rule37_seam", "rule_37_module_lists", ()),
)


def test_rule_37_exception_tables_stay_defined_here() -> None:
    """Rule 37 exempts only ``rules_identity.py``, so its tables live there."""
    tree = ast.parse(Path(rules_identity.__file__).read_text(encoding="utf-8"))
    assigned: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        assigned.update(target.id for target in targets if isinstance(target, ast.Name))
    assert set(RULE_37_TABLES) <= assigned


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world, tables excluded."""
    assert ("scripts", "module_conventions/rules_identity.py") in (
        rules_identity.RULE_37_ALLOWED_LITERAL_FILES
    )
    for name in SPLIT_SIBLINGS:
        assert (
            "scripts",
            f"module_conventions/{name}.py",
        ) not in rules_identity.RULE_37_ALLOWED_LITERAL_FILES


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rules_identity", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_identity", "registry"}, (
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
    assert getattr(rules_identity, detector)(corpus) == list(expected)


def test_rule_37_scan_helpers_keep_their_pre_split_calls() -> None:
    """The re-exported scan helpers accept their pre-split two-argument calls."""
    assert rules_identity._module_literal_names(
        ast.parse("NAMES = ['alpha', 'beta']\n"), {"alpha", "beta"}
    ) == [(1, "NAMES", ["alpha", "beta"])]
    assert rules_identity._string_module_alternations(
        ast.parse("PATTERN = r'(alpha|beta)'\n"), {"alpha", "beta"}
    ) == [(1, "<string alternation:alpha|beta>", ["alpha", "beta"])]
    assert rules_identity._template_module_literals(
        "{% for m in ['alpha', 'beta'] %}{{ m }}{% endfor %}\n", {"alpha", "beta"}
    ) == [(1, "<template literal>", ["alpha", "beta"])]
