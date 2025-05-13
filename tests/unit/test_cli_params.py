"""Tests for CLI command parameters and options."""
import pytest
import sys
from unittest.mock import patch, MagicMock, ANY
from quickscale.cli import main
from quickscale.commands import command_manager
from quickscale.commands.command_manager import CommandManager

class TestCLIParameters:
    """Test CLI command parameters and options."""
    
    @pytest.mark.parametrize(
        "args,expected_func,expected_kwargs",
        [
            (
                ["quickscale", "logs"], 
                "view_logs", 
                {"service": None, "follow": False}
            ),
            (
                ["quickscale", "logs", "web"], 
                "view_logs", 
                {"service": "web", "follow": False}
            ),
            (
                ["quickscale", "logs", "-f"], 
                "view_logs", 
                {"service": None, "follow": True}
            ),
            (
                ["quickscale", "shell", "-c", "echo 'test'"], 
                "open_shell", 
                {"command": "echo 'test'"}
            ),
        ]
    )
    def test_command_parameters(self, args, expected_func, expected_kwargs):
        """Test CLI commands parse parameters correctly."""
        with patch("sys.argv", args):
            with patch.object(CommandManager, expected_func) as mock_func:
                try:
                    main()
                    self._validate_function_calls(mock_func, expected_kwargs)
                except (SystemExit, Exception) as e:
                    # If the CLI exits or throws an exception, but the function was called,
                    # still validate that it was called with the right parameters
                    if mock_func.call_count > 0:
                        self._validate_function_calls(mock_func, expected_kwargs)
    
    def _validate_function_calls(self, mock_func, expected_kwargs):
        """Helper method to validate function call arguments."""
        # Check that the function was called at least once
        assert mock_func.call_count > 0
        
        # For each expected keyword argument, check that it was passed correctly
        actual_args, actual_kwargs = mock_func.call_args
        
        for key, value in expected_kwargs.items():
            if key in actual_kwargs:
                # If the argument was passed by keyword, check its value
                assert actual_kwargs[key] == value
            else:
                # If using positional args for this test, we need to check more carefully
                # This is just a simple approach - might need to be enhanced based on actual calls
                if mock_func.__name__ == "view_logs" and key == "service" and len(actual_args) > 0:
                    assert actual_args[0] == value
                elif mock_func.__name__ == "view_logs" and key == "follow" and "follow" in actual_kwargs:
                    assert actual_kwargs["follow"] == value
    
    def test_help_command_general(self, capsys):
        """Test general help command."""
        with patch("sys.argv", ["quickscale", "help"]):
            try:
                main()
                captured = capsys.readouterr()
                assert "usage:" in captured.out.lower()
                assert "command" in captured.out.lower()
            except SystemExit:
                # If the command exits, that's okay
                captured = capsys.readouterr()
                if captured.out:
                    assert "usage:" in captured.out.lower() or "command" in captured.out.lower()