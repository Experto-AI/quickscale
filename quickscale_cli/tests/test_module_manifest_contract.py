"""Contract tests for module manifests and configurator defaults."""

from __future__ import annotations

import re
from pathlib import Path

from quickscale_cli.commands.module_config import (
    get_default_auth_config,
    get_default_blog_config,
    get_default_crm_config,
    get_default_forms_config,
    get_default_listings_config,
)
from quickscale_cli.module_catalog import get_module_entries
from quickscale_core.manifest.loader import load_manifest_from_path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = REPO_ROOT / "quickscale_modules"

DEFAULT_CONFIG_FACTORIES = {
    "auth": get_default_auth_config,
    "blog": get_default_blog_config,
    "listings": get_default_listings_config,
    "crm": get_default_crm_config,
    "forms": get_default_forms_config,
}

SETTING_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _manifest_path(module_name: str) -> Path:
    return MODULES_ROOT / module_name / "module.yml"


def test_ready_modules_have_valid_manifest() -> None:
    """Every catalog-ready module must have a valid module.yml manifest."""
    for entry in get_module_entries(include_experimental=False):
        manifest_path = _manifest_path(entry.name)
        assert manifest_path.exists(), f"Missing manifest: {manifest_path}"

        manifest = load_manifest_from_path(manifest_path)
        assert manifest.name == entry.name


def test_configurator_defaults_match_manifest_option_keys() -> None:
    """Configurator default keys must align with manifest option keys."""
    for module_name, factory in DEFAULT_CONFIG_FACTORIES.items():
        manifest = load_manifest_from_path(_manifest_path(module_name))
        manifest_keys = set(manifest.get_all_options().keys())
        default_keys = set(factory().keys())

        assert default_keys == manifest_keys, (
            f"Default config keys mismatch for '{module_name}': "
            f"defaults={sorted(default_keys)} manifest={sorted(manifest_keys)}"
        )


def test_mutable_options_map_to_valid_django_settings() -> None:
    """Mutable options must declare valid Django setting names."""
    for entry in get_module_entries(include_experimental=False):
        manifest = load_manifest_from_path(_manifest_path(entry.name))

        for option_name, option in manifest.mutable_options.items():
            assert option.django_setting, (
                f"Mutable option '{entry.name}.{option_name}' must define django_setting"
            )
            assert SETTING_NAME_PATTERN.match(option.django_setting), (
                f"Invalid django_setting for '{entry.name}.{option_name}': "
                f"{option.django_setting}"
            )
