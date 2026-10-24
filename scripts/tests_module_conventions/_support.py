"""Shared golden fixtures and helpers for the module-conventions control cases."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

from scripts import check_module_conventions as checker
from scripts.check_module_conventions import Corpus, Module

REPO_ROOT = Path(__file__).resolve().parents[2]


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
            "backend": {
                "type": "string",
                "default": "local",
                "django_setting": "QUICKSCALE_DEMO_BACKEND",
                "description": "Demo backend selector.",
                "validation": {"choices": ["local", "remote"]},
            },
            "api_rate_limit": {
                "type": "string",
                "default": "5/hour",
                "django_setting": "QUICKSCALE_DEMO_API_RATE_LIMIT",
                "description": "Throttle rate.",
                "validation": {"pattern": r"^\d+/(second|minute|hour|day)$"},
            },
            "cdn_url": {
                "type": "string",
                "default": "/demo/",
                "django_setting": "QUICKSCALE_DEMO_CDN_URL",
                "description": "Relative-or-absolute demo URL.",
                "validation": {},
            },
            "marketing_host": {
                "type": "string",
                "default": "",
                "django_setting": "QUICKSCALE_DEMO_MARKETING_HOST",
                "description": "Optional absolute marketing host.",
                "validation": {"pattern": r"^(?:https?://[^\s]+)?$"},
            },
        },
        "immutable": {},
    },
    "dependencies": ["quickscale-core"],
    "required_modules": [],
    "derivation": {
        "wiring_projections": [
            {
                "wiring_field": "url_includes",
                "derivation_type": "static",
                "expression": {"value": [["demo/", "quickscale_modules_demo.urls"]]},
            },
        ],
        "option_derivations": {
            "cdn_url": {
                "normalization_rules": [
                    {
                        "source_key": "cdn_url",
                        "target_key": "cdn_url",
                        "rule_type": "path_or_absolute_url",
                        "description": "Canonical relative-or-absolute demo URL.",
                    },
                ],
            },
            "marketing_host": {
                "normalization_rules": [
                    {
                        "source_key": "marketing_host",
                        "target_key": "marketing_host",
                        "rule_type": "url",
                        "description": "Canonical absolute marketing host.",
                    },
                ],
            },
        },
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
- `backend` - demo backend selector.
- `api_rate_limit` - throttle rate.
- `cdn_url` - relative-or-absolute demo URL.
- `marketing_host` - optional absolute marketing host.

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
                "from django.core.management.base import BaseCommand\n"
                "\n"
                "\n"
                "class Command(BaseCommand):\n"
                "    def handle(self, *args, **options):\n"
                "        return None\n"
            ),
        },
        root_files={
            "pyproject.toml": (
                "[project]\n"
                "name = 'quickscale-module-demo'\n"
                "version = '0.0.0'\n"
                "description = 'Conformance-control module.'\n"
                "requires-python = '>=3.14,<3.15'\n"
                "readme = 'README.md'\n"
                "license = 'Apache-2.0'\n"
                "authors = [{name = 'Experto AI', email = 'victor@experto.ai'}]\n"
                "dynamic = ['dependencies']\n"
                "\n"
                "[tool.poetry]\n"
                "packages = [{include = 'quickscale_modules_demo', from = 'src'}]\n"
                "\n"
                "[tool.poetry.dependencies]\n"
                "python = '>=3.14,<3.15'\n"
                "Django = '>=6.0.8,<6.1.0'\n"
                "quickscale-core = {path = '../../quickscale_core', develop = true}\n"
                "\n"
                "[tool.poetry.group.dev.dependencies]\n"
                "pytest-django = '^4.11.1'\n"
                "\n"
                "[build-system]\n"
                "requires = ['poetry-core>=2.0,<3.0']\n"
                "build-backend = 'poetry.core.masonry.api'\n"
                "\n"
                "[tool.ruff]\n"
                "target-version = 'py314'\n"
                "\n"
                "[tool.ruff.lint]\n"
                "select = ['E4', 'E7', 'E9', 'F', 'S']\n"
                "\n"
                "[tool.ruff.lint.per-file-ignores]\n"
                "'tests/**' = ['S']\n"
                "\n"
                "[tool.pytest.ini_options]\n"
                "DJANGO_SETTINGS_MODULE = 'tests.settings'\n"
                "pythonpath = ['.', 'src', '../..']\n"
                "python_files = ['test_*.py']\n"
                "testpaths = ['tests']\n"
                "addopts = '-v --cov=quickscale_modules_demo --cov-report=html "
                "--cov-report=term-missing --cov-fail-under=90'\n"
                "markers = [\n"
                "    'bypass_rls: test requires BYPASSRLS database privilege (superuser / "
                "migration DDL). Deselected unless QUICKSCALE_ALLOW_BYPASSRLS is exactly 1.',\n"
                "    'e2e: End-to-end integration tests that exercise the full user workflow',\n"
                "    'isolation: cross-tenant isolation tests "
                "(roadmap Finding 14 / F11 rollout)',\n"
                "]\n"
                "\n"
                "[tool.coverage.report]\n"
                "fail_under = 90\n"
                "\n"
                "[tool.django-stubs]\n"
                "django_settings_module = 'tests.settings'\n"
            ).replace("demo", name),
            "README.md": GOLDEN_README.replace("demo", name),
            "poetry.toml": "[virtualenvs]\nin-project = true\n",
        },
        tests={
            "settings.py": (
                "SECRET_KEY = 'test'\n"
                "QUICKSCALE_DEMO_ENABLED = True\n"
                "QUICKSCALE_DEMO_BACKEND = 'local'\n"
                "QUICKSCALE_DEMO_API_RATE_LIMIT = '5/hour'\n"
                "QUICKSCALE_DEMO_CDN_URL = '/demo/'\n"
                "QUICKSCALE_DEMO_MARKETING_HOST = ''\n"
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


#: The capability vocabulary the synthetic corpora carry.  The rule 4
#: detectors parse it in place of a harness literal (SA296 (d)); a corpus that
#: needs a different vocabulary replaces ``core_conventions_text``, and the
#: live-tree control pins the parse against core's shipped declaration.
CORE_CONVENTIONS = """\
from enum import Enum
from types import MappingProxyType


class CapabilityShape(Enum):
    ITERABLE = "iterable"
    MAPPING = "mapping"
    STRING = "string"


CAPABILITIES: dict[str, CapabilityShape] = MappingProxyType(
    {
        "anonymize_handlers": CapabilityShape.ITERABLE,
        "removal_obligations": CapabilityShape.ITERABLE,
    }
)
"""


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
        core_conventions_text=CORE_CONVENTIONS,
    )


def _with_files(module: Module, **files: str) -> Module:
    """Replace package files; ``views=`` is shorthand for ``views.py``."""
    updated = dict(module.files)
    for key, value in files.items():
        if key not in updated and f"{key}.py" in updated:
            key = f"{key}.py"
        updated[key] = value
    return replace(module, files=updated)


def _with_pyproject(module: Module, text: str) -> Module:
    """Replace a module's pyproject.toml text."""
    return replace(module, root_files={**module.root_files, "pyproject.toml": text})


def _with_addopts(module: Module, addopts: str) -> Module:
    """Replace the golden pyproject's pytest addopts value."""
    pyproject = module.root_files["pyproject.toml"]
    head, marker, tail = pyproject.partition("addopts = '")
    assert marker, "golden fixture pyproject has no addopts"
    _, _, rest = tail.partition("'")
    return replace(
        module,
        root_files={
            **module.root_files,
            "pyproject.toml": f"{head}addopts = '{addopts}'{rest}",
        },
    )


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
