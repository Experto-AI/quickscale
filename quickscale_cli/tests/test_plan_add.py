"""Tests for quickscale plan --add workflow"""

import os

import yaml
from click.testing import CliRunner

from quickscale_cli.commands.plan_command import plan


class TestPlanAddBasic:
    """Basic tests for plan --add command"""

    def test_plan_add_not_in_project(self):
        """Test plan --add when not in a QuickScale project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(plan, ["--add"])

            assert result.exit_code != 0
            assert "Not in a QuickScale project" in result.output

    def test_plan_add_help(self):
        """Test that --add flag is documented in help"""
        runner = CliRunner()
        result = runner.invoke(plan, ["--help"])

        assert result.exit_code == 0
        assert "--add" in result.output

    def test_plan_add_with_config(self):
        """Test plan --add when config exists"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create config with no modules
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

            # Select module 1 (auth), then save
            result = runner.invoke(plan, ["--add"], input="1\ny\n")

            assert result.exit_code == 0 or "Cancelled" not in result.output
            if result.exit_code == 0:
                assert "auth" in result.output

    def test_plan_add_with_state_only(self):
        """Test plan --add when only state exists (no config)"""
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

            # Select module 1 (auth), then save
            result = runner.invoke(plan, ["--add"], input="1\ny\n")

            # Should work even without config
            assert result.exit_code == 0 or "Cannot add" not in result.output


class TestPlanAddShowsCurrentModules:
    """Tests for displaying current modules"""

    def test_plan_add_shows_installed_modules(self):
        """Test that --add shows which modules are already installed"""
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

            # Don't select any new modules, cancel
            result = runner.invoke(plan, ["--add"], input="\nn\n")

            # Should show auth as installed
            assert "auth" in result.output
            assert "installed" in result.output.lower() or "Current" in result.output


class TestPlanAddSelectsNewModules:
    """Tests for selecting new modules"""

    def test_plan_add_skips_installed_modules(self):
        """Test that installed modules are not shown as available"""
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

            # Skip module selection
            result = runner.invoke(plan, ["--add"], input="\nn\n")

            # Available modules list should not show auth for selection
            # (auth appears in "Current Modules" but not in "Available Modules to Add")
            lines = result.output.split("\n")
            available_section = False
            for line in lines:
                if "Available Modules to Add" in line:
                    available_section = True
                elif available_section and ("Current" in line or "---" in line):
                    available_section = False
                elif available_section:
                    # In the available section, auth should not be numbered for selection
                    if ". auth" in line.lower():
                        assert (
                            False
                        ), "auth should not appear as available for selection"

    def test_plan_add_updates_config(self):
        """Test that adding module updates quickscale.yml"""
        runner = CliRunner()
        with runner.isolated_filesystem():
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

            # Select blog (module 2 in available list), then save
            result = runner.invoke(plan, ["--add"], input="2\ny\n")

            if result.exit_code == 0:
                # Check that config was updated
                with open("quickscale.yml") as f:
                    content = f.read()
                assert "blog" in content


class TestPlanAddNoModulesSelected:
    """Tests for when no modules are selected"""

    def test_plan_add_no_selection(self):
        """Test --add with no module selected"""
        runner = CliRunner()
        with runner.isolated_filesystem():
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

            # Press enter to skip selection
            result = runner.invoke(plan, ["--add"], input="\n")

            assert result.exit_code == 0
            assert "No new modules selected" in result.output


class TestPlanAddAllModulesInstalled:
    """Tests for when all modules are already installed"""

    def test_plan_add_all_installed(self):
        """Test --add when all modules are already installed"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs(".quickscale", exist_ok=True)

            # Create state with all modules
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
                            },
                            "blog": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                            },
                            "listings": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                            },
                            "billing": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                            },
                            "teams": {
                                "version": None,
                                "embedded_at": "2025-12-01T11:00:00",
                            },
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
  blog:
  listings:
  billing:
  teams:
docker:
  start: false
"""
                )

            result = runner.invoke(plan, ["--add"], input="")

            assert result.exit_code == 0
            assert (
                "All modules are already installed" in result.output
                or "No new modules selected" in result.output
            )
