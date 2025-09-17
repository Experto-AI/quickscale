"""
Tests for default services creation functionality.

This test verifies that the default services creation management command works correctly
and that the new demo_free_service example is properly implemented.
"""

import unittest
from pathlib import Path


class DefaultServicesTests(unittest.TestCase):
    """Test cases for default services creation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(__file__).parent.parent.parent.parent
        self.services_app_path = self.base_path / 'quickscale' / 'project_templates' / 'services'
    
    def test_create_default_services_management_command_exists(self):
        """Test that the create_default_services management command exists."""
        command_path = self.services_app_path / 'management' / 'commands' / 'create_default_services.py'
        self.assertTrue(command_path.exists(), 
                       "create_default_services management command should exist")
        
        # Check for proper command structure
        with open(command_path, 'r') as f:
            command_content = f.read()
        
        self.assertIn("class Command(BaseCommand)", command_content,
                     "Command class should inherit from BaseCommand")
        self.assertIn("def handle(self", command_content,
                     "Command should have handle method")
        self.assertIn("create_default_services", command_content,
                     "Command should have create_default_services method")
    
    def test_demo_free_service_implementation_exists(self):
        """Test that the demo_free_service is implemented in examples.py."""
        examples_path = self.services_app_path / 'examples.py'
        
        with open(examples_path, 'r') as f:
            examples_content = f.read()
        
        # Check for demo free service
        self.assertIn('@register_service("demo_free_service")', examples_content,
                     "demo_free_service should be registered")
        self.assertIn("class DemoFreeService(BaseService)", examples_content,
                     "DemoFreeService class should exist")
        self.assertIn("def execute_service(self, user: 'AbstractUser', message:", examples_content,
                     "DemoFreeService should have execute_service method")
    
    def test_demo_free_service_returns_proper_structure(self):
        """Test that demo_free_service returns the expected data structure."""
        examples_path = self.services_app_path / 'examples.py'
        
        with open(examples_path, 'r') as f:
            examples_content = f.read()
        
        # Check for expected return structure
        self.assertIn("'cost': 'FREE'", examples_content,
                     "demo_free_service should indicate it's free")
        self.assertIn("'success': True", examples_content,
                     "demo_free_service should return success indicator")
        self.assertIn("'result':", examples_content,
                     "demo_free_service should return result structure")
    
    def test_entrypoint_calls_create_default_services(self):
        """Test that entrypoint.sh calls the create_default_services command."""
        entrypoint_path = self.base_path / 'quickscale' / 'project_templates' / 'entrypoint.sh'
        
        with open(entrypoint_path, 'r') as f:
            entrypoint_content = f.read()
        
        self.assertIn("python manage.py create_default_services", entrypoint_content,
                     "entrypoint.sh should call create_default_services")
        self.assertIn("Creating default example services", entrypoint_content,
                     "entrypoint.sh should have descriptive message for service creation")
    
    def test_default_services_list_matches_examples(self):
        """Test that services created by default match those in examples.py."""
        command_path = self.services_app_path / 'management' / 'commands' / 'create_default_services.py'
        examples_path = self.services_app_path / 'examples.py'
        
        with open(command_path, 'r') as f:
            command_content = f.read()
        
        with open(examples_path, 'r') as f:
            examples_content = f.read()
        
        # Services that should be created by default
        expected_services = [
            'text_sentiment_analysis',
            'image_metadata_extractor',
            'demo_free_service'
        ]
        
        for service_name in expected_services:
            with self.subTest(service=service_name):
                # Check that service is in default creation list
                self.assertIn(f"'name': '{service_name}'", command_content,
                             f"Service {service_name} should be in default creation list")
                
                # Check that service is implemented in examples.py
                self.assertIn(f'@register_service("{service_name}")', examples_content,
                             f"Service {service_name} should be registered in examples.py")
    
    def test_management_commands_have_init_files(self):
        """Test that management command directories have proper __init__.py files."""
        management_init = self.services_app_path / 'management' / '__init__.py'
        commands_init = self.services_app_path / 'management' / 'commands' / '__init__.py'
        
        self.assertTrue(management_init.exists(),
                       "management directory should have __init__.py")
        self.assertTrue(commands_init.exists(),
                       "commands directory should have __init__.py")


if __name__ == '__main__':
    unittest.main()
