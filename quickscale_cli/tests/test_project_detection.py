"""Tests for project detection utilities"""

import os

import yaml
from click.testing import CliRunner

from quickscale_cli.commands.plan_command import (
    _detect_existing_project,
    _get_applied_modules,
)


class TestDetectExistingProject:
    """Tests for _detect_existing_project function"""

    def test_detect_project_with_config(self):
        """Test detection when quickscale.yml exists"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create config
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: testapp
  theme: showcase_html
docker:
  start: false
"""
                )

            # Change to isolated filesystem directory
            project_path, config = _detect_existing_project()

            assert project_path is not None
            assert config is not None
            assert config.project.name == "testapp"

    def test_detect_project_with_state_only(self):
        """Test detection when only state file exists"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "name": "testapp",
                            "theme": "showcase_html",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            project_path, config = _detect_existing_project()

            assert project_path is not None
            # Config should be None since only state exists
            assert config is None

    def test_detect_project_not_found(self):
        """Test when no project files exist"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            project_path, config = _detect_existing_project()

            assert project_path is None
            assert config is None


class TestGetAppliedModules:
    """Tests for _get_applied_modules function"""

    def test_get_applied_modules_with_state(self):
        """Test getting applied modules from state file"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "name": "testapp",
                            "theme": "showcase_html",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "commit_sha": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            },
                            "blog": {
                                "version": None,
                                "commit_sha": None,
                                "embedded_at": "2025-12-01T11:30:00",
                                "options": {},
                            },
                        },
                    },
                    f,
                )

            from pathlib import Path

            modules = _get_applied_modules(Path.cwd())

            assert "auth" in modules
            assert "blog" in modules

    def test_get_applied_modules_no_state(self):
        """Test getting applied modules when no state exists"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            from pathlib import Path

            modules = _get_applied_modules(Path.cwd())

            assert modules == []

    def test_get_applied_modules_empty_state(self):
        """Test getting applied modules when state has no modules"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            with open(".quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "name": "testapp",
                            "theme": "showcase_html",
                            "created_at": "2025-12-01T10:00:00",
                            "last_applied": "2025-12-01T12:00:00",
                        },
                        "modules": {},
                    },
                    f,
                )

            from pathlib import Path

            modules = _get_applied_modules(Path.cwd())

            assert modules == []
