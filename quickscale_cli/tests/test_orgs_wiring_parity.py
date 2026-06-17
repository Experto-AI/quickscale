"""Wiring-parity tests for the manifest-driven orgs path (Track 2 M4 follow-up).

Compares the legacy ``_orgs_wiring`` builder output against the
manifest-driven ``build_manifest_wiring_spec("orgs", ...)`` for every
option case, asserting full
:class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

Scope
-----
* Default options (empty dict) — solo mode
* Explicit solo mode
* Saas mode — URL include moves from pre_home to post_home
* Invalid mode value — falls back to solo
* Whitespace / case normalisation
* Combined override cases
* Batch multi-case parity
"""

from __future__ import annotations

from wiring_parity import assert_wiring_parity


class TestOrgsWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("orgs", [{}])


class TestOrgsWiringParitySoloMode:
    """Solo mode: root include in pre_home_url_includes, url_includes empty."""

    def test_explicit_solo(self) -> None:
        assert_wiring_parity("orgs", [{"mode": "solo"}])

    def test_solo_pre_home_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {"mode": "solo"})
        assert spec.pre_home_url_includes == (("", "quickscale_modules_orgs.urls"),)
        assert spec.url_includes == ()

    def test_solo_settings(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {"mode": "solo"})
        assert spec.settings["QUICKSCALE_MODE"] == "solo"
        assert (
            spec.settings["ACCOUNT_ADAPTER"]
            == "quickscale_modules_orgs.adapters.OrgsAccountAdapter"
        )


class TestOrgsWiringParitySaasMode:
    """Saas mode: root include in url_includes, pre_home_url_includes empty."""

    def test_explicit_saas(self) -> None:
        assert_wiring_parity("orgs", [{"mode": "saas"}])

    def test_saas_url_includes(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {"mode": "saas"})
        assert spec.pre_home_url_includes == ()
        assert spec.url_includes == (("", "quickscale_modules_orgs.urls"),)

    def test_saas_settings(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {"mode": "saas"})
        assert spec.settings["QUICKSCALE_MODE"] == "saas"


class TestOrgsWiringParityInvalidMode:
    """Invalid mode values must fall back to solo."""

    def test_invalid_mode_fallback(self) -> None:
        assert_wiring_parity("orgs", [{"mode": "enterprise"}])

    def test_invalid_mode_uses_solo_placement(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {"mode": "enterprise"})
        assert spec.settings["QUICKSCALE_MODE"] == "solo"
        assert spec.pre_home_url_includes == (("", "quickscale_modules_orgs.urls"),)
        assert spec.url_includes == ()


class TestOrgsWiringParityNormalisation:
    """Whitespace and case normalisation must match legacy behaviour."""

    def test_uppercase_saas(self) -> None:
        assert_wiring_parity("orgs", [{"mode": "SAAS"}])

    def test_whitespace_padded_solo(self) -> None:
        assert_wiring_parity("orgs", [{"mode": "  solo  "}])

    def test_mixed_case_saas(self) -> None:
        assert_wiring_parity("orgs", [{"mode": "Saas"}])


class TestOrgsWiringParityStaticWiring:
    """Static wiring fields must be present and identical in both paths."""

    def test_apps(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {})
        assert spec.apps == ("quickscale_modules_orgs",)

    def test_middleware(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {})
        assert spec.middleware == (
            "quickscale_modules_orgs.middleware.TenantMiddleware",
        )

    def test_account_adapter_setting(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("orgs", {})
        assert (
            spec.settings["ACCOUNT_ADAPTER"]
            == "quickscale_modules_orgs.adapters.OrgsAccountAdapter"
        )


class TestOrgsWiringParityBatchCases:
    """Run multiple option cases through the harness in a single call."""

    def test_multiple_cases_in_one_call(self) -> None:
        assert_wiring_parity(
            "orgs",
            [
                {},
                {"mode": "solo"},
                {"mode": "saas"},
                {"mode": "SAAS"},
                {"mode": "  solo  "},
                {"mode": "enterprise"},
                {"mode": "Saas"},
            ],
        )
