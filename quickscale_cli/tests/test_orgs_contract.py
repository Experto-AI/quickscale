"""Contract tests for the ready-state orgs module integration."""

from quickscale_cli.commands.module_wiring_specs import build_module_wiring_specs
from quickscale_cli.module_catalog import get_module_entry, get_module_names
from quickscale_cli.schema.config_schema import validate_config
from quickscale_core.module_wiring import collect_wiring


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


def test_orgs_wiring_spec_registers_runtime_surface() -> None:
    """Managed wiring should surface the orgs runtime in generated projects."""
    specs = build_module_wiring_specs({"orgs": {}}, project_package="myapp")

    orgs_spec = specs["orgs"]

    assert orgs_spec.apps == ("quickscale_modules_orgs",)
    assert orgs_spec.middleware == (
        "quickscale_modules_orgs.middleware.TenantMiddleware",
    )
    assert orgs_spec.settings == {
        "ACCOUNT_ADAPTER": "quickscale_modules_orgs.adapters.OrgsAccountAdapter",
        "QUICKSCALE_MODE": "solo",
    }
    assert orgs_spec.url_includes == (("", "quickscale_modules_orgs.urls"),)


def test_orgs_wiring_preserves_auth_contracts_when_both_are_selected() -> None:
    """Orgs should layer on top of auth without disturbing auth-owned apps and URLs."""
    specs = build_module_wiring_specs(
        {"auth": {}, "orgs": {}},
        project_package="myapp",
    )

    apps, middleware, settings, urls = collect_wiring(specs)

    assert "quickscale_modules_auth" in apps
    assert "quickscale_modules_orgs" in apps
    assert middleware.index(
        "allauth.account.middleware.AccountMiddleware"
    ) < middleware.index("quickscale_modules_orgs.middleware.TenantMiddleware")
    assert (
        settings["ACCOUNT_ADAPTER"]
        == "quickscale_modules_orgs.adapters.OrgsAccountAdapter"
    )
    assert ("accounts/", "allauth.urls") in urls
    assert ("", "quickscale_modules_orgs.urls") in urls
