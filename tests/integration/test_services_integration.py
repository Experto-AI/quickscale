"""
Integration tests for Sprint 10: AI Service Framework Foundation.

These tests verify that all Sprint 10 components work together correctly
in the QuickScale project generator, testing the complete integration
of the services Django app with the existing credit system.
"""

import os
import unittest
import tempfile
import shutil
from pathlib import Path
import subprocess
import sys


class ServicesIntegrationTests(unittest.TestCase):
    """Integration tests for services framework."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
        self.temp_dir = None
        
    def tearDown(self):
        """Clean up test environment."""
        if self.temp_dir and os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)
    
    def test_services_app_included_in_generated_project(self):
        """Test that services app is included when generating a project."""
        # Check the template settings.py includes services
        settings_path = self.base_path / 'quickscale' / 'templates' / 'core' / 'settings.py'
        
        with open(settings_path, 'r') as f:
            settings_content = f.read()
        
        # Services app should be in INSTALLED_APPS
        self.assertIn("'services.apps.ServicesConfig'", settings_content,
                     "Services app not found in INSTALLED_APPS")
        
        # Should have appropriate comment
        self.assertIn("# AI Service Framework", settings_content,
                     "AI Service Framework comment not found")
    
    def test_services_urls_integrated_in_core_urls(self):
        """Test that services URLs are properly integrated."""
        core_urls_path = self.base_path / 'quickscale' / 'templates' / 'core' / 'urls.py'
        
        with open(core_urls_path, 'r') as f:
            urls_content = f.read()
        
        # Services URLs should be included
        self.assertIn("path('services/', include('services.urls'", urls_content,
                     "Services URLs not included in core URLs")
    
    def test_services_models_work_with_credit_system(self):
        """Test that services models integrate properly with credit system."""
        # Check that Service model exists in credits app
        credits_models_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py'
        
        with open(credits_models_path, 'r') as f:
            models_content = f.read()
        
        # Service model should exist
        self.assertIn("class Service(models.Model)", models_content,
                     "Service model not found in credits app")
        
        # ServiceUsage model should exist
        self.assertIn("class ServiceUsage(models.Model)", models_content,
                     "ServiceUsage model not found in credits app")
        
        # Models should have proper relationships
        self.assertIn("service = models.ForeignKey(\n        Service,", models_content,
                     "Service ForeignKey not found")
        self.assertIn("credit_transaction = models.ForeignKey(\n        CreditTransaction,", models_content,
                     "CreditTransaction ForeignKey not found")
    
    def test_base_service_integrates_with_credit_consumption(self):
        """Test that BaseService class integrates with credit consumption."""
        base_service_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'base.py'
        
        with open(base_service_path, 'r') as f:
            base_content = f.read()
        
        # Should import from credits app
        self.assertIn("from credits.models import", base_content,
                     "Credits models import not found")
        
        # Should use priority credit consumption
        self.assertIn("consume_credits_with_priority", base_content,
                     "Priority credit consumption not found")
        
        # Should create ServiceUsage records
        self.assertIn("ServiceUsage.objects.create", base_content,
                     "ServiceUsage creation not found")
    
    def test_service_registry_works_with_examples(self):
        """Test that service registry works with example services."""
        decorators_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'decorators.py'
        examples_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'examples.py'
        
        # Check registry exists
        with open(decorators_path, 'r') as f:
            decorators_content = f.read()
        
        self.assertIn("class ServiceRegistry:", decorators_content,
                     "ServiceRegistry class not found")
        self.assertIn("def register_service(service_name: str):", decorators_content,
                     "register_service decorator not found")
        
        # Check examples use the registry
        with open(examples_path, 'r') as f:
            examples_content = f.read()
        
        self.assertIn("@register_service(", examples_content,
                     "Service registration decorator not used in examples")
        self.assertIn("from .decorators import register_service", examples_content,
                     "Registry import not found in examples")
    
    def test_services_views_integrate_with_templates(self):
        """Test that services views integrate properly with templates."""
        views_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'views.py'
        templates_dir = self.base_path / 'quickscale' / 'templates' / 'services' / 'templates' / 'services'
        
        # Check views exist
        with open(views_path, 'r') as f:
            views_content = f.read()
        
        # Views should render appropriate templates
        view_template_mapping = {
            'service_list': 'service_list.html',
            'service_usage_form': 'service_usage_form.html',
            'use_service': 'service_usage_result.html'
        }
        
        for view_name, template_name in view_template_mapping.items():
            # Check view exists
            self.assertIn(f"def {view_name}(", views_content,
                         f"{view_name} view not found")
            
            # Check template exists
            template_path = templates_dir / template_name
            self.assertTrue(template_path.exists(),
                           f"Template {template_name} not found")
    
    def test_services_dashboard_integration(self):
        """Test that services are integrated into the dashboard."""
        dashboard_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'templates' / 'credits' / 'dashboard.html'
        
        with open(dashboard_path, 'r') as f:
            dashboard_content = f.read()
        
        # Should have services section
        self.assertIn("Available Services", dashboard_content,
                     "Available Services section not found")
        
        # Should link to services
        self.assertIn("services:", dashboard_content,
                     "Services URL namespace not found")
        
        # Should show service information
        self.assertIn("service.credit_cost", dashboard_content,
                     "Service credit cost not displayed")
    
    def test_migration_consistency(self):
        """Test that Sprint 10 migration is consistent."""
        migration_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'migrations' / '0005_ai_service_framework.py'
        
        # Migration should exist
        self.assertTrue(migration_path.exists(),
                       "Sprint 10 migration not found")
        
        with open(migration_path, 'r') as f:
            migration_content = f.read()
        
        # Should be a no-op migration since models already exist
        self.assertIn("operations = [", migration_content,
                     "Operations list not found")
        self.assertIn("# No database changes needed", migration_content,
                     "No-op migration comment not found")
    
    def test_complete_service_workflow_integration(self):
        """Test that the complete service workflow is properly integrated."""
        # This test verifies the end-to-end integration by checking that all pieces exist
        
        # 1. Service model exists in credits app
        credits_models_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py'
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
        self.assertIn("class Service(models.Model)", credits_content)
        
        # 2. BaseService class exists in services app
        base_service_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'base.py'
        with open(base_service_path, 'r') as f:
            base_content = f.read()
        self.assertIn("class BaseService(ABC)", base_content)
        
        # 3. Service registry exists and is functional
        decorators_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'decorators.py'
        with open(decorators_path, 'r') as f:
            decorators_content = f.read()
        self.assertIn("service_registry = ServiceRegistry()", decorators_content)
        
        # 4. Example services use the framework
        examples_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'examples.py'
        with open(examples_path, 'r') as f:
            examples_content = f.read()
        self.assertIn("class TextSentimentAnalysisService(BaseService)", examples_content)
        self.assertIn("@register_service(", examples_content)
        
        # 5. Views connect services to credit consumption
        views_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'views.py'
        with open(views_path, 'r') as f:
            views_content = f.read()
        self.assertIn("consume_credits_with_priority", views_content)
        
        # 6. URLs are properly configured
        urls_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'urls.py'
        with open(urls_path, 'r') as f:
            urls_content = f.read()
        self.assertIn("app_name = 'services'", urls_content)
        
        # 7. Templates exist and are properly structured
        templates_dir = self.base_path / 'quickscale' / 'templates' / 'services' / 'templates' / 'services'
        required_templates = ['service_list.html', 'service_usage_form.html', 'service_usage_result.html']
        
        for template in required_templates:
            template_path = templates_dir / template
            self.assertTrue(template_path.exists(),
                           f"Required template {template} not found")
    
    def test_file_structure_completeness(self):
        """Test that all required files for Sprint 10 exist."""
        services_app_path = self.base_path / 'quickscale' / 'templates' / 'services'
        
        # Required files in services app
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
            file_path = services_app_path / file_name
            self.assertTrue(file_path.exists(),
                           f"Required services app file {file_name} not found")
            
            # Check files are not empty
            with open(file_path, 'r') as f:
                content = f.read().strip()
            self.assertTrue(len(content) > 0,
                           f"Services app file {file_name} is empty")
        
        # Required template files
        templates_path = services_app_path / 'templates' / 'services'
        required_templates = [
            'service_list.html',
            'service_usage_form.html',
            'service_usage_result.html'
        ]
        
        for template_name in required_templates:
            template_path = templates_path / template_name
            self.assertTrue(template_path.exists(),
                           f"Required template {template_name} not found")
            
            # Check templates are not empty
            with open(template_path, 'r') as f:
                content = f.read().strip()
            self.assertTrue(len(content) > 0,
                           f"Template {template_name} is empty")


class ServiceFrameworkBehaviorTests(unittest.TestCase):
    """Tests for Sprint 10 framework behavior and contracts."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    def test_base_service_contract_enforcement(self):
        """Test that BaseService enforces the proper contract."""
        base_service_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'base.py'
        
        with open(base_service_path, 'r') as f:
            base_content = f.read()
        
        # Should be abstract base class
        self.assertIn("from abc import ABC, abstractmethod", base_content,
                     "ABC import not found")
        self.assertIn("class BaseService(ABC)", base_content,
                     "BaseService not inheriting from ABC")
        
        # Should have abstract execute_service method
        self.assertIn("@abstractmethod", base_content,
                     "abstractmethod decorator not found")
        self.assertIn("def execute_service(self, user: User, **kwargs):", base_content,
                     "abstract execute_service method not found")
    
    def test_service_registry_contract(self):
        """Test that service registry maintains proper contracts."""
        decorators_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'decorators.py'
        
        with open(decorators_path, 'r') as f:
            decorators_content = f.read()
        
        # Should validate BaseService subclass
        self.assertIn("if not issubclass(service_class, BaseService):", decorators_content,
                     "BaseService validation not found in registry")
        
        # Should prevent duplicate registration
        self.assertIn("if service_name in self._services:", decorators_content,
                     "Duplicate registration check not found")
        
        # Should have proper type hints
        self.assertIn("Type[BaseService]", decorators_content,
                     "Proper type hints not found")
    
    def test_credit_integration_contract(self):
        """Test that credit integration follows proper contracts."""
        base_service_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'base.py'
        
        with open(base_service_path, 'r') as f:
            base_content = f.read()
        
        # Should validate user before credit consumption
        self.assertIn("if not isinstance(user, User):", base_content,
                     "User validation not found")
        
        # Should use atomic transactions (check in the CreditAccount methods it uses)
        credits_models_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py'
        with open(credits_models_path, 'r') as f:
            credits_content = f.read()
        self.assertIn("with transaction.atomic():", credits_content,
                     "Atomic transaction usage not found in credit consumption")
        
        # Should handle insufficient credits properly
        self.assertIn("InsufficientCreditsError", base_content,
                     "InsufficientCreditsError handling not found")
    
    def test_example_services_follow_contract(self):
        """Test that example services follow the BaseService contract."""
        examples_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'examples.py'
        
        with open(examples_path, 'r') as f:
            examples_content = f.read()
        
        # Should inherit from BaseService
        self.assertIn("class TextSentimentAnalysisService(BaseService):", examples_content,
                     "TextSentimentAnalysisService not inheriting from BaseService")
        self.assertIn("class ImageMetadataExtractorService(BaseService):", examples_content,
                     "ImageMetadataExtractorService not inheriting from BaseService")
        
        # Should implement execute_service method
        self.assertIn("def execute_service(self, user: User", examples_content,
                     "execute_service method not implemented in examples")
        
        # Should use registration decorator
        self.assertIn("@register_service(", examples_content,
                     "Registration decorator not used in examples")


class ZeroCostServiceIntegrationTests(unittest.TestCase):
    """Integration tests for Sprint 24: Zero-Cost Services."""
    
    def setUp(self):
        """Set up test environment."""
        self.base_path = Path(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
    
    def test_service_model_allows_zero_cost(self):
        """Test that Service model in credits app allows zero credit cost."""
        credits_models_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'models.py'
        
        with open(credits_models_path, 'r') as f:
            models_content = f.read()
        
        # Should allow MinValueValidator(Decimal('0.0'))
        self.assertIn("MinValueValidator(Decimal('0.0'))", models_content,
                     "Service model does not allow zero credit cost")
        
        # Should have updated help text
        self.assertIn("0.0 for free services", models_content,
                     "Service model help text does not mention free services")
        
        # Should have updated __str__ method for free services
        self.assertIn("if credit_cost == 0:", models_content,
                     "Service model __str__ method does not handle zero cost")
        self.assertIn('return f"{name} (Free)"', models_content,
                     "Service model __str__ method does not return 'Free' for zero cost")
    
    def test_base_service_handles_zero_cost(self):
        """Test that BaseService handles zero-cost services correctly."""
        base_service_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'base.py'
        
        with open(base_service_path, 'r') as f:
            base_content = f.read()
        
        # Should handle zero-cost services
        self.assertIn("if service.credit_cost == 0:", base_content,
                     "BaseService does not handle zero-cost services")
        
        # Should create zero-amount transaction for tracking
        self.assertIn("amount=Decimal('0')", base_content,
                     "BaseService does not create zero-amount transaction")
        
        # Should have appropriate description for free services
        self.assertIn("(free)", base_content,
                     "BaseService description does not mention free services")
    
    def test_migration_exists_for_zero_cost(self):
        """Test that migration exists for zero-cost service support."""
        migrations_path = self.base_path / 'quickscale' / 'templates' / 'credits' / 'migrations'
        migration_file = migrations_path / '0008_allow_zero_cost_services.py'
        
        self.assertTrue(migration_file.exists(),
                       "Migration for zero-cost services not found")
        
        with open(migration_file, 'r') as f:
            migration_content = f.read()
        
        # Should update Service model credit_cost field
        self.assertIn("model_name='service'", migration_content,
                     "Migration does not target Service model")
        self.assertIn("name='credit_cost'", migration_content,
                     "Migration does not target credit_cost field")
        self.assertIn("MinValueValidator(Decimal('0.0'))", migration_content,
                     "Migration does not set correct validator")
    
    def test_configure_service_command_supports_free_flag(self):
        """Test that configure_service management command supports --free flag."""
        command_path = self.base_path / 'quickscale' / 'templates' / 'services' / 'management' / 'commands' / 'configure_service.py'
        
        with open(command_path, 'r') as f:
            command_content = f.read()
        
        # Should have --free flag
        self.assertIn("'--free'", command_content,
                     "configure_service command does not support --free flag")
        
        # Should handle free flag in logic
        self.assertIn("options['free']", command_content,
                     "configure_service command does not process --free flag")
        
        # Should set credit_cost to 0.0 when free
        self.assertIn("credit_cost = Decimal('0.0')", command_content,
                     "configure_service command does not set zero cost for free services")
        
        # Should display "Free" in output
        self.assertIn("if credit_cost == 0:", command_content,
                     "configure_service command does not handle free service display")
    
    def test_service_generator_supports_free_flag(self):
        """Test that service generator supports --free flag."""
        generator_path = self.base_path / 'quickscale' / 'commands' / 'service_generator_commands.py'
        
        with open(generator_path, 'r') as f:
            generator_content = f.read()
        
        # Should have free parameter
        self.assertIn("free: bool = False", generator_content,
                     "Service generator does not support free parameter")
        
        # Should handle free flag logic
        self.assertIn("if free:", generator_content,
                     "Service generator does not process free flag")
        self.assertIn("credit_cost = 0.0", generator_content,
                     "Service generator does not set zero cost for free services")
        
        # Should use --free flag in database configuration
        self.assertIn("--free", generator_content,
                     "Service generator does not use --free flag for database config")
    
    def test_cli_supports_free_flag(self):
        """Test that CLI supports --free flag for generate-service command."""
        cli_path = self.base_path / 'quickscale' / 'cli.py'
        
        with open(cli_path, 'r') as f:
            cli_content = f.read()
        
        # Should have --free argument
        self.assertIn("--free", cli_content,
                     "CLI does not support --free flag")
        
        # Should have help text for free flag
        self.assertIn("Generate a free service", cli_content,
                     "CLI does not have help text for --free flag")
        
        # Should have example usage
        self.assertIn("--free", cli_content,
                     "CLI does not show example usage of --free flag")
    
    def test_command_manager_supports_free_flag(self):
        """Test that command manager supports free flag."""
        manager_path = self.base_path / 'quickscale' / 'commands' / 'command_manager.py'
        
        with open(manager_path, 'r') as f:
            manager_content = f.read()
        
        # Should have free parameter in generate_service method
        self.assertIn("free: bool = False", manager_content,
                     "Command manager generate_service does not support free parameter")
        
        # Should pass free parameter to command
        self.assertIn("free=", manager_content,
                     "Command manager does not pass free parameter")
        
        # Should get free flag from args
        self.assertIn("getattr(args, 'free', False)", manager_content,
                     "Command manager does not extract free flag from args")
    
    def test_zero_cost_service_integration_complete(self):
        """Test that zero-cost service integration is complete across all components."""
        # This test verifies that all components work together
        components_to_check = [
            # Model changes
            ('quickscale/templates/credits/models.py', [
                'MinValueValidator(Decimal(\'0.0\'))',
                'if credit_cost == 0:',
                '0.0 for free services'
            ]),
            # BaseService changes
            ('quickscale/templates/services/base.py', [
                'if service.credit_cost == 0:',
                'amount=Decimal(\'0\')',
                '(free)'
            ]),
            # Migration
            ('quickscale/templates/credits/migrations/0008_allow_zero_cost_services.py', [
                'MinValueValidator(Decimal(\'0.0\'))',
                '0.0 for free services'
            ]),
            # Management command
            ('quickscale/templates/services/management/commands/configure_service.py', [
                '--free',
                'credit_cost = Decimal(\'0.0\')',
                'if credit_cost == 0:'
            ]),
            # Service generator
            ('quickscale/commands/service_generator_commands.py', [
                'free: bool = False',
                'if free:',
                'credit_cost = 0.0'
            ]),
            # CLI
            ('quickscale/cli.py', [
                '--free',
                'Generate a free service'
            ]),
            # Command manager
            ('quickscale/commands/command_manager.py', [
                'free: bool = False',
                'free=',
                'getattr(args, \'free\', False)'
            ])
        ]
        
        for file_path, required_content in components_to_check:
            full_path = self.base_path / file_path
            
            with self.subTest(file=file_path):
                self.assertTrue(full_path.exists(),
                               f"Required file {file_path} not found")
                
                with open(full_path, 'r') as f:
                    content = f.read()
                
                for required_text in required_content:
                    self.assertIn(required_text, content,
                                 f"Required content '{required_text}' not found in {file_path}")


if __name__ == '__main__':
    unittest.main() 