"""Comprehensive CLI tests for quickscale main function."""
import sys
import argparse
import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import tempfile

from quickscale.cli import main


class TestCLIMain:
    """Comprehensive tests for CLI main function."""
    
    @patch('sys.argv', ['quickscale'])
    def test_main_no_arguments(self):
        """Test main with no arguments shows help."""
        # When no command is provided, argparse will print help and return 0
        # This is handled by argparse itself, not by CommandManager
        result = main()
        assert result == 0
    
    @patch('sys.argv', ['quickscale', '--help'])
    def test_main_help_argument(self):
        """Test main with --help argument (should cause SystemExit)."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # argparse exits with code 0 for help
        assert exc_info.value.code == 0
    
    @patch('sys.argv', ['quickscale', 'invalid_command'])
    def test_main_invalid_command(self):
        """Test main with invalid command."""
        with pytest.raises(SystemExit) as exc_info:
            main()
        
        # Should exit with error code 8 (UnknownCommandError)
        assert exc_info.value.code == 8


class TestCLIErrorHandling:
    """Test CLI error handling scenarios."""
    
    @patch('sys.argv', ['quickscale', 'init'])  # Missing required argument
    def test_main_command_with_missing_args(self):
        """Test main with command missing required arguments."""
        # This should raise SystemExit due to argparse error
        with pytest.raises(SystemExit):
            main()
    
    @patch('sys.argv', ['quickscale', 'logs', '--lines', 'invalid'])
    def test_main_invalid_argument_type(self):
        """Test main with invalid argument type."""
        # This should raise SystemExit due to argparse error
        with pytest.raises(SystemExit):
            main()


class TestCLIParserConfiguration:
    """Test CLI argument parser configuration."""
    
    def test_parser_creation(self):
        """Test that parser is created correctly."""
        from quickscale.cli import (
            create_parser, setup_init_parser, setup_service_parsers,
            setup_utility_parsers, setup_logs_parser, setup_manage_parser,
            setup_service_generator_parsers, setup_sync_back_parser,
            setup_help_and_version_parsers
        )
        
        parser, subparsers = create_parser()
        
        # Set up all parsers like in main()
        setup_init_parser(subparsers)
        setup_service_parsers(subparsers)
        setup_utility_parsers(subparsers)
        setup_logs_parser(subparsers)
        setup_manage_parser(subparsers)
        setup_service_generator_parsers(subparsers)
        setup_sync_back_parser(subparsers)
        setup_help_and_version_parsers(subparsers)
        
        assert parser is not None
        assert isinstance(parser, argparse.ArgumentParser)
        
        # Test that all expected subcommands exist
        expected_commands = [
            'init', 'up', 'down', 'logs', 'ps', 'shell', 'django-shell',
            'manage', 'sync-back', 'generate-service', 'validate-service',
            'show-service-examples', 'check', 'destroy', 'help', 'version'
        ]
        
        for command in expected_commands:
            assert command in subparsers.choices
    
    def test_init_parser_configuration(self):
        """Test init subparser configuration."""
        from quickscale.cli import create_parser, setup_init_parser
        
        parser, subparsers = create_parser()
        setup_init_parser(subparsers)
        
        # Test parsing init command
        args = parser.parse_args(['init', 'test_project'])
        assert args.command == 'init'
        assert args.name == 'test_project'
    
    def test_logs_parser_configuration(self):
        """Test logs subparser configuration."""
        from quickscale.cli import create_parser, setup_logs_parser
        
        parser, subparsers = create_parser()
        setup_logs_parser(subparsers)
        
        # Test parsing logs command with all options
        args = parser.parse_args(['logs', 'web', '--follow', '--lines', '100'])
        assert args.command == 'logs'
        assert args.service == 'web'
        assert args.follow is True
        assert args.lines == 100
        
        # Test parsing logs command with no follow by default
        args = parser.parse_args(['logs'])
        assert args.follow is False
    
    def test_generate_service_parser_configuration(self):
        """Test generate-service subparser configuration."""
        from quickscale.cli import create_parser, setup_service_generator_parsers
        
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Test parsing generate-service command with all options
        args = parser.parse_args([
            'generate-service', 'test_service',
            '--type', 'text_processing',
            '--credit-cost', '2.5',
            '--description', 'Test service',
            '--skip-db-config'
        ])
        
        assert args.command == 'generate-service'
        assert args.name == 'test_service'
        assert args.type == 'text_processing'
        assert args.credit_cost == 2.5
        assert args.description == 'Test service'
        assert args.skip_db_config is True
