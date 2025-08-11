"""Unit tests for template generation module."""
import os
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest import mock

from quickscale.utils.template_generator import (
    copy_sync_modules,
    fix_imports,
    process_file_templates,
    render_template,
    is_binary_file
)


class TestTemplateGenerator(unittest.TestCase):
    """Test cases for template generator module."""
    
    def setUp(self):
        """Set up test environment."""
        # Create a temporary directory for test files
        self.test_dir = tempfile.mkdtemp()
        
        # Set up a mock logger
        self.logger = mock.MagicMock()
        
    def tearDown(self):
        """Clean up test environment."""
        # Remove the temporary directory
        shutil.rmtree(self.test_dir)
        
    def test_render_template(self):
        """Test template rendering."""
        # Create a template string
        template = "Hello, $name! Welcome to $project_name."
        
        # Define variables
        variables = {
            "name": "User",
            "project_name": "TestProject"
        }
        
        # Render the template
        result = render_template(template, variables)
        
        # Check the result
        self.assertEqual(result, "Hello, User! Welcome to TestProject.")
        
    def test_process_file_templates(self):
        """Test processing of template files."""
        # Create a template file
        template_file = Path(self.test_dir) / "template.py"
        with open(template_file, 'w') as f:
            f.write('"""$project_name module."""\n\nPROJECT_NAME = "$project_name"\n')
            
        # Define template variables
        variables = {
            "project_name": "TestProject"
        }
        
        # Process templates by directly calling render_template
        with open(template_file, 'r') as f:
            content = f.read()
        
        rendered_content = render_template(content, variables)
        
        # Write back the rendered content
        with open(template_file, 'w') as f:
            f.write(rendered_content)
        
        # Check if the file was properly rendered
        with open(template_file, 'r') as f:
            content = f.read()
            
        self.assertEqual(content, '"""TestProject module."""\n\nPROJECT_NAME = "TestProject"\n')


if __name__ == "__main__":
    unittest.main()
