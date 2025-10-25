"""Unit tests for module configuration management."""

from datetime import datetime
from pathlib import Path

from quickscale_core.config import (
    ModuleConfig,
    ModuleInfo,
    add_module,
    load_config,
    remove_module,
    save_config,
    update_module_version,
)


class TestModuleInfo:
    """Tests for ModuleInfo dataclass"""

    def test_to_dict(self) -> None:
        """Test converting ModuleInfo to dictionary"""
        info = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="v0.62.0",
            installed_at="2025-10-24",
        )
        data = info.to_dict()
        assert data["prefix"] == "modules/auth"
        assert data["branch"] == "splits/auth-module"
        assert data["installed_version"] == "v0.62.0"
        assert data["installed_at"] == "2025-10-24"

    def test_from_dict(self) -> None:
        """Test creating ModuleInfo from dictionary"""
        data = {
            "prefix": "modules/auth",
            "branch": "splits/auth-module",
            "installed_version": "v0.62.0",
            "installed_at": "2025-10-24",
        }
        info = ModuleInfo.from_dict(data)
        assert info.prefix == "modules/auth"
        assert info.branch == "splits/auth-module"
        assert info.installed_version == "v0.62.0"
        assert info.installed_at == "2025-10-24"


class TestModuleConfig:
    """Tests for ModuleConfig dataclass"""

    def test_to_dict_empty_modules(self) -> None:
        """Test converting empty ModuleConfig to dictionary"""
        config = ModuleConfig(default_remote="https://github.com/repo.git")
        data = config.to_dict()
        assert data["default_remote"] == "https://github.com/repo.git"
        assert data["modules"] == {}

    def test_to_dict_with_modules(self) -> None:
        """Test converting ModuleConfig with modules to dictionary"""
        config = ModuleConfig(default_remote="https://github.com/repo.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="v0.62.0",
            installed_at="2025-10-24",
        )
        data = config.to_dict()
        assert "auth" in data["modules"]
        assert data["modules"]["auth"]["prefix"] == "modules/auth"

    def test_from_dict(self) -> None:
        """Test creating ModuleConfig from dictionary"""
        data = {
            "default_remote": "https://github.com/repo.git",
            "modules": {
                "auth": {
                    "prefix": "modules/auth",
                    "branch": "splits/auth-module",
                    "installed_version": "v0.62.0",
                    "installed_at": "2025-10-24",
                }
            },
        }
        config = ModuleConfig.from_dict(data)
        assert config.default_remote == "https://github.com/repo.git"
        assert "auth" in config.modules
        assert config.modules["auth"].prefix == "modules/auth"


class TestLoadConfig:
    """Tests for load_config function"""

    def test_load_config_when_file_not_exists(self, tmp_path: Path) -> None:
        """Test loading config when file doesn't exist returns default"""
        config = load_config(tmp_path)
        assert config.default_remote == "https://github.com/Experto-AI/quickscale.git"
        assert config.modules == {}

    def test_load_config_when_file_exists(self, tmp_path: Path) -> None:
        """Test loading config from existing file"""
        # Create config file
        config_dir = tmp_path / ".quickscale"
        config_dir.mkdir()
        config_file = config_dir / "config.yml"
        config_file.write_text(
            """default_remote: https://github.com/custom/repo.git
modules:
  auth:
    prefix: modules/auth
    branch: splits/auth-module
    installed_version: v0.62.0
    installed_at: '2025-10-24'
"""
        )

        # Load config
        config = load_config(tmp_path)
        assert config.default_remote == "https://github.com/custom/repo.git"
        assert "auth" in config.modules
        assert config.modules["auth"].prefix == "modules/auth"


class TestSaveConfig:
    """Tests for save_config function"""

    def test_save_config_creates_directory(self, tmp_path: Path) -> None:
        """Test saving config creates .quickscale directory"""
        config = ModuleConfig(default_remote="https://github.com/repo.git")
        save_config(config, tmp_path)

        config_file = tmp_path / ".quickscale" / "config.yml"
        assert config_file.exists()

    def test_save_config_writes_yaml(self, tmp_path: Path) -> None:
        """Test saving config writes valid YAML"""
        config = ModuleConfig(default_remote="https://github.com/repo.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="v0.62.0",
            installed_at="2025-10-24",
        )
        save_config(config, tmp_path)

        config_file = tmp_path / ".quickscale" / "config.yml"
        content = config_file.read_text()
        assert "default_remote: https://github.com/repo.git" in content
        assert "auth:" in content
        assert "modules/auth" in content


class TestAddModule:
    """Tests for add_module function"""

    def test_add_module_creates_config_if_not_exists(self, tmp_path: Path) -> None:
        """Test adding module creates config file if it doesn't exist"""
        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="v0.62.0",
            project_path=tmp_path,
        )

        config_file = tmp_path / ".quickscale" / "config.yml"
        assert config_file.exists()

    def test_add_module_adds_to_config(self, tmp_path: Path) -> None:
        """Test adding module updates config correctly"""
        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="v0.62.0",
            project_path=tmp_path,
        )

        config = load_config(tmp_path)
        assert "auth" in config.modules
        assert config.modules["auth"].prefix == "modules/auth"
        assert config.modules["auth"].branch == "splits/auth-module"
        assert config.modules["auth"].installed_version == "v0.62.0"

    def test_add_module_sets_current_date(self, tmp_path: Path) -> None:
        """Test adding module sets current date"""
        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="v0.62.0",
            project_path=tmp_path,
        )

        config = load_config(tmp_path)
        expected_date = datetime.now().strftime("%Y-%m-%d")
        assert config.modules["auth"].installed_at == expected_date


class TestRemoveModule:
    """Tests for remove_module function"""

    def test_remove_module_removes_from_config(self, tmp_path: Path) -> None:
        """Test removing module updates config"""
        # Add module first
        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="v0.62.0",
            project_path=tmp_path,
        )

        # Remove module
        remove_module("auth", tmp_path)

        config = load_config(tmp_path)
        assert "auth" not in config.modules

    def test_remove_nonexistent_module_is_safe(self, tmp_path: Path) -> None:
        """Test removing non-existent module doesn't fail"""
        remove_module("nonexistent", tmp_path)
        # Should not raise any exception


class TestUpdateModuleVersion:
    """Tests for update_module_version function"""

    def test_update_module_version(self, tmp_path: Path) -> None:
        """Test updating module version"""
        # Add module first
        add_module(
            module_name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            version="v0.62.0",
            project_path=tmp_path,
        )

        # Update version
        update_module_version("auth", "v0.63.0", tmp_path)

        config = load_config(tmp_path)
        assert config.modules["auth"].installed_version == "v0.63.0"

    def test_update_nonexistent_module_is_safe(self, tmp_path: Path) -> None:
        """Test updating non-existent module doesn't fail"""
        update_module_version("nonexistent", "v0.63.0", tmp_path)
        # Should not raise any exception
