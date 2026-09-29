"""Contract tests for the orgs module's manifest-owned configuration.

The orgs option defaults, normalization, and validation are declared in
``quickscale_modules/orgs/module.yml`` and enforced through the shared manifest
engine; its CLI configurator is the one generic manifest-driven configurator.
These tests pin that contract and the operator-facing behaviour it produces.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from quickscale_cli.commands.module_config import MODULE_CONFIGURATOR_REGISTRY
from quickscale_core.contracts.resolvers import (
    load_module_manifest_with_fallback,
    resolve_manifest_module_options,
)
from quickscale_core.manifest.option_validation import validate_module_options

_EXPECTED_DEFAULTS: dict[str, object] = {"mode": "solo"}
_MODES = ["solo", "saas"]


def _manifest():
    return load_module_manifest_with_fallback("orgs")


# ===========================================================================
# 1. Manifest declarations
# ===========================================================================


class TestManifestDeclaration:
    """The manifest owns the option set, choices, and normalization rules."""

    def test_defaults_match_the_manifest(self) -> None:
        assert resolve_manifest_module_options("orgs") == _EXPECTED_DEFAULTS

    def test_mode_choices_are_declared(self) -> None:
        option = _manifest().get_option("mode")
        assert option is not None
        assert option.validation.get("choices") == _MODES

    def test_mode_normalization_rules_are_declared(self) -> None:
        derivation = _manifest().option_derivations["mode"]
        rule_types = [rule["rule_type"] for rule in derivation["normalization_rules"]]
        assert rule_types == ["strip", "lowercase"]


# ===========================================================================
# 2. Resolution through the generic resolver
# ===========================================================================


class TestOrgResolution:
    """The generic resolver merges defaults with canonicalized overrides."""

    def test_no_overrides_returns_defaults(self) -> None:
        assert resolve_manifest_module_options("orgs") == _EXPECTED_DEFAULTS

    def test_saas_mode_override(self) -> None:
        assert resolve_manifest_module_options("orgs", {"mode": "saas"}) == {
            "mode": "saas"
        }

    def test_mode_is_stripped_and_lowercased(self) -> None:
        assert resolve_manifest_module_options("orgs", {"mode": "  SaaS  "}) == {
            "mode": "saas"
        }

    def test_invalid_mode_passes_through_resolution(self) -> None:
        """SA27: resolution does not coerce an invalid mode; validation refuses."""
        assert resolve_manifest_module_options("orgs", {"mode": "team"}) == {
            "mode": "team"
        }

    def test_blank_mode_resolves_to_empty(self) -> None:
        assert resolve_manifest_module_options("orgs", {"mode": "   "}) == {"mode": ""}

    def test_resolution_is_idempotent(self) -> None:
        resolved = resolve_manifest_module_options("orgs", {"mode": " SaaS "})
        assert resolve_manifest_module_options("orgs", resolved) == resolved

    def test_resolved_keys_match_the_manifest(self) -> None:
        resolved = resolve_manifest_module_options("orgs", {"mode": "saas"})
        assert set(resolved.keys()) == set(_EXPECTED_DEFAULTS.keys())


# ===========================================================================
# 3. Validation through the shared engine
# ===========================================================================


class TestOrgValidation:
    """The engine refuses a mode outside the manifest's declared choices."""

    def test_defaults_pass_validation(self) -> None:
        assert validate_module_options(_manifest(), _EXPECTED_DEFAULTS) == []

    @pytest.mark.parametrize("mode", _MODES)
    def test_valid_modes_pass_validation(self, mode: str) -> None:
        assert validate_module_options(_manifest(), {"mode": mode}) == []

    def test_mixed_case_modes_are_canonicalized_before_the_check(self) -> None:
        assert validate_module_options(_manifest(), {"mode": "Solo"}) == []
        assert validate_module_options(_manifest(), {"mode": "SAAS"}) == []

    @pytest.mark.parametrize("invalid_mode", ["team", "enterprise", "INVALID", "0"])
    def test_invalid_mode_fails_validation(self, invalid_mode: str) -> None:
        issues = validate_module_options(_manifest(), {"mode": invalid_mode})
        assert len(issues) >= 1
        assert any("modules.orgs.mode" in issue for issue in issues)
        assert any("solo" in issue and "saas" in issue for issue in issues)

    def test_blank_mode_fails_validation(self) -> None:
        issues = validate_module_options(_manifest(), {"mode": ""})
        assert any("modules.orgs.mode" in issue for issue in issues)


# ===========================================================================
# 4. CLI configurator behaviour
# ===========================================================================


class TestOrgConfigurator:
    """The CLI configurator's prompts and defaults come from the manifest."""

    def test_defaults_factory_reads_the_manifest(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["orgs"]
        assert entry.get_defaults() == _EXPECTED_DEFAULTS

    def test_non_interactive_configuration_uses_manifest_defaults(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["orgs"]
        assert entry.configure(non_interactive=True) == _EXPECTED_DEFAULTS

    def test_existing_declared_values_are_canonicalized(self) -> None:
        entry = MODULE_CONFIGURATOR_REGISTRY["orgs"]
        config = entry.configure(
            non_interactive=True, existing_config={"mode": "  SaaS  "}
        )
        assert config == {"mode": "saas"}

    @patch("quickscale_cli.commands.module_config.click.prompt")
    def test_interactive_prompt_reads_the_manifest(self, mock_prompt) -> None:
        mock_prompt.return_value = "saas"

        entry = MODULE_CONFIGURATOR_REGISTRY["orgs"]
        config = entry.configure(non_interactive=False)

        assert config == {"mode": "saas"}
        _, kwargs = mock_prompt.call_args
        choice = kwargs["type"]
        assert list(choice.choices) == _MODES
