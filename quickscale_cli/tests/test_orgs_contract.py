"""Contract tests for the ready-state orgs module integration."""

from quickscale_cli.module_catalog import get_module_entry, get_module_names
from quickscale_cli.schema.config_schema import validate_config


def test_orgs_catalog_entry_is_public_ready() -> None:
    """The orgs module should be visible as a shipped catalog entry."""
    entry = get_module_entry("orgs")

    assert entry is not None
    assert entry.ready is True
    assert "memberships" in entry.description


def test_orgs_is_in_ready_module_names() -> None:
    """Ready module names should surface orgs without experimental flags."""
    assert "orgs" in get_module_names(include_experimental=False)


def test_orgs_module_is_accepted_by_config_validation() -> None:
    """The config schema should accept orgs as a public-ready module."""
    yaml_content = """
version: "1"
project:
  slug: myapp
  package: myapp
modules:
  orgs:
"""

    config = validate_config(yaml_content)

    assert "orgs" in config.modules
