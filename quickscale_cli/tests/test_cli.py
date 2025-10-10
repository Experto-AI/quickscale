"""Tests for QuickScale CLI main commands."""

import quickscale_cli
from quickscale_cli.main import cli


def test_cli_help(cli_runner):
    """Test that CLI help works."""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "QuickScale" in result.output
    assert "Django SaaS Project Generator" in result.output


def test_cli_version_flag(cli_runner):
    """Test that --version flag works."""
    result = cli_runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "quickscale" in result.output.lower()
    assert quickscale_cli.__version__ in result.output


def test_version_command(cli_runner):
    """Test that version command works."""
    result = cli_runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "QuickScale CLI" in result.output
    assert quickscale_cli.__version__ in result.output


def test_init_command_exists(cli_runner):
    """Test that init command is available."""
    result = cli_runner.invoke(cli, ["init", "--help"])
    assert result.exit_code == 0
    assert "Generate a new Django project" in result.output


def test_init_command_basic(cli_runner, sample_project_name):
    """Test that init command runs (even though not fully implemented)."""
    result = cli_runner.invoke(cli, ["init", sample_project_name])
    assert result.exit_code == 0
    assert sample_project_name in result.output
