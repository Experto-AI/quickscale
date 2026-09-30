"""Focused tests for the orgs manifest adapter."""

from __future__ import annotations

from typing import Any

import pytest

from quickscale_core.manifest import ManifestError, build_generic_manifest_spec
from quickscale_core.module_wiring import ModuleWiringSpec
from quickscale_modules_orgs.adapter import (
    _orgs_manifest_adapter,
    get_manifest_adapter,
)


class TestOrgsManifestAdapter:
    """Orgs adapter settings, validation, and URL placement contract."""

    def test_sentinel_returns_callable(self) -> None:
        """The public sentinel returns the module adapter."""
        assert get_manifest_adapter() is _orgs_manifest_adapter

    def test_solo_defaults_use_pre_home_urls(self) -> None:
        """Solo mode keeps the org mount before the project's home route."""
        spec = _orgs_manifest_adapter({})

        assert isinstance(spec, ModuleWiringSpec)
        assert spec.apps == ("rest_framework", "quickscale_modules_orgs")
        assert spec.middleware == (
            "quickscale_modules_orgs.middleware.TenantMiddleware",
        )
        assert spec.settings == {
            "QUICKSCALE_MODE": "solo",
        }
        assert spec.pre_home_url_includes == (
            ("orgs/", "quickscale_modules_orgs.urls"),
        )
        assert spec.url_includes == ()

    def test_saas_mode_uses_post_home_urls(self) -> None:
        """SaaS mode keeps the org mount after the project's home route."""
        spec = _orgs_manifest_adapter({"mode": "saas"})

        assert spec.settings["QUICKSCALE_MODE"] == "saas"
        assert spec.pre_home_url_includes == ()
        assert spec.url_includes == (("orgs/", "quickscale_modules_orgs.urls"),)

    @pytest.mark.parametrize(
        ("mode", "pre_home", "post_home"),
        [
            ("solo", (("orgs/", "quickscale_modules_orgs.urls"),), ()),
            ("saas", (), (("orgs/", "quickscale_modules_orgs.urls"),)),
        ],
    )
    def test_manifest_owns_the_orgs_mount(
        self,
        mode: str,
        pre_home: tuple[tuple[str, str], ...],
        post_home: tuple[tuple[str, str], ...],
    ) -> None:
        """Rule 7: the manifest's conditional url_includes is the mount's home."""
        spec = build_generic_manifest_spec("orgs", {"mode": mode})

        assert spec.pre_home_url_includes == pre_home
        assert spec.url_includes == post_home

    @pytest.mark.parametrize("raw_mode", [" SaaS ", "SAAS", " solo ", "SOLO"])
    def test_mode_is_normalized(self, raw_mode: str) -> None:
        """Mode whitespace and case normalization match the resolver contract."""
        expected_mode = raw_mode.strip().lower()
        spec = _orgs_manifest_adapter({"mode": raw_mode})

        assert spec.settings["QUICKSCALE_MODE"] == expected_mode
        if expected_mode == "solo":
            assert spec.pre_home_url_includes
            assert not spec.url_includes
        else:
            assert spec.url_includes
            assert not spec.pre_home_url_includes

    @pytest.mark.parametrize("options", [{"mode": "invalid"}, {"mode": ""}])
    def test_invalid_mode_fails_closed(self, options: dict[str, Any]) -> None:
        """Invalid modes are rejected instead of producing contradictory URLs."""
        with pytest.raises(ManifestError, match="modules.orgs.mode"):
            _orgs_manifest_adapter(options)

    def test_repeated_calls_do_not_leak_mode_or_url_placement(self) -> None:
        """Repeated calls remain isolated across mode changes."""
        saas = _orgs_manifest_adapter({"mode": "saas"})
        solo = _orgs_manifest_adapter({})
        saas_again = _orgs_manifest_adapter({"mode": "saas"})

        assert saas.url_includes == (("orgs/", "quickscale_modules_orgs.urls"),)
        assert saas.pre_home_url_includes == ()
        assert solo.pre_home_url_includes == (
            ("orgs/", "quickscale_modules_orgs.urls"),
        )
        assert solo.url_includes == ()
        assert saas_again == saas
