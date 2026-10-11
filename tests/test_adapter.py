"""Focused tests for the social manifest adapter.

Covers ``project_package`` validation, embed-provider filtering,
renderer-ID replacement, and the sentinel contract.  The manifest boundary
owns every option default, normalization rule, check, projection, and
settings surface; the adapter contributes only the embed-capable provider
slice, the project-qualified mount, and the rendered managed-file content.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.manifest import build_generic_manifest_spec
from quickscale_core.module_wiring import ModuleWiringSpec

from quickscale_modules_social.adapter import (
    _build_social_post_hook,
    _qualify_managed_url_includes,
    _social_manifest_adapter,
    get_manifest_adapter,
)

_RESOLVED_OPTIONS: dict[str, Any] = {
    "enabled": True,
    "link_tree_enabled": True,
    "layout_variant": "list",
    "embeds_enabled": True,
    "provider_allowlist": [
        "facebook",
        "instagram",
        "linkedin",
        "tiktok",
        "x",
        "youtube",
    ],
    "cache_ttl_seconds": 300,
    "links_per_page": 24,
    "embeds_per_page": 12,
}


def _resolved(**overrides: Any) -> dict[str, Any]:
    """Return the canonical resolved options the hook consumes."""
    resolved = dict(_RESOLVED_OPTIONS)
    resolved.update(overrides)
    return resolved


def _managed_files() -> dict[str, str]:
    """Return the social manifest's declared managed output -> renderer mapping."""
    return {
        "quickscale_managed/__init__.py": "social.managed_init",
        "quickscale_managed/social_urls.py": "social.managed_urls",
        "quickscale_managed/social_views.py": "social.managed_views",
    }


class TestGetManifestAdapter:
    """get_manifest_adapter sentinel contract."""

    def test_returns_callable(self) -> None:
        """get_manifest_adapter must return a callable."""
        adapter = get_manifest_adapter()
        assert callable(adapter)

    def test_import_does_not_require_django(self) -> None:
        """Installed managed wiring can import the adapter before Django exists."""
        workspace_root = Path(__file__).resolve().parents[3]
        core_src = workspace_root / "quickscale_core" / "src"
        social_src = workspace_root / "quickscale_modules" / "social" / "src"
        code = f"""
import importlib.abc
import sys

sys.path.insert(0, {str(social_src)!r})
sys.path.insert(0, {str(core_src)!r})

class BlockDjango(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "django" or fullname.startswith("django."):
            raise ModuleNotFoundError("blocked Django import")
        return None

sys.meta_path.insert(0, BlockDjango())
from quickscale_modules_social.adapter import get_manifest_adapter

assert callable(get_manifest_adapter())
assert "quickscale_core.runtime.dr" not in sys.modules
assert not any(name.startswith("quickscale_core.dr_engine") for name in sys.modules)
"""

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

        assert result.returncode == 0, (
            f"adapter import failed without Django:\nstdout: {result.stdout}\n"
            f"stderr: {result.stderr}"
        )


class TestSocialManifestMount:
    """Rule 7: social's mount lives only in the manifest."""

    def test_manifest_owns_the_social_mount(self) -> None:
        """The manifest's url_includes is the mount's only home."""
        spec = build_generic_manifest_spec("social", {})

        assert spec.url_includes == (
            ("_quickscale/social/", "quickscale_managed.social_urls"),
        )
        assert spec.pre_home_url_includes == ()

    def test_adapter_qualifies_the_manifest_include(self) -> None:
        """The adapter supplies the project package the manifest cannot know."""
        spec = _social_manifest_adapter({}, project_package="myapp")

        assert spec.url_includes == (
            ("_quickscale/social/", "myapp.quickscale_managed.social_urls"),
        )

    def test_disabled_module_drops_the_mount_but_keeps_managed_files(self) -> None:
        """Rule 1 (D3): off keeps the app, settings, and managed files, and
        mounts none of the module's public URLs."""
        spec = _social_manifest_adapter({"enabled": False}, project_package="myapp")

        assert spec.settings["QUICKSCALE_SOCIAL_ENABLED"] is False
        assert spec.apps == ("quickscale_modules_social",)
        assert spec.url_includes == ()
        assert spec.pre_home_url_includes == ()
        assert set(spec.managed_files) == {
            "quickscale_managed/__init__.py",
            "quickscale_managed/social_urls.py",
            "quickscale_managed/social_views.py",
        }

    def test_undeclared_include_target_fails_closed(self) -> None:
        """A target social does not render is refused, not qualified."""
        with pytest.raises(ValueError, match="managed URLconf social renders"):
            _qualify_managed_url_includes(
                (("_quickscale/social/", "quickscale_managed.socail_urls"),),
                "myapp",
                managed_files=_managed_files(),
            )

    def test_non_urlconf_include_target_fails_closed(self) -> None:
        """A managed file that is not the rendered URLconf is refused."""
        with pytest.raises(ValueError, match="managed URLconf social renders"):
            _qualify_managed_url_includes(
                (("_quickscale/social/", "quickscale_managed.social_views"),),
                "myapp",
                managed_files=_managed_files(),
            )

    def test_absolute_include_target_fails_closed(self) -> None:
        """A target outside the managed package is refused, not qualified."""
        with pytest.raises(ValueError, match="managed URLconf social renders"):
            _qualify_managed_url_includes(
                (("_quickscale/social/", "quickscale_modules_social.urls"),),
                "myapp",
                managed_files=_managed_files(),
            )

    def test_empty_include_set_fails_closed(self) -> None:
        """A manifest without the mount cannot silently wire nothing."""
        with pytest.raises(ValueError, match="expected the module's mount"):
            _qualify_managed_url_includes(
                (),
                "myapp",
                managed_files=_managed_files(),
            )


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


class TestSocialManifestAdapterApps:
    """Django apps come from the manifest's single static projection."""

    def test_actual_manifest_provides_social_app(self) -> None:
        """The canonical manifest supplies the social Django app label."""
        result = _social_manifest_adapter({}, project_package="myapp")

        assert result.apps == ("quickscale_modules_social",)


class TestSocialManifestAdapterEmbedFiltering:
    """Embed-provider filtering from the canonical provider allowlist."""

    def test_filters_embed_providers(self) -> None:
        """Only embed-supporting providers appear in the embed allowlist."""
        spec = _social_manifest_adapter(
            {"provider_allowlist": ["youtube", "linkedin", "x"]},
            project_package="myapp",
        )

        assert spec.settings["QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST"] == [
            "youtube",
            "linkedin",
            "x",
        ]
        assert spec.settings["QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST"] == [
            "youtube"
        ]

    def test_empty_embed_allowlist_when_no_providers_support_embeds(self) -> None:
        """When no provider supports embeds, the embed allowlist is empty."""
        spec = _social_manifest_adapter(
            {"provider_allowlist": ["linkedin", "x"], "embeds_enabled": False},
            project_package="myapp",
        )

        assert spec.settings["QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST"] == []


class TestSocialManifestAdapterRendererIdReplacement:
    """Renderer-ID placeholder replacement via the post-resolution hook."""

    @patch("quickscale_modules_social.adapter.render_social_managed_init_module")
    @patch("quickscale_modules_social.adapter.render_social_managed_urls_module")
    @patch("quickscale_modules_social.adapter.render_social_managed_views_module")
    def test_renderer_id_placeholders_replaced(
        self,
        mock_render_views: MagicMock,
        mock_render_urls: MagicMock,
        mock_render_init: MagicMock,
    ) -> None:
        """The hook replaces each renderer-ID placeholder with its content."""
        mock_render_init.return_value = "# init content"
        mock_render_urls.return_value = "# urls content"
        mock_render_views.return_value = "# views content"

        hook = _build_social_post_hook("myapp")
        spec = ModuleWiringSpec(
            apps=("quickscale_modules_social",),
            url_includes=(("_quickscale/social/", "quickscale_managed.social_urls"),),
            managed_files=_managed_files(),
        )

        result = hook(spec, _resolved())

        assert result.managed_files["quickscale_managed/__init__.py"] == (
            "# init content"
        )
        assert result.managed_files["quickscale_managed/social_urls.py"] == (
            "# urls content"
        )
        assert result.managed_files["quickscale_managed/social_views.py"] == (
            "# views content"
        )
        mock_render_init.assert_called_once()
        mock_render_urls.assert_called_once()
        mock_render_views.assert_called_once_with(
            ["facebook", "instagram", "linkedin", "tiktok", "x", "youtube"],
            ["tiktok", "youtube"],
            layout_variant="list",
            cache_ttl_seconds=300,
            links_per_page=24,
            embeds_per_page=12,
        )

    def test_unknown_renderer_id_skipped(self) -> None:
        """A renderer ID not in the dispatch table must be skipped."""
        hook = _build_social_post_hook("myapp")
        spec = ModuleWiringSpec(
            url_includes=(("_quickscale/social/", "quickscale_managed.social_urls"),),
            managed_files={
                "quickscale_managed/social_urls.py": "social.managed_urls",
                "quickscale_managed/unknown.py": "social.nonexistent_renderer",
            },
        )

        result = hook(spec, _resolved())

        assert "quickscale_managed/unknown.py" not in result.managed_files
        assert "quickscale_managed/social_urls.py" in result.managed_files
