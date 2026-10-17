"""Control cases for the package module-convention rules."""

from __future__ import annotations

import copy
from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Corpus, Module
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _violations,
    _with_addopts,
    _with_files,
    _with_pyproject,
)


def test_package_root_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{"__init__.py": module.files["__init__.py"] + "default_app_config = 'demo'\n"},
    )
    assert _violations(checker.rule_15_package_root, broken)


def test_signals_receiver_control() -> None:
    module = _golden_module()
    broken = _with_files(module, **{"signals.py": "def receiver():\n    pass\n"})
    assert _violations(checker.rule_16_signals, broken)


def test_command_output_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_run.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def handle(self, *args, **options):\n"
                "        print('x')\n"
            )
        },
    )
    assert any(
        "calls print()" in violation
        for violation in _violations(checker.rule_17_management_commands, broken)
    )


def test_destructive_command_dry_run_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_purge.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def handle(self, *args, **options):\n"
                "        return None\n"
            )
        },
    )
    assert any(
        "dry-run" in violation
        for violation in _violations(checker.rule_17_management_commands, broken)
    )


def test_command_base_control() -> None:
    """Rule 17: a command's Command class subclasses BaseCommand."""
    module = _golden_module()
    assert _violations(checker.rule_17_management_commands, module) == []
    no_base = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_run.py": (
                "class Command:\n    def handle(self, *args, **options):\n        return None\n"
            )
        },
    )
    assert any(
        "does not subclass BaseCommand" in violation
        for violation in _violations(checker.rule_17_management_commands, no_base)
    )
    no_class = _with_files(
        module,
        **{"management/commands/quickscale_demo_run.py": "def handle():\n    return None\n"},
    )
    assert any(
        "defines no Command class" in violation
        for violation in _violations(checker.rule_17_management_commands, no_class)
    )
    aliased = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_run.py": (
                "from django.core.management.base import BaseCommand as DjangoBaseCommand\n"
                "\n"
                "\n"
                "class Command(DjangoBaseCommand):\n"
                "    def handle(self, *args, **options):\n"
                "        return None\n"
            )
        },
    )
    assert _violations(checker.rule_17_management_commands, aliased) == []
    wrong_origin = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_run.py": (
                "from demo.helpers import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def handle(self, *args, **options):\n"
                "        return None\n"
            )
        },
    )
    assert any(
        "does not subclass BaseCommand" in violation
        for violation in _violations(checker.rule_17_management_commands, wrong_origin)
    )


def test_command_error_control() -> None:
    """Rule 17: a command reports failures by raising CommandError."""
    module = _golden_module()

    def _command(source: str) -> Module:
        return _with_files(module, **{"management/commands/quickscale_demo_run.py": source})

    raising = _command(
        "from django.core.management.base import BaseCommand, CommandError\n"
        "\n"
        "\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        raise CommandError('Requested snapshot does not exist.')\n"
    )
    assert _violations(checker.rule_17_management_commands, raising) == []
    wrong_type = _command(
        "from django.core.management.base import BaseCommand\n"
        "\n"
        "\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        raise ValueError('bad input')\n"
    )
    assert any(
        "raises ValueError; commands report failures through "
        "django.core.management.base.CommandError" in violation
        for violation in _violations(checker.rule_17_management_commands, wrong_type)
    )
    wrong_origin = _command(
        "from django.core.management.base import BaseCommand\n"
        "from demo.helpers import CommandError\n"
        "\n"
        "\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        raise CommandError('Requested snapshot does not exist.')\n"
    )
    assert any(
        "raises CommandError; commands report failures through "
        "django.core.management.base.CommandError" in violation
        for violation in _violations(checker.rule_17_management_commands, wrong_origin)
    )
    re_raising = _command(
        "from django.core.management.base import BaseCommand\n"
        "\n"
        "\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        try:\n"
        "            risky()\n"
        "        except DemoError:\n"
        "            raise\n"
    )
    assert _violations(checker.rule_17_management_commands, re_raising) == []
    internal_raise = _command(
        "from django.core.management.base import BaseCommand, CommandError\n"
        "\n"
        "\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        try:\n"
        "            raise ValueError('bad input')\n"
        "        except ValueError:\n"
        "            raise CommandError('--snapshot-id must be an integer.')\n"
    )
    assert any(
        "raises ValueError" in violation
        for violation in _violations(checker.rule_17_management_commands, internal_raise)
    )
    aliased = _command(
        "from django.core.management.base import BaseCommand, CommandError as QSError\n"
        "\n"
        "\n"
        "class Command(BaseCommand):\n"
        "    def handle(self, *args, **options):\n"
        "        raise QSError('Requested snapshot does not exist.')\n"
    )
    assert _violations(checker.rule_17_management_commands, aliased) == []


def test_package_tooling_control() -> None:
    module = _golden_module()
    broken = replace(module, root_files={**module.root_files, "pyproject.toml": "[project]\n"})
    assert _violations(checker.rule_18_package_tooling, broken)
    missing_tests = replace(module, tests={})
    assert _violations(checker.rule_18_package_tooling, missing_tests)


def test_module_directory_without_manifest_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_18_package_tooling, module, extra_dirs=("stray",))


def test_package_root_requires_declarations() -> None:
    module = _golden_module()
    broken = _with_files(module, **{"__init__.py": '"""Demo."""\n'})
    violations = _violations(checker.rule_15_package_root, broken)
    assert any("__version__" in violation for violation in violations)
    assert any("__all__" in violation for violation in violations)


def test_malformed_tool_shape_is_a_violation() -> None:
    module = _golden_module()
    broken = replace(
        module,
        root_files={**module.root_files, "pyproject.toml": "tool = 1\n"},
    )
    assert any(
        "pytest" in violation for violation in _violations(checker.rule_18_package_tooling, broken)
    )


def test_coverage_target_control() -> None:
    """Rule 18: --cov names the module's import package, never a src/ path."""
    module = _golden_module()
    assert _violations(checker.rule_18_package_tooling, module) == []
    assert _violations(checker.rule_18_package_tooling, _golden_module("blog")) == []
    space_form = _with_addopts(module, "-v --cov quickscale_modules_demo --cov-fail-under=90")
    assert _violations(checker.rule_18_package_tooling, space_form) == []
    path_form = _with_addopts(module, "-v --cov=src/quickscale_modules_demo --cov-fail-under=90")
    assert any(
        "pyproject --cov target 'src/quickscale_modules_demo' does not name "
        "the import package 'quickscale_modules_demo'" in violation
        for violation in _violations(checker.rule_18_package_tooling, path_form)
    )
    other_package = _with_addopts(module, "-v --cov=quickscale_modules_orgs")
    assert any(
        "pyproject --cov target 'quickscale_modules_orgs' does not name "
        "the import package 'quickscale_modules_demo'" in violation
        for violation in _violations(checker.rule_18_package_tooling, other_package)
    )
    report_flag_only = _with_addopts(module, "-v --cov-report=html")
    assert any(
        "pyproject addopts declares no --cov target" in violation
        for violation in _violations(checker.rule_18_package_tooling, report_flag_only)
    )
    trailing_bare = _with_addopts(module, "-v --cov=quickscale_modules_demo --cov")
    assert any(
        "pyproject --cov takes no target" in violation
        for violation in _violations(checker.rule_18_package_tooling, trailing_bare)
    )
    option_after_bare = _with_addopts(module, "-v --cov --cov-report=html")
    assert any(
        "pyproject --cov takes no target" in violation
        for violation in _violations(checker.rule_18_package_tooling, option_after_bare)
    )


def test_pyproject_template_control() -> None:
    """Rule 18: the module pyproject files follow one template (SA293 (c))."""
    module = _golden_module()
    template = module.root_files["pyproject.toml"]
    assert _violations(checker.rule_18_package_tooling, module) == []

    stale = _with_pyproject(
        module,
        template.replace(
            "[tool.poetry.group.dev.dependencies]\n",
            "# pytest, pytest-cov, ruff, mypy centralized in root pyproject.toml\n"
            "[tool.poetry.group.dev.dependencies]\n",
        ),
    )
    assert any(
        "pyproject keeps the stale 'centralized in root' comment" in violation
        for violation in _violations(checker.rule_18_package_tooling, stale)
    )

    missing = _with_pyproject(
        module, template.replace("[tool.coverage.report]\nfail_under = 90\n\n", "")
    )
    assert any(
        "pyproject is missing the [tool.coverage.report] table" in violation
        for violation in _violations(checker.rule_18_package_tooling, missing)
    )

    reordered = _with_pyproject(
        module,
        template.replace(
            "[tool.django-stubs]\ndjango_settings_module = 'tests.settings'\n", ""
        ).replace(
            "[tool.coverage.report]\n",
            "[tool.django-stubs]\ndjango_settings_module = 'tests.settings'\n"
            "\n[tool.coverage.report]\n",
        ),
    )
    assert any(
        "pyproject tables are not in the template order" in violation
        for violation in _violations(checker.rule_18_package_tooling, reordered)
    )

    unexpected = _with_pyproject(module, template + "\n[tool.bandit]\n")
    assert any(
        "pyproject table [tool.bandit] is not part of the template" in violation
        for violation in _violations(checker.rule_18_package_tooling, unexpected)
    )

    root_key = _with_pyproject(
        module, template.replace("[project]", "keywords = ['release']\n\n[project]", 1)
    )
    assert any(
        "pyproject key 'keywords' is not part of the template" in violation
        for violation in _violations(checker.rule_18_package_tooling, root_key)
    )

    extra_group = _with_pyproject(
        module,
        template.replace(
            "[tool.poetry.group.dev.dependencies]",
            "[tool.poetry.group.docs.dependencies]\nfoo = '^1'\n\n"
            "[tool.poetry.group.dev.dependencies]",
            1,
        ),
    )
    assert any(
        "pyproject [tool.poetry.group] key 'docs' is not part of the template" in violation
        for violation in _violations(checker.rule_18_package_tooling, extra_group)
    )

    one_pythonpath = _with_pyproject(
        module,
        template.replace(
            "pythonpath = ['.', 'src', '../..']", "pythonpath = ['.', 'src', '../orgs/src']"
        ),
    )
    assert any(
        "pythonpath is ['.', 'src', '../orgs/src']" in violation
        for violation in _violations(checker.rule_18_package_tooling, one_pythonpath)
    )

    one_marker_set = _with_pyproject(
        module,
        template.replace(
            "    'e2e: End-to-end integration tests that exercise the full user workflow',\n",
            "",
        ),
    )
    assert any(
        "pyproject [tool.pytest.ini_options] markers are" in violation
        for violation in _violations(checker.rule_18_package_tooling, one_marker_set)
    )

    floor = _with_pyproject(
        module, template.replace("pytest-django = '^4.11.1'", "pytest-django = '>=4.11.1'")
    )
    assert any(
        "pyproject [tool.poetry.group.dev.dependencies] pytest-django is '>=4.11.1'; "
        "the template's is '^4.11.1'" in violation
        for violation in _violations(checker.rule_18_package_tooling, floor)
    )

    extra_floor = _with_pyproject(
        module,
        template.replace(
            "pytest-django = '^4.11.1'",
            "pytest-django = '^4.11.1'\ndjango-filter = '>=26.1'",
        ),
    )
    assert any(
        "dev dependency 'django-filter' is '>=26.1'; dev specs take the caret form" in violation
        for violation in _violations(checker.rule_18_package_tooling, extra_floor)
    )

    extra_ini_key = _with_pyproject(
        module,
        template.replace("testpaths = ['tests']", "testpaths = ['tests']\nnorecursedirs = ['.']"),
    )
    assert any(
        "pyproject [tool.pytest.ini_options] key 'norecursedirs' is not part of the template"
        in violation
        for violation in _violations(checker.rule_18_package_tooling, extra_ini_key)
    )

    per_module = _with_pyproject(
        module,
        template.replace(
            "pytest-django = '^4.11.1'",
            "pytest-django = '^4.11.1'\ndjango-filter = '^26.1'",
        ).replace(
            "quickscale-core = {path = '../../quickscale_core', develop = true}",
            "posthog = '^7.33.0'\n"
            "quickscale-core = {path = '../../quickscale_core', develop = true}",
        ),
    )
    assert _violations(checker.rule_18_package_tooling, per_module) == []


BASE_TEST_SETTINGS_FIXTURE = """\
BASE_TEST_SETTINGS_KEYS = ("SECRET_KEY", "USE_TZ")
"""

TEST_SETTINGS_FIXTURE = """\
from quickscale_core.testing.settings import suite_secret_key

SECRET_KEY = suite_secret_key("demo")
USE_TZ = True
QUICKSCALE_DEMO_ENABLED = True
"""

TEST_CONFTEST_FIXTURE = """\
from quickscale_core.testing.pytest_plugin import (
    pytest_collection_modifyitems,
    pytest_configure,
)
"""


def _shared_test_support_module(
    *,
    settings: str = TEST_SETTINGS_FIXTURE,
    conftest: str | None = TEST_CONFTEST_FIXTURE,
) -> Module:
    """Build a module whose tests adopt the core base and plugin fixtures."""
    module = _golden_module()
    tests = {**module.tests, "settings.py": settings}
    if conftest is None:
        tests.pop("conftest.py", None)
    else:
        tests["conftest.py"] = conftest
    return replace(module, tests=tests)


def _shared_test_support_corpus(*modules: Module) -> Corpus:
    """Build a corpus whose core tree carries the base and plugin fixtures."""
    return replace(
        _corpus(*modules),
        core_files={
            "testing/settings.py": BASE_TEST_SETTINGS_FIXTURE,
            "testing/pytest_plugin.py": "",
        },
    )


def test_shared_test_settings_base_control() -> None:
    """Rule 18: each module's tests/settings.py comes from the core base."""
    assert (
        checker.rule_18_package_tooling(_shared_test_support_corpus(_shared_test_support_module()))
        == []
    )

    without_import = _shared_test_support_module(settings="SECRET_KEY = 'test'\nUSE_TZ = True\n")
    findings = checker.rule_18_package_tooling(_shared_test_support_corpus(without_import))
    assert any("does not import the core test-settings base" in violation for violation in findings)

    missing_key = _shared_test_support_module(
        settings=TEST_SETTINGS_FIXTURE.replace("USE_TZ = True\n", "")
    )
    findings = checker.rule_18_package_tooling(_shared_test_support_corpus(missing_key))
    assert any("does not define USE_TZ (core base key)" in violation for violation in findings)

    extra_keys = _shared_test_support_module(
        settings=TEST_SETTINGS_FIXTURE + "QUICKSCALE_DEMO_BACKEND = 'local'\n"
    )
    assert checker.rule_18_package_tooling(_shared_test_support_corpus(extra_keys)) == []


def test_shared_conftest_plugin_control() -> None:
    """Rule 18: conftest hooks come from the core plugin; wrappers delegate."""
    assert (
        checker.rule_18_package_tooling(_shared_test_support_corpus(_shared_test_support_module()))
        == []
    )

    local_copy = _shared_test_support_module(
        conftest=(
            "def pytest_configure(config):\n"
            "    pass\n\n\n"
            "def pytest_collection_modifyitems(config, items):\n"
            "    pass\n"
        )
    )
    findings = checker.rule_18_package_tooling(_shared_test_support_corpus(local_copy))
    assert any(
        "does not take pytest_configure from the core conftest plugin" in violation
        for violation in findings
    )
    assert any(
        "does not take pytest_collection_modifyitems from the core conftest plugin" in violation
        for violation in findings
    )

    wrapper = _shared_test_support_module(
        conftest=(
            "from quickscale_core.testing.pytest_plugin import (\n"
            "    pytest_collection_modifyitems,\n"
            "    pytest_configure as shared_pytest_configure,\n"
            ")\n\n\n"
            "def pytest_configure(config):\n"
            "    shared_pytest_configure(config)\n"
            "    config.option.reuse_db = True\n"
        )
    )
    assert checker.rule_18_package_tooling(_shared_test_support_corpus(wrapper)) == []

    non_delegating = _shared_test_support_module(
        conftest=(
            "from quickscale_core.testing.pytest_plugin import (\n"
            "    pytest_collection_modifyitems,\n"
            "    pytest_configure as shared_pytest_configure,\n"
            ")\n\n\n"
            "def pytest_configure(config):\n"
            "    config.option.reuse_db = True\n"
        )
    )
    findings = checker.rule_18_package_tooling(_shared_test_support_corpus(non_delegating))
    assert any(
        "defines a local pytest_configure that does not call the core conftest plugin hook"
        in violation
        for violation in findings
    )

    nested_import = _shared_test_support_module(
        conftest=(
            "def _apply(config):\n"
            "    from quickscale_core.testing.pytest_plugin import pytest_configure as shared\n"
            "    shared(config)\n"
            "\n"
            "def pytest_configure(config):\n"
            "    shared(config)\n"
        )
    )
    findings = checker.rule_18_package_tooling(_shared_test_support_corpus(nested_import))
    assert any(
        "does not take pytest_configure from the core conftest plugin" in violation
        for violation in findings
    )

    missing_conftest = _shared_test_support_module(conftest=None)
    findings = checker.rule_18_package_tooling(_shared_test_support_corpus(missing_conftest))
    assert any("does not adopt the core conftest plugin" in violation for violation in findings)


def test_shared_test_support_core_tree_control() -> None:
    """Rule 18: a loaded core tree missing the base or plugin fails."""
    corpus = _shared_test_support_corpus(_shared_test_support_module())
    assert checker.rule_18_package_tooling(corpus) == []

    without_base = {
        rel: text for rel, text in corpus.core_files.items() if rel != "testing/settings.py"
    }
    findings = checker.rule_18_package_tooling(replace(corpus, core_files=without_base))
    assert any("carries no shared test-settings base" in violation for violation in findings)

    without_plugin = {
        rel: text for rel, text in corpus.core_files.items() if rel != "testing/pytest_plugin.py"
    }
    findings = checker.rule_18_package_tooling(replace(corpus, core_files=without_plugin))
    assert any("carries no conftest plugin" in violation for violation in findings)

    keyless_base = {"testing/settings.py": "SECRET_KEY = 'test'\n", "testing/pytest_plugin.py": ""}
    findings = checker.rule_18_package_tooling(replace(corpus, core_files=keyless_base))
    assert any("declares no BASE_TEST_SETTINGS_KEYS tuple" in violation for violation in findings)


def test_shared_test_support_skips_an_empty_corpus() -> None:
    """An empty synthetic corpus skips the clause, as rule 31 does."""
    module = _shared_test_support_module(settings="SECRET_KEY = 'test'\n", conftest=None)
    assert checker.rule_18_package_tooling(_corpus(module)) == []


def test_cross_module_import_outside_public_surface_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="from quickscale_modules_storage._helpers import select_storage_backend\n",
    )
    assert any(
        "outside the module's public surface" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )
    assert _violations(checker.rule_4_public_surface, module) == []


def test_cross_module_private_name_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="from quickscale_modules_orgs.current_org import _restore_current_org_id\n",
    )
    assert any(
        "imports private name '_restore_current_org_id' from orgs" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )
    assert _violations(checker.rule_4_public_surface, module) == []


def test_qualified_private_foundation_member_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "import quickscale_modules_orgs.current_org as org_context\n\n\n"
            "def restore(prior):\n"
            "    org_context._restore_current_org_id(prior)\n"
        ),
    )
    assert any(
        "reads private member org_context._restore_current_org_id of orgs" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )
    raw_path = _with_files(
        module,
        views=(
            "import quickscale_modules_orgs\n\n\n"
            "def restore(prior):\n"
            "    quickscale_modules_orgs.admin._org_db_context(prior)\n"
        ),
    )
    assert any(
        "reads private member" in violation
        for violation in _violations(checker.rule_4_public_surface, raw_path)
    )
    public_member = _with_files(
        module,
        views=(
            "import quickscale_modules_orgs.current_org as org_context\n\n\n"
            "def restore(organization):\n"
            "    with org_context.org_scope(organization):\n"
            "        pass\n"
        ),
    )
    assert _violations(checker.rule_4_public_surface, public_member) == []
    same_module = _with_files(
        _golden_module("orgs"),
        views=(
            "import quickscale_modules_orgs\n\n\n"
            "def restore(prior):\n"
            "    quickscale_modules_orgs.current_org._restore_current_org_id(prior)\n"
        ),
    )
    assert _violations(checker.rule_4_public_surface, same_module) == []


def test_orgs_extension_base_import_is_allowed() -> None:
    module = _golden_module()
    # The golden fixture's models.py builds on orgs' published extension base.
    assert _violations(checker.rule_4_public_surface, module) == []


def test_package_root_import_checks_every_name_control() -> None:
    module = _golden_module()
    broken = _with_files(module, views="from quickscale_modules_orgs import models, checks\n")
    assert any(
        "imports orgs:checks" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )


def test_cross_module_setting_read_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.conf import settings\n\n\nRATE = settings.QUICKSCALE_BLOG_POSTS_PER_PAGE\n"
        ),
    )
    assert any(
        "reads blog's setting" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )


def test_unknown_capability_vocabulary_is_reported() -> None:
    module = _golden_module()
    unknown = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import collect_capabilities\n\n\n"
            "def handlers() -> tuple[object, ...]:\n"
            "    return collect_capabilities('handlers')\n"
        ),
    )
    assert any(
        "not in CAPABILITIES" in violation
        for violation in _violations(checker.rule_4_public_surface, unknown)
    )


def test_constructed_capability_name_fails_closed() -> None:
    module = _golden_module()
    constructed = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import collect_capabilities\n\n\n"
            "def collect(name: str) -> tuple[object, ...]:\n"
            "    return collect_capabilities(name)\n"
        ),
    )
    assert any(
        "not in CAPABILITIES" in violation
        for violation in _violations(checker.rule_4_public_surface, constructed)
    )


def test_listed_capability_name_and_constant_pass() -> None:
    module = _golden_module()
    listed = _with_files(
        module,
        views=(
            "from quickscale_core.runtime import collect_capabilities\n\n\n"
            "ANONYMIZE_HANDLERS_CAPABILITY = 'anonymize_handlers'\n\n\n"
            "def handlers() -> tuple[object, ...]:\n"
            "    return collect_capabilities('removal_obligations')\n\n\n"
            "def constant_handlers() -> tuple[object, ...]:\n"
            "    return collect_capabilities(ANONYMIZE_HANDLERS_CAPABILITY)\n"
        ),
    )
    assert _violations(checker.rule_4_public_surface, listed) == []


def test_app_config_walk_control() -> None:
    """Rule 4: walking app configs with getattr() is refused, seams excepted."""
    walk = (
        "from django.apps import apps\n\n\n"
        "def invalidate(org_id):\n"
        "    for app_config in sorted(apps.get_app_configs(), key=lambda c: c.label):\n"
        "        hook = getattr(app_config, 'invalidate_organization_cache', None)\n"
        "        if callable(hook):\n"
        "            hook(org_id)\n"
    )
    module = _golden_module()
    broken = _with_files(module, views=walk)
    assert any(
        "reads an app config through getattr()" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )
    assert _violations(checker.rule_4_public_surface, module) == []
    assigned_walk = _with_files(
        module,
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
    assert any(
        "reads an app config through getattr()" in violation
        for violation in _violations(checker.rule_4_public_surface, assigned_walk)
    )
    assigned_single = _with_files(
        module,
        views=(
            "from django.apps import apps\n\n\n"
            "def hook(label):\n"
            "    app_config = apps.get_app_config(label)\n"
            "    return getattr(app_config, 'invalidate_organization_cache', None)\n"
        ),
    )
    assert any(
        "reads an app config through getattr()" in violation
        for violation in _violations(checker.rule_4_public_surface, assigned_single)
    )
    observer = _with_files(
        module,
        views=("def observe(app_config):\n    return getattr(app_config, 'label', '')\n"),
    )
    assert _violations(checker.rule_4_public_surface, observer) == []
    direct = _with_files(
        module,
        views=(
            "from django.apps import apps\n\n\n"
            "def hook():\n"
            "    return getattr(apps.get_app_config('quickscale_demo'), 'hook', None)\n"
        ),
    )
    assert any(
        "reads an app config through getattr()" in violation
        for violation in _violations(checker.rule_4_public_surface, direct)
    )
    seam_source = (
        "from django.apps import apps\n\n\n"
        "def discover():\n"
        "    hooks = []\n"
        "    for app_config in sorted(apps.get_app_configs(), key=lambda c: c.label):\n"
        "        hook = getattr(\n"
        "            app_config, 'reconcile_account_deletion_provider_state', None\n"
        "        )\n"
        "        if callable(hook):\n"
        "            hooks.append(hook)\n"
        "    return hooks\n"
    )
    seam = _with_files(_golden_module("auth"), **{"_account_deletion_providers.py": seam_source})
    assert _violations(checker.rule_4_public_surface, seam) == []
    elsewhere = _with_files(_golden_module(), **{"_account_deletion_providers.py": seam_source})
    assert any(
        "reads an app config through getattr()" in violation
        for violation in _violations(checker.rule_4_public_surface, elsewhere)
    )
    other_attribute = _with_files(
        _golden_module("auth"),
        **{
            "_account_deletion_providers.py": seam_source.replace(
                "reconcile_account_deletion_provider_state", "invalidate_organization_cache"
            )
        },
    )
    assert any(
        "reads an app config through getattr()" in violation
        for violation in _violations(checker.rule_4_public_surface, other_attribute)
    )


def test_migration_model_import_is_excepted() -> None:
    module = _golden_module()
    excepted = _with_files(
        module,
        **{
            "migrations/0001_initial.py": "from quickscale_modules_orgs.models import TenantModel\n"
        },
    )
    assert _violations(checker.rule_4_public_surface, excepted) == []


def test_service_surface_requires_all_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module, **{"services.py": "def demo_query(*, subject):\n    return subject\n"}
    )
    assert any(
        "no __all__" in violation
        for violation in _violations(checker.rule_23_service_surface, broken)
    )
    assert _violations(checker.rule_23_service_surface, module) == []


def test_service_surface_export_must_be_defined_control() -> None:
    module = _golden_module()
    broken = _with_files(module, **{"services.py": '__all__ = ["missing"]\n'})
    assert any(
        "is not defined" in violation
        for violation in _violations(checker.rule_23_service_surface, broken)
    )


def test_service_surface_positional_parameter_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "services.py": (
                '__all__ = ["demo_query"]\n\n\n'
                "def demo_query(subject, other):\n"
                "    return subject\n"
            )
        },
    )
    assert any(
        "positional" in violation
        for violation in _violations(checker.rule_23_service_surface, broken)
    )


def test_service_surface_cross_module_export_control() -> None:
    provider = _golden_module("provider")
    consumer = _golden_module("consumer")
    imported = _with_files(
        consumer,
        views="from quickscale_modules_provider.services import demo_query\n",
    )
    assert _violations(checker.rule_23_service_surface, provider, imported) == []
    hidden = _with_files(
        consumer,
        views="from quickscale_modules_provider.services import hidden\n",
    )
    assert any(
        "outside provider's services.__all__" in violation
        for violation in _violations(checker.rule_23_service_surface, provider, hidden)
    )


def test_aliased_settings_read_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.conf import settings as cfg\n\n\n"
            "RATE = cfg.QUICKSCALE_BLOG_POSTS_PER_PAGE\n"
        ),
    )
    assert any(
        "reads blog's setting" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )


def test_async_service_signature_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "services.py": (
                '__all__ = ["demo_query"]\n\n\n'
                "async def demo_query(subject, other):\n"
                "    return subject\n"
            )
        },
    )
    assert any(
        "positional" in violation
        for violation in _violations(checker.rule_23_service_surface, broken)
    )


def test_re_exported_service_signature_control() -> None:
    module = _golden_module()
    broken = replace(
        module,
        files={
            **module.files,
            "helpers.py": "def demo_query(subject, other):\n    return subject\n",
            "services.py": '__all__ = ["demo_query"]\n\n\nfrom .helpers import demo_query\n',
        },
    )
    assert any(
        "positional" in violation
        for violation in _violations(checker.rule_23_service_surface, broken)
    )
    good = replace(
        broken,
        files={
            **broken.files,
            "helpers.py": "def demo_query(*, subject):\n    return subject\n",
        },
    )
    assert _violations(checker.rule_23_service_surface, good) == []


def test_service_surface_annotated_all_is_accepted() -> None:
    module = _golden_module()
    declared = _with_files(
        module,
        **{
            "services.py": (
                '__all__: list[str] = ["demo_query"]\n\n\n'
                "def demo_query(*, subject: str) -> str:\n"
                "    return subject\n"
            )
        },
    )
    assert _violations(checker.rule_23_service_surface, declared) == []


def test_service_module_member_access_control() -> None:
    provider = _golden_module("provider")
    consumer = _golden_module("consumer")
    hidden = _with_files(
        consumer,
        views=(
            "from quickscale_modules_provider import services as provider_services\n\n\n"
            "def index():\n"
            "    return provider_services.hidden()\n"
        ),
    )
    assert any(
        "outside services.__all__" in violation
        for violation in _violations(checker.rule_23_service_surface, provider, hidden)
    )
    exported = _with_files(
        consumer,
        views=(
            "from quickscale_modules_provider import services as provider_services\n\n\n"
            "def index():\n"
            "    return provider_services.demo_query(subject='x')\n"
        ),
    )
    assert _violations(checker.rule_23_service_surface, provider, exported) == []


def test_qualified_settings_read_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "import django.conf as conf\n\n\nRATE = conf.settings.QUICKSCALE_BLOG_POSTS_PER_PAGE\n"
        ),
    )
    assert any(
        "reads blog's setting" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )


def test_unaliased_qualified_settings_read_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "import django.conf\n\n\nRATE = django.conf.settings.QUICKSCALE_BLOG_POSTS_PER_PAGE\n"
        ),
    )
    assert any(
        "reads blog's setting" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )


def test_parent_module_settings_read_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django import conf as cfg\n\n\n"
            "RATE = cfg.settings.QUICKSCALE_BLOG_POSTS_PER_PAGE\n"
        ),
    )
    assert any(
        "reads blog's setting" in violation
        for violation in _violations(checker.rule_4_public_surface, broken)
    )
    corpus = replace(
        _corpus(module),
        core_files={
            "runtime.py": (
                "from django import conf as cfg\n\nMODE = cfg.settings.QUICKSCALE_ORGS_MODE\n"
            )
        },
    )
    assert any(
        "names module setting" in violation
        for violation in checker.rule_5_dependency_direction(corpus)
    )


def test_renamed_re_exported_service_signature_control() -> None:
    module = _golden_module()
    broken = replace(
        module,
        files={
            **module.files,
            "helpers.py": "def internal(subject, other):\n    return subject\n",
            "services.py": (
                '__all__ = ["demo_query"]\n\n\nfrom .helpers import internal as demo_query\n'
            ),
        },
    )
    assert any(
        "positional" in violation
        for violation in _violations(checker.rule_23_service_surface, broken)
    )
    good = replace(
        broken,
        files={
            **broken.files,
            "helpers.py": "def internal(*, subject):\n    return subject\n",
        },
    )
    assert _violations(checker.rule_23_service_surface, good) == []


def test_unaliased_dotted_service_import_control() -> None:
    provider = _golden_module("provider")
    consumer = _golden_module("consumer")
    exported = _with_files(
        consumer,
        views=(
            "import quickscale_modules_provider.services\n\n\n"
            "def index():\n"
            "    return quickscale_modules_provider.services.demo_query(subject='x')\n"
        ),
    )
    assert _violations(checker.rule_23_service_surface, provider, exported) == []
    hidden = _with_files(
        consumer,
        views=(
            "import quickscale_modules_provider.services\n\n\n"
            "def index():\n"
            "    return quickscale_modules_provider.services.hidden()\n"
        ),
    )
    assert any(
        "outside services.__all__" in violation
        for violation in _violations(checker.rule_23_service_surface, provider, hidden)
    )


def test_legacy_name_controls() -> None:
    module = _golden_module()
    manifest = copy.deepcopy(module.manifest)
    manifest["retired_settings"] = {
        "QUICKSCALE_DEMO_MODE": "Use QUICKSCALE_DEMO_ENABLED instead.",
        "DEMO_POSTS_PER_PAGE": "Use QUICKSCALE_DEMO_POSTS_PER_PAGE instead.",
    }
    declared = replace(module, manifest=manifest)
    assert _violations(checker.rule_6_no_legacy_names, declared) == []
    python_declaration = _with_files(
        module,
        checks=(
            "RETIRED_SETTINGS = {\n"
            '    "QUICKSCALE_DEMO_MODE": "Use QUICKSCALE_DEMO_ENABLED instead.",\n'
            "}\n"
        ),
    )
    assert any(
        "declare them in module.yml" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, python_declaration)
    )
    attribute_read = _with_files(
        declared,
        views=("from django.conf import settings\n\nMODE = settings.QUICKSCALE_DEMO_MODE\n"),
    )
    assert any(
        "reads retired setting QUICKSCALE_DEMO_MODE" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, attribute_read)
    )
    unprefixed_read = _with_files(
        declared,
        views=("from django.conf import settings\n\nPAGE = settings.DEMO_POSTS_PER_PAGE\n"),
    )
    assert any(
        "reads retired setting DEMO_POSTS_PER_PAGE" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, unprefixed_read)
    )
    getattr_read = _with_files(
        declared,
        views=(
            "from django.conf import settings\n\n"
            'MODE = getattr(settings, "QUICKSCALE_DEMO_MODE", "solo")\n'
        ),
    )
    assert any(
        "names retired setting QUICKSCALE_DEMO_MODE" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, getattr_read)
    )
    aliased_manifest = copy.deepcopy(module.manifest)
    aliased_manifest["derivation"]["legacy_aliases"] = [{"old": "enabled"}]
    assert any(
        "legacy alias" in violation
        for violation in _violations(
            checker.rule_6_no_legacy_names, replace(module, manifest=aliased_manifest)
        )
    )
    hidden_option = copy.deepcopy(module.manifest)
    hidden_option["retired_options"] = {"enabled": "Retired."}
    assert any(
        "still accepted" in violation
        for violation in _violations(
            checker.rule_6_no_legacy_names, replace(module, manifest=hidden_option)
        )
    )


def test_checks_setting_relist_control() -> None:
    module = _golden_module()
    relisted = _with_files(
        module,
        checks=(
            "def check_demo() -> list[str]:\n"
            "    return []\n\n\n"
            "_PROJECTED_SECRETS = ('QUICKSCALE_DEMO_SECRET_KEY',)\n"
        ),
    )
    assert any(
        "names setting QUICKSCALE_DEMO_SECRET_KEY" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, relisted)
    )
    hand_authored = _with_files(
        module,
        checks=(
            "from django.conf import settings\n\n\n"
            "def check_demo() -> list[str]:\n"
            '    if not hasattr(settings, "QUICKSCALE_DEMO_SECRET_KEY"):\n'
            '        return ["QUICKSCALE_DEMO_SECRET_KEY is not set."]\n'
            "    return []\n"
        ),
    )
    assert any(
        "names setting QUICKSCALE_DEMO_SECRET_KEY" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, hand_authored)
    )
    message_argument = _with_files(
        module,
        checks=(
            "def check_demo() -> list[str]:\n"
            '    return [Error("QUICKSCALE_DEMO_SECRET_KEY is not set.")]\n'
        ),
    )
    assert _violations(checker.rule_6_no_legacy_names, message_argument) == []
    retired_mapping = _with_files(
        module,
        checks=(
            "RETIRED_SETTINGS = {\n"
            '    "QUICKSCALE_DEMO_MODE": "Use QUICKSCALE_DEMO_ENABLED instead.",\n'
            "}\n"
        ),
    )
    violations = _violations(checker.rule_6_no_legacy_names, retired_mapping)
    assert any("declare them in module.yml" in violation for violation in violations)
    assert not any("names setting" in violation for violation in violations)


def test_checks_projected_recheck_control() -> None:
    """Rule 6: checks delegate the projected presence to the generic check."""
    module = _golden_module()
    direct = _with_files(
        module,
        checks=(
            "from django.conf import settings\n\n"
            "from quickscale_core.runtime import projected_setting_names\n\n\n"
            "def check_demo() -> list[str]:\n"
            "    return [\n"
            "        name\n"
            "        for name in projected_setting_names('demo')\n"
            "        if not hasattr(settings, name)\n"
            "    ]\n"
        ),
    )
    assert any(
        "checks.py:9: re-tests a projected setting's presence" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, direct)
    )
    aliased = _with_files(
        module,
        checks=(
            "from quickscale_core.runtime import projected_setting_names as projection\n"
            "\n"
            "\n"
            "def check_demo():\n"
            "    return projection('demo')\n"
        ),
    )
    assert any(
        "checks.py:5: re-tests a projected setting's presence" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, aliased)
    )
    attribute = _with_files(
        module,
        checks=(
            "import quickscale_core.runtime as runtime\n"
            "\n"
            "\n"
            "def check_demo():\n"
            "    return runtime.projected_setting_names('demo')\n"
        ),
    )
    assert any(
        "checks.py:5: re-tests a projected setting's presence" in violation
        for violation in _violations(checker.rule_6_no_legacy_names, attribute)
    )
    sanctioned = _with_files(
        module,
        checks=(
            "from quickscale_core.runtime import module_settings_are_supplied\n"
            "\n"
            "\n"
            "def check_demo() -> list[str]:\n"
            "    if not module_settings_are_supplied('demo'):\n"
            "        return []\n"
            "    return []\n"
        ),
    )
    assert _violations(checker.rule_6_no_legacy_names, sanctioned) == []


def test_package_file_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_11_package_files, module) == []
    missing = replace(
        module,
        files={key: value for key, value in module.files.items() if key != "py.typed"},
    )
    assert any(
        "missing py.typed" in violation
        for violation in _violations(checker.rule_11_package_files, missing)
    )
    one_off = _with_files(module, **{"helpers.py": "VALUE = 1\n"})
    assert any(
        "must fold into a standard file or become private" in violation
        for violation in _violations(checker.rule_11_package_files, one_off)
    )
    missing_test = replace(
        module,
        tests={key: value for key, value in module.tests.items() if key != "test_apps.py"},
    )
    assert any(
        "missing tests/test_apps.py" in violation
        for violation in _violations(checker.rule_11_package_files, missing_test)
    )
    missing_isolation = replace(
        module,
        tests={key: value for key, value in module.tests.items() if key != "test_isolation.py"},
    )
    assert any(
        "missing tests/test_isolation.py" in violation
        for violation in _violations(checker.rule_11_package_files, missing_isolation)
    )
    no_enabled = _with_files(
        module,
        services=(
            '"""Demo service surface."""\n\n'
            '__all__ = ["demo_query"]\n\n\n'
            "def demo_query(*, subject: str) -> str:\n"
            "    return subject\n"
        ),
    )
    assert any(
        "does not publish is_enabled()" in violation
        for violation in _violations(checker.rule_11_package_files, no_enabled)
    )


def test_command_flag_conventions_controls() -> None:
    module = _golden_module()
    format_flag = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_report.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--format', choices=('human', 'json'))\n"
            )
        },
    )
    assert any(
        "--format" in violation
        for violation in _violations(checker.rule_17_management_commands, format_flag)
    )
    scheduled_alias = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_report.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--scheduled', action='store_true')\n"
            )
        },
    )
    assert any(
        "--scheduled" in violation
        for violation in _violations(checker.rule_17_management_commands, scheduled_alias)
    )
    bad_trigger = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_report.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--trigger', choices=['scheduled'], "
                "default='scheduled')\n"
            )
        },
    )
    violations = _violations(checker.rule_17_management_commands, bad_trigger)
    assert any("--trigger must offer" in violation for violation in violations)
    assert any("--trigger must default" in violation for violation in violations)
    purge_without_confirm = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_purge.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--dry-run', action='store_true')\n"
            )
        },
    )
    assert any(
        "--confirm" in violation
        for violation in _violations(checker.rule_17_management_commands, purge_without_confirm)
    )
    organization_flag = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_report.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--organization')\n"
            )
        },
    )
    assert any(
        "--organization; use --organization-id <uuid>" in violation
        for violation in _violations(checker.rule_17_management_commands, organization_flag)
    )
    org_flag = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_report.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--org')\n"
            )
        },
    )
    assert any(
        "--org; use --organization-id <uuid>" in violation
        for violation in _violations(checker.rule_17_management_commands, org_flag)
    )
    slug_selector = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_report.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--organization-slug')\n"
            )
        },
    )
    assert any(
        "--organization-slug; use --organization-id <uuid>" in violation
        for violation in _violations(checker.rule_17_management_commands, slug_selector)
    )
    slug_without_selector = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_purge.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def add_arguments(self, parser):\n"
                "        parser.add_argument('--slug')\n"
                "        parser.add_argument('--confirm')\n"
                "        parser.add_argument('--dry-run', action='store_true')\n"
            )
        },
    )
    assert any(
        "offers --slug without --organization-id" in violation
        for violation in _violations(checker.rule_17_management_commands, slug_without_selector)
    )
    conforming = _with_files(
        module,
        **{
            "management/commands/quickscale_demo_purge.py": (
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "from quickscale_core.runtime import require_scheduled_module_enabled\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
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
                "module_name='demo')\n"
            )
        },
    )
    assert _violations(checker.rule_17_management_commands, conforming) == []
