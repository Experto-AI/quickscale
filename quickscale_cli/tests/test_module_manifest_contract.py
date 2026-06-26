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
from quickscale_core.contracts.module_catalog import get_discovered_module_entries
from quickscale_core.manifest.entry_point import MANIFEST_ADAPTER_REGISTRY
from quickscale_core.manifest.loader import load_manifest_from_path

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = REPO_ROOT / "quickscale_modules"

# Generator template directories used by the React/HTML showcase contract tests.
REACT_TEMPLATES_DIR = (
    REPO_ROOT
    / "quickscale_core"
    / "src"
    / "quickscale_core"
    / "generator"
    / "templates"
    / "themes"
    / "showcase_react"
)
HTML_TEMPLATES_DIR = (
    REPO_ROOT
    / "quickscale_core"
    / "src"
    / "quickscale_core"
    / "generator"
    / "templates"
    / "themes"
    / "showcase_html"
)

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

# Jinja2 control tags in a .j2 template can contain literal `}` characters (e.g.
# `{% endraw %}`, `{% endif %}`).  The Phase 3 React theme templates wrap
# TypeScript interface bodies in `{% raw %}` / `{% endraw %}` blocks so they
# can host conditional inclusion logic, which means a naive
# `text.split("interface QuickScaleModules {")[1].split("}")[0]` truncates
# the body at the first inner tag's `}` instead of the interface's actual
# closing brace.  Stripping all Jinja2 control tags before the split restores
# the intended behavior: every `}` left in the text is a real language brace.
_JINJA2_CONTROL_TAG_PATTERN = re.compile(r"\{%.*?%\}", re.DOTALL)


def _strip_jinja2_control_tags(template_text: str) -> str:
    """Remove Jinja2 control tags (`{% ... %}`) from a template string."""
    return _JINJA2_CONTROL_TAG_PATTERN.sub("", template_text)


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
    for entry in get_discovered_module_entries():
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
    for entry in get_discovered_module_entries():
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
    for entry in get_discovered_module_entries():
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
    for entry in get_discovered_module_entries():
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
    for entry in get_discovered_module_entries():
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


def test_all_catalog_modules_have_manifest_adapter() -> None:
    """Every selectable catalog module must have a registered manifest adapter.

    Prevents silent omissions like the v0.86.0 billing regression where
    'billing' was missing from the wiring dispatch and every generated
    project quietly had no billing INSTALLED_APPS entry, no billing settings,
    and no billing URL wiring.

    When adding a new module: register a manifest adapter in
    ``MANIFEST_ADAPTER_REGISTRY`` via ``quickscale_core.manifest.entry_point``.
    """
    unwired = [
        entry.name
        for entry in get_discovered_module_entries()
        if entry.name not in MANIFEST_ADAPTER_REGISTRY
    ]

    assert not unwired, (
        f"Modules missing from MANIFEST_ADAPTER_REGISTRY: {unwired}. "
        "Register a manifest adapter in quickscale_core.manifest.entry_point."
    )


# ---------------------------------------------------------------------------
# Theme showcase coverage contracts
#
# These frozensets document *intentional* omissions from the two showcase
# themes.  Before adding a new module to the catalog ask: does it have a
# user-facing content card?  If not, add its name here with a comment.
#
# _REACT_UI_EXCLUDED_MODULES  – modules that must NOT appear in
#     window.__QUICKSCALE__.modules (index.html.j2) or the QuickScaleModules
#     TypeScript interface (useModules.ts.j2).
#
# _HTML_THEME_EXCLUDED_MODULES – modules that must NOT have a card in the
#     HTML showcase module grid (showcase_html/templates/index.html.j2).
# ---------------------------------------------------------------------------

_REACT_UI_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "orgs",  # transparent infrastructure (TenantMiddleware + multi-tenancy), no content page
        "analytics",  # background PostHog tracking, no content page
    }
)

_HTML_THEME_EXCLUDED_MODULES: frozenset[str] = frozenset(
    {
        "orgs",  # transparent infrastructure (TenantMiddleware + multi-tenancy), no content page
        "analytics",  # background PostHog tracking, no content page
        "social",  # surfaced in base.html top-nav via QUICKSCALE_SOCIAL_*_ENABLED flags, not a card
    }
)


def test_all_catalog_modules_in_react_index_html_modules_block() -> None:
    """Every UI-visible catalog module must appear in window.__QUICKSCALE__.modules
    in the React theme's index.html.j2.

    Without this entry the module's presence flag is never set in the React
    runtime config, so every React component that gates on modules.{name} will
    silently never activate.

    When adding a new module: add a line to the modules: { } block in
    index.html.j2, or add the name to _REACT_UI_EXCLUDED_MODULES if the module
    is intentionally infrastructure-only with no UI card.
    """
    index_html = (REACT_TEMPLATES_DIR / "templates" / "index.html.j2").read_text()
    # Extract just the modules: { ... } object (terminates before owner: {)
    modules_block = index_html.split("modules: {")[1].split("owner: {")[0]

    missing = [
        entry.name
        for entry in get_discovered_module_entries()
        if entry.name not in _REACT_UI_EXCLUDED_MODULES
        and f"{entry.name}:" not in modules_block
    ]
    assert not missing, (
        f"Modules missing from window.__QUICKSCALE__.modules in index.html.j2: {missing!r}. "
        "Add the module entry or add the name to _REACT_UI_EXCLUDED_MODULES."
    )


def test_all_catalog_modules_in_react_typescript_interface() -> None:
    """Every UI-visible catalog module must appear in the QuickScaleModules
    TypeScript interface in useModules.ts.j2.

    A missing field means TypeScript does not know the module flag exists, so
    reading modules.{name} in any React component is a compile-time type error.

    When adding a new module: add a '{name}: boolean' line to the
    QuickScaleModules interface, or add the name to _REACT_UI_EXCLUDED_MODULES.
    """
    use_modules = _strip_jinja2_control_tags(
        (REACT_TEMPLATES_DIR / "src" / "hooks" / "useModules.ts.j2").read_text()
    )
    # Extract only the QuickScaleModules interface body
    interface_block = use_modules.split("interface QuickScaleModules {")[1].split("}")[
        0
    ]

    missing = [
        entry.name
        for entry in get_discovered_module_entries()
        if entry.name not in _REACT_UI_EXCLUDED_MODULES
        and f"{entry.name}: boolean" not in interface_block
    ]
    assert not missing, (
        f"Modules missing from QuickScaleModules interface in useModules.ts.j2: {missing!r}. "
        "Add the field or add the name to _REACT_UI_EXCLUDED_MODULES."
    )


def test_react_index_html_and_typescript_interface_module_sets_are_symmetric() -> None:
    """The module keys in index.html.j2 and useModules.ts.j2 must be identical.

    Asymmetry means the React runtime config and the TypeScript type declarations
    disagree: either a runtime key has no matching type or a typed field is never
    set at runtime.
    """
    index_html = (REACT_TEMPLATES_DIR / "templates" / "index.html.j2").read_text()
    use_modules = _strip_jinja2_control_tags(
        (REACT_TEMPLATES_DIR / "src" / "hooks" / "useModules.ts.j2").read_text()
    )

    modules_block = index_html.split("modules: {")[1].split("owner: {")[0]
    html_modules = set(re.findall(r"\b(\w+):\s+\{%", modules_block))

    interface_block = use_modules.split("interface QuickScaleModules {")[1].split("}")[
        0
    ]
    ts_modules = set(re.findall(r"^\s+(\w+):\s+boolean", interface_block, re.MULTILINE))

    assert html_modules == ts_modules, (
        "index.html.j2 and useModules.ts.j2 module sets diverge.\n"
        f"  In index.html.j2 only: {sorted(html_modules - ts_modules)}\n"
        f"  In useModules.ts.j2 only: {sorted(ts_modules - html_modules)}"
    )


def test_all_catalog_modules_have_html_theme_card() -> None:
    """Every UI-visible catalog module must have a module card in the HTML
    showcase's index.html.j2.

    Without a card the module is silently invisible on the HTML theme landing
    page — the user has no entry point to the installed module.

    When adding a new module: add a card block guarded by
    {% if 'quickscale_modules_{name}' in settings.INSTALLED_APPS %}, or add
    the name to _HTML_THEME_EXCLUDED_MODULES if the module is intentionally
    excluded from the HTML grid.
    """
    index_html = (HTML_TEMPLATES_DIR / "templates" / "index.html.j2").read_text()

    missing = [
        entry.name
        for entry in get_discovered_module_entries()
        if entry.name not in _HTML_THEME_EXCLUDED_MODULES
        and f"quickscale_modules_{entry.name}" not in index_html
    ]
    assert not missing, (
        f"Modules missing from HTML theme index.html.j2 module grid: {missing!r}. "
        "Add a module card or add the name to _HTML_THEME_EXCLUDED_MODULES."
    )


def test_html_theme_empty_state_includes_all_card_modules() -> None:
    """The HTML theme empty-state guard must cover every module that has a card.

    The empty-state message ('No modules installed') is shown only when none of
    the known card modules are in INSTALLED_APPS.  If a module has a card but is
    absent from the guard, the empty-state hides as soon as that module is active
    but re-appears for any combination that omits only the missing module.

    When adding a new HTML theme card: also add the module to the
    {% if 'quickscale_modules_{name}' not in settings.INSTALLED_APPS and ... %}
    empty-state condition at the bottom of the module-grid section.
    """
    index_html = (HTML_TEMPLATES_DIR / "templates" / "index.html.j2").read_text()

    card_modules = [
        entry.name
        for entry in get_discovered_module_entries()
        if entry.name not in _HTML_THEME_EXCLUDED_MODULES
    ]
    not_in_empty_state = [
        name
        for name in card_modules
        if f"'quickscale_modules_{name}' not in settings.INSTALLED_APPS"
        not in index_html
    ]
    assert not not_in_empty_state, (
        f"Modules with cards but absent from HTML empty-state guard: {not_in_empty_state!r}. "
        "Add each module to the final {% if ... not in ... %} empty-state condition."
    )
