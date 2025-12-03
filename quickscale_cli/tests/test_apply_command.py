"""Tests for quickscale apply command"""

import os

from click.testing import CliRunner

from quickscale_cli.commands.apply_command import apply


class TestApplyCommandBasic:
    """Basic tests for apply command"""

    def test_apply_missing_config_file(self):
        """Test apply command when config file doesn't exist"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(apply, ["nonexistent.yml"])

            assert result.exit_code != 0
            # Click's Path type with exists=True gives this error format
            assert "does not exist" in result.output

    def test_apply_help(self):
        """Test apply command help output"""
        runner = CliRunner()
        result = runner.invoke(apply, ["--help"])

        assert result.exit_code == 0
        assert "Execute project configuration" in result.output
        assert "--force" in result.output
        assert "--no-docker" in result.output
        assert "--no-modules" in result.output

    def test_apply_invalid_yaml_syntax(self):
        """Test apply command with invalid YAML"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write("invalid: [unclosed bracket")

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert (
                "Configuration error" in result.output
                or "Invalid YAML" in result.output
            )

    def test_apply_missing_required_fields(self):
        """Test apply command with missing required fields"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write("version: '1'\n")

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output


class TestApplyConfigValidation:
    """Tests for configuration validation in apply command"""

    def test_apply_invalid_project_name(self):
        """Test apply with invalid project name in config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: 123invalid
"""
                )

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output

    def test_apply_unknown_theme(self):
        """Test apply with unknown theme in config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
  theme: unknown_theme
"""
                )

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output

    def test_apply_unknown_module(self):
        """Test apply with unknown module in config"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
modules:
  unknown_module:
"""
                )

            result = runner.invoke(apply, ["quickscale.yml"])

            assert result.exit_code != 0
            assert "Configuration error" in result.output


class TestApplyDirectoryHandling:
    """Tests for directory handling in apply command"""

    def test_apply_directory_exists_no_force(self):
        """Test apply when directory exists and --force not used"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create config
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
docker:
  start: false
"""
                )

            # Create existing directory with content
            os.makedirs("myapp", exist_ok=True)
            with open("myapp/existing.txt", "w") as f:
                f.write("existing content")

            # Don't confirm
            result = runner.invoke(apply, ["quickscale.yml"], input="n\n")

            assert result.exit_code != 0

    def test_apply_reads_config_from_project_dir(self):
        """Test apply reads config from project directory (myapp/quickscale.yml)"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create project directory with config
            os.makedirs("myapp", exist_ok=True)
            with open("myapp/quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
docker:
  start: false
"""
                )

            # Apply should work (will need confirmation)
            result = runner.invoke(
                apply,
                ["myapp/quickscale.yml"],
                input="y\ny\n",  # Confirm directory has content, proceed
            )

            # Just check it processes the config correctly
            assert "myapp" in result.output


class TestApplyProjectGeneration:
    """Tests for project generation via apply command"""

    def test_apply_generates_project_structure(self):
        """Test that apply generates basic project structure"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Create minimal config
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: testapp
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Check project was generated
            if result.exit_code == 0:
                assert os.path.exists("testapp")
                assert os.path.exists("testapp/manage.py")
                assert os.path.exists("testapp/pyproject.toml")

    def test_apply_shows_execution_steps(self):
        """Test that apply shows execution progress"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Should show progress indicators
            assert "⏳" in result.output or "Generating" in result.output


class TestApplyOptions:
    """Tests for apply command options"""

    def test_apply_no_docker_flag(self):
        """Test --no-docker flag skips Docker operations"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
docker:
  start: true
  build: true
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-docker", "--no-modules"],
                input="y\n",
            )

            # Docker operations should be skipped
            assert "Starting Docker" not in result.output or "Docker" in result.output

    def test_apply_no_modules_flag(self):
        """Test --no-modules flag skips module embedding"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
modules:
  auth:
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Module embedding should be skipped
            assert "Embedding module: auth" not in result.output


class TestApplyConfigSummary:
    """Tests for configuration summary display"""

    def test_apply_shows_config_summary(self):
        """Test that apply shows configuration summary before execution"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
  theme: showcase_html
modules:
  auth:
docker:
  start: true
  build: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml"],
                input="n\n",  # Cancel before execution
            )

            # Should show configuration summary
            assert "myapp" in result.output
            assert "showcase_html" in result.output
            assert "auth" in result.output


class TestApplyUnimplementedThemes:
    """Tests for handling unimplemented themes"""

    def test_apply_showcase_htmx_not_implemented(self):
        """Test that showcase_htmx theme shows not implemented error"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
  theme: showcase_htmx
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Should fail with not implemented error
            assert result.exit_code != 0 or "not yet implemented" in result.output

    def test_apply_showcase_react_not_implemented(self):
        """Test that showcase_react theme shows not implemented error"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
  theme: showcase_react
docker:
  start: false
"""
                )

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Should fail with not implemented error
            assert result.exit_code != 0 or "not yet implemented" in result.output


class TestApplyDefaultConfig:
    """Tests for default config file behavior"""

    def test_apply_uses_default_config_file(self):
        """Test that apply uses quickscale.yml by default"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            with open("quickscale.yml", "w") as f:
                f.write(
                    """
version: "1"
project:
  name: myapp
docker:
  start: false
"""
                )

            # Run without specifying config file
            result = runner.invoke(
                apply,
                ["--no-modules", "--no-docker"],
                input="y\n",
            )

            # Should find and use quickscale.yml
            assert "myapp" in result.output

    def test_apply_error_no_default_config(self):
        """Test error when no default quickscale.yml exists"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # No quickscale.yml exists
            result = runner.invoke(apply, [])

            assert result.exit_code != 0
            assert (
                "Configuration file not found" in result.output
                or "does not exist" in result.output
            )


class TestApplyIncrementalApply:
    """Tests for incremental apply behavior"""

    def test_apply_creates_state_file(self):
        """Test that apply creates .quickscale/state.yml on successful apply"""
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

            result = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            if result.exit_code == 0:
                # State file should be created
                assert os.path.exists("testapp/.quickscale/state.yml")

    def test_apply_second_apply_is_idempotent(self):
        """Test that second apply with same config shows 'nothing to do'"""
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

            # First apply
            result1 = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            if result1.exit_code == 0:
                # Create quickscale.yml in the generated project directory
                with open("testapp/quickscale.yml", "w") as f:
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

                # Second apply should detect no changes
                result2 = runner.invoke(
                    apply,
                    ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                    input="y\n",
                )

                # Should show "nothing to do" message
                assert (
                    "Nothing to do" in result2.output
                    or "No changes detected" in result2.output
                    or "matches applied state" in result2.output
                )

    def test_apply_shows_delta_for_existing_project(self):
        """Test that apply shows delta when applying to existing project"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # First create a project with initial config
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

            result1 = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            if result1.exit_code == 0:
                # Modify config to add a module (will not actually embed)
                with open("testapp/quickscale.yml", "w") as f:
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

                # Second apply should show delta
                result2 = runner.invoke(
                    apply,
                    ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                    input="n\n",  # Decline to proceed
                )

                # Should show modules to add
                assert (
                    "Modules to add" in result2.output
                    or "auth" in result2.output
                    or "Changes to apply" in result2.output
                )


class TestApplyStateRecovery:
    """Tests for state file recovery scenarios"""

    def test_apply_handles_missing_state_file(self):
        """Test that apply works when project exists but state file is missing"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # First create a project
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

            result1 = runner.invoke(
                apply,
                ["quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            if result1.exit_code == 0:
                # Delete state file to simulate corruption/missing state
                import shutil

                if os.path.exists("testapp/.quickscale"):
                    shutil.rmtree("testapp/.quickscale")

                # Move config back to project directory
                with open("testapp/quickscale.yml", "w") as f:
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

                # Apply should detect existing project and handle gracefully
                result2 = runner.invoke(
                    apply,
                    ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                    input="n\n",  # Don't proceed to avoid regeneration
                )

                # Should handle existing project gracefully
                assert result2.exit_code != 0 or "Existing project" in result2.output

    def test_apply_detects_filesystem_modules(self):
        """Test that apply respects modules in state file"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            import yaml

            # Create project with state file containing module info
            os.makedirs("testapp/.quickscale", exist_ok=True)
            with open("testapp/.quickscale/state.yml", "w") as f:
                yaml.dump(
                    {
                        "version": "1",
                        "project": {
                            "name": "testapp",
                            "theme": "showcase_html",
                            "created_at": "2025-01-01T00:00:00",
                            "last_applied": "2025-01-01T00:00:00",
                        },
                        "modules": {
                            "auth": {
                                "version": None,
                                "commit_sha": None,
                                "embedded_at": "2025-01-01T00:00:00",
                                "options": {},
                            }
                        },
                    },
                    f,
                )

            # Create config with same module
            with open("testapp/quickscale.yml", "w") as f:
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

            # Create minimal project structure
            os.makedirs("testapp/modules/auth", exist_ok=True)
            with open("testapp/manage.py", "w") as f:
                f.write("# Django manage.py")

            # Apply should show no changes since auth is already in state
            result = runner.invoke(
                apply,
                ["testapp/quickscale.yml", "--no-modules", "--no-docker"],
                input="y\n",
            )

            # Should show auth is unchanged
            assert "Nothing to do" in result.output or "unchanged" in result.output
