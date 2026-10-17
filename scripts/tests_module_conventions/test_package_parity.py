"""
Behavioral controls for the ``rules_package`` split (SA267).

The public-surface scan, the legacy-name checks, the management-command
analysis, the service-surface scan, and rules 11/15/16/18 live in private
siblings (``_package_surfaces``, ``_package_legacy``, ``_package_commands``,
``_package_services``, ``_package_files``) behind the ``rules_package`` facade.
SA267 has closed, so SA279 retired the pre-split surface pins; these controls
keep the split's structural invariants and the exact ordered findings of
representative corpora captured from the pre-split module, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.check_module_conventions import Module
from scripts.module_conventions import (
    _package_commands,
    _package_files,
    _package_legacy,
    _package_pyproject,
    _package_services,
    _package_surfaces,
    rules_package,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _with_addopts,
    _with_files,
)

SPLIT_SIBLINGS = {
    "_package_commands": _package_commands,
    "_package_files": _package_files,
    "_package_legacy": _package_legacy,
    "_package_pyproject": _package_pyproject,
    "_package_services": _package_services,
    "_package_surfaces": _package_surfaces,
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
    "app_config_walk": lambda: _corpus(
        _with_files(
            _golden_module(),
            views=(
                "from django.apps import apps\n\n\n"
                "def invalidate(org_id):\n"
                "    for app_config in sorted(apps.get_app_configs(), "
                "key=lambda c: c.label):\n"
                "        hook = getattr(app_config, 'invalidate_organization_cache', None)\n"
                "        if callable(hook):\n"
                "            hook(org_id)\n"
            ),
        )
    ),
    "app_config_walk_seam": lambda: _corpus(
        _with_files(
            _golden_module("auth"),
            **{
                "_account_deletion_providers.py": (
                    "from django.apps import apps\n\n\n"
                    "def discover():\n"
                    "    hooks = []\n"
                    "    for app_config in sorted(apps.get_app_configs(), "
                    "key=lambda c: c.label):\n"
                    "        hook = getattr(\n"
                    "            app_config, 'reconcile_account_deletion_provider_state', None\n"
                    "        )\n"
                    "        if callable(hook):\n"
                    "            hooks.append(hook)\n"
                    "    return hooks\n"
                )
            },
        )
    ),
    "app_config_walk_aliased": lambda: _corpus(
        _with_files(
            _golden_module(),
            views=(
                "from django.apps import apps\n\n\n"
                "def invalidate(org_id):\n"
                "    configs = sorted(apps.get_app_configs(), key=lambda c: c.label)\n"
                "    for app_config in configs:\n"
                "        hook = getattr(app_config, 'invalidate_organization_cache', None)\n"
                "        if callable(hook):\n"
                "            hook(org_id)\n"
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
    "checks_relist": lambda: _corpus(
        _with_files(
            _golden_module(),
            checks="_PROJECTED_SECRETS = ('QUICKSCALE_DEMO_SECRET_KEY',)\n",
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
    "organization_flag": lambda: _corpus(
        _command_module(
            "report",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--organization')\n",
        )
    ),
    "org_flag": lambda: _corpus(
        _command_module(
            "report",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--org')\n",
        )
    ),
    "organization_slug_flag": lambda: _corpus(
        _command_module(
            "report",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--organization-slug')\n",
        )
    ),
    "slug_without_selector": lambda: _corpus(
        _command_module(
            "purge",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--slug')\n"
            "        parser.add_argument('--confirm')\n"
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
            "from quickscale_core.runtime import require_scheduled_module_enabled\n"
            "\n"
            "\n"
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--confirm')\n"
            "        parser.add_argument('--dry-run', action='store_true')\n"
            "        parser.add_argument('--organization-id')\n"
            "        parser.add_argument('--slug')\n"
            "        parser.add_argument('--trigger', choices=['manual', 'scheduled'], "
            "default='manual')\n"
            "        parser.add_argument('--json', action='store_true')\n"
            "\n"
            "    def handle(self, *args, **options):\n"
            "        require_scheduled_module_enabled(options['trigger'], "
            "module_name='demo')\n",
        )
    ),
    "trigger_without_helper": lambda: _corpus(
        _command_module(
            "report",
            "class Command:\n"
            "    def add_arguments(self, parser):\n"
            "        parser.add_argument('--trigger', choices=['manual', 'scheduled'], "
            "default='manual')\n",
        )
    ),
    "private_support_module": lambda: _corpus(
        _with_files(
            _golden_module(),
            **{
                "management/commands/_support.py": (
                    "class Command:\n"
                    "    def add_arguments(self, parser):\n"
                    "        parser.add_argument('--format')\n"
                    "        parser.add_argument('--trigger', choices=['scheduled'])\n"
                    "    def handle(self, *args, **options):\n"
                    "        print('x')\n"
                )
            },
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
    "coverage_path_form": lambda: _corpus(
        _with_addopts(_golden_module(), "-v --cov=src/quickscale_modules_demo")
    ),
    "coverage_targetless": lambda: _corpus(
        _with_addopts(_golden_module(), "-v --cov=quickscale_modules_demo --cov")
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
    (
        "app_config_walk",
        "rule_4_public_surface",
        (
            "rule 4: demo: views.py:6 reads an app config through getattr(); "
            "collect the capability through collect_capabilities",
        ),
    ),
    ("app_config_walk_seam", "rule_4_public_surface", ()),
    (
        "app_config_walk_aliased",
        "rule_4_public_surface",
        (
            "rule 4: demo: views.py:7 reads an app config through getattr(); "
            "collect the capability through collect_capabilities",
        ),
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
        "checks_relist",
        "rule_6_no_legacy_names",
        (
            "rule 6: demo: checks.py:1 names setting QUICKSCALE_DEMO_SECRET_KEY; "
            "read it from the manifest projection",
        ),
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
            "rule 17: demo: quickscale_demo_report --trigger must refuse scheduled "
            "runs through require_scheduled_module_enabled",
        ),
    ),
    (
        "purge_no_confirm",
        "rule_17_management_commands",
        ("rule 17: demo: quickscale_demo_purge deletes data and takes no --confirm",),
    ),
    (
        "organization_flag",
        "rule_17_management_commands",
        (
            "rule 17: demo: quickscale_demo_report spells an organization selector "
            "--organization; use --organization-id <uuid>",
        ),
    ),
    (
        "org_flag",
        "rule_17_management_commands",
        (
            "rule 17: demo: quickscale_demo_report spells an organization selector "
            "--org; use --organization-id <uuid>",
        ),
    ),
    (
        "organization_slug_flag",
        "rule_17_management_commands",
        (
            "rule 17: demo: quickscale_demo_report spells an organization selector "
            "--organization-slug; use --organization-id <uuid>",
        ),
    ),
    (
        "slug_without_selector",
        "rule_17_management_commands",
        (
            "rule 17: demo: quickscale_demo_purge offers --slug without --organization-id; "
            "a slug lookup is non-destructive preflight",
        ),
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
    (
        "trigger_without_helper",
        "rule_17_management_commands",
        (
            "rule 17: demo: quickscale_demo_report --trigger must refuse scheduled "
            "runs through require_scheduled_module_enabled",
        ),
    ),
    ("private_support_module", "rule_17_management_commands", ()),
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
            "rule 18: demo: pyproject is missing the [tool.poetry] table",
            "rule 18: demo: pyproject is missing the [tool.poetry.dependencies] table",
            "rule 18: demo: pyproject is missing the [tool.poetry.group.dev.dependencies] table",
            "rule 18: demo: pyproject is missing the [build-system] table",
            "rule 18: demo: pyproject is missing the [tool.ruff] table",
            "rule 18: demo: pyproject is missing the [tool.ruff.lint] table",
            "rule 18: demo: pyproject is missing the [tool.ruff.lint.per-file-ignores] table",
            "rule 18: demo: pyproject is missing the [tool.pytest.ini_options] table",
            "rule 18: demo: pyproject is missing the [tool.coverage.report] table",
            "rule 18: demo: pyproject is missing the [tool.django-stubs] table",
            "rule 18: demo: pyproject name is None; the template derives 'quickscale-module-demo'",
            "rule 18: demo: pyproject description is missing",
            "rule 18: demo: pyproject [project] has no 'requires-python'",
            "rule 18: demo: pyproject [project] has no 'readme'",
            "rule 18: demo: pyproject [project] has no 'license'",
            "rule 18: demo: pyproject [project] has no 'authors'",
            "rule 18: demo: pyproject [project] has no 'dynamic'",
        ),
    ),
    (
        "coverage_path_form",
        "rule_18_package_tooling",
        (
            "rule 18: demo: pyproject --cov target 'src/quickscale_modules_demo' does not "
            "name the import package 'quickscale_modules_demo'",
        ),
    ),
    (
        "coverage_targetless",
        "rule_18_package_tooling",
        (
            "rule 18: demo: pyproject --cov takes no target; name the import package "
            "'quickscale_modules_demo'",
        ),
    ),
)


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
