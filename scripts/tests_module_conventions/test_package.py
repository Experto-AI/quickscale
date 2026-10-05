"""Control cases for the package module-convention rules."""

from __future__ import annotations

import copy
from dataclasses import replace

from scripts import check_module_conventions as checker
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _violations,
    _with_files,
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
        **{"management/commands/quickscale_demo_run.py": "def handle():\n    print('x')\n"},
    )
    assert _violations(checker.rule_17_management_commands, broken)


def test_destructive_command_dry_run_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{"management/commands/quickscale_demo_purge.py": "def handle():\n    pass\n"},
    )
    assert any(
        "dry-run" in violation
        for violation in _violations(checker.rule_17_management_commands, broken)
    )


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
    declaration = (
        "from collections.abc import Mapping\n\n"
        "RETIRED_SETTINGS: Mapping[str, str] = {\n"
        '    "QUICKSCALE_DEMO_MODE": "Use QUICKSCALE_DEMO_ENABLED instead.",\n'
        '    "DEMO_POSTS_PER_PAGE": "Use QUICKSCALE_DEMO_POSTS_PER_PAGE instead.",\n'
        "}\n"
    )
    declared = _with_files(module, checks=declaration)
    assert _violations(checker.rule_6_no_legacy_names, declared) == []
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
