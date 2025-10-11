"""Tests for QuickScale CLI main commands."""

import quickscale_cli
from quickscale_cli.main import cli


def test_cli_help(cli_runner):
    """Test CLI help command displays project information correctly."""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "QuickScale" in result.output
    assert "Django SaaS Project Generator" in result.output


def test_cli_version_flag(cli_runner):
    """Test version flag returns current package version."""
    result = cli_runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "quickscale" in result.output.lower()
    assert quickscale_cli.__version__ in result.output


def test_version_command(cli_runner):
    """Test version command displays CLI and core package versions."""
    result = cli_runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "QuickScale CLI" in result.output
    assert quickscale_cli.__version__ in result.output


def test_init_command_exists(cli_runner):
    """Test init command is registered and accessible via help."""
    result = cli_runner.invoke(cli, ["init", "--help"])
    assert result.exit_code == 0
    assert "Generate a new Django project" in result.output


def test_init_command_basic(cli_runner, sample_project_name):
    """Test init command accepts project name and displays placeholder message."""
    result = cli_runner.invoke(cli, ["init", sample_project_name])
    assert result.exit_code == 0
    assert sample_project_name in result.output
