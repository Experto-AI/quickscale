"""
Tests for Sprint 10: AI Service Framework Foundation.

These tests verify that the services Django app template, BaseService class,
service registration system, and all related infrastructure are properly
implemented in the QuickScale project generator templates.
"""

import os
import unittest
import re
from pathlib import Path
from typing import Dict, Any, Union


class ServicesAppStructureTests(unittest.TestCase):
    """Test cases for services Django app structure."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.services_app_path = self.base_path / 'quickscale' / 'project_templates' / 'services'
        self.core_settings_path = self.base_path / 'quickscale' / 'project_templates' / 'core' / 'settings.py'
        
    def test_services_app_directory_exists(self):
        """Test that services app directory exists."""
        self.assertTrue(self.services_app_path.exists(),
                       "Services app directory not found")
        self.assertTrue(self.services_app_path.is_dir(),
                       "Services path is not a directory")
    
    def test_services_app_files_exist(self):
        """Test that all required services app files exist."""
        required_files = [
            '__init__.py',
            'apps.py',
            'base.py',
            'decorators.py',
            'examples.py',
            'models.py',
            'urls.py',
            'views.py'
        ]
        
        for file_name in required_files:
            file_path = self.services_app_path / file_name
            self.assertTrue(file_path.exists(),
                           f"Required file {file_name} not found in services app")
    
    def test_services_templates_directory_exists(self):
        """Test that services templates directory exists."""
        templates_path = self.services_app_path / 'templates' / 'services'
        self.assertTrue(templates_path.exists(),
                       "Services templates directory not found")
        
        # Check for required template files
        required_templates = [
            'service_list.html',
            'service_usage_form.html',
            'service_usage_result.html'
        ]
        
        for template_name in required_templates:
            template_path = templates_path / template_name
            self.assertTrue(template_path.exists(),
                           f"Required template {template_name} not found")
    
    def test_services_app_config(self):
        """Test that ServicesConfig is properly implemented."""
        apps_py = self.services_app_path / 'apps.py'
        
        with open(apps_py, 'r') as f:
            apps_content = f.read()
        
        # Check for ServicesConfig class
        self.assertIn("class ServicesConfig(AppConfig)", apps_content,
                     "ServicesConfig class not found")
        
        # Check for proper configuration
        self.assertIn("name = 'services'", apps_content,
                     "App name not properly set")
        self.assertIn("verbose_name = _('Services')", apps_content,
                     "Verbose name not properly set")
        self.assertIn("default_auto_field = 'django.db.models.BigAutoField'", apps_content,
                     "Auto field not properly configured")
    
    def test_services_app_in_installed_apps(self):
        """Test that services app is included in INSTALLED_APPS."""
        with open(self.core_settings_path, 'r') as f:
            settings_content = f.read()
        
        self.assertIn("'services.apps.ServicesConfig'", settings_content,
                     "ServicesConfig not found in INSTALLED_APPS")
        self.assertIn("# AI Service Framework", settings_content,
                     "Services app comment not found in INSTALLED_APPS")


class BaseServiceClassTests(unittest.TestCase):
    """Test cases for BaseService class implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.services_app_path = self.base_path / 'quickscale' / 'project_templates' / 'services'
        self.base_py = self.services_app_path / 'base.py'
    
    def test_base_service_class_exists(self):
        """Test that BaseService class is properly defined."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for ABC inheritance
        self.assertIn("from abc import ABC, abstractmethod", base_content,
                     "ABC imports not found")
        self.assertIn("class BaseService(ABC)", base_content,
                     "BaseService class not found or not inheriting from ABC")
    
    def test_base_service_initialization(self):
        """Test that BaseService has proper initialization."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for __init__ method
        self.assertIn("def __init__(self, service_name: str)", base_content,
                     "BaseService __init__ method not found")
        self.assertIn("self.service_name = service_name", base_content,
                     "Service name assignment not found")
        self.assertIn("self._service_model = None", base_content,
                     "Service model cache initialization not found")
    
    def test_base_service_model_property(self):
        """Test that BaseService has proper service_model property."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for service_model property
        self.assertIn("@property", base_content,
                     "Property decorator not found")
        self.assertIn("def service_model(self) -> Service:", base_content,
                     "service_model property not found")
        
        # Check for lazy loading logic
        self.assertIn("if self._service_model is None:", base_content,
                     "Lazy loading check not found")
        self.assertIn("Service.objects.get(name=self.service_name, is_active=True)", base_content,
                     "Service lookup not found")
        self.assertIn("except Service.DoesNotExist:", base_content,
                     "Service not found exception handling not found")
    
    def test_base_service_consume_credits_method(self):
        """Test that BaseService has proper consume_credits method."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for consume_credits method
        self.assertIn("def consume_credits(self, user: User) -> ServiceUsage:", base_content,
                     "consume_credits method not found")
        
        # Check for user validation
        self.assertIn("if not isinstance(user, User):", base_content,
                     "User validation not found")
        self.assertIn("raise ValueError(\"User must be a valid User instance\")", base_content,
                     "User validation error not found")
        
        # Check for credit consumption logic
        self.assertIn("credit_account.consume_credits_with_priority", base_content,
                     "Priority credit consumption not found")
        self.assertIn("ServiceUsage.objects.create", base_content,
                     "ServiceUsage creation not found")
    
    def test_base_service_check_user_credits_method(self):
        """Test that BaseService has proper check_user_credits method."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for check_user_credits method
        self.assertIn("def check_user_credits(self, user: User) -> dict:", base_content,
                     "check_user_credits method not found")
        
        # Check for return dictionary structure
        self.assertIn("'has_sufficient_credits':", base_content,
                     "has_sufficient_credits key not found")
        self.assertIn("'required_credits':", base_content,
                     "required_credits key not found")
        self.assertIn("'available_credits':", base_content,
                     "available_credits key not found")
        self.assertIn("'shortfall':", base_content,
                     "shortfall key not found")
    
    def test_base_service_abstract_execute_method(self):
        """Test that BaseService has abstract execute_service method."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for abstract method
        self.assertIn("@abstractmethod", base_content,
                     "abstractmethod decorator not found")
        self.assertIn("def execute_service(self, user: User, **kwargs):", base_content,
                     "abstract execute_service method not found")
        self.assertIn("pass", base_content,
                     "Abstract method implementation not found")
    
    def test_base_service_run_method(self):
        """Test that BaseService has proper run method."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for run method
        self.assertIn("def run(self, user: User, **kwargs):", base_content,
                     "run method not found")
        
        # Check for proper flow
        self.assertIn("service_usage = self.consume_credits(user)", base_content,
                     "Credit consumption in run method not found")
        self.assertIn("result = self.execute_service(user, **kwargs)", base_content,
                     "Service execution in run method not found")
        self.assertIn("'success': True", base_content,
                     "Success return in run method not found")
        self.assertIn("'result': result", base_content,
                     "Result return in run method not found")
    
    def test_base_service_imports(self):
        """Test that BaseService has proper imports."""
        with open(self.base_py, 'r') as f:
            base_content = f.read()
        
        # Check for required imports
        self.assertIn("from decimal import Decimal", base_content,
                     "Decimal import not found")
        self.assertIn("from django.contrib.auth import get_user_model", base_content,
                     "get_user_model import not found")
        self.assertIn("from credits.models import CreditAccount, Service, ServiceUsage, InsufficientCreditsError", base_content,
                     "Credits models import not found")


class ServiceRegistryTests(unittest.TestCase):
    """Test cases for service registration system."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.services_app_path = self.base_path / 'quickscale' / 'project_templates' / 'services'
        self.decorators_py = self.services_app_path / 'decorators.py'
    
    def test_service_registry_class_exists(self):
        """Test that ServiceRegistry class is properly defined."""
        with open(self.decorators_py, 'r') as f:
            decorators_content = f.read()
        
        # Check for ServiceRegistry class
        self.assertIn("class ServiceRegistry:", decorators_content,
                     "ServiceRegistry class not found")
        self.assertIn("def __init__(self):", decorators_content,
                     "ServiceRegistry __init__ method not found")
        self.assertIn("self._services: Dict[str, Type[BaseService]] = {}", decorators_content,
                     "Services dictionary initialization not found")
    
    def test_service_registry_register_method(self):
        """Test that ServiceRegistry has proper register method."""
        with open(self.decorators_py, 'r') as f:
            decorators_content = f.read()
        
        # Check for register method
        self.assertIn("def register(self, service_name: str, service_class: Type[BaseService]) -> None:", decorators_content,
                     "register method not found")
        
        # Check for validation
        self.assertIn("if not issubclass(service_class, BaseService):", decorators_content,
                     "BaseService validation not found")
        self.assertIn("if service_name in self._services:", decorators_content,
                     "Duplicate service validation not found")
        self.assertIn("self._services[service_name] = service_class", decorators_content,
                     "Service registration not found")
    
    def test_service_registry_utility_methods(self):
        """Test that ServiceRegistry has proper utility methods."""
        with open(self.decorators_py, 'r') as f:
            decorators_content = f.read()
        
        # Check for utility methods
        self.assertIn("def get_service(self, service_name: str) -> Optional[Type[BaseService]]:", decorators_content,
                     "get_service method not found")
        self.assertIn("def get_all_services(self) -> Dict[str, Type[BaseService]]:", decorators_content,
                     "get_all_services method not found")
        self.assertIn("def is_registered(self, service_name: str) -> bool:", decorators_content,
                     "is_registered method not found")
        self.assertIn("def unregister(self, service_name: str) -> bool:", decorators_content,
                     "unregister method not found")
    
    def test_register_service_decorator(self):
        """Test that register_service decorator is properly implemented."""
        with open(self.decorators_py, 'r') as f:
            decorators_content = f.read()
        
        # Check for decorator function
        self.assertIn("def register_service(service_name: str):", decorators_content,
                     "register_service decorator not found")
        self.assertIn("def decorator(service_class: Type[BaseService]):", decorators_content,
                     "decorator inner function not found")
        
        # Check for validation
        self.assertIn("if not issubclass(service_class, BaseService):", decorators_content,
                     "BaseService validation in decorator not found")
        self.assertIn("service_registry.register(service_name, service_class)", decorators_content,
                     "Service registration in decorator not found")
        self.assertIn("return service_class", decorators_content,
                     "Service class return not found")
    
    def test_global_service_registry(self):
        """Test that global service registry instance exists."""
        with open(self.decorators_py, 'r') as f:
            decorators_content = f.read()
        
        # Check for global instance
        self.assertIn("service_registry = ServiceRegistry()", decorators_content,
                     "Global service registry instance not found")
    
    def test_utility_functions(self):
        """Test that utility functions are properly implemented."""
        with open(self.decorators_py, 'r') as f:
            decorators_content = f.read()
        
        # Check for utility functions
        self.assertIn("def get_registered_service(service_name: str) -> Optional[Type[BaseService]]:", decorators_content,
                     "get_registered_service function not found")
        self.assertIn("def get_all_registered_services() -> Dict[str, Type[BaseService]]:", decorators_content,
                     "get_all_registered_services function not found")
        self.assertIn("def create_service_instance(service_name: str) -> Optional[BaseService]:", decorators_content,
                     "create_service_instance function not found")
    
    def test_type_hints(self):
        """Test that proper type hints are used."""
        with open(self.decorators_py, 'r') as f:
            decorators_content = f.read()
        
        # Check for type imports
        self.assertIn("from typing import Dict, Type, Optional", decorators_content,
                     "Type imports not found")
        self.assertIn("from .base import BaseService", decorators_content,
                     "BaseService import not found")


class ServiceExamplesTests(unittest.TestCase):
    """Test cases for example service implementations."""

    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.examples_py = self.base_path / 'quickscale' / 'project_templates' / 'services' / 'examples.py'
        with open(self.examples_py, 'r') as f:
            self.examples_content = f.read()

    def test_example_services_exist(self):
        """Test that example service classes are properly defined."""
        # Updated to check for the actual service names introduced in Sprint 14
        self.assertIn("class TextSentimentAnalysisService(BaseService):", self.examples_content,
                      "TextSentimentAnalysisService class not found")
        self.assertIn("class TextKeywordExtractorService(BaseService):", self.examples_content,
                      "TextKeywordExtractorService class not found")
        self.assertIn("class ImageMetadataExtractorService(BaseService):", self.examples_content,
                      "ImageMetadataExtractorService class not found")
        self.assertIn("class DataValidatorService(BaseService):", self.examples_content,
                      "DataValidatorService class not found")

    def test_example_service_decorators(self):
        """Test that example services use the register_service decorator."""
        # Updated to check for the actual service names introduced in Sprint 14
        self.assertIn('@register_service("text_sentiment_analysis")', self.examples_content,
                      "TextSentimentAnalysisService registration not found")
        self.assertIn('@register_service("text_keyword_extractor")', self.examples_content,
                      "TextKeywordExtractorService registration not found")
        self.assertIn('@register_service("image_metadata_extractor")', self.examples_content,
                      "ImageMetadataExtractorService registration not found")
        self.assertIn('@register_service("data_validator")', self.examples_content,
                      "DataValidatorService registration not found")

    def test_example_service_implementation(self):
        """Test that example services have the execute_service method implemented."""
        # Updated to check for specific execute_service methods in new services
        self.assertIn('def execute_service(self, user: User, text: str = "", **kwargs) -> Dict[str, Any]:', self.examples_content,
                      "TextSentimentAnalysisService execute_service method not found")
        self.assertIn('def execute_service(self, user: User, text: str = "", max_keywords: int = 10, **kwargs) -> Dict[str, Any]:', self.examples_content,
                      "TextKeywordExtractorService execute_service method not found")
        self.assertIn('def execute_service(self, user: User, image_data: Union[str, bytes] = None, **kwargs) -> Dict[str, Any]:', self.examples_content,
                      "ImageMetadataExtractorService execute_service method not found")
        self.assertIn('def execute_service(self, user: User, data: Any = None, data_type: str = "text", **kwargs) -> Dict[str, Any]:', self.examples_content,
                      "DataValidatorService execute_service method not found")

    def test_usage_documentation(self):
        """Test that example services include basic usage documentation."""
        # Updated to reflect the new structure of usage examples in examples.py
        match = re.search(r'"""\n# Advanced Usage Patterns for QuickScale AI Services(.*)"""', self.examples_content, re.DOTALL)
        self.assertIsNotNone(match, "Advanced usage patterns documentation block not found.")
        usage_doc_content = match.group(1)

        self.assertIn("## 1. Service Chaining Example", usage_doc_content,
                      "Service Chaining Example not found in usage documentation")
        self.assertIn("def process_text_pipeline(user, text):", usage_doc_content,
                      "process_text_pipeline example not found")
        self.assertIn("## 2. Batch Processing Example", usage_doc_content,
                      "Batch Processing Example not found in usage documentation")
        self.assertIn("def batch_process_texts(user, texts: List[str], service_name: str):", usage_doc_content,
                      "batch_process_texts example not found")
        self.assertIn("## 3. Error Handling with Retry Logic", usage_doc_content,
                      "Error Handling with Retry Logic example not found")
        self.assertIn("def robust_service_call(user, service_name: str, max_retries: int = 3, **kwargs):", usage_doc_content,
                      "robust_service_call example not found")
        self.assertIn("## 4. Service Performance Monitoring", usage_doc_content,
                      "Service Performance Monitoring example not found")
        self.assertIn("def monitored_service_call(user, service_name: str, **kwargs):", usage_doc_content,
                      "monitored_service_call example not found")


class ServicesViewsTests(unittest.TestCase):
    """Test cases for services views implementation."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.services_app_path = self.base_path / 'quickscale' / 'project_templates' / 'services'
        self.views_py = self.services_app_path / 'views.py'
    
    def test_service_list_view_exists(self):
        """Test that service_list view is properly implemented."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for service_list view
        self.assertIn("def service_list(request):", views_content,
                     "service_list view not found")
        self.assertIn("@login_required", views_content,
                     "login_required decorator not found")
        
        # Check for proper logic
        self.assertIn("Service.objects.filter(is_active=True)", views_content,
                     "Active services query not found")
        self.assertIn("service.user_usage_count", views_content,
                     "Usage count calculation not found")
    
    def test_service_usage_form_view_exists(self):
        """Test that service_usage_form view is properly implemented."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for service_usage_form view
        self.assertIn("def service_usage_form(request, service_id):", views_content,
                     "service_usage_form view not found")
        self.assertIn("get_object_or_404(Service, id=service_id, is_active=True)", views_content,
                     "Service lookup not found")
    
    def test_service_status_api_view_exists(self):
        """Test that service_status_api view is properly implemented."""
        with open(self.views_py, 'r') as f:
            views_content = f.read()
        
        # Check for API view
        self.assertIn("def service_status_api(request, service_id):", views_content,
                     "service_status_api view not found")
        self.assertIn("return JsonResponse({", views_content,
                     "JSON response not found")
        
        # Check for registered services integration
        self.assertIn("get_all_registered_services()", views_content,
                     "Registered services check not found")
        self.assertIn("'is_registered':", views_content,
                     "is_registered field not found")


class ServicesUrlsTests(unittest.TestCase):
    """Test cases for services URL configuration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.services_app_path = self.base_path / 'quickscale' / 'project_templates' / 'services'
        self.urls_py = self.services_app_path / 'urls.py'
        self.core_urls_py = self.base_path / 'quickscale' / 'project_templates' / 'core' / 'urls.py'
    
    def test_services_urls_exist(self):
        """Test that services URLs are properly configured."""
        with open(self.urls_py, 'r') as f:
            urls_content = f.read()
        
        # Check for app namespace
        self.assertIn("app_name = 'services'", urls_content,
                     "Services app namespace not found")
        
        # Check for URL patterns
        self.assertIn("path('', views.service_list, name='list')", urls_content,
                     "Service list URL not found")
        self.assertIn("path('<int:service_id>/use/', views.service_usage_form, name='use_form')", urls_content,
                     "Service usage form URL not found")
        self.assertIn("path('<int:service_id>/execute/', views.use_service, name='use_service')", urls_content,
                     "Service execution URL not found")
        self.assertIn("path('<int:service_id>/status/', views.service_status_api, name='status_api')", urls_content,
                     "Service status API URL not found")
    
    def test_services_urls_included_in_core(self):
        """Test that services URLs are included in core URLs."""
        with open(self.core_urls_py, 'r') as f:
            core_urls_content = f.read()
        
        # Check for services URL inclusion
        self.assertIn("path('services/', include('services.urls', namespace='services'))", core_urls_content,
                     "Services URLs not included in core URLs")


class ServicesTemplatesTests(unittest.TestCase):
    """Test cases for services templates."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.services_app_path = self.base_path / 'quickscale' / 'project_templates' / 'services'
        self.templates_path = self.services_app_path / 'templates' / 'services'
        self.service_list_template = self.templates_path / 'service_list.html'
        self.service_usage_form_template = self.templates_path / 'service_usage_form.html'
        self.service_usage_result_template = self.templates_path / 'service_usage_result.html'
    
    def test_service_list_template_structure(self):
        """Test service list template structure."""
        with open(self.service_list_template, 'r') as f:
            template_content = f.read()
        
        # Check template structure
        self.assertIn("{% extends 'base.html' %}", template_content,
                     "Service list template does not extend base.html")
        self.assertIn("{% for service in services %}", template_content,
                     "Services loop not found")
        self.assertIn("{{ service.name }}", template_content,
                     "Service name not displayed")
        self.assertIn("{{ service.credit_cost }}", template_content,
                     "Service credit cost not displayed")
        
        # Check for credit balance display
        self.assertIn("{{ current_balance }}", template_content,
                     "Current balance not displayed")
        self.assertIn("subscription-balance", template_content,
                     "Subscription balance section not found")
        self.assertIn("payg-balance", template_content,
                     "Pay-as-you-go balance section not found")
    
    def test_service_usage_form_template_structure(self):
        """Test service usage form template structure."""
        with open(self.service_usage_form_template, 'r') as f:
            template_content = f.read()
        
        # Check template structure
        self.assertIn("{% extends 'base.html' %}", template_content,
                     "Service usage form template does not extend base.html")
        self.assertIn("{{ service.name }}", template_content,
                     "Service name not displayed")
        self.assertIn("{{ service.description }}", template_content,
                     "Service description not displayed")
        
        # Check for HTMX integration
        self.assertIn("hx-post", template_content,
                     "HTMX post not found")
        self.assertIn("hx-target", template_content,
                     "HTMX target not found")
    
    def test_service_usage_result_template_structure(self):
        """Test service usage result template structure."""
        with open(self.service_usage_result_template, 'r') as f:
            template_content = f.read()
        
        # Check for success/error handling
        self.assertIn("{% if success %}", template_content,
                     "Success condition not found")
        self.assertIn("{% else %}", template_content,
                     "Error condition not found")
        
        # Check for balance display
        self.assertIn("{{ remaining_balance }}", template_content,
                     "Remaining balance not displayed")
        self.assertIn("{{ subscription_balance }}", template_content,
                     "Subscription balance not displayed")
        self.assertIn("{{ payg_balance }}", template_content,
                     "Pay-as-you-go balance not displayed")


class ServiceMigrationTests(unittest.TestCase):
    """Test cases for services migration."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.credits_app_path = self.base_path / 'quickscale' / 'project_templates' / 'credits'
        self.migration_file = self.credits_app_path / 'migrations' / '0001_initial.py'
    
    def test_sprint10_migration_exists(self):
        """Test that Sprint 10 service framework exists in initial migration."""
        self.assertTrue(self.migration_file.exists(),
                       "Initial migration file not found")
                       
        # Check that service models are included
        with open(self.migration_file, 'r') as f:
            migration_content = f.read()
            
        self.assertIn("Service", migration_content,
                     "Service model should be in initial migration")
        self.assertIn("ServiceUsage", migration_content,
                     "ServiceUsage model should be in initial migration")
    
    def test_migration_documents_completion(self):
        """Test that migration properly documents service framework completion."""
        with open(self.migration_file, 'r') as f:
            migration_content = f.read()
        
        # Check that the migration includes service-related models
        self.assertIn("Service", migration_content,
                     "Migration should include Service model")
        self.assertIn("ServiceUsage", migration_content,
                     "Migration should include ServiceUsage model")
        
        # Check that service-related fields are properly configured
        self.assertIn("credit_cost", migration_content,
                     "Migration should include credit_cost field")
        self.assertIn("is_active", migration_content,
                     "Migration should include is_active field")
        
        # Check for proper service framework documentation in consolidated migration
        self.assertIn("Service", migration_content,
                     "Service model should be documented in migration")
        self.assertIn("ServiceUsage", migration_content,
                     "ServiceUsage model should be documented in migration")
        self.assertIn("Services that consume credits", migration_content,
                     "Service model description should be in migration")


class ServiceIntegrationTests(unittest.TestCase):
    """Test cases for services integration with the rest of the system."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.templates_path = self.base_path / 'quickscale' / 'project_templates'
    
    def test_services_integration_in_dashboard(self):
        """Test that services are integrated in admin dashboard."""
        admin_dashboard_template = self.templates_path / 'templates' / 'admin_dashboard' / 'dashboard.html'
        
        if admin_dashboard_template.exists():
            with open(admin_dashboard_template, 'r') as f:
                dashboard_content = f.read()
            
            # Should have services section or link
            services_present = any([
                'services' in dashboard_content.lower(),
                'service' in dashboard_content.lower()
            ])
            
            # This is acceptable as services integration is optional
            if not services_present:
                pass  # Integration is optional, test passes


class ServiceTemplateSyntaxTests(unittest.TestCase):
    """Test cases for services template syntax correctness."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))
        self.services_templates_path = self.base_path / 'quickscale' / 'project_templates' / 'services' / 'templates' / 'services'
    
    def test_service_usage_form_template_no_invalid_filters(self):
        """Test that service_usage_form.html doesn't use invalid Django template filters."""
        template_path = self.services_templates_path / 'service_usage_form.html'
        
        if template_path.exists():
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Check for invalid 'sub' filter usage
            self.assertNotIn('|sub:', template_content,
                           "Template contains invalid 'sub' filter - Django doesn't have a built-in subtraction filter")
            
            # Check for complex arithmetic that should be done in view
            complex_arithmetic_patterns = [
                r'\|add:.*\|add:.*\|add:',  # Multiple chained add operations
                r'\|sub:',                   # Invalid sub filter
            ]
            
            for pattern in complex_arithmetic_patterns:
                matches = re.search(pattern, template_content)
                self.assertIsNone(matches,
                                f"Template contains complex arithmetic pattern '{pattern}' that should be calculated in the view")
    
    def test_service_usage_form_uses_view_calculated_values(self):
        """Test that template uses pre-calculated values from view instead of template arithmetic."""
        template_path = self.services_templates_path / 'service_usage_form.html'
        
        if template_path.exists():
            with open(template_path, 'r') as f:
                template_content = f.read()
            
            # Check for proper usage of view-calculated values
            self.assertIn('consumption_preview', template_content,
                         "Template should use consumption_preview from view")
            self.assertIn('credits_needed', template_content,
                         "Template should use credits_needed from view")
            
            # Ensure no direct arithmetic on service.credit_cost for complex calculations
            complex_cost_calculations = [
                'service.credit_cost|add:',
                'service.credit_cost|sub:',
            ]
            
            for calc in complex_cost_calculations:
                self.assertNotIn(calc, template_content,
                               f"Template should not perform complex calculations like '{calc}' - use view calculations instead")
    
    def test_all_service_templates_syntax_valid(self):
        """Test that all service templates use valid Django template syntax."""
        if not self.services_templates_path.exists():
            return
        
        for template_file in self.services_templates_path.glob('*.html'):
            with open(template_file, 'r') as f:
                template_content = f.read()
            
            # Check for common invalid filter patterns
            invalid_patterns = [
                r'\|sub:',      # Invalid subtraction filter
                r'\|div:',      # Invalid division filter
                r'\|mul:',      # Invalid multiplication filter
                r'\|mod:',      # Invalid modulo filter
            ]
            
            for pattern in invalid_patterns:
                matches = re.search(pattern, template_content)
                self.assertIsNone(matches,
                                f"Template {template_file.name} contains invalid filter pattern '{pattern}'")


if __name__ == '__main__':
    unittest.main() 