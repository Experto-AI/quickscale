"""Tests for implied_module_defaults.py — module implication materialization.

Tests the planner/apply seam that materializes implicit module dependencies
(e.g. selecting "social" should automatically materialize "orgs").
"""

from quickscale_cli.commands.implied_module_defaults import (
    get_implied_module_default_configs,
)


class TestGetImpliedModuleDefaultConfigs:
    """Regression tests for the planner/apply implication seam."""

    def test_empty_modules_returns_empty(self) -> None:
        """No selected modules should produce no implied configs."""
        result = get_implied_module_default_configs([])
        assert result == {}

    def test_no_implication_for_standalone_modules(self) -> None:
        """Modules without implications should not trigger new configs."""
        result = get_implied_module_default_configs(["auth", "storage"])
        assert result == {}

    def test_single_module_no_match_returns_empty(self) -> None:
        """A single module that doesn't imply anything returns empty."""
        result = get_implied_module_default_configs(["notifications"])
        assert result == {}

    # --- billing -> orgs ---

    def test_billing_implies_orgs(self) -> None:
        """Selecting billing should materialize orgs."""
        result = get_implied_module_default_configs(["billing"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_with_orgs_already_selected(self) -> None:
        """billing with orgs already present should not duplicate orgs."""
        result = get_implied_module_default_configs(["billing", "orgs"])
        assert "orgs" not in result

    # --- crm -> orgs ---

    def test_crm_implies_orgs(self) -> None:
        """Selecting crm should materialize orgs."""
        result = get_implied_module_default_configs(["crm"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_crm_with_orgs_already_selected(self) -> None:
        """crm with orgs already present should not duplicate orgs."""
        result = get_implied_module_default_configs(["crm", "orgs"])
        assert "orgs" not in result

    # --- social -> orgs (FIX for SOCIAL-CR-002) ---

    def test_social_implies_orgs(self) -> None:
        """Selecting social should materialize orgs.

        Regression for SOCIAL-CR-002: social/module.yml declares
        ``required_modules: [orgs]`` but the planner/apply flow
        was not materializing orgs when social was selected.
        """
        result = get_implied_module_default_configs(["social"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_social_with_orgs_already_selected(self) -> None:
        """social with orgs already present should not duplicate orgs."""
        result = get_implied_module_default_configs(["social", "orgs"])
        assert "orgs" not in result

    # --- orgs -> notifications ---

    def test_orgs_implies_notifications(self) -> None:
        """Selecting orgs should materialize notifications with default config."""
        result = get_implied_module_default_configs(["orgs"])
        assert "notifications" in result
        config = result["notifications"]
        assert isinstance(config, dict)
        # notifications gets a non-empty default config dict
        assert config != {}

    def test_orgs_with_notifications_already_selected(self) -> None:
        """orgs with notifications already present should not duplicate."""
        result = get_implied_module_default_configs(["orgs", "notifications"])
        assert "notifications" not in result

    # --- multiple implicators ---

    def test_billing_and_crm_imply_orgs_only_once(self) -> None:
        """Multiple implicators (billing + crm) should produce orgs once."""
        result = get_implied_module_default_configs(["billing", "crm"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_billing_and_social_imply_orgs_only_once(self) -> None:
        """Multiple implicators (billing + social) should produce orgs once."""
        result = get_implied_module_default_configs(["billing", "social"])
        assert "orgs" in result
        assert result["orgs"] == {}

    def test_all_org_implicators_together(self) -> None:
        """billing + crm + social should materialize orgs only once.

        Since orgs is materialized by all three, the orgs → notifications
        chain fires once as expected.
        """
        result = get_implied_module_default_configs(["billing", "crm", "social"])
        assert "orgs" in result
        assert result["orgs"] == {}
        # orgs → notifications chain fires once since orgs is materialized
        assert "notifications" in result

    def test_full_chain_billing_implies_orgs_implies_notifications(self) -> None:
        """Chain: billing → orgs → notifications should materialize both."""
        result = get_implied_module_default_configs(["billing"])
        assert "orgs" in result
        assert "notifications" in result
        assert result["orgs"] == {}

    def test_full_chain_social_implies_orgs_implies_notifications(self) -> None:
        """Chain: social → orgs → notifications should materialize both."""
        result = get_implied_module_default_configs(["social"])
        assert "orgs" in result
        assert "notifications" in result
        assert result["orgs"] == {}

    # --- existing behavior preservation ---

    def test_billing_orgs_notifications_chain_preserved(self) -> None:
        """billing → orgs → notifications chain still works unchanged."""
        result = get_implied_module_default_configs(["billing"])
        assert "orgs" in result
        assert "notifications" in result

    def test_crm_orgs_chain_preserved(self) -> None:
        """crm → orgs chain still works unchanged."""
        result = get_implied_module_default_configs(["crm"])
        assert "orgs" in result

    def test_unaffected_module_does_not_trigger(self) -> None:
        """A selected module with no implications changes nothing."""
        result = get_implied_module_default_configs(["auth"])
        assert result == {}

    def test_case_sensitivity(self) -> None:
        """Module names are case-sensitive; wrong case returns empty."""
        result = get_implied_module_default_configs(["Social"])
        assert result == {}
