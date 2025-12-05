"""Tests for settings manager"""

import pytest
from pathlib import Path

from quickscale_core.settings_manager import (
    update_setting,
    update_multiple_settings,
    apply_mutable_config_changes,
)


@pytest.fixture
def temp_settings_file(tmp_path: Path) -> Path:
    """Create a temporary settings file"""
    settings_content = '''"""Django settings for test project."""

import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = 'django-insecure-test-key'

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
]

# Session settings
SESSION_COOKIE_AGE = 1209600  # 2 weeks

# Allauth settings
ACCOUNT_ALLOW_REGISTRATION = True
ACCOUNT_EMAIL_VERIFICATION = "none"
'''
    settings_path = tmp_path / "settings.py"
    settings_path.write_text(settings_content)
    return settings_path


class TestUpdateSetting:
    """Tests for update_setting function"""

    def test_update_boolean_true_to_false(self, temp_settings_file: Path) -> None:
        """Test updating boolean from True to False"""
        success, message = update_setting(
            temp_settings_file, "ACCOUNT_ALLOW_REGISTRATION", False
        )
        assert success is True
        assert "Updated ACCOUNT_ALLOW_REGISTRATION" in message

        content = temp_settings_file.read_text()
        assert "ACCOUNT_ALLOW_REGISTRATION = False" in content

    def test_update_boolean_false_to_true(self, temp_settings_file: Path) -> None:
        """Test updating boolean from False to True"""
        # First set to False
        temp_settings_file.write_text(
            temp_settings_file.read_text().replace(
                "ACCOUNT_ALLOW_REGISTRATION = True",
                "ACCOUNT_ALLOW_REGISTRATION = False",
            )
        )

        success, message = update_setting(
            temp_settings_file, "ACCOUNT_ALLOW_REGISTRATION", True
        )
        assert success is True

        content = temp_settings_file.read_text()
        assert "ACCOUNT_ALLOW_REGISTRATION = True" in content

    def test_update_integer_setting(self, temp_settings_file: Path) -> None:
        """Test updating integer setting"""
        success, message = update_setting(
            temp_settings_file, "SESSION_COOKIE_AGE", 86400
        )
        assert success is True

        content = temp_settings_file.read_text()
        assert "SESSION_COOKIE_AGE = 86400" in content

    def test_update_string_setting(self, temp_settings_file: Path) -> None:
        """Test updating string setting"""
        success, message = update_setting(
            temp_settings_file, "ACCOUNT_EMAIL_VERIFICATION", "mandatory"
        )
        assert success is True

        content = temp_settings_file.read_text()
        assert 'ACCOUNT_EMAIL_VERIFICATION = "mandatory"' in content

    def test_update_setting_not_found(self, temp_settings_file: Path) -> None:
        """Test updating setting that doesn't exist - adds it"""
        success, message = update_setting(temp_settings_file, "NEW_SETTING", "value")
        assert success is True
        # New settings are added at the end
        content = temp_settings_file.read_text()
        assert 'NEW_SETTING = "value"' in content

    def test_update_setting_file_not_found(self, tmp_path: Path) -> None:
        """Test updating setting in non-existent file"""
        fake_path = tmp_path / "nonexistent.py"
        success, message = update_setting(fake_path, "ANY_SETTING", "value")
        assert success is False
        assert "not found" in message.lower() or "Error" in message


class TestUpdateMultipleSettings:
    """Tests for update_multiple_settings function"""

    def test_update_multiple_settings(self, temp_settings_file: Path) -> None:
        """Test updating multiple settings at once"""
        settings = {
            "ACCOUNT_ALLOW_REGISTRATION": False,
            "SESSION_COOKIE_AGE": 3600,
        }
        results = update_multiple_settings(temp_settings_file, settings)

        assert len(results) == 2
        assert all(success for _, success, _ in results)

        content = temp_settings_file.read_text()
        assert "ACCOUNT_ALLOW_REGISTRATION = False" in content
        assert "SESSION_COOKIE_AGE = 3600" in content

    def test_update_multiple_partial_failure(self, temp_settings_file: Path) -> None:
        """Test that partial failures don't stop other updates"""
        settings = {
            "ACCOUNT_ALLOW_REGISTRATION": False,  # exists
            "NONEXISTENT_SETTING": "value",  # doesn't exist
            "SESSION_COOKIE_AGE": 86400,  # exists
        }
        results = update_multiple_settings(temp_settings_file, settings)

        assert len(results) == 3
        successes = [success for _, success, _ in results]
        # At least 2 should succeed (the existing ones)
        assert sum(successes) >= 2


class TestApplyMutableConfigChanges:
    """Tests for apply_mutable_config_changes function"""

    def test_apply_config_changes(self, tmp_path: Path) -> None:
        """Test applying config changes via the high-level function"""
        # Create project structure matching QuickScale layout
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        # QuickScale uses project_name/settings/base.py
        settings_dir = project_path / "myproject" / "settings"
        settings_dir.mkdir(parents=True)

        settings_content = """
ACCOUNT_ALLOW_REGISTRATION = True
SESSION_COOKIE_AGE = 1209600
"""
        settings_path = settings_dir / "base.py"
        settings_path.write_text(settings_content)

        config_changes = {
            "ACCOUNT_ALLOW_REGISTRATION": False,
            "SESSION_COOKIE_AGE": 86400,
        }

        results = apply_mutable_config_changes(project_path, "auth", config_changes)

        assert len(results) == 2
        assert all(success for _, success, _ in results)

        content = settings_path.read_text()
        assert "ACCOUNT_ALLOW_REGISTRATION = False" in content
        assert "SESSION_COOKIE_AGE = 86400" in content

    def test_apply_config_no_settings_file(self, tmp_path: Path) -> None:
        """Test applying config when settings file doesn't exist"""
        project_path = tmp_path / "myproject"
        project_path.mkdir()
        # No core/settings.py

        config_changes = {"SOME_SETTING": "value"}
        results = apply_mutable_config_changes(project_path, "auth", config_changes)

        # Should return empty list or failure results
        if results:
            assert not all(success for _, success, _ in results)
