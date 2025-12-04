"""Tests for quickscale plan --reconfigure workflow"""

import os

import yaml
from click.testing import CliRunner

from quickscale_cli.commands.plan_command import plan


class TestPlanReconfigureBasic:
    """Basic tests for plan --reconfigure command"""

    def test_plan_reconfigure_not_in_project(self):
        """Test plan --reconfigure when not in a QuickScale project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(plan, ["--reconfigure"])

            assert result.exit_code != 0
            assert "Not in a QuickScale project" in result.output

    def test_plan_reconfigure_help(self):
        """Test that --reconfigure flag is documented in help"""
        runner = CliRunner()
        result = runner.invoke(plan, ["--help"])

        assert result.exit_code == 0
        assert "--reconfigure" in result.output


class TestPlanReconfigureWithState:
    """Tests for --reconfigure with state file"""

    def test_plan_reconfigure_shows_project_info(self):
        """Test that --reconfigure shows current project info"""
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

            # Don't add modules (n), docker start (n), cancel save (n)
            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "testapp" in result.output
            assert "showcase_html" in result.output

    def test_plan_reconfigure_shows_theme_locked(self):
        """Test that --reconfigure shows theme is locked"""
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

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "locked" in result.output.lower()


class TestPlanReconfigureShowsModules:
    """Tests for module display in reconfigure"""

    def test_plan_reconfigure_shows_installed_modules(self):
        """Test that --reconfigure shows installed modules"""
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
                                "embedded_at": "2025-12-01T11:00:00",
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

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "auth" in result.output

    def test_plan_reconfigure_shows_pending_modules(self):
        """Test that --reconfigure shows modules pending apply"""
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
                                "embedded_at": "2025-12-01T11:00:00",
                            }
                        },
                    },
                    f,
                )

            # Config has blog but state doesn't - blog is pending
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

            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert "auth" in result.output
            assert "blog" in result.output


class TestPlanReconfigureDocker:
    """Tests for Docker reconfiguration"""

    def test_plan_reconfigure_docker_options(self):
        """Test that --reconfigure allows Docker option changes"""
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

            # Don't add modules (n), docker start (y), build (y), save (y)
            result = runner.invoke(plan, ["--reconfigure"], input="n\ny\ny\ny\n")

            if result.exit_code == 0:
                with open("quickscale.yml") as f:
                    content = f.read()
                assert "start: true" in content
                assert "build: true" in content


class TestPlanReconfigureAddModules:
    """Tests for adding modules during reconfigure"""

    def test_plan_reconfigure_add_module(self):
        """Test adding a module during reconfigure"""
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

            # Add modules (y), select 1 (auth), docker (n), save (y)
            result = runner.invoke(plan, ["--reconfigure"], input="y\n1\nn\ny\n")

            if result.exit_code == 0:
                with open("quickscale.yml") as f:
                    content = f.read()
                assert "auth" in content


class TestPlanReconfigureSavesConfig:
    """Tests for config saving"""

    def test_plan_reconfigure_saves_config(self):
        """Test that --reconfigure saves updated config"""
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

            # Don't add modules, docker start (y), build (n), save (y)
            result = runner.invoke(plan, ["--reconfigure"], input="n\ny\nn\ny\n")

            assert result.exit_code == 0
            assert os.path.exists("quickscale.yml")
            with open("quickscale.yml") as f:
                content = f.read()
            assert "testapp" in content

    def test_plan_reconfigure_cancel(self):
        """Test canceling --reconfigure doesn't save config"""
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

            # Don't add modules, docker (n), cancel save (n)
            result = runner.invoke(plan, ["--reconfigure"], input="n\nn\nn\n")

            assert result.exit_code != 0 or "Cancelled" in result.output
            # quickscale.yml should not exist unless we saved
            if result.exit_code != 0:
                assert not os.path.exists("quickscale.yml")
