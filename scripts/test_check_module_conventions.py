"""
Control cases for the rule 40 module-conventions conformance check.

Each covered rule's detector is fed a synthetic violation and must report it,
proving the check fails on a violation.  The live repository must pass the
whole harness, and the covered rules plus the recorded open rules must be a
partition of rules 1-39 so no rule can be silently omitted.
"""

from __future__ import annotations

import copy
import re
from dataclasses import replace
from pathlib import Path

import pytest

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Corpus, Module

REPO_ROOT = Path(__file__).resolve().parents[1]

GOLDEN_MANIFEST: dict[str, object] = {
    "name": "demo",
    "config": {
        "mutable": {
            "enabled": {
                "type": "boolean",
                "default": True,
                "django_setting": "QUICKSCALE_DEMO_ENABLED",
                "description": "Enable the demo module.",
                "validation": {},
            },
            "api_rate_limit": {
                "type": "string",
                "default": "5/hour",
                "django_setting": "QUICKSCALE_DEMO_API_RATE_LIMIT",
                "description": "Throttle rate.",
                "validation": {"pattern": r"^\d+/(second|minute|hour|day)$"},
            },
        },
        "immutable": {},
    },
    "dependencies": [],
    "required_modules": [],
    "derivation": {
        "wiring_projections": [
            {
                "wiring_field": "url_includes",
                "derivation_type": "static",
                "expression": {"value": [["demo/", "quickscale_modules_demo.urls"]]},
            },
        ],
    },
}

GOLDEN_APPS = """\
from django.apps import AppConfig

from quickscale_core.runtime import register_module_checks


class QuickscaleDemoConfig(AppConfig):
    name = "quickscale_modules_demo"
    label = "quickscale_demo"

    def ready(self) -> None:
        from quickscale_modules_demo.checks import check_demo

        register_module_checks(self, [check_demo])
"""

GOLDEN_README = """\
# demo

## Overview
A demo module.

## Configuration
- `enabled` - enable the demo module.
- `api_rate_limit` - throttle rate.

## Public surface
Nothing.

## URLs
`demo/`.

## Management commands
- `quickscale_demo_run`.

## Operations
None.

## Extending
None.
"""


def _golden_module(name: str = "demo") -> Module:
    """Build one module that satisfies every covered detector."""
    stem = f"quickscale_{name}"
    manifest = {**GOLDEN_MANIFEST, "name": name}
    return Module(
        name=name,
        manifest=manifest,
        files={
            "__init__.py": (
                '"""Demo module."""\n\n__version__ = "0.0.0"\n\n__all__ = ["__version__"]\n'
            ),
            "py.typed": "",
            "apps.py": GOLDEN_APPS.replace("demo", name),
            "adapter.py": "def build(spec):\n    return spec.url_includes\n",
            "checks.py": "def check_demo() -> list[str]:\n    return []\n",
            "exceptions.py": "class DemoError(Exception):\n    pass\n",
            "models.py": (
                "from django.db import models\n"
                "from quickscale_modules_orgs.models import TenantModel\n\n\n"
                "class Widget(TenantModel):\n"
                "    class Meta(TenantModel.Meta):\n"
                "        ordering = ['pk']\n"
                "        indexes = [\n"
                "            models.Index(fields=['name'], name='qs_demo_widget_name_idx'),\n"
                "        ]\n"
                "        constraints = [\n"
                "            models.UniqueConstraint(\n"
                "                fields=['slug'], name='quickscale_demo_widget_slug_unique'\n"
                "            ),\n"
                "        ]\n\n"
                "    def __str__(self) -> str:\n"
                "        return 'widget'\n"
            ),
            "services.py": (
                '"""Demo service surface."""\n\n'
                '__all__ = ["demo_query", "is_enabled"]\n\n\n'
                "def demo_query(*, subject: str) -> str:\n"
                "    return subject\n\n\n"
                "def is_enabled() -> bool:\n"
                "    return True\n"
            ),
            "urls.py": (
                '"""Demo URLs."""\n\nfrom django.urls import path\n\n'
                "from . import views\n\n"
                f'app_name = "{stem}"\n\n'
                "urlpatterns = [path('', views.IndexView.as_view(), name='index')]\n"
            ),
            "views.py": "class IndexView:\n    pass\n",
            "templates/quickscale_demo/base.html": (
                '{% extends "base.html" %}\n{% block content %}{% block demo_content %}'
                "{% endblock %}{% endblock %}\n"
            ),
            "templates/quickscale_demo/page.html": (
                '{% extends "quickscale_demo/base.html" %}\n'
                "{% block demo_content %}{% endblock %}\n"
            ),
            "management/commands/quickscale_demo_run.py": (
                "class Command:\n    def handle(self, *args, **options):\n        return None\n"
            ),
        },
        root_files={
            "pyproject.toml": (
                "[project]\nname = 'quickscale-module-demo'\n"
                "[tool.pytest.ini_options]\naddopts = ''\n[tool.ruff]\n"
            ),
            "README.md": GOLDEN_README.replace("demo", name),
            "poetry.toml": "[virtualenvs]\nin-project = true\n",
        },
        tests={
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED = True\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
            "test_apps.py": (
                '"""App configuration behaviour."""\n\n\ndef test_config():\n    assert True\n'
            ),
            "test_migrations.py": (
                '"""Migration contract."""\n\n\ndef test_migration():\n    assert True\n'
            ),
            "test_services.py": (
                '"""Service surface behaviour."""\n\n\ndef test_service():\n    assert True\n'
            ),
            "test_isolation.py": (
                '"""Tenant isolation behaviour."""\n\n\ndef test_isolation():\n    assert True\n'
            ),
            "test_rls_boundary.py": (
                '"""RLS boundary behaviour."""\n\n\ndef test_boundary():\n    assert True\n'
            ),
            "test_widget.py": '"""Widget behaviour."""\n\n\ndef test_widget():\n    assert True\n',
        },
    )


def _corpus(*modules: Module, extra_dirs: tuple[str, ...] = ()) -> Corpus:
    names = tuple(module.name for module in modules) + extra_dirs
    mypy_ini = "\n".join(
        f"[mypy-quickscale_modules_{module.name}.*]\n"
        "disallow_untyped_defs = False\n"
        "warn_return_any = False\n"
        "warn_unused_ignores = False\n"
        for module in modules
    )
    return Corpus(
        modules=tuple(modules),
        module_dir_names=names,
        core_files={},
        cli_files={},
        script_files={},
        mypy_ini=mypy_ini,
    )


def _with_files(module: Module, **files: str) -> Module:
    """Replace package files; ``views=`` is shorthand for ``views.py``."""
    updated = dict(module.files)
    for key, value in files.items():
        if key not in updated and f"{key}.py" in updated:
            key = f"{key}.py"
        updated[key] = value
    return replace(module, files=updated)


def _violations(detector, *modules: Module, extra_dirs: tuple[str, ...] = ()) -> list[str]:
    return detector(_corpus(*modules, extra_dirs=extra_dirs))


def _with_option(module: Module, key: str, option: dict[str, object]) -> Module:
    """Replace one mutable manifest option on a copy of the module."""
    manifest = copy.deepcopy(module.manifest)
    manifest["config"]["mutable"][key] = option
    return replace(module, manifest=manifest)


def _without_option(module: Module, key: str) -> Module:
    manifest = copy.deepcopy(module.manifest)
    del manifest["config"]["mutable"][key]
    return replace(module, manifest=manifest)


def _with_mount(module: Module, mount: str) -> Module:
    """Declare ``mount`` as the module's URL include in its manifest."""
    manifest = copy.deepcopy(module.manifest)
    for projection in manifest["derivation"]["wiring_projections"]:
        if projection.get("wiring_field") == "url_includes":
            projection["expression"]["value"] = [[mount, f"quickscale_modules_{module.name}.urls"]]
    return replace(module, manifest=manifest)


def _seam_corpus(template: str, module: Module | None = None) -> Corpus:
    """Build a corpus whose theme seam template is the given ``index.html.j2``."""
    return replace(
        _corpus(module if module is not None else _golden_module()),
        core_files={checker.THEME_SEAM_TEMPLATE: template},
    )


def test_golden_fixture_passes_every_covered_rule() -> None:
    module = _golden_module()
    corpus = _corpus(module)
    failed = {rule.number: rule.detector(corpus) for rule in checker.RULES if rule.detector(corpus)}
    assert failed == {}


def test_settings_names_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_1_settings_names, module) == []
    no_enabled = _without_option(module, "enabled")
    assert any(
        "declares no enabled option" in violation
        for violation in _violations(checker.rule_1_settings_names, no_enabled)
    )
    wrong_type = _with_option(
        module,
        "enabled",
        {
            "type": "string",
            "default": "yes",
            "django_setting": "QUICKSCALE_DEMO_ENABLED",
            "description": "Enable the demo module.",
            "validation": {},
        },
    )
    assert any(
        "enabled type" in violation
        for violation in _violations(checker.rule_1_settings_names, wrong_type)
    )
    wrong_name = _with_option(
        module,
        "enabled",
        {
            "type": "boolean",
            "default": True,
            "django_setting": "QUICKSCALE_DEMO_ON",
            "description": "Enable the demo module.",
            "validation": {},
        },
    )
    assert any(
        "enabled setting" in violation
        for violation in _violations(checker.rule_1_settings_names, wrong_name)
    )
    bad_suffix = _with_option(
        module,
        "api_rate_limit",
        {
            "type": "integer",
            "default": 5,
            "django_setting": "QUICKSCALE_DEMO_API_RATE_LIMIT",
            "description": "Throttle rate.",
            "validation": {},
        },
    )
    assert any(
        "expected string" in violation
        for violation in _violations(checker.rule_1_settings_names, bad_suffix)
    )
    bad_default = _with_option(
        module,
        "action_key_env_var",
        {
            "type": "string",
            "default": "not-a-name",
            "django_setting": "QUICKSCALE_DEMO_ACTION_KEY_ENV_VAR",
            "description": "Environment variable name.",
            "validation": {},
        },
    )
    assert any(
        "not an environment-variable name" in violation
        for violation in _violations(checker.rule_1_settings_names, bad_default)
    )


def test_settings_reads_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_3_settings_reads, module) == []
    undeclared = _with_files(
        module,
        services=("from django.conf import settings\n\nKEY = settings.QUICKSCALE_DEMO_MISSING\n"),
    )
    assert any(
        "reads undeclared" in violation
        for violation in _violations(checker.rule_3_settings_reads, undeclared)
    )
    cross_module = _with_files(
        module,
        services=(
            "from django.conf import settings\n\nKEY = settings.QUICKSCALE_BILLING_SECRET_KEY\n"
        ),
    )
    assert any(
        "reads billing's" in violation
        for violation in _violations(checker.rule_3_settings_reads, cross_module)
    )
    with_default = _with_files(
        module,
        services=(
            "from django.conf import settings\n\n"
            'KEY = getattr(settings, "QUICKSCALE_DEMO_ENABLED", True)\n'
        ),
    )
    assert any(
        "through getattr()" in violation
        for violation in _violations(checker.rule_3_settings_reads, with_default)
    )
    aliased_default = _with_files(
        module,
        services=(
            "from django.conf import settings as cfg\n\n"
            'KEY = getattr(cfg, "QUICKSCALE_DEMO_ENABLED", True)\n'
        ),
    )
    assert any(
        "through getattr()" in violation
        for violation in _violations(checker.rule_3_settings_reads, aliased_default)
    )
    qualified_default = _with_files(
        module,
        services=(
            "import django.conf as conf\n\n"
            'KEY = getattr(conf.settings, "QUICKSCALE_DEMO_ENABLED", True)\n'
        ),
    )
    assert any(
        "through getattr()" in violation
        for violation in _violations(checker.rule_3_settings_reads, qualified_default)
    )
    missing_setting = replace(
        module,
        tests={**module.tests, "settings.py": "SECRET_KEY = 'test'\n"},
    )
    assert any(
        "tests/settings.py does not define" in violation
        for violation in _violations(checker.rule_3_settings_reads, missing_setting)
    )
    commented_setting = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "# QUICKSCALE_DEMO_ENABLED = True\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert any(
        "tests/settings.py does not define QUICKSCALE_DEMO_ENABLED" in violation
        for violation in _violations(checker.rule_3_settings_reads, commented_setting)
    )
    annotation_only = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED: bool\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert any(
        "tests/settings.py does not define QUICKSCALE_DEMO_ENABLED" in violation
        for violation in _violations(checker.rule_3_settings_reads, annotation_only)
    )
    annotated_value = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED: bool = True\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert _violations(checker.rule_3_settings_reads, annotated_value) == []
    unpacked_setting = replace(
        module,
        tests={
            **module.tests,
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED, = (True,)\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
            ),
        },
    )
    assert _violations(checker.rule_3_settings_reads, unpacked_setting) == []


def test_identity_names_control() -> None:
    module = _golden_module()
    broken = _with_files(module, apps=module.files["apps.py"].replace("label", "labels"))
    assert _violations(checker.rule_2_identity_names, broken)
    assert _violations(checker.rule_2_identity_names, module) == []


def test_identity_accepts_single_quoted_literals() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"]
        .replace('"quickscale_modules_demo"', "'quickscale_modules_demo'")
        .replace('"quickscale_demo"', "'quickscale_demo'"),
        urls=module.files["urls.py"].replace('"quickscale_demo"', "'quickscale_demo'"),
    )
    assert _violations(checker.rule_2_identity_names, broken) == []


def test_url_route_name_control() -> None:
    module = _golden_module()
    broken = _with_files(module, urls=module.files["urls.py"].replace("'index'", "'demo_list'"))
    violations = _violations(checker.rule_7_urls, broken)
    assert any("repeats the module" in violation for violation in violations)
    assert _violations(checker.rule_7_urls, module) == []


def test_url_mount_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    manifest["derivation"] = {"wiring_projections": []}
    assert _violations(checker.rule_7_urls, replace(module, manifest=manifest))


def test_url_include_literal_control() -> None:
    module = _golden_module()
    broken_keyword = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    return Wiring(url_includes=[['demo/', 'quickscale_modules_demo.urls']])\n"
        ),
    )
    assert any(
        "literal url_includes" in violation
        for violation in _violations(checker.rule_7_urls, broken_keyword)
    )
    broken_assignment = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    url_includes = [['demo/', 'quickscale_modules_demo.urls']]\n"
            "    return url_includes\n"
        ),
    )
    assert any(
        "literal url_includes" in violation
        for violation in _violations(checker.rule_7_urls, broken_assignment)
    )
    broken_annotated = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    url_includes: list = [['demo/', 'quickscale_modules_demo.urls']]\n"
            "    return url_includes\n"
        ),
    )
    assert any(
        "literal url_includes" in violation
        for violation in _violations(checker.rule_7_urls, broken_annotated)
    )
    empty_literals = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    url_includes = ()\n"
            "    if not url_includes:\n"
            "        return Wiring(url_includes=[])\n"
            "    return url_includes\n"
        ),
    )
    assert _violations(checker.rule_7_urls, empty_literals) == []
    annotated_empty = _with_files(
        module,
        adapter=("def build():\n    url_includes: list = []\n    return url_includes\n"),
    )
    assert _violations(checker.rule_7_urls, annotated_empty) == []


def test_template_page_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{"templates/quickscale_demo/page.html": "<html><body>page</body></html>\n"},
    )
    violations = _violations(checker.rule_8_templates, broken)
    assert any("does not extend" in violation for violation in violations)
    assert any("emits <html>" in violation for violation in violations)
    assert _violations(checker.rule_8_templates, module) == []


def test_json_api_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.http import JsonResponse\n\n\ndef index():\n    return JsonResponse({})\n"
        ),
    )
    assert _violations(checker.rule_9_http_apis, broken)


def test_error_body_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views='def index():\n    return {"error": {"code": "x", "message": "y"}}\n',
    )
    assert _violations(checker.rule_9_http_apis, broken)


def test_check_registration_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace("register_module_checks(self, [check_demo])", "pass"),
    )
    assert _violations(checker.rule_10_checks_errors, broken)


def test_error_base_control() -> None:
    module = _golden_module()
    broken = _with_files(module, exceptions="class DemoProblem(Exception):\n    pass\n")
    assert _violations(checker.rule_10_checks_errors, broken)


def test_ready_raise_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "register_module_checks(self, [check_demo])",
            "raise RuntimeError('boom')",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, broken)


def test_manifest_schema_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    config = {
        "mutable": {
            "api_rate_limit": {
                "type": "string",
                "default": "5/hour",
                "django_setting": "QUICKSCALE_DEMO_API_RATE_LIMIT",
                "description": "Throttle rate.",
                "validation": {"regex": "nope"},
            },
        },
        "immutable": {},
    }
    manifest["config"] = config
    assert _violations(checker.rule_12_manifest_options, replace(module, manifest=manifest))


def test_manifest_missing_description_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    option = dict(manifest["config"]["mutable"]["api_rate_limit"])  # type: ignore[index]
    option.pop("description")
    manifest["config"] = {
        "mutable": {"api_rate_limit": option},
        "immutable": {},
    }
    assert _violations(checker.rule_12_manifest_options, replace(module, manifest=manifest))


def test_tenant_meta_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        models=(
            "from quickscale_modules_orgs.models import TenantModel\n\n\n"
            "class Widget(TenantModel):\n"
            "    class Meta:\n"
            "        ordering = ['pk']\n\n"
            "    def __str__(self) -> str:\n"
            "        return 'widget'\n"
        ),
    )
    assert _violations(checker.rule_13_tenant_models, broken)


def test_model_str_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        models=(
            "from quickscale_modules_orgs.models import TenantModel\n\n\n"
            "class Widget(TenantModel):\n"
            "    class Meta(TenantModel.Meta):\n"
            "        ordering = ['pk']\n"
        ),
    )
    assert any(
        "__str__" in violation for violation in _violations(checker.rule_14_model_basics, broken)
    )


def test_literal_choices_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        models=(
            "from quickscale_modules_orgs.models import TenantModel\n\n"
            "WIDGET_CHOICES = ['a', 'b']\n\n\n"
            "class Widget(TenantModel):\n"
            "    class Meta(TenantModel.Meta):\n"
            "        ordering = ['pk']\n\n"
            "    def __str__(self) -> str:\n"
            "        return 'widget'\n"
        ),
    )
    assert any(
        "choice" in violation for violation in _violations(checker.rule_14_model_basics, broken)
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


def test_email_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.core.mail import send_mail\n\n\n"
            "def index():\n    send_mail('a', 'b', 'c', ['d'])\n"
        ),
    )
    assert _violations(checker.rule_20_email, broken)


def test_email_requirement_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="from quickscale_modules_notifications.services import send_notification\n",
    )
    assert any(
        "requiring notifications" in violation
        for violation in _violations(checker.rule_20_email, broken)
    )


def test_analytics_helper_control() -> None:
    analytics = Module(
        name="analytics",
        manifest={
            "name": "analytics",
            "config": {"mutable": {}, "immutable": {}},
            "dependencies": [],
        },
        files={
            "services.py": (
                "def capture_event(**kwargs):\n    return None\n\n"
                "def capture_pageview(**kwargs):\n    return None\n\n"
                "__all__ = ['capture_event', 'capture_pageview']\n"
            ),
        },
        root_files={},
        tests={},
    )
    assert _violations(checker.rule_22_analytics_events, analytics)


def test_analytics_event_name_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from quickscale_modules_analytics.services import capture_event\n\n"
            "def index():\n    capture_event(distinct_id='x', event='form_submit')\n"
        ),
    )
    violations = _violations(checker.rule_22_analytics_events, broken)
    assert any("stem" in violation for violation in violations)


def test_py_typed_control() -> None:
    module = _golden_module()
    broken = replace(
        module, files={key: value for key, value in module.files.items() if key != "py.typed"}
    )
    assert any(
        "py.typed" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_now_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="import datetime\n\n\ndef index():\n    return datetime.datetime.now()\n",
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_timezone_alias_is_not_datetime_now() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as datetime_clock\n\n\n"
            "def index():\n    return datetime_clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_alias_controls() -> None:
    module = _golden_module()
    django_alias = _with_files(
        module,
        views=(
            "from django.utils import timezone as datetime\n\n\n"
            "def index():\n    return datetime.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, django_alias) == []
    stdlib_alias = _with_files(
        module,
        views="from datetime import datetime as dt\n\n\ndef index():\n    return dt.now()\n",
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, stdlib_alias)
    )
    module_alias = _with_files(
        module,
        views="import datetime as clock\n\n\ndef index():\n    return clock.datetime.now()\n",
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, module_alias)
    )


def test_datetime_scope_local_alias_does_not_mask_module_import() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime\n\n\n"
            "def index():\n"
            "    return datetime.now()\n\n\n"
            "def other():\n"
            "    from django.utils import timezone as datetime\n"
            "    return datetime.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def _webhook_module(services: str) -> Module:
    module = _golden_module()
    return _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{"services.py": services},
    )


def test_webhook_with_statement_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        with nullcontext():\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_false_else_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        if False:\n"
        "            pass\n"
        "        else:\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_true_pass_guard_still_verifies() -> None:
    good = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        if True:\n"
        "            pass\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, good) == []


def test_webhook_return_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_swallowed_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    except ValueError:\n"
        "        pass\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_loop_else_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        for _ in []:\n"
        "            pass\n"
        "        else:\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_finally_return_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        try:\n"
        "            pass\n"
        "        finally:\n"
        "            return body\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_true_return_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if True:\n"
        "        return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_handler_raise_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    except ValueError:\n"
        "        if False:\n"
        "            raise\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_with_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def handle(*, body, signature):\n"
        "    with nullcontext():\n"
        "        return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_finally_override_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    finally:\n"
        "        return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_optional_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature == 'expected':\n"
        "        if not hmac.compare_digest(signature, 'expected'):\n"
        "            raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_conditional_return_before_guard_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature != 'expected':\n"
        "        return body\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_conditional_return_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature != 'expected':\n"
        "        return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_short_circuit_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n\n\n"
        "def handle(*, body, signature):\n"
        "    return body or _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_ignored_sentinel_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        return False\n"
        "    return True\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_datetime_import_order_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n"
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n"
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_registration_after_return_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        return\n        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_dead_branch_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if False:\n            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_after_terminal_branch_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if True:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_after_terminal_try_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        try:\n"
            "            return\n"
            "        finally:\n"
            "            pass\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_short_circuited_expression_control() -> None:
    module = _golden_module()
    dead = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if False and register_module_checks(self, [check_demo]):\n            pass\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead)
    )
    short_circuit = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        True or register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, short_circuit)
    )


def test_registration_with_static_boolop_test_control() -> None:
    module = _golden_module()
    dead = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if False and True:\n            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead)
    )
    terminal = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if True or False:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, terminal)
    )
    executed = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if True and True:\n            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, executed) == []


def test_registration_in_uncalled_lambda_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        unused = lambda: register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_later_handler_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        try:\n"
            "            raise ValueError('boom')\n"
            "        except TypeError:\n"
            "            pass\n"
            "        except ValueError:\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_after_break_bypasses_else_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            pass\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )
    nested_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            for inner in [1]:\n"
            "                break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, nested_break)
    )
    dead_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if False:\n"
            "                break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead_break)
    )
    try_star = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            except* Exception:\n"
            "                pass\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, try_star) == []
    unreachable_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, unreachable_break)
    )
    terminal_try = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                return\n"
            "            finally:\n"
            "                pass\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, terminal_try)
    )
    terminal_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            match 1:\n"
            "                case _:\n"
            "                    return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, terminal_match)
    )
    finally_override = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                return\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, finally_override)
    )


def test_registration_loop_termination_controls() -> None:
    module = _golden_module()
    nested_terminal_loop = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            for inner in []:\n"
            "                pass\n"
            "            else:\n"
            "                return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, nested_terminal_loop)
    )
    nested_terminal_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                match 1:\n"
            "                    case _:\n"
            "                        return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, nested_terminal_match)
    )
    continue_before_break = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            continue\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, continue_before_break)
    )
    finally_continue = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                continue\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, finally_continue)
    )
    caught_raise = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        for _ in [1]:\n"
            "            try:\n"
            "                raise ValueError('boom')\n"
            "            except ValueError:\n"
            "                pass\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, caught_raise) == []
    guarded_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        for _ in [1]:\n"
            "            match 1:\n"
            "                case _ if False:\n"
            "                    return\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, guarded_match) == []
    compound_continue = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                continue\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, compound_continue)
    )
    match_subject = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        match register_module_checks(self, [check_demo]):\n"
            "            case _:\n"
            "                pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, match_subject) == []
    match_guard = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        match 1:\n"
            "            case _ if register_module_checks(self, [check_demo]) is None:\n"
            "                pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, match_guard) == []
    conditional_finally = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        flag = False\n"
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                if flag:\n"
            "                    continue\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, conditional_finally) == []
    compound_continue_suffix = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                if flag:\n"
            "                    pass\n"
            "                continue\n"
            "            break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, compound_continue_suffix)
    )
    finally_suffix = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            try:\n"
            "                break\n"
            "            finally:\n"
            "                if flag:\n"
            "                    pass\n"
            "                continue\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, finally_suffix)
    )
    wrapped_continue_call = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            if True:\n"
            "                continue\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, wrapped_continue_call)
    )
    dead_match = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        for _ in [1]:\n"
            "            match 1:\n"
            "                case _ if False:\n"
            "                    break\n"
            "        else:\n"
            "            return\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, dead_match)
    )


def test_registration_after_return_inside_loop_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        while True:\n"
            "            return\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_conditional_expression_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        value = 1 if (register_module_checks(self, [check_demo]) or True) else 2\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_context_expression_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        with nullcontext(register_module_checks(self, [check_demo])):\n"
            "            pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_after_caught_raise_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n"
            "\n"
            "    def setup_checks(self) -> None:\n"
            "        try:\n"
            "            raise ValueError('boom')\n"
            "        except ValueError:\n"
            "            pass\n"
            "        register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_registration_in_evaluated_condition_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        if register_module_checks(self, [check_demo]):\n            pass\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_webhook_nested_sentinel_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        if True:\n"
        "            return False\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_registration_returned_call_is_credited() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        return register_module_checks(self, [check_demo])\n",
        ),
    )
    assert _violations(checker.rule_10_checks_errors, good) == []


def test_datetime_call_before_rebinding_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n\n\n"
            "from django.utils import timezone as clock\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_webhook_match_sentinel_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        match signature:\n"
        "            case _:\n"
        "                return False\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_early_sentinel_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if signature != 'expected':\n"
        "        return False\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_assert_only_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    assert hmac.compare_digest(signature, 'expected')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_datetime_deferred_function_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n\n\n"
            "from datetime import datetime as clock\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n\n\n"
            "from django.utils import timezone as clock\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_compound_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "if True:\n"
            "    from datetime import datetime as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    function_scope = _with_files(
        module,
        views=(
            "def index():\n"
            "    if True:\n"
            "        from datetime import datetime as clock\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, function_scope)
    )


def test_datetime_unreachable_compound_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "if False:\n"
            "    from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_compound_call_before_rebind_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "if True:\n"
            "    created = clock.now()\n"
            "    from django.utils import timezone as clock\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_nested_function_closure_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "def outer():\n"
            "    from datetime import datetime as clock\n\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    return inner()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "def outer():\n"
            "    from django.utils import timezone as clock\n\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    return inner()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_webhook_early_return_view_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return request.body\n"
            "        result = handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
            "        return Response({'status': 'accepted', 'duplicate': result.duplicate})\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_conditional_bypass_view_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        if request.headers.get('X-Signature'):\n"
            "            result = handle(\n"
            "                body=request.body,\n"
            "                signature=request.headers.get('X-Signature', ''),\n"
            "            )\n"
            "        return Response({'status': 'accepted'})\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_signature_unused_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(body, b'x'):\n"
        "        raise ValueError('bad body')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_datetime_while_false_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "while False:\n"
            "    from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_uncertain_branch_import_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n"
            "flag = False\n"
            "if flag:\n"
            "    from django.utils import timezone as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_uncertain_branch_stdlib_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n"
            "flag = True\n"
            "if flag:\n"
            "    from datetime import datetime as clock\n\n\n"
            "def index():\n"
            "    return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_webhook_conditional_accepting_return_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        if not request.headers.get('X-Signature'):\n"
            "            return request.body\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_constant_signature_propagation_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature='expected')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_signature_wrong_argument_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=signature, signature='expected')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unused_signature_parameter_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature, backup_signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature='expected', backup_signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_entry_alternate_parameter_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature, backup_signature='expected'):\n"
        "    if not hmac.compare_digest(backup_signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_overwritten_signature_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    signature = 'expected'\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_entry_overwrite_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    signature = 'expected'\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_compound_overwrite_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if True:\n"
        "        signature = 'expected'\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_compound_overwrite_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    with nullcontext():\n"
        "        signature = 'expected'\n"
        "    _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_nonconstant_overwrite_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature, flag=False):\n"
        "    if flag:\n"
        "        signature = 'expected'\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_datetime_class_while_false_positive() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    while False:\n"
            "        from datetime import datetime as clock\n\n"
            "    created = clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_webhook_short_circuit_return_view_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return request.body or handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_datetime_closure_after_definition_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "def outer():\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    from datetime import datetime as clock\n"
            "    return inner()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "def outer():\n"
            "    def inner():\n"
            "        return clock.now()\n\n"
            "    from django.utils import timezone as clock\n"
            "    return inner()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_webhook_with_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n"
        "from contextlib import nullcontext\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    with nullcontext():\n"
        "        return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_true_return_before_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    if True:\n"
        "        return body\n"
        "    _verify(body=body, signature=signature)\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_finally_helper_override_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    try:\n"
        "        _verify(body=body, signature=signature)\n"
        "    finally:\n"
        "        return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_optional_helper_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n\n\n"
        "def handle(*, body, signature):\n"
        "    if signature == 'expected':\n"
        "        _verify(body=body, signature=signature)\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_returned_helper_is_credited() -> None:
    good = _webhook_module(
        "import hmac\n\n\n"
        "def _verify(*, body, signature):\n"
        "    if not hmac.compare_digest(signature, 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n\n\n"
        "def handle(*, body, signature):\n"
        "    return _verify(body=body, signature=signature)\n"
    )
    assert _violations(checker.rule_26_webhooks, good) == []


def test_datetime_class_body_call_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\nclass View:\n    created = clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_class_body_compound_call_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    if True:\n"
            "        created = clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_class_body_timezone_positive() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    created = clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_class_compound_method_scope() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    from django.utils import timezone as clock\n\n"
            "    if True:\n"
            "        def index(self):\n"
            "            return clock.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_class_compound_method_accepts_enclosing_timezone() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    from datetime import datetime as clock\n\n"
            "    if True:\n"
            "        def index(self):\n"
            "            return clock.now()\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_method_default_uses_class_scope() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.utils import timezone as clock\n\n\n"
            "class View:\n"
            "    from datetime import datetime as clock\n\n"
            "    def index(self, now=clock.now()):\n"
            "        return now\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_method_default_accepts_class_timezone() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from datetime import datetime as clock\n\n\n"
            "class View:\n"
            "    from django.utils import timezone as clock\n\n"
            "    def index(self, now=clock.now()):\n"
            "        return now\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_datetime_class_scope_does_not_leak_into_methods() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime\n\n\n"
            "class View:\n"
            "    from django.utils import timezone as datetime\n\n"
            "    def index(self):\n"
            "        return datetime.now()\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_default_argument_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from datetime import datetime\n\n\ndef index(now=datetime.now()):\n    return now\n"
        ),
    )
    assert any(
        "datetime.now" in violation
        for violation in _violations(checker.rule_24_small_conventions, broken)
    )


def test_datetime_default_argument_accepts_timezone() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        views=(
            "from django.utils import timezone\n\n\n"
            "def index(now=timezone.now()):\n"
            "    return now\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, good) == []


def test_cache_key_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "from django.core.cache import cache\n\n"
            "WIDGET_CACHE_KEY = 'widgets:all'\n\n"
            "def index():\n    cache.set('other:key', 1)\n"
        ),
    )
    assert _violations(checker.rule_24_small_conventions, broken)


def test_webhook_view_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "class IndexView:\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body)\n"
        ),
    )
    assert any(
        "throttle_classes" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_test_name_control() -> None:
    module = _golden_module()
    docstring = '"""SA999 widget behaviour."""\n\n\ndef test_widget():\n    pass\n'
    broken = replace(module, tests={**module.tests, "test_widget.py": docstring})
    assert _violations(checker.rule_29_test_names, broken)
    comment = "# SA999 legacy reason\ndef test_widget():\n    pass\n"
    commented = replace(module, tests={**module.tests, "test_widget.py": comment})
    assert _violations(checker.rule_29_test_names, commented)


def test_throttle_scope_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "throttles.py": ("class DemoThrottle:\n    scope = 'demo_api'\n    rate = '5/hour'\n"),
        },
    )
    violations = _violations(checker.rule_32_throttles, broken)
    assert any("scope" in violation for violation in violations)
    assert any("rate" in violation for violation in violations)


def test_shared_stem_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "def _lock_key(value):\n"
            "    return f'widget:lock:{value}'\n\n"
            "FUNC_NAME = 'widget_equality'\n"
        ),
    )
    violations = _violations(checker.rule_33_shared_stems, broken)
    assert any("advisory-lock key" in violation for violation in violations)
    assert any("database function" in violation for violation in violations)


def test_readme_content_control() -> None:
    module = _golden_module()
    broken = replace(
        module,
        root_files={
            **module.root_files,
            "README.md": module.root_files["README.md"].replace(
                "`api_rate_limit` - throttle rate.", ""
            ),
        },
    )
    assert any(
        "api_rate_limit" in violation
        for violation in _violations(checker.rule_38_readme_content, broken)
    )


def test_module_dependency_control() -> None:
    module = _golden_module()
    manifest = {**module.manifest, "required_modules": ["other>=1.0"]}
    assert _violations(checker.rule_39_module_dependencies, replace(module, manifest=manifest))


def test_module_directory_without_manifest_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_18_package_tooling, module, extra_dirs=("stray",))


def test_template_assets_checked_without_pages() -> None:
    module = _golden_module()
    stripped = replace(
        module,
        files={
            key: value for key, value in module.files.items() if not key.startswith("templates/")
        }
        | {"static/demo/css/a.css": "body {}\n"},
    )
    assert any("root" in violation for violation in _violations(checker.rule_8_templates, stripped))


def test_page_must_fill_module_content_block() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{"templates/quickscale_demo/page.html": '{% extends "quickscale_demo/base.html" %}\n'},
    )
    assert any(
        "demo_content" in violation for violation in _violations(checker.rule_8_templates, broken)
    )


def test_page_may_not_extend_project_base_directly() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        **{
            "templates/quickscale_demo/page.html": (
                '{% extends "base.html" %}\n{% block demo_content %}{% endblock %}\n'
            )
        },
    )
    assert any(
        "does not extend" in violation
        for violation in _violations(checker.rule_8_templates, broken)
    )


def test_webhook_requires_drf_base() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView:\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body)\n"
        ),
    )
    assert any(
        "not a DRF APIView" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_requires_service_call() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body)\n"
        ),
    )
    assert any(
        "services.py function" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_aliased_service_import_control() -> None:
    module = _golden_module()
    good = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle as verify\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return verify(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert _violations(checker.rule_26_webhooks, good) == []


def test_webhook_constant_signature_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body, signature='x')\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "request headers" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_ignored_verification_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    hmac.compare_digest(signature, 'expected')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_sdk_constant_signature_control() -> None:
    broken = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(body, 'fixed', 'secret')\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_sdk_incoming_signature_control() -> None:
    positional = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(body, signature, 'secret')\n"
    )
    assert _violations(checker.rule_26_webhooks, positional) == []
    keyword = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        payload=body, sig_header=signature, secret='secret'\n"
        "    )\n"
    )
    assert _violations(checker.rule_26_webhooks, keyword) == []
    wrapper = _webhook_module(
        "def handle(*, body, signature):\n"
        "    return client.construct_event(\n"
        "        body=body, signature=signature, webhook_secret='secret'\n"
        "    )\n"
    )
    assert _violations(checker.rule_26_webhooks, wrapper) == []


def test_webhook_sdk_wrong_signature_slot_control() -> None:
    broken = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(signature, 'fixed', 'secret')\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_sdk_conditional_signature_control() -> None:
    dead_branch = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        body, signature if False else 'fixed', 'secret'\n"
        "    )\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, dead_branch)
    )
    unknown = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature, flag):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        body, signature if flag else 'fixed', 'secret'\n"
        "    )\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, unknown)
    )
    selected = _webhook_module(
        "import stripe\n\n\n"
        "def handle(*, body, signature):\n"
        "    return stripe.Webhook.construct_event(\n"
        "        body, signature if True else 'fixed', 'secret'\n"
        "    )\n"
    )
    assert _violations(checker.rule_26_webhooks, selected) == []


def test_webhook_derived_signature_control() -> None:
    good = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    expected = 'expected'.encode('utf-8')\n"
        "    if not hmac.compare_digest((signature or '').encode('utf-8'), expected):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, good) == []
    masked = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature and 'expected', 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, masked)
    )
    masked_falsy = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature and '', ''):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, masked_falsy)
    )
    constant_prefix = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest('' and signature, ''):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, constant_prefix)
    )


def test_webhook_discarding_call_control() -> None:
    broken = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest((lambda ignored: 'expected')(signature), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )
    derived = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature.strip().encode('utf-8'), b'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, derived) == []
    constant = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(str('expected'), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, constant)
    )
    constructed = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(str(signature), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert _violations(checker.rule_26_webhooks, constructed) == []
    discarding_method = _webhook_module(
        "import hmac\n\n\n"
        "def handle(*, body, signature):\n"
        "    if not hmac.compare_digest(signature.join(['expected']), 'expected'):\n"
        "        raise ValueError('bad signature')\n"
        "    return body\n"
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, discarding_method)
    )


def test_webhook_self_comparison_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, signature):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_success_value_return_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        return body\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_inverted_guard_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if hmac.compare_digest(signature, 'expected'):\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_rejection_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        if False:\n"
                "            raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unsupported_polarity_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected') == False:\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_return_before_raise_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        return body\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unreachable_guard_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if False:\n"
                "        if not hmac.compare_digest(signature, 'expected'):\n"
                "            raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_inverted_assert_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    assert not hmac.compare_digest(signature, 'expected')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_nested_executed_return_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        if True:\n"
                "            return body\n"
                "        raise ValueError('bad signature')\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_function_view_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.webhook, name='vendor_webhook')",
        ),
        views="def webhook(request):\n    return request.body\n",
    )
    assert any(
        "APIView.as_view()" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_unsigned_service_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(body=request.body, signature='x')\n"
        ),
        **{"services.py": "def handle(*, body, signature):\n    return body\n"},
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_webhook_pass_body_verification_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        urls=module.files["urls.py"].replace(
            "path('', views.IndexView.as_view(), name='index')",
            "path('webhooks/vendor/', views.IndexView.as_view(), name='vendor_webhook')",
        ),
        views=(
            "from rest_framework.views import APIView\n"
            "from quickscale_modules_demo.services import handle\n\n\n"
            "class IndexView(APIView):\n"
            "    authentication_classes = []\n"
            "    permission_classes = []\n"
            "    throttle_classes = []\n\n"
            "    def post(self, request):\n"
            "        return handle(\n"
            "            body=request.body,\n"
            "            signature=request.headers.get('X-Signature', ''),\n"
            "        )\n"
        ),
        **{
            "services.py": (
                "import hmac\n\n\n"
                "def handle(*, body, signature):\n"
                "    if not hmac.compare_digest(signature, 'expected'):\n"
                "        pass\n"
                "    return body\n"
            )
        },
    )
    assert any(
        "does not verify a signature" in violation
        for violation in _violations(checker.rule_26_webhooks, broken)
    )


def test_registration_in_unrelated_class_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        pass\n",
        )
        + (
            "\n\nclass OtherConfig:\n"
            "    def ready(self) -> None:\n"
            "        register_module_checks(self, [check_demo])\n"
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_in_uncalled_nested_function_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        def unused() -> None:\n"
            "            register_module_checks(self, [check_demo])\n",
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_class_method_shadowed_by_module_helper_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        self.setup_checks()\n\n    def setup_checks(self) -> None:\n        pass\n",
        )
        + "\n\ndef setup_checks() -> None:\n    register_module_checks(None, [])\n",
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_module_helper_shadowed_by_class_method_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        setup_checks()\n\n"
            "    def setup_checks(self) -> None:\n"
            "        register_module_checks(self, [check_demo])\n",
        )
        + "\n\ndef setup_checks() -> None:\n    pass\n",
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_registration_outside_ready_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "def ready(self) -> None:", "def unused(self) -> None:"
        ),
    )
    assert any(
        "registers nothing" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_swallowed_registration_in_except_star_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        try:\n"
            "            register_module_checks(self, [check_demo])\n"
            "        except* Exception:\n"
            "            pass\n",
        ),
    )
    assert any(
        "catches a registration failure" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_swallowed_registration_failure_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        apps=module.files["apps.py"].replace(
            "        register_module_checks(self, [check_demo])\n",
            "        try:\n"
            "            register_module_checks(self, [check_demo])\n"
            "        except Exception:\n"
            "            pass\n",
        ),
    )
    assert any(
        "catches a registration failure" in violation
        for violation in _violations(checker.rule_10_checks_errors, broken)
    )


def test_ticket_filename_control() -> None:
    module = _golden_module()
    broken = replace(
        module,
        tests={
            "settings.py": module.tests["settings.py"],
            "test_SA999_widget.py": '"""Widget."""\n',
        },
    )
    assert any(
        "ticket id" in violation for violation in _violations(checker.rule_29_test_names, broken)
    )


def test_keyword_event_constant_control() -> None:
    module = _golden_module()
    services = 'DEMO_CREATED_EVENT: Final[str] = "quickscale_demo_created"\n'
    views = (
        "from quickscale_modules_demo.services import DEMO_CREATED_EVENT\n"
        "from quickscale_modules_analytics.services import capture_event\n\n"
        "def index():\n"
        "    capture_event(distinct_id='x', event=DEMO_CREATED_EVENT)\n"
    )
    good = _with_files(module, **{"services.py": services, "views.py": views})
    assert _violations(checker.rule_22_analytics_events, good) == []
    bad = _with_files(
        module,
        **{
            "services.py": services.replace("quickscale_demo_created", "created"),
            "views.py": views,
        },
    )
    assert any(
        "stem" in violation for violation in _violations(checker.rule_22_analytics_events, bad)
    )


def test_immutable_django_setting_control() -> None:
    module = _golden_module()
    manifest = dict(module.manifest)
    manifest["config"] = {
        "mutable": {},
        "immutable": {
            "mode": {
                "type": "string",
                "default": "solo",
                "description": "Mode.",
                "django_setting": "QUICKSCALE_DEMO_MODE",
            }
        },
    }
    assert any(
        "immutable" in violation
        for violation in _violations(
            checker.rule_12_manifest_options, replace(module, manifest=manifest)
        )
    )


def test_package_root_requires_declarations() -> None:
    module = _golden_module()
    broken = _with_files(module, **{"__init__.py": '"""Demo."""\n'})
    violations = _violations(checker.rule_15_package_root, broken)
    assert any("__version__" in violation for violation in violations)
    assert any("__all__" in violation for violation in violations)


def test_documentation_only_mentions_are_not_violations() -> None:
    module = _golden_module()
    documented = _with_files(
        module,
        views=(
            '"""Use DRF rather than JsonResponse, timezone.now() rather than '
            "datetime.now(), and never django.core.mail or send_mail here. "
            'Do not use gettext, RunSQL, or django.db.models.Index()."""\n'
        ),
    )
    assert _violations(checker.rule_9_http_apis, documented) == []
    assert _violations(checker.rule_14_model_basics, documented) == []
    assert _violations(checker.rule_20_email, documented) == []
    assert _violations(checker.rule_24_small_conventions, documented) == []
    assert _violations(checker.rule_32_throttles, documented) == []


def test_error_body_with_nonliteral_key_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views=(
            "def index():\n    return {key: 1, 'error': {'code': 'invalid', 'message': 'bad'}}\n"
        ),
    )
    assert any(
        "error body" in violation for violation in _violations(checker.rule_9_http_apis, broken)
    )


def test_malformed_nested_config_shape_is_a_violation() -> None:
    module = _golden_module()
    broken = replace(module, manifest={**module.manifest, "config": [1]})
    assert _violations(checker.rule_12_manifest_options, broken)
    # A non-mapping config is skipped, never a traceback.
    assert _violations(checker.rule_38_readme_content, broken) == []


def test_email_dependency_shape_control() -> None:
    module = _golden_module()
    broken = _with_files(
        module,
        views="from quickscale_modules_notifications.services import send_notification\n",
    )
    broken = replace(broken, manifest={**broken.manifest, "required_modules": 1})
    assert any(
        "requiring notifications" in violation
        for violation in _violations(checker.rule_20_email, broken)
    )
    assert any(
        "must be a list" in violation
        for violation in _violations(checker.rule_39_module_dependencies, broken)
    )


def test_malformed_tool_shape_is_a_violation() -> None:
    module = _golden_module()
    broken = replace(
        module,
        root_files={**module.root_files, "pyproject.toml": "tool = 1\n"},
    )
    assert any(
        "pytest" in violation for violation in _violations(checker.rule_18_package_tooling, broken)
    )


def test_malformed_tree_returns_violations_not_tracebacks(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module_dir = tmp_path / "quickscale_modules" / "demo"
    package = module_dir / "src" / "quickscale_modules_demo"
    package.mkdir(parents=True)
    (module_dir / "module.yml").write_text(
        "name: demo\nconfig:\n  mutable:\n    1:\n      type: string\nrequired_modules: 1\n",
        encoding="utf-8",
    )
    (module_dir / "README.md").write_text(GOLDEN_README, encoding="utf-8")
    (package / "__init__.py").write_text('"""Demo."""\n', encoding="utf-8")
    (package / "views.py").write_text(
        "from quickscale_modules_notifications.services import send_notification\n",
        encoding="utf-8",
    )
    assert checker.check_conventions(tmp_path)
    assert checker.main([str(tmp_path)]) == 1
    assert "VIOLATION:" in capsys.readouterr().out


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


def test_upward_import_control() -> None:
    auth = _golden_module("auth")
    broken = _with_files(auth, views="from quickscale_modules_blog.models import Post\n")
    assert any(
        "imports upward" in violation
        for violation in _violations(checker.rule_5_dependency_direction, broken)
    )
    assert _violations(checker.rule_5_dependency_direction, auth) == []


def test_same_layer_cycle_control() -> None:
    blog = _with_files(
        _golden_module("blog"), views="from quickscale_modules_crm.models import Contact\n"
    )
    crm = _with_files(
        _golden_module("crm"), views="from quickscale_modules_blog.models import Post\n"
    )
    assert any(
        "cycle" in violation
        for violation in _violations(checker.rule_5_dependency_direction, blog, crm)
    )


def test_core_module_setting_name_control() -> None:
    module = _golden_module()
    corpus = replace(
        _corpus(module),
        core_files={
            "runtime.py": (
                "from django.conf import settings\n\nMODE = settings.QUICKSCALE_ORGS_MODE\n"
            )
        },
    )
    assert any(
        "names module setting" in violation
        for violation in checker.rule_5_dependency_direction(corpus)
    )


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


def test_aliased_core_setting_read_control() -> None:
    module = _golden_module()
    corpus = replace(
        _corpus(module),
        core_files={
            "runtime.py": (
                "from django.conf import settings as cfg\n\nMODE = cfg.QUICKSCALE_ORGS_MODE\n"
            )
        },
    )
    assert any(
        "names module setting" in violation
        for violation in checker.rule_5_dependency_direction(corpus)
    )


def test_migration_model_import_is_not_an_upward_reference() -> None:
    orgs = _golden_module("orgs")
    excepted = _with_files(
        orgs,
        **{
            "migrations/0001_initial.py": (
                "from quickscale_modules_billing.models import Subscription\n"
            )
        },
    )
    assert _violations(checker.rule_5_dependency_direction, excepted) == []
    non_model = _with_files(
        orgs,
        **{
            "migrations/0001_initial.py": (
                "from quickscale_modules_billing.services import debit_user\n"
            )
        },
    )
    assert any(
        "imports upward" in violation
        for violation in _violations(checker.rule_5_dependency_direction, non_model)
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


def test_migration_mixed_import_control() -> None:
    orgs = _golden_module("orgs")
    mixed = _with_files(
        orgs,
        **{
            "migrations/0002_extra.py": (
                "from quickscale_modules_billing import models, services\n"
            )
        },
    )
    assert any(
        "imports upward" in violation
        for violation in _violations(checker.rule_5_dependency_direction, mixed)
    )
    models_only = _with_files(
        orgs,
        **{"migrations/0003_extra.py": "from quickscale_modules_billing import models\n"},
    )
    assert _violations(checker.rule_5_dependency_direction, models_only) == []


def test_theme_seam_control() -> None:
    good = "{{ seam_module_flags }}\n{{ seam_module_paths }}\n"
    assert checker.rule_31_theme_seam(_seam_corpus(good)) == []
    missing = _seam_corpus("{{ seam_module_flags }}\n")
    assert any("does not render" in violation for violation in checker.rule_31_theme_seam(missing))
    literal_line = _seam_corpus('{{ seam_module_flags }}\n"demo": true,\n{{ seam_module_paths }}\n')
    assert any(
        "names module 'demo' literally" in violation
        for violation in checker.rule_31_theme_seam(literal_line)
    )
    bare_key = _seam_corpus("{{ seam_module_flags }}\ndemo: true,\n{{ seam_module_paths }}\n")
    assert any("bare key" in violation for violation in checker.rule_31_theme_seam(bare_key))
    absolute_mount = _seam_corpus("{{ seam_module_flags }}\n{{ seam_module_paths }}\n'/demo/'")
    assert any(
        "names module 'demo' literally" in violation
        for violation in checker.rule_31_theme_seam(absolute_mount)
    )
    empty_core = _corpus(_golden_module())
    assert checker.rule_31_theme_seam(empty_core) == []
    missing_template = replace(empty_core, core_files={"other.py": "x\n"})
    assert any(
        "carries no theme index.html.j2" in violation
        for violation in checker.rule_31_theme_seam(missing_template)
    )
    auth = _with_mount(_golden_module("auth"), "accounts/")
    accounts_literal = _seam_corpus(
        '{{ seam_module_flags }}\n{{ seam_module_paths }}\n<a href="/accounts/">Accounts</a>\n',
        auth,
    )
    assert any(
        "mount 'accounts/'" in violation
        for violation in checker.rule_31_theme_seam(accounts_literal)
    )
    named_url = _seam_corpus(
        "{{ seam_module_flags }}\n{{ seam_module_paths }}\n{% url 'quickscale_auth:login' %}\n",
        auth,
    )
    assert checker.rule_31_theme_seam(named_url) == []


def test_secrets_control() -> None:
    module = _golden_module()
    assert _violations(checker.rule_35_secrets, module) == []
    getenv = _with_files(module, services='import os\n\nKEY = os.getenv("DEMO_KEY")\n')
    assert any(
        "uses os.getenv/os.environ" in violation
        for violation in _violations(checker.rule_35_secrets, getenv)
    )
    environ = _with_files(module, services='import os\n\nKEY = os.environ["DEMO_KEY"]\n')
    environ_violations = _violations(checker.rule_35_secrets, environ)
    assert len(environ_violations) == 1
    assert "uses os.getenv/os.environ" in environ_violations[0]
    aliased = _with_files(
        module,
        services='import os as operating_system\n\nKEY = operating_system.getenv("DEMO_KEY")\n',
    )
    assert any(
        "uses os.getenv/os.environ" in violation
        for violation in _violations(checker.rule_35_secrets, aliased)
    )
    orgs = _golden_module("orgs")
    boot_guard = _with_files(
        orgs,
        checks=('import os\n\nBYPASS = os.environ.get("QUICKSCALE_ALLOW_BYPASSRLS")\n'),
    )
    assert _violations(checker.rule_35_secrets, boot_guard) == []
    other_variable = _with_files(orgs, checks='import os\n\nKEY = os.environ.get("DEMO_KEY")\n')
    assert any(
        "uses os.getenv/os.environ" in violation
        for violation in _violations(checker.rule_35_secrets, other_variable)
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


def test_authorization_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_19_authorization, module) == []
    staff = _with_files(module, views="def index(request, user):\n    return user.is_staff\n")
    assert any(
        "is_staff" in violation for violation in _violations(checker.rule_19_authorization, staff)
    )
    flag = _with_files(
        module,
        views='def index(request, user):\n    return getattr(user, "is_superuser", False)\n',
    )
    assert any(
        "is_superuser" in violation
        for violation in _violations(checker.rule_19_authorization, flag)
    )
    admin = _with_files(
        module,
        views=(
            "from rest_framework.permissions import IsAdminUser\n\n"
            "class IndexView:\n    permission_classes = [IsAdminUser]\n"
        ),
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, admin)
    )
    aliased_admin = _with_files(
        module,
        views=(
            "from rest_framework.permissions import IsAdminUser as AdminOnly\n\n"
            "class IndexView:\n    permission_classes = [AdminOnly]\n"
        ),
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, aliased_admin)
    )
    aliased_login = _with_files(
        module,
        views=(
            "from django.contrib.auth.views import redirect_to_login as login_redirect\n\n"
            "def index(request):\n    return login_redirect(request.get_full_path())\n"
        ),
    )
    assert any(
        "redirect_to_login" in violation
        for violation in _violations(checker.rule_19_authorization, aliased_login)
    )
    login = _with_files(
        module,
        views=(
            "from django.contrib.auth.views import redirect_to_login\n\n"
            "def index(request):\n    return redirect_to_login(request.get_full_path())\n"
        ),
    )
    assert any(
        "redirect_to_login" in violation
        for violation in _violations(checker.rule_19_authorization, login)
    )
    private_sibling = _with_files(
        module,
        **{
            "_view_invitation.py": (
                "from django.contrib.auth.views import redirect_to_login\n\n"
                "def index(request):\n"
                "    return redirect_to_login(request.get_full_path())\n"
            )
        },
    )
    assert any(
        "redirect_to_login" in violation
        for violation in _violations(checker.rule_19_authorization, private_sibling)
    )
    operator = _with_files(
        _golden_module("orgs"),
        **{
            "_view_context.py": (
                'def index(request, user):\n    return getattr(user, "is_superuser", False)\n'
            )
        },
    )
    assert _violations(checker.rule_19_authorization, operator) == []
    suffix_sibling = _with_files(
        module,
        **{
            "_profile_views.py": (
                "from rest_framework.permissions import IsAdminUser\n\n"
                "class IndexView:\n    permission_classes = [IsAdminUser]\n"
            )
        },
    )
    assert any(
        "IsAdminUser" in violation
        for violation in _violations(checker.rule_19_authorization, suffix_sibling)
    )
    documented = _with_files(
        module,
        views='"""Views never use is_staff or redirect_to_login, by rule 19."""\n',
    )
    assert _violations(checker.rule_19_authorization, documented) == []


def test_name_reference_controls() -> None:
    orgs = _golden_module("orgs")
    assert _violations(checker.rule_34_name_references, orgs) == []
    upward = _with_files(
        orgs,
        services=(
            "from django.apps import apps\n\nPLAN = apps.get_model('quickscale_billing', 'Plan')\n"
        ),
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, upward)
    )
    namespace = _with_files(
        orgs,
        services=(
            "from django.urls import reverse\n\nURL = reverse('quickscale_billing:pricing')\n"
        ),
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, namespace)
    )
    label_prefix = _with_files(orgs, services="LABEL = 'quickscale_billing_'\n")
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, label_prefix)
    )
    lookalike = _with_files(orgs, services="LABEL = 'quickscale_billingx'\n")
    assert _violations(checker.rule_34_name_references, lookalike) == []
    downward = _with_files(
        _golden_module("blog"),
        **{
            "services.py": (
                "from django.apps import apps\n\n"
                'X = apps.is_installed("quickscale_modules_storage")\n'
            )
        },
    )
    assert _violations(checker.rule_34_name_references, downward) == []
    self_reference = _with_files(
        orgs,
        services=(
            "from importlib import import_module\n\n"
            "mod = import_module('quickscale_modules_orgs.checks')\n"
        ),
    )
    assert _violations(checker.rule_34_name_references, self_reference) == []
    migration = _with_files(
        orgs,
        **{
            "migrations/0002_extra.py": (
                "from django.apps import apps\n\n"
                "PLAN = apps.get_model('quickscale_billing', 'Plan')\n"
            )
        },
    )
    assert _violations(checker.rule_34_name_references, migration) == []
    service_migration = _with_files(
        orgs,
        **{
            "migrations/0003_extra.py": (
                "from importlib import import_module\n\n"
                "mod = import_module('quickscale_modules_billing.services')\n"
            )
        },
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, service_migration)
    )
    app_config_migration = _with_files(
        orgs,
        **{
            "migrations/0004_extra.py": (
                "from django.apps import apps\n\n"
                "config = apps.get_app_config('quickscale_billing')\n"
            )
        },
    )
    assert any(
        "references billing by name upward" in violation
        for violation in _violations(checker.rule_34_name_references, app_config_migration)
    )
    keyword_migration = _with_files(
        orgs,
        **{
            "migrations/0005_extra.py": (
                "from django.apps import apps\n\n"
                "PLAN = apps.get_model(app_label='quickscale_billing', model_name='Plan')\n"
            )
        },
    )
    assert _violations(checker.rule_34_name_references, keyword_migration) == []
    annotated_dependencies = _with_files(
        orgs,
        **{
            "migrations/0006_extra.py": (
                "dependencies: list[tuple[str, str]] = [('quickscale_billing', '0001_initial')]\n"
            )
        },
    )
    assert _violations(checker.rule_34_name_references, annotated_dependencies) == []
    notifications = _with_files(
        _golden_module("notifications"),
        services=(
            'from django.apps import apps\n\nX = apps.is_installed("quickscale_modules_orgs")\n'
        ),
    )
    orgs_reference = _with_files(
        orgs,
        services=(
            "from django.apps import apps\n\n"
            'X = apps.is_installed("quickscale_modules_notifications")\n'
        ),
    )
    assert any(
        "cycle" in violation
        for violation in _violations(checker.rule_34_name_references, orgs_reference, notifications)
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


def test_constraint_name_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_25_constraint_names, module) == []
    unnamed = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        indexes = [models.Index(fields=['name'])]\n"
        ),
    )
    assert any(
        "Index without a name" in violation
        for violation in _violations(checker.rule_25_constraint_names, unnamed)
    )
    bad_prefix = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        constraints = [\n"
            "            models.UniqueConstraint(fields=['slug'], name='widget_slug_unique')\n"
            "        ]\n"
        ),
    )
    assert any(
        "must start with quickscale_demo_" in violation
        for violation in _violations(checker.rule_25_constraint_names, bad_prefix)
    )
    together = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        unique_together = [('a', 'b')]\n"
        ),
    )
    assert any(
        "uses unique_together" in violation
        for violation in _violations(checker.rule_25_constraint_names, together)
    )
    abstract = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        abstract = True\n"
            "        indexes = [models.Index(fields=['name'])]\n"
        ),
    )
    assert _violations(checker.rule_25_constraint_names, abstract) == []
    abstract_constraint = _with_files(
        module,
        models=(
            "from django.db import models\n\n\n"
            "class Widget(models.Model):\n"
            "    class Meta:\n"
            "        abstract = True\n"
            "        constraints = [models.UniqueConstraint(fields=['slug'])]\n"
        ),
    )
    assert any(
        "UniqueConstraint without a name" in violation
        for violation in _violations(checker.rule_25_constraint_names, abstract_constraint)
    )


def test_package_file_name_controls() -> None:
    module = _golden_module()
    assert _violations(checker.rule_28_file_names, module) == []
    extra = _with_files(module, **{"utils.py": "def helper():\n    return None\n"})
    assert any(
        "utils.py is not an allowed package file name" in violation
        for violation in _violations(checker.rule_28_file_names, extra)
    )
    private = _with_files(module, **{"_utils.py": "def helper():\n    return None\n"})
    assert _violations(checker.rule_28_file_names, private) == []
    events = _with_files(module, **{"events.py": 'PAGEVIEW = "$pageview"\n'})
    assert any(
        "events.py is not an allowed package file name" in violation
        for violation in _violations(checker.rule_28_file_names, events)
    )
    markdownx = _with_files(_golden_module("blog"), **{"markdownx_urls.py": "urlpatterns = []\n"})
    assert _violations(checker.rule_28_file_names, markdownx) == []
    demo_markdownx = _with_files(module, **{"markdownx_urls.py": "urlpatterns = []\n"})
    assert any(
        "markdownx_urls.py is not an allowed package file name" in violation
        for violation in _violations(checker.rule_28_file_names, demo_markdownx)
    )


def test_typecheck_config_controls() -> None:
    module = _golden_module()
    corpus = _corpus(module)
    assert checker.rule_36_typecheck_config(corpus) == []
    missing = replace(corpus, mypy_ini="")
    assert any(
        "has no [mypy-quickscale_modules_demo.*] section" in violation
        for violation in checker.rule_36_typecheck_config(missing)
    )
    ignored = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "ignore_missing_imports = True\n"
        ),
    )
    assert any(
        "section key 'ignore_missing_imports' is not allowed" in violation
        for violation in checker.rule_36_typecheck_config(ignored)
    )
    extra_codes = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\ndisable_error_code = var-annotated, assignment\n"
        ),
    )
    assert any(
        "disables assignment" in violation
        for violation in checker.rule_36_typecheck_config(extra_codes)
    )
    allowed_code = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\ndisable_error_code = var-annotated\n",
    )
    assert checker.rule_36_typecheck_config(allowed_code) == []
    stricter = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\ndisallow_any_generics = True\n",
    )
    assert checker.rule_36_typecheck_config(stricter) == []
    relaxed = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nwarn_no_return = False\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(relaxed)
    )
    extra_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-quickscale_modules_demo.models]\n"
            "ignore_missing_imports = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-quickscale_modules_demo.models]" in violation
        for violation in checker.rule_36_typecheck_config(extra_section)
    )
    grouped_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-third_party.*,quickscale_modules_demo.models]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-third_party.*,quickscale_modules_demo.models]" in violation
        for violation in checker.rule_36_typecheck_config(grouped_section)
    )
    wildcard_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-*.models]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-*.models]" in violation
        for violation in checker.rule_36_typecheck_config(wildcard_section)
    )
    parent_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-quickscale_modules_demo.models.*]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-quickscale_modules_demo.models.*]" in violation
        for violation in checker.rule_36_typecheck_config(parent_section)
    )
    unrelated_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-third_party.*]\n"
            "ignore_missing_imports = True\n"
        ),
    )
    assert checker.rule_36_typecheck_config(unrelated_section) == []
    separator_section = replace(
        corpus,
        mypy_ini=(
            "[mypy-quickscale_modules_demo.*]\n"
            "disallow_untyped_defs = False\n"
            "[mypy-quickscale_modules_demo/models.*]\n"
            "ignore_errors = True\n"
        ),
    )
    assert any(
        "declares an extra section [mypy-quickscale_modules_demo/models.*]" in violation
        for violation in checker.rule_36_typecheck_config(separator_section)
    )
    aliased_relaxation = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nallow_untyped_calls = True\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(aliased_relaxation)
    )
    permitted_alias = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nallow_untyped_defs = True\n",
    )
    assert checker.rule_36_typecheck_config(permitted_alias) == []
    permitted_no_alias = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nno_warn_return_any = True\n",
    )
    assert checker.rule_36_typecheck_config(permitted_no_alias) == []
    redefinition_new = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nallow_redefinition_new = True\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(redefinition_new)
    )
    for option in (
        "implicit_optional = True",
        "allow_untyped_globals = True",
        "allow_redefinition_old = True",
        "strict_optional = False",
        "local_partial_types = False",
    ):
        relaxed_option = replace(
            corpus,
            mypy_ini=f"[mypy-quickscale_modules_demo.*]\n{option}\n",
        )
        assert any(
            "relaxes outside the allowed set" in violation
            for violation in checker.rule_36_typecheck_config(relaxed_option)
        ), option
    for option in (
        "implicit_optional = False",
        "allow_untyped_globals = False",
        "strict_optional = True",
    ):
        stricter_option = replace(
            corpus,
            mypy_ini=f"[mypy-quickscale_modules_demo.*]\n{option}\n",
        )
        assert checker.rule_36_typecheck_config(stricter_option) == [], option
    for option in (
        "implicit_optional = yes",
        "allow_untyped_globals = 1",
        "allow_redefinition_old = on",
        "strict_optional = no",
        "local_partial_types = off",
    ):
        spelled_option = replace(
            corpus,
            mypy_ini=f"[mypy-quickscale_modules_demo.*]\n{option}\n",
        )
        assert any(
            "relaxes outside the allowed set" in violation
            for violation in checker.rule_36_typecheck_config(spelled_option)
        ), option
    reexport = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nimplicit_reexport = False\n",
    )
    assert checker.rule_36_typecheck_config(reexport) == []
    ignore_errors = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nignore_errors = True\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(ignore_errors)
    )
    follow_imports = replace(
        corpus,
        mypy_ini="[mypy-quickscale_modules_demo.*]\nfollow_imports = skip\n",
    )
    assert any(
        "relaxes outside the allowed set" in violation
        for violation in checker.rule_36_typecheck_config(follow_imports)
    )
    per_module = replace(
        module,
        root_files={
            **module.root_files,
            "pyproject.toml": module.root_files["pyproject.toml"]
            + "\n[tool.mypy]\ndisallow_untyped_defs = false\n",
        },
    )
    assert any(
        "declares per-module [tool.mypy]" in violation
        for violation in checker.rule_36_typecheck_config(_corpus(per_module))
    )


def test_module_list_controls() -> None:
    corpus = _corpus(
        _golden_module("alpha"),
        _golden_module("beta"),
        _golden_module("gamma"),
    )
    assert checker.rule_37_module_lists(corpus) == []
    core_literal = replace(
        corpus,
        core_files={"contracts/registry.py": "REGISTRY = ('alpha', 'beta', 'gamma')\n"},
    )
    assert any(
        "literal REGISTRY lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(core_literal)
    )
    cli_literal = replace(
        corpus,
        cli_files={"commands/registry.py": "SETTINGS = {'alpha': 1, 'beta': 2, 'gamma': 3}\n"},
    )
    assert any(
        "literal SETTINGS lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(cli_literal)
    )
    script_literal = replace(
        corpus,
        script_files={"other.py": "NAMES = ['alpha', 'beta', 'gamma']\n"},
    )
    assert any(
        "literal NAMES lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(script_literal)
    )
    script_test = replace(
        corpus,
        script_files={"test_helper.py": "NAMES = ['alpha', 'beta', 'gamma']\n"},
    )
    assert checker.rule_37_module_lists(script_test) == []
    catalog = replace(
        corpus,
        core_files={"contracts/module_catalog.py": "MODULE_CATALOG = ('alpha', 'beta', 'gamma')\n"},
    )
    assert checker.rule_37_module_lists(catalog) == []
    harness = replace(
        corpus,
        script_files={
            "check_module_conventions.py": "MODULE_LAYERS = {'alpha': 1, 'beta': 2, 'gamma': 3}\n"
        },
    )
    assert checker.rule_37_module_lists(harness) == []
    registry = replace(
        corpus,
        cli_files={
            "commands/registry.py": (
                "ENTRIES = [\n"
                "    Entry(name='alpha'),\n"
                "    Entry(name='beta'),\n"
                "    Entry(name='gamma'),\n"
                "]\n"
            )
        },
    )
    assert any(
        "literal ENTRIES lists 3 module names" in violation
        for violation in checker.rule_37_module_lists(registry)
    )
    small_registry = replace(
        corpus,
        cli_files={"commands/small_registry.py": "MODULES = ['alpha', 'beta']\n"},
    )
    assert any(
        "literal MODULES lists 2 module names" in violation
        for violation in checker.rule_37_module_lists(small_registry)
    )
    singleton = replace(
        corpus,
        cli_files={"commands/singleton.py": "MODULES = ['alpha']\n"},
    )
    assert any(
        "literal MODULES lists 1 module name" in violation
        for violation in checker.rule_37_module_lists(singleton)
    )
    exclusion = replace(
        corpus,
        core_files={"generator/seam.py": "_NON_SEAM_MODULES = frozenset({'alpha'})\n"},
    )
    assert checker.rule_37_module_lists(exclusion) == []
    returned = replace(
        corpus,
        cli_files={"commands/returned.py": "def get_modules():\n    return ['alpha']\n"},
    )
    assert any(
        "literal return:get_modules lists 1 module name" in violation
        for violation in checker.rule_37_module_lists(returned)
    )
    presentation = replace(
        corpus,
        core_files={
            "apply/steps/env_sync.py": (
                "ENV_EXAMPLE_MODULE_SPECS = (\n"
                "    Spec(module='alpha'),\n"
                "    Spec(module='beta'),\n"
                "    Spec(module='gamma'),\n"
                ")\n"
            ),
            "generator/seam.py": (
                "_SEAM_MODULE_PATHS = (\n"
                "    ('alpha', '{% url one %}'),\n"
                "    ('beta', '{% url two %}'),\n"
                "    ('gamma', '{% url three %}'),\n"
                ")\n"
            ),
        },
    )
    assert checker.rule_37_module_lists(presentation) == []


def test_layer_table_mirrors_the_shipped_modules() -> None:
    corpus = checker.load_corpus(REPO_ROOT)
    assert {module.name for module in corpus.modules} == set(checker.MODULE_LAYERS)


def test_covered_and_open_rules_partition_1_to_39() -> None:
    covered = {rule.number for rule in checker.RULES}
    open_rules = {number for number, _ in checker.OPEN_RULES}
    assert covered | open_rules == set(range(1, 40))
    assert not covered & open_rules


def test_every_open_rule_names_its_closer() -> None:
    for number, closer in checker.OPEN_RULES:
        assert re.search(r"SA\d+", closer), f"rule {number} needs a closing ticket: {closer!r}"


def test_covered_rules_are_unique_and_numbered() -> None:
    numbers = [rule.number for rule in checker.RULES]
    assert numbers == sorted(numbers)
    assert len(numbers) == len(set(numbers))


def test_live_tree_passes_the_harness() -> None:
    assert checker.check_conventions(REPO_ROOT) == []


def test_missing_modules_root_is_authority_failure(tmp_path: Path) -> None:
    with pytest.raises(checker.AuthorityError):
        checker.load_corpus(tmp_path)


def test_malformed_manifest_is_authority_failure(tmp_path: Path) -> None:
    modules_root = tmp_path / "quickscale_modules"
    module_dir = modules_root / "demo"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yml").write_text("name: [unterminated\n", encoding="utf-8")
    with pytest.raises(checker.AuthorityError):
        checker.load_corpus(tmp_path)


def test_main_reports_authority_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    assert checker.main([str(tmp_path)]) == 2
    assert "ERROR:" in capsys.readouterr().err
