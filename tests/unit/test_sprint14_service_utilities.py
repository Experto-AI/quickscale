"""Tests for Sprint 14 service utility functions."""
import unittest
from unittest.mock import patch, mock_open, MagicMock
import os
import tempfile

from quickscale.utils.service_dev_utils import (
    ServiceDevelopmentHelper,
    validate_service_file,
    show_service_examples
)


class TestSprint14ServiceUtilities(unittest.TestCase):
    """Test Sprint 14 service utility functions."""
    
    def setUp(self):
        """Set up test fixtures."""
        self.helper = ServiceDevelopmentHelper()
    
    def test_validate_service_structure_valid_file(self):
        """Test service structure validation with valid service file."""
        valid_service_content = '''
from services.base import BaseService
from services.decorators import register_service
from typing import Dict, Any
from django.contrib.auth.models import User

@register_service("test_service")
class TestService(BaseService):
    """Test service for validation."""
    
    def execute_service(self, user: User, **kwargs) -> Dict[str, Any]:
        """Execute the test service."""
        if not kwargs.get('input_data'):
            raise ValueError("input_data is required")
        
        return {"result": "success"}
'''
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=valid_service_content)):
            
            result = self.helper.validate_service_structure('/fake/path/test_service.py')
            
            self.assertTrue(result['valid'])
            self.assertEqual(len(result['errors']), 0)
    
    def test_validate_service_structure_missing_imports(self):
        """Test service structure validation with missing imports."""
        invalid_service_content = '''
# Missing required imports
class TestService:
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=invalid_service_content)):
            
            result = self.helper.validate_service_structure('/fake/path/test_service.py')
            
            self.assertFalse(result['valid'])
            self.assertGreater(len(result['errors']), 0)
            self.assertTrue(any('import' in error.lower() for error in result['errors']))
    
    def test_validate_service_structure_missing_decorator(self):
        """Test service structure validation with missing @register_service decorator."""
        invalid_service_content = '''
from services.base import BaseService
from services.decorators import register_service

class TestService(BaseService):
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=invalid_service_content)):
            
            result = self.helper.validate_service_structure('/fake/path/test_service.py')
            
            self.assertFalse(result['valid'])
            self.assertTrue(any('register_service' in error for error in result['errors']))
    
    def test_validate_service_structure_file_not_found(self):
        """Test service structure validation with non-existent file."""
        with patch('os.path.exists', return_value=False):
            result = self.helper.validate_service_structure('/nonexistent/path.py')
            
            self.assertFalse(result['valid'])
            self.assertTrue(any('not found' in error for error in result['errors']))
    
    def test_analyze_service_dependencies_external_packages(self):
        """Test service dependency analysis with external packages."""
        service_content = '''
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
import openai
import requests
from PIL import Image
import cv2

from services.base import BaseService
'''
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=service_content)):
            
            result = self.helper.analyze_service_dependencies('/fake/path/service.py')
            
            self.assertGreater(len(result['external_imports']), 0)
            self.assertGreater(len(result['recommendations']), 0)
            
            # Check for specific recommendations
            recommendations_text = ' '.join(result['recommendations']).lower()
            self.assertIn('openai', recommendations_text)
            self.assertIn('requests', recommendations_text)
            self.assertIn('memory', recommendations_text)
    
    def test_analyze_service_dependencies_no_external(self):
        """Test service dependency analysis with no external dependencies."""
        service_content = '''
from services.base import BaseService
from services.decorators import register_service
from django.contrib.auth.models import User
'''
        
        with patch('os.path.exists', return_value=True), \
             patch('builtins.open', mock_open(read_data=service_content)):
            
            result = self.helper.analyze_service_dependencies('/fake/path/service.py')
            
            self.assertEqual(len(result['external_imports']), 0)
    
    def test_generate_service_config_template(self):
        """Test generation of service configuration template."""
        template = self.helper.generate_service_config_template('test_service', 2.5)
        
        self.assertIn('test_service', template)
        self.assertIn('2.5', template)
        self.assertIn('Service.objects.get_or_create', template)
        self.assertIn('credit_cost', template)
        self.assertIn('is_active', template)
    
    def test_check_project_structure_valid_project(self):
        """Test project structure check with valid QuickScale project."""
        with patch('pathlib.Path.cwd') as mock_cwd, \
             patch('pathlib.Path.exists') as mock_exists:
            
            mock_cwd.return_value = MagicMock()
            mock_exists.return_value = True
            
            result = self.helper.check_project_structure()
            
            self.assertTrue(result['is_quickscale_project'])
            self.assertEqual(len(result['missing_components']), 0)
    
    def test_check_project_structure_invalid_project(self):
        """Test project structure check with invalid project."""
        with patch('pathlib.Path.cwd') as mock_cwd:
            # Create a mock path that has files not existing
            mock_project_path = MagicMock()
            mock_cwd.return_value = mock_project_path
            
            # Mock individual file/directory checks to return False
            def mock_exists_side_effect(path_obj):
                return False
            
            with patch.object(type(mock_project_path), '__truediv__') as mock_div:
                mock_component = MagicMock()
                mock_component.exists.return_value = False
                mock_div.return_value = mock_component
                
                result = self.helper.check_project_structure()
                
                self.assertFalse(result['is_quickscale_project'])
                self.assertGreater(len(result['missing_components']), 0)
                self.assertGreater(len(result['recommendations']), 0)
    
    def test_get_service_examples(self):
        """Test retrieval of service examples."""
        helper = ServiceDevelopmentHelper()
        examples = helper.get_service_examples()
        
        # Should return list of available examples
        self.assertIsInstance(examples, list)
        self.assertGreater(len(examples), 0)
        
        # Check first example has required fields
        first_example = examples[0]
        self.assertIn('name', first_example)
        self.assertIn('type', first_example)
        self.assertIn('description', first_example)
        self.assertIn('use_case', first_example)
        
        # Should have valid types 
        for example in examples:
            self.assertIn(example['type'], ['text_processing', 'image_processing', 'basic'])
    
    @patch('quickscale.utils.service_dev_utils.MessageManager')
    def test_validate_service_file(self, mock_message_manager):
        """Test validate_service_file function."""
        valid_service_content = '''
from services.base import BaseService
from services.decorators import register_service

@register_service("test")
class TestService(BaseService):
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        
        # Create temporary file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
            f.write(valid_service_content)
            f.flush()
            
            try:
                validate_service_file(f.name)
                
                # Check that validation was performed
                mock_message_manager.info.assert_called()
                
            finally:
                os.unlink(f.name)
    
    @patch('quickscale.utils.service_dev_utils.MessageManager')
    def test_show_service_examples(self, mock_message_manager):
        """Test show_service_examples function."""
        show_service_examples()
        
        # Verify that examples were displayed
        mock_message_manager.info.assert_called()
        
        # Check that at least one call included service example information
        call_args = [call[0][0] for call in mock_message_manager.info.call_args_list]
        self.assertTrue(any('Service Examples' in arg for arg in call_args))
    
    def test_service_development_helper_initialization(self):
        """Test ServiceDevelopmentHelper class initialization."""
        helper = ServiceDevelopmentHelper()
        
        # Test that helper has all expected methods
        expected_methods = [
            'validate_service_structure',
            'analyze_service_dependencies',
            'generate_service_config_template',
            'check_project_structure',
            'get_service_examples'
        ]
        
        for method_name in expected_methods:
            self.assertTrue(hasattr(helper, method_name))
            self.assertTrue(callable(getattr(helper, method_name)))


if __name__ == '__main__':
    unittest.main() 