"""Tests for the generic transitive implication resolver.

Verifies that :func:`resolve_module_implications` correctly reads ``implies``
blocks from ``module.yml`` manifests and computes the transitive closure (e.g.
billing → orgs → notifications).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.contracts.module_discovery import ImproperlyConfigured
from quickscale_core.manifest.implications import resolve_module_implications
from quickscale_core.manifest.loader import ManifestError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def modules_base_path() -> Path:
    """Return the path to the maintainer's quickscale_modules directory."""
    return Path(__file__).resolve().parent.parent.parent / "quickscale_modules"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    """Boundary and error-path tests."""

    def test_empty_names_returns_empty(self, modules_base_path: Path) -> None:
        """An empty name list should produce no implied configs."""
        result = resolve_module_implications([], modules_base_path=modules_base_path)
        assert result == {}

    def test_unknown_names_returns_empty(self, modules_base_path: Path) -> None:
        """Names that don't match a manifest directory produce no configs."""
        result = resolve_module_implications(
            ["nonexistent_module"],
            modules_base_path=modules_base_path,
        )
        assert result == {}

    def test_unknown_and_known_mixed(self, modules_base_path: Path) -> None:
        """Known module implications are resolved even when unknown modules are also listed."""
        result = resolve_module_implications(
            ["billing", "nonexistent"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result

    def test_module_without_implies_returns_empty(
        self, modules_base_path: Path
    ) -> None:
        """Modules with no ``implies`` block should produce no configs."""
        # Notifications has no implies and no modules imply *from* it
        result = resolve_module_implications(
            ["notifications"],
            modules_base_path=modules_base_path,
        )
        assert result == {}

    def test_module_without_manifest_silent(self, modules_base_path: Path) -> None:
        """A name with no matching directory is silently skipped."""
        result = resolve_module_implications(
            ["__nonexistent_test_module__"],
            modules_base_path=modules_base_path,
        )
        assert result == {}

    def test_non_module_directory_silent(self, tmp_path: Path) -> None:
        """A directory without a module.yml is silently skipped."""
        (tmp_path / "bogus").mkdir()
        result = resolve_module_implications(
            ["bogus"],
            modules_base_path=tmp_path,
        )
        assert result == {}

    def test_invalid_manifest_raises(self, tmp_path: Path) -> None:
        """A malformed module.yml raises ManifestError."""
        module_dir = tmp_path / "badmod"
        module_dir.mkdir()
        (module_dir / "module.yml").write_text("invalid: [yaml: broken\n")
        with pytest.raises(ManifestError):
            resolve_module_implications(
                ["badmod"],
                modules_base_path=tmp_path,
            )

    def test_case_sensitivity(self, modules_base_path: Path) -> None:
        """Module names are case-sensitive; wrong case produces no implications."""
        result = resolve_module_implications(
            ["Billing"],
            modules_base_path=modules_base_path,
        )
        assert result == {}


# ---------------------------------------------------------------------------
# billing → orgs → notifications
# ---------------------------------------------------------------------------


class TestBillingImplications:
    """billing → orgs → notifications chain."""

    def test_billing_implies_orgs(self, modules_base_path: Path) -> None:
        """Selecting billing should materialize orgs (via manifest implies)."""
        result = resolve_module_implications(
            ["billing"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """billing with orgs already present should not list orgs."""
        result = resolve_module_implications(
            ["billing", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result

    def test_billing_chain_implies_notifications(self, modules_base_path: Path) -> None:
        """billing → orgs → notifications chain should materialize both."""
        result = resolve_module_implications(
            ["billing"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result
        assert result["orgs"] == {}
        # notifications has no inline defaults — they come from its own manifest
        assert isinstance(result["notifications"], dict)
        assert result["notifications"] == {}

    def test_billing_chain_with_notifications_already_selected(
        self, modules_base_path: Path
    ) -> None:
        """billing → orgs → notifications: skip notifications if already present."""
        result = resolve_module_implications(
            ["billing", "notifications"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" not in result


# ---------------------------------------------------------------------------
# crm → orgs → notifications
# ---------------------------------------------------------------------------


class TestCrmImplications:
    """crm → orgs → notifications chain."""

    def test_crm_implies_orgs(self, modules_base_path: Path) -> None:
        """Selecting crm should materialize orgs."""
        result = resolve_module_implications(
            ["crm"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_crm_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """crm with orgs already present should not duplicate."""
        result = resolve_module_implications(
            ["crm", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result

    def test_crm_chain_implies_notifications(self, modules_base_path: Path) -> None:
        """crm → orgs → notifications chain."""
        result = resolve_module_implications(
            ["crm"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# social → orgs → notifications
# ---------------------------------------------------------------------------


class TestSocialImplications:
    """social → orgs → notifications chain."""

    def test_social_implies_orgs(self, modules_base_path: Path) -> None:
        """Selecting social should materialize orgs."""
        result = resolve_module_implications(
            ["social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_social_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """social with orgs already present should not duplicate."""
        result = resolve_module_implications(
            ["social", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result

    def test_social_chain_implies_notifications(self, modules_base_path: Path) -> None:
        """social → orgs → notifications chain."""
        result = resolve_module_implications(
            ["social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# orgs → notifications (direct)
# ---------------------------------------------------------------------------


class TestOrgsImplications:
    """orgs → notifications chain."""

    def test_orgs_implies_notifications(self, modules_base_path: Path) -> None:
        """Selecting orgs should materialize notifications (defaults from own manifest)."""
        result = resolve_module_implications(
            ["orgs"],
            modules_base_path=modules_base_path,
        )
        assert "notifications" in result
        config = result["notifications"]
        assert isinstance(config, dict)
        # SA7.3: inline defaults removed — notifications provides its own
        assert config == {}

    def test_orgs_with_notifications_already_selected(
        self, modules_base_path: Path
    ) -> None:
        """orgs with notifications already present should not duplicate."""
        result = resolve_module_implications(
            ["orgs", "notifications"],
            modules_base_path=modules_base_path,
        )
        assert "notifications" not in result


# ---------------------------------------------------------------------------
# auth → orgs → notifications (Cluster A)
# ---------------------------------------------------------------------------


class TestAuthImplications:
    """auth → orgs → notifications chain."""

    def test_auth_implies_orgs(self, modules_base_path: Path) -> None:
        """Selecting auth should materialize orgs."""
        result = resolve_module_implications(
            ["auth"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_auth_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """auth with orgs already present should not duplicate."""
        result = resolve_module_implications(
            ["auth", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result

    def test_auth_chain_implies_notifications(self, modules_base_path: Path) -> None:
        """auth → orgs → notifications chain."""
        result = resolve_module_implications(
            ["auth"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# Multiple implicators
# ---------------------------------------------------------------------------


class TestMultipleImplicators:
    """Multiple modules that imply the same targets should deduplicate."""

    def test_billing_and_crm_imply_orgs_once(self, modules_base_path: Path) -> None:
        """billing + crm should produce orgs once."""
        result = resolve_module_implications(
            ["billing", "crm"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_and_social_imply_orgs_once(self, modules_base_path: Path) -> None:
        """billing + social should produce orgs once."""
        result = resolve_module_implications(
            ["billing", "social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_all_org_implicators_together(self, modules_base_path: Path) -> None:
        """billing + crm + social should materialize orgs only once,
        and the orgs → notifications chain fires once."""
        result = resolve_module_implications(
            ["billing", "crm", "social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}
        assert "notifications" in result

    def test_full_chain_billing(self, modules_base_path: Path) -> None:
        """Full chain: billing → orgs → notifications."""
        result = resolve_module_implications(
            ["billing"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result

    def test_full_chain_social(self, modules_base_path: Path) -> None:
        """Full chain: social → orgs → notifications."""
        result = resolve_module_implications(
            ["social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result

    def test_auth_implies_orgs(self, modules_base_path: Path) -> None:
        """Selecting auth should materialize orgs (and transitively notifications)."""
        result = resolve_module_implications(
            ["auth"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}
        assert "notifications" in result


# ---------------------------------------------------------------------------
# Default modules_base_path
# ---------------------------------------------------------------------------


class TestDefaultModulesBasePath:
    """The default ``modules_base_path`` (without explicit argument) should
    resolve to the repo-root ``quickscale_modules/`` directory."""

    def test_default_path_resolves_billing_chain(self) -> None:
        """Calling without modules_base_path should find repo manifests."""
        result = resolve_module_implications(["billing"])
        assert "orgs" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# SA113: Bundled manifest fallback
# ---------------------------------------------------------------------------


class TestBundledManifestFallback:
    """SA113: resolve_module_implications falls back to bundled manifest
    snapshots when the source-tree modules workspace is unavailable."""

    def test_fallback_resolves_billing_chain(self) -> None:
        """billing → orgs → notifications resolves from bundled manifests
        when get_modules_base_path raises ImproperlyConfigured."""
        with patch(
            "quickscale_core.manifest.implications.get_modules_base_path",
            side_effect=ImproperlyConfigured("no source tree"),
        ):
            result = resolve_module_implications(["billing"])
            assert "orgs" in result
            assert "notifications" in result

    def test_fallback_with_explicit_path_unaffected(self) -> None:
        """Explicitly passing modules_base_path still works—the fallback
        path is not invoked."""
        result = resolve_module_implications([], modules_base_path=Path("/nonexistent"))
        assert result == {}

    def test_fallback_with_explicit_path_still_resolves(self, tmp_path: Path) -> None:
        """Explicit modules_base_path is used directly even when the source
        tree is unavailable — the bundled fallback is NOT invoked when an
        explicit path is supplied."""
        billing_dir = tmp_path / "billing"
        billing_dir.mkdir()
        (billing_dir / "module.yml").write_text(
            "name: billing\n"
            'version: "1.0.0"\n'
            "config:\n"
            "  mutable: {}\n"
            "  immutable: {}\n"
            "implies:\n"
            "  - name: orgs\n"
            "    default_config: {}\n"
        )
        orgs_dir = tmp_path / "orgs"
        orgs_dir.mkdir()
        (orgs_dir / "module.yml").write_text(
            "name: orgs\n"
            'version: "1.0.0"\n'
            "config:\n"
            "  mutable: {}\n"
            "  immutable: {}\n"
            "implies: []\n"
        )

        # Even with source tree unavailable, explicit path is honoured.
        with patch(
            "quickscale_core.manifest.implications.get_modules_base_path",
            side_effect=ImproperlyConfigured("no source tree"),
        ):
            result = resolve_module_implications(
                ["billing"],
                modules_base_path=tmp_path,
            )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_fallback_selected_manifest_missing_raises(self, tmp_path: Path) -> None:
        """Bundled fallback: a selected module with no manifest in the
        bundled snapshot raises ImproperlyConfigured."""
        bundle_dir = tmp_path / "manifests"
        bundle_dir.mkdir(parents=True)
        # bundle_dir exists but contains no module.yml files at all.
        with (
            patch(
                "quickscale_core.manifest.implications.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.implications.get_bundled_manifests_path",
                return_value=bundle_dir,
            ),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_module_implications(["billing"])

    def test_fallback_implied_manifest_missing_raises(self, tmp_path: Path) -> None:
        """Bundled fallback: a transitive implication target missing from
        the bundled snapshot raises ImproperlyConfigured."""
        bundle_dir = tmp_path / "manifests"
        bundle_dir.mkdir(parents=True)
        billing_dir = bundle_dir / "billing"
        billing_dir.mkdir()
        (billing_dir / "module.yml").write_text(
            "name: billing\n"
            'version: "1.0.0"\n'
            "config:\n"
            "  mutable: {}\n"
            "  immutable: {}\n"
            "implies:\n"
            "  - name: orgs\n"
            "    default_config: {}\n"
        )
        # orgs directory exists but has no module.yml — missing chain link.
        orgs_dir = bundle_dir / "orgs"
        orgs_dir.mkdir()

        with (
            patch(
                "quickscale_core.manifest.implications.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.implications.get_bundled_manifests_path",
                return_value=bundle_dir,
            ),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_module_implications(["billing"])

    def test_fallback_malformed_manifest_raises(self, tmp_path: Path) -> None:
        """Bundled fallback: a malformed module.yml in the bundled snapshot
        raises ManifestError (remains a hard failure)."""
        bundle_dir = tmp_path / "manifests"
        bundle_dir.mkdir(parents=True)
        billing_dir = bundle_dir / "billing"
        billing_dir.mkdir()
        (billing_dir / "module.yml").write_text("invalid: [yaml: broken\n")

        with (
            patch(
                "quickscale_core.manifest.implications.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.implications.get_bundled_manifests_path",
                return_value=bundle_dir,
            ),
        ):
            with pytest.raises(ManifestError):
                resolve_module_implications(["billing"])

    def test_fallback_fail_hard_when_both_unavailable(self) -> None:
        """When both source-tree and bundled manifests are unavailable,
        ImproperlyConfigured is raised (fail-hard)."""
        with (
            patch(
                "quickscale_core.manifest.implications.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.implications.get_bundled_manifests_path",
                side_effect=ImproperlyConfigured("no bundled manifests"),
            ),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_module_implications(["billing"])


# ---------------------------------------------------------------------------
# SA111b: Fast in-monorepo fallback regression test
# ---------------------------------------------------------------------------


class TestSa111bFallbackRegression:
    """SA111b: fast in-monorepo bundled-manifest fallback regression test.

    Monkeypatches ``get_modules_base_path`` to raise ``ImproperlyConfigured``
    and confirms that ``resolve_module_implications`` falls through to the
    bundled-manifest snapshots via ``get_bundled_manifests_path()``.  This is
    a cheap early-signal companion for the authoritative installed-wheel probe
    (SA111a).  Runs inside ``make check``.
    """

    def test_fallback_resolves_billing_to_orgs(self) -> None:
        """Monkeypatch the source-tree path so the resolver falls back to
        bundled manifests and still resolves billing → orgs."""
        with patch(
            "quickscale_core.manifest.implications.get_modules_base_path",
            side_effect=ImproperlyConfigured("no source tree"),
        ):
            result = resolve_module_implications(["billing"])
            assert "orgs" in result
