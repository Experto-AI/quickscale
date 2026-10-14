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
import ast
import re
from pathlib import Path
from typing import Any

from quickscale_core.contracts.module_catalog import MODULE_CATALOG
from quickscale_core.runtime.seam import (
    SEAM_DECLARATION_RELATIVE_PATH,
    SEAM_KEY_MANIFEST_RELATIVE_PATH,
    render_module_api_paths,
    render_module_flags,
    render_module_paths,
    render_seam_declaration,
    render_seam_key_manifest,
    seam_api_path_names,
    seam_module_api_paths,
    seam_module_flags,
    seam_module_paths,
    seam_modules,
    seam_path_names,
)

import pytest


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


class TestSeamApiBaseResolution:
    """Rule 41: ``moduleApiPaths`` resolves each module's base at the API boundary."""

    def test_api_path_names_are_the_api_surfaces(self) -> None:
        assert seam_api_path_names() == ("orgs", "billing", "crm", "forms")

    def test_api_endpoint_suffixes_match_shipped_url_sources(self) -> None:
        """Route drift cannot silently invalidate the seam's endpoint structure."""
        from quickscale_core.runtime.seam import _SEAM_MODULE_API_PATHS

        modules_root = Path(__file__).resolve().parents[2] / "quickscale_modules"
        for module, route, suffix in _SEAM_MODULE_API_PATHS:
            source = (
                modules_root
                / module
                / "src"
                / f"quickscale_modules_{module}"
                / "urls.py"
            )
            tree = ast.parse(source.read_text())
            endpoint_name = route.split(":")[1]
            if module == "crm":
                assert any(
                    isinstance(node, ast.Assign)
                    and any(
                        isinstance(target, ast.Name) and target.id == "root_view_name"
                        for target in node.targets
                    )
                    and isinstance(node.value, ast.Constant)
                    and node.value.value == endpoint_name
                    for node in ast.walk(tree)
                )
            matching_paths = [
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "path"
                and node.args
                and (
                    any(
                        keyword.arg == "name"
                        and isinstance(keyword.value, ast.Constant)
                        and keyword.value.value == endpoint_name
                        for keyword in node.keywords
                    )
                    or (
                        module == "crm"
                        and isinstance(node.args[0], ast.Constant)
                        and node.args[0].value == "api/"
                    )
                )
            ]
            assert len(matching_paths) == 1
            assert ast.literal_eval(matching_paths[0].args[0]) == "api/" + suffix

    @pytest.mark.parametrize("outer_prefix", ["", "/api", "/tenant/api/acme/api"])
    def test_api_bases_cut_at_the_mount_api_boundary(self, outer_prefix) -> None:
        settings_obj = _settings(
            INSTALLED_APPS=[
                "quickscale_modules_orgs",
                "quickscale_modules_billing",
                "quickscale_modules_crm",
                "quickscale_modules_forms",
            ],
            QUICKSCALE_ORGS_ENABLED=True,
            QUICKSCALE_BILLING_ENABLED=True,
            QUICKSCALE_CRM_ENABLED=True,
            QUICKSCALE_FORMS_ENABLED=True,
        )
        reverse = _RecordingReverse(
            {
                "quickscale_orgs:api_list_create": "/orgs/api/",
                "quickscale_billing:subscription_plans": "/billing/api/plans/",
                "quickscale_crm:api_root": "/crm/api/",
                "quickscale_forms:admin_form_list": "/forms/api/admin/forms/",
                "home": "/",
            }
        )

        reverse.routes = {
            name: outer_prefix + path for name, path in reverse.routes.items()
        }
        paths = seam_module_api_paths(settings_obj, reverse)

        assert paths == {
            "orgs": outer_prefix + "/orgs/api/",
            "billing": outer_prefix + "/billing/api/",
            "crm": outer_prefix + "/crm/api/",
            "forms": outer_prefix + "/forms/api/",
        }
        assert reverse.calls == [
            "quickscale_orgs:api_list_create",
            "quickscale_billing:subscription_plans",
            "quickscale_crm:api_root",
            "quickscale_forms:admin_form_list",
        ]

    def test_non_default_mount_still_cuts_at_the_api_boundary(self) -> None:
        settings_obj = _settings(
            INSTALLED_APPS=["quickscale_modules_orgs"],
            QUICKSCALE_ORGS_ENABLED=True,
        )
        reverse = _RecordingReverse(
            {"quickscale_orgs:api_list_create": "/tenant/acme/orgs/api/", "home": "/"}
        )

        paths = seam_module_api_paths(settings_obj, reverse)

        assert paths["orgs"] == "/tenant/acme/orgs/api/"

    def test_disabled_and_absent_api_bases_fall_back_home(self) -> None:
        settings_obj = _settings(
            INSTALLED_APPS=["quickscale_modules_orgs"],
            QUICKSCALE_ORGS_ENABLED=False,
        )
        reverse = _RecordingReverse({"home": "/"})

        paths = seam_module_api_paths(settings_obj, reverse)

        assert paths == {"orgs": "/", "billing": "/", "crm": "/", "forms": "/"}
        assert reverse.calls == ["home", "home", "home", "home"]

    @pytest.mark.parametrize("path", ["/orgs/", "/api/orgs/"])
    def test_route_without_api_boundary_fails_loud(self, path) -> None:
        settings_obj = _settings(
            INSTALLED_APPS=["quickscale_modules_orgs"],
            QUICKSCALE_ORGS_ENABLED=True,
        )
        reverse = _RecordingReverse(
            {"quickscale_orgs:api_list_create": path, "home": "/"}
        )

        with pytest.raises(ValueError, match="api"):
            seam_module_api_paths(settings_obj, reverse)


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
        assert render_module_api_paths({"orgs": "/orgs/api/"}, indent="  ") == (
            '  orgs: "/orgs/api/"'
        )

    def test_render_module_api_paths_omits_only_the_last_comma(self) -> None:
        rendered = render_module_api_paths(
            {"orgs": "/orgs/api/", "billing": "/billing/api/"}
        )

        assert rendered == (
            '          orgs: "/orgs/api/",\n          billing: "/billing/api/"'
        )


def _interface_property_names(declaration: str, interface_name: str) -> set[str]:
    """Return the property names of one exported interface in *declaration*."""
    body = declaration.split(f"export interface {interface_name} {{", 1)[1]
    return {
        line.strip().split(":", 1)[0]
        for line in body.split("}", 1)[0].splitlines()
        if line.strip()
    }


class TestSeamDeclaration:
    """The managed seam declaration renders from the shipped seam tables (SA276)."""

    def test_declaration_carries_exactly_the_seam_tables(self) -> None:
        """Each interface holds exactly its table's names, one per line."""
        declaration = render_seam_declaration()

        assert _interface_property_names(declaration, "QuickScaleModules") == {
            module.name for module in seam_modules()
        }
        assert _interface_property_names(declaration, "QuickScaleModulePaths") == set(
            seam_path_names()
        )
        assert _interface_property_names(
            declaration, "QuickScaleModuleApiPaths"
        ) == set(seam_api_path_names())

    def test_declaration_types_each_table(self) -> None:
        """Flags are booleans; both path tables are strings."""
        declaration = render_seam_declaration()

        for module in seam_modules():
            assert f"  {module.name}: boolean" in declaration
        for name in seam_path_names():
            assert f"  {name}: string" in declaration
        for name in seam_api_path_names():
            assert f"  {name}: string" in declaration

    def test_declaration_is_a_replaced_managed_file(self) -> None:
        """It states the regenerate contract and lives at a project-relative path."""
        declaration = render_seam_declaration()

        assert declaration.startswith("// QuickScale managed seam declaration.")
        assert "DO NOT EDIT MANUALLY" in declaration
        assert declaration.endswith("}\n")
        assert not SEAM_DECLARATION_RELATIVE_PATH.startswith("/")
        assert SEAM_DECLARATION_RELATIVE_PATH.endswith("quickscaleSeam.d.ts")


def _key_array(manifest: str, name: str) -> list[str]:
    """Return the string array *name* declares in the key manifest."""
    body = manifest.split(f"export const {name} = [", 1)[1].split("]", 1)[0]
    return re.findall(r"'([^']*)'", body)


class TestSeamKeyManifest:
    """The managed seam key manifest renders from the shipped seam tables (SA276)."""

    def test_manifest_carries_exactly_the_seam_tables(self) -> None:
        """Every declared array holds exactly its table's names."""
        manifest = render_seam_key_manifest()

        assert _key_array(manifest, "SEAM_MODULE_FLAG_KEYS") == [
            module.name for module in seam_modules()
        ]
        assert _key_array(manifest, "SEAM_MODULE_PATH_KEYS") == list(seam_path_names())
        assert _key_array(manifest, "SEAM_MODULE_API_PATH_KEYS") == list(
            seam_api_path_names()
        )

    def test_manifest_states_the_regenerate_contract(self) -> None:
        """It states the regenerate contract and lives at a project-relative path."""
        manifest = render_seam_key_manifest()

        assert manifest.startswith("// QuickScale managed seam key manifest.")
        assert "DO NOT EDIT MANUALLY" in manifest
        assert manifest.endswith("as const\n")
        assert not SEAM_KEY_MANIFEST_RELATIVE_PATH.startswith("/")
        assert SEAM_KEY_MANIFEST_RELATIVE_PATH.endswith("quickscaleSeam.keys.ts")


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
            path(
                "orgs/",
                include(
                    ([path("api/", _view, name="api_list_create")], "quickscale_orgs")
                ),
            ),
            path(
                "billing/",
                include(
                    (
                        [path("api/plans/", _view, name="subscription_plans")],
                        "quickscale_billing",
                    )
                ),
            ),
            path(
                "crm/",
                include(([path("api/", _view, name="api_root")], "quickscale_crm")),
            ),
            path(
                "forms/",
                include(
                    (
                        [path("api/admin/forms/", _view, name="admin_form_list")],
                        "quickscale_forms",
                    )
                ),
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
                "quickscale_modules_orgs",
                "quickscale_modules_billing",
                "quickscale_modules_forms",
            ],
            raising=False,
        )
        for name in (
            "QUICKSCALE_CRM_ENABLED",
            "QUICKSCALE_SOCIAL_ENABLED",
            "QUICKSCALE_ANALYTICS_ENABLED",
            "QUICKSCALE_SOCIAL_LINK_TREE_ENABLED",
            "QUICKSCALE_ORGS_ENABLED",
            "QUICKSCALE_BILLING_ENABLED",
            "QUICKSCALE_FORMS_ENABLED",
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
            "apiPaths: {\n{% seam_module_api_paths %}\n};"
        )

        rendered = template.render(Context({}))

        assert "          crm: true," in rendered
        assert "          social: true," in rendered
        assert "          analytics: true," in rendered
        # Absent from INSTALLED_APPS: the flag renders false.
        assert "          blog: false," in rendered
        assert '          crm: "/crm",' in rendered
        assert '          social: "/social",' in rendered
        assert '          analytics: "/analytics/"' in rendered
        assert '          orgs: "/orgs/api/",' in rendered
        assert '          billing: "/billing/api/",' in rendered
        assert '          crm: "/crm/api/",' in rendered
        assert '          forms: "/forms/api/"' in rendered

    def test_api_bases_preserve_django_script_prefix(self) -> None:
        from django.urls import get_script_prefix, reverse, set_script_prefix

        settings_obj = _settings(
            INSTALLED_APPS=[
                f"quickscale_modules_{name}" for name in seam_api_path_names()
            ],
            **{
                f"QUICKSCALE_{name.upper()}_ENABLED": True
                for name in seam_api_path_names()
            },
        )
        urlconf = self._urlconf()
        previous_prefix = get_script_prefix()
        try:
            set_script_prefix("/api/")
            paths = seam_module_api_paths(
                settings_obj, lambda name: reverse(name, urlconf=urlconf)
            )
        finally:
            set_script_prefix(previous_prefix)
        assert paths == {name: f"/api/{name}/api/" for name in seam_api_path_names()}
