"""SA235 acceptance: module root URL names resolve to their own views.

Rule 41 makes each module's React shell routes manifest-declared and renders
them after the module's own includes.  This test generates a React project,
renders the managed URL wiring with the module mounts and their declared
``spa_routes``, and proves two things against Django's resolver:

* every module root URL name (blog, listings) resolves to that
  module's own view;
* a module's declared React shell route (CRM) resolves to the shell where the
  module serves no route of its own.

The control case inserts the retired ``^blog/?$`` shell reservation ahead of
the module include and proves the acceptance check fails under it.

The generated ``urls.py`` is executed with a stubbed project package and its
``admin/`` route removed, so the test exercises the generated route order
without booting the admin app registry.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from pathlib import Path

import pytest
from django.conf import settings as django_settings
from django.http import HttpRequest, HttpResponse
from django.urls import (
    clear_url_caches,
    include,
    path,
    re_path,
    resolve,
    reverse,
    set_urlconf,
)

from quickscale_core.generator.generator import ProjectGenerator
from quickscale_core.module_wiring import ModuleWiringSpec, render_urls_modules_py

PROJECT_NAME = "spa_route_acceptance"

_MODULE_URLCONF_NAMES = (
    "qs_test_blog_urls",
    "qs_test_listings_urls",
    "qs_test_crm_urls",
)

_PACKAGE_MODULE_NAMES = (
    PROJECT_NAME,
    f"{PROJECT_NAME}.views",
    f"{PROJECT_NAME}.urls_modules",
)


def _blog_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("blog")


def _listings_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("listings")


def _crm_dashboard_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("crm")


def _shell_view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("shell")


def _legacy_blog_shell(request: HttpRequest) -> HttpResponse:
    return HttpResponse("legacy shell")


def _register_module_urlconfs() -> None:
    """Register importable stub module URLconfs with their app namespaces."""
    specs: dict[str, tuple[str, str, str, object]] = {
        "qs_test_blog_urls": ("quickscale_blog", "post_list", "", _blog_view),
        "qs_test_listings_urls": (
            "quickscale_listings",
            "listing_list",
            "",
            _listings_view,
        ),
        "qs_test_crm_urls": (
            "quickscale_crm",
            "dashboard",
            "dashboard/",
            _crm_dashboard_view,
        ),
    }
    for module_name, (app_name, route_name, route, view) in specs.items():
        module = types.ModuleType(module_name)
        module.urlpatterns = [path(route, view, name=route_name)]
        module.app_name = app_name
        sys.modules[module_name] = module


def _remove_module_urlconfs() -> None:
    for module_name in _MODULE_URLCONF_NAMES:
        sys.modules.pop(module_name, None)


def _remove_package_modules() -> None:
    for module_name in _PACKAGE_MODULE_NAMES + (f"{PROJECT_NAME}.urls",):
        sys.modules.pop(module_name, None)


@pytest.fixture()
def generated_urls(tmp_path: Path) -> Iterator[types.ModuleType]:
    """Generate a project, execute its route order, and return the urlconf."""
    if not django_settings.configured:
        django_settings.configure(
            DEBUG=False,
            SECRET_KEY="quickscale-test-key",
            USE_I18N=False,
            USE_TZ=False,
            ROOT_URLCONF=__name__,
        )

    generator = ProjectGenerator(theme="showcase_react")
    output_path = tmp_path / PROJECT_NAME
    generator.generate(PROJECT_NAME, output_path)

    specs = {
        "blog": ModuleWiringSpec(
            url_includes=(("blog/", "qs_test_blog_urls"),),
            spa_routes=(("^blog/?$", "shell"),),
        ),
        "listings": ModuleWiringSpec(
            url_includes=(("listings/", "qs_test_listings_urls"),),
            spa_routes=(("^listings/?$", "shell"),),
        ),
        "crm": ModuleWiringSpec(
            url_includes=(("crm/", "qs_test_crm_urls"),),
            spa_routes=(("^crm/?$", "shell"),),
        ),
    }
    rendered_wiring = render_urls_modules_py(specs)

    urls_source = (output_path / PROJECT_NAME / "urls.py").read_text()
    # Drop the admin route: it needs a booted app registry, and it is not part
    # of the module route-order contract under test.
    urls_source = urls_source.replace("from django.contrib import admin\n", "")
    urls_source = urls_source.replace('    path("admin/", admin.site.urls),\n', "")
    assert "admin" not in urls_source.replace("django.contrib.admin", "")

    _register_module_urlconfs()
    _remove_package_modules()
    package = types.ModuleType(PROJECT_NAME)
    package.__path__ = []  # type: ignore[attr-defined]
    views = types.ModuleType(f"{PROJECT_NAME}.views")
    views.react_shell_view = _shell_view
    views.orgs_react_shell_view = _shell_view
    views.custom_404_view = _shell_view
    views.custom_500_view = _shell_view
    urls_modules = types.ModuleType(f"{PROJECT_NAME}.urls_modules")
    urls = types.ModuleType(f"{PROJECT_NAME}.urls")
    for module in (package, views, urls_modules, urls):
        module.__package__ = PROJECT_NAME
        sys.modules[module.__name__] = module
    try:
        exec(compile(rendered_wiring, "<urls_modules>", "exec"), urls_modules.__dict__)
        exec(
            compile(urls_source, str(output_path / PROJECT_NAME / "urls.py"), "exec"),
            urls.__dict__,
        )
        yield urls
    finally:
        _remove_package_modules()
        _remove_module_urlconfs()
        set_urlconf(None)
        clear_url_caches()


def test_module_root_url_names_resolve_to_their_own_views(
    generated_urls: types.ModuleType,
) -> None:
    """Every module root URL name resolves to that module's own view (rule 41)."""
    set_urlconf(generated_urls)
    clear_url_caches()
    try:
        roots = {
            "quickscale_blog:post_list": ("/blog/", _blog_view),
            "quickscale_listings:listing_list": ("/listings/", _listings_view),
        }
        for url_name, (expected_path, expected_view) in roots.items():
            assert reverse(url_name) == expected_path
            resolved = resolve(expected_path)
            assert resolved.func is expected_view, (
                f"{url_name} resolved to {resolved.func!r} instead of the module view"
            )

        # CRM serves no root route, so its manifest-declared React shell route
        # covers /crm and /crm/.
        assert reverse("quickscale_crm_shell") == "/crm"
        assert resolve("/crm/").func is _shell_view
        assert resolve("/crm/dashboard/").func is _crm_dashboard_view
    finally:
        set_urlconf(None)
        clear_url_caches()


def test_generated_context_processor_billing_url_follows_routes_and_enabled(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The generated context processor reverses billing's routes and gates on enabled.

    Anonymous visitors get billing's pricing page and authenticated users its
    dashboard, in either deployment mode and at whatever prefix the project
    mounts.  Billing keeps its URL patterns mounted while switched off but
    answers as disabled (rule 1), so the projected enabled setting yields
    ``None``, as it does while billing is absent and no namespace resolves.
    """
    if not django_settings.configured:
        django_settings.configure(
            DEBUG=False,
            SECRET_KEY="quickscale-test-key",
            USE_I18N=False,
            USE_TZ=False,
            ROOT_URLCONF=__name__,
        )

    generator = ProjectGenerator(theme="showcase_react")
    project_name = "context_processor_billing"
    output_path = tmp_path / project_name
    generator.generate(project_name, output_path)
    source = (output_path / project_name / "context_processors.py").read_text()

    module = types.ModuleType("qs_test_context_processors")
    exec(compile(source, "<context_processors>", "exec"), module.__dict__)

    billing_patterns = [
        path("pricing/", _shell_view, name="pricing_page"),
        path("dashboard/", _shell_view, name="dashboard"),
    ]
    mounted_root = types.ModuleType("qs_test_billing_root")
    mounted_root.urlpatterns = [
        path(
            "billing/",
            include(
                (billing_patterns, "quickscale_billing"),
                namespace="quickscale_billing",
            ),
        )
    ]
    remounted_root = types.ModuleType("qs_test_remounted_billing_root")
    remounted_root.urlpatterns = [
        path(
            "payments/",
            include(
                (billing_patterns, "quickscale_billing"),
                namespace="quickscale_billing",
            ),
        )
    ]
    empty_root = types.ModuleType("qs_test_no_billing_root")
    empty_root.urlpatterns = []
    sys.modules[mounted_root.__name__] = mounted_root
    sys.modules[remounted_root.__name__] = remounted_root
    sys.modules[empty_root.__name__] = empty_root

    anonymous = types.SimpleNamespace(
        user=types.SimpleNamespace(is_authenticated=False)
    )
    authenticated = types.SimpleNamespace(
        user=types.SimpleNamespace(is_authenticated=True)
    )
    monkeypatch.setattr(
        django_settings, "QUICKSCALE_BILLING_ENABLED", True, raising=False
    )

    def billing_url(request: object) -> object:
        return module.installed_modules(request)["modules"]["billing"]["url"]

    try:
        set_urlconf(mounted_root)
        clear_url_caches()
        for mode in ("solo", "saas"):
            monkeypatch.setattr(
                django_settings, "QUICKSCALE_ORGS_MODE", mode, raising=False
            )
            assert billing_url(anonymous) == "/billing/pricing/"
            assert billing_url(authenticated) == "/billing/dashboard/"

        monkeypatch.setattr(
            django_settings, "QUICKSCALE_BILLING_ENABLED", False, raising=False
        )
        assert billing_url(anonymous) is None
        assert billing_url(authenticated) is None

        monkeypatch.setattr(
            django_settings, "QUICKSCALE_BILLING_ENABLED", True, raising=False
        )
        set_urlconf(remounted_root)
        clear_url_caches()
        assert billing_url(anonymous) == "/payments/pricing/"
        assert billing_url(authenticated) == "/payments/dashboard/"

        set_urlconf(empty_root)
        clear_url_caches()
        assert billing_url(anonymous) is None
        assert billing_url(authenticated) is None
    finally:
        sys.modules.pop(mounted_root.__name__, None)
        sys.modules.pop(remounted_root.__name__, None)
        sys.modules.pop(empty_root.__name__, None)
        set_urlconf(None)
        clear_url_caches()


def test_shifted_shell_control_fails_the_acceptance(
    generated_urls: types.ModuleType,
) -> None:
    """Control: the retired ``^blog/?$`` shell reservation shadows the index.

    The same acceptance probe run against a URLconf whose shell reservation
    precedes the module include resolves ``/blog/`` to the shell, proving the
    check is sensitive to the ordering rule 41 fixes.
    """
    control = types.ModuleType("spa_route_acceptance_control")
    control.urlpatterns = [
        re_path(r"^blog/?$", _legacy_blog_shell, name="legacy-blog-shell"),
        *generated_urls.urlpatterns,
    ]
    sys.modules[control.__name__] = control
    set_urlconf(control)
    clear_url_caches()
    try:
        assert resolve("/blog/").func is _legacy_blog_shell, (
            "the control reservation must shadow the module index"
        )
    finally:
        sys.modules.pop(control.__name__, None)
        set_urlconf(None)
        clear_url_caches()
