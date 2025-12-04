"""Tests for quickscale status command"""

import json
import os

import yaml
from click.testing import CliRunner

from quickscale_cli.commands.status_command import status


class TestStatusCommandBasic:
    """Basic tests for status command"""

    def test_status_not_in_project_directory(self):
        """Test status command when not in a QuickScale project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(status, [])

            assert result.exit_code != 0
            assert "Not in a QuickScale project" in result.output

    def test_status_help(self):
        """Test status command help output"""
        runner = CliRunner()
        result = runner.invoke(status, ["--help"])

        assert result.exit_code == 0
        assert "Show project status" in result.output
        assert "--json" in result.output


class TestStatusWithState:
    """Tests for status command with state file"""

    def test_status_with_state_only(self):
        """Test status when only state file exists"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create state file
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

            result = runner.invoke(status, [])

            assert result.exit_code == 0
            assert "testapp" in result.output
            assert "showcase_html" in result.output

    def test_status_shows_applied_modules(self):
        """Test that status shows applied modules"""
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
                            }
                        },
                    },
                    f,
                )

            result = runner.invoke(status, [])

            assert result.exit_code == 0
            assert "auth" in result.output


class TestStatusWithConfig:
    """Tests for status command with config file"""

    def test_status_with_config_only(self):
        """Test status when only config file exists (new project)"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create config file
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

            result = runner.invoke(status, [])

            assert result.exit_code == 0
            assert "No state file found" in result.output or "testapp" in result.output


class TestStatusPendingChanges:
    """Tests for pending changes detection"""

    def test_status_shows_pending_module_add(self):
        """Test that status shows modules to be added"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create state without auth
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

            # Create config with auth
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: testapp
  theme: showcase_html
modules:
  auth:
docker:
  start: false
"""
                )

            result = runner.invoke(status, [])

            assert result.exit_code == 0
            # Should show pending changes
            assert "Pending" in result.output or "add" in result.output.lower()

    def test_status_no_pending_changes(self):
        """Test status when config matches state"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create matching state and config
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
                            }
                        },
                    },
                    f,
                )

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: testapp
  theme: showcase_html
modules:
  auth:
docker:
  start: false
"""
                )

            result = runner.invoke(status, [])

            assert result.exit_code == 0
            assert (
                "matches applied state" in result.output
                or "No changes" in result.output
            )


class TestStatusJsonOutput:
    """Tests for JSON output format"""

    def test_status_json_output(self):
        """Test status with --json flag"""
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

            result = runner.invoke(status, ["--json"])

            assert result.exit_code == 0
            # Should be valid JSON
            data = json.loads(result.output)
            assert "project_path" in data
            assert data["has_state"] is True

    def test_status_json_includes_state(self):
        """Test that JSON output includes state details"""
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
                                "version": "0.70.0",
                                "commit_sha": "abc123",
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )

            result = runner.invoke(status, ["--json"])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "state" in data
            assert data["state"]["project"]["name"] == "testapp"
            assert "auth" in data["state"]["modules"]

    def test_status_json_includes_pending_changes(self):
        """Test that JSON output includes pending changes"""
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

            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: testapp
  theme: showcase_html
modules:
  auth:
  blog:
docker:
  start: false
"""
                )

            result = runner.invoke(status, ["--json"])

            assert result.exit_code == 0
            data = json.loads(result.output)
            assert "pending_changes" in data
            assert data["pending_changes"]["has_changes"] is True
            assert "auth" in data["pending_changes"]["modules_to_add"]
            assert "blog" in data["pending_changes"]["modules_to_add"]


class TestStatusDriftDetection:
    """Tests for filesystem drift detection"""

    def test_status_detects_orphaned_modules(self):
        """Test that status detects modules in filesystem but not in state"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)
            os.makedirs("modules/orphan", exist_ok=True)

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

            result = runner.invoke(status, [])

            assert result.exit_code == 0
            assert "orphan" in result.output.lower() or "Orphaned" in result.output

    def test_status_detects_missing_modules(self):
        """Test that status detects modules in state but not in filesystem"""
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
                            "missing_module": {
                                "version": None,
                                "commit_sha": None,
                                "embedded_at": "2025-12-01T11:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )

            result = runner.invoke(status, [])

            assert result.exit_code == 0
            assert "missing" in result.output.lower() or "Missing" in result.output
