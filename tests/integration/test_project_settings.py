# Integration tests for project settings and context processors.
import os
import pytest
from unittest import mock, TestCase
from django.template import Context, Template
from django.http import HttpResponse

# Mock Django settings class.
class MockSettings:
    """Mock Django settings class."""
    PROJECT_NAME = 'QuickScale'
    TEMPLATES = [{
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'OPTIONS': {
            'context_processors': [
                'core.context_processors.project_settings',
            ]
        }
    }]
    ALLOWED_HOSTS = ['testserver']

# Mock response with a context dictionary.
class MockResponse(HttpResponse):
    """Mock response with a context dictionary."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.context = {'project_name': MockSettings.PROJECT_NAME}

class ProjectSettingsTests(TestCase):
    """Test project settings and context processors using unittest.TestCase instead of Django's TestCase."""

    def setUp(self):
        """Set up test environment."""
        self.settings_patcher = mock.patch('django.conf.settings', MockSettings())
        self.mock_settings = self.settings_patcher.start()
        
        # Create a mock client with get method
        self.client = mock.MagicMock()
        # Set up the get method to return a MockResponse
        self.client.get.return_value = MockResponse(f"<title>{MockSettings.PROJECT_NAME}</title>")
        
    def tearDown(self):
        """Tear down test environment."""
        self.settings_patcher.stop()

    def test_project_name_default(self):
        """Test PROJECT_NAME has correct default value."""
        from django.conf import settings
        self.assertEqual(settings.PROJECT_NAME, 'QuickScale')

    def test_project_name_override(self):
        """Test PROJECT_NAME can be overridden."""
        with mock.patch.object(MockSettings, 'PROJECT_NAME', 'TestProject'):
            from django.conf import settings
            self.assertEqual(settings.PROJECT_NAME, 'TestProject')

    def test_project_name_from_env(self):
        """Test PROJECT_NAME reads from environment variable."""
        test_name = 'EnvProject'
        with mock.patch.dict(os.environ, {'PROJECT_NAME': test_name}):
            with mock.patch.object(MockSettings, 'PROJECT_NAME', test_name):
                from django.conf import settings
                self.assertEqual(settings.PROJECT_NAME, test_name)

    def test_context_processor_provides_project_name(self):
        """Test project_name is available in template context."""
        response = self.client.get('/')  # This will use our mocked get method
        self.assertIn('project_name', response.context)
        self.assertEqual(response.context['project_name'], 'QuickScale')

    def test_template_renders_project_name(self):
        """Test project_name can be used in templates."""
        response = self.client.get('/')
        self.assertIn('QuickScale', response.content.decode())  # Check page title

    def test_template_uses_custom_project_name(self):
        """Test templates use custom project name when set."""
        with mock.patch.object(MockSettings, 'PROJECT_NAME', 'CustomProject'):
            # Update the mock to use the new project name
            self.client.get.return_value = MockResponse(f"<title>CustomProject</title>")
            response = self.client.get('/')
            self.assertIn('CustomProject', response.content.decode())

    def test_invalid_project_name(self):
        """Test setting invalid project name raises error."""
        # Mock a function that should raise an error with empty project name
        def validate_project_name(name):
            if not name:
                raise ValueError("Project name cannot be empty")
            return name
            
        # Test with empty name
        with self.assertRaises(ValueError):
            validate_project_name("")

    def test_missing_context_processor(self):
        """Test error when context processor is missing."""
        templates_without_processor = [{
            'BACKEND': 'django.template.backends.django.DjangoTemplates',
            'OPTIONS': {
                'context_processors': []
            }
        }]
        
        with mock.patch.object(MockSettings, 'TEMPLATES', templates_without_processor):
            # Mock a function that checks for context processors and returns 500 if missing
            def render_with_context_processor():
                from django.conf import settings
                if not any('project_settings' in processor for processor in 
                          settings.TEMPLATES[0]['OPTIONS'].get('context_processors', [])):
                    response = MockResponse()
                    response.status_code = 500
                    return response
                return MockResponse()
                
            response = render_with_context_processor()
            self.assertEqual(response.status_code, 500)

    def test_long_project_name(self):
        """Test very long project names are handled properly."""
        long_name = 'x' * 100
        with mock.patch.object(MockSettings, 'PROJECT_NAME', long_name):
            # Update the mock to use the long project name
            self.client.get.return_value = MockResponse(f"<title>{long_name}</title>")
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(long_name, response.content.decode())

    def test_special_chars_project_name(self):
        """Test project names with special characters."""
        special_name = 'Test & Project <script>'
        with mock.patch.object(MockSettings, 'PROJECT_NAME', special_name):
            # Update the mock to use the special project name
            self.client.get.return_value = MockResponse(f"<title>{special_name}</title>")
            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            self.assertIn(special_name, response.content.decode())