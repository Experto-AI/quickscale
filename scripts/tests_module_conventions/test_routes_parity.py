"""
Behavioral controls for the ``rules_routes`` split (SA267).

The route detectors' mechanics live in private siblings (``_routes_urls``,
``_routes_templates``, ``_routes_http_apis``, ``_routes_view_index``,
``_routes_authorization``, ``_routes_theme_seam``, ``_routes_throttles``)
behind the ``rules_routes`` facade.  SA267 has closed, so SA279 retired the
pre-split surface pins; these controls keep the split's structural invariants
and the exact ordered findings of representative corpora captured from the
pre-split module, so a later change cannot silently drop, reorder, or reword
them.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.check_module_conventions import Corpus
from scripts.module_conventions import (
    _routes_authorization,
    _routes_http_apis,
    _routes_templates,
    _routes_theme_seam,
    _routes_throttles,
    _routes_urls,
    _routes_view_index,
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


#: Rule 37's module-name exception tables stay defined in the facade: the
#: rule's allowlist exempts only ``rules_routes.py``.
RULE_37_TABLES = (
    "RULE_7_ALLOWED_TEMPLATE_MOUNTS",
    "OPERATOR_TOKENS",
    "TRAFFIC_FILTER_TOKENS",
)


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


def _rule19_public_read_corpus() -> Corpus:
    module = _golden_module()
    return _corpus(
        _with_files(
            module,
            views=(
                "from django.views.generic import TemplateView\n\n"
                "class DemoPublicReadMixin:\n"
                "    pass\n\n"
                "class PublicPageView(DemoPublicReadMixin, TemplateView):\n"
                "    pass\n"
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
    "rule19_public_read": _rule19_public_read_corpus,
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
        "rule19_public_read",
        "rule_19_authorization",
        (
            "rule 19: demo: views.py: public-read mixin DemoPublicReadMixin neither "
            "inherits PublicSystemOrgReadMixin nor declares PublicReadPresentationMixin",
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
