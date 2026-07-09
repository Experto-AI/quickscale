"""Focused tests for the social manifest adapter.

Covers ``project_package`` validation, embed-provider filtering,
renderer-ID replacement, and the sentinel contract.
"""

from __future__ import annotations

from unittest.mock import MagicMock, PropertyMock, patch

import pytest

from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_social.adapter import (
    _social_manifest_adapter,
    get_manifest_adapter,
)


class TestGetManifestAdapter:
    """get_manifest_adapter sentinel contract."""

    def test_returns_callable(self) -> None:
        """get_manifest_adapter must return a callable."""
        adapter = get_manifest_adapter()
        assert callable(adapter)


class TestSocialManifestAdapterProjectPackage:
    """_social_manifest_adapter — project_package validation."""

    def test_raises_value_error_when_project_package_is_none(self) -> None:
        """A missing project_package must raise ValueError."""
        with pytest.raises(
            ValueError,
            match="project_package is required for managed social wiring",
        ):
            _social_manifest_adapter({}, project_package=None)

    def test_raises_value_error_when_project_package_is_omitted(self) -> None:
        """Omitting project_package entirely must also raise ValueError.

        The parameter defaults to None in the signature.
        """
        with pytest.raises(
            ValueError,
            match="project_package is required for managed social wiring",
        ):
            _social_manifest_adapter({})


class TestSocialManifestAdapterEmbedFiltering:
    """Embed-provider filtering from the provider allowlist."""

    @patch(
        "quickscale_modules_social.adapter.social_provider_supports_embeds",
        autospec=True,
    )
    @patch("quickscale_modules_social.adapter.assemble_wiring_spec")
    @patch("quickscale_modules_social.adapter.load_social_manifest")
    @patch("quickscale_modules_social.adapter.resolve_social_module_options")
    def test_filters_embed_providers(
        self,
        mock_resolve: MagicMock,
        mock_load: MagicMock,
        mock_assemble: MagicMock,
        mock_supports_embeds: MagicMock,
    ) -> None:
        """Only embed-supporting providers appear in the embed allowlist."""
        mock_resolve.return_value = {
            "provider_allowlist": ["youtube", "linkedin", "x"],
            "link_tree_enabled": True,
            "layout_variant": "list",
            "embeds_enabled": True,
            "cache_ttl_seconds": 300,
            "links_per_page": 24,
            "embeds_per_page": 12,
        }
        mock_load.return_value = MagicMock(
            managed_files=PropertyMock(return_value={}),
        )
        mock_assemble.return_value = ModuleWiringSpec()

        def supports_embeds_side_effect(provider: str) -> bool:
            return provider in ("youtube",)

        mock_supports_embeds.side_effect = supports_embeds_side_effect

        _social_manifest_adapter(
            {},
            project_package="myapp",
        )

        # — Retrieve the ResolverResult passed to assemble_wiring_spec —
        call_args, _ = mock_assemble.call_args
        resolver_result = call_args[0]

        assert resolver_result.derived_settings[
            "QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST"
        ] == ["youtube", "linkedin", "x"]
        assert resolver_result.derived_settings[
            "QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST"
        ] == ["youtube"]

    @patch(
        "quickscale_modules_social.adapter.social_provider_supports_embeds",
        autospec=True,
    )
    @patch("quickscale_modules_social.adapter.assemble_wiring_spec")
    @patch("quickscale_modules_social.adapter.load_social_manifest")
    @patch("quickscale_modules_social.adapter.resolve_social_module_options")
    def test_empty_embed_allowlist_when_no_providers_support_embeds(
        self,
        mock_resolve: MagicMock,
        mock_load: MagicMock,
        mock_assemble: MagicMock,
        mock_supports_embeds: MagicMock,
    ) -> None:
        """When no provider supports embeds, the embed allowlist is empty."""
        mock_resolve.return_value = {
            "provider_allowlist": ["linkedin", "x"],
            "link_tree_enabled": True,
            "layout_variant": "list",
            "embeds_enabled": True,
            "cache_ttl_seconds": 300,
            "links_per_page": 24,
            "embeds_per_page": 12,
        }
        mock_load.return_value = MagicMock(
            managed_files=PropertyMock(return_value={}),
        )
        mock_assemble.return_value = ModuleWiringSpec()
        mock_supports_embeds.return_value = False

        _social_manifest_adapter(
            {},
            project_package="myapp",
        )

        call_args, _ = mock_assemble.call_args
        resolver_result = call_args[0]

        assert (
            resolver_result.derived_settings[
                "QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST"
            ]
            == []
        )


class TestSocialManifestAdapterRendererIdReplacement:
    """Renderer-ID placeholder replacement via the post-resolution hook."""

    @patch("quickscale_modules_social.adapter.render_social_managed_init_module")
    @patch("quickscale_modules_social.adapter.render_social_managed_urls_module")
    @patch("quickscale_modules_social.adapter.render_social_managed_views_module")
    @patch("quickscale_modules_social.adapter.assemble_wiring_spec")
    @patch("quickscale_modules_social.adapter.load_social_manifest")
    @patch("quickscale_modules_social.adapter.resolve_social_module_options")
    def test_renderer_id_placeholders_replaced(
        self,
        mock_resolve: MagicMock,
        mock_load: MagicMock,
        mock_assemble: MagicMock,
        mock_render_views: MagicMock,
        mock_render_urls: MagicMock,
        mock_render_init: MagicMock,
    ) -> None:
        """The post-resolution hook must replace renderer-ID placeholders with content."""
        mock_resolve.return_value = {
            "provider_allowlist": ["youtube", "linkedin"],
            "link_tree_enabled": True,
            "layout_variant": "list",
            "embeds_enabled": True,
            "cache_ttl_seconds": 300,
            "links_per_page": 24,
            "embeds_per_page": 12,
        }
        mock_load.return_value = MagicMock(
            managed_files=PropertyMock(return_value={}),
        )

        mock_render_init.return_value = "# init content"
        mock_render_urls.return_value = "# urls content"
        mock_render_views.return_value = "# views content"

        original_assemble = _import_original_assemble()
        if original_assemble is None:
            return

        def assemble_side_effect(result, *, post_hook):
            """Simulate assemble_wiring_spec: create a spec with placeholder managed_files,
            then apply the post_hook."""
            spec = ModuleWiringSpec(
                managed_files={
                    "quickscale_managed/__init__.py": "social.managed_init",
                    "quickscale_managed/social_urls.py": "social.managed_urls",
                    "quickscale_managed/social_views.py": "social.managed_views",
                },
            )
            return post_hook(spec, dict(result.resolved))

        mock_assemble.side_effect = assemble_side_effect

        result = _social_manifest_adapter(
            {},
            project_package="myapp",
        )

        assert (
            result.managed_files["quickscale_managed/__init__.py"] == "# init content"
        )
        assert (
            result.managed_files["quickscale_managed/social_urls.py"]
            == "# urls content"
        )
        assert (
            result.managed_files["quickscale_managed/social_views.py"]
            == "# views content"
        )
        mock_render_init.assert_called_once()
        mock_render_urls.assert_called_once()
        mock_render_views.assert_called_once()

    @patch("quickscale_modules_social.adapter.assemble_wiring_spec")
    @patch("quickscale_modules_social.adapter.load_social_manifest")
    @patch("quickscale_modules_social.adapter.resolve_social_module_options")
    def test_unknown_renderer_id_skipped(
        self,
        mock_resolve: MagicMock,
        mock_load: MagicMock,
        mock_assemble: MagicMock,
    ) -> None:
        """A renderer ID not in the dispatch table must be skipped silently."""
        mock_resolve.return_value = {
            "provider_allowlist": ["youtube"],
            "link_tree_enabled": True,
            "layout_variant": "list",
            "embeds_enabled": True,
            "cache_ttl_seconds": 300,
            "links_per_page": 24,
            "embeds_per_page": 12,
        }
        mock_load.return_value = MagicMock(
            managed_files=PropertyMock(return_value={}),
        )

        def assemble_side_effect(result, *, post_hook):
            spec = ModuleWiringSpec(
                managed_files={
                    "quickscale_managed/unknown.py": "social.nonexistent_renderer",
                },
            )
            return post_hook(spec, dict(result.resolved))

        mock_assemble.side_effect = assemble_side_effect

        result = _social_manifest_adapter(
            {},
            project_package="myapp",
        )

        assert "quickscale_managed/unknown.py" not in result.managed_files


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _import_original_assemble() -> object | None:
    """Return the original assemble_wiring_spec for type checking."""
    from quickscale_core.manifest.assembler import assemble_wiring_spec

    return assemble_wiring_spec
