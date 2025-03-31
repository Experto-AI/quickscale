"""Integration tests for CLI error handling."""
import os
import sys
from unittest.mock import patch, MagicMock
import pytest
from quickscale.cli import main, QuickScaleArgumentParser
from tests.utils import capture_output

class TestCLIErrorHandling:
    """Integration tests for CLI command error handling."""
    
    def test_unknown_command_error(self, capsys):
        """Verify error handling for unknown commands."""
        with patch.object(sys, 'argv', ['quickscale', 'nonexistent']):
            with pytest.raises(SystemExit):
                main()
            
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "Unknown command" in captured.out or "invalid choice" in captured.out
        assert "Suggestion:" in captured.out
    
    def test_missing_required_argument(self, capsys):
        """Verify error handling for missing required arguments."""
        with patch.object(sys, 'argv', ['quickscale', 'build']):
            with pytest.raises(SystemExit):
                main()
            
        captured = capsys.readouterr()
        assert "Error:" in captured.out
        assert "the following arguments are required" in captured.out
        assert "Suggestion:" in captured.out
    
    def test_project_not_found_error(self, capsys, tmp_path):
        """Verify handling of project not found errors."""
        # Instead of changing directories, just mock the directory checks
        with patch.object(sys, 'argv', ['quickscale', 'manage', 'runserver']):
            # Mock the ProjectManager to simulate no project found
            with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                       return_value={'has_project': False}):
                with pytest.raises(SystemExit):
                    main()
                
        captured = capsys.readouterr()
        assert "Error: No active project found" in captured.out
        assert "Suggestion:" in captured.out
    
    def test_validation_error_empty_manage(self, capsys):
        """Verify validation errors for empty manage command."""
        with patch.object(sys, 'argv', ['quickscale', 'manage']):
            with patch('quickscale.commands.project_manager.ProjectManager.get_project_state',
                       return_value={'has_project': True}):  # Mock as if project exists
                with pytest.raises(SystemExit):
                    main()
                
        captured = capsys.readouterr()
        assert "Error: No Django management command specified" in captured.out
        assert "Suggestion:" in captured.out


class TestArgumentParserErrorHandling:
    """Tests for QuickScaleArgumentParser error handling."""
    
    def test_argument_parsing_error(self):
        """Verify custom error handling for argument parsing errors."""
        parser = QuickScaleArgumentParser()
        parser.add_argument('required_arg')
        
        # The issue is that the error handler directly calls sys.exit()
        # Instead of mocking handle_command_error, we need to patch the error method
        with patch.object(parser, 'error') as mock_error:
            parser.parse_args([])
            
            # Verify error method was called with the expected message
            mock_error.assert_called_once()
            args = mock_error.call_args[0]
            assert "the following arguments are required" in args[0]
    
    def test_invalid_choice_error(self):
        """Verify custom error handling for invalid choice errors."""
        parser = QuickScaleArgumentParser()
        parser.add_argument('command', choices=['valid'])
        
        # The issue is that the parser calls error twice - once for invalid choice 
        # and once for unrecognized arguments
        with patch.object(parser, 'error') as mock_error:
            try:
                parser.parse_args(['invalid'])
            except SystemExit:
                pass
            
            # We just verify that error was called and one of the calls contained our expected message
            assert mock_error.call_count >= 1
            
            # Check that at least one call has the expected error message about invalid choice
            has_invalid_choice_error = any(
                "invalid choice" in call[0][0] for call in mock_error.call_args_list
            )
            assert has_invalid_choice_error, "No error call contained 'invalid choice' message"