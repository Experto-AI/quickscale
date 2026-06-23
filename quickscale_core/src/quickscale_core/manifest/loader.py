"""Module Manifest Loader

Loads and validates module.yml manifest files.
"""

from pathlib import Path
import posixpath
from typing import Any

import yaml

from quickscale_core.manifest.schema import (
    MANAGED_FILE_ROOT_PREFIX,
    ConfigOption,
    ImpliesEntry,
    ManagedFileDeclaration,
    ModuleManifest,
)


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


def _parse_yaml_content(yaml_content: str, module_name: str | None) -> dict[str, Any]:
    """Parse YAML content and return data dictionary"""
    try:
        data = yaml.safe_load(yaml_content)
    except yaml.YAMLError as e:
        raise ManifestError(f"Invalid YAML syntax: {e}", module_name) from e

    if not isinstance(data, dict):
        raise ManifestError("Manifest must be a YAML mapping", module_name)

    return data


def _validate_required_string_field(
    data: dict[str, Any], field: str, module_name: str | None
) -> str:
    """Validate a required string field exists and is non-empty"""
    if field not in data:
        raise ManifestError(f"Missing required field '{field}'", module_name)

    value = data[field]
    if not isinstance(value, str) or not value:
        raise ManifestError(f"'{field}' must be a non-empty string", module_name)

    return value


def _validate_list_field(
    data: dict[str, Any], field: str, module_name: str | None
) -> list[str]:
    """Validate an optional list field"""
    value = data.get(field, [])
    if not isinstance(value, list):
        raise ManifestError(f"'{field}' must be a list", module_name)
    return value


def _validate_mutable_options(
    mutable_options: dict[str, ConfigOption], module_name: str | None
) -> None:
    """Validate that mutable options have django_setting defined"""
    for opt_name, option in mutable_options.items():
        if not option.django_setting:
            raise ManifestError(
                f"Mutable option '{opt_name}' must have 'django_setting' defined",
                module_name,
            )


def _parse_managed_files(
    data: dict[str, Any], module_name: str | None
) -> dict[str, ManagedFileDeclaration]:
    """Parse and validate the top-level ``managed_files`` section.

    Each entry must be a mapping with at least ``renderer`` (non-empty
    string) and ``output_path`` (non-empty string starting with
    ``quickscale_managed/``).  Entries that violate the write boundary
    raise :class:`ManifestError`.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        A dict mapping managed-file keys to their
        :class:`ManagedFileDeclaration` instances.  Returns an empty
        dict when the section is absent.

    Raises:
        ManifestError: If the section is malformed or a path escapes
            the managed root.
    """
    raw_section = data.get("managed_files")
    if raw_section is None:
        return {}

    if not isinstance(raw_section, dict):
        raise ManifestError("'managed_files' must be a mapping", module_name)

    declarations: dict[str, ManagedFileDeclaration] = {}

    for key, entry in raw_section.items():
        if entry is None:
            entry = {}
        if not isinstance(entry, dict):
            raise ManifestError(
                f"managed_files.{key} must be a mapping or empty",
                module_name,
            )

        renderer = entry.get("renderer")
        if not isinstance(renderer, str) or not renderer:
            raise ManifestError(
                f"managed_files.{key}.renderer must be a non-empty string",
                module_name,
            )

        output_path = entry.get("output_path")
        if not isinstance(output_path, str) or not output_path:
            raise ManifestError(
                f"managed_files.{key}.output_path must be a non-empty string",
                module_name,
            )

        if not output_path.startswith(MANAGED_FILE_ROOT_PREFIX):
            raise ManifestError(
                f"managed_files.{key}.output_path must start with "
                f"'{MANAGED_FILE_ROOT_PREFIX}' "
                f"(got '{output_path}')",
                module_name,
            )

        # Defense-in-depth: normalize the path to reject traversal attempts
        # like "quickscale_managed/../etc/passwd".
        normalized = posixpath.normpath(output_path)
        if not (
            normalized.startswith(MANAGED_FILE_ROOT_PREFIX)
            or normalized == MANAGED_FILE_ROOT_PREFIX.rstrip("/")
        ):
            raise ManifestError(
                f"managed_files.{key}.output_path resolves outside "
                f"'{MANAGED_FILE_ROOT_PREFIX}' after normalization "
                f"(got '{output_path}')",
                module_name,
            )

        declarations[key] = ManagedFileDeclaration(
            key=key,
            renderer=renderer,
            output_path=output_path,
        )

    return declarations


def _parse_implies(data: dict[str, Any], module_name: str | None) -> list[ImpliesEntry]:
    """Parse and validate the top-level ``implies`` section.

    Each entry must be a mapping with at least ``name`` (non-empty string).
    An optional ``default_config`` mapping provides configuration defaults
    for the implied module.  Returns an empty list when the section is absent.

    Args:
        data: The full parsed YAML data dictionary.
        module_name: Optional module name for error messages.

    Returns:
        A list of :class:`ImpliesEntry` instances.  Returns an empty list
        when the section is absent.

    Raises:
        ManifestError: If the section is malformed.
    """
    raw_section = data.get("implies")
    if raw_section is None:
        return []

    if not isinstance(raw_section, list):
        raise ManifestError("'implies' must be a list", module_name)

    entries: list[ImpliesEntry] = []
    for i, entry in enumerate(raw_section):
        if not isinstance(entry, dict):
            raise ManifestError(f"implies[{i}] must be a mapping", module_name)

        name = entry.get("name")
        if not isinstance(name, str) or not name:
            raise ManifestError(
                f"implies[{i}].name must be a non-empty string", module_name
            )

        default_config = entry.get("default_config", {})
        if not isinstance(default_config, dict):
            raise ManifestError(
                f"implies[{i}].default_config must be a mapping", module_name
            )

        entries.append(ImpliesEntry(name=name, default_config=dict(default_config)))

    return entries


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
    data = _parse_yaml_content(yaml_content, module_name)

    # Validate required fields
    name = _validate_required_string_field(data, "name", module_name)
    version = _validate_required_string_field(data, "version", module_name)

    # Parse config section
    config_data = data.get("config", {})
    if not isinstance(config_data, dict):
        raise ManifestError("'config' must be a mapping", module_name)

    mutable_options = _parse_config_section(config_data, "mutable")
    immutable_options = _parse_config_section(config_data, "immutable")
    _validate_mutable_options(mutable_options, module_name)

    # Parse list fields
    required_modules = _validate_list_field(data, "required_modules", module_name)
    dependencies = _validate_list_field(data, "dependencies", module_name)
    django_apps = _validate_list_field(data, "django_apps", module_name)

    # Parse managed-files declarations (additive; empty when absent)
    managed_files = _parse_managed_files(data, module_name)

    # Parse implies declarations (additive; empty when absent)
    implies = _parse_implies(data, module_name)

    return ModuleManifest(
        name=name,
        version=version,
        description=data.get("description", ""),
        mutable_options=mutable_options,
        immutable_options=immutable_options,
        required_modules=required_modules,
        dependencies=dependencies,
        django_apps=django_apps,
        managed_files=managed_files,
        implies=implies,
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
    project_path: Path, module_name: str, *, strict: bool = False
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
        if strict:
            raise ManifestError(
                f"Manifest file not found: {manifest_path}",
                module_name,
            )
        return None

    try:
        return load_manifest_from_path(manifest_path)
    except ManifestError:
        if strict:
            raise
        return None
