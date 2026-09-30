"""URL resolution tests for the rendered social managed URLconf.

The managed ``quickscale_managed/social_urls.py`` and the social adapter's
``urls_modules.py`` wiring are rendered into generated projects.  These tests
execute both rendered artifacts with stub payload views and prove the two
integration endpoints resolve and reverse at their public paths under the
mount declared by the module manifest.
"""

from __future__ import annotations

import sys
from types import ModuleType
from typing import Any

from django.http import HttpRequest, JsonResponse
from django.urls import include, path, resolve, reverse

from quickscale_core.manifest.social_manifest import render_social_managed_urls_module
from quickscale_core.module_wiring import render_urls_modules_py

from quickscale_modules_social.adapter import _social_manifest_adapter

MOUNT = "_quickscale/social/"
_PROJECT_PACKAGE = "testproject"
_IMPORT_LINE = (
    "from .social_views import social_embeds_payload, social_link_tree_payload"
)


def _stub_link_tree(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"surface": "link_tree"})


def _stub_embeds(request: HttpRequest) -> JsonResponse:
    return JsonResponse({"surface": "embeds"})


def _rendered_namespace() -> dict[str, Any]:
    """Execute the rendered managed URLconf with stub payload views."""
    content = render_social_managed_urls_module()
    assert _IMPORT_LINE in content, "managed URLconf import line changed"
    namespace: dict[str, Any] = {
        "social_link_tree_payload": _stub_link_tree,
        "social_embeds_payload": _stub_embeds,
    }
    exec(  # noqa: S102 - executing the generated artifact under test
        content.replace(_IMPORT_LINE, "# payload views provided by the namespace"),
        namespace,
    )
    return namespace


def _rendered_urlconf() -> ModuleType:
    """Mount the rendered managed URLconf at the manifest's mount."""
    namespace = _rendered_namespace()
    urlconf = ModuleType("rendered_social_urls")
    urlconf.urlpatterns = [  # type: ignore[attr-defined]
        path(MOUNT, include((namespace["urlpatterns"], namespace["app_name"])))
    ]
    return urlconf


def _install_managed_urlconf(namespace: dict[str, Any]) -> list[str]:
    """Register the rendered URLconf under its emitted import path.

    The emitted ``urls_modules.py`` includes
    ``{project_package}.quickscale_managed.social_urls`` by string; the test
    registers that dotted path so the emitted wiring resolves it.
    """
    names = [
        _PROJECT_PACKAGE,
        f"{_PROJECT_PACKAGE}.quickscale_managed",
        f"{_PROJECT_PACKAGE}.quickscale_managed.social_urls",
    ]
    project_module = ModuleType(names[0])
    project_module.__path__ = []  # type: ignore[attr-defined]
    managed_module = ModuleType(names[1])
    managed_module.__path__ = []  # type: ignore[attr-defined]
    urls_module = ModuleType(names[2])
    urls_module.urlpatterns = namespace["urlpatterns"]  # type: ignore[attr-defined]
    urls_module.app_name = namespace["app_name"]  # type: ignore[attr-defined]
    for name, module in zip(
        names, (project_module, managed_module, urls_module), strict=True
    ):
        sys.modules[name] = module
    return names


def test_managed_urls_resolve_the_payload_endpoints() -> None:
    """Both integration endpoints resolve at their public paths."""
    urlconf = _rendered_urlconf()

    link_tree = resolve("/_quickscale/social/", urlconf=urlconf)
    embeds = resolve("/_quickscale/social/embeds/", urlconf=urlconf)

    assert link_tree.func is _stub_link_tree
    assert link_tree.view_name == "quickscale_managed_social:link_tree"
    assert embeds.func is _stub_embeds
    assert embeds.view_name == "quickscale_managed_social:embeds"


def test_managed_urls_reverse_the_payload_endpoints() -> None:
    """Both integration endpoints reverse from their snake_case route names."""
    urlconf = _rendered_urlconf()

    assert reverse("quickscale_managed_social:link_tree", urlconf=urlconf) == (
        "/_quickscale/social/"
    )
    assert reverse("quickscale_managed_social:embeds", urlconf=urlconf) == (
        "/_quickscale/social/embeds/"
    )


def test_emitted_wiring_resolves_and_reverses_the_payload_endpoints() -> None:
    """Wiring rendered from the adapter spec reaches both managed endpoints."""
    spec = _social_manifest_adapter({}, project_package=_PROJECT_PACKAGE)
    emitted = render_urls_modules_py({"social": spec})
    installed = _install_managed_urlconf(_rendered_namespace())
    try:
        wiring: dict[str, Any] = {}
        exec(emitted, wiring)  # noqa: S102 - executing the generated artifact
        urlconf = ModuleType("emitted_social_urls_modules")
        urlconf.urlpatterns = wiring["POST_HOME_MODULE_URLPATTERNS"]  # type: ignore[attr-defined]

        assert resolve("/_quickscale/social/", urlconf=urlconf).view_name == (
            "quickscale_managed_social:link_tree"
        )
        assert resolve("/_quickscale/social/embeds/", urlconf=urlconf).view_name == (
            "quickscale_managed_social:embeds"
        )
        assert reverse("quickscale_managed_social:link_tree", urlconf=urlconf) == (
            "/_quickscale/social/"
        )
        assert reverse("quickscale_managed_social:embeds", urlconf=urlconf) == (
            "/_quickscale/social/embeds/"
        )
    finally:
        for name in installed:
            sys.modules.pop(name, None)
