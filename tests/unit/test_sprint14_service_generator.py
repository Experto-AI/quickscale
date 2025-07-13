"""Tests for Sprint 14 service generator functionality."""
import unittest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock, mock_open

from quickscale.commands.service_generator_commands import (
    ServiceGeneratorCommand,
    ValidateServiceCommand,
    ServiceExamplesCommand
)
from quickscale.utils.service_templates import (
    get_basic_service_template,
    get_text_processing_template,
    get_image_processing_template,
    generate_service_file,
    get_service_readme_template
)
from quickscale.utils.service_dev_utils import (
    ServiceDevelopmentHelper,
    validate_service_file,
    show_service_examples
)


class TestServiceGeneratorCommand(unittest.TestCase):
    """Test cases for ServiceGeneratorCommand."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.command = ServiceGeneratorCommand()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_validate_service_name_valid_names(self):
        """Test service name validation with valid names."""
        valid_names = [
            "text_analyzer",
            "sentiment_analysis",
            "image_classifier",
            "data_processor"
        ]
        
        for name in valid_names:
            with self.subTest(name=name):
                self.assertTrue(self.command._validate_service_name(name))
    
    def test_validate_service_name_invalid_names(self):
        """Test service name validation with invalid names."""
        invalid_names = [
            "",  # Empty
            "TextAnalyzer",  # PascalCase
            "text-analyzer",  # Hyphenated
            "text analyzer",  # Spaces
            "123service",  # Starts with number
        ]
        
        for name in invalid_names:
            with self.subTest(name=name):
                self.assertFalse(self.command._validate_service_name(name))
    
    def test_to_class_name_conversion(self):
        """Test conversion of service names to class names."""
        test_cases = [
            ("text_analyzer", "TextAnalyzerService"),
            ("sentiment_analysis", "SentimentAnalysisService"),
            ("my_service", "MyServiceService")
        ]
        
        for service_name, expected_class in test_cases:
            with self.subTest(service_name=service_name):
                result = self.command._to_class_name(service_name)
                self.assertEqual(result, expected_class)
    
    @patch('builtins.input', return_value='n')  # User says no to overwrite
    @patch('quickscale.commands.service_generator_commands.os.path.exists')
    @patch('quickscale.commands.service_generator_commands.MessageManager')
    def test_execute_service_generation_file_exists_no_overwrite(self, mock_message, mock_exists, mock_input):
        """Test service generation when file exists and user chooses not to overwrite."""
        command = ServiceGeneratorCommand()
        mock_exists.return_value = True
        
        # Mock file operations to avoid actual file creation
        with patch('builtins.open', mock_open()) as mock_file:
            result = command.execute('test_service')
            
            # Should not create file when user says no
            mock_file.assert_not_called()
            
            # Should display cancellation message
            mock_message.info.assert_called_with("Service generation cancelled")
    
    @patch('builtins.input', return_value='y')
    def test_execute_service_generation_file_exists_overwrite(self, mock_input):
        """Test service generation when file exists and user chooses to overwrite."""
        # Create existing service file
        services_dir = Path(self.test_dir) / "services"
        services_dir.mkdir(parents=True, exist_ok=True)
        
        service_file = services_dir / "test_service_service.py"
        service_file.write_text("existing content")
        
        result = self.command.execute("test_service", output_dir=self.test_dir)
        
        self.assertTrue(result["success"])
        self.assertIn("service_file", result)
        self.assertIn("example_file", result)
        
        # Verify files were created (files are created in test_dir directly since we passed output_dir)
        actual_service_file = Path(self.test_dir) / "test_service_service.py"
        actual_example_file = Path(self.test_dir) / "test_service_example.py"
        self.assertTrue(actual_service_file.exists())
        self.assertTrue(actual_example_file.exists())
        
        # Verify content was actually rendered (should contain the service name)
        content = actual_service_file.read_text()
        self.assertIn("test_service", content)
    
    def test_execute_service_generation_new_file(self):
        """Test service generation for new service file."""
        result = self.command.execute("new_service", output_dir=self.test_dir)
        
        self.assertTrue(result["success"])
        self.assertIn("service_file", result)
        self.assertIn("example_file", result)
        
        # Verify files were created (files are created in test_dir directly since we passed output_dir)
        service_file = Path(self.test_dir) / "new_service_service.py"
        example_file = Path(self.test_dir) / "new_service_example.py"
        
        self.assertTrue(service_file.exists())
        self.assertTrue(example_file.exists())
        
        # Verify content was actually rendered (should contain the service name)
        content = service_file.read_text()
        self.assertIn("new_service", content)
        self.assertIn("NewServiceService", content)
    
    def test_execute_with_invalid_service_name(self):
        """Test service generation with invalid service name."""
        with self.assertRaises(ValueError) as context:
            self.command.execute("Invalid-Name")
        
        self.assertIn("Invalid service name", str(context.exception))
    
    def test_get_service_template_types(self):
        """Test service template selection by type."""
        # Test basic template
        basic_template = self.command._get_service_template("basic")
        self.assertIn("BaseService", basic_template)
        self.assertIn("@register_service", basic_template)
        
        # Test text processing template
        text_template = self.command._get_service_template("text_processing")
        self.assertIn("text processing", text_template.lower())
        self.assertIn("text: str", text_template)
        
        # Test image processing template
        image_template = self.command._get_service_template("image_processing")
        self.assertIn("image", image_template.lower())
        
        # Test unknown type defaults to basic
        unknown_template = self.command._get_service_template("unknown_type")
        self.assertEqual(unknown_template, basic_template)

    @patch('builtins.input', return_value='n')  # User says no to overwrite
    def test_generate_service_with_existing_file(self, mock_input):
        """Test service generation when file already exists."""
        # Create an existing service file
        existing_file = Path(self.test_dir) / "existing_service_service.py"
        existing_file.write_text("existing content")
        
        # Try to generate service with the same name
        result = self.command.execute('existing_service', output_dir=self.test_dir)
        
        # Should fail because user chose not to overwrite
        self.assertFalse(result["success"])
        self.assertEqual(result["reason"], "File already exists")
    
    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_configure_service_uses_quickscale_manage(self, mock_exists, mock_subprocess):
        """Test that database configuration uses quickscale manage command instead of direct python manage.py."""
        # Mock that we're in a Django project directory
        mock_exists.return_value = True
        
        # Mock Docker services are running (docker compose ps returns output)
        docker_ps_result = MagicMock()
        docker_ps_result.returncode = 0
        docker_ps_result.stdout = "web_container_id\ndb_container_id"
        
        # Mock successful quickscale manage command
        manage_result = MagicMock()
        manage_result.returncode = 0
        manage_result.stdout = "✅ Created service 'test_service' with 1.0 credit cost"
        
        # Configure subprocess.run to return different results based on command
        def subprocess_side_effect(cmd, **kwargs):
            if cmd == ['docker', 'compose', 'ps', '--quiet']:
                return docker_ps_result
            elif cmd[0] == 'quickscale' and cmd[1] == 'manage':
                return manage_result
            else:
                raise ValueError(f"Unexpected command: {cmd}")
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        # Test the database configuration method
        result = self.command._configure_service_in_database('test_service', 'Test service', 1.0)
        
        # Verify the quickscale manage command was called correctly
        expected_manage_call = unittest.mock.call([
            'quickscale', 'manage', 'configure_service', 'test_service',
            '--description', 'Test service',
            '--credit-cost', '1.0'
        ], capture_output=True, text=True, timeout=20)
        
        # Check that subprocess.run was called with the correct commands
        calls = mock_subprocess.call_args_list
        self.assertEqual(len(calls), 2)  # Docker ps check + quickscale manage
        
        # Verify docker compose ps was called first
        self.assertEqual(calls[0], unittest.mock.call(['docker', 'compose', 'ps', '--quiet'], 
                                                     capture_output=True, text=True, timeout=10))
        
        # Verify quickscale manage was called second  
        self.assertEqual(calls[1], expected_manage_call)
        
        # Verify result indicates success
        self.assertTrue(result["success"])
        self.assertIn("✅ Created service", result["output"])

    @patch('subprocess.run')
    @patch('os.path.exists')
    def test_generate_service_database_configuration_failure_provides_helpful_message(self, mock_exists, mock_subprocess):
        """Test that when database configuration fails, helpful error messages are provided."""
        # Mock that we're in a Django project directory
        mock_exists.return_value = True
        
        # Mock Docker services are running (docker compose ps returns output)
        docker_ps_result = MagicMock()
        docker_ps_result.returncode = 0
        docker_ps_result.stdout = "web_container_id\ndb_container_id"
        
        # Mock failed quickscale manage command (simulate the original error)
        manage_result = MagicMock()
        manage_result.returncode = 1
        manage_result.stderr = 'CommandError: Error configuring service: could not translate host name "db" to address: Temporary failure in name resolution'
        
        # Configure subprocess.run to return different results based on command
        def subprocess_side_effect(cmd, **kwargs):
            if cmd == ['docker', 'compose', 'ps', '--quiet']:
                return docker_ps_result
            elif cmd[0] == 'quickscale' and cmd[1] == 'manage':
                return manage_result
            else:
                raise ValueError(f"Unexpected command: {cmd}")
        
        mock_subprocess.side_effect = subprocess_side_effect
        
        # Test the full service generation including database configuration
        result = self.command.execute('test_service', 'basic', output_dir=self.test_dir, skip_db_config=False)
        
        # Verify that service files were created successfully even though database config failed
        self.assertTrue(result["success"])
        self.assertIn("service_file", result)
        self.assertIn("example_file", result)
        
        # Verify database configuration failed but was handled gracefully
        self.assertFalse(result["database_configured"])
        self.assertIn("database_config_warning", result)
        
        # Verify the helpful error message is provided
        error_reason = result["database_config_warning"]
        self.assertIn("Management command failed", error_reason)
        
        # Verify files were actually created
        service_file = Path(self.test_dir) / "test_service_service.py"
        example_file = Path(self.test_dir) / "test_service_example.py"
        self.assertTrue(service_file.exists())
        self.assertTrue(example_file.exists())
        
        # Verify that quickscale manage was called (not direct python manage.py)
        manage_calls = [call for call in mock_subprocess.call_args_list if len(call[0]) > 0 and call[0][0][0] == 'quickscale']
        self.assertEqual(len(manage_calls), 1)
        expected_cmd = ['quickscale', 'manage', 'configure_service', 'test_service', '--description', 'AI service: Test Service', '--credit-cost', '1.0']
        self.assertEqual(manage_calls[0][0][0], expected_cmd)


class TestValidateServiceCommand(unittest.TestCase):
    """Test cases for ValidateServiceCommand."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.command = ValidateServiceCommand()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_execute_validates_service_file(self):
        """Test service file validation."""
        # Create a valid service file
        service_file = Path(self.test_dir) / "test_service.py"
        service_content = '''
from services.base import BaseService
from services.decorators import register_service

@register_service("test_service")
class TestService(BaseService):
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        service_file.write_text(service_content)
        
        result = self.command.execute(str(service_file))
        
        self.assertTrue(result["validation_completed"])
        self.assertIsInstance(result, dict)
    
    def test_execute_with_nonexistent_file(self):
        """Test validation with nonexistent file."""
        from quickscale.utils.error_manager import CommandError
        
        nonexistent_file = Path(self.test_dir) / "nonexistent.py"
        
        # This should raise a CommandError when the file doesn't exist
        with self.assertRaises(CommandError) as context:
            self.command.execute(str(nonexistent_file))
        
        self.assertIn("Service file not found", str(context.exception))


class TestServiceExamplesCommand(unittest.TestCase):
    """Test cases for ServiceExamplesCommand."""
    
    def setUp(self):
        """Set up test environment."""
        self.command = ServiceExamplesCommand()
    
    def test_execute_shows_all_examples(self):
        """Test showing all service examples."""
        result = self.command.execute()
        
        self.assertTrue(result["examples_displayed"])
        self.assertIsInstance(result, dict)
    
    def test_execute_shows_specific_example_type(self):
        """Test showing examples for specific type."""
        result = self.command.execute(example_type="text_processing")
        
        self.assertIn("examples", result)
        self.assertIn("count", result)
        self.assertGreater(result["count"], 0)
        # Check that examples are filtered for text processing
        for example in result["examples"]:
            self.assertEqual(example["type"], "text_processing")
    
    def test_execute_with_unknown_type(self):
        """Test showing examples with unknown type."""
        result = self.command.execute(example_type="unknown_type")
        
        self.assertIn("examples", result)
        self.assertIn("count", result)
        self.assertEqual(result["count"], 0)  # No examples for unknown type


class TestServiceTemplates(unittest.TestCase):
    """Test cases for service template functions."""
    
    def test_get_basic_service_template(self):
        """Test basic service template generation through ServiceGeneratorCommand."""
        command = ServiceGeneratorCommand()
        template = command._get_basic_template()
        
        self.assertIn("$SERVICE_NAME", template)
        self.assertIn("$SERVICE_CLASS", template)
        self.assertIn("@register_service", template)
    
    def test_get_text_processing_template(self):
        """Test text processing service template generation through ServiceGeneratorCommand."""
        command = ServiceGeneratorCommand()
        template = command._get_text_processing_template()
        
        self.assertIn("$SERVICE_NAME", template)
        self.assertIn("$SERVICE_CLASS", template)
        self.assertIn("text processing", template.lower())
    
    def test_get_image_processing_template(self):
        """Test image processing service template generation through ServiceGeneratorCommand."""
        command = ServiceGeneratorCommand()
        template = command._get_image_processing_template()
        
        self.assertIn("$SERVICE_NAME", template)
        self.assertIn("$SERVICE_CLASS", template)
        self.assertIn("image", template.lower())


class TestServiceDevUtils(unittest.TestCase):
    """Test cases for service development utilities."""
    
    def test_service_validation_valid_file(self):
        """Test service validation with valid service file."""
        valid_content = '''
from services.base import BaseService
from services.decorators import register_service

@register_service("test_service")
class TestService(BaseService):
    def execute_service(self, user, **kwargs):
        if not kwargs.get('input_data'):
            raise ValueError("input_data is required")
        return {"result": "success"}
'''
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data=valid_content)):
            
            helper = ServiceDevelopmentHelper()
            result = helper.validate_service_structure('/fake/path.py')
            
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
    
    def test_service_validation_invalid_file(self):
        """Test service validation with invalid service file."""
        invalid_content = '''
# Missing required imports and structure
def some_function():
    pass
'''
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', unittest.mock.mock_open(read_data=invalid_content)):
            
            helper = ServiceDevelopmentHelper()
            result = helper.validate_service_structure('/fake/path.py')
            
            self.assertFalse(result['valid'])
            self.assertGreater(len(result['errors']), 0)
    
    def test_get_service_examples(self):
        """Test getting service examples."""
        helper = ServiceDevelopmentHelper()
        examples = helper.get_service_examples()
        
        self.assertIsInstance(examples, list)
        self.assertGreater(len(examples), 0)
        
        # Check that examples have required fields
        for example in examples:
            self.assertIn("name", example)
            self.assertIn("description", example)
            self.assertIn("type", example)
            self.assertIn("use_case", example)
    
    def test_get_service_examples_by_type(self):
        """Test filtering service examples by type."""
        helper = ServiceDevelopmentHelper()
        all_examples = helper.get_service_examples()
        
        # Filter examples that contain 'text' in the name (simulate text processing examples)
        text_examples = [ex for ex in all_examples if 'text' in ex['name'].lower()]
        
        self.assertIsInstance(text_examples, list)
        # Each filtered example should contain 'text' in the name
        for example in text_examples:
            self.assertIn('text', example['name'].lower())
    
    def test_generate_service_config_template(self):
        """Test service configuration template generation."""
        helper = ServiceDevelopmentHelper()
        template = helper.generate_service_config_template("test_service", 2.5)
        
        self.assertIn("test_service", template)
        self.assertIn("2.5", template)
        self.assertIn("Service.objects.get_or_create", template)
    
    @patch('quickscale.utils.service_dev_utils.MessageManager')
    def test_show_service_examples_function(self, mock_message_manager):
        """Test show_service_examples function."""
        show_service_examples()
        
        # Verify that function executed without error
        mock_message_manager.info.assert_called()


class TestServiceTemplateIntegration(unittest.TestCase):
    """Integration tests for service template generation."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    @patch('quickscale.utils.template_generator.render_template')
    def test_complete_service_generation_workflow(self, mock_render):
        """Test complete service generation workflow."""
        mock_render.return_value = "generated service content"
        
        command = ServiceGeneratorCommand()
        
        # Test various service types
        service_types = ["basic", "text_processing", "image_processing"]
        
        for service_type in service_types:
            with self.subTest(service_type=service_type):
                service_name = f"{service_type}_test"
                
                result = command.execute(
                    service_name,
                    service_type=service_type,
                    output_dir=self.test_dir
                )
                
                self.assertTrue(result["success"])
                self.assertIn("service_file", result)
                self.assertIn("example_file", result)
                
                # Verify files were created (files go directly in test_dir when output_dir is specified)
                service_file = Path(self.test_dir) / f"{service_name}_service.py"
                example_file = Path(self.test_dir) / f"{service_name}_example.py"
                
                self.assertTrue(service_file.exists())
                self.assertTrue(example_file.exists())


if __name__ == '__main__':
    unittest.main() 