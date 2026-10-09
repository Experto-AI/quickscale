"""Contract tests for the React seam's runtime producer (SA258 slice a).

Module Conventions rule 31: the seam's module flags and paths resolve at
request time from the shipped inventory and the live settings, through the
``quickscale_seam`` template-tag library.  These tests hold the producer's
inventory, resolution, JS rendering, and tag wiring in place — including the
controls proving a switched-off or absent module resolves ``false`` and the
``home`` fallback.
"""

from __future__ import annotations

import types
from typing import Any

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.runtime.seam import (
    render_module_flags,
    render_module_paths,
    seam_module_flags,
    seam_module_paths,
    seam_modules,
    seam_path_names,
)


def _settings(**attributes: Any) -> types.SimpleNamespace:
    """Return a settings-like object with the given attributes."""
    return types.SimpleNamespace(**attributes)


class _RecordingReverse:
    """A URL reverser that records every route name it resolves."""

    def __init__(self, routes: dict[str, str]) -> None:
        self.routes = routes
        self.calls: list[str] = []

    def __call__(self, route: str) -> str:
        self.calls.append(route)
        return self.routes[route]


class TestSeamInventory:
    """The seam reports the shipped inventory, minus its documented exclusion."""

    def test_seam_modules_cover_the_catalog_minus_orgs(self) -> None:
        catalogue = {entry.name for entry in MODULE_CATALOG}
        seam_names = {module.name for module in seam_modules()}

        assert seam_names == catalogue - {"orgs"}

    def test_seam_module_shapes(self) -> None:
        modules = {module.name: module for module in seam_modules()}

        assert modules["auth"].app_label == "quickscale_modules_auth"
        assert modules["auth"].enabled_setting == "QUICKSCALE_AUTH_ENABLED"
        assert modules["notifications"].app_label == "quickscale_modules_notifications"
        assert modules["notifications"].enabled_setting == (
            "QUICKSCALE_NOTIFICATIONS_ENABLED"
        )

    def test_seam_path_names_are_the_theme_surfaces(self) -> None:
        assert seam_path_names() == ("crm", "social", "analytics")


class TestSeamResolution:
    """Flags and paths follow installed-and-enabled, with the home fallback."""

    def test_flags_require_installed_and_enabled(self) -> None:
        settings_obj = _settings(
            INSTALLED_APPS=["quickscale_modules_auth", "quickscale_modules_crm"],
            QUICKSCALE_AUTH_ENABLED=True,
            # Installed but switched off: the flag must be false.
            QUICKSCALE_CRM_ENABLED=False,
        )

        flags = seam_module_flags(settings_obj)

        assert flags["auth"] is True
        assert flags["crm"] is False
        # Absent from INSTALLED_APPS: the flag is false.
        assert flags["blog"] is False
        # orgs never carries a modules flag (owner.mode reports it instead).
        assert "orgs" not in flags

    def test_flag_false_when_enabled_setting_is_absent(self) -> None:
        settings_obj = _settings(INSTALLED_APPS=["quickscale_modules_storage"])

        flags = seam_module_flags(settings_obj)

        assert flags["storage"] is False

    def test_paths_reverse_enabled_routes(self) -> None:
        settings_obj = _settings(
            INSTALLED_APPS=[
                "quickscale_modules_crm",
                "quickscale_modules_social",
                "quickscale_modules_analytics",
            ],
            QUICKSCALE_CRM_ENABLED=True,
            QUICKSCALE_SOCIAL_ENABLED=True,
            QUICKSCALE_ANALYTICS_ENABLED=True,
            QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=True,
        )
        reverse = _RecordingReverse(
            {
                "quickscale_crm_shell": "/crm/",
                "social-link-tree": "/social",
                "quickscale_analytics:dashboard": "/analytics/",
                "home": "/",
            }
        )

        paths = seam_module_paths(settings_obj, reverse)

        assert paths == {
            "crm": "/crm/",
            "social": "/social",
            "analytics": "/analytics/",
        }
        assert reverse.calls == [
            "quickscale_crm_shell",
            "social-link-tree",
            "quickscale_analytics:dashboard",
        ]

    def test_disabled_and_absent_paths_fall_back_home(self) -> None:
        settings_obj = _settings(
            INSTALLED_APPS=["quickscale_modules_crm"],
            QUICKSCALE_CRM_ENABLED=False,
        )
        reverse = _RecordingReverse({"home": "/"})

        paths = seam_module_paths(settings_obj, reverse)

        assert paths == {"crm": "/", "social": "/", "analytics": "/"}
        assert reverse.calls == ["home", "home", "home"]

    def test_social_path_prefers_link_tree_then_embeds(self) -> None:
        routes = {
            "social-link-tree": "/social",
            "social-embeds": "/social/embeds",
            "home": "/",
        }
        base = {
            "INSTALLED_APPS": ["quickscale_modules_social"],
            "QUICKSCALE_SOCIAL_ENABLED": True,
        }

        link_tree = _settings(
            **base,
            QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=True,
            QUICKSCALE_SOCIAL_EMBEDS_ENABLED=True,
        )
        link_tree_reverse = _RecordingReverse(routes)
        assert seam_module_paths(link_tree, link_tree_reverse)["social"] == "/social"
        assert "social-link-tree" in link_tree_reverse.calls

        embeds = _settings(
            **base,
            QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=False,
            QUICKSCALE_SOCIAL_EMBEDS_ENABLED=True,
        )
        embeds_reverse = _RecordingReverse(routes)
        assert seam_module_paths(embeds, embeds_reverse)["social"] == "/social/embeds"
        assert "social-embeds" in embeds_reverse.calls

        neither = _settings(
            **base,
            QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=False,
            QUICKSCALE_SOCIAL_EMBEDS_ENABLED=False,
        )
        neither_reverse = _RecordingReverse(routes)
        # No feature enabled: the link tree stays the default route.
        assert seam_module_paths(neither, neither_reverse)["social"] == "/social"


class TestSeamRendering:
    """The rendered JS bodies keep the emitted template's exact shape."""

    def test_render_module_flags_omits_orgs_and_keeps_trailing_commas(self) -> None:
        rendered = render_module_flags({"auth": True, "backups": False})

        assert rendered == "          auth: true,\n          backups: false,"

    def test_render_module_paths_omits_only_the_last_comma(self) -> None:
        rendered = render_module_paths(
            {"crm": "/crm/", "social": "/social", "analytics": "/analytics/"}
        )

        assert rendered == (
            '          crm: "/crm/",\n'
            '          social: "/social",\n'
            '          analytics: "/analytics/"'
        )

    def test_renderers_accept_an_indent_override(self) -> None:
        assert render_module_flags({"auth": True}, indent="  ") == "  auth: true,"
        assert render_module_paths({"crm": "/crm/"}, indent="  ") == '  crm: "/crm/"'


class TestSeamTemplateTags:
    """The ``quickscale_seam`` library renders the bodies from live settings."""

    @staticmethod
    def _urlconf() -> types.ModuleType:
        from django.urls import include, path

        def _view(request: Any) -> None:
            return None

        urlconf = types.ModuleType("_quickscale_runtime_seam_test_urls")
        urlconf.urlpatterns = [
            path("", _view, name="home"),
            path("crm", _view, name="quickscale_crm_shell"),
            path("social", _view, name="social-link-tree"),
            path("social/embeds", _view, name="social-embeds"),
            path(
                "analytics/",
                include(([path("", _view, name="dashboard")], "quickscale_analytics")),
            ),
        ]
        return urlconf

    def test_tags_render_from_live_settings(self, monkeypatch) -> None:
        from django.conf import settings as django_settings
        from django.template import Context, Engine

        if not django_settings.configured:
            django_settings.configure(
                DEBUG=False,
                SECRET_KEY="quickscale-test-key",
                USE_I18N=False,
                USE_TZ=False,
            )

        from django.urls import clear_url_caches

        monkeypatch.setattr(
            django_settings, "ROOT_URLCONF", self._urlconf(), raising=False
        )
        clear_url_caches()
        monkeypatch.setattr(
            django_settings,
            "INSTALLED_APPS",
            [
                "quickscale_modules_crm",
                "quickscale_modules_social",
                "quickscale_modules_analytics",
            ],
            raising=False,
        )
        for name in (
            "QUICKSCALE_CRM_ENABLED",
            "QUICKSCALE_SOCIAL_ENABLED",
            "QUICKSCALE_ANALYTICS_ENABLED",
            "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED",
        ):
            monkeypatch.setattr(django_settings, name, True, raising=False)
        monkeypatch.setattr(
            django_settings, "QUICKSCALE_SOCIAL_EMBEDS_ENABLED", False, raising=False
        )

        engine = Engine(
            libraries={"quickscale_seam": "quickscale_core.runtime.seam_tags"}
        )
        template = engine.from_string(
            "{% load quickscale_seam %}modules: {\n{% seam_module_flags %}\n};"
            "paths: {\n{% seam_module_paths %}\n};"
        )

        rendered = template.render(Context({}))

        assert "          crm: true," in rendered
        assert "          social: true," in rendered
        assert "          analytics: true," in rendered
        # Absent from INSTALLED_APPS: the flag renders false.
        assert "          billing: false," in rendered
        assert '          crm: "/crm",' in rendered
        assert '          social: "/social",' in rendered
        assert '          analytics: "/analytics/"' in rendered
