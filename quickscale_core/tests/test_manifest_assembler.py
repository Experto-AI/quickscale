"""Tests for the manifest-to-ModuleWiringSpec assembler (A2).

These tests cover:
- assemble_wiring_spec: basic assembly from ResolverResult.
- assemble_wiring_spec: post_hook seam (receives correct args, can augment).
- PostResolutionHook: type alias importable from the package.
- Frozen ModuleWiringSpec is returned.
- managed_files populated from resolver result declarations (Phase 1.3).
"""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.manifest import (
    ManifestError,
    PostResolutionHook,
    ResolverResult,
    assemble_wiring_spec,
)
from quickscale_core.manifest.assembler import (
    PostResolutionHook as PostResolutionHookDirect,
    assemble_wiring_spec as assemble_wiring_spec_direct,
)
from quickscale_core.manifest.schema import ManagedFileDeclaration
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
    managed_files: tuple[ManagedFileDeclaration, ...] = (),
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
        managed_files=managed_files,
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
# Managed files emission (Phase 1.3)
# ---------------------------------------------------------------------------


class TestAssembleManagedFiles:
    """Tests for managed_files population from ResolverResult declarations."""

    def test_empty_declarations_produce_empty_managed_files(self) -> None:
        """No managed_files declarations -> empty managed_files dict."""
        result = _make_result()
        spec = assemble_wiring_spec(result)
        assert spec.managed_files == {}

    def test_single_declaration_emitted(self) -> None:
        """A single managed_files declaration is emitted as output_path -> renderer."""
        decl = ManagedFileDeclaration(
            key="social_link_tree",
            renderer="social/link_tree.html",
            output_path="quickscale_managed/social/link_tree.html",
        )
        result = _make_result(managed_files=(decl,))
        spec = assemble_wiring_spec(result)
        assert spec.managed_files == {
            "quickscale_managed/social/link_tree.html": "social/link_tree.html",
        }

    def test_multiple_declarations_emitted(self) -> None:
        """Multiple declarations are all emitted."""
        decl1 = ManagedFileDeclaration(
            key="file_a",
            renderer="renderer_a",
            output_path="quickscale_managed/a.html",
        )
        decl2 = ManagedFileDeclaration(
            key="file_b",
            renderer="renderer_b",
            output_path="quickscale_managed/b.html",
        )
        result = _make_result(managed_files=(decl1, decl2))
        spec = assemble_wiring_spec(result)
        assert spec.managed_files == {
            "quickscale_managed/a.html": "renderer_a",
            "quickscale_managed/b.html": "renderer_b",
        }

    def test_invalid_path_silently_skipped(self) -> None:
        """Declarations with paths outside quickscale_managed/ are skipped.

        This is defense-in-depth; the loader already rejects such paths.
        """
        valid = ManagedFileDeclaration(
            key="valid",
            renderer="r",
            output_path="quickscale_managed/valid.html",
        )
        invalid = ManagedFileDeclaration(
            key="invalid",
            renderer="r",
            output_path="templates/escaped.html",
        )
        result = _make_result(managed_files=(valid, invalid))
        spec = assemble_wiring_spec(result)
        assert spec.managed_files == {
            "quickscale_managed/valid.html": "r",
        }
        assert "templates/escaped.html" not in spec.managed_files

    def test_managed_files_do_not_disturb_other_fields(self) -> None:
        """Emit managed_files without disturbing apps/middleware/settings/url."""
        decl = ManagedFileDeclaration(
            key="f",
            renderer="r",
            output_path="quickscale_managed/f.html",
        )
        result = _make_result(
            apps=("myapp",),
            middleware=("myapp.mw.M",),
            derived_settings={"SETTING_A": "value_a"},
            url_includes=(("blog/", "myapp.blog.urls"),),
            pre_home_url_includes=(("robots.txt", "myapp.robots"),),
            managed_files=(decl,),
        )
        spec = assemble_wiring_spec(result)
        # All other fields are populated normally
        assert spec.apps == ("myapp",)
        assert spec.middleware == ("myapp.mw.M",)
        assert spec.settings == {"SETTING_A": "value_a"}
        assert spec.url_includes == (("blog/", "myapp.blog.urls"),)
        assert spec.pre_home_url_includes == (("robots.txt", "myapp.robots"),)
        # And managed_files is also populated
        assert spec.managed_files == {"quickscale_managed/f.html": "r"}


# ---------------------------------------------------------------------------
# Validation issues enforcement (SA27)
# ---------------------------------------------------------------------------


class TestAssembleValidationIssues:
    """Tests for the SA27 validation_issues enforcement in assemble_wiring_spec."""

    def test_no_validation_issues_passes(self) -> None:
        """Empty validation_issues list assembles without error."""
        result = _make_result()
        spec = assemble_wiring_spec(result)
        assert isinstance(spec, ModuleWiringSpec)

    def test_single_validation_issue_raises_manifest_error(self) -> None:
        """A single validation issue raises ManifestError with the issue text."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={"key": "val"},
            validation_issues=["modules.test.key must be a positive integer"],
        )
        with pytest.raises(ManifestError) as exc_info:
            assemble_wiring_spec(result)
        assert "must be a positive integer" in str(exc_info.value)
        assert "test" in str(exc_info.value)

    def test_multiple_validation_issues_all_listed(self) -> None:
        """Multiple validation issues are all included in the error message."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={"key": "val"},
            validation_issues=[
                "modules.test.field_a is required",
                "modules.test.field_b must be a boolean",
            ],
        )
        with pytest.raises(ManifestError) as exc_info:
            assemble_wiring_spec(result)
        msg = str(exc_info.value)
        assert "field_a is required" in msg
        assert "field_b must be a boolean" in msg

    def test_validation_issues_with_post_hook_still_raises(self) -> None:
        """Validation issues are checked before the post_hook runs."""
        result = ResolverResult(
            module_name="test",
            defaults={},
            resolved={"key": "val"},
            validation_issues=["modules.test.key is invalid"],
        )

        def hook(spec: ModuleWiringSpec, resolved: dict[str, Any]) -> ModuleWiringSpec:
            msg = "hook should never be called"
            raise AssertionError(msg)

        with pytest.raises(ManifestError, match="key is invalid"):
            assemble_wiring_spec(result, post_hook=hook)

    def test_module_name_in_error_message(self) -> None:
        """The error message includes the module name."""
        result = ResolverResult(
            module_name="analytics",
            defaults={},
            resolved={},
            validation_issues=["modules.analytics.provider must be one of: posthog"],
        )
        with pytest.raises(ManifestError) as exc_info:
            assemble_wiring_spec(result)
        assert "analytics" in str(exc_info.value)


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
