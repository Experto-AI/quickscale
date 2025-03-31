"""Unit tests for CLI commands."""
import sys
from unittest.mock import patch, MagicMock
import pytest
from quickscale.cli import main
from quickscale.commands import command_manager

class TestCLICommands:
    """Test cases for individual CLI commands."""
    
    def test_version_command(self, capsys):
        """Test version command outputs correct information."""
        with patch.object(sys, 'argv', ['quickscale', 'version']):
            main()
            captured = capsys.readouterr()
            assert "QuickScale" in captured.out
            assert "version" in captured.out.lower()
    
    def test_help_command(self, capsys):
        """Test help command displays usage information."""
        with patch.object(sys, 'argv', ['quickscale', 'help']):
            main()
            captured = capsys.readouterr()
            assert "usage:" in captured.out.lower()
            assert "command" in captured.out.lower()
    
    def test_check_command(self):
        """Test check command runs requirements verification."""
        with patch.object(sys, 'argv', ['quickscale', 'check']):
            with patch.object(command_manager, 'check_requirements') as mock_check:
                main()
                mock_check.assert_called_once_with(print_info=True)
    
    def test_invalid_command(self, capsys):
        """Test invalid command handling."""
        with patch.object(sys, 'argv', ['quickscale', 'invalid_command']):
            try:
                result = main()
                captured = capsys.readouterr()
                assert result == 1
                assert "usage:" in captured.out.lower() or "unknown command" in captured.out.lower() or "invalid command" in captured.out.lower()
            except SystemExit as e:
                # Handle the case where argparse exits with sys.exit()
                assert e.code != 0