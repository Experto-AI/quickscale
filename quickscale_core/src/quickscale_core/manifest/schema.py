"""Module Manifest Schema

Dataclasses for module manifest (module.yml) configuration.
Defines mutable vs immutable config options for modules.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

#: Root prefix that all manifest-declared managed-file output paths must
#: resolve under.  This is the single source of truth for the write
#: boundary enforced by the loader and assembler.
MANAGED_FILE_ROOT_PREFIX = "quickscale_managed/"


@dataclass(frozen=True)
class ManagedFileDeclaration:
    """Declarative description of a single module-owned managed file.

    Managed files are generated artifacts that a module contributes to the
    generated project.  The declaration is intentionally minimal: a renderer
    identifier and a rooted output path.  Content generation is deferred to
    a later phase; this dataclass captures only the structural contract.

    Attributes:
        key: The YAML key identifying this managed file within the
            module's ``managed_files`` section.
        renderer: Renderer identifier (e.g. a template path or renderer
            name) that describes how the file content is produced.
        output_path: Destination path for the generated file, relative
            to the project root.  Must start with
            ``quickscale_managed/`` to enforce the write boundary.
    """

    key: str
    renderer: str
    output_path: str

    @property
    def is_within_managed_root(self) -> bool:
        """Return True when the output_path is under the managed root prefix."""
        return self.output_path.startswith(MANAGED_FILE_ROOT_PREFIX)


@dataclass
class ConfigOption:
    """Configuration option for a module"""

    name: str
    option_type: str  # boolean, string, integer, list
    default: Any = None
    django_setting: str | None = None  # Only for mutable options
    description: str = ""
    mutability: Literal["mutable", "immutable"] = "immutable"
    validation: dict[str, Any] = field(default_factory=dict)

    @property
    def is_mutable(self) -> bool:
        """Check if this option is mutable (can be changed after embed)"""
        return self.mutability == "mutable" and self.django_setting is not None


@dataclass
class ModuleManifest:
    """Complete module manifest from module.yml"""

    name: str
    version: str
    description: str = ""
    mutable_options: dict[str, ConfigOption] = field(default_factory=dict)
    immutable_options: dict[str, ConfigOption] = field(default_factory=dict)
    required_modules: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    django_apps: list[str] = field(default_factory=list)
    managed_files: dict[str, ManagedFileDeclaration] = field(default_factory=dict)

    def get_option(self, option_name: str) -> ConfigOption | None:
        """Get a config option by name from either mutable or immutable"""
        if option_name in self.mutable_options:
            return self.mutable_options[option_name]
        if option_name in self.immutable_options:
            return self.immutable_options[option_name]
        return None

    def is_option_mutable(self, option_name: str) -> bool:
        """Check if a specific option is mutable"""
        return option_name in self.mutable_options

    def get_all_options(self) -> dict[str, ConfigOption]:
        """Get all config options (mutable and immutable)"""
        return {**self.mutable_options, **self.immutable_options}

    def get_defaults(self) -> dict[str, Any]:
        """Get default values for all options"""
        defaults = {}
        for name, option in self.mutable_options.items():
            defaults[name] = option.default
        for name, option in self.immutable_options.items():
            defaults[name] = option.default
        return defaults

    def get_django_settings_mapping(self) -> dict[str, str]:
        """Get mapping from option names to Django settings keys (mutable only)"""
        mapping = {}
        for name, option in self.mutable_options.items():
            if option.django_setting:
                mapping[name] = option.django_setting
        return mapping
