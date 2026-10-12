"""
Parity controls for the ``rules_routes`` split (SA267).

The route detectors' mechanics live in private siblings (``_routes_urls``,
``_routes_templates``, ``_routes_http_apis``, ``_routes_view_index``,
``_routes_authorization``, ``_routes_theme_seam``, ``_routes_throttles``)
behind the ``rules_routes`` facade.  These controls pin the facade's preserved
surface, the split's structural invariants, and the exact ordered findings of
representative corpora captured from the pre-split module, so a later slice
cannot silently drop, reorder, or reword them.
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
    _routes_authorization,
    _routes_http_apis,
    _routes_templates,
    _routes_theme_seam,
    _routes_throttles,
    _routes_urls,
    _routes_view_index,
    registry,
    rules_routes,
)
from scripts.module_conventions.rules_identity import RULE_37_ALLOWED_LITERAL_FILES
from scripts.tests_module_conventions._support import (
    _corpus,
    _golden_module,
    _seam_corpus,
    _with_files,
    _with_mount,
)

SPLIT_SIBLINGS = {
    "_routes_authorization": _routes_authorization,
    "_routes_http_apis": _routes_http_apis,
    "_routes_templates": _routes_templates,
    "_routes_theme_seam": _routes_theme_seam,
    "_routes_throttles": _routes_throttles,
    "_routes_urls": _routes_urls,
    "_routes_view_index": _routes_view_index,
}

#: Every module-level name the pre-split ``rules_routes`` published, from its
#: own ``def``/``class``/assignment statements.  The facade must keep exposing
#: all of them, private helpers included.
FROZEN_SURFACE = (
    "CORE_LIST_PAGINATION",
    "CORE_SESSION_AUTHENTICATION",
    "DJANGO_VIEW_MODULE_PREFIXES",
    "DRF_VIEW_MODULE_PREFIXES",
    "FORBIDDEN_VIEW_TOKENS",
    "GUARD_MIXIN_NAMES",
    "OPERATOR_TOKENS",
    "PUBLIC_READ_MIXIN_NAMES",
    "PUBLIC_READ_MIXIN_SUFFIX",
    "RATE_LITERAL",
    "ROLE_ENFORCING_BASE_NAMES",
    "RULE_7_ALLOWED_TEMPLATE_MOUNTS",
    "SEAM_LIBRARY_LOAD",
    "THEME_SEAM_TEMPLATE",
    "THEME_SEAM_TEMPLATES",
    "THEME_TS_ROOT",
    "THEME_TS_TEST_MARKER",
    "TRAFFIC_FILTER_TOKENS",
    "VIEW_MODULE_PREFIXES",
    "WIRING_LITERAL_FIELDS",
    "_adapter_literal_wiring_violations",
    "_allow_any_hand_check_violations",
    "_base_name",
    "_base_view_target",
    "_class_declares_guard",
    "_declares_literal_wiring",
    "_declares_min_org_role",
    "_declares_page_size_setting",
    "_declares_permission_classes",
    "_defines_view_class",
    "_defines_view_code",
    "_dotted_name",
    "_effective_methods",
    "_effective_permission_names",
    "_get_permissions_binding",
    "_inherits_role_enforcement",
    "_is_admin_model_override",
    "_is_sanctioned_guard_name",
    "_is_view_base",
    "_is_view_module",
    "_module_helper_index",
    "_pagination_bindings",
    "_pagination_violations",
    "_paginator_classifications",
    "_permission_expression_name",
    "_reads_user_is_authenticated",
    "_rendered_managed_json_violations",
    "_resolves_to_core_list_pagination",
    "_resolves_to_core_session_authentication",
    "_resolves_to_drf_page_number_pagination",
    "_resolves_to_drf_session_authentication",
    "_route_name_violations",
    "_session_authentication_bindings",
    "_session_authentication_violations",
    "_sibling_paginator_imports",
    "_sibling_rel",
    "_takes_request",
    "_template_mount_literal_violations",
    "_theme_api_literal_violations",
    "_throttle_registration_violations",
    "_url_prefix_collision_violations",
    "_view_bindings",
    "_view_class_index",
    "_view_framework",
    "_view_token",
    "_webhook_view_names",
    "rule_19_authorization",
    "rule_31_theme_seam",
    "rule_32_throttles",
    "rule_7_urls",
    "rule_8_templates",
    "rule_9_http_apis",
)

#: The pre-split signature of every callable the registry, the entry point, or
#: the control cases invoke.
FROZEN_SIGNATURES = {
    "rule_7_urls": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_8_templates": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_9_http_apis": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_19_authorization": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_31_theme_seam": "(corpus: 'Corpus') -> 'list[str]'",
    "rule_32_throttles": "(corpus: 'Corpus') -> 'list[str]'",
    "_url_prefix_collision_violations": "(corpus: 'Corpus') -> 'list[str]'",
}

#: Rule 37's module-name exception tables stay defined in the facade: the
#: rule's allowlist exempts only ``rules_routes.py``.
RULE_37_TABLES = (
    "RULE_7_ALLOWED_TEMPLATE_MOUNTS",
    "OPERATOR_TOKENS",
    "TRAFFIC_FILTER_TOKENS",
)

FROZEN_RULE_7_MOUNTS = {
    ("generator/templates/templates/404.html.j2", "auth"): (
        "the 404 hint tests the requested path against the module's mount; it declares no route"
    ),
    ("generator/templates/templates/404.html.j2", "billing"): (
        "the 404 hint tests the requested path against the module's mount; it declares no route"
    ),
}

FROZEN_OPERATOR_KEYS = (
    ("forms", "views.py"),
    ("orgs", "_api_views.py"),
    ("orgs", "_debug.py"),
    ("orgs", "_view_context.py"),
    ("orgs", "_view_org_management.py"),
    ("orgs", "admin.py"),
    ("orgs", "debug_views.py"),
    ("orgs", "middleware.py"),
    ("orgs", "permissions.py"),
)

FROZEN_TRAFFIC_FILTERS = {("analytics", "services.py"): frozenset({"is_staff"})}


def _clean_corpus() -> Corpus:
    return _corpus(_golden_module())


def _rule7_corpus() -> Corpus:
    module = _golden_module()
    adapter_literal = _with_files(
        module,
        adapter=(
            "def build():\n"
            "    return Wiring(url_includes=[['demo/', 'quickscale_modules_demo.urls']])\n"
        ),
    )
    bad_name = _with_files(
        adapter_literal,
        urls=adapter_literal.files["urls.py"].replace("'index'", "'demo_list'"),
    )
    return replace(
        _corpus(
            bad_name,
            _with_mount(_golden_module("alpha"), "shared/"),
            _with_mount(_golden_module("beta"), "shared/"),
        ),
        core_files={
            "generator/templates/project_name/sample.j2": '<a href="/demo/">Demo</a>\n',
            "generator/templates/themes/showcase_react/src/hooks/useDemo.ts": (
                "export const base = '/demo/api/'\n"
            ),
        },
    )


def _rule8_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            **{
                "templates/quickscale_demo/reports/page.html": "<html><body>x</body></html>\n",
                "static/other/a.css": "body {}\n",
                "static/demo/notes/a.txt": "notes\n",
                "templatetags/reports.py": "x = 1\n",
                "admin.py": (
                    "class WidgetAdmin:\n"
                    "    change_list_template = 'quickscale_demo/admin/widget/change_list.html'\n"
                ),
            },
        )
    )


def _rule9_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            views=(
                "from django.http import JsonResponse\n"
                "from rest_framework.pagination import PageNumberPagination\n"
                "from rest_framework.views import APIView\n"
                "from quickscale_core.runtime import PlainListPagination\n\n\n"
                "class DemoPagination(PlainListPagination):\n"
                "    page_size = 25\n"
                "    page_size_setting = 'QUICKSCALE_DEMO_PER_PAGE'\n\n\n"
                "class DrfPagination(PageNumberPagination):\n"
                "    page_size_query_param = None\n\n\n"
                "class IndexView(APIView):\n"
                "    pagination_class = PageNumberPagination\n\n\n"
                "def index():\n"
                "    return JsonResponse({'error': {'code': 'x'}})\n"
            ),
        )
    )


def _rule19_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            views=(
                "from django.views.generic import TemplateView\n"
                "from rest_framework.permissions import AllowAny\n"
                "from rest_framework.views import APIView\n\n\n"
                "class PublicAPIView(APIView):\n"
                "    permission_classes = [AllowAny]\n\n"
                "    def get(self, request):\n"
                "        if not request.user.is_authenticated:\n"
                "            raise PermissionError\n"
                "        return None\n\n\n"
                "class MountPageView(TemplateView):\n"
                "    pass\n\n\n"
                "def index(request):\n"
                "    return request.user.is_staff\n"
            ),
        )
    )


_SEAM = (
    "{% load static quickscale_seam %}\n"
    "{% seam_module_flags %}\n"
    "{% seam_module_paths %}\n"
    "{% seam_module_api_paths %}\n"
)


def _rule31_corpus() -> Corpus:
    return _seam_corpus(_SEAM + "'/demo/'\nINSTALLED_APPS\n")


def _rule32_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            views=(
                "from rest_framework.views import APIView\n\n\n"
                "class DemoThrottle:\n"
                "    scope = 'demo_api'\n"
                "    rate = '5/hour'\n\n\n"
                "class IndexView(APIView):\n"
                "    throttle_classes = [DemoThrottle]\n\n"
                "    def get(self, request):\n"
                "        return None\n\n\n"
                "throttle_scope = 'demo_api'\n"
            ),
        )
    )


def _collision_corpus() -> Corpus:
    return _corpus(
        _with_mount(_golden_module("alpha"), "shared/"),
        _with_mount(_golden_module("beta"), "shared/"),
    )


CASE_BUILDERS = {
    "clean": _clean_corpus,
    "rule7": _rule7_corpus,
    "rule8": _rule8_corpus,
    "rule9": _rule9_corpus,
    "rule19": _rule19_corpus,
    "rule31": _rule31_corpus,
    "rule32": _rule32_corpus,
    "collision": _collision_corpus,
}

#: (case, detector, expected findings) captured from the pre-split module; the
#: list is exact, so order, wording, and duplicate findings are all pinned.
EXACT_FINDINGS = (
    ("clean", "rule_7_urls", ()),
    ("clean", "rule_8_templates", ()),
    ("clean", "rule_9_http_apis", ()),
    ("clean", "rule_19_authorization", ()),
    ("clean", "rule_31_theme_seam", ()),
    ("clean", "rule_32_throttles", ()),
    ("clean", "_url_prefix_collision_violations", ()),
    (
        "rule7",
        "rule_7_urls",
        (
            "rule 7: demo: adapter.py declares a literal url_includes",
            "rule 7: demo: route name 'demo_list' in path name repeats the module",
            "rule 7: core generator/templates/project_name/sample.j2: module 'demo' mount "
            "'demo/' is written as a literal",
            "rule 7: modules 'alpha' and 'beta' both mount URL prefix 'shared/' with "
            "different targets",
            "rule 7: core generator/templates/themes/showcase_react/src/hooks/useDemo.ts:1: "
            "module 'demo' API path '/demo/api' is written as a literal; the theme reads "
            "moduleApiPaths from the seam",
        ),
    ),
    (
        "rule8",
        "rule_8_templates",
        (
            "rule 8: demo: templates/quickscale_demo/reports/page.html is not flat under "
            "templates/quickscale_demo/",
            "rule 8: demo: templates/quickscale_demo/reports/page.html emits <html>",
            "rule 8: demo: templates/quickscale_demo/reports/page.html does not extend "
            "quickscale_demo/base.html",
            "rule 8: demo: templates/quickscale_demo/reports/page.html fills no demo_content block",
            "rule 8: demo: static path static/other/a.css lacks the quickscale_demo root",
            "rule 8: demo: static path static/demo/notes/a.txt lacks the quickscale_demo root",
            "rule 8: demo: template tag library 'reports' lacks the quickscale_demo stem",
            "rule 8: demo: admin.py admin override "
            "'quickscale_demo/admin/widget/change_list.html' is not under "
            "admin/<label>/<model>/",
        ),
    ),
    (
        "rule9",
        "rule_9_http_apis",
        (
            "rule 9: demo: views.py uses JsonResponse",
            "rule 9: demo: views.py defines a PageNumberPagination subclass DrfPagination "
            "outside core",
            "rule 9: demo: views.py sets a literal page_size",
            "rule 9: demo: views.py pagination_class must name a subclass of core's "
            "PlainListPagination",
            "rule 9: demo: views.py builds an error body in module code",
        ),
    ),
    (
        "rule19",
        "rule_19_authorization",
        (
            "rule 19: demo: views.py:20 uses is_staff outside the listed operator paths",
            "rule 19: demo: views.py: view class PublicAPIView declares AllowAny and reads "
            "request.user.is_authenticated by hand",
            "rule 19: demo: views.py: view class MountPageView declares no authorization guard",
        ),
    ),
    (
        "rule31",
        "rule_31_theme_seam",
        (
            "rule 31: generator/templates/themes/showcase_react/templates/index.html.j2 "
            "writes demo's mount 'demo/' literally",
            "rule 31: the theme's index.html.j2 names module 'demo' literally",
            "rule 31: the theme's index.html.j2 carries an INSTALLED_APPS test",
        ),
    ),
    (
        "rule32",
        "rule_32_throttles",
        (
            "rule 32: demo: views.py: IndexView declares throttle_classes; a throttle "
            "attaches through throttle_scope only",
            "rule 32: demo: DemoThrottle scope 'demo_api' lacks the quickscale_demo_ stem",
            "rule 32: demo: DemoThrottle hard-codes a rate",
            "rule 32: demo: views.py throttle scope 'demo_api' lacks the quickscale_demo_ stem",
            "rule 32: demo: views.py writes a throttle rate literal '5/hour'",
        ),
    ),
    (
        "collision",
        "_url_prefix_collision_violations",
        (
            "rule 7: modules 'alpha' and 'beta' both mount URL prefix 'shared/' with "
            "different targets",
        ),
    ),
)


def test_facade_publishes_the_pre_split_surface() -> None:
    """The facade's ``__all__`` is the pre-split module's own name set."""
    assert rules_routes.__all__ == FROZEN_SURFACE
    for name in FROZEN_SURFACE:
        assert getattr(rules_routes, name) is not None


def test_entrypoint_signatures_are_unchanged() -> None:
    """Each entrypoint keeps its pre-split signature, read at its definition."""
    assert {
        "rule_7_urls": str(inspect.signature(rules_routes.rule_7_urls)),
        "rule_8_templates": str(inspect.signature(_routes_templates.rule_8_templates)),
        "rule_9_http_apis": str(inspect.signature(_routes_http_apis.rule_9_http_apis)),
        "rule_19_authorization": str(inspect.signature(rules_routes.rule_19_authorization)),
        "rule_31_theme_seam": str(inspect.signature(_routes_theme_seam.rule_31_theme_seam)),
        "rule_32_throttles": str(inspect.signature(_routes_throttles.rule_32_throttles)),
        "_url_prefix_collision_violations": str(
            inspect.signature(_routes_urls._url_prefix_collision_violations)
        ),
    } == FROZEN_SIGNATURES


def test_rule_37_exception_tables_stay_defined_here() -> None:
    """Rule 37 exempts only ``rules_routes.py``, so its tables must live there."""
    tree = ast.parse(Path(rules_routes.__file__).read_text(encoding="utf-8"))
    assigned: set[str] = set()
    for node in tree.body:
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        assigned.update(target.id for target in targets if isinstance(target, ast.Name))
    assert set(RULE_37_TABLES) <= assigned
    assert rules_routes.RULE_7_ALLOWED_TEMPLATE_MOUNTS == FROZEN_RULE_7_MOUNTS
    assert tuple(sorted(rules_routes.OPERATOR_TOKENS)) == FROZEN_OPERATOR_KEYS
    assert rules_routes.TRAFFIC_FILTER_TOKENS == FROZEN_TRAFFIC_FILTERS


def test_rule_37_exempts_only_the_facade() -> None:
    """The split siblings stay inside rule 37's closed world, tables excluded."""
    assert ("scripts", "module_conventions/rules_routes.py") in RULE_37_ALLOWED_LITERAL_FILES
    for name in SPLIT_SIBLINGS:
        assert ("scripts", f"module_conventions/{name}.py") not in RULE_37_ALLOWED_LITERAL_FILES


def test_split_siblings_never_import_the_facade_or_registry() -> None:
    """Helpers reach their collaborators through siblings, never the facade."""
    for name, module in SPLIT_SIBLINGS.items():
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] not in {"rules_routes", "registry"}, (
                    name,
                    node.lineno,
                )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] not in {"rules_routes", "registry"}, (
                        name,
                        node.lineno,
                    )


def test_orchestrators_and_entrypoints_keep_their_homes() -> None:
    """Rule 7's and rule 19's ordered groups stay orchestrated by the facade."""
    assert rules_routes.rule_7_urls.__module__ == "scripts.module_conventions.rules_routes"
    assert (
        rules_routes._template_mount_literal_violations.__module__
        == "scripts.module_conventions.rules_routes"
    )
    assert rules_routes.rule_19_authorization.__module__ == (
        "scripts.module_conventions.rules_routes"
    )
    assert _routes_urls._url_prefix_collision_violations.__module__ == (
        "scripts.module_conventions._routes_urls"
    )
    assert _routes_templates.rule_8_templates.__module__ == (
        "scripts.module_conventions._routes_templates"
    )
    assert _routes_http_apis.rule_9_http_apis.__module__ == (
        "scripts.module_conventions._routes_http_apis"
    )
    assert _routes_theme_seam.rule_31_theme_seam.__module__ == (
        "scripts.module_conventions._routes_theme_seam"
    )
    assert _routes_throttles.rule_32_throttles.__module__ == (
        "scripts.module_conventions._routes_throttles"
    )
    assert _routes_authorization._guard_violations.__module__ == (
        "scripts.module_conventions._routes_authorization"
    )
    assert _routes_view_index._view_class_index.__module__ == (
        "scripts.module_conventions._routes_view_index"
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
    assert getattr(rules_routes, detector)(corpus) == list(expected)


def test_registry_and_entrypoint_read_the_facade() -> None:
    """The registry's detectors are the facade orchestration, not a sibling."""
    detectors = {rule.number: rule.detector for rule in registry.RULES}
    assert detectors[7] is rules_routes.rule_7_urls
    assert detectors[8] is rules_routes.rule_8_templates
    assert detectors[9] is rules_routes.rule_9_http_apis
    assert detectors[19] is rules_routes.rule_19_authorization
    assert detectors[31] is rules_routes.rule_31_theme_seam
    assert detectors[32] is rules_routes.rule_32_throttles
    assert checker.THEME_SEAM_TEMPLATE is rules_routes.THEME_SEAM_TEMPLATE
    assert checker.THEME_SEAM_TEMPLATES is rules_routes.THEME_SEAM_TEMPLATES
