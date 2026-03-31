"""Tests for module_wiring.py - deterministic wiring renderer."""

from pathlib import Path

import pytest

from quickscale_core.module_wiring import (
    ModuleWiringSpec,
    _merge_unique,
    _sort_module_items,
    collect_wiring,
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

    def test_collect_wiring_settings_last_writer_wins(self) -> None:
        """For colliding setting keys, the last module (alphabetically) wins."""
        specs = {
            "beta": ModuleWiringSpec(settings={"KEY": "beta_value"}),
            "alpha": ModuleWiringSpec(settings={"KEY": "alpha_value"}),
        }
        _, _, settings, _ = collect_wiring(specs)
        # alpha < beta alphabetically, so beta is processed last → wins
        assert settings["KEY"] == "beta_value"

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
        """No URL specs renders an empty MODULE_URLPATTERNS list."""
        content = render_urls_modules_py({})
        assert "MODULE_URLPATTERNS: list[URLPattern] = []" in content
        assert "from django.urls import URLPattern" in content

    def test_render_urls_modules_py_empty_header(self) -> None:
        """Empty URL output still has the DO-NOT-EDIT header."""
        content = render_urls_modules_py({})
        assert "DO NOT EDIT MANUALLY" in content
        assert "QuickScale managed module URL wiring" in content

    def test_render_urls_modules_py_with_urls(self) -> None:
        """URL patterns appear in the MODULE_URLPATTERNS list."""
        specs = {
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),))
        }
        content = render_urls_modules_py(specs)
        assert 'path("accounts/", include("allauth.urls"))' in content
        assert "MODULE_URLPATTERNS = [" in content
        assert "from django.urls import include, path" in content

    def test_render_urls_modules_py_multiple_patterns(self) -> None:
        """Multiple URL patterns all appear in the output."""
        specs = {
            "auth": ModuleWiringSpec(url_includes=(("accounts/", "allauth.urls"),)),
            "api": ModuleWiringSpec(url_includes=(("api/", "my_api.urls"),)),
        }
        content = render_urls_modules_py(specs)
        assert "accounts/" in content
        assert "api/" in content

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
        assert spec.url_includes == ()
        assert spec.managed_files == {}

    def test_spec_with_all_fields(self) -> None:
        """Spec stores all provided fields correctly."""
        spec = ModuleWiringSpec(
            apps=("app1", "app2"),
            middleware=("mw1",),
            settings={"K": "V"},
            url_includes=(("path/", "pkg.urls"),),
        )
        assert spec.apps == ("app1", "app2")
        assert spec.middleware == ("mw1",)
        assert spec.settings == {"K": "V"}
        assert spec.url_includes == (("path/", "pkg.urls"),)

    def test_spec_is_frozen(self) -> None:
        """ModuleWiringSpec is immutable (frozen dataclass)."""
        spec = ModuleWiringSpec(apps=("app1",))
        with pytest.raises(Exception):
            spec.apps = ("app2",)  # type: ignore[misc]
