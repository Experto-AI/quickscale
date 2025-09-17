"""Unit tests for CLI commands."""
import sys
from unittest.mock import patch

from quickscale.cli import main
from quickscale.commands import command_manager


class TestCLICommands:
    """Test cases for individual CLI commands."""
    
    def test_check_command(self):
        """Test check command runs requirements verification."""
        with patch.object(sys, 'argv', ['quickscale', 'check']):
            with patch.object(command_manager, 'check_requirements') as mock_check:
                main()
                mock_check.assert_called_once_with(print_info=True)
                
    def test_command_execution_error(self, capsys):
        """Test error handling during command execution."""
        with patch.object(sys, 'argv', ['quickscale', 'check']):
            with patch.object(command_manager, 'handle_command', side_effect=Exception("Test error")):
                result = main()
                captured = capsys.readouterr()
                assert result == 1
                assert "an error occurred while executing 'check'" in captured.out.lower()
                assert "test error" in captured.out.lower()
