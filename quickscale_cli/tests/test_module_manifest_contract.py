"""Contract tests for module manifests and configurator defaults."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

from quickscale_cli.commands.module_config import (
    get_default_analytics_config,
    get_default_auth_config,
    get_default_backups_config,
    get_default_blog_config,
    get_default_crm_config,
    get_default_forms_config,
    get_default_listings_config,
    get_default_social_config,
    get_default_storage_config,
)
from quickscale_cli.commands.module_wiring_specs import MODULE_WIRING_BUILDERS
from quickscale_cli.module_catalog import get_module_entries
from quickscale_core.manifest.loader import load_manifest_from_path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = REPO_ROOT / "quickscale_modules"

DEFAULT_CONFIG_FACTORIES = {
    "analytics": get_default_analytics_config,
    "auth": get_default_auth_config,
    "blog": get_default_blog_config,
    "listings": get_default_listings_config,
    "crm": get_default_crm_config,
    "forms": get_default_forms_config,
    "storage": get_default_storage_config,
    "backups": get_default_backups_config,
    "social": get_default_social_config,
}

BASE_RUNTIME_DEPENDENCY_NAMES = {"django", "python"}
FIRST_PARTY_MODULE_PACKAGE_PREFIX = "quickscale-module-"
MANIFEST_DEPENDENCY_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_.-]+")
SETTING_NAME_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]*$")
VERSION_EXPORT_PATTERN = re.compile(r'^__version__ = "([^"]+)"$', re.MULTILINE)


def _manifest_path(module_name: str) -> Path:
    return MODULES_ROOT / module_name / "module.yml"


def _pyproject_path(module_name: str) -> Path:
    return MODULES_ROOT / module_name / "pyproject.toml"


def _package_init_path(module_name: str) -> Path:
    return (
        MODULES_ROOT
        / module_name
        / "src"
        / f"quickscale_modules_{module_name}"
        / "__init__.py"
    )


def _pyproject_data(module_name: str) -> dict[str, object]:
    return tomllib.loads(_pyproject_path(module_name).read_text())


def _manifest_dependency_names(module_name: str) -> set[str]:
    manifest = load_manifest_from_path(_manifest_path(module_name))
    dependency_names: set[str] = set()

    for dependency in manifest.dependencies:
        if isinstance(dependency, dict):
            dependency_spec = dependency.get("dependency_name") or dependency.get(
                "name"
            )
        else:
            dependency_spec = getattr(dependency, "dependency_name", dependency)

        assert isinstance(dependency_spec, str), (
            f"{module_name} manifest dependency must be string-like: {dependency!r}"
        )

        dependency_match = MANIFEST_DEPENDENCY_NAME_PATTERN.match(
            dependency_spec.strip()
        )
        assert dependency_match is not None, (
            f"{module_name} manifest dependency is missing a package name: {dependency_spec}"
        )

        dependency_names.add(dependency_match.group(0).lower())

    return dependency_names


def _runtime_dependency_names(module_name: str) -> set[str]:
    pyproject = _pyproject_data(module_name)
    poetry_dependencies = pyproject["tool"]["poetry"]["dependencies"]
    assert isinstance(poetry_dependencies, dict)

    return {
        dependency_name.lower()
        for dependency_name in poetry_dependencies
        if dependency_name.lower() not in BASE_RUNTIME_DEPENDENCY_NAMES
        and not dependency_name.lower().startswith(FIRST_PARTY_MODULE_PACKAGE_PREFIX)
    }


def _runtime_module_dependency_names(module_name: str) -> set[str]:
    pyproject = _pyproject_data(module_name)
    poetry_dependencies = pyproject["tool"]["poetry"]["dependencies"]
    assert isinstance(poetry_dependencies, dict)

    return {
        dependency_name.lower()
        for dependency_name in poetry_dependencies
        if dependency_name.lower().startswith(FIRST_PARTY_MODULE_PACKAGE_PREFIX)
    }


def _required_module_package_names(module_name: str) -> set[str]:
    manifest = load_manifest_from_path(_manifest_path(module_name))
    return {
        f"{FIRST_PARTY_MODULE_PACKAGE_PREFIX}{required_module}".lower()
        for required_module in manifest.required_modules
    }


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


def test_ready_packaged_module_versions_match_manifest_version() -> None:
    """Ready packaged modules must keep manifest, pyproject, and __version__ aligned."""
    for entry in get_module_entries(include_experimental=False):
        module_name = entry.name
        manifest = load_manifest_from_path(_manifest_path(module_name))
        pyproject_version = _pyproject_data(module_name)["project"]["version"]
        package_init_path = _package_init_path(module_name)

        version_match = None
        if package_init_path.exists():
            version_match = VERSION_EXPORT_PATTERN.search(package_init_path.read_text())

        assert pyproject_version == manifest.version, (
            f"{module_name} pyproject version should match module.yml: "
            f"pyproject={pyproject_version} manifest={manifest.version}"
        )

        if package_init_path.exists():
            assert version_match is not None, (
                f"{module_name} package should export __version__ in __init__.py"
            )
            assert version_match.group(1) == manifest.version, (
                f"{module_name} __version__ should match module.yml: "
                f"package={version_match.group(1)} manifest={manifest.version}"
            )


def test_ready_packaged_module_dependency_names_match_pyproject_runtime_dependencies() -> (
    None
):
    """Ready packaged modules must keep third-party dependency names aligned."""
    for entry in get_module_entries(include_experimental=False):
        module_name = entry.name
        manifest_dependency_names = _manifest_dependency_names(module_name)
        runtime_dependency_names = _runtime_dependency_names(module_name)

        assert manifest_dependency_names == runtime_dependency_names, (
            f"{module_name} manifest dependencies should match pyproject runtime packages: "
            f"manifest={sorted(manifest_dependency_names)} "
            f"pyproject={sorted(runtime_dependency_names)}"
        )


def test_ready_packaged_module_required_modules_match_pyproject_first_party_dependencies() -> (
    None
):
    """Required module metadata must align with first-party package dependencies."""
    for entry in get_module_entries(include_experimental=False):
        module_name = entry.name
        required_module_packages = _required_module_package_names(module_name)
        runtime_module_dependencies = _runtime_module_dependency_names(module_name)

        assert required_module_packages == runtime_module_dependencies, (
            f"{module_name} required_modules should match first-party package dependencies: "
            f"manifest={sorted(required_module_packages)} "
            f"pyproject={sorted(runtime_module_dependencies)}"
        )


def test_storage_cloud_dependencies_are_optional_and_exposed_via_cloud_extra() -> None:
    """Storage should keep cloud packages opt-in for local generated projects."""
    pyproject = _pyproject_data("storage")
    dependencies = pyproject["tool"]["poetry"]["dependencies"]
    extras = pyproject["tool"]["poetry"]["extras"]
    assert isinstance(dependencies, dict)
    assert isinstance(extras, dict)
    django_storages_dependency = dependencies["django-storages"]
    boto3_dependency = dependencies["boto3"]
    assert isinstance(django_storages_dependency, dict)
    assert isinstance(boto3_dependency, dict)

    assert django_storages_dependency["optional"] is True
    assert boto3_dependency["optional"] is True
    assert extras["cloud"] == ["django-storages", "boto3"]


def test_forms_manifest_no_longer_ships_dead_storage_backend_option() -> None:
    """Forms should not expose immutable options that have no runtime effect."""
    manifest = load_manifest_from_path(_manifest_path("forms"))

    assert "storage_backend" not in manifest.get_all_options()


def test_blog_api_rate_limit_default_matches_manifest_contract() -> None:
    """Blog API rate-limit defaults should stay aligned across CLI and manifest."""
    manifest = load_manifest_from_path(_manifest_path("blog"))
    option = manifest.get_all_options()["api_rate_limit"]
    defaults = get_default_blog_config()

    assert option.django_setting == "BLOG_API_RATE_LIMIT"
    assert option.default == defaults["api_rate_limit"] == "5/hour"


# Modules with special-case handling inside build_module_wiring_specs that are
# intentionally absent from MODULE_WIRING_BUILDERS (e.g. social generates managed
# backend transport files and therefore needs project_package at wiring time).
_SPECIAL_CASE_WIRING_MODULES: frozenset[str] = frozenset({"social"})


def test_all_catalog_modules_have_wiring_builder() -> None:
    """Every selectable catalog module must have a registered wiring builder.

    Prevents silent omissions like the v0.86.0 billing regression where
    'billing' was missing from MODULE_WIRING_BUILDERS and every generated
    project quietly had no billing INSTALLED_APPS entry, no billing settings,
    and no billing URL wiring.

    When adding a new module: add a _<name>_wiring() function in
    module_wiring_specs.py and register it in MODULE_WIRING_BUILDERS, or add
    the module name to _SPECIAL_CASE_WIRING_MODULES if it requires custom
    handling inside build_module_wiring_specs.
    """
    unwired = [
        entry.name
        for entry in get_module_entries(include_experimental=False)
        if entry.name not in MODULE_WIRING_BUILDERS
        and entry.name not in _SPECIAL_CASE_WIRING_MODULES
    ]

    assert not unwired, (
        f"Modules missing from MODULE_WIRING_BUILDERS: {unwired}. "
        "Add a wiring builder function and register it in MODULE_WIRING_BUILDERS, "
        "or add the module name to _SPECIAL_CASE_WIRING_MODULES in this test file "
        "if it has custom handling in build_module_wiring_specs."
    )
