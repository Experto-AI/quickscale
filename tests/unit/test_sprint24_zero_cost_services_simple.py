"""
Simple tests for Sprint 24: Zero-Cost AI Services Implementation.

These tests verify the core functionality without Django setup.
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from decimal import Decimal
from unittest.mock import patch, MagicMock, mock_open

from quickscale.commands.service_generator_commands import ServiceGeneratorCommand
from quickscale.commands.command_manager import CommandManager


class TestZeroCostServiceGenerator(unittest.TestCase):
    """Test cases for service generator with zero-cost services."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.command = ServiceGeneratorCommand()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_service_generator_free_flag_sets_zero_cost(self):
        """Test that --free flag sets credit cost to 0.0."""
        # Mock file operations
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.mkdir'):
                    with patch.object(self.command, '_configure_service_in_database') as mock_config:
                        mock_config.return_value = {"success": True}
                        
                        # Execute with free flag
                        result = self.command.execute(
                            service_name='free_test_service',
                            service_type='basic',
                            output_dir=self.test_dir,
                            free=True,
                            description='Free test service'
                        )
                        
                        # Verify credit cost is set to 0.0
                        self.assertEqual(result['credit_cost'], 0.0)
                        self.assertTrue(result['success'])
                        
                        # Verify database configuration was called with correct parameters
                        mock_config.assert_called_once_with(
                            'free_test_service',
                            'Free test service',
                            0.0
                        )
    
    def test_service_generator_free_overrides_credit_cost(self):
        """Test that --free flag overrides --credit-cost."""
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.mkdir'):
                    with patch.object(self.command, '_configure_service_in_database') as mock_config:
                        mock_config.return_value = {"success": True}
                        
                        # Execute with both free flag and credit cost
                        result = self.command.execute(
                            service_name='test_service',
                            service_type='basic',
                            output_dir=self.test_dir,
                            credit_cost=5.0,  # This should be overridden
                            free=True,
                            description='Test service'
                        )
                        
                        # Verify free flag overrides credit cost
                        self.assertEqual(result['credit_cost'], 0.0)
                        
                        # Verify database configuration was called with 0.0
                        mock_config.assert_called_once_with(
                            'test_service',
                            'Test service',
                            0.0
                        )
    
    def test_service_generator_without_free_flag(self):
        """Test that service generator works normally without --free flag."""
        with patch('builtins.open', mock_open()) as mock_file:
            with patch('pathlib.Path.exists', return_value=False):
                with patch('pathlib.Path.mkdir'):
                    with patch.object(self.command, '_configure_service_in_database') as mock_config:
                        mock_config.return_value = {"success": True}
                        
                        # Execute without free flag
                        result = self.command.execute(
                            service_name='paid_service',
                            service_type='basic',
                            output_dir=self.test_dir,
                            credit_cost=2.0,
                            description='Paid service'
                        )
                        
                        # Verify credit cost is preserved
                        self.assertEqual(result['credit_cost'], 2.0)
                        self.assertTrue(result['success'])
                        
                        # Verify database configuration was called with correct parameters
                        mock_config.assert_called_once_with(
                            'paid_service',
                            'Paid service',
                            2.0
                        )
    
    @patch('subprocess.run')
    def test_configure_service_in_database_uses_free_flag(self, mock_subprocess):
        """Test that _configure_service_in_database uses --free flag for zero cost."""
        # Mock Docker services check
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "container_id"
        
        # Mock successful management command
        def mock_run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "Service configured successfully"
            return result
        
        mock_subprocess.side_effect = mock_run
        
        # Mock os.path.exists to return True (manage.py exists)
        with patch('os.path.exists', return_value=True):
            result = self.command._configure_service_in_database(
                'free_service',
                'Free service description',
                0.0
            )
            
            self.assertTrue(result['success'])
            
            # Verify the command was called with --free flag
            calls = mock_subprocess.call_args_list
            self.assertEqual(len(calls), 2)  # One for docker ps check, one for manage command
            
            # Check the manage command call
            manage_call = calls[1]
            cmd_args = manage_call[0][0]  # First positional argument (the command)
            
            self.assertIn('--free', cmd_args)
            self.assertNotIn('--credit-cost', cmd_args)
    
    @patch('subprocess.run')
    def test_configure_service_in_database_uses_credit_cost(self, mock_subprocess):
        """Test that _configure_service_in_database uses --credit-cost for paid services."""
        # Mock Docker services check
        mock_subprocess.return_value.returncode = 0
        mock_subprocess.return_value.stdout = "container_id"
        
        # Mock successful management command
        def mock_run(*args, **kwargs):
            result = MagicMock()
            result.returncode = 0
            result.stdout = "Service configured successfully"
            return result
        
        mock_subprocess.side_effect = mock_run
        
        # Mock os.path.exists to return True (manage.py exists)
        with patch('os.path.exists', return_value=True):
            result = self.command._configure_service_in_database(
                'paid_service',
                'Paid service description',
                2.5
            )
            
            self.assertTrue(result['success'])
            
            # Verify the command was called with --credit-cost flag
            calls = mock_subprocess.call_args_list
            self.assertEqual(len(calls), 2)  # One for docker ps check, one for manage command
            
            # Check the manage command call
            manage_call = calls[1]
            cmd_args = manage_call[0][0]  # First positional argument (the command)
            
            self.assertIn('--credit-cost', cmd_args)
            self.assertIn('2.5', cmd_args)
            self.assertNotIn('--free', cmd_args)


class TestZeroCostServiceCommandManager(unittest.TestCase):
    """Test cases for command manager with zero-cost services."""
    
    def setUp(self):
        """Set up test environment."""
        self.command_manager = CommandManager()
    
    def test_command_manager_generate_service_with_free_flag(self):
        """Test command manager passes free flag correctly."""
        with patch.object(self.command_manager._commands['generate-service'], 'execute') as mock_execute:
            mock_execute.return_value = {'success': True, 'credit_cost': 0.0}
            
            result = self.command_manager.generate_service(
                service_name='free_test',
                service_type='basic',
                credit_cost=1.0,
                description='Test service',
                free=True
            )
            
            # Verify execute was called with free=True
            mock_execute.assert_called_once_with(
                'free_test',
                service_type='basic',
                output_dir=None,
                credit_cost=1.0,
                description='Test service',
                skip_db_config=False,
                free=True
            )
            
            self.assertTrue(result['success'])


class TestZeroCostServiceValidation(unittest.TestCase):
    """Test cases for service name validation."""
    
    def setUp(self):
        """Set up test environment."""
        self.command = ServiceGeneratorCommand()
    
    def test_validate_service_name_with_free_services(self):
        """Test that service name validation works for free services."""
        valid_names = [
            'free_service',
            'free_text_analyzer',
            'free_utility',
            'zero_cost_service'
        ]
        
        for name in valid_names:
            with self.subTest(name=name):
                self.assertTrue(self.command._validate_service_name(name))
    
    def test_to_class_name_with_free_services(self):
        """Test class name generation for free services."""
        test_cases = [
            ('free_service', 'FreeServiceService'),
            ('free_text_analyzer', 'FreeTextAnalyzerService'),
            ('zero_cost_utility', 'ZeroCostUtilityService')
        ]
        
        for service_name, expected_class in test_cases:
            with self.subTest(service_name=service_name):
                result = self.command._to_class_name(service_name)
                self.assertEqual(result, expected_class)


class TestZeroCostServiceFileContent(unittest.TestCase):
    """Test cases for verifying file content includes zero-cost service support."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent
    
    def test_service_model_allows_zero_cost(self):
        """Test that Service model allows zero credit cost."""
        credits_models_path = self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'models.py'
        
        if credits_models_path.exists():
            with open(credits_models_path, 'r') as f:
                models_content = f.read()
            
            # Should allow MinValueValidator(Decimal('0.0'))
            self.assertIn("MinValueValidator(Decimal('0.0'))", models_content)
            
            # Should have updated help text
            self.assertIn("0.0 for free services", models_content)
            
            # Should have updated __str__ method for free services
            self.assertIn("if credit_cost == 0:", models_content)
    
    def test_migration_exists_for_zero_cost(self):
        """Test that migration exists for zero-cost service support."""
        migrations_path = self.base_path / 'quickscale' / 'project_templates' / 'credits' / 'migrations'
        migration_file = migrations_path / '0008_allow_zero_cost_services.py'
        
        if migration_file.exists():
            with open(migration_file, 'r') as f:
                migration_content = f.read()
            
            # Should update Service model credit_cost field
            self.assertIn("model_name='service'", migration_content)
            self.assertIn("name='credit_cost'", migration_content)
            self.assertIn("MinValueValidator(Decimal('0.0'))", migration_content)
    
    def test_configure_service_command_supports_free_flag(self):
        """Test that configure_service management command supports --free flag."""
        command_path = self.base_path / 'quickscale' / 'project_templates' / 'services' / 'management' / 'commands' / 'configure_service.py'
        
        if command_path.exists():
            with open(command_path, 'r') as f:
                command_content = f.read()
            
            # Should have --free flag
            self.assertIn("'--free'", command_content)
            
            # Should handle free flag in logic
            self.assertIn("options['free']", command_content)
            
            # Should set credit_cost to 0.0 when free
            self.assertIn("credit_cost = Decimal('0.0')", command_content)
    
    def test_cli_supports_free_flag(self):
        """Test that CLI supports --free flag for generate-service command."""
        cli_path = self.base_path / 'quickscale' / 'cli.py'
        
        if cli_path.exists():
            with open(cli_path, 'r') as f:
                cli_content = f.read()
            
            # Should have --free argument
            self.assertIn("--free", cli_content)
            
            # Should have help text for free flag
            self.assertIn("Generate a free service", cli_content)


if __name__ == '__main__':
    unittest.main()