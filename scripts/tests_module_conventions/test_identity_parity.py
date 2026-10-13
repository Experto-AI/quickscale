"""
Parity controls for the ``rules_identity`` split (SA267).

The identity detectors' mechanics live in private siblings
(``_identity_names``, ``_identity_conventions``, ``_identity_tests``,
``_identity_stems``, ``_identity_references``, ``_identity_files``,
``_identity_module_lists``) behind the ``rules_identity`` facade.  These
controls pin the facade's preserved surface, the split's structural
invariants, and the exact ordered findings of representative corpora captured
from the pre-split module, so a later slice cannot silently drop, reorder, or
reword them.
"""

from __future__ import annotations

import ast
import inspect
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Corpus
from scripts.module_conventions import (
    _identity_conventions,
    _identity_files,
    _identity_module_lists,
    _identity_names,
    _identity_references,
    _identity_stems,
    _identity_tests,
    registry,
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

#: Every module-level name the pre-split ``rules_identity`` published, from its
#: own ``def``/``class``/assignment statements.  The facade must keep exposing
#: all of them, private helpers included.
FROZEN_SURFACE = (
    "AMBIGUOUS_BINDING",
    "RULE_28_ALLOWED_DIRS",
    "RULE_28_ALLOWED_FILES",
    "RULE_28_ALLOWED_NON_PYTHON",
    "RULE_28_LISTED_EXTRA_FILES",
    "RULE_37_ALLOWED_BRANCHES",
    "RULE_37_ALLOWED_CONSTANTS",
    "RULE_37_ALLOWED_LITERALS",
    "RULE_37_ALLOWED_LITERAL_FILES",
    "RULE_37_BRANCH_OPERANDS",
    "RULE_37_BRANCH_OPERATORS",
    "RULE_37_MINIMUM_MODULE_NAMES",
    "TICKET_IN_SHIPPED",
    "TICKET_IN_TEST",
    "_TEMPLATE_BRACKET_LITERAL",
    "_TEMPLATE_PIPE_GROUP",
    "_TEMPLATE_QUOTED_NAME",
    "_add_import_bindings",
    "_collect_scope_imports",
    "_datetime_now_calls",
    "_facade_targets",
    "_is_migration_model_path",
    "_is_session_receiver",
    "_migration_model_reference_ids",
    "_module_literal_names",
    "_module_name_branches",
    "_module_named_logger_line",
    "_module_prefixed_constants",
    "_name_reference_target",
    "_resolve_module_path",
    "_resolves_to_stdlib_datetime",
    "_session_literal_keys",
    "_string_module_alternations",
    "_template_module_literals",
    "_tests_entry_allowed",
    "_visit_definition_expressions",
    "rule_24_small_conventions",
    "rule_28_file_names",
    "rule_29_test_names",
    "rule_2_identity_names",
    "rule_33_shared_stems",
    "rule_34_name_references",
    "rule_37_module_lists",
)

#: The pre-split signature of every callable the pre-split module published,
#: including the private helpers the facade re-exports.  The registry, the
#: entry point, and the control cases invoke the rule entrypoints; external
#: callers may reach any helper through its pre-split call shape.
FROZEN_SIGNATURES = {
    "_add_import_bindings": (
        "(bindings: 'dict[str, tuple[str, ...]]', node: 'ast.AST', *, overwrite: 'bool' = True)"
        " -> 'None'"
    ),
    "_visit_definition_expressions": (
        "(node: 'ast.AST', bindings: 'dict[str, tuple[str, ...]]', visit: 'Callable[[ast.AST,"
        " dict[str, tuple[str, ...]]], None]') -> 'None'"
    ),
    "_collect_scope_imports": (
        "(statements: 'list[ast.stmt]', bindings: 'dict[str, tuple[str, ...]]', *, overwrite:"
        " 'bool' = True) -> 'None'"
    ),
    "_datetime_now_calls": "(tree: 'ast.Module') -> 'list[ast.Call]'",
    "_resolve_module_path": (
        "(node: 'ast.expr', bindings: 'Mapping[str, tuple[str, ...]]') -> 'tuple[str, ...] | None'"
    ),
    "_resolves_to_stdlib_datetime": (
        "(node: 'ast.expr', bindings: 'Mapping[str, tuple[str, ...]]') -> 'bool'"
    ),
    "rule_2_identity_names": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_24_small_conventions": "(corpus: 'Corpus') -> 'list[str]'",
    "_tests_entry_allowed": "(rel: 'str') -> 'bool'",
    "rule_29_test_names": "(corpus: 'Corpus') -> 'list[str]'",
    "_is_session_receiver": "(node: 'ast.expr') -> 'bool'",
    "_session_literal_keys": "(tree: 'ast.Module') -> 'list[tuple[int, str]]'",
    "rule_33_shared_stems": "(corpus: 'Corpus') -> 'list[str]'",
    "_name_reference_target": "(value: 'str') -> 'str | None'",
    "_migration_model_reference_ids": "(tree: 'ast.Module') -> 'set[int]'",
    "_is_migration_model_path": "(value: 'str', target: 'str') -> 'bool'",
    "rule_34_name_references": "(corpus: 'Corpus') -> 'list[str]'",
    "_facade_targets": "(module: 'Module') -> 'set[str]'",
    "_module_named_logger_line": "(tree: 'ast.Module') -> 'int | None'",
    "rule_28_file_names": "(corpus: 'Corpus') -> 'list[str]'",
    "_module_literal_names": (
        "(tree: 'ast.Module', vocabulary: 'set[str]') -> 'list[tuple[int, str, list[str]]]'"
    ),
    "_string_module_alternations": (
        "(tree: 'ast.Module', vocabulary: 'set[str]') -> 'list[tuple[int, str, list[str]]]'"
    ),
    "_template_module_literals": (
        "(text: 'str', vocabulary: 'set[str]') -> 'list[tuple[int, str, list[str]]]'"
    ),
    "_module_name_branches": (
        "(tree: 'ast.Module', vocabulary: 'set[str]') -> 'list[tuple[int, str, str]]'"
    ),
    "_module_prefixed_constants": (
        "(tree: 'ast.Module', vocabulary: 'set[str]') -> 'list[tuple[int, str]]'"
    ),
    "rule_37_module_lists": "(corpus: 'Corpus') -> 'list[str]'",
}

#: The entrypoints the registry and the check entry point read from the facade.
IDENTITY_RULES = (
    "rule_2_identity_names",
    "rule_24_small_conventions",
    "rule_28_file_names",
    "rule_29_test_names",
    "rule_33_shared_stems",
    "rule_34_name_references",
    "rule_37_module_lists",
)

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

FROZEN_RULE_28_LISTED_EXTRA_FILES = {
    "backups": frozenset({"persistence.py"}),
    "orgs": frozenset({"debug_views.py"}),
    "billing": frozenset({"webhook_urls.py"}),
    "storage": frozenset({"markdownx_urls.py"}),
}

FROZEN_RULE_37_ALLOWED_LITERAL_FILES = frozenset(
    {
        ("scripts", "check_module_conventions.py"),
        ("scripts", "module_conventions/core.py"),
        ("scripts", "module_conventions/registry.py"),
        ("scripts", "module_conventions/rule_44.py"),
        ("scripts", "module_conventions/rules_analytics.py"),
        ("scripts", "module_conventions/rules_dependencies.py"),
        ("scripts", "module_conventions/rules_docs.py"),
        ("scripts", "module_conventions/rules_identity.py"),
        ("scripts", "module_conventions/rules_misc.py"),
        ("scripts", "module_conventions/rules_models.py"),
        ("scripts", "module_conventions/rules_package.py"),
        ("scripts", "module_conventions/rules_routes.py"),
        ("scripts", "module_conventions/rules_settings.py"),
        ("scripts", "module_conventions/rules_webhooks.py"),
    }
)

FROZEN_RULE_37_MINIMUM_MODULE_NAMES = 2

FROZEN_RULE_37_ALLOWED_LITERALS = (
    ("cli", "utils/auth_migration.py", "_CORE_AUTH_APPS"),
    ("core", "apply/steps/env_sync.py", "ENV_EXAMPLE_MODULE_SPECS"),
    ("core", "contracts/module_catalog.py", "MODULE_CATALOG"),
    ("core", "runtime/seam.py", "_NON_SEAM_MODULES"),
    ("core", "runtime/seam.py", "_SEAM_MODULE_API_PATHS"),
    ("core", "runtime/seam.py", "_SEAM_MODULE_PATHS"),
    ("core", "runtime/urls.py", "<string alternation:blog|listings|members|settings>"),
    ("core", "runtime/urls.py", "_TEMPLATE_MODULE_URLS"),
    ("scripts", "check_module_core_compatibility.py", "SKIP_INSTALL_PROBE_MODULES"),
    ("scripts", "check_org_context_primitives.py", "EXEMPT_MODULES"),
)

FROZEN_RULE_37_ALLOWED_BRANCHES = {
    ("cli", "utils/_dependency_io.py", "storage"): (
        "storage's cloud extra selects the module's optional boto3/django-storages "
        "dependencies from its backend option; the manifest dependency model "
        "carries names only, so the condition has no generic home yet"
    ),
    ("cli", "commands/_module_embed.py", "auth"): (
        "auth's split-branch migration gate runs before the embedded module is "
        "importable, so it cannot live in the module's adapter"
    ),
}

FROZEN_RULE_37_ALLOWED_CONSTANTS = (
    ("cli", "utils/_dependency_io.py", "_STORAGE_CLOUD_BACKENDS"),
    ("cli", "utils/_dependency_io.py", "_STORAGE_CLOUD_DEPENDENCIES"),
    ("cli", "utils/_dependency_io.py", "_STORAGE_CLOUD_EXTRA"),
    ("core", "contracts/module_options.py", "ANALYTICS_POSTHOG_DEFAULT_HOST"),
    ("core", "contracts/module_options.py", "ANALYTICS_PROVIDER_POSTHOG"),
    ("core", "contracts/module_options.py", "BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR_OPTION"),
    ("core", "contracts/module_options.py", "BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR_OPTION"),
    ("core", "contracts/module_options.py", "BILLING_ENV_VAR_OPTION_NAMES"),
    ("core", "contracts/module_options.py", "NOTIFICATIONS_RESEND_API_KEY_ENV_VAR_OPTION"),
    ("core", "contracts/module_options.py", "NOTIFICATIONS_WEBHOOK_SECRET_ENV_VAR_OPTION"),
    ("core", "contracts/module_options.py", "SOCIAL_EMBEDS_PATH"),
    ("core", "contracts/module_options.py", "SOCIAL_INTEGRATION_BASE_PATH"),
    ("core", "contracts/module_options.py", "SOCIAL_INTEGRATION_EMBEDS_PATH"),
    ("core", "contracts/module_options.py", "SOCIAL_LINK_TREE_PATH"),
    ("core", "contracts/module_options.py", "STORAGE_ACCESS_KEY_ID_ENV_VAR_OPTION"),
    ("core", "contracts/module_options.py", "STORAGE_SECRET_ACCESS_KEY_ENV_VAR_OPTION"),
    ("core", "manifest/social_manifest.py", "SOCIAL_LAYOUT_VARIANTS"),
    ("core", "manifest/social_manifest.py", "SOCIAL_PAYLOAD_HTTP_STATUS"),
    ("core", "manifest/social_manifest.py", "SOCIAL_PAYLOAD_STATUSES"),
    ("core", "manifest/social_manifest.py", "SOCIAL_PROVIDER_CATALOG"),
    ("core", "manifest/social_manifest.py", "SOCIAL_STATUS_DISABLED"),
    ("core", "manifest/social_manifest.py", "SOCIAL_STATUS_EMPTY"),
    ("core", "manifest/social_manifest.py", "SOCIAL_STATUS_ENABLED"),
    ("core", "manifest/social_manifest.py", "SOCIAL_STATUS_ERROR"),
    ("core", "manifest/social_manifest.py", "_SOCIAL_PROVIDER_ALIASES"),
    ("core", "manifest/social_manifest.py", "_SOCIAL_PROVIDER_BY_HOST"),
    ("core", "manifest/social_manifest.py", "_SOCIAL_PROVIDER_BY_NAME"),
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


def test_facade_publishes_the_pre_split_surface() -> None:
    """The facade's ``__all__`` is the pre-split module's own name set."""
    assert rules_identity.__all__ == FROZEN_SURFACE
    for name in FROZEN_SURFACE:
        assert getattr(rules_identity, name) is not None


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each pre-split callable keeps its pre-split signature through the facade."""
    assert {
        name: str(inspect.signature(getattr(rules_identity, name))) for name in FROZEN_SIGNATURES
    } == FROZEN_SIGNATURES


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
    assert rules_identity.RULE_28_LISTED_EXTRA_FILES == FROZEN_RULE_28_LISTED_EXTRA_FILES
    assert rules_identity.RULE_37_ALLOWED_LITERAL_FILES == FROZEN_RULE_37_ALLOWED_LITERAL_FILES
    assert rules_identity.RULE_37_MINIMUM_MODULE_NAMES == FROZEN_RULE_37_MINIMUM_MODULE_NAMES
    assert (
        rules_identity.RULE_37_MINIMUM_MODULE_NAMES
        is _identity_module_lists.RULE_37_MINIMUM_MODULE_NAMES
    )
    assert tuple(sorted(rules_identity.RULE_37_ALLOWED_LITERALS)) == FROZEN_RULE_37_ALLOWED_LITERALS
    assert rules_identity.RULE_37_ALLOWED_BRANCHES == FROZEN_RULE_37_ALLOWED_BRANCHES
    assert (
        tuple(sorted(rules_identity.RULE_37_ALLOWED_CONSTANTS)) == FROZEN_RULE_37_ALLOWED_CONSTANTS
    )


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


def test_orchestrators_and_entrypoints_keep_their_homes() -> None:
    """Rules 28 and 37 stay orchestrated by the facade; the rest move out."""
    assert rules_identity.rule_28_file_names.__module__ == (
        "scripts.module_conventions.rules_identity"
    )
    assert rules_identity.rule_37_module_lists.__module__ == (
        "scripts.module_conventions.rules_identity"
    )
    assert _identity_names.rule_2_identity_names.__module__ == (
        "scripts.module_conventions._identity_names"
    )
    assert _identity_conventions.rule_24_small_conventions.__module__ == (
        "scripts.module_conventions._identity_conventions"
    )
    assert _identity_tests.rule_29_test_names.__module__ == (
        "scripts.module_conventions._identity_tests"
    )
    assert _identity_stems.rule_33_shared_stems.__module__ == (
        "scripts.module_conventions._identity_stems"
    )
    assert _identity_references.rule_34_name_references.__module__ == (
        "scripts.module_conventions._identity_references"
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


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registry's detectors are the facade, not a sibling module."""
    detectors = {rule.number: rule.detector for rule in registry.RULES}
    assert detectors[2] is rules_identity.rule_2_identity_names
    assert detectors[24] is rules_identity.rule_24_small_conventions
    assert detectors[28] is rules_identity.rule_28_file_names
    assert detectors[29] is rules_identity.rule_29_test_names
    assert detectors[33] is rules_identity.rule_33_shared_stems
    assert detectors[34] is rules_identity.rule_34_name_references
    assert detectors[37] is rules_identity.rule_37_module_lists
    for name in IDENTITY_RULES:
        assert getattr(checker, name) is getattr(rules_identity, name)
