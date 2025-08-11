"""Comprehensive unit tests for CLI main function and argument parsing."""
import sys
import pytest
from unittest.mock import patch, Mock, MagicMock
from argparse import Namespace

from quickscale.cli import main, create_parser, handle_init_command, handle_check_command_output, handle_log_scan_output


class TestCLIMain:
    """Test cases for CLI main function."""
    
    def test_main_no_command(self, capsys):
        """Test main function with no command shows help."""
        with patch.object(sys, 'argv', ['quickscale']):
            result = main()
            captured = capsys.readouterr()
            
            assert result == 0
            assert 'usage:' in captured.out.lower()
    
    def test_main_init_command_success(self):
        """Test main function with init command."""
        with patch.object(sys, 'argv', ['quickscale', 'init', 'test-project']):
            with patch('quickscale.cli.handle_init_command', return_value=0) as mock_handle:
                result = main()
                
                assert result == 0
                mock_handle.assert_called_once()
                args = mock_handle.call_args[0][0]
                assert args.command == 'init'
                assert args.name == 'test-project'
    
    def test_main_init_command_failure(self):
        """Test main function with init command failure."""
        with patch.object(sys, 'argv', ['quickscale', 'init', 'test-project']):
            with patch('quickscale.cli.handle_init_command', return_value=1) as mock_handle:
                result = main()
                
                assert result == 1
    
    def test_main_check_command(self):
        """Test main function with check command."""
        with patch.object(sys, 'argv', ['quickscale', 'check']):
            with patch('quickscale.cli.handle_check_command_output') as mock_check_output:
                with patch('quickscale.cli.handle_log_scan_output') as mock_log_output:
                    with patch('quickscale.cli.command_manager') as mock_manager:
                        result = main()
                        
                        assert result == 0
                        mock_check_output.assert_called_once()
                        mock_log_output.assert_called_once()
                        mock_manager.handle_command.assert_called_once()
    
    def test_main_version_command(self):
        """Test main function with version command."""
        with patch.object(sys, 'argv', ['quickscale', 'version']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'version'
    
    def test_main_help_command(self):
        """Test main function with help command."""
        with patch.object(sys, 'argv', ['quickscale', 'help']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
    
    def test_main_unknown_command(self, capsys):
        """Test main function with unknown command."""
        with patch.object(sys, 'argv', ['quickscale', 'unknown-command']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                mock_manager.handle_command.side_effect = KeyError("Command 'unknown-command' not found")
                
                with pytest.raises(SystemExit) as exc_info:
                    result = main()
                
                captured = capsys.readouterr()
                
                # Should exit with error code 8 (UnknownCommandError)
                assert exc_info.value.code == 8
                assert "unknown command" in captured.out.lower()
    
    def test_main_command_execution_error(self, capsys):
        """Test main function with command execution error."""
        with patch.object(sys, 'argv', ['quickscale', 'up']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                mock_manager.handle_command.side_effect = Exception("Test error")
                
                result = main()
                captured = capsys.readouterr()
                
                assert result == 1
                assert "error occurred while executing 'up'" in captured.out.lower()
                assert "test error" in captured.out.lower()
    
    def test_main_service_commands(self):
        """Test main function with various service commands."""
        service_commands = ['up', 'down', 'ps', 'logs']
        
        for cmd in service_commands:
            with patch.object(sys, 'argv', ['quickscale', cmd]):
                with patch('quickscale.cli.command_manager') as mock_manager:
                    result = main()
                    
                    assert result == 0
                    mock_manager.handle_command.assert_called_once()
                    args = mock_manager.handle_command.call_args[0]
                    assert args[0] == cmd
    
    def test_main_service_up_with_no_cache(self):
        """Test main function with up command and --no-cache option."""
        with patch.object(sys, 'argv', ['quickscale', 'up', '--no-cache']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'up'
                assert args[1].no_cache is True
    
    def test_main_destroy_command(self):
        """Test main function with destroy command."""
        with patch.object(sys, 'argv', ['quickscale', 'destroy']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
    
    def test_main_destroy_with_delete_images(self):
        """Test main function with destroy command and --delete-images option."""
        with patch.object(sys, 'argv', ['quickscale', 'destroy', '--delete-images']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'destroy'
                assert args[1].delete_images is True
    
    def test_main_logs_command_with_options(self):
        """Test main function with logs command and various options."""
        with patch.object(sys, 'argv', [
            'quickscale', 'logs', 'web',
            '--follow', '--since', '1h', '--lines', '50', '--timestamps'
        ]):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'logs'
                assert args[1].service == 'web'
                assert args[1].follow is True
                assert args[1].since == '1h'
                assert args[1].lines == 50
                assert args[1].timestamps is True
    
    def test_main_shell_command(self):
        """Test main function with shell command."""
        with patch.object(sys, 'argv', ['quickscale', 'shell']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
    
    def test_main_shell_command_with_cmd(self):
        """Test main function with shell command and -c option."""
        with patch.object(sys, 'argv', ['quickscale', 'shell', '-c', 'ls -la']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                args = mock_manager.handle_command.call_args[0]
                assert args[1].cmd == 'ls -la'
    
    def test_main_django_shell_command(self):
        """Test main function with django-shell command."""
        with patch.object(sys, 'argv', ['quickscale', 'django-shell']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                mock_manager.handle_command.assert_called_once()
    
    def test_main_manage_command(self):
        """Test main function with manage command."""
        with patch.object(sys, 'argv', ['quickscale', 'manage', 'migrate', '--fake']):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'manage'
                assert args[1].args == ['migrate', '--fake']
    
    def test_main_generate_service_command(self):
        """Test main function with generate-service command."""
        with patch.object(sys, 'argv', [
            'quickscale', 'generate-service', 'test_service',
            '--type', 'text_processing',
            '--credit-cost', '2.5',
            '--description', 'Test service',
            '--skip-db-config'
        ]):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'generate-service'
                assert args[1].name == 'test_service'
                assert args[1].type == 'text_processing'
                assert args[1].credit_cost == 2.5
                assert args[1].description == 'Test service'
                assert args[1].skip_db_config is True
    
    def test_main_generate_service_free(self):
        """Test main function with generate-service command using --free flag."""
        with patch.object(sys, 'argv', [
            'quickscale', 'generate-service', 'free_service', '--free'
        ]):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                args = mock_manager.handle_command.call_args[0]
                assert args[1].free is True
    
    def test_main_validate_service_command(self):
        """Test main function with validate-service command."""
        with patch.object(sys, 'argv', [
            'quickscale', 'validate-service', 'test_service.py', '--tips'
        ]):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'validate-service'
                assert args[1].name_or_path == 'test_service.py'
                assert args[1].tips is True
    
    def test_main_show_service_examples_command(self):
        """Test main function with show-service-examples command."""
        with patch.object(sys, 'argv', [
            'quickscale', 'show-service-examples', '--type', 'text_processing'
        ]):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'show-service-examples'
                assert args[1].type == 'text_processing'
    
    def test_main_sync_back_command(self):
        """Test main function with sync-back command."""
        with patch.object(sys, 'argv', [
            'quickscale', 'sync-back', '/path/to/project',
            '--preview'
        ]):
            with patch('quickscale.cli.command_manager') as mock_manager:
                result = main()
                
                assert result == 0
                args = mock_manager.handle_command.call_args[0]
                assert args[0] == 'sync-back'
                assert args[1].project_path == '/path/to/project'
                assert args[1].preview is True
                assert args[1].interactive is False  # Should be False since we only used --preview


class TestCLIHelpers:
    """Test cases for CLI helper functions."""
    
    def test_create_parser(self):
        """Test parser creation."""
        parser, subparsers = create_parser()
        
        assert parser is not None
        assert subparsers is not None
        # In test environment, prog might be __main__.py instead of quickscale
        assert parser.prog in ['quickscale', '__main__.py']
    
    @patch('quickscale.cli.InitCommand')
    def test_handle_init_command_success(self, mock_init_command):
        """Test handle_init_command with successful initialization."""
        args = Namespace(name='test_project')  # Use valid Python identifier
        mock_init_instance = Mock()
        mock_init_command.return_value = mock_init_instance
        mock_init_instance.execute.return_value = None
        
        result = handle_init_command(args)
        
        assert result == 0
        mock_init_instance.execute.assert_called_once_with('test_project')
    
    @patch('quickscale.cli.command_manager')
    def test_handle_init_command_failure(self, mock_manager):
        """Test handle_init_command with initialization failure."""
        args = Namespace(name='test-project')
        mock_manager.init_project.side_effect = Exception("Init failed")
        
        with patch('quickscale.utils.message_manager.MessageManager') as mock_msg:
            result = handle_init_command(args)
            
            assert result == 1
            mock_msg.error.assert_called()
    
    @patch('quickscale.cli.command_manager')
    def test_handle_check_command_output(self, mock_manager):
        """Test handle_check_command_output function."""
        args = Mock()
        args.db_verification = {'database': True, 'web_service': {'static_files': True}}
        
        handle_check_command_output(args)
        
        # Should call check_requirements but not cause any errors
        assert True  # Function should complete without error
    
    def test_handle_log_scan_output(self):
        """Test handle_log_scan_output function."""
        args = Mock()
        # Mock the log_scan attribute with proper structure
        args.log_scan = {
            'total_issues': 2,
            'error_count': 1,
            'logs_accessed': True,
            'real_errors': False
        }
        
        # Should complete without error 
        handle_log_scan_output(args)
        assert True
    
    def test_argument_parsing_edge_cases(self):
        """Test edge cases in argument parsing."""
        parser, subparsers = create_parser()
        
        # Import parser setup functions
        from quickscale.cli import (
            setup_service_parsers, setup_utility_parsers, setup_logs_parser,
            setup_manage_parser, setup_service_generator_parsers,
            setup_sync_back_parser, setup_help_and_version_parsers, setup_init_parser
        )
        
        # Set up all parsers
        setup_init_parser(subparsers)
        setup_service_parsers(subparsers)
        setup_utility_parsers(subparsers)
        setup_logs_parser(subparsers)
        setup_manage_parser(subparsers)
        setup_service_generator_parsers(subparsers)
        setup_sync_back_parser(subparsers)
        setup_help_and_version_parsers(subparsers)
        
        # Test with empty arguments (should not crash)
        args = parser.parse_args([])
        assert args.command is None
        
        # Test help command
        args = parser.parse_args(['help'])
        assert args.command == 'help'
        
        # Test version command
        args = parser.parse_args(['version'])
        assert args.command == 'version'
    
    def test_service_command_arguments(self):
        """Test service command argument parsing."""
        parser, subparsers = create_parser()
        
        # Import parser setup functions
        from quickscale.cli import (
            setup_service_parsers, setup_utility_parsers, setup_logs_parser,
            setup_manage_parser, setup_service_generator_parsers,
            setup_sync_back_parser, setup_help_and_version_parsers, setup_init_parser
        )
        
        # Set up all parsers
        setup_init_parser(subparsers)
        setup_service_parsers(subparsers)
        setup_utility_parsers(subparsers)
        setup_logs_parser(subparsers)
        setup_manage_parser(subparsers)
        setup_service_generator_parsers(subparsers)
        setup_sync_back_parser(subparsers)
        setup_help_and_version_parsers(subparsers)
        
        # Test up command with --no-cache
        args = parser.parse_args(['up', '--no-cache'])
        assert args.command == 'up'
        assert args.no_cache is True
        
        # Test logs command with all options
        args = parser.parse_args([
            'logs', 'web', '--follow', '--since', '1h', 
            '--lines', '50', '--timestamps'
        ])
        assert args.command == 'logs'
        assert args.service == 'web'
        assert args.follow is True
        assert args.since == '1h'
        assert args.lines == 50
        assert args.timestamps is True
        
        # Test generate-service with all options
        args = parser.parse_args([
            'generate-service', 'test_service',
            '--type', 'text_processing',
            '--output', '/custom/dir',
            '--credit-cost', '2.5',
            '--description', 'Test service',
            '--skip-db-config',
            '--free'
        ])
        assert args.command == 'generate-service'
        assert args.name == 'test_service'
        assert args.type == 'text_processing'
        assert args.output_dir == '/custom/dir'
        assert args.credit_cost == 2.5
        assert args.description == 'Test service'
        assert args.skip_db_config is True
        assert args.free is True
        
        # Test validate-service command
        args = parser.parse_args(['validate-service', 'test.py', '--tips'])
        assert args.command == 'validate-service'
        assert args.name_or_path == 'test.py'
        assert args.tips is True
        
        # Test show-service-examples command
        args = parser.parse_args(['show-service-examples', '--type', 'text_processing'])
        assert args.command == 'show-service-examples'
        assert args.type == 'text_processing'
        
        # Test sync-back command with individual flags (mutually exclusive)
        args = parser.parse_args([
            'sync-back', '/path/to/project',
            '--preview'
        ])
        assert args.command == 'sync-back'
        assert args.project_path == '/path/to/project'
        assert args.preview is True
        
        args = parser.parse_args([
            'sync-back', '/path/to/project',
            '--apply'
        ])
        assert args.command == 'sync-back'
        assert args.project_path == '/path/to/project'
        assert args.apply is True
        
        args = parser.parse_args([
            'sync-back', '/path/to/project',
            '--interactive'
        ])
        assert args.command == 'sync-back'
        assert args.project_path == '/path/to/project'
        assert args.interactive is True
        
        # Test manage command
        args = parser.parse_args(['manage', 'migrate', '--fake', 'app_name'])
        assert args.command == 'manage'
        assert args.args == ['migrate', '--fake', 'app_name']


class TestCLIIntegration:
    """Integration tests for CLI functionality."""
    
    @patch('quickscale.cli.command_manager')
    @patch('sys.argv', ['quickscale', 'sync-back', '/some/path', '--preview'])
    def test_full_command_flow(self, mock_manager):
        """Test complete command flow from CLI to command manager."""
        # Test specific command flow
        result = main()
        assert result == 0
        
        # Verify command manager was called
        mock_manager.handle_command.assert_called()
    
    def test_error_propagation(self, capsys):
        """Test that errors are properly propagated and displayed."""
        error_scenarios = [
            (KeyError("Command not found"), "command error:"),
            (Exception("General error"), "error occurred while executing"),
        ]
        
        for error, expected_text in error_scenarios:
            with patch.object(sys, 'argv', ['quickscale', 'up']):
                with patch('quickscale.cli.command_manager') as mock_manager:
                    mock_manager.handle_command.side_effect = error
                    
                    result = main()
                    captured = capsys.readouterr()
                    
                    assert result == 1
                    assert expected_text in captured.out.lower()
                    
                    # Reset capture
                    capsys.readouterr()
