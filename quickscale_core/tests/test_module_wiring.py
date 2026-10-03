"""Tests for module_wiring.py - deterministic wiring renderer."""

from pathlib import Path

import pytest

from quickscale_core.module_wiring import (
    ModuleWiringSpec,
    _merge_unique,
    _sort_module_items,
    collect_spa_routes,
    collect_wiring,
    collect_url_wiring,
    render_settings_modules_py,
    render_urls_modules_py,
    write_managed_wiring,
)


class TestMergeUnique:
    """Tests for _merge_unique helper."""

    def test_merge_unique_appends_new_items(self) -> None:
        """New items are appended in order."""
        items: list[str] = ["a", "b"]
        _merge_unique(items, ["c", "d"])
        assert items == ["a", "b", "c", "d"]

    def test_merge_unique_skips_duplicates(self) -> None:
        """Items already present are not re-added."""
        items: list[str] = ["a", "b"]
        _merge_unique(items, ["b", "c", "a"])
        assert items == ["a", "b", "c"]

    def test_merge_unique_empty_additions(self) -> None:
        """Adding an empty iterable leaves items unchanged."""
        items: list[str] = ["x"]
        _merge_unique(items, [])
        assert items == ["x"]

    def test_merge_unique_into_empty_list(self) -> None:
        """Items are added to an empty list."""
        items: list[str] = []
        _merge_unique(items, ["a", "b", "a"])
        assert items == ["a", "b"]

    def test_merge_unique_preserves_first_seen_order(self) -> None:
        """First-seen order is preserved across multiple calls."""
        items: list[str] = ["z"]
        _merge_unique(items, ["m", "a"])
        _merge_unique(items, ["a", "z", "b"])
        assert items == ["z", "m", "a", "b"]


class TestSortModuleItems:
    """Tests for _sort_module_items helper."""

    def test_sort_module_items_returns_sorted_pairs(self) -> None:
        """Items are returned sorted by module name."""
        specs = {
            "payments": ModuleWiringSpec(apps=("payments_app",)),
            "auth": ModuleWiringSpec(apps=("auth_app",)),
            "blog": ModuleWiringSpec(apps=("blog_app",)),
        }
        result = _sort_module_items(specs)
        names = [name for name, _ in result]
        assert names == ["auth", "blog", "payments"]

    def test_sort_module_items_single_entry(self) -> None:
        """Single-entry mapping returns a list with one tuple."""
        specs = {"only": ModuleWiringSpec()}
        result = _sort_module_items(specs)
        assert len(result) == 1
        assert result[0][0] == "only"

    def test_sort_module_items_empty_mapping(self) -> None:
        """Empty mapping returns empty list."""
        result = _sort_module_items({})
        assert result == []


class TestCollectWiring:
    """Tests for collect_wiring."""

    def test_collect_wiring_empty_specs(self) -> None:
        """Empty module specs produce empty collections."""
        apps, middleware, settings, urls = collect_wiring({})
        assert apps == []
        assert middleware == []
        assert settings == {}
        assert urls == []

    def test_collect_wiring_single_spec(self) -> None:
        """Single spec produces the spec's wiring."""
        spec = ModuleWiringSpec(
            apps=("myapp",),
            middleware=("myapp.middleware.MyMiddleware",),
            settings={"MY_SETTING": True},
            url_includes=(("api/", "myapp.urls"),),
        )
        apps, middleware, settings, urls = collect_wiring({"myapp": spec})
        assert apps == ["myapp"]
        assert middleware == ["myapp.middleware.MyMiddleware"]
        assert settings == {"MY_SETTING": True}
        assert urls == [("api/", "myapp.urls")]

    def test_collect_wiring_multiple_specs_sorted(self) -> None:
        """Apps are merged in deterministic (sorted) module name order."""
        specs = {
            "z_module": ModuleWiringSpec(apps=("z_app",)),
            "a_module": ModuleWiringSpec(apps=("a_app",)),
        }
        apps, _, _, _ = collect_wiring(specs)
        assert apps == ["a_app", "z_app"]

    def test_collect_wiring_deduplicates_apps(self) -> None:
        """Duplicate apps across modules appear only once."""
        specs = {
            "mod_a": ModuleWiringSpec(apps=("shared_app", "mod_a_app")),
            "mod_b": ModuleWiringSpec(apps=("shared_app", "mod_b_app")),
        }
        apps, _, _, _ = collect_wiring(specs)
        assert apps.count("shared_app") == 1

    def test_collect_wiring_equal_setting_values_from_two_modules_are_allowed(
        self,
    ) -> None:
        """Two modules may write one setting when their values are equal."""
        extensions = ["markdown.extensions.fenced_code"]
        specs = {
            "blog": ModuleWiringSpec(
                settings={"MARKDOWNX_MARKDOWN_EXTENSIONS": extensions}
            ),
            "listings": ModuleWiringSpec(
                settings={"MARKDOWNX_MARKDOWN_EXTENSIONS": extensions}
            ),
        }
        _, _, settings, _ = collect_wiring(specs)
        assert settings["MARKDOWNX_MARKDOWN_EXTENSIONS"] == extensions

    def test_collect_wiring_conflicting_setting_values_fail(self) -> None:
        """A differing second value fails, naming both modules and the key."""
        specs = {
            "auth": ModuleWiringSpec(settings={"ACCOUNT_ADAPTER": "auth.Adapter"}),
            "orgs": ModuleWiringSpec(settings={"ACCOUNT_ADAPTER": "orgs.Adapter"}),
        }
        with pytest.raises(ValueError) as exc_info:
            collect_wiring(specs)
        message = str(exc_info.value)
        assert "'auth'" in message
        assert "'orgs'" in message
        assert "ACCOUNT_ADAPTER" in message

    def test_collect_wiring_rest_framework_merges_top_level_keys(self) -> None:
        """Different top-level REST_FRAMEWORK keys from two modules both survive."""
        specs = {
            "billing": ModuleWiringSpec(
                settings={"REST_FRAMEWORK": {"DEFAULT_THROTTLE_RATES": {"a": "1/hour"}}}
            ),
            "crm": ModuleWiringSpec(settings={"REST_FRAMEWORK": {"PAGE_SIZE": 25}}),
        }
        _, _, settings, _ = collect_wiring(specs)
        assert settings["REST_FRAMEWORK"] == {
            "DEFAULT_THROTTLE_RATES": {"a": "1/hour"},
            "PAGE_SIZE": 25,
        }

    def test_collect_wiring_rest_framework_merges_nested_dicts(self) -> None:
        """REST_FRAMEWORK sub-dicts merge key by key across modules."""
        specs = {
            "billing": ModuleWiringSpec(
                settings={
                    "REST_FRAMEWORK": {
                        "DEFAULT_THROTTLE_RATES": {
                            "quickscale_billing_checkout": "30/hour"
                        }
                    }
                }
            ),
            "forms": ModuleWiringSpec(
                settings={
                    "REST_FRAMEWORK": {
                        "DEFAULT_THROTTLE_RATES": {"quickscale_forms_submit": "5/hour"}
                    }
                }
            ),
        }
        _, _, settings, _ = collect_wiring(specs)
        assert settings["REST_FRAMEWORK"] == {
            "DEFAULT_THROTTLE_RATES": {
                "quickscale_billing_checkout": "30/hour",
                "quickscale_forms_submit": "5/hour",
            }
        }

    def test_collect_wiring_rest_framework_sub_key_conflict_fails(self) -> None:
        """Two modules may not set one REST_FRAMEWORK sub-key differently."""
        specs = {
            "billing": ModuleWiringSpec(
                settings={
                    "REST_FRAMEWORK": {
                        "DEFAULT_THROTTLE_RATES": {
                            "quickscale_billing_checkout": "30/hour"
                        }
                    }
                }
            ),
            "forms": ModuleWiringSpec(
                settings={
                    "REST_FRAMEWORK": {
                        "DEFAULT_THROTTLE_RATES": {
                            "quickscale_billing_checkout": "5/hour"
                        }
                    }
                }
            ),
        }
        with pytest.raises(ValueError) as exc_info:
            collect_wiring(specs)
        message = str(exc_info.value)
        assert "'billing'" in message
        assert "'forms'" in message
        assert "DEFAULT_THROTTLE_RATES" in message
        assert "quickscale_billing_checkout" in message

    def test_collect_wiring_rest_framework_equal_values_are_allowed(self) -> None:
        """Equal REST_FRAMEWORK contributions merge without failing."""
        contribution = {"DEFAULT_THROTTLE_RATES": {"shared": "30/hour"}}
        specs = {
            "billing": ModuleWiringSpec(settings={"REST_FRAMEWORK": contribution}),
            "forms": ModuleWiringSpec(settings={"REST_FRAMEWORK": contribution}),
        }
        _, _, settings, _ = collect_wiring(specs)
        assert settings["REST_FRAMEWORK"] == contribution

    def test_collect_wiring_unlisted_dict_settings_do_not_merge(self) -> None:
        """Only listed settings merge sub-keys; other dict keys must match."""
        specs = {
            "mod_a": ModuleWiringSpec(settings={"SOME_DICT": {"a": 1}}),
            "mod_b": ModuleWiringSpec(settings={"SOME_DICT": {"b": 2}}),
        }
        with pytest.raises(ValueError, match="SOME_DICT"):
            collect_wiring(specs)

    def test_collect_wiring_deduplicates_urls(self) -> None:
        """Duplicate URL includes appear only once."""
        specs = {
            "mod_a": ModuleWiringSpec(url_includes=(("api/", "mod_a.urls"),)),
            "mod_b": ModuleWiringSpec(url_includes=(("api/", "mod_a.urls"),)),
        }
        _, _, _, urls = collect_wiring(specs)
        assert urls.count(("api/", "mod_a.urls")) == 1

    def test_collect_wiring_multiple_urls_preserved(self) -> None:
        """Different URL patterns from multiple modules are all included."""
        specs = {
            "mod_a": ModuleWiringSpec(url_includes=(("a/", "mod_a.urls"),)),
            "mod_b": ModuleWiringSpec(url_includes=(("b/", "mod_b.urls"),)),
        }
        _, _, _, urls = collect_wiring(specs)
        assert ("a/", "mod_a.urls") in urls
        assert ("b/", "mod_b.urls") in urls

    def test_collect_wiring_places_pre_home_urls_before_post_home_urls(self) -> None:
        """Pre-home URLs are returned ahead of post-home URLs regardless of module sort."""
        specs = {
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),)),
            "orgs": ModuleWiringSpec(
                pre_home_url_includes=(("", "quickscale_modules_orgs.urls"),)
            ),
        }
        _, _, _, urls = collect_wiring(specs)
        assert urls == [
            ("", "quickscale_modules_orgs.urls"),
            ("accounts/", "allauth.urls"),
        ]


class TestCollectUrlWiring:
    """Tests for collect_url_wiring."""

    def test_collect_url_wiring_separates_pre_home_and_post_home(self) -> None:
        """URL includes are grouped into pre-home and post-home buckets."""
        specs = {
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),)),
            "orgs": ModuleWiringSpec(
                pre_home_url_includes=(("", "quickscale_modules_orgs.urls"),)
            ),
        }

        pre_home_urls, post_home_urls = collect_url_wiring(specs)

        assert pre_home_urls == [("", "quickscale_modules_orgs.urls")]
        assert post_home_urls == [("accounts/", "allauth.urls")]


class TestRenderSettingsModulesPy:
    """Tests for render_settings_modules_py."""

    def test_render_settings_modules_py_header(self) -> None:
        """Output contains the DO-NOT-EDIT header."""
        content = render_settings_modules_py({})
        assert "DO NOT EDIT MANUALLY" in content
        assert "QuickScale managed module settings wiring" in content

    def test_render_settings_modules_py_empty_specs(self) -> None:
        """Empty specs produce empty lists and dict."""
        content = render_settings_modules_py({})
        assert "MODULE_INSTALLED_APPS: list[str] = []" in content
        assert "MODULE_MIDDLEWARE: list[str] = []" in content
        assert "MODULE_SETTINGS: dict[str, object] = {}" in content

    def test_render_settings_modules_py_with_apps(self) -> None:
        """Apps appear in MODULE_INSTALLED_APPS."""
        specs = {"auth": ModuleWiringSpec(apps=("django_allauth",))}
        content = render_settings_modules_py(specs)
        assert "django_allauth" in content

    def test_render_settings_modules_py_with_settings(self) -> None:
        """Settings appear in MODULE_SETTINGS."""
        specs = {"auth": ModuleWiringSpec(settings={"ACCOUNT_SIGNUP": True})}
        content = render_settings_modules_py(specs)
        assert "ACCOUNT_SIGNUP" in content

    def test_render_settings_modules_py_is_valid_python(self) -> None:
        """Rendered output can be compiled as valid Python."""
        specs = {
            "auth": ModuleWiringSpec(
                apps=("allauth",),
                middleware=("allauth.middleware.X",),
                settings={"LOGIN_URL": "/login/"},
            )
        }
        content = render_settings_modules_py(specs)
        compile(content, "<string>", "exec")  # should not raise


class TestRenderUrlsModulesPy:
    """Tests for render_urls_modules_py."""

    def test_render_urls_modules_py_empty_produces_empty_list(self) -> None:
        """No URL specs renders empty pre-home and post-home lists."""
        content = render_urls_modules_py({})
        assert "PRE_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []" in content
        assert "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []" in content
        assert "MODULE_URLPATTERNS: list[ManagedURLPattern] = []" in content
        assert "from django.urls import URLPattern, URLResolver" in content

    def test_render_urls_modules_py_empty_header(self) -> None:
        """Empty URL output still has the DO-NOT-EDIT header."""
        content = render_urls_modules_py({})
        assert "DO NOT EDIT MANUALLY" in content
        assert "QuickScale managed module URL wiring" in content

    def test_render_urls_modules_py_with_urls(self) -> None:
        """Post-home URL patterns appear in the rendered output."""
        specs = {
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),))
        }
        content = render_urls_modules_py(specs)
        assert 'path("accounts/", include("allauth.urls"))' in content
        assert "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = [" in content
        assert "MODULE_URLPATTERNS: list[ManagedURLPattern] = (" in content
        assert "SPA_MODULE_URLPATTERNS: list[ManagedURLPattern] = []" in content
        assert (
            "from django.urls import URLPattern, URLResolver, include, path" in content
        )

    def test_render_urls_modules_py_renders_spa_routes(self) -> None:
        """Manifest-declared React shell routes render under the module stem."""
        specs = {
            "crm": ModuleWiringSpec(
                url_includes=(("crm/", "quickscale_modules_crm.urls"),),
                spa_routes=(("^crm/?$", "shell"),),
            )
        }
        content = render_urls_modules_py(specs)
        assert "SPA_MODULE_URLPATTERNS: list[ManagedURLPattern] = [" in content
        assert (
            "re_path('^crm/?$', react_shell_view, name='quickscale_crm_shell')"
            in content
        )
        assert "from .views import react_shell_view" in content
        assert "re_path" in content.split("\n\n")[0] or "re_path" in content
        compile(content, "<string>", "exec")  # should not raise

    def test_collect_spa_routes_reports_module_route_and_name(self) -> None:
        """collect_spa_routes emits (module, route, name) in module-name order."""
        specs = {
            "crm": ModuleWiringSpec(spa_routes=(("^crm/?$", "shell"),)),
            "blog": ModuleWiringSpec(spa_routes=(("^blog/?$", "shell"),)),
        }
        assert collect_spa_routes(specs) == [
            ("blog", "^blog/?$", "shell"),
            ("crm", "^crm/?$", "shell"),
        ]

    def test_render_urls_modules_py_multiple_patterns(self) -> None:
        """Multiple URL patterns all appear in the output."""
        specs = {
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),)),
            "api": ModuleWiringSpec(url_includes=(("api/", "my_api.urls"),)),
        }
        content = render_urls_modules_py(specs)
        assert "accounts/" in content
        assert "api/" in content

    def test_render_urls_modules_py_separates_pre_home_patterns(self) -> None:
        """Pre-home URL patterns are rendered into their dedicated bucket."""
        specs = {
            "orgs": ModuleWiringSpec(
                pre_home_url_includes=(("", "quickscale_modules_orgs.urls"),)
            ),
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),)),
        }
        content = render_urls_modules_py(specs)
        assert "PRE_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = [" in content
        assert 'path("", include("quickscale_modules_orgs.urls"))' in content
        assert "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = [" in content
        assert "PRE_HOME_MODULE_URLPATTERNS + POST_HOME_MODULE_URLPATTERNS" in content

    def test_render_urls_modules_py_is_valid_python(self) -> None:
        """Rendered URL output can be compiled as valid Python."""
        specs = {
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),))
        }
        content = render_urls_modules_py(specs)
        compile(content, "<string>", "exec")  # should not raise


class TestWriteManagedWiring:
    """Tests for write_managed_wiring."""

    def test_write_managed_wiring_creates_files(self, tmp_path: Path) -> None:
        """Both settings/modules.py and urls_modules.py are created."""
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()

        specs = {
            "auth": ModuleWiringSpec(
                apps=("allauth",),
                settings={"ACCOUNT_LOGIN": True},
                url_includes=(("accounts/", "allauth.urls"),),
            )
        }
        write_managed_wiring(package_dir, specs)

        settings_file = package_dir / "settings" / "modules.py"
        urls_file = package_dir / "urls_modules.py"

        assert settings_file.exists()
        assert urls_file.exists()

    def test_write_managed_wiring_settings_content(self, tmp_path: Path) -> None:
        """Written settings/modules.py contains expected content."""
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()

        specs = {"auth": ModuleWiringSpec(apps=("testapp",))}
        write_managed_wiring(package_dir, specs)

        content = (package_dir / "settings" / "modules.py").read_text()
        assert "testapp" in content
        assert "MODULE_INSTALLED_APPS" in content

    def test_write_managed_wiring_urls_content(self, tmp_path: Path) -> None:
        """Written urls_modules.py contains expected content."""
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()

        specs = {"auth": ModuleWiringSpec(url_includes=(("api/", "auth.urls"),))}
        write_managed_wiring(package_dir, specs)

        content = (package_dir / "urls_modules.py").read_text()
        assert "api/" in content

    def test_write_managed_wiring_creates_settings_dir(self, tmp_path: Path) -> None:
        """The settings/ subdirectory is created if it doesn't exist."""
        package_dir = tmp_path / "newpackage"
        package_dir.mkdir()

        write_managed_wiring(package_dir, {})

        assert (package_dir / "settings").is_dir()

    def test_write_managed_wiring_empty_specs(self, tmp_path: Path) -> None:
        """Empty specs produce valid empty wiring files."""
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()

        write_managed_wiring(package_dir, {})

        settings_content = (package_dir / "settings" / "modules.py").read_text()
        urls_content = (package_dir / "urls_modules.py").read_text()

        assert "MODULE_INSTALLED_APPS" in settings_content
        assert "MODULE_URLPATTERNS" in urls_content

    def test_write_managed_wiring_creates_extra_managed_files(
        self, tmp_path: Path
    ) -> None:
        """Extra managed integration files are written into quickscale_managed/."""
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()

        specs = {
            "social": ModuleWiringSpec(
                url_includes=(
                    ("_quickscale/social/", "myapp.quickscale_managed.social_urls"),
                ),
                managed_files={
                    "quickscale_managed/__init__.py": '"""managed"""\n',
                    "quickscale_managed/social_urls.py": "urlpatterns = []\n",
                },
            )
        }

        write_managed_wiring(package_dir, specs)

        assert (package_dir / "quickscale_managed" / "__init__.py").exists()
        assert (package_dir / "quickscale_managed" / "social_urls.py").exists()

    def test_write_managed_wiring_removes_stale_extra_managed_files(
        self, tmp_path: Path
    ) -> None:
        """Stale quickscale_managed files are removed when no specs require them."""
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()
        managed_dir = package_dir / "quickscale_managed"
        managed_dir.mkdir()
        stale_file = managed_dir / "stale.py"
        stale_file.write_text("stale = True\n")

        write_managed_wiring(package_dir, {})

        assert not stale_file.exists()
        assert not managed_dir.exists()


class TestModuleWiringSpec:
    """Tests for ModuleWiringSpec dataclass."""

    def test_default_spec_has_empty_fields(self) -> None:
        """Default spec has empty tuples and dict."""
        spec = ModuleWiringSpec()
        assert spec.apps == ()
        assert spec.middleware == ()
        assert spec.settings == {}
        assert spec.pre_home_url_includes == ()
        assert spec.url_includes == ()
        assert spec.spa_routes == ()
        assert spec.managed_files == {}

    def test_spec_with_all_fields(self) -> None:
        """Spec stores all provided fields correctly."""
        spec = ModuleWiringSpec(
            apps=("app1", "app2"),
            middleware=("mw1",),
            settings={"K": "V"},
            pre_home_url_includes=(("", "pkg.pre_home_urls"),),
            url_includes=(("path/", "pkg.urls"),),
        )
        assert spec.apps == ("app1", "app2")
        assert spec.middleware == ("mw1",)
        assert spec.settings == {"K": "V"}
        assert spec.pre_home_url_includes == (("", "pkg.pre_home_urls"),)
        assert spec.url_includes == (("path/", "pkg.urls"),)

    def test_spec_is_frozen(self) -> None:
        """ModuleWiringSpec is immutable (frozen dataclass)."""
        spec = ModuleWiringSpec(apps=("app1",))
        with pytest.raises(Exception):
            spec.apps = ("app2",)  # type: ignore[misc]


def test_generated_urls_template_renders_module_spa_routes_after_module_urls() -> None:
    """Rule 41: module React shell routes render after the modules' includes.

    The host shell keeps only the theme and tenancy reservations; a module's
    server-rendered index keeps its path, and the module's declared React
    shell routes load from the managed wiring after every module include.
    """
    template_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "quickscale_core"
        / "generator"
        / "templates"
        / "project_name"
        / "urls.py.j2"
    )
    content = template_path.read_text()

    react_shell_marker = "urlpatterns += react_shell_urlpatterns"
    pre_home_marker = "urlpatterns += PRE_HOME_MODULE_URLPATTERNS"
    post_home_marker = "urlpatterns += POST_HOME_MODULE_URLPATTERNS"
    spa_marker = "urlpatterns += SPA_MODULE_URLPATTERNS"
    catch_all_marker = 're_path(r".*", react_shell_view)'
    # SA94: retired showcase_html removed the non-React home marker.
    assert react_shell_marker in content
    assert pre_home_marker in content
    assert post_home_marker in content
    assert spa_marker in content
    assert r"^orgs/(?!api(?:/|$))[^/]+/(blog|listings|members|settings)/?$" in content
    assert r"^orgs/[^/]+/forms/[^/]+/?$" not in content
    assert r"^orgs/[^/]+/billing/" not in content
    assert r"^orgs/invitations/" not in content
    # The orgs/theme reservations stay ahead of the module URL lists.
    assert content.index(react_shell_marker) < content.index(pre_home_marker)
    # The module React shell routes come after every module include, and
    # before the SPA catch-all.
    assert content.index(post_home_marker) < content.index(spa_marker)
    assert content.index(spa_marker) < content.index(catch_all_marker)

    # Rule 41: no module path literal remains in the generator template.  The
    # module shell routes are manifest-declared and rendered from discovery.
    assert r"^crm/?$" not in content
    assert 'name="crm-shell"' not in content
    assert r"^(profile|blog|listings|settings)/?$" not in content
    assert r"^blog/?$" not in content
    assert r"^listings/?$" not in content
    # Forms keeps its host reservations: its module entrypoint renders only a
    # mount-point div (rule 41's stated exception), so the shell must win.
    assert r"^forms/?$" in content
    assert r"^forms/[^/]+/?$" in content


def test_crm_module_shell_route_declared_in_manifest() -> None:
    """CR-T120-003 + SA235: the CRM React shell route is manifest-declared.

    The React SPA owns /crm and /crm/ through the CRM manifest's ``spa_routes``
    entry, rendered after the module's own include; the Django staff dashboard
    lives at /crm/dashboard/ to avoid shadowing.  The generated template holds
    no CRM path literal (rule 41).
    """
    template_path = (
        Path(__file__).resolve().parents[1]
        / "src"
        / "quickscale_core"
        / "generator"
        / "templates"
        / "project_name"
        / "urls.py.j2"
    )
    template_content = template_path.read_text()
    assert r"^crm/?$" not in template_content
    assert 'name="crm-shell"' not in template_content
    assert r"^orgs/[^/]+/crm" not in template_content
    assert r"/crm/dashboard" not in template_content

    crm_manifest = (
        Path(__file__).resolve().parents[2]
        / "quickscale_modules"
        / "crm"
        / "module.yml"
    ).read_text()
    assert "wiring_field: spa_routes" in crm_manifest
    assert "- ^crm/?$" in crm_manifest

    # The actual CRM module urls.py is module-relative: the manifest's
    # url_includes entry mounts it at crm/, so the dashboard registers at
    # dashboard/ and no crm/ prefix lives in the module URLconf (rule 7).
    crm_urls_module = (
        Path(__file__).resolve().parents[2]
        / "quickscale_modules"
        / "crm"
        / "src"
        / "quickscale_modules_crm"
        / "urls.py"
    )
    crm_content = crm_urls_module.read_text()
    assert 'path("dashboard/",' in crm_content
    assert 'path("crm/' not in crm_content
