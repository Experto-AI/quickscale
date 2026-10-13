"""
Parity controls for the ``rules_package`` split (SA267).

The public-surface scan, the legacy-name checks, the management-command
analysis, the service-surface scan, and rules 11/15/16/18 live in private
siblings (``_package_surfaces``, ``_package_legacy``, ``_package_commands``,
``_package_services``, ``_package_files``) behind the ``rules_package``
facade.  These controls pin the facade's preserved surface, the split's
structural invariants, and the exact ordered findings of representative
corpora captured from the pre-split module, so a later slice cannot silently
drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import copy
import inspect
import tomllib
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _package_commands,
    _package_files,
    _package_legacy,
    _package_services,
    _package_surfaces,
    core,
    registry,
    rules_package,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_package_commands": _package_commands,
    "_package_files": _package_files,
    "_package_legacy": _package_legacy,
    "_package_services": _package_services,
    "_package_surfaces": _package_surfaces,
}

FROZEN_SURFACE = (
    "CONFIRM_COMMAND_KEYWORDS",
    "DESTRUCTIVE_COMMAND_KEYWORDS",
    "RETIRED_SETTINGS_NAME",
    "RULE_11_ONE_OFF_FILES",
    "RULE_11_REQUIRED_FILES",
    "RULE_11_REQUIRED_ROOT_FILES",
    "RULE_11_REQUIRED_TESTS",
    "_all_option_keys",
    "_capability_arguments",
    "_command_flags",
    "_constant_string",
    "_has_tenant_model",
    "_literal_strings",
    "_manifest_retired_settings",
    "_mapping_entries",
    "_module_bindings",
    "_module_member_bindings",
    "_module_string_constants",
    "_private_member_accesses",
    "_public_surface",
    "_retired_declaration_keys",
    "_service_functions",
    "_settings_attribute_names",
    "rule_11_package_files",
    "rule_15_package_root",
    "rule_16_signals",
    "rule_17_management_commands",
    "rule_18_package_tooling",
    "rule_23_service_surface",
    "rule_4_public_surface",
    "rule_6_no_legacy_names",
)

#: The pre-split module's own imports, which it exposed as module attributes;
#: the facade keeps every one importable through its redundant aliases.
FROZEN_IMPORTED_BINDINGS = (
    "Any",
    "CAPABILITY_NAMES",
    "Corpus",
    "MODULE_ABSTRACT_BASES",
    "MODULE_IMPORT_PREFIX",
    "Mapping",
    "Module",
    "ORG_PUBLIC_SURFACE",
    "Path",
    "ast",
    "tomllib",
    "_ancestors",
    "_attribute_chain",
    "_call_func_name",
    "_class_names",
    "_cross_module_imports",
    "_declared_exports",
    "_docstring_nodes",
    "_is_settings_receiver",
    "_keyword",
    "_model_classes",
    "_module_target",
    "_parse",
    "_service_module_bindings",
    "_setting_name_module",
    "_settings_attribute_reads",
    "_settings_bindings",
    "_string_assignments",
    "_string_list",
)

FROZEN_CORE_HELPERS = (
    "CAPABILITY_NAMES",
    "Corpus",
    "MODULE_ABSTRACT_BASES",
    "MODULE_IMPORT_PREFIX",
    "Module",
    "ORG_PUBLIC_SURFACE",
    "_ancestors",
    "_attribute_chain",
    "_call_func_name",
    "_class_names",
    "_cross_module_imports",
    "_declared_exports",
    "_docstring_nodes",
    "_is_settings_receiver",
    "_keyword",
    "_model_classes",
    "_module_target",
    "_parse",
    "_service_module_bindings",
    "_setting_name_module",
    "_settings_attribute_reads",
    "_settings_bindings",
    "_string_assignments",
    "_string_list",
)

FROZEN_SIGNATURES = {
    "_all_option_keys": "(module: 'Module') -> 'set[str]'",
    "_capability_arguments": (
        "(tree: 'ast.Module', module: 'Module') -> 'list[tuple[str | None, int]]'"
    ),
    "_command_flags": "(tree: 'ast.Module') -> 'dict[str, ast.Call]'",
    "_constant_string": "(node: 'ast.expr | None') -> 'str | None'",
    "_has_tenant_model": "(text: 'str') -> 'bool'",
    "_literal_strings": "(node: 'ast.expr | None') -> 'set[str]'",
    "_manifest_retired_settings": "(module: 'Module') -> 'set[str]'",
    "_mapping_entries": "(node: 'Any') -> 'list[tuple[Any, Any]]'",
    "_module_bindings": "(tree: 'ast.Module') -> 'set[str]'",
    "_module_member_bindings": (
        "(tree: 'ast.Module', module_name: 'str') -> 'dict[str, tuple[str, tuple[str, ...]]]'"
    ),
    "_module_string_constants": "(module: 'Module') -> 'dict[str, str]'",
    "_private_member_accesses": (
        "(tree: 'ast.Module', module_name: 'str') -> 'list[tuple[int, str, str]]'"
    ),
    "_public_surface": "(module_name: 'str') -> 'tuple[str, ...]'",
    "_retired_declaration_keys": "(tree: 'ast.Module') -> 'list[ast.Constant]'",
    "_service_functions": (
        "(module: 'Module', tree: 'ast.Module') -> "
        "'dict[str, ast.FunctionDef | ast.AsyncFunctionDef]'"
    ),
    "_settings_attribute_names": "(tree: 'ast.Module') -> 'list[tuple[str, int]]'",
    "rule_11_package_files": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_15_package_root": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_16_signals": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_17_management_commands": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_18_package_tooling": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_23_service_surface": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_4_public_surface": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_6_no_legacy_names": "(corpus: 'Corpus') -> 'list[str]'",
}


def _retired_manifest(module: Module) -> Module:
    """Build the golden module with rule 6's retired settings declared."""
    manifest = copy.deepcopy(module.manifest)
    manifest["retired_settings"] = {
        "QUICKSCALE_DEMO_MODE": "Use QUICKSCALE_DEMO_ENABLED instead.",
        "DEMO_POSTS_PER_PAGE": "Use QUICKSCALE_DEMO_POSTS_PER_PAGE instead.",
    }
    return replace(module, manifest=manifest)


def _aliased_manifest(module: Module) -> Module:
    """Build the golden module with a legacy alias authored in its manifest."""
    manifest = copy.deepcopy(module.manifest)
    manifest["derivation"]["legacy_aliases"] = [{"old": "enabled"}]
    return replace(module, manifest=manifest)


def _retired_option_manifest(module: Module) -> Module:
    """Build the golden module with a retired option still live."""
    manifest = copy.deepcopy(module.manifest)
    manifest["retired_options"] = {"enabled": "Retired."}
    return replace(module, manifest=manifest)


def _command_module(name: str, source: str) -> Module:
    """Build the golden module with its numbered demo command replaced."""
    return _with_files(
        _golden_module(), **{f"management/commands/quickscale_demo_{name}.py": source}
    )


CASE_BUILDERS = {
    "clean": lambda: _corpus(_golden_module()),
    "import_outside_surface": lambda: _corpus(
        _with_files(
            _golden_module(),
            views="from quickscale_modules_storage._helpers import select_storage_backend\n",
        )
    ),
    "private_name_import": lambda: _corpus(
        _with_files(
            _golden_module(),
            views="from quickscale_modules_orgs.current_org import _restore_current_org_id\n",
        )
    ),
    "private_member_access": lambda: _corpus(
        _with_files(
            _golden_module(),
            views=(
                "import quickscale_modules_orgs.current_org as org_context\n\n\n"
                "def restore(prior):\n"
                "    org_context._restore_current_org_id(prior)\n"
            ),
        )
    ),
    "settings_read": lambda: _corpus(
        _with_files(
            _golden_module(),
            views=(
                "from django.conf import settings\n\n\n"
                "RATE = settings.QUICKSCALE_BLOG_POSTS_PER_PAGE\n"
            ),
        )
    ),
    "unknown_capability": lambda: _corpus(
        _with_files(
            _golden_module(),
            views=(
                "from quickscale_core.runtime import collect_capabilities\n\n\n"
                "def handlers() -> tuple[object, ...]:\n"
                "    return collect_capabilities('handlers')\n"
            ),
        )
    ),
    "constructed_capability": lambda: _corpus(
        _with_files(
            _golden_module(),
            views=(
                "from quickscale_core.runtime import collect_capabilities\n\n\n"
                "def collect(name: str) -> tuple[object, ...]:\n"
                "    return collect_capabilities(name)\n"
            ),
        )
    ),
    "clean_retired": lambda: _corpus(_retired_manifest(_golden_module())),
    "python_retired": lambda: _corpus(
        _with_files(
            _golden_module(),
            checks=(
                "RETIRED_SETTINGS = {\n"
                '    "QUICKSCALE_DEMO_MODE": "Use QUICKSCALE_DEMO_ENABLED instead.",\n'
                "}\n"
            ),
        )
    ),
    "legacy_alias": lambda: _corpus(_aliased_manifest(_golden_module())),
    "retired_option_live": lambda: _corpus(_retired_option_manifest(_golden_module())),
    "retired_read": lambda: _corpus(
        _with_files(
            _retired_manifest(_golden_module()),
            views=("from django.conf import settings\n\nMODE = settings.QUICKSCALE_DEMO_MODE\n"),
        )
    ),
    "retired_string": lambda: _corpus(
        _with_files(
            _retired_manifest(_golden_module()),
            views=(
                "from django.conf import settings\n\n"
                'MODE = getattr(settings, "QUICKSCALE_DEMO_MODE", "solo")\n'
            ),
        )
    ),
    "format_flag": lambda: _corpus(
        _command_module(
            "report",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--format', choices=('human', 'json'))\n",
        )
    ),
    "scheduled_alias": lambda: _corpus(
        _command_module(
            "report",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--scheduled', action='store_true')\n",
        )
    ),
    "bad_trigger": lambda: _corpus(
        _command_module(
            "report",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--trigger', choices=['scheduled'], "
            "default='scheduled')\n",
        )
    ),
    "purge_no_confirm": lambda: _corpus(
        _command_module(
            "purge",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--dry-run', action='store_true')\n",
        )
    ),
    "print_call": lambda: _corpus(
        _command_module(
            "run",
            "class Command:\n    def handle(self, *args, **options):\n        print('x')\n",
        )
    ),
    "exit_call": lambda: _corpus(
        _command_module(
            "run",
            "import sys\n\n\nclass Command:\n"
            "    def handle(self, *args, **options):\n"
            "        sys.exit(1)\n",
        )
    ),
    "conforming_command": lambda: _corpus(
        _command_module(
            "purge",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--confirm')\n"
            "        parser.add_argument('--dry-run', action='store_true')\n"
            "        parser.add_argument('--trigger', choices=['manual', 'scheduled'], "
            "default='manual')\n"
            "        parser.add_argument('--json', action='store_true')\n",
        )
    ),
    "missing_all": lambda: _corpus(
        _with_files(_golden_module(), services="def demo_query(*, subject):\n    return subject\n")
    ),
    "missing_services": lambda: _corpus(
        replace(
            _golden_module(),
            files={k: v for k, v in _golden_module().files.items() if k != "services.py"},
        )
    ),
    "undefined_export": lambda: _corpus(
        _with_files(_golden_module(), services='__all__ = ["missing"]\n')
    ),
    "positional_param": lambda: _corpus(
        _with_files(
            _golden_module(),
            services=(
                '__all__ = ["demo_query"]\n\n\n'
                "def demo_query(subject, other):\n    return subject\n"
            ),
        )
    ),
    "cross_import_hidden": lambda: _corpus(
        _golden_module("provider"),
        _with_files(
            _golden_module("consumer"),
            views="from quickscale_modules_provider.services import hidden\n",
        ),
    ),
    "member_hidden": lambda: _corpus(
        _golden_module("provider"),
        _with_files(
            _golden_module("consumer"),
            views=(
                "from quickscale_modules_provider import services as provider_services\n\n\n"
                "def index():\n"
                "    return provider_services.hidden()\n"
            ),
        ),
    ),
    "missing_py_typed": lambda: _corpus(
        replace(
            _golden_module(),
            files={k: v for k, v in _golden_module().files.items() if k != "py.typed"},
        )
    ),
    "one_off_file": lambda: _corpus(_with_files(_golden_module(), **{"helpers.py": "VALUE = 1\n"})),
    "no_is_enabled": lambda: _corpus(
        _with_files(
            _golden_module(),
            services=(
                '"""Demo service surface."""\n\n'
                '__all__ = ["demo_query"]\n\n\n'
                "def demo_query(*, subject: str) -> str:\n    return subject\n"
            ),
        )
    ),
    "root_extra": lambda: _corpus(
        _with_files(
            _golden_module(),
            **{
                "__init__.py": _golden_module().files["__init__.py"]
                + "default_app_config = 'demo'\n"
            },
        )
    ),
    "signal_receiver": lambda: _corpus(
        _with_files(_golden_module(), **{"signals.py": "def receiver():\n    pass\n"})
    ),
    "tooling_broken": lambda: _corpus(
        replace(
            _golden_module(),
            root_files={**_golden_module().root_files, "pyproject.toml": "[project]\n"},
        )
    ),
}

#: (case, detector, expected findings) captured from the pre-split module; the
#: list is exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", "rule_4_public_surface", ()),
    (
        "import_outside_surface",
        "rule_4_public_surface",
        ("rule 4: demo: views.py:1 imports storage:_helpers outside the module's public surface",),
    ),
    (
        "private_name_import",
        "rule_4_public_surface",
        ("rule 4: demo: views.py:1 imports private name '_restore_current_org_id' from orgs",),
    ),
    (
        "private_member_access",
        "rule_4_public_surface",
        (
            "rule 4: demo: views.py:5 reads private member "
            "org_context._restore_current_org_id of orgs",
        ),
    ),
    (
        "settings_read",
        "rule_4_public_surface",
        ("rule 4: demo: views.py:4 reads blog's setting QUICKSCALE_BLOG_POSTS_PER_PAGE",),
    ),
    (
        "unknown_capability",
        "rule_4_public_surface",
        ("rule 4: demo: views.py:5 collects 'handlers', which is not in CAPABILITIES",),
    ),
    (
        "constructed_capability",
        "rule_4_public_surface",
        ("rule 4: demo: views.py:5 collects an unresolved name, which is not in CAPABILITIES",),
    ),
    ("clean_retired", "rule_6_no_legacy_names", ()),
    (
        "python_retired",
        "rule_6_no_legacy_names",
        (
            "rule 6: demo: checks.py keeps retired setting names in Python; "
            "declare them in module.yml as retired_settings",
        ),
    ),
    (
        "legacy_alias",
        "rule_6_no_legacy_names",
        ("rule 6: demo: manifest authors a legacy alias",),
    ),
    (
        "retired_option_live",
        "rule_6_no_legacy_names",
        ("rule 6: demo: retired option 'enabled' is still accepted",),
    ),
    (
        "retired_read",
        "rule_6_no_legacy_names",
        ("rule 6: demo: views.py:3 reads retired setting QUICKSCALE_DEMO_MODE",),
    ),
    (
        "retired_string",
        "rule_6_no_legacy_names",
        ("rule 6: demo: views.py:3 names retired setting QUICKSCALE_DEMO_MODE",),
    ),
    (
        "format_flag",
        "rule_17_management_commands",
        ("rule 17: demo: quickscale_demo_report spells machine output --format; use --json",),
    ),
    (
        "scheduled_alias",
        "rule_17_management_commands",
        (
            "rule 17: demo: quickscale_demo_report keeps the retired --scheduled alias; "
            "use --trigger scheduled",
        ),
    ),
    (
        "bad_trigger",
        "rule_17_management_commands",
        (
            "rule 17: demo: quickscale_demo_report --trigger must offer manual and scheduled",
            "rule 17: demo: quickscale_demo_report --trigger must default to manual",
        ),
    ),
    (
        "purge_no_confirm",
        "rule_17_management_commands",
        ("rule 17: demo: quickscale_demo_purge deletes data and takes no --confirm",),
    ),
    (
        "print_call",
        "rule_17_management_commands",
        ("rule 17: demo: quickscale_demo_run calls print()",),
    ),
    (
        "exit_call",
        "rule_17_management_commands",
        ("rule 17: demo: quickscale_demo_run calls sys.exit()",),
    ),
    ("conforming_command", "rule_17_management_commands", ()),
    ("clean", "rule_23_service_surface", ()),
    (
        "missing_all",
        "rule_23_service_surface",
        ("rule 23: demo: services.py declares no __all__",),
    ),
    (
        "missing_services",
        "rule_23_service_surface",
        ("rule 23: demo: services.py is missing",),
    ),
    (
        "undefined_export",
        "rule_23_service_surface",
        ("rule 23: demo: service 'missing' in __all__ is not defined",),
    ),
    (
        "positional_param",
        "rule_23_service_surface",
        (
            "rule 23: demo: demo_query takes 2 positional parameter(s); services take "
            "keyword-only parameters after at most one subject",
        ),
    ),
    (
        "cross_import_hidden",
        "rule_23_service_surface",
        ("rule 23: consumer: views.py:1 imports 'hidden' outside provider's services.__all__",),
    ),
    (
        "member_hidden",
        "rule_23_service_surface",
        ("rule 23: consumer: views.py:5 uses provider.services.hidden outside services.__all__",),
    ),
    ("clean", "rule_11_package_files", ()),
    ("missing_py_typed", "rule_11_package_files", ("rule 11: demo: missing py.typed",)),
    (
        "one_off_file",
        "rule_11_package_files",
        ("rule 11: demo: helpers.py must fold into a standard file or become private",),
    ),
    (
        "no_is_enabled",
        "rule_11_package_files",
        ("rule 11: demo: services.py does not publish is_enabled()",),
    ),
    ("clean", "rule_15_package_root", ()),
    (
        "root_extra",
        "rule_15_package_root",
        ("rule 15: demo: __init__.py holds Assign outside __version__/__all__",),
    ),
    ("clean", "rule_16_signals", ()),
    (
        "signal_receiver",
        "rule_16_signals",
        (
            "rule 16: demo: signals.py holds FunctionDef",
            "rule 16: demo: signals.py defines a receiver function",
        ),
    ),
    ("clean", "rule_18_package_tooling", ()),
    (
        "tooling_broken",
        "rule_18_package_tooling",
        (
            "rule 18: demo: pyproject has no pytest ini_options",
            "rule 18: demo: pyproject has no [tool.ruff]",
        ),
    ),
)


def test_facade_publishes_the_pre_split_surface() -> None:
    """The facade's ``__all__`` is the pre-split module's own name set."""
    assert rules_package.__all__ == FROZEN_SURFACE
    for name in FROZEN_SURFACE:
        assert getattr(rules_package, name) is not None


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert rules_package.ast is ast
    assert rules_package.tomllib is tomllib
    assert rules_package.Mapping is Mapping
    assert rules_package.Path is Path
    assert rules_package.Any is Any
    for name in FROZEN_IMPORTED_BINDINGS:
        assert getattr(rules_package, name) is not None
    for name in FROZEN_CORE_HELPERS:
        assert getattr(rules_package, name) is getattr(core, name)


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each pre-split callable keeps its pre-split signature through the facade."""
    assert {
        name: str(inspect.signature(getattr(rules_package, name))) for name in FROZEN_SIGNATURES
    } == FROZEN_SIGNATURES


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world."""
    assert ("scripts", "module_conventions/rules_package.py") in RULE_37_ALLOWED_LITERAL_FILES
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
                assert node.module.split(".")[-1] not in {"rules_package", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_package", "registry"}, (
                        name,
                        node.lineno,
                    )


def test_orchestrators_and_entrypoints_keep_their_homes() -> None:
    """Rules 4, 6, 17, and 23 stay orchestrated by the facade."""
    for name in (
        "rule_4_public_surface",
        "rule_6_no_legacy_names",
        "rule_17_management_commands",
        "rule_23_service_surface",
    ):
        assert getattr(rules_package, name).__module__ == (
            "scripts.module_conventions.rules_package"
        )
    for name in (
        "rule_11_package_files",
        "rule_15_package_root",
        "rule_16_signals",
        "rule_18_package_tooling",
        "_has_tenant_model",
    ):
        assert getattr(rules_package, name).__module__ == (
            "scripts.module_conventions._package_files"
        )
    for name in (
        "_public_surface",
        "_module_member_bindings",
        "_private_member_accesses",
        "_module_string_constants",
        "_capability_arguments",
    ):
        assert getattr(rules_package, name).__module__ == (
            "scripts.module_conventions._package_surfaces"
        )
    for name in (
        "_settings_attribute_names",
        "_mapping_entries",
        "_retired_declaration_keys",
        "_manifest_retired_settings",
        "_all_option_keys",
    ):
        assert getattr(rules_package, name).__module__ == (
            "scripts.module_conventions._package_legacy"
        )
    for name in ("_command_flags", "_literal_strings", "_constant_string"):
        assert getattr(rules_package, name).__module__ == (
            "scripts.module_conventions._package_commands"
        )
    for name in ("_service_functions", "_module_bindings"):
        assert getattr(rules_package, name).__module__ == (
            "scripts.module_conventions._package_services"
        )


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registry's detectors are the facade callables, not siblings."""
    detectors = {rule.number: rule.detector for rule in registry.RULES}
    for number, name in (
        (4, "rule_4_public_surface"),
        (6, "rule_6_no_legacy_names"),
        (11, "rule_11_package_files"),
        (15, "rule_15_package_root"),
        (16, "rule_16_signals"),
        (17, "rule_17_management_commands"),
        (18, "rule_18_package_tooling"),
        (23, "rule_23_service_surface"),
    ):
        assert detectors[number] is getattr(rules_package, name)
        assert getattr(checker, name) is getattr(rules_package, name)


@pytest.mark.parametrize(
    ("case", "detector", "expected"),
    EXACT_FINDINGS,
    ids=[f"{case}-{detector}" for case, detector, _ in EXACT_FINDINGS],
)
def test_detector_findings_are_exact_and_ordered(
    case: str, detector: str, expected: tuple[str, ...]
) -> None:
    corpus = CASE_BUILDERS[case]()
    assert getattr(rules_package, detector)(corpus) == list(expected)
