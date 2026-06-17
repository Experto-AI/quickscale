"""Tests for the manifest-to-ModuleWiringSpec assembler (A2).

These tests cover:
- assemble_wiring_spec: basic assembly from ResolverResult.
- assemble_wiring_spec: post_hook seam (receives correct args, can augment).
- PostResolutionHook: type alias importable from the package.
- Frozen ModuleWiringSpec is returned.
- managed_files defaults to empty (A4 deferred).
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.manifest import (
    PostResolutionHook,
    ResolverResult,
    assemble_wiring_spec,
)
from quickscale_core.manifest.assembler import (
    PostResolutionHook as PostResolutionHookDirect,
    assemble_wiring_spec as assemble_wiring_spec_direct,
)
from quickscale_core.module_wiring import ModuleWiringSpec


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    module_name: str = "test",
    resolved: dict[str, Any] | None = None,
    derived_settings: dict[str, Any] | None = None,
    apps: tuple[str, ...] = (),
    middleware: tuple[str, ...] = (),
    url_includes: tuple[tuple[str, str], ...] = (),
    pre_home_url_includes: tuple[tuple[str, str], ...] = (),
) -> ResolverResult:
    return ResolverResult(
        module_name=module_name,
        defaults={},
        resolved=resolved or {},
        derived_settings=derived_settings or {},
        apps=apps,
        middleware=middleware,
        url_includes=url_includes,
        pre_home_url_includes=pre_home_url_includes,
    )


# ---------------------------------------------------------------------------
# Basic assembly
# ---------------------------------------------------------------------------


class TestAssembleWiringSpec:
    """Tests for assemble_wiring_spec assembly from a ResolverResult."""

    def test_returns_module_wiring_spec(self) -> None:
        """assemble_wiring_spec returns a ModuleWiringSpec instance."""
        result = _make_result()
        spec = assemble_wiring_spec(result)
        assert isinstance(spec, ModuleWiringSpec)

    def test_spec_is_frozen(self) -> None:
        """The returned ModuleWiringSpec is frozen (immutable)."""
        result = _make_result(apps=("myapp",))
        spec = assemble_wiring_spec(result)
        with pytest.raises(AttributeError):
            spec.apps = ("other",)  # type: ignore[misc]

    def test_apps_copied_from_result(self) -> None:
        """Apps field is copied from the resolver result."""
        result = _make_result(apps=("mymodule.analytics",))
        spec = assemble_wiring_spec(result)
        assert spec.apps == ("mymodule.analytics",)

    def test_middleware_copied_from_result(self) -> None:
        """Middleware field is copied from the resolver result."""
        result = _make_result(middleware=("mymodule.mw.M",))
        spec = assemble_wiring_spec(result)
        assert spec.middleware == ("mymodule.mw.M",)

    def test_settings_from_derived_settings(self) -> None:
        """Settings are populated from derived_settings in the resolver result."""
        result = _make_result(
            derived_settings={
                "QUICKSCALE_ANALYTICS_ENABLED": True,
                "QUICKSCALE_ANALYTICS_PROVIDER": "posthog",
            }
        )
        spec = assemble_wiring_spec(result)
        assert spec.settings == {
            "QUICKSCALE_ANALYTICS_ENABLED": True,
            "QUICKSCALE_ANALYTICS_PROVIDER": "posthog",
        }

    def test_url_includes_copied_from_result(self) -> None:
        """url_includes field is copied from the resolver result."""
        result = _make_result(url_includes=(("analytics/", "mymodule.analytics.urls"),))
        spec = assemble_wiring_spec(result)
        assert spec.url_includes == (("analytics/", "mymodule.analytics.urls"),)

    def test_pre_home_url_includes_copied_from_result(self) -> None:
        """pre_home_url_includes field is copied from the resolver result."""
        result = _make_result(pre_home_url_includes=(("auth/", "mymodule.auth.urls"),))
        spec = assemble_wiring_spec(result)
        assert spec.pre_home_url_includes == (("auth/", "mymodule.auth.urls"),)

    def test_managed_files_empty_by_default(self) -> None:
        """managed_files is empty (A4 codegen deferred)."""
        result = _make_result()
        spec = assemble_wiring_spec(result)
        assert spec.managed_files == {}

    def test_all_empty_result_produces_empty_spec(self) -> None:
        """An empty resolver result produces an empty ModuleWiringSpec."""
        result = _make_result()
        spec = assemble_wiring_spec(result)
        assert spec.apps == ()
        assert spec.middleware == ()
        assert spec.settings == {}
        assert spec.url_includes == ()
        assert spec.pre_home_url_includes == ()
        assert spec.managed_files == {}

    def test_all_fields_populated(self) -> None:
        """All wiring fields are correctly populated from a full resolver result."""
        result = _make_result(
            derived_settings={"SETTING_A": "value_a"},
            apps=("myapp",),
            middleware=("myapp.mw.M",),
            url_includes=(("blog/", "myapp.blog.urls"),),
            pre_home_url_includes=(("robots.txt", "myapp.robots"),),
        )
        spec = assemble_wiring_spec(result)
        assert spec.apps == ("myapp",)
        assert spec.middleware == ("myapp.mw.M",)
        assert spec.settings == {"SETTING_A": "value_a"}
        assert spec.url_includes == (("blog/", "myapp.blog.urls"),)
        assert spec.pre_home_url_includes == (("robots.txt", "myapp.robots"),)
        assert spec.managed_files == {}


# ---------------------------------------------------------------------------
# Post-resolution hook seam
# ---------------------------------------------------------------------------


class TestPostResolutionHook:
    """Tests for the per-adapter post-resolution hook seam."""

    def test_no_hook_returns_assembled_spec_unchanged(self) -> None:
        """Without a hook the assembled spec is returned directly."""
        result = _make_result(apps=("myapp",))
        spec = assemble_wiring_spec(result)
        assert spec.apps == ("myapp",)

    def test_hook_is_called_with_spec_and_resolved(self) -> None:
        """The post_hook receives the assembled spec and resolved options."""
        captured: list[Any] = []

        def hook(spec: ModuleWiringSpec, resolved: dict[str, Any]) -> ModuleWiringSpec:
            captured.append(("spec", spec))
            captured.append(("resolved", resolved))
            return spec

        result = _make_result(
            resolved={"key": "val"},
            apps=("myapp",),
        )
        spec = assemble_wiring_spec(result, post_hook=hook)

        assert len(captured) == 2
        assert captured[0] == ("spec", spec)
        assert captured[1][0] == "resolved"
        assert captured[1][1] == {"key": "val"}

    def test_hook_can_augment_spec(self) -> None:
        """The post_hook can return a modified ModuleWiringSpec."""

        def hook(spec: ModuleWiringSpec, resolved: dict[str, Any]) -> ModuleWiringSpec:
            return ModuleWiringSpec(
                apps=spec.apps + ("extra_app",),
                middleware=spec.middleware,
                settings=dict(spec.settings),
                url_includes=spec.url_includes,
                pre_home_url_includes=spec.pre_home_url_includes,
                managed_files={},
            )

        result = _make_result(apps=("myapp",))
        spec = assemble_wiring_spec(result, post_hook=hook)
        assert spec.apps == ("myapp", "extra_app")

    def test_hook_receives_copy_of_resolved(self) -> None:
        """The hook receives a copy — mutations do not propagate back to result."""
        mutations: list[dict] = []

        def hook(spec: ModuleWiringSpec, resolved: dict[str, Any]) -> ModuleWiringSpec:
            resolved["injected_key"] = "injected_value"
            mutations.append(resolved)
            return spec

        result = _make_result(resolved={"orig": "val"})
        assemble_wiring_spec(result, post_hook=hook)

        # The hook mutated its copy but the original result is unchanged.
        assert "injected_key" not in result.resolved
        assert mutations[0]["orig"] == "val"
        assert mutations[0]["injected_key"] == "injected_value"

    def test_hook_returning_original_spec(self) -> None:
        """A hook that returns the spec unchanged is a no-op."""
        result = _make_result(derived_settings={"KEY": "val"})

        def noop_hook(
            spec: ModuleWiringSpec, resolved: dict[str, Any]
        ) -> ModuleWiringSpec:
            return spec

        spec = assemble_wiring_spec(result, post_hook=noop_hook)
        assert spec.settings == {"KEY": "val"}

    def test_hook_can_override_middleware(self) -> None:
        """Hook can replace the middleware tuple (gnarly case pattern)."""

        def middleware_hook(
            spec: ModuleWiringSpec, resolved: dict[str, Any]
        ) -> ModuleWiringSpec:
            # Only add CorsMiddleware when cors is enabled
            if resolved.get("cors_enabled"):
                return ModuleWiringSpec(
                    apps=spec.apps,
                    middleware=spec.middleware
                    + ("django.middleware.common.CorsMiddleware",),
                    settings=dict(spec.settings),
                    url_includes=spec.url_includes,
                    pre_home_url_includes=spec.pre_home_url_includes,
                    managed_files={},
                )
            return spec

        result_no_cors = _make_result(resolved={"cors_enabled": False})
        spec_no_cors = assemble_wiring_spec(result_no_cors, post_hook=middleware_hook)
        assert "django.middleware.common.CorsMiddleware" not in spec_no_cors.middleware

        result_cors = _make_result(resolved={"cors_enabled": True})
        spec_cors = assemble_wiring_spec(result_cors, post_hook=middleware_hook)
        assert "django.middleware.common.CorsMiddleware" in spec_cors.middleware


# ---------------------------------------------------------------------------
# Public exports
# ---------------------------------------------------------------------------


class TestPublicExports:
    """Verify assembler types are importable from quickscale_core.manifest."""

    def test_assemble_wiring_spec_importable(self) -> None:
        """assemble_wiring_spec is exported from quickscale_core.manifest."""
        assert assemble_wiring_spec is assemble_wiring_spec_direct

    def test_post_resolution_hook_importable(self) -> None:
        """PostResolutionHook is exported from quickscale_core.manifest."""
        assert PostResolutionHook is PostResolutionHookDirect
