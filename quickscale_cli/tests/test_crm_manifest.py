"""Tests for CRM module manifest configuration validation."""

from __future__ import annotations

from quickscale_core.contracts.resolvers import validate_crm_module_options


def test_validate_crm_module_options_valid() -> None:
    """Valid CRM options should produce no validation issues."""
    options = {
        "enable_api": True,
        "deals_per_page": 25,
        "contacts_per_page": 50,
    }
    issues = validate_crm_module_options(options)
    assert issues == []


def test_validate_crm_module_options_valid_none() -> None:
    """None options should resolve to defaults and produce no issues."""
    issues = validate_crm_module_options(None)
    assert issues == []


def test_validate_crm_module_options_deals_per_page_zero() -> None:
    """deals_per_page below 1 should produce a validation issue."""
    options = {
        "enable_api": True,
        "deals_per_page": 0,
        "contacts_per_page": 50,
    }
    issues = validate_crm_module_options(options)
    assert "modules.crm.deals_per_page must be at least 1" in issues


def test_validate_crm_module_options_contacts_per_page_zero() -> None:
    """contacts_per_page below 1 should produce a validation issue."""
    options = {
        "enable_api": True,
        "deals_per_page": 25,
        "contacts_per_page": 0,
    }
    issues = validate_crm_module_options(options)
    assert "modules.crm.contacts_per_page must be at least 1" in issues


def test_validate_crm_module_options_enable_api_rejects_non_bool() -> None:
    """enable_api string input should be rejected by validation."""
    options = {
        "enable_api": "yes",
        "deals_per_page": 25,
        "contacts_per_page": 50,
    }
    issues = validate_crm_module_options(options)
    # validate checks the raw input type before resolution, so truthy
    # strings like "yes" are caught as non-boolean.
    assert "modules.crm.enable_api must be boolean" in issues


def test_validate_crm_module_options_defaults() -> None:
    """Empty options should resolve to defaults and produce no issues."""
    issues = validate_crm_module_options({})
    assert issues == []
