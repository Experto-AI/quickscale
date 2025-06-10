"""
Unit tests for Sprint 14 Service Development Utilities.

Tests the service development helper utilities for AI engineers.
"""

import os
import tempfile
import shutil
from pathlib import Path
import unittest
from unittest import mock
from unittest.mock import patch, MagicMock

from quickscale.utils.service_dev_utils import (
    ServiceDevelopmentHelper,
    validate_service_file,
    show_service_examples
)


class TestServiceDevelopmentHelper(unittest.TestCase):
    """Test cases for ServiceDevelopmentHelper class."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.helper = ServiceDevelopmentHelper()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_service_file(self, content: str) -> str:
        """Create a test service file with given content."""
        service_file = Path(self.test_dir) / "test_service.py"
        service_file.write_text(content)
        return str(service_file)
    
    def test_validate_service_structure_valid_service(self):
        """Test validation of a properly structured service."""
        valid_service_content = '''
from typing import Dict, Any
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service

User = get_user_model()

@register_service("test_service")
class TestService(BaseService):
    """Test service implementation."""
    
    def execute_service(self, user: User, **kwargs) -> Dict[str, Any]:
        """Execute test service logic."""
        input_data = kwargs.get('input_data')
        if not input_data:
            raise ValueError("input_data is required")
        
        return {"result": "success", "input": input_data}
'''
        
        service_file = self._create_test_service_file(valid_service_content)
        result = self.helper.validate_service_structure(service_file)
        
        self.assertTrue(result["valid"])
        self.assertEqual(len(result["errors"]), 0)
    
    def test_validate_service_structure_missing_imports(self):
        """Test validation with missing required imports."""
        invalid_service_content = '''
class TestService:
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        
        service_file = self._create_test_service_file(invalid_service_content)
        result = self.helper.validate_service_structure(service_file)
        
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 0)
        
        # Check for specific error messages
        error_messages = " ".join(result["errors"])
        self.assertIn("Missing required import", error_messages)
    
    def test_validate_service_structure_missing_inheritance(self):
        """Test validation with missing BaseService inheritance."""
        invalid_service_content = '''
from services.base import BaseService
from services.decorators import register_service

@register_service("test_service")
class TestService:
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        
        service_file = self._create_test_service_file(invalid_service_content)
        result = self.helper.validate_service_structure(service_file)
        
        self.assertFalse(result["valid"])
        self.assertIn("inherit from BaseService", " ".join(result["errors"]))
    
    def test_validate_service_structure_missing_decorator(self):
        """Test validation with missing @register_service decorator."""
        invalid_service_content = '''
from services.base import BaseService
from services.decorators import register_service

class TestService(BaseService):
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        
        service_file = self._create_test_service_file(invalid_service_content)
        result = self.helper.validate_service_structure(service_file)
        
        self.assertFalse(result["valid"])
        self.assertIn("@register_service decorator", " ".join(result["errors"]))
    
    def test_validate_service_structure_missing_method(self):
        """Test validation with missing execute_service method."""
        invalid_service_content = '''
from services.base import BaseService
from services.decorators import register_service

@register_service("test_service")
class TestService(BaseService):
    def some_other_method(self):
        pass
'''
        
        service_file = self._create_test_service_file(invalid_service_content)
        result = self.helper.validate_service_structure(service_file)
        
        self.assertFalse(result["valid"])
        self.assertIn("execute_service method", " ".join(result["errors"]))
    
    def test_validate_service_structure_nonexistent_file(self):
        """Test validation with nonexistent file."""
        nonexistent_file = "/path/to/nonexistent/file.py"
        result = self.helper.validate_service_structure(nonexistent_file)
        
        self.assertFalse(result["valid"])
        self.assertIn("not found", " ".join(result["errors"]))
    
    def test_analyze_service_dependencies_external_imports(self):
        """Test dependency analysis with external imports."""
        service_content = '''
import numpy as np
import requests
from openai import OpenAI
from services.base import BaseService

class TestService(BaseService):
    pass
'''
        
        service_file = self._create_test_service_file(service_content)
        result = self.helper.analyze_service_dependencies(service_file)
        
        self.assertGreater(len(result["external_imports"]), 0)
        
        # Check for specific recommendations
        recommendations = " ".join(result["recommendations"])
        self.assertIn("OpenAI", recommendations)
    
    def test_analyze_service_dependencies_no_external_imports(self):
        """Test dependency analysis with only internal imports."""
        service_content = '''
from services.base import BaseService
from services.decorators import register_service
from django.contrib.auth import get_user_model

class TestService(BaseService):
    pass
'''
        
        service_file = self._create_test_service_file(service_content)
        result = self.helper.analyze_service_dependencies(service_file)
        
        self.assertEqual(len(result["external_imports"]), 0)
    
    def test_generate_service_config_template(self):
        """Test service configuration template generation."""
        template = self.helper.generate_service_config_template("test_service", 2.5)
        
        self.assertIsInstance(template, str)
        self.assertIn("test_service", template)
        self.assertIn("2.5", template)
        self.assertIn("Service.objects.get_or_create", template)
    
    def test_check_project_structure_not_quickscale_project(self):
        """Test project structure check in non-QuickScale directory."""
        # Change to test directory (which isn't a QuickScale project)
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)
            result = self.helper.check_project_structure()
            
            self.assertFalse(result["is_quickscale_project"])
            self.assertGreater(len(result["missing_components"]), 0)
            self.assertGreater(len(result["recommendations"]), 0)
        finally:
            os.chdir(original_cwd)
    
    def test_check_project_structure_partial_quickscale_project(self):
        """Test project structure check with some QuickScale files present."""
        # Create some but not all required files
        (Path(self.test_dir) / "manage.py").touch()
        (Path(self.test_dir) / "services").mkdir()
        
        original_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)
            result = self.helper.check_project_structure()
            
            self.assertFalse(result["is_quickscale_project"])
            self.assertLess(len(result["missing_components"]), 5)  # Some but not all missing
        finally:
            os.chdir(original_cwd)
    
    def test_get_service_examples(self):
        """Test getting service examples."""
        examples = self.helper.get_service_examples()
        
        self.assertIsInstance(examples, list)
        self.assertGreater(len(examples), 0)
        
        # Check structure of examples
        for example in examples:
            self.assertIn("name", example)
            self.assertIn("type", example)
            self.assertIn("description", example)
            self.assertIn("use_case", example)
    
    @patch('quickscale.utils.service_dev_utils.MessageManager')
    def test_display_development_tips(self, mock_message_manager):
        """Test displaying service development tips."""
        helper = ServiceDevelopmentHelper()
        helper.display_development_tips()
        
        # Verify that tips were displayed
        mock_message_manager.info.assert_called()
        
        # Check that tips contain useful information
        call_args = [call[0][0] for call in mock_message_manager.info.call_args_list]
        tips_text = " ".join(call_args)
        
        self.assertIn("service", tips_text.lower())
        self.assertIn("credit", tips_text.lower())


class TestServiceDevUtilityFunctions(unittest.TestCase):
    """Test cases for utility functions in service_dev_utils module."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def _create_test_service_file(self, content: str) -> str:
        """Create a test service file with given content."""
        service_file = Path(self.test_dir) / "test_service.py"
        service_file.write_text(content)
        return str(service_file)
    
    @patch('quickscale.utils.service_dev_utils.MessageManager')
    def test_validate_service_file(self, mock_message_manager):
        """Test validate_service_file function."""
        valid_service_content = '''
from services.base import BaseService
from services.decorators import register_service

@register_service("test_service")
class TestService(BaseService):
    def execute_service(self, user, **kwargs):
        return {"result": "success"}
'''
        
        service_file = self._create_test_service_file(valid_service_content)
        validate_service_file(service_file)
        
        # Verify function completed without errors
        mock_message_manager.success.assert_called()
    
    @patch('quickscale.utils.service_dev_utils.MessageManager')
    def test_show_service_examples(self, mock_message_manager):
        """Test show_service_examples function."""
        show_service_examples()
        
        # Verify that examples were displayed
        mock_message_manager.info.assert_called()
        
        # Check that examples contain service information
        call_args = [call[0][0] for call in mock_message_manager.info.call_args_list]
        examples_text = " ".join(call_args)
        
        self.assertIn("service", examples_text.lower())


class TestServiceDevelopmentIntegration(unittest.TestCase):
    """Integration tests for service development utilities."""
    
    def setUp(self):
        """Set up test environment."""
        self.test_dir = tempfile.mkdtemp()
        self.helper = ServiceDevelopmentHelper()
        
    def tearDown(self):
        """Clean up test environment."""
        shutil.rmtree(self.test_dir)
    
    def test_complete_service_validation_workflow(self):
        """Test complete service validation workflow."""
        # Create a comprehensive service file
        comprehensive_service = '''
"""
Advanced AI service for sentiment analysis.
"""

from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service
import numpy as np
import requests

User = get_user_model()

@register_service("sentiment_analyzer")
class SentimentAnalyzerService(BaseService):
    """Sentiment analysis service that processes text."""
    
    def execute_service(self, user: User, text: str = "", **kwargs) -> Dict[str, Any]:
        """Execute sentiment analysis on provided text."""
        if not text:
            raise ValueError("Text input is required for sentiment analysis")
        
        # TODO: Implement actual sentiment analysis
        # This is a placeholder implementation
        positive_words = ["good", "great", "excellent", "amazing"]
        negative_words = ["bad", "terrible", "awful", "horrible"]
        
        words = text.lower().split()
        positive_count = sum(1 for word in words if word in positive_words)
        negative_count = sum(1 for word in words if word in negative_words)
        
        if positive_count > negative_count:
            sentiment = "positive"
            score = 0.7
        elif negative_count > positive_count:
            sentiment = "negative"
            score = 0.3
        else:
            sentiment = "neutral"
            score = 0.5
        
        return {
            "sentiment": sentiment,
            "score": score,
            "positive_words": positive_count,
            "negative_words": negative_count,
            "total_words": len(words)
        }
'''
        
        service_file = Path(self.test_dir) / "sentiment_analyzer.py"
        service_file.write_text(comprehensive_service)
        
        # Test validation
        validation_result = self.helper.validate_service_structure(str(service_file))
        self.assertTrue(validation_result["valid"])
        
        # Test dependency analysis
        dependency_result = self.helper.analyze_service_dependencies(str(service_file))
        self.assertGreater(len(dependency_result["external_imports"]), 0)
        
        # Test configuration template generation
        config_template = self.helper.generate_service_config_template("sentiment_analyzer", 1.5)
        self.assertIn("sentiment_analyzer", config_template)
        self.assertIn("1.5", config_template)
    
    def test_service_validation_error_accumulation(self):
        """Test that validation properly accumulates multiple errors."""
        problematic_service = '''
# Missing imports
# Missing proper class structure
# Missing decorator

def some_function():
    return "not a service"
'''
        
        service_file = Path(self.test_dir) / "bad_service.py"
        service_file.write_text(problematic_service)
        
        result = self.helper.validate_service_structure(str(service_file))
        
        self.assertFalse(result["valid"])
        self.assertGreater(len(result["errors"]), 1)  # Multiple errors should be found


if __name__ == "__main__":
    unittest.main() 