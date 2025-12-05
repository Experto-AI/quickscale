"""Module Manifest Schema

Dataclasses for module manifest (module.yml) configuration.
Defines mutable vs immutable config options for modules.
"""

from dataclasses import dataclass, field
from typing import Any, Literal


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
    dependencies: list[str] = field(default_factory=list)
    django_apps: list[str] = field(default_factory=list)

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
