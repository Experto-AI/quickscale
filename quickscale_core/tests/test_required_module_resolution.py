"""Tests for the transitive required-module resolver.

Verifies that :func:`resolve_required_modules` reads ``required_modules``
declarations from ``module.yml`` manifests and computes the transitive
closure for a selected set (for example billing → orgs → auth, notifications).
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from quickscale_core.contracts.module_discovery import ImproperlyConfigured
from quickscale_core.manifest.loader import ManifestError
from quickscale_core.manifest.required_modules import resolve_required_modules


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
        """An empty name list should produce no required configs."""
        result = resolve_required_modules([], modules_base_path=modules_base_path)
        assert result == {}

    def test_unknown_names_returns_empty(self, modules_base_path: Path) -> None:
        """Names that don't match a manifest directory produce no configs."""
        result = resolve_required_modules(
            ["nonexistent_module"],
            modules_base_path=modules_base_path,
        )
        assert result == {}

    def test_unknown_and_known_mixed(self, modules_base_path: Path) -> None:
        """Known module requirements resolve even when unknown names are listed."""
        result = resolve_required_modules(
            ["billing", "nonexistent"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result

    def test_module_without_required_modules_returns_empty(
        self, modules_base_path: Path
    ) -> None:
        """Modules with no required_modules should produce no configs."""
        result = resolve_required_modules(
            ["notifications"],
            modules_base_path=modules_base_path,
        )
        assert result == {}

    def test_module_without_manifest_silent(self, modules_base_path: Path) -> None:
        """A name with no matching directory is silently skipped."""
        result = resolve_required_modules(
            ["__nonexistent_test_module__"],
            modules_base_path=modules_base_path,
        )
        assert result == {}

    def test_non_module_directory_silent(self, tmp_path: Path) -> None:
        """A directory without a module.yml is silently skipped."""
        (tmp_path / "bogus").mkdir()
        result = resolve_required_modules(
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
            resolve_required_modules(
                ["badmod"],
                modules_base_path=tmp_path,
            )

    def test_missing_required_manifest_raises(self, tmp_path: Path) -> None:
        """A discovered required module with no manifest fails hard."""
        billing_dir = tmp_path / "billing"
        billing_dir.mkdir()
        (billing_dir / "module.yml").write_text(
            "name: billing\n"
            'version: "1.0.0"\n'
            "config:\n"
            "  mutable: {}\n"
            "  immutable: {}\n"
            "required_modules:\n"
            "  - orgs\n"
        )
        with pytest.raises(ManifestError, match="Required module 'orgs'"):
            resolve_required_modules(["billing"], modules_base_path=tmp_path)

    def test_missing_required_manifest_raises_when_also_selected(
        self, tmp_path: Path
    ) -> None:
        """A required edge fails hard even when the name was also selected."""
        billing_dir = tmp_path / "billing"
        billing_dir.mkdir()
        (billing_dir / "module.yml").write_text(
            "name: billing\n"
            'version: "1.0.0"\n'
            "config:\n"
            "  mutable: {}\n"
            "  immutable: {}\n"
            "required_modules:\n"
            "  - orgs\n"
        )
        with pytest.raises(ManifestError, match="Required module 'orgs'"):
            resolve_required_modules(
                ["billing", "orgs"],
                modules_base_path=tmp_path,
            )

    def test_case_sensitivity(self, modules_base_path: Path) -> None:
        """Module names are case-sensitive; wrong case resolves nothing."""
        result = resolve_required_modules(
            ["Billing"],
            modules_base_path=modules_base_path,
        )
        assert result == {}


# ---------------------------------------------------------------------------
# billing → orgs → auth, notifications
# ---------------------------------------------------------------------------


class TestBillingRequirements:
    """billing → orgs → auth, notifications chain."""

    def test_billing_requires_orgs(self, modules_base_path: Path) -> None:
        """Selecting billing should materialize orgs."""
        result = resolve_required_modules(
            ["billing"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """billing with orgs already present should not list orgs."""
        result = resolve_required_modules(
            ["billing", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result
        assert "auth" in result
        assert "notifications" in result

    def test_billing_chain_requires_auth_and_notifications(
        self, modules_base_path: Path
    ) -> None:
        """billing → orgs → auth, notifications should materialize all three."""
        result = resolve_required_modules(
            ["billing"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result
        assert result["orgs"] == {}
        assert result["auth"] == {}
        assert result["notifications"] == {}

    def test_billing_chain_with_everything_already_selected(
        self, modules_base_path: Path
    ) -> None:
        """A fully selected closure produces nothing new."""
        result = resolve_required_modules(
            ["billing", "orgs", "auth", "notifications"],
            modules_base_path=modules_base_path,
        )
        assert result == {}


# ---------------------------------------------------------------------------
# crm → orgs → auth, notifications
# ---------------------------------------------------------------------------


class TestCrmRequirements:
    """crm → orgs → auth, notifications chain."""

    def test_crm_requires_orgs(self, modules_base_path: Path) -> None:
        """Selecting crm should materialize orgs."""
        result = resolve_required_modules(
            ["crm"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_crm_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """crm with orgs already present should not duplicate."""
        result = resolve_required_modules(
            ["crm", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result

    def test_crm_chain_requires_auth_and_notifications(
        self, modules_base_path: Path
    ) -> None:
        """crm → orgs → auth, notifications chain."""
        result = resolve_required_modules(
            ["crm"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# social → orgs → auth, notifications
# ---------------------------------------------------------------------------


class TestSocialRequirements:
    """social → orgs → auth, notifications chain."""

    def test_social_requires_orgs(self, modules_base_path: Path) -> None:
        """Selecting social should materialize orgs."""
        result = resolve_required_modules(
            ["social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_social_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """social with orgs already present should not duplicate."""
        result = resolve_required_modules(
            ["social", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result

    def test_social_chain_requires_auth_and_notifications(
        self, modules_base_path: Path
    ) -> None:
        """social → orgs → auth, notifications chain."""
        result = resolve_required_modules(
            ["social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# orgs → auth, notifications (direct)
# ---------------------------------------------------------------------------


class TestOrgsRequirements:
    """orgs → auth, notifications chain."""

    def test_orgs_requires_notifications(self, modules_base_path: Path) -> None:
        """Selecting orgs should materialize auth and notifications."""
        result = resolve_required_modules(
            ["orgs"],
            modules_base_path=modules_base_path,
        )
        assert "auth" in result
        assert "notifications" in result
        assert result["notifications"] == {}

    def test_orgs_with_notifications_already_selected(
        self, modules_base_path: Path
    ) -> None:
        """orgs with notifications already present should not duplicate."""
        result = resolve_required_modules(
            ["orgs", "notifications"],
            modules_base_path=modules_base_path,
        )
        assert "auth" in result
        assert "notifications" not in result


# ---------------------------------------------------------------------------
# auth → orgs → notifications (the auth ↔ orgs cycle)
# ---------------------------------------------------------------------------


class TestAuthRequirements:
    """auth → orgs → notifications chain; the cycle terminates."""

    def test_auth_requires_orgs(self, modules_base_path: Path) -> None:
        """Selecting auth should materialize orgs and notifications."""
        result = resolve_required_modules(
            ["auth"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "notifications" in result
        assert result["orgs"] == {}

    def test_auth_with_orgs_already_selected(self, modules_base_path: Path) -> None:
        """auth with orgs already present should not duplicate."""
        result = resolve_required_modules(
            ["auth", "orgs"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" not in result
        assert "notifications" in result

    def test_auth_orgs_cycle_terminates(self, modules_base_path: Path) -> None:
        """The auth → orgs → auth edge is a cycle; resolution still ends."""
        result = resolve_required_modules(
            ["auth"],
            modules_base_path=modules_base_path,
        )
        assert set(result) == {"orgs", "notifications"}


# ---------------------------------------------------------------------------
# Multiple dependants
# ---------------------------------------------------------------------------


class TestMultipleDependants:
    """Several modules requiring the same target should deduplicate."""

    def test_billing_and_crm_require_orgs_once(self, modules_base_path: Path) -> None:
        """billing + crm should produce orgs once."""
        result = resolve_required_modules(
            ["billing", "crm"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_and_social_require_orgs_once(
        self, modules_base_path: Path
    ) -> None:
        """billing + social should produce orgs once."""
        result = resolve_required_modules(
            ["billing", "social"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_all_org_dependants_together(self, modules_base_path: Path) -> None:
        """billing + crm + social should materialize the closure only once."""
        result = resolve_required_modules(
            ["billing", "crm", "social"],
            modules_base_path=modules_base_path,
        )
        assert set(result) == {"orgs", "auth", "notifications"}

    def test_blog_and_listings_require_orgs(self, modules_base_path: Path) -> None:
        """blog and listings require orgs like the other dependants."""
        result = resolve_required_modules(
            ["blog", "listings"],
            modules_base_path=modules_base_path,
        )
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# Default modules_base_path
# ---------------------------------------------------------------------------


class TestDefaultModulesBasePath:
    """The default ``modules_base_path`` (without explicit argument) should
    resolve to the repo-root ``quickscale_modules/`` directory."""

    def test_default_path_resolves_billing_chain(self) -> None:
        """Calling without modules_base_path should find repo manifests."""
        result = resolve_required_modules(["billing"])
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result


# ---------------------------------------------------------------------------
# Bundled manifest fallback
# ---------------------------------------------------------------------------


class TestBundledManifestFallback:
    """resolve_required_modules falls back to bundled manifest snapshots
    when the source-tree modules workspace is unavailable."""

    def test_fallback_resolves_billing_chain(self) -> None:
        """billing → orgs → auth, notifications resolves from bundled
        manifests when get_modules_base_path raises ImproperlyConfigured."""
        with patch(
            "quickscale_core.manifest.required_modules.get_modules_base_path",
            side_effect=ImproperlyConfigured("no source tree"),
        ):
            result = resolve_required_modules(["billing"])
            assert "orgs" in result
            assert "auth" in result
            assert "notifications" in result

    def test_fallback_with_explicit_path_unaffected(self) -> None:
        """Explicitly passing modules_base_path still works—the fallback
        path is not invoked."""
        result = resolve_required_modules([], modules_base_path=Path("/nonexistent"))
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
            "required_modules:\n"
            "  - orgs\n"
        )
        orgs_dir = tmp_path / "orgs"
        orgs_dir.mkdir()
        (orgs_dir / "module.yml").write_text(
            "name: orgs\n"
            'version: "1.0.0"\n'
            "config:\n"
            "  mutable: {}\n"
            "  immutable: {}\n"
            "required_modules: []\n"
        )

        # Even with source tree unavailable, explicit path is honoured.
        with patch(
            "quickscale_core.manifest.required_modules.get_modules_base_path",
            side_effect=ImproperlyConfigured("no source tree"),
        ):
            result = resolve_required_modules(
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
                "quickscale_core.manifest.required_modules.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.required_modules.get_bundled_manifests_path",
                return_value=bundle_dir,
            ),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_required_modules(["billing"])

    def test_fallback_required_manifest_missing_raises(self, tmp_path: Path) -> None:
        """Bundled fallback: a transitive required module missing from
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
            "required_modules:\n"
            "  - orgs\n"
        )
        # orgs directory exists but has no module.yml — missing chain link.
        orgs_dir = bundle_dir / "orgs"
        orgs_dir.mkdir()

        with (
            patch(
                "quickscale_core.manifest.required_modules.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.required_modules.get_bundled_manifests_path",
                return_value=bundle_dir,
            ),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_required_modules(["billing"])

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
                "quickscale_core.manifest.required_modules.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.required_modules.get_bundled_manifests_path",
                return_value=bundle_dir,
            ),
        ):
            with pytest.raises(ManifestError):
                resolve_required_modules(["billing"])

    def test_fallback_fail_hard_when_both_unavailable(self) -> None:
        """When both source-tree and bundled manifests are unavailable,
        ImproperlyConfigured is raised (fail-hard)."""
        with (
            patch(
                "quickscale_core.manifest.required_modules.get_modules_base_path",
                side_effect=ImproperlyConfigured("no source tree"),
            ),
            patch(
                "quickscale_core.manifest.required_modules.get_bundled_manifests_path",
                side_effect=ImproperlyConfigured("no bundled manifests"),
            ),
        ):
            with pytest.raises(ImproperlyConfigured):
                resolve_required_modules(["billing"])


# ---------------------------------------------------------------------------
# Fast in-monorepo fallback regression test
# ---------------------------------------------------------------------------


class TestFastFallbackRegression:
    """Monkeypatches ``get_modules_base_path`` to raise ``ImproperlyConfigured``
    and confirms that ``resolve_required_modules`` falls through to the
    bundled-manifest snapshots via ``get_bundled_manifests_path()``."""

    def test_fallback_resolves_billing_to_orgs(self) -> None:
        """Monkeypatch the source-tree path so the resolver falls back to
        bundled manifests and still resolves billing → orgs."""
        with patch(
            "quickscale_core.manifest.required_modules.get_modules_base_path",
            side_effect=ImproperlyConfigured("no source tree"),
        ):
            result = resolve_required_modules(["billing"])
            assert "orgs" in result
