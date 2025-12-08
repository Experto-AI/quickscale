"""Tests for QuickScale CLI main commands."""

import quickscale_cli
from quickscale_cli.main import cli


def test_cli_help(cli_runner):
    """Test CLI help command displays project information correctly"""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "QuickScale" in result.output
    assert "Compose your Django SaaS" in result.output


def test_cli_version_flag(cli_runner):
    """Test version flag returns current package version"""
    result = cli_runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "quickscale" in result.output.lower()
    assert quickscale_cli.__version__ in result.output


def test_version_command(cli_runner):
    """Test version command displays CLI and core package versions"""
    result = cli_runner.invoke(cli, ["version"])
    assert result.exit_code == 0
    assert "QuickScale CLI" in result.output
    assert quickscale_cli.__version__ in result.output


def test_plan_command_help(cli_runner):
    """Test plan command help displays correct information"""
    result = cli_runner.invoke(cli, ["plan", "--help"])
    assert result.exit_code == 0
    assert "quickscale.yml" in result.output
    assert "configuration" in result.output.lower()


def test_apply_command_help(cli_runner):
    """Test apply command help displays correct information"""
    result = cli_runner.invoke(cli, ["apply", "--help"])
    assert result.exit_code == 0
    assert "Execute project configuration" in result.output


def test_status_command_help(cli_runner):
    """Test status command help displays correct information"""
    result = cli_runner.invoke(cli, ["status", "--help"])
    assert result.exit_code == 0
    # Check for status-related content
    assert "status" in result.output.lower()


def test_remove_command_help(cli_runner):
    """Test remove command help displays correct information"""
    result = cli_runner.invoke(cli, ["remove", "--help"])
    assert result.exit_code == 0
    # Check for remove-related content
    assert "module" in result.output.lower()


def test_update_command_help(cli_runner):
    """Test update command help displays correct information"""
    result = cli_runner.invoke(cli, ["update", "--help"])
    assert result.exit_code == 0
    # Check for update-related content
    assert "update" in result.output.lower()


def test_cli_commands_available(cli_runner):
    """Test that expected CLI commands are available"""
    result = cli_runner.invoke(cli, ["--help"])
    assert result.exit_code == 0

    # These commands should be available (plan/apply workflow)
    assert "plan" in result.output
    assert "apply" in result.output
    assert "status" in result.output
    assert "remove" in result.output
    assert "update" in result.output

    # Verify deprecated init command is not available in help output
    # (removed in v0.72.0 in favor of plan/apply workflow)
    # Check that "  init" doesn't appear as a primary command line
    assert not any("  init" in line for line in result.output.splitlines())
