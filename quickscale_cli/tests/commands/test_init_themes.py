"""Tests for CLI theme selection"""

from click.testing import CliRunner

from quickscale_cli.main import cli


class TestCLIThemeSelection:
    """Test CLI --theme flag"""

    def test_init_without_theme_flag(self, tmp_path):
        """Init command should work without --theme flag (default)"""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "testproject"])
            assert result.exit_code == 0
            assert "Using theme: starter_html" in result.output
            assert "Created project: testproject (theme: starter_html)" in result.output

    def test_init_with_explicit_html_theme(self, tmp_path):
        """Init command should accept explicit starter_html theme"""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "testproject", "--theme", "starter_html"])
            assert result.exit_code == 0
            assert "Using theme: starter_html" in result.output

    def test_init_with_htmx_theme_shows_error(self, tmp_path):
        """Init command should show helpful error for unimplemented htmx theme"""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "testproject", "--theme", "starter_htmx"])
            assert result.exit_code == 1
            assert "Theme 'starter_htmx' is not yet implemented" in result.output
            assert "Coming in v0.67.0" in result.output

    def test_init_with_react_theme_shows_error(self, tmp_path):
        """Init command should show helpful error for unimplemented react theme"""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "testproject", "--theme", "starter_react"])
            assert result.exit_code == 1
            assert "Theme 'starter_react' is not yet implemented" in result.output
            assert "Coming in v0.68.0" in result.output

    def test_init_with_invalid_theme(self, tmp_path):
        """Init command should reject completely invalid theme names"""
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(cli, ["init", "testproject", "--theme", "invalid"])
            assert result.exit_code == 2  # Click validation error
            assert "Invalid value for '--theme'" in result.output


class TestCLIThemeHelp:
    """Test CLI help text for themes"""

    def test_help_shows_theme_option(self):
        """Init help should document --theme option"""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "--theme" in result.output
        assert "starter_html" in result.output
        assert "starter_htmx" in result.output
        assert "starter_react" in result.output

    def test_help_shows_theme_descriptions(self):
        """Init help should include theme descriptions"""
        runner = CliRunner()
        result = runner.invoke(cli, ["init", "--help"])
        assert result.exit_code == 0
        assert "Pure HTML + CSS" in result.output
        assert "HTMX + Alpine.js" in result.output
        assert "React + TypeScript" in result.output
