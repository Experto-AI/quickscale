"""Module Manifest Loader

Loads and validates module.yml manifest files.
"""

from pathlib import Path
from typing import Any

import yaml

from quickscale_core.manifest.schema import ConfigOption, ModuleManifest


class ManifestError(Exception):
    """Error loading or validating a module manifest"""

    def __init__(self, message: str, module_name: str | None = None):
        self.message = message
        self.module_name = module_name
        super().__init__(self._format_message())

    def _format_message(self) -> str:
        """Format error message with module name"""
        if self.module_name:
            return f"[{self.module_name}] {self.message}"
        return self.message


def _parse_config_option(
    name: str, data: dict[str, Any], mutability: str
) -> ConfigOption:
    """Parse a single config option from manifest data"""
    return ConfigOption(
        name=name,
        option_type=data.get("type", "string"),
        default=data.get("default"),
        django_setting=data.get("django_setting"),
        description=data.get("description", ""),
        mutability=mutability,  # type: ignore[arg-type]
        validation=data.get("validation", {}),
    )


def _parse_config_section(
    config_data: dict[str, Any], section: str
) -> dict[str, ConfigOption]:
    """Parse a config section (mutable or immutable)"""
    options = {}
    section_data = config_data.get(section, {})

    if not isinstance(section_data, dict):
        raise ManifestError(f"config.{section} must be a mapping")

    for option_name, option_data in section_data.items():
        if option_data is None:
            option_data = {}
        elif not isinstance(option_data, dict):
            raise ManifestError(
                f"config.{section}.{option_name} must be a mapping or empty"
            )

        options[option_name] = _parse_config_option(option_name, option_data, section)

    return options


def load_manifest(yaml_content: str, module_name: str | None = None) -> ModuleManifest:
    """Load and validate a module manifest from YAML content

    Args:
        yaml_content: Raw YAML string
        module_name: Optional module name for error messages

    Returns:
        ModuleManifest: Validated manifest object

    Raises:
        ManifestError: If validation fails

    """
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid YAML syntax: {e}", module_name) from e

    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a YAML mapping", module_name)

    # Validate required fields
    if "name" not in data:
        raise ManifestError("Missing required field 'name'", module_name)
    if "version" not in data:
        raise ManifestError("Missing required field 'version'", module_name)

    name = data["name"]
    version = data["version"]

    if not isinstance(name, str) or not name:
        raise ManifestError("'name' must be a non-empty string", module_name)
    if not isinstance(version, str) or not version:
        raise ManifestError("'version' must be a non-empty string", module_name)

    # Parse config section
    config_data = data.get("config", {})
    if not isinstance(config_data, dict):
        raise ManifestError("'config' must be a mapping", module_name)

    mutable_options = _parse_config_section(config_data, "mutable")
    immutable_options = _parse_config_section(config_data, "immutable")

    # Validate mutable options have django_setting
    for opt_name, option in mutable_options.items():
        if not option.django_setting:
            raise ManifestError(
                f"Mutable option '{opt_name}' must have 'django_setting' defined",
                module_name,
            )

    # Parse dependencies
    dependencies = data.get("dependencies", [])
    if not isinstance(dependencies, list):
        raise ManifestError("'dependencies' must be a list", module_name)

    # Parse django_apps
    django_apps = data.get("django_apps", [])
    if not isinstance(django_apps, list):
        raise ManifestError("'django_apps' must be a list", module_name)

    return ModuleManifest(
        name=name,
        version=version,
        description=data.get("description", ""),
        mutable_options=mutable_options,
        immutable_options=immutable_options,
        dependencies=dependencies,
        django_apps=django_apps,
    )


def load_manifest_from_path(manifest_path: Path) -> ModuleManifest:
    """Load a module manifest from a file path

    Args:
        manifest_path: Path to module.yml file

    Returns:
        ModuleManifest: Validated manifest object

    Raises:
        ManifestError: If file not found or validation fails

    """
    if not manifest_path.exists():
        raise ManifestError(f"Manifest file not found: {manifest_path}")

    try:
        yaml_content = manifest_path.read_text()
    except OSError as e:
        raise ManifestError(f"Failed to read manifest: {e}") from e

    # Extract module name from path (parent directory name)
    module_name = manifest_path.parent.name

    return load_manifest(yaml_content, module_name)


def get_manifest_for_module(
    project_path: Path, module_name: str
) -> ModuleManifest | None:
    """Get manifest for an embedded module in a project

    Args:
        project_path: Path to the project root
        module_name: Name of the module

    Returns:
        ModuleManifest if found, None otherwise

    """
    manifest_path = project_path / "modules" / module_name / "module.yml"
    if not manifest_path.exists():
        return None

    try:
        return load_manifest_from_path(manifest_path)
    except ManifestError:
        return None
