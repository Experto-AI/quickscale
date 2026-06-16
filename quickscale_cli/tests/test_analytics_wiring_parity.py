"""Wiring-parity tests for the manifest-driven analytics path (C2).

Compares the legacy ``_analytics_wiring`` builder output against the manifest-driven
``build_manifest_wiring_spec("analytics", ...)`` for every option case, asserting
full :class:`~quickscale_core.module_wiring.ModuleWiringSpec` dataclass equality.

PR-4 hazard: the legacy ``_analytics_wiring`` returns an EMPTY ModuleWiringSpec
when ``enabled`` is ``False``.  This file exercises that disabled case to confirm
parity is preserved.

Scope
-----
* Default options (empty dict)
* Disabled case (PR-4 short-circuit — must return empty spec)
* Provider override (only posthog supported)
* Custom env-var names
* Custom posthog host
* Combined override case
"""

from __future__ import annotations


from wiring_parity import assert_wiring_parity


class TestAnalyticsWiringParityDefaults:
    """Default options must produce equal specs from both paths."""

    def test_empty_options(self) -> None:
        assert_wiring_parity("analytics", [{}])


class TestAnalyticsWiringParityDisabled:
    """PR-4 hazard: disabled analytics must return an empty spec."""

    def test_disabled_returns_empty_spec(self) -> None:
        assert_wiring_parity("analytics", [{"enabled": False}])

    def test_disabled_apps_is_empty(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("analytics", {"enabled": False})
        assert spec.apps == ()

    def test_disabled_settings_is_empty(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("analytics", {"enabled": False})
        assert dict(spec.settings) == {}

    def test_disabled_middleware_is_empty(self) -> None:
        from quickscale_core.manifest.entry_point import build_manifest_wiring_spec

        spec = build_manifest_wiring_spec("analytics", {"enabled": False})
        assert spec.middleware == ()


class TestAnalyticsWiringParityOverrides:
    """Overridden options must produce equal specs from both paths."""

    def test_custom_posthog_host(self) -> None:
        assert_wiring_parity(
            "analytics",
            [{"posthog_host": "https://eu.i.posthog.com"}],
        )

    def test_custom_api_key_env_var(self) -> None:
        assert_wiring_parity(
            "analytics",
            [{"posthog_api_key_env_var": "CUSTOM_PH_KEY"}],
        )

    def test_custom_host_env_var(self) -> None:
        assert_wiring_parity(
            "analytics",
            [{"posthog_host_env_var": "CUSTOM_PH_HOST"}],
        )

    def test_exclude_staff_true(self) -> None:
        assert_wiring_parity("analytics", [{"exclude_staff": True}])

    def test_anonymous_by_default_false(self) -> None:
        assert_wiring_parity("analytics", [{"anonymous_by_default": False}])

    def test_exclude_debug_false(self) -> None:
        assert_wiring_parity("analytics", [{"exclude_debug": False}])

    def test_combined_overrides(self) -> None:
        assert_wiring_parity(
            "analytics",
            [
                {
                    "posthog_host": "eu.i.posthog.com",
                    "exclude_staff": True,
                    "anonymous_by_default": False,
                }
            ],
        )


class TestAnalyticsWiringParityBatchCases:
    """Run multiple option cases through the harness in a single call."""

    def test_multiple_cases_in_one_call(self) -> None:
        assert_wiring_parity(
            "analytics",
            [
                {},
                {"enabled": False},
                {"posthog_host": "https://eu.i.posthog.com"},
                {"exclude_staff": True, "anonymous_by_default": False},
            ],
        )
