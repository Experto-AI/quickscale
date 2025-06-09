"""Service development utilities for AI engineers."""
import os
import importlib.util
from pathlib import Path
from typing import Dict, List, Optional, Any, Type
from quickscale.utils.message_manager import MessageManager
from django.core.management.base import CommandError


class ServiceDevelopmentHelper:
    """Utility class to help AI engineers with service development."""
    
    @staticmethod
    def validate_service_structure(service_file_path: str) -> Dict[str, Any]:
        """Validate that a service file follows the correct structure."""
        validation_result = {
            "valid": False,
            "errors": [],
            "warnings": [],
            "suggestions": []
        }
        
        if not os.path.exists(service_file_path):
            validation_result["errors"].append(f"Service file not found: {service_file_path}")
            return validation_result
        
        try:
            with open(service_file_path, 'r') as f:
                content = f.read()
            
            # Check for required imports
            required_imports = [
                "from services.base import BaseService",
                "from services.decorators import register_service"
            ]
            
            for import_stmt in required_imports:
                if import_stmt not in content:
                    validation_result["errors"].append(f"Missing required import: {import_stmt}")
            
            # Check for BaseService inheritance
            if "class" in content and "BaseService" in content:
                if "class" in content and "(BaseService)" not in content:
                    validation_result["errors"].append("Service class must inherit from BaseService")
            else:
                validation_result["errors"].append("Service class not found or doesn't inherit from BaseService")
            
            # Check for @register_service decorator
            if "@register_service" not in content:
                validation_result["errors"].append("Missing @register_service decorator")
            
            # Check for execute_service method
            if "def execute_service" not in content:
                validation_result["errors"].append("Missing execute_service method")
            
            # Check for proper type hints
            if "from typing import" not in content:
                validation_result["warnings"].append("Consider adding type hints for better code quality")
            
            # Check for docstrings
            if '"""' not in content:
                validation_result["warnings"].append("Consider adding docstrings for better documentation")
            
            # Suggestions for best practices
            if "TODO" in content:
                validation_result["suggestions"].append("Remember to implement the TODO items before deploying")
            
            if "raise ValueError" not in content:
                validation_result["suggestions"].append("Consider adding input validation with appropriate error messages")
            
            validation_result["valid"] = len(validation_result["errors"]) == 0
            
        except Exception as e:
            validation_result["errors"].append(f"Error reading service file: {str(e)}")
        
        return validation_result
    
    @staticmethod
    def analyze_service_dependencies(service_file_path: str) -> Dict[str, Any]:
        """Analyze service dependencies and suggest optimizations."""
        analysis = {
            "external_imports": [],
            "suggested_packages": [],
            "potential_issues": [],
            "recommendations": []
        }
        
        if not os.path.exists(service_file_path):
            analysis["potential_issues"].append(f"Service file not found: {service_file_path}")
            return analysis
        
        try:
            with open(service_file_path, 'r') as f:
                lines = f.readlines()
            
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if line.startswith("import ") or line.startswith("from "):
                    # Skip QuickScale internal imports
                    if "services." in line or "credits." in line or "django." in line:
                        continue
                    
                    # Identify external packages
                    if "import " in line:
                        analysis["external_imports"].append({
                            "line": line_num,
                            "import": line
                        })
                        
                        # Suggest popular AI packages
                        if any(pkg in line for pkg in ["numpy", "pandas", "sklearn"]):
                            analysis["suggested_packages"].append("Consider using requirements.txt to track these dependencies")
                        
                        if "openai" in line.lower():
                            analysis["recommendations"].append("Remember to handle OpenAI API rate limits and errors")
                        
                        if "requests" in line:
                            analysis["recommendations"].append("Consider using connection pooling for HTTP requests")
                        
                        if "PIL" in line or "cv2" in line:
                            analysis["recommendations"].append("Image processing can be memory intensive - consider cleanup")
        
        except Exception as e:
            analysis["potential_issues"].append(f"Error analyzing dependencies: {str(e)}")
        
        return analysis
    
    @staticmethod
    def generate_service_config_template(service_name: str, credit_cost: float = 1.0) -> str:
        """Generate a configuration template for adding the service to the database."""
        template = f'''"""
Configuration for {service_name} service.

Add this configuration to your Django management command or admin interface:
"""

from credits.models import Service

# Create or update service configuration
service, created = Service.objects.get_or_create(
    name="{service_name}",
    defaults={{
        "description": "TODO: Add description for {service_name}",
        "credit_cost": {credit_cost},
        "is_active": True
    }}
)

if created:
    print(f"Created new service: {{service.name}}")
else:
    print(f"Service already exists: {{service.name}}")
    # Update existing service if needed
    service.credit_cost = {credit_cost}
    service.is_active = True
    service.save()
    print(f"Updated service configuration")
'''
        return template
    
    @staticmethod
    def check_project_structure() -> Dict[str, Any]:
        """Check if the current directory is a QuickScale project."""
        check_result = {
            "is_quickscale_project": False,
            "missing_components": [],
            "recommendations": []
        }
        
        current_dir = Path.cwd()
        
        # Check for key QuickScale files/directories
        required_components = [
            ("manage.py", "Django management script"),
            ("services/", "Services directory"),
            ("credits/", "Credits app directory"),
            ("docker-compose.yml", "Docker Compose configuration"),
            (".env", "Environment configuration")
        ]
        
        for component, description in required_components:
            if not (current_dir / component).exists():
                check_result["missing_components"].append({
                    "component": component,
                    "description": description
                })
        
        check_result["is_quickscale_project"] = len(check_result["missing_components"]) == 0
        
        if not check_result["is_quickscale_project"]:
            check_result["recommendations"].append(
                "This doesn't appear to be a QuickScale project. "
                "Use 'quickscale init <project_name>' to create a new project."
            )
        
        return check_result
    
    @staticmethod
    def get_service_examples() -> List[Dict[str, str]]:
        """Get a list of available service examples with descriptions."""
        examples = [
            {
                "name": "text_sentiment",
                "type": "text_processing",
                "description": "Analyze sentiment of text input using simple keyword matching",
                "use_case": "Customer feedback analysis, social media monitoring"
            },
            {
                "name": "text_summarizer",
                "type": "text_processing", 
                "description": "Create summaries of long text by extracting key sentences",
                "use_case": "Document summarization, news article processing"
            },
            {
                "name": "image_classifier",
                "type": "image_processing",
                "description": "Classify images into predefined categories",
                "use_case": "Content moderation, product categorization"
            },
            {
                "name": "text_translator",
                "type": "text_processing",
                "description": "Translate text between languages using external APIs",
                "use_case": "Multilingual content, international communication"
            },
            {
                "name": "document_parser",
                "type": "text_processing",
                "description": "Extract structured data from documents",
                "use_case": "Invoice processing, form data extraction"
            }
        ]
        return examples
    
    @staticmethod
    def display_development_tips() -> None:
        """Display helpful tips for service development."""
        MessageManager.info("🚀 QuickScale Service Development Tips:")
        MessageManager.info("")
        MessageManager.info("1. Service Structure:")
        MessageManager.info("   - Inherit from BaseService")
        MessageManager.info("   - Use @register_service decorator")
        MessageManager.info("   - Implement execute_service method")
        MessageManager.info("")
        MessageManager.info("2. Credit System:")
        MessageManager.info("   - Credits are consumed automatically when service.run() is called")
        MessageManager.info("   - Use service.check_user_credits() to validate before processing")
        MessageManager.info("   - Configure credit costs in the Service model via admin")
        MessageManager.info("")
        MessageManager.info("3. Error Handling:")
        MessageManager.info("   - Validate inputs early with clear error messages")
        MessageManager.info("   - Handle external API failures gracefully")
        MessageManager.info("   - Don't catch InsufficientCreditsError - let it propagate")
        MessageManager.info("")
        MessageManager.info("4. Testing:")
        MessageManager.info("   - Test with different user credit scenarios")
        MessageManager.info("   - Mock external API calls for consistent testing")
        MessageManager.info("   - Validate both success and error paths")
        MessageManager.info("")
        MessageManager.info("5. Performance:")
        MessageManager.info("   - Consider caching for expensive operations")
        MessageManager.info("   - Handle large data efficiently")
        MessageManager.info("   - Use connection pooling for external services")


def validate_service_file(file_path: str) -> None:
    """Validate a service file and display results."""
    helper = ServiceDevelopmentHelper()
    
    MessageManager.info(f"Validating service file: {file_path}")
    
    # Check project structure first
    project_check = helper.check_project_structure()
    if not project_check["is_quickscale_project"]:
        MessageManager.warning("Warning: This doesn't appear to be a QuickScale project")
        for missing in project_check["missing_components"]:
            MessageManager.warning(f"  Missing: {missing['component']} ({missing['description']})")
        MessageManager.info("")
    
    # Validate service structure
    validation = helper.validate_service_structure(file_path)
    
    if validation["valid"]:
        MessageManager.success("✅ Service structure is valid!")
    else:
        MessageManager.error("❌ Service validation failed:")
        for error in validation["errors"]:
            MessageManager.error(f"  • {error}")
    
    if validation["warnings"]:
        MessageManager.warning("⚠️ Warnings:")
        for warning in validation["warnings"]:
            MessageManager.warning(f"  • {warning}")
    
    if validation["suggestions"]:
        MessageManager.info("💡 Suggestions:")
        for suggestion in validation["suggestions"]:
            MessageManager.info(f"  • {suggestion}")
    
    # Analyze dependencies
    MessageManager.info("")
    MessageManager.info("🔍 Dependency Analysis:")
    
    analysis = helper.analyze_service_dependencies(file_path)
    
    if analysis["external_imports"]:
        MessageManager.info("External imports found:")
        for imp in analysis["external_imports"]:
            MessageManager.info(f"  Line {imp['line']}: {imp['import']}")
    
    if analysis["recommendations"]:
        MessageManager.info("Recommendations:")
        for rec in analysis["recommendations"]:
            MessageManager.info(f"  • {rec}")
    
    if analysis["potential_issues"]:
        MessageManager.warning("Potential issues:")
        for issue in analysis["potential_issues"]:
            MessageManager.warning(f"  • {issue}")
    
    if not validation["valid"]:
        MessageManager.error("Service validation failed. Please fix the errors listed above.")
        raise CommandError("Service validation failed due to structural issues.")


def show_service_examples() -> None:
    """Display available service examples."""
    helper = ServiceDevelopmentHelper()
    examples = helper.get_service_examples()
    
    MessageManager.info("📚 Available Service Examples:")
    MessageManager.info("")
    
    for example in examples:
        MessageManager.info(f"🔧 {example['name']} ({example['type']})")
        MessageManager.info(f"   Description: {example['description']}")
        MessageManager.info(f"   Use case: {example['use_case']}")
        MessageManager.info(f"   Generate: quickscale generate-service {example['name']} --type {example['type']}")
        MessageManager.info("") 