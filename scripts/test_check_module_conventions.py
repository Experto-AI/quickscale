"""
Control cases for the rule 40 module-conventions conformance check.

Each covered rule's detector is fed a synthetic violation and must report it,
proving the check fails on a violation.  The live repository must pass the
whole harness, and the covered rules plus the recorded open rules must be a
partition of rules 1-39 so no rule can be silently omitted.
"""

from __future__ import annotations

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
                "        ordering = ['pk']\n\n"
                "    def __str__(self) -> str:\n"
                "        return 'widget'\n"
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
            "settings.py": "SECRET_KEY = 'test'\n",
            "test_widget.py": '"""Widget behaviour."""\n\n\ndef test_widget():\n    assert True\n',
        },
    )


def _corpus(*modules: Module, extra_dirs: tuple[str, ...] = ()) -> Corpus:
    names = tuple(module.name for module in modules) + extra_dirs
    return Corpus(
        modules=tuple(modules),
        module_dir_names=names,
        core_files={},
        cli_files={},
        mypy_ini="",
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


def test_golden_fixture_passes_every_covered_rule() -> None:
    module = _golden_module()
    corpus = _corpus(module)
    failed = {rule.number: rule.detector(corpus) for rule in checker.RULES if rule.detector(corpus)}
    assert failed == {}


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
