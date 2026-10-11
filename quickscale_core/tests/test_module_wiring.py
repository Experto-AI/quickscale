"""Tests for module_wiring.py - deterministic wiring renderer."""

import os
from pathlib import Path
from types import ModuleType

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

    def test_collect_wiring_rest_framework_rejects_unadmitted_sub_key(self) -> None:
        """Module wiring admits only DEFAULT_THROTTLE_RATES (rule 30)."""
        specs = {
            "billing": ModuleWiringSpec(
                settings={"REST_FRAMEWORK": {"DEFAULT_THROTTLE_RATES": {"a": "1/hour"}}}
            ),
            "crm": ModuleWiringSpec(settings={"REST_FRAMEWORK": {"PAGE_SIZE": 25}}),
        }
        with pytest.raises(ValueError) as exc_info:
            collect_wiring(specs)
        message = str(exc_info.value)
        assert "'crm'" in message
        assert "PAGE_SIZE" in message
        assert "DEFAULT_THROTTLE_RATES" in message

    def test_collect_wiring_rest_framework_non_mapping_is_rejected(self) -> None:
        """A module's REST_FRAMEWORK value must be the admitted mapping."""
        specs = {
            "crm": ModuleWiringSpec(settings={"REST_FRAMEWORK": ["not-a-mapping"]}),
        }
        with pytest.raises(ValueError) as exc_info:
            collect_wiring(specs)
        message = str(exc_info.value)
        assert "'crm'" in message
        assert "REST_FRAMEWORK" in message

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

    @pytest.mark.parametrize(
        "targets", [("vendor.urls", "alpha.urls"), ("alpha.urls", "vendor.urls")]
    )
    @pytest.mark.parametrize("duplicate_index", [0, 1])
    @pytest.mark.parametrize("chain_bucket", ["pre", "post", "split"])
    @pytest.mark.parametrize("duplicate_bucket", ["pre", "post"])
    def test_chain_duplicates_merge_across_buckets(
        self, targets, duplicate_index, chain_bucket, duplicate_bucket
    ) -> None:
        """Either chain target deduplicates; an unseen target still conflicts."""
        pairs = tuple(("shared/", target) for target in targets)
        pre = (
            pairs
            if chain_bucket == "pre"
            else pairs[:1]
            if chain_bucket == "split"
            else ()
        )
        post = (
            pairs
            if chain_bucket == "post"
            else pairs[1:]
            if chain_bucket == "split"
            else ()
        )
        duplicate = (pairs[duplicate_index],)
        specs = {
            "beta": ModuleWiringSpec(
                pre_home_url_includes=duplicate if duplicate_bucket == "pre" else (),
                url_includes=duplicate if duplicate_bucket == "post" else (),
            ),
            "alpha": ModuleWiringSpec(pre_home_url_includes=pre, url_includes=post),
        }
        assert collect_url_wiring(specs) == (list(pre), list(post))
        rendered = render_urls_modules_py(specs)
        for target in targets:
            assert rendered.count(f'path("shared/", include("{target}"))') == 1
        specs["gamma"] = ModuleWiringSpec(url_includes=(("shared/", "other.urls"),))
        with pytest.raises(ValueError, match="modules 'alpha' and 'gamma'.*'shared/'"):
            collect_url_wiring(specs)

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

    def test_collect_url_wiring_conflicting_prefix_fails(self) -> None:
        """Two modules mounting one prefix with different targets fail."""
        specs = {
            "blog": ModuleWiringSpec(
                url_includes=(("markdownx/", "quickscale_modules_blog.markdownx_urls"),)
            ),
            "listings": ModuleWiringSpec(
                url_includes=(
                    ("markdownx/", "quickscale_modules_listings.markdownx_urls"),
                )
            ),
        }

        with pytest.raises(ValueError) as exc_info:
            collect_url_wiring(specs)

        message = str(exc_info.value)
        assert "'blog'" in message
        assert "'listings'" in message
        assert "markdownx/" in message

    def test_collect_url_wiring_equal_pair_from_two_modules_collapses(self) -> None:
        """The identical (prefix, target) pair from two modules mounts once."""
        specs = {
            "mod_a": ModuleWiringSpec(url_includes=(("api/", "mod_a.urls"),)),
            "mod_b": ModuleWiringSpec(url_includes=(("api/", "mod_a.urls"),)),
        }

        pre_home_urls, post_home_urls = collect_url_wiring(specs)

        assert pre_home_urls == []
        assert post_home_urls == [("api/", "mod_a.urls")]

    def test_collect_url_wiring_same_module_chain_allowed(self) -> None:
        """One module may chain several targets under one prefix."""
        specs = {
            "auth": ModuleWiringSpec(
                url_includes=(
                    ("accounts/", "allauth.urls"),
                    ("accounts/", "quickscale_modules_auth.urls"),
                )
            ),
        }

        _, post_home_urls = collect_url_wiring(specs)

        assert post_home_urls == [
            ("accounts/", "allauth.urls"),
            ("accounts/", "quickscale_modules_auth.urls"),
        ]

    def test_collect_url_wiring_cross_bucket_equal_pair_mounts_once(self) -> None:
        """An identical pair declared in both buckets still mounts once."""
        specs = {
            "mod_a": ModuleWiringSpec(
                pre_home_url_includes=(("shared/", "vendor.urls"),)
            ),
            "mod_b": ModuleWiringSpec(url_includes=(("shared/", "vendor.urls"),)),
        }

        pre_home_urls, post_home_urls = collect_url_wiring(specs)
        rendered = render_urls_modules_py(specs)

        assert pre_home_urls == [("shared/", "vendor.urls")]
        assert post_home_urls == []
        assert rendered.count('path("shared/", include("vendor.urls"))') == 1

    def test_collect_url_wiring_conflict_across_buckets_fails(self) -> None:
        """A pre-home mount and a post-home mount of one prefix may not differ."""
        specs = {
            "mod_a": ModuleWiringSpec(pre_home_url_includes=(("orgs/", "mod_a.urls"),)),
            "mod_b": ModuleWiringSpec(url_includes=(("orgs/", "mod_b.urls"),)),
        }

        with pytest.raises(ValueError, match="orgs/"):
            collect_url_wiring(specs)

    def test_collect_wiring_raises_on_conflicting_prefix(self) -> None:
        """collect_wiring propagates a URL prefix conflict."""
        specs = {
            "mod_a": ModuleWiringSpec(url_includes=(("api/", "mod_a.urls"),)),
            "mod_b": ModuleWiringSpec(url_includes=(("api/", "mod_b.urls"),)),
        }

        with pytest.raises(ValueError, match="api/"):
            collect_wiring(specs)


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


def _exec_rendered_modules(content: str) -> dict[str, object]:
    """Execute rendered settings content in an isolated module namespace."""
    namespace: dict[str, object] = {}
    exec(compile(content, "<rendered-modules>", "exec"), namespace)
    return namespace


class TestRenderSettingsModulesPyEnvMarkers:
    """The ``__QS_ENV__`` marker contract for generated ``modules.py``.

    A nonblank marker becomes a runtime ``os.environ.get("NAME", "")`` read;
    a blank marker becomes the literal empty string and is never resolved
    through an empty environment-variable name.  No credential material is
    read, embedded, or persisted while rendering.
    """

    def test_blank_marker_renders_literal_empty_string(self) -> None:
        """A blank marker is the literal empty string, not an empty-name read."""
        specs = {
            "storage": ModuleWiringSpec(settings={"AWS_ACCESS_KEY_ID": "__QS_ENV__:"})
        }

        content = render_settings_modules_py(specs)

        assert "'AWS_ACCESS_KEY_ID': ''" in content
        assert "__QS_ENV__" not in content
        assert 'os.environ.get("", "")' not in content
        assert "import os" not in content

    def test_blank_marker_survives_an_empty_name_environment_entry(self) -> None:
        """Even an empty-name environment entry is never read for a blank marker."""
        reads: list[tuple[str, object]] = []

        class _ProbeEnviron(dict):
            def get(self, key: str, default: object = None) -> object:
                reads.append((key, default))
                return "read-from-environment"

        probe = ModuleType("os")
        probe.environ = _ProbeEnviron({"": "should-never-be-read"})

        specs = {
            "storage": ModuleWiringSpec(settings={"AWS_ACCESS_KEY_ID": "__QS_ENV__:"})
        }
        content = render_settings_modules_py(specs)

        namespace: dict[str, object] = {"os": probe}
        exec(compile(content, "<rendered-modules>", "exec"), namespace)

        assert namespace["MODULE_SETTINGS"] == {"AWS_ACCESS_KEY_ID": ""}
        assert reads == []

    def test_nonblank_marker_resolves_in_isolated_generated_python(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The generated file resolves the name at runtime, never at render time."""
        monkeypatch.setenv("FIXTURE_ACCESS_KEY", "resolved-value")
        specs = {
            "storage": ModuleWiringSpec(
                settings={
                    "AWS_ACCESS_KEY_ID": "__QS_ENV__:FIXTURE_ACCESS_KEY",
                    "AWS_SECRET_ACCESS_KEY": "__QS_ENV__:FIXTURE_ABSENT_KEY",
                }
            )
        }

        content = render_settings_modules_py(specs)

        assert "import os" in content
        assert 'os.environ.get("FIXTURE_ACCESS_KEY", "")' in content
        assert 'os.environ.get("FIXTURE_ABSENT_KEY", "")' in content
        assert "__QS_ENV__" not in content

        namespace = _exec_rendered_modules(content)
        assert namespace["MODULE_SETTINGS"] == {
            "AWS_ACCESS_KEY_ID": "resolved-value",
            "AWS_SECRET_ACCESS_KEY": "",
        }

    def test_ordinary_literals_survive(self) -> None:
        """Literal values are rendered unchanged and never treated as markers."""
        specs = {
            "auth": ModuleWiringSpec(
                settings={
                    "LOGIN_URL": "/login/",
                    "FEATURE_ENABLED": False,
                    "MAX_ATTEMPTS": 3,
                    "PREFIXED_TEXT": "x__QS_ENV__:NOT_A_MARKER",
                }
            )
        }

        content = render_settings_modules_py(specs)

        assert "'LOGIN_URL': '/login/'" in content
        assert "'FEATURE_ENABLED': False" in content
        assert "'MAX_ATTEMPTS': 3" in content
        assert "'PREFIXED_TEXT': 'x__QS_ENV__:NOT_A_MARKER'" in content
        assert "import os" not in content

    def test_rendering_never_reads_the_environment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Rendering emits the environment read; it never performs one."""

        class _RaisingEnviron(dict):
            def get(self, key: str, default: object = None) -> object:
                raise AssertionError(f"renderer read environment key {key!r}")

        monkeypatch.setattr(os, "environ", _RaisingEnviron())
        specs = {
            "storage": ModuleWiringSpec(
                settings={"AWS_SECRET_ACCESS_KEY": "__QS_ENV__:FIXTURE_SECRET"}
            )
        }

        content = render_settings_modules_py(specs)

        assert 'os.environ.get("FIXTURE_SECRET", "")' in content

    def test_written_file_never_carries_the_secret_value(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The persisted managed file holds the name, never the secret value."""
        monkeypatch.setenv("FIXTURE_SECRET", "super-secret-value")
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()

        specs = {
            "storage": ModuleWiringSpec(
                settings={"AWS_SECRET_ACCESS_KEY": "__QS_ENV__:FIXTURE_SECRET"}
            )
        }
        write_managed_wiring(package_dir, specs)

        written = (package_dir / "settings" / "modules.py").read_text()
        assert "super-secret-value" not in written
        assert 'os.environ.get("FIXTURE_SECRET", "")' in written


class TestRenderUrlsModulesPy:
    """Tests for render_urls_modules_py."""

    def test_render_urls_modules_py_empty_produces_empty_list(self) -> None:
        """No URL specs renders empty pre-home and post-home lists."""
        content = render_urls_modules_py({})
        assert "PRE_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []" in content
        assert "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []" in content
        assert "SPA_MODULE_URLPATTERNS: list[ManagedURLPattern] = []" in content
        assert "from django.urls import URLPattern, URLResolver" in content
        assert (
            "urlpatterns: list[ManagedURLPattern] = compose_managed_urlpatterns("
            in content
        )

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
        assert "from .views import orgs_react_shell_view, react_shell_view" in content
        assert "re_path" in content
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

    def test_render_urls_modules_py_empty_matches_generator_stub(self) -> None:
        """The generator's stub and the empty apply rendering are byte-identical.

        The generated ``urls_modules.py`` stub must already be the managed
        URLconf shape, or a project's first ``apply`` would rewrite it for no
        reason.  The template carries no Jinja variables, so its file content
        is the rendered stub.
        """
        stub_path = (
            Path(__file__).resolve().parents[1]
            / "src"
            / "quickscale_core"
            / "generator"
            / "templates"
            / "project_name"
            / "urls_modules.py.j2"
        )
        assert stub_path.read_text() == render_urls_modules_py({})


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


def test_generated_urls_template_includes_the_managed_urlconf() -> None:
    """The user-owned urls.py holds one include of the managed URLconf.

    URL inclusion flows through ``<package>/urls_modules.py`` (regenerated by
    apply) and ``quickscale_core.runtime.urls`` only: the generated
    ``urls.py`` keeps its own fixed routes, one ``include()`` line, and the
    SPA catch-all, and names no module and no module route (rule 41).
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

    assert 'path("", include("{{ package_name }}.urls_modules")),' in content
    assert 're_path(r".*", react_shell_view)' in content
    # The retired bucket imports and appends are gone.
    for retired in (
        "PRE_HOME_MODULE_URLPATTERNS",
        "POST_HOME_MODULE_URLPATTERNS",
        "SPA_MODULE_URLPATTERNS",
        "MODULE_URLPATTERNS",
        "react_shell_urlpatterns",
    ):
        assert retired not in content
    # Rule 41: no module surface literal remains in the user-owned template.
    assert r"^crm/?$" not in content
    assert 'name="crm-shell"' not in content
    assert r"^(profile|blog|listings|settings)/?$" not in content
    assert r"^blog/?$" not in content
    assert r"^listings/?$" not in content
    assert r"^orgs" not in content
    assert r"^forms" not in content
    assert r"^social" not in content
    assert "orgs_react_shell_view" not in content


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
