"""Tests for required-module materialization.

Tests the planner/apply seam that materializes required module dependencies
(e.g. selecting "social" automatically materializes "orgs" and its own
required closure).
"""

from quickscale_core.manifest.required_modules import resolve_required_modules


class TestResolveRequiredModules:
    """Regression tests for the planner/apply required-module seam."""

    def test_empty_modules_returns_empty(self) -> None:
        """No selected modules should produce no required configs."""
        result = resolve_required_modules([])
        assert result == {}

    def test_no_requirements_for_standalone_modules(self) -> None:
        """Modules without requirements should not trigger new configs."""
        result = resolve_required_modules(["storage"])
        assert result == {}

    def test_single_module_without_requirements_returns_empty(self) -> None:
        """A module that requires nothing returns empty."""
        result = resolve_required_modules(["notifications"])
        assert result == {}

    # --- billing -> orgs -> auth, notifications ---

    def test_billing_requires_orgs(self) -> None:
        """Selecting billing should materialize orgs."""
        result = resolve_required_modules(["billing"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_with_orgs_already_selected(self) -> None:
        """billing with orgs already present should not duplicate orgs."""
        result = resolve_required_modules(["billing", "orgs"])
        assert "orgs" not in result

    # --- crm -> orgs ---

    def test_crm_requires_orgs(self) -> None:
        """Selecting crm should materialize orgs."""
        result = resolve_required_modules(["crm"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_crm_with_orgs_already_selected(self) -> None:
        """crm with orgs already present should not duplicate orgs."""
        result = resolve_required_modules(["crm", "orgs"])
        assert "orgs" not in result

    # --- social -> orgs ---

    def test_social_requires_orgs(self) -> None:
        """Selecting social should materialize orgs."""
        result = resolve_required_modules(["social"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_social_with_orgs_already_selected(self) -> None:
        """social with orgs already present should not duplicate orgs."""
        result = resolve_required_modules(["social", "orgs"])
        assert "orgs" not in result

    # --- listings -> orgs ---

    def test_listings_requires_orgs(self) -> None:
        """Selecting listings should materialize orgs."""
        result = resolve_required_modules(["listings"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_listings_with_orgs_already_selected(self) -> None:
        """listings with orgs already present should not duplicate orgs."""
        result = resolve_required_modules(["listings", "orgs"])
        assert "orgs" not in result

    # --- orgs -> auth, notifications ---

    def test_orgs_requires_auth_and_notifications(self) -> None:
        """Selecting orgs should materialize auth and notifications."""
        result = resolve_required_modules(["orgs"])
        assert "auth" in result
        assert "notifications" in result
        config = result["notifications"]
        assert isinstance(config, dict)
        assert config == {}

    def test_orgs_with_notifications_already_selected(self) -> None:
        """orgs with notifications already present should not duplicate."""
        result = resolve_required_modules(["orgs", "notifications"])
        assert "auth" in result
        assert "notifications" not in result

    # --- multiple dependants ---

    def test_billing_and_crm_require_orgs_only_once(self) -> None:
        """Multiple dependants (billing + crm) should produce orgs once."""
        result = resolve_required_modules(["billing", "crm"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_and_social_require_orgs_only_once(self) -> None:
        """Multiple dependants (billing + social) should produce orgs once."""
        result = resolve_required_modules(["billing", "social"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_all_org_dependants_together(self) -> None:
        """billing + crm + social materialize the closure only once."""
        result = resolve_required_modules(["billing", "crm", "social"])
        assert set(result) == {"orgs", "auth", "notifications"}

    def test_full_chain_billing(self) -> None:
        """Chain: billing → orgs → auth, notifications materializes all."""
        result = resolve_required_modules(["billing"])
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result
        assert result["orgs"] == {}

    def test_full_chain_social(self) -> None:
        """Chain: social → orgs → auth, notifications materializes all."""
        result = resolve_required_modules(["social"])
        assert "orgs" in result
        assert "auth" in result
        assert "notifications" in result
        assert result["orgs"] == {}

    # --- auth -> orgs (Cluster A) ---

    def test_auth_requires_orgs(self) -> None:
        """Selecting auth should materialize orgs."""
        result = resolve_required_modules(["auth"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_auth_with_orgs_already_selected(self) -> None:
        """auth with orgs already present should not duplicate orgs."""
        result = resolve_required_modules(["auth", "orgs"])
        assert "orgs" not in result

    def test_auth_chain_requires_notifications(self) -> None:
        """Chain: auth → orgs → notifications should materialize both."""
        result = resolve_required_modules(["auth"])
        assert "orgs" in result
        assert "notifications" in result
        assert result["orgs"] == {}

    def test_case_sensitivity(self) -> None:
        """Module names are case-sensitive; wrong case returns empty."""
        result = resolve_required_modules(["Social"])
        assert result == {}
