"""Tests for Sprint 14 CLI integration features."""
import unittest
from unittest.mock import patch, MagicMock, mock_open
import argparse
import sys
from io import StringIO

# Import the actual command manager and setup functions
from quickscale.commands.command_manager import CommandManager
from quickscale.cli import create_parser, setup_service_generator_parsers


class TestSprint14CLIIntegration(unittest.TestCase):
    """Test Sprint 14 CLI integration features."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.command_manager = CommandManager()
    
    def test_generate_service_command_registration(self):
        """Test that generate-service command is properly registered."""
        # Create parser with service generator commands
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Test that generate-service command exists
        with patch('sys.argv', ['quickscale', 'generate-service', 'test_service']):
            try:
                args = parser.parse_args(['generate-service', 'test_service'])
                self.assertEqual(args.command, 'generate-service')
                self.assertEqual(args.name, 'test_service')
            except SystemExit:
                self.fail("generate-service command should be registered")
    
    def test_generate_service_command_arguments(self):
        """Test generate-service command argument parsing."""
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Test basic service generation with default type
        args = parser.parse_args(['generate-service', 'my_service'])
        self.assertEqual(args.command, 'generate-service')
        self.assertEqual(args.name, 'my_service')
        self.assertEqual(args.type, 'basic')  # Default value is 'basic'
        
        # Test service generation with type
        args = parser.parse_args(['generate-service', 'my_service', '--type', 'text_processing'])
        self.assertEqual(args.command, 'generate-service')
        self.assertEqual(args.name, 'my_service')
        self.assertEqual(args.type, 'text_processing')
    
    def test_generate_service_command_output_directory(self):
        """Test generate-service command with output directory."""
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Test with output directory (note: CLI uses --output-dir not --output)
        args = parser.parse_args(['generate-service', 'my_service', '--output-dir', '/custom/path'])
        self.assertEqual(args.command, 'generate-service')
        self.assertEqual(args.name, 'my_service')
        self.assertEqual(getattr(args, 'output_dir'), '/custom/path')
    
    @patch('quickscale.commands.command_manager.CommandManager.execute_command')
    def test_command_manager_service_generation(self, mock_execute_command):
        """Test that command manager properly handles service generation."""
        mock_execute_command.return_value = {'success': True}
        
        # Test service generation through command manager
        result = self.command_manager.generate_service('test_service')
        
        mock_execute_command.assert_called_once_with('generate-service', 'test_service', service_type='basic', output_dir=None)
        self.assertEqual(result, {'success': True})
    
    def test_service_generator_help_text(self):
        """Test that generate-service command has proper help text."""
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Capture help output
        with patch('sys.stdout', new_callable=StringIO) as mock_stdout:
            with patch('sys.stderr', new_callable=StringIO):
                try:
                    parser.parse_args(['generate-service', '--help'])
                except SystemExit:
                    pass  # Help command exits normally
        
        help_output = mock_stdout.getvalue()
        self.assertIn('generate-service', help_output)
        self.assertIn('Generate a new AI service template', help_output)
    
    def test_invalid_service_name_handling(self):
        """Test handling of invalid service names."""
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Test missing service name
        with patch('sys.stderr', new_callable=StringIO):
            with self.assertRaises(SystemExit):
                parser.parse_args(['generate-service'])
    
    def test_service_type_validation(self):
        """Test validation of service types."""
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Test valid service types
        valid_types = ['basic', 'text_processing', 'image_processing']
        for service_type in valid_types:
            args = parser.parse_args(['generate-service', 'test_service', '--type', service_type])
            self.assertEqual(args.type, service_type)
    
    @patch('quickscale.commands.service_generator_commands.os.makedirs')
    @patch('quickscale.commands.service_generator_commands.os.path.exists')
    @patch('builtins.input', return_value='n')  # Mock input to return 'n' (no overwrite)
    def test_service_generator_command_execution(self, mock_input, mock_exists, mock_makedirs):
        """Test service generator command execution through command manager."""
        mock_exists.return_value = True  # File exists
        mock_makedirs.return_value = None
        
        # Test that service generation works
        result = self.command_manager.generate_service('test_service')
        
        # Should fail because user chose not to overwrite existing file
        self.assertFalse(result.get('success', False))
        self.assertEqual(result.get('reason'), 'File already exists')
    
    def test_command_manager_methods(self):
        """Test that command manager has the expected methods."""
        # Test that generate_service method exists and is callable
        self.assertTrue(hasattr(self.command_manager, 'generate_service'))
        self.assertTrue(callable(getattr(self.command_manager, 'generate_service')))
        
        # Test that execute_command method exists and is callable
        self.assertTrue(hasattr(self.command_manager, 'execute_command'))
        self.assertTrue(callable(getattr(self.command_manager, 'execute_command')))
    
    def test_list_services_command_registration(self):
        """Test that list-services command is properly registered."""
        parser, subparsers = create_parser()
        setup_service_generator_parsers(subparsers)
        
        # Test list-services command
        args = parser.parse_args(['list-services'])
        self.assertEqual(args.command, 'list-services')
        
        # Test with details flag
        args = parser.parse_args(['list-services', '--details'])
        self.assertEqual(args.command, 'list-services')
        self.assertTrue(args.details)


if __name__ == '__main__':
    unittest.main() 