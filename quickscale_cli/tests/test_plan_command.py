"""Tests for quickscale plan command"""

import os

from click.testing import CliRunner

from quickscale_cli.commands.plan_command import plan


class TestPlanCommandBasic:
    """Basic tests for plan command"""

    def test_plan_with_invalid_project_name(self):
        """Test plan command with invalid project name"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(plan, ["123invalid"])

            assert result.exit_code != 0
            assert "not a valid project name" in result.output

    def test_plan_help(self):
        """Test plan command help output"""
        runner = CliRunner()
        result = runner.invoke(plan, ["--help"])

        assert result.exit_code == 0
        assert "Create or update a project configuration" in result.output
        assert "--output" in result.output
        assert "--add" in result.output
        assert "--reconfigure" in result.output

    def test_plan_creates_directory_structure(self):
        """Test that plan creates the project directory with quickscale.yml"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Provide input: theme (1), modules (skip), docker start (y), docker build (y), save (y)
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0
            assert os.path.exists("myapp/quickscale.yml")
            assert "Configuration saved" in result.output

    def test_plan_with_output_option(self):
        """Test plan command with custom output path"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs("custom", exist_ok=True)

            result = runner.invoke(
                plan,
                ["myapp", "--output", "custom/config.yml"],
                input="1\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0
            assert os.path.exists("custom/config.yml")

    def test_plan_existing_file_no_overwrite(self):
        """Test plan command when file exists and user declines overwrite"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs("myapp", exist_ok=True)
            with open("myapp/quickscale.yml", "w") as f:
                f.write("existing content")

            result = runner.invoke(
                plan,
                ["myapp"],
                input="n\n",  # Don't overwrite
            )

            assert result.exit_code != 0
            assert "Cancelled" in result.output

    def test_plan_existing_file_overwrite(self):
        """Test plan command when file exists and user confirms overwrite"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            os.makedirs("myapp", exist_ok=True)
            with open("myapp/quickscale.yml", "w") as f:
                f.write("existing content")

            # y (overwrite), 1 (theme), empty (no modules), y,y (docker), y (save)
            result = runner.invoke(
                plan,
                ["myapp"],
                input="y\n1\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0
            assert os.path.exists("myapp/quickscale.yml")


class TestPlanThemeSelection:
    """Tests for theme selection in plan command"""

    def test_plan_selects_default_theme(self):
        """Test that pressing Enter selects default showcase_html theme"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Empty input for theme selection (default), no modules, docker defaults, save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            assert "showcase_html" in content

    def test_plan_selects_theme_by_number(self):
        """Test selecting theme by number"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select theme 1, no modules, docker defaults, save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            assert "showcase_html" in content

    def test_plan_selects_theme_by_name(self):
        """Test selecting theme by name"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select theme by name, no modules, docker defaults, save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="showcase_html\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            assert "showcase_html" in content


class TestPlanModuleSelection:
    """Tests for module selection in plan command"""

    def test_plan_no_modules_selected(self):
        """Test plan with no modules selected"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select default theme, empty modules, docker defaults, save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            # Should not have modules section or it should be empty
            assert (
                "modules:" not in content
                or "modules: {}" in content
                or "modules:\n" not in content
            )

    def test_plan_single_module_by_number(self):
        """Test selecting a single module by number"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select theme 1, module 1 (auth), docker defaults, save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n1\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            assert "auth:" in content

    def test_plan_multiple_modules_by_numbers(self):
        """Test selecting multiple modules by comma-separated numbers"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select theme 1, modules 1,3 (auth, listings), docker defaults, save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n1,3\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            assert "auth:" in content
            assert "listings:" in content


class TestPlanDockerConfiguration:
    """Tests for Docker configuration in plan command"""

    def test_plan_docker_both_enabled(self):
        """Test plan with Docker start and build enabled"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select theme 1, no modules, docker start (y), build (y), save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            assert "start: true" in content
            assert "build: true" in content

    def test_plan_docker_disabled(self):
        """Test plan with Docker disabled"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select theme 1, no modules, docker start (n), save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n\nn\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()
            assert "start: false" in content


class TestPlanConfigPreview:
    """Tests for configuration preview in plan command"""

    def test_plan_shows_preview(self):
        """Test that plan shows configuration preview before saving"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n\ny\ny\ny\n",
            )

            assert "Configuration Preview" in result.output
            assert "version:" in result.output
            assert "project:" in result.output

    def test_plan_cancel_after_preview(self):
        """Test canceling after seeing preview"""
        runner = CliRunner()
        with runner.isolated_filesystem():
            # Select theme 1, no modules, docker defaults, DON'T save
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n\ny\ny\nn\n",
            )

            assert result.exit_code != 0
            assert "Cancelled" in result.output
            assert not os.path.exists("myapp/quickscale.yml")


class TestPlanYamlValidation:
    """Tests for YAML output validation"""

    def test_plan_generates_valid_yaml(self):
        """Test that plan generates valid YAML that can be parsed"""
        from quickscale_cli.schema.config_schema import validate_config

        runner = CliRunner()
        with runner.isolated_filesystem():
            result = runner.invoke(
                plan,
                ["myapp"],
                input="1\n1\ny\ny\ny\n",
            )

            assert result.exit_code == 0

            with open("myapp/quickscale.yml") as f:
                content = f.read()

            # Should be valid config
            config = validate_config(content)
            assert config.project.name == "myapp"
            assert config.project.theme == "showcase_html"
            assert "auth" in config.modules
