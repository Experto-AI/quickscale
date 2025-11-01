"""Module configuration management for QuickScale projects."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import yaml


@dataclass
class ModuleInfo:
    """Information about an installed module"""

    prefix: str
    branch: str
    installed_version: str
    installed_at: str

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization"""
        return {
            "prefix": self.prefix,
            "branch": self.branch,
            "installed_version": self.installed_version,
            "installed_at": self.installed_at,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModuleInfo":
        """Create from dictionary loaded from YAML"""
        return cls(
            prefix=data["prefix"],
            branch=data["branch"],
            installed_version=data["installed_version"],
            installed_at=data["installed_at"],
        )


@dataclass
class ModuleConfig:
    """QuickScale module configuration"""

    default_remote: str
    modules: dict[str, ModuleInfo] = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Convert to dictionary for YAML serialization"""
        return {
            "default_remote": self.default_remote,
            "modules": {name: info.to_dict() for name, info in self.modules.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ModuleConfig":
        """Create from dictionary loaded from YAML"""
        modules = {
            name: ModuleInfo.from_dict(info)
            for name, info in data.get("modules", {}).items()
        }
        return cls(default_remote=data["default_remote"], modules=modules)


def get_config_path(project_path: Path | None = None) -> Path:
    """Get the path to the module configuration file"""
    base_path = project_path or Path.cwd()
    return base_path / ".quickscale" / "config.yml"


def load_config(project_path: Path | None = None) -> ModuleConfig:
    """Load module configuration from YAML file"""
    config_path = get_config_path(project_path)

    if not config_path.exists():
        # Return default config if file doesn't exist
        return ModuleConfig(
            default_remote="https://github.com/Experto-AI/quickscale.git"
        )

    with open(config_path) as f:
        data = yaml.safe_load(f)

    return ModuleConfig.from_dict(data)


def save_config(config: ModuleConfig, project_path: Path | None = None) -> None:
    """Save module configuration to YAML file"""
    config_path = get_config_path(project_path)

    # Create .quickscale directory if it doesn't exist
    config_path.parent.mkdir(parents=True, exist_ok=True)

    with open(config_path, "w") as f:
        yaml.dump(config.to_dict(), f, default_flow_style=False, sort_keys=False)


def add_module(
    module_name: str,
    prefix: str,
    branch: str,
    version: str,
    project_path: Path | None = None,
) -> None:
    """Add a module to the configuration"""
    config = load_config(project_path)

    config.modules[module_name] = ModuleInfo(
        prefix=prefix,
        branch=branch,
        installed_version=version,
        installed_at=datetime.now().strftime("%Y-%m-%d"),
    )

    save_config(config, project_path)


def remove_module(module_name: str, project_path: Path | None = None) -> None:
    """Remove a module from the configuration"""
    config = load_config(project_path)

    if module_name in config.modules:
        del config.modules[module_name]
        save_config(config, project_path)


def update_module_version(
    module_name: str, version: str, project_path: Path | None = None
) -> None:
    """Update the installed version of a module"""
    config = load_config(project_path)

    if module_name in config.modules:
        config.modules[module_name].installed_version = version
        save_config(config, project_path)
