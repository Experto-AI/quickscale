"""Contract tests for the managed URLconf runtime.

The user-owned ``<package>/urls.py`` holds one ``include()`` line; the
module-derived includes live in the managed ``<package>/urls_modules.py``
that ``apply`` regenerates; and the theme's shell route table plus the
composition order live in ``quickscale_core.runtime.urls``.  These tests pin
the runtime half: the composed order (rule 41), the orgs API exclusion, and
the Django-template module URL resolution that the generated context
processor delegates to.
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest
from django.conf import settings as django_settings
from django.http import HttpRequest, HttpResponse
from django.urls import clear_url_caches, include, path, re_path, set_urlconf

from quickscale_core.runtime.urls import (
    compose_managed_urlpatterns,
    installed_module_context,
)

_BILLING_ROOT = "qs_test_runtime_urls_billing_root"
_EMPTY_ROOT = "qs_test_runtime_urls_empty_root"


def _view(request: HttpRequest) -> HttpResponse:
    return HttpResponse("view")


@pytest.fixture(autouse=True)
def _configured_django() -> Iterator[None]:
    """Configure minimal Django settings and clear URLconf caches per test."""
    if not django_settings.configured:
        django_settings.configure(
            DEBUG=False,
            SECRET_KEY="quickscale-test-key",
            USE_I18N=False,
            USE_TZ=False,
            ROOT_URLCONF=__name__,
        )
    yield
    set_urlconf(None)
    clear_url_caches()
    for module_name in (_BILLING_ROOT, _EMPTY_ROOT):
        sys.modules.pop(module_name, None)


def _marker(pattern: Any) -> str:
    """Return a stable identifier for a composed URL pattern."""
    name = getattr(pattern, "name", None)
    if isinstance(name, str):
        return name
    route = getattr(getattr(pattern, "pattern", None), "_route", None)
    if isinstance(route, str):
        return route
    regex = getattr(getattr(pattern, "pattern", None), "regex", None)
    return getattr(regex, "pattern", repr(pattern))


def _compose() -> list[Any]:
    """Compose with stub includes so no module URLconf is imported."""
    pre_home = [
        path(
            "orgs/",
            include(([path("", _view, name="orgs_index")], "quickscale_modules_orgs")),
        )
    ]
    post_home = [
        path(
            "blog/",
            include(([path("", _view, name="blog_index")], "quickscale_modules_blog")),
        )
    ]
    return compose_managed_urlpatterns(
        pre_home=pre_home,
        post_home=post_home,
        spa=[re_path("^crm/?$", _view, name="quickscale_crm_shell")],
        react_shell_view=_view,
        orgs_shell_view=_view,
    )


def test_compose_managed_urlpatterns_orders_shell_pre_social_post_spa() -> None:
    """Rule 41: shell routes, pre-home, social, post-home, then SPA routes."""
    markers = [_marker(pattern) for pattern in _compose()]

    assert markers[0] == "home"
    assert "orgs/" in markers
    assert "social-link-tree" in markers
    assert "social-embeds" in markers
    assert "blog/" in markers
    assert "quickscale_crm_shell" in markers

    assert markers.index("home") < markers.index("orgs/")
    assert markers.index("orgs/") < markers.index("social-link-tree")
    assert markers.index("social-link-tree") < markers.index("social-embeds")
    assert markers.index("social-embeds") < markers.index("blog/")
    assert markers.index("blog/") < markers.index("quickscale_crm_shell")


def test_shell_routes_exclude_the_orgs_api_prefix() -> None:
    """The orgs shell regexes must let /orgs/api/... reach the module."""
    patterns = compose_managed_urlpatterns(
        pre_home=[],
        post_home=[],
        spa=[],
        react_shell_view=_view,
        orgs_shell_view=_view,
    )
    shell_regexes = [
        pattern.pattern.regex
        for pattern in patterns
        if _marker(pattern).startswith("^orgs")
    ]
    assert len(shell_regexes) >= 4

    api_paths = [
        "orgs/api/",
        "orgs/api/acme/",
        "orgs/api/acme/settings/",
        "orgs/api/blog/",
        "orgs/api/listings/",
        "orgs/api/members/",
    ]
    for api_path in api_paths:
        assert not any(regex.match(api_path) for regex in shell_regexes), api_path

    shell_paths = ["orgs/acme/", "orgs/acme/members/", "orgs/acme/settings/"]
    for shell_path in shell_paths:
        assert any(regex.match(shell_path) for regex in shell_regexes), shell_path


def _mount_billing_root() -> types.ModuleType:
    """Register a stub root URLconf mounting the billing namespace."""
    billing_patterns = [
        path("pricing/", _view, name="pricing_page"),
        path("dashboard/", _view, name="dashboard"),
    ]
    root = types.ModuleType(_BILLING_ROOT)
    root.urlpatterns = [  # type: ignore[attr-defined]
        path(
            "billing/",
            include(
                (billing_patterns, "quickscale_billing"),
                namespace="quickscale_billing",
            ),
        )
    ]
    sys.modules[_BILLING_ROOT] = root
    return root


def test_installed_module_context_resolves_billing_by_authentication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anonymous visitors get the pricing page; signed-in users the dashboard."""
    root = _mount_billing_root()
    monkeypatch.setattr(
        django_settings, "QUICKSCALE_BILLING_ENABLED", True, raising=False
    )
    anonymous: Any = types.SimpleNamespace(
        user=types.SimpleNamespace(is_authenticated=False)
    )
    authenticated: Any = types.SimpleNamespace(
        user=types.SimpleNamespace(is_authenticated=True)
    )

    set_urlconf(root)
    clear_url_caches()

    assert installed_module_context(anonymous) == {
        "billing": {"url": "/billing/pricing/"}
    }
    assert installed_module_context(authenticated) == {
        "billing": {"url": "/billing/dashboard/"}
    }


def test_installed_module_context_is_none_when_the_module_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A switched-off module yields a present key with a null URL."""
    root = _mount_billing_root()
    monkeypatch.setattr(
        django_settings, "QUICKSCALE_BILLING_ENABLED", False, raising=False
    )
    anonymous: Any = types.SimpleNamespace(
        user=types.SimpleNamespace(is_authenticated=False)
    )

    set_urlconf(root)
    clear_url_caches()

    assert installed_module_context(anonymous) == {"billing": {"url": None}}


def test_installed_module_context_is_none_without_the_namespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An absent module namespace yields a present key with a null URL."""
    root = types.ModuleType(_EMPTY_ROOT)
    root.urlpatterns = []  # type: ignore[attr-defined]
    sys.modules[_EMPTY_ROOT] = root
    monkeypatch.setattr(
        django_settings, "QUICKSCALE_BILLING_ENABLED", True, raising=False
    )
    anonymous: Any = types.SimpleNamespace(
        user=types.SimpleNamespace(is_authenticated=False)
    )

    set_urlconf(root)
    clear_url_caches()

    assert installed_module_context(anonymous) == {"billing": {"url": None}}
