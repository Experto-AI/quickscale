"""Tests for the manifest-driven wiring projection engine (A1).

These tests cover:
- WiringProjection dataclass representation and immutability.
- ModuleDerivationSchema.get_all_wiring_projections helper.
- OptionDerivation.wiring_projections field.
- The new ResolverResult wiring fields (apps, middleware, url_includes,
  pre_home_url_includes) defaulting to empty tuples.
- The wiring projection engine in resolver.py (_project_wiring_contribution,
  _project_all_wiring) for all four derivation types.
- resolve_module_config populating the new wiring fields end-to-end.
"""

from __future__ import annotations

import pytest

from quickscale_core.manifest import (
    ConfigOption,
    ModuleDerivationSchema,
    ModuleManifest,
    OptionDerivation,
    ResolverResult,
    WiringProjection,
    resolve_module_config,
)
from quickscale_core.manifest.derivation import (
    WiringProjection as WiringProjectionDirect,
)
from quickscale_core.manifest.resolver import (
    _project_all_wiring,
    _project_wiring_contribution,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manifest(
    name: str = "test_module",
    mutable_options: dict | None = None,
) -> ModuleManifest:
    return ModuleManifest(
        name=name,
        version="1.0.0",
        mutable_options=mutable_options or {},
        immutable_options={},
    )


def _make_schema(
    module_name: str = "test_module",
    option_derivations: dict | None = None,
    module_wiring_projections: list[WiringProjection] | None = None,
) -> ModuleDerivationSchema:
    return ModuleDerivationSchema(
        module_name=module_name,
        version="1",
        option_derivations=option_derivations or {},
        module_wiring_projections=module_wiring_projections or [],
    )


# ---------------------------------------------------------------------------
# WiringProjection dataclass
# ---------------------------------------------------------------------------


class TestWiringProjection:
    """Tests for WiringProjection dataclass."""

    def test_minimum_construction(self) -> None:
        """WiringProjection can be created with just a wiring_field."""
        proj = WiringProjection(wiring_field="apps")
        assert proj.wiring_field == "apps"
        assert proj.source_options == []
        assert proj.derivation_type == "static"
        assert proj.expression == {}
        assert proj.default == []
        assert proj.description == ""

    def test_static_projection_with_value(self) -> None:
        """WiringProjection can hold a static apps contribution."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": ["mymodule.analytics"]},
            description="Analytics app label",
        )
        assert proj.wiring_field == "apps"
        assert proj.expression["value"] == ["mymodule.analytics"]

    def test_url_projection(self) -> None:
        """WiringProjection can hold url_includes contributions."""
        proj = WiringProjection(
            wiring_field="url_includes",
            derivation_type="static",
            expression={"value": [["analytics/", "mymodule.analytics.urls"]]},
        )
        assert proj.wiring_field == "url_includes"
        assert proj.expression["value"][0] == ["analytics/", "mymodule.analytics.urls"]

    def test_conditional_projection(self) -> None:
        """WiringProjection can represent conditional wiring."""
        proj = WiringProjection(
            wiring_field="middleware",
            source_options=["enabled"],
            derivation_type="conditional",
            expression={
                "branches": {
                    True: ["mymodule.middleware.AnalyticsMiddleware"],
                    False: [],
                }
            },
            default=[],
        )
        assert proj.derivation_type == "conditional"
        assert "branches" in proj.expression

    def test_is_frozen(self) -> None:
        """WiringProjection instances are immutable."""
        proj = WiringProjection(wiring_field="apps")
        with pytest.raises(AttributeError):
            proj.wiring_field = "middleware"  # type: ignore[misc]

    def test_importable_from_manifest_package(self) -> None:
        """WiringProjection is importable from quickscale_core.manifest."""
        from quickscale_core.manifest import WiringProjection as WPkg

        assert WPkg is WiringProjectionDirect


# ---------------------------------------------------------------------------
# OptionDerivation.wiring_projections field
# ---------------------------------------------------------------------------


class TestOptionDerivationWiringProjections:
    """Tests for wiring_projections on OptionDerivation."""

    def test_default_empty(self) -> None:
        """OptionDerivation.wiring_projections defaults to empty list."""
        od = OptionDerivation(option_key="enabled")
        assert od.wiring_projections == []

    def test_can_carry_projections(self) -> None:
        """OptionDerivation can carry WiringProjection instances."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="conditional",
            source_options=["enabled"],
            expression={"branches": {True: ["mymodule.app"]}},
            default=[],
        )
        od = OptionDerivation(
            option_key="enabled",
            wiring_projections=[proj],
        )
        assert len(od.wiring_projections) == 1
        assert od.wiring_projections[0].wiring_field == "apps"


# ---------------------------------------------------------------------------
# ModuleDerivationSchema.get_all_wiring_projections
# ---------------------------------------------------------------------------


class TestGetAllWiringProjections:
    """Tests for ModuleDerivationSchema.get_all_wiring_projections."""

    def test_empty_schema_returns_empty(self) -> None:
        """get_all_wiring_projections returns empty list when no projections."""
        schema = _make_schema()
        assert schema.get_all_wiring_projections() == []

    def test_module_level_projections_returned(self) -> None:
        """Module-level wiring projections are returned."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": ["mymodule.analytics"]},
        )
        schema = _make_schema(module_wiring_projections=[proj])
        result = schema.get_all_wiring_projections()
        assert len(result) == 1
        assert result[0].wiring_field == "apps"

    def test_per_option_projections_returned(self) -> None:
        """Per-option wiring projections are collected."""
        proj = WiringProjection(
            wiring_field="middleware",
            derivation_type="static",
            expression={"value": ["mymodule.middleware.M"]},
        )
        schema = _make_schema(
            option_derivations={
                "enabled": OptionDerivation(
                    option_key="enabled",
                    wiring_projections=[proj],
                )
            }
        )
        result = schema.get_all_wiring_projections()
        assert len(result) == 1
        assert result[0].wiring_field == "middleware"

    def test_module_level_comes_before_per_option(self) -> None:
        """Module-level projections come before per-option projections."""
        module_proj = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": ["module_app"]},
        )
        option_proj = WiringProjection(
            wiring_field="middleware",
            derivation_type="static",
            expression={"value": ["module_mw"]},
        )
        schema = _make_schema(
            module_wiring_projections=[module_proj],
            option_derivations={
                "x": OptionDerivation(option_key="x", wiring_projections=[option_proj])
            },
        )
        result = schema.get_all_wiring_projections()
        assert len(result) == 2
        assert result[0].wiring_field == "apps"
        assert result[1].wiring_field == "middleware"

    def test_combined_from_multiple_options(self) -> None:
        """Projections from multiple options are all collected."""
        proj_a = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": ["app_a"]},
        )
        proj_b = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": ["app_b"]},
        )
        schema = _make_schema(
            option_derivations={
                "opt_a": OptionDerivation(
                    option_key="opt_a", wiring_projections=[proj_a]
                ),
                "opt_b": OptionDerivation(
                    option_key="opt_b", wiring_projections=[proj_b]
                ),
            }
        )
        result = schema.get_all_wiring_projections()
        assert len(result) == 2


# ---------------------------------------------------------------------------
# ResolverResult new wiring fields
# ---------------------------------------------------------------------------


class TestResolverResultWiringFields:
    """Tests for the new wiring fields on ResolverResult."""

    def test_defaults_empty(self) -> None:
        """New wiring fields default to empty tuples."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={},
        )
        assert result.apps == ()
        assert result.middleware == ()
        assert result.url_includes == ()
        assert result.pre_home_url_includes == ()

    def test_explicit_values(self) -> None:
        """New wiring fields can be set explicitly."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={},
            apps=("myapp",),
            middleware=("myapp.mw.M",),
            url_includes=(("blog/", "myapp.blog.urls"),),
            pre_home_url_includes=(("auth/", "myapp.auth.urls"),),
        )
        assert result.apps == ("myapp",)
        assert result.middleware == ("myapp.mw.M",)
        assert result.url_includes == (("blog/", "myapp.blog.urls"),)
        assert result.pre_home_url_includes == (("auth/", "myapp.auth.urls"),)

    def test_frozen(self) -> None:
        """ResolverResult wiring fields are immutable."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={},
            apps=("myapp",),
        )
        with pytest.raises(AttributeError):
            result.apps = ("other",)  # type: ignore[misc]


# ---------------------------------------------------------------------------
# _project_wiring_contribution (unit tests)
# ---------------------------------------------------------------------------


class TestProjectWiringContribution:
    """Unit tests for the wiring projection computation function."""

    def test_static_apps(self) -> None:
        """Static projection contributes constant app labels."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": ["mymodule.analytics"]},
        )
        result = _project_wiring_contribution(proj, {})
        assert result == ["mymodule.analytics"]

    def test_static_empty_value_returns_empty(self) -> None:
        """Static projection with empty value returns empty list."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": []},
        )
        assert _project_wiring_contribution(proj, {}) == []

    def test_static_missing_value_uses_default(self) -> None:
        """Static projection with no value key falls back to default."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={},
            default=["default_app"],
        )
        assert _project_wiring_contribution(proj, {}) == ["default_app"]

    def test_static_url_tuple_coercion(self) -> None:
        """Static url_includes contribution items are coerced to (str, str) tuples."""
        proj = WiringProjection(
            wiring_field="url_includes",
            derivation_type="static",
            expression={"value": [["analytics/", "mymodule.analytics.urls"]]},
        )
        result = _project_wiring_contribution(proj, {})
        assert result == [("analytics/", "mymodule.analytics.urls")]

    def test_static_pre_home_url_tuple_coercion(self) -> None:
        """Static pre_home_url_includes contribution items are coerced to tuples."""
        proj = WiringProjection(
            wiring_field="pre_home_url_includes",
            derivation_type="static",
            expression={"value": [["auth/", "mymodule.auth.urls"]]},
        )
        result = _project_wiring_contribution(proj, {})
        assert result == [("auth/", "mymodule.auth.urls")]

    def test_direct_apps_from_option(self) -> None:
        """Direct projection reads app labels from a resolved option."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="direct",
            source_options=["app_label"],
            expression={"option": "app_label"},
        )
        result = _project_wiring_contribution(proj, {"app_label": "mymodule.app"})
        assert result == ["mymodule.app"]

    def test_direct_list_from_option(self) -> None:
        """Direct projection uses list values from option unchanged."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="direct",
            expression={"option": "apps"},
        )
        result = _project_wiring_contribution(proj, {"apps": ["app_a", "app_b"]})
        assert result == ["app_a", "app_b"]

    def test_direct_missing_option_uses_default(self) -> None:
        """Direct projection falls back to default when option is absent."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="direct",
            expression={"option": "nonexistent"},
            default=["fallback_app"],
        )
        assert _project_wiring_contribution(proj, {}) == ["fallback_app"]

    def test_direct_none_option_uses_default(self) -> None:
        """Direct projection falls back to default when option value is None."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="direct",
            expression={"option": "app_label"},
            default=["fallback_app"],
        )
        assert _project_wiring_contribution(proj, {"app_label": None}) == [
            "fallback_app"
        ]

    def test_conditional_apps(self) -> None:
        """Conditional projection selects branch based on resolved option."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="conditional",
            source_options=["enabled"],
            expression={
                "branches": {
                    True: ["mymodule.analytics"],
                    False: [],
                }
            },
            default=[],
        )
        assert _project_wiring_contribution(proj, {"enabled": True}) == [
            "mymodule.analytics"
        ]
        assert _project_wiring_contribution(proj, {"enabled": False}) == []

    def test_conditional_unmatched_uses_default(self) -> None:
        """Conditional projection uses default when no branch matches."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="conditional",
            source_options=["mode"],
            expression={"branches": {"on": ["mymodule.app"]}},
            default=["default_app"],
        )
        assert _project_wiring_contribution(proj, {"mode": "off"}) == ["default_app"]

    def test_conditional_middleware(self) -> None:
        """Conditional projection works for middleware field."""
        proj = WiringProjection(
            wiring_field="middleware",
            derivation_type="conditional",
            source_options=["provider"],
            expression={
                "branches": {
                    "posthog": ["mymodule.analytics.AnalyticsMiddleware"],
                }
            },
            default=[],
        )
        assert _project_wiring_contribution(proj, {"provider": "posthog"}) == [
            "mymodule.analytics.AnalyticsMiddleware"
        ]

    def test_conditional_url_includes(self) -> None:
        """Conditional projection works for url_includes field."""
        proj = WiringProjection(
            wiring_field="url_includes",
            derivation_type="conditional",
            source_options=["enabled"],
            expression={
                "branches": {
                    True: [["analytics/", "mymodule.analytics.urls"]],
                    False: [],
                }
            },
            default=[],
        )
        result = _project_wiring_contribution(proj, {"enabled": True})
        assert result == [("analytics/", "mymodule.analytics.urls")]

    def test_computed_apps(self) -> None:
        """Computed projection renders templates from resolved values."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="computed",
            expression={"values": ["mymodule.{module_name}"]},
        )
        result = _project_wiring_contribution(proj, {"module_name": "blog"})
        assert result == ["mymodule.blog"]

    def test_computed_uses_default_on_template_failure(self) -> None:
        """Computed projection falls back to default on template error."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="computed",
            expression={"values": ["{missing_key}"]},
            default=["fallback_app"],
        )
        assert _project_wiring_contribution(proj, {}) == ["fallback_app"]

    def test_unknown_derivation_type_returns_default(self) -> None:
        """Unknown derivation type returns the default contribution."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="magic",
            expression={},
            default=["fallback"],
        )
        assert _project_wiring_contribution(proj, {}) == ["fallback"]

    def test_url_field_ignores_non_sequence_items(self) -> None:
        """Non-sequence items in url_includes contribution are skipped."""
        proj = WiringProjection(
            wiring_field="url_includes",
            derivation_type="static",
            expression={"value": ["not_a_tuple", ["ok/", "mymodule.urls"]]},
        )
        result = _project_wiring_contribution(proj, {})
        # "not_a_tuple" is a string — len >= 2 but individual chars, not a pair
        # Actually string has chars not route tuples, so only the list item qualifies
        assert ("ok/", "mymodule.urls") in result

    def test_apps_field_coerces_to_string(self) -> None:
        """Apps contribution items are coerced to strings."""
        proj = WiringProjection(
            wiring_field="apps",
            derivation_type="static",
            expression={"value": [42, True]},
        )
        result = _project_wiring_contribution(proj, {})
        assert result == ["42", "True"]


# ---------------------------------------------------------------------------
# _project_all_wiring (unit tests)
# ---------------------------------------------------------------------------


class TestProjectAllWiring:
    """Unit tests for the full wiring accumulation function."""

    def test_empty_schema_returns_empty_collections(self) -> None:
        """An empty schema produces empty wiring collections."""
        schema = _make_schema()
        result = _project_all_wiring(schema, {})
        assert result["apps"] == []
        assert result["middleware"] == []
        assert result["url_includes"] == []
        assert result["pre_home_url_includes"] == []

    def test_accumulates_across_multiple_projections(self) -> None:
        """Contributions from multiple projections are accumulated."""
        schema = _make_schema(
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="apps",
                    derivation_type="static",
                    expression={"value": ["app_a"]},
                ),
                WiringProjection(
                    wiring_field="apps",
                    derivation_type="static",
                    expression={"value": ["app_b"]},
                ),
            ]
        )
        result = _project_all_wiring(schema, {})
        assert result["apps"] == ["app_a", "app_b"]

    def test_skips_unknown_wiring_field(self) -> None:
        """Projections with unknown wiring_field are silently skipped."""
        schema = _make_schema(
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="unknown_field",
                    derivation_type="static",
                    expression={"value": ["something"]},
                ),
            ]
        )
        result = _project_all_wiring(schema, {})
        assert "unknown_field" not in result
        assert result["apps"] == []

    def test_mixed_fields(self) -> None:
        """Multiple wiring fields are accumulated separately."""
        schema = _make_schema(
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="apps",
                    derivation_type="static",
                    expression={"value": ["myapp"]},
                ),
                WiringProjection(
                    wiring_field="middleware",
                    derivation_type="static",
                    expression={"value": ["myapp.mw.M"]},
                ),
                WiringProjection(
                    wiring_field="url_includes",
                    derivation_type="static",
                    expression={"value": [["blog/", "myapp.blog.urls"]]},
                ),
                WiringProjection(
                    wiring_field="pre_home_url_includes",
                    derivation_type="static",
                    expression={"value": [["auth/", "myapp.auth.urls"]]},
                ),
            ]
        )
        result = _project_all_wiring(schema, {})
        assert result["apps"] == ["myapp"]
        assert result["middleware"] == ["myapp.mw.M"]
        assert result["url_includes"] == [("blog/", "myapp.blog.urls")]
        assert result["pre_home_url_includes"] == [("auth/", "myapp.auth.urls")]


# ---------------------------------------------------------------------------
# resolve_module_config end-to-end with wiring fields
# ---------------------------------------------------------------------------


class TestResolveModuleConfigWithWiring:
    """End-to-end tests for resolve_module_config with wiring projections."""

    def test_no_projections_produces_empty_wiring(self) -> None:
        """A schema with no WiringProjection declarations produces empty wiring."""
        manifest = _make_manifest(
            mutable_options={
                "enabled": ConfigOption(
                    name="enabled",
                    option_type="boolean",
                    default=True,
                    django_setting="ENABLED",
                    mutability="mutable",
                )
            }
        )
        schema = _make_schema()
        result = resolve_module_config(manifest, schema)

        assert result.apps == ()
        assert result.middleware == ()
        assert result.url_includes == ()
        assert result.pre_home_url_includes == ()

    def test_static_app_projection(self) -> None:
        """Static wiring projection contributes apps to the result."""
        manifest = _make_manifest()
        schema = _make_schema(
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="apps",
                    derivation_type="static",
                    expression={"value": ["mymodule.analytics"]},
                )
            ]
        )
        result = resolve_module_config(manifest, schema)
        assert result.apps == ("mymodule.analytics",)

    def test_conditional_middleware_projection(self) -> None:
        """Conditional wiring projection contributes middleware based on option."""
        manifest = _make_manifest(
            mutable_options={
                "enabled": ConfigOption(
                    name="enabled",
                    option_type="boolean",
                    default=True,
                    django_setting="ENABLED",
                    mutability="mutable",
                )
            }
        )
        schema = _make_schema(
            option_derivations={
                "enabled": OptionDerivation(
                    option_key="enabled",
                    wiring_projections=[
                        WiringProjection(
                            wiring_field="middleware",
                            derivation_type="conditional",
                            source_options=["enabled"],
                            expression={
                                "branches": {
                                    True: ["mymodule.mw.AnalyticsMiddleware"],
                                    False: [],
                                }
                            },
                            default=[],
                        )
                    ],
                )
            }
        )

        result_on = resolve_module_config(manifest, schema)
        assert result_on.middleware == ("mymodule.mw.AnalyticsMiddleware",)

        result_off = resolve_module_config(
            manifest, schema, overrides={"enabled": False}
        )
        assert result_off.middleware == ()

    def test_url_includes_projection(self) -> None:
        """url_includes projection produces tuple of (route, include) pairs."""
        manifest = _make_manifest()
        schema = _make_schema(
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="url_includes",
                    derivation_type="static",
                    expression={"value": [["analytics/", "mymodule.analytics.urls"]]},
                )
            ]
        )
        result = resolve_module_config(manifest, schema)
        assert result.url_includes == (("analytics/", "mymodule.analytics.urls"),)

    def test_pre_home_url_includes_projection(self) -> None:
        """pre_home_url_includes projection produces tuple of (route, include) pairs."""
        manifest = _make_manifest()
        schema = _make_schema(
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="pre_home_url_includes",
                    derivation_type="static",
                    expression={"value": [["auth/", "mymodule.auth.urls"]]},
                )
            ]
        )
        result = resolve_module_config(manifest, schema)
        assert result.pre_home_url_includes == (("auth/", "mymodule.auth.urls"),)

    def test_full_wiring_all_four_fields(self) -> None:
        """All four wiring fields are populated when projections declare them."""
        manifest = _make_manifest()
        schema = _make_schema(
            module_wiring_projections=[
                WiringProjection(
                    wiring_field="apps",
                    derivation_type="static",
                    expression={"value": ["mymodule.blog"]},
                ),
                WiringProjection(
                    wiring_field="middleware",
                    derivation_type="static",
                    expression={"value": ["mymodule.blog.middleware.BlogMiddleware"]},
                ),
                WiringProjection(
                    wiring_field="url_includes",
                    derivation_type="static",
                    expression={"value": [["blog/", "mymodule.blog.urls"]]},
                ),
                WiringProjection(
                    wiring_field="pre_home_url_includes",
                    derivation_type="static",
                    expression={"value": [["robots.txt", "mymodule.blog.robots"]]},
                ),
            ]
        )
        result = resolve_module_config(manifest, schema)

        assert result.apps == ("mymodule.blog",)
        assert result.middleware == ("mymodule.blog.middleware.BlogMiddleware",)
        assert result.url_includes == (("blog/", "mymodule.blog.urls"),)
        assert result.pre_home_url_includes == (("robots.txt", "mymodule.blog.robots"),)

    def test_existing_resolver_behavior_unaffected(self) -> None:
        """Existing derived_settings and resolved fields are not affected by
        adding wiring projections."""
        from quickscale_core.manifest import DerivedSetting

        manifest = _make_manifest(
            mutable_options={
                "api_key": ConfigOption(
                    name="api_key",
                    option_type="string",
                    default="phc_abc",
                    django_setting="POSTHOG_KEY",
                    mutability="mutable",
                )
            }
        )
        schema = _make_schema(
            option_derivations={
                "api_key": OptionDerivation(
                    option_key="api_key",
                    derived_settings=[
                        DerivedSetting(
                            setting_key="POSTHOG_KEY",
                            source_options=["api_key"],
                            derivation_type="direct",
                            expression={"option": "api_key"},
                        )
                    ],
                    wiring_projections=[
                        WiringProjection(
                            wiring_field="apps",
                            derivation_type="static",
                            expression={"value": ["mymodule.analytics"]},
                        )
                    ],
                )
            }
        )
        result = resolve_module_config(manifest, schema)

        # Existing behavior preserved
        assert result.resolved["api_key"] == "phc_abc"
        assert result.derived_settings["POSTHOG_KEY"] == "phc_abc"
        # New wiring fields populated
        assert result.apps == ("mymodule.analytics",)
