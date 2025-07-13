"""Commands for generating AI service templates and examples."""
import os
import string
from pathlib import Path
from typing import Dict, Optional, Any
from .command_base import Command
from quickscale.utils.message_manager import MessageManager
from quickscale.utils.template_generator import render_template
from quickscale.utils.service_templates import generate_service_file, get_service_readme_template
from quickscale.utils.timeout_constants import DOCKER_OPERATIONS_TIMEOUT


class ServiceGeneratorCommand(Command):
    """Command to generate service templates for AI engineers."""
    
    def execute(self, service_name: str, service_type: str = "basic", output_dir: Optional[str] = None, 
                credit_cost: float = 1.0, description: Optional[str] = None, skip_db_config: bool = False) -> Dict[str, Any]:
        """Generate a new service template."""
        self.logger.info(f"Generating service template: {service_name}")
        
        # Validate service name
        if not self._validate_service_name(service_name):
            raise ValueError(f"Invalid service name: {service_name}")
        
        # Generate description if not provided
        if not description:
            description = f"AI service: {service_name.replace('_', ' ').title()}"
        
        # Determine output directory
        if output_dir:
            target_dir = Path(output_dir)
        else:
            target_dir = Path.cwd() / "services"
        
        # Ensure target directory exists
        target_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate service file
        service_file_path = target_dir / f"{service_name}_service.py"
        
        if service_file_path.exists():
            MessageManager.warning(f"Service file already exists: {service_file_path}")
            overwrite = input("Overwrite existing file? [y/N]: ").lower().strip()
            if overwrite != 'y':
                MessageManager.info("Service generation cancelled")
                return {"success": False, "reason": "File already exists"}
        
        # Generate service template content
        template_content = self._get_service_template(service_type)
        
        # Template variables
        variables = {
            "SERVICE_NAME": service_name,
            "SERVICE_CLASS": self._to_class_name(service_name),
            "SERVICE_DESCRIPTION": description,
        }
        
        # Render template
        rendered_content = render_template(template_content, variables)
        
        # Write service file
        with open(service_file_path, 'w', encoding='utf-8') as f:
            f.write(rendered_content)
        
        MessageManager.success(f"Service template generated: {service_file_path}")
        
        # Generate usage example
        example_file_path = target_dir / f"{service_name}_example.py"
        example_content = self._get_usage_example_template()
        rendered_example = render_template(example_content, variables)
        
        with open(example_file_path, 'w', encoding='utf-8') as f:
            f.write(rendered_example)
        
        MessageManager.success(f"Usage example generated: {example_file_path}")
        
        result = {
            "success": True,
            "service_file": str(service_file_path),
            "example_file": str(example_file_path),
            "service_name": service_name,
            "description": description,
            "credit_cost": credit_cost
        }
        
        # Configure service in database unless skip_db_config is True
        if not skip_db_config:
            try:
                db_config_result = self._configure_service_in_database(service_name, description, credit_cost)
                result["database_configured"] = db_config_result["success"]
                if db_config_result["success"]:
                    MessageManager.success(f"Service '{service_name}' configured in database with {credit_cost} credit cost")
                else:
                    reason = db_config_result.get('reason', 'Unknown reason')
                    MessageManager.warning(f"Database configuration skipped: {reason}")
                    
                    # Provide helpful guidance based on the specific failure reason
                    if "Docker services are not running" in reason:
                        MessageManager.info("To configure the service in the database:")
                        MessageManager.info(f"  1. Start your project: quickscale up")
                        MessageManager.info(f"  2. Configure service: quickscale manage configure_service {service_name} --description \"{description}\" --credit-cost {credit_cost}")
                    elif "Cannot check Docker services" in reason:
                        MessageManager.info("To configure the service in the database:")
                        MessageManager.info(f"  1. Ensure Docker is running and project is started: quickscale up")
                        MessageManager.info(f"  2. Configure service: quickscale manage configure_service {service_name} --description \"{description}\" --credit-cost {credit_cost}")
                    else:
                        MessageManager.info(f"You can configure it manually with: quickscale manage configure_service {service_name} --description \"{description}\" --credit-cost {credit_cost}")
                    
                    result["database_config_warning"] = reason
            except Exception as e:
                MessageManager.warning(f"Could not configure service in database: {str(e)}")
                MessageManager.info("To configure the service in the database:")
                MessageManager.info(f"  1. Start your project: quickscale up")
                MessageManager.info(f"  2. Configure service: quickscale manage configure_service {service_name} --description \"{description}\" --credit-cost {credit_cost}")
                result["database_configured"] = False
                result["database_config_error"] = str(e)
        else:
            MessageManager.info(f"Database configuration skipped. Configure manually with:")
            MessageManager.info(f"  quickscale manage configure_service {service_name} --description \"{description}\" --credit-cost {credit_cost}")
            result["database_configured"] = False
            result["database_config_skipped"] = True
        
        return result
    
    def _validate_service_name(self, service_name: str) -> bool:
        """Validate service name follows Python naming conventions."""
        if not service_name:
            return False
        
        # Must be valid Python identifier
        if not service_name.isidentifier():
            return False
        
        # Should not start with uppercase (by convention)
        if service_name[0].isupper():
            return False
        
        # Should use snake_case
        if ' ' in service_name or '-' in service_name:
            return False
        
        return True
    
    def _configure_service_in_database(self, service_name: str, description: str, credit_cost: float) -> Dict[str, Any]:
        """Configure the service in the database by running Django management command."""
        import os
        import subprocess
        from decimal import Decimal
        
        # Check if we're in a Django project directory
        if not os.path.exists('manage.py'):
            return {"success": False, "reason": "Not in a Django project directory (manage.py not found)"}
        
        # Check if Docker services are running before attempting database operations
        try:
            # Use docker compose ps to check if services are up
            result = subprocess.run(['docker', 'compose', 'ps', '--quiet'], 
                                   capture_output=True, text=True, timeout=10)
            
            if result.returncode != 0 or not result.stdout.strip():
                return {
                    "success": False, 
                    "reason": "Docker services are not running. Start services with 'quickscale up' first."
                }
                
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return {
                "success": False, 
                "reason": "Cannot check Docker services. Ensure Docker is installed and 'quickscale up' has been run."
            }
        
        try:
            # Use quickscale manage to run the Django management command inside Docker container
            cmd = [
                'quickscale', 'manage', 'configure_service', service_name,
                '--description', description,
                '--credit-cost', str(credit_cost)
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=DOCKER_OPERATIONS_TIMEOUT)
            
            if result.returncode == 0:
                return {"success": True, "output": result.stdout}
            else:
                return {"success": False, "reason": f"Management command failed: {result.stderr}"}
                
        except subprocess.TimeoutExpired:
            return {"success": False, "reason": "Database configuration timed out"}
        except Exception as e:
            return {"success": False, "reason": f"Error running management command: {str(e)}"}
    
    def _to_class_name(self, service_name: str) -> str:
        """Convert snake_case service name to PascalCase class name."""
        words = service_name.split('_')
        return ''.join(word.capitalize() for word in words) + 'Service'
    
    def _get_service_template(self, service_type: str) -> str:
        """Get the appropriate service template based on type."""
        if service_type == "text_processing":
            return self._get_text_processing_template()
        elif service_type == "image_processing":
            return self._get_image_processing_template()
        else:
            return self._get_basic_template()
    
    def _get_basic_template(self) -> str:
        """Basic service template for general use."""
        return '''"""
$SERVICE_DESCRIPTION implementation using QuickScale AI Service Framework.

This service integrates with the credit system and provides a foundation
for implementing AI functionality.
"""

from typing import Dict, Any
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service

User = get_user_model()


@register_service("$SERVICE_NAME")
class $SERVICE_CLASS(BaseService):
    """$SERVICE_DESCRIPTION that consumes credits."""
    
    def execute_service(self, user: User, **kwargs) -> Dict[str, Any]:
        """Execute the $SERVICE_NAME logic."""
        # TODO: Implement your AI service logic here
        
        # Example input validation
        input_data = kwargs.get('input_data')
        if not input_data:
            raise ValueError("input_data is required for $SERVICE_NAME")
        
        # TODO: Replace this placeholder with your actual implementation
        # Examples:
        # - Call external AI APIs (OpenAI, Hugging Face, etc.)
        # - Process data with local models
        # - Perform complex calculations
        # - Generate content or insights
        
        result = {
            'service_name': '$SERVICE_NAME',
            'status': 'completed',
            'input_received': bool(input_data),
            'message': 'Service executed successfully',
            # TODO: Add your actual results here
        }
        
        return result
'''
    
    def _get_text_processing_template(self) -> str:
        """Text processing service template."""
        return '''"""
$SERVICE_DESCRIPTION implementation for text processing using QuickScale AI Service Framework.

This service provides text analysis capabilities with credit consumption tracking.
"""

from typing import Dict, Any, List
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service

User = get_user_model()


@register_service("$SERVICE_NAME")
class $SERVICE_CLASS(BaseService):
    """$SERVICE_DESCRIPTION that processes text and consumes credits."""
    
    def execute_service(self, user: User, text: str = "", **kwargs) -> Dict[str, Any]:
        """Execute text processing logic."""
        if not text:
            raise ValueError("Text input is required for $SERVICE_NAME")
        
        # Basic text analysis
        words = text.split()
        word_count = len(words)
        char_count = len(text)
        sentence_count = text.count('.') + text.count('!') + text.count('?')
        
        # TODO: Implement your text processing logic here
        # Examples:
        # - Sentiment analysis
        # - Text summarization
        # - Language detection
        # - Named entity recognition
        # - Text classification
        # - Content generation
        
        result = {
            'service_name': '$SERVICE_NAME',
            'status': 'completed',
            'analysis': {
                'word_count': word_count,
                'character_count': char_count,
                'sentence_count': sentence_count,
                'text_length': len(text.strip())
            },
            'metadata': {
                'processing_time': 'N/A',  # TODO: Add actual timing
                'model_version': '1.0',
                'confidence_score': 0.95  # TODO: Add actual confidence if applicable
            }
            # TODO: Add your text processing results here
        }
        
        return result
'''
    
    def _get_image_processing_template(self) -> str:
        """Image processing service template."""
        return '''"""
$SERVICE_DESCRIPTION implementation for image processing using QuickScale AI Service Framework.

This service provides image analysis capabilities with credit consumption tracking.
"""

from typing import Dict, Any, Union
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service

User = get_user_model()


@register_service("$SERVICE_NAME")
class $SERVICE_CLASS(BaseService):
    """$SERVICE_DESCRIPTION that processes images and consumes credits."""
    
    def execute_service(self, user: User, image_data: Union[str, bytes] = None, **kwargs) -> Dict[str, Any]:
        """Execute image processing logic."""
        if not image_data:
            raise ValueError("Image data is required for $SERVICE_NAME")
        
        # Basic image info
        image_size = len(image_data) if isinstance(image_data, (str, bytes)) else 0
        
        # TODO: Implement your image processing logic here
        # Examples:
        # - Image classification
        # - Object detection
        # - Face recognition
        # - Image enhancement
        # - Style transfer
        # - OCR (text extraction)
        # - Image generation
        
        result = {
            'service_name': '$SERVICE_NAME',
            'status': 'completed',
            'image_info': {
                'size_bytes': image_size,
                'format': kwargs.get('image_format', 'unknown'),
                'dimensions': kwargs.get('dimensions', 'unknown')
            },
            'analysis_results': {
                # TODO: Add your actual image analysis results here
                'detected_objects': [],
                'confidence_scores': [],
                'processing_notes': 'Placeholder implementation'
            },
            'metadata': {
                'processing_time': 'N/A',  # TODO: Add actual timing
                'model_version': '1.0',
                'confidence_score': 0.90  # TODO: Add actual confidence if applicable
            }
        }
        
        return result
'''
    
    def _get_usage_example_template(self) -> str:
        """Generate usage example template."""
        return '''"""
Usage example for $SERVICE_CLASS.

This example demonstrates how to use the $SERVICE_NAME service
with the QuickScale credit system.
"""

from django.contrib.auth import get_user_model
from services.decorators import create_service_instance
from credits.models import InsufficientCreditsError

User = get_user_model()


def use_$SERVICE_NAME_service(user, **kwargs):
    """Example function showing how to use the $SERVICE_NAME service."""
    
    # Method 1: Using the service registry
    service = create_service_instance("$SERVICE_NAME")
    if not service:
        return {'error': 'Service $SERVICE_NAME not found'}
    
    # Check if user has sufficient credits
    credit_check = service.check_user_credits(user)
    if not credit_check['has_sufficient_credits']:
        return {
            'error': f"Insufficient credits. Need {credit_check['shortfall']} more credits.",
            'required_credits': credit_check['required_credits'],
            'available_credits': credit_check['available_credits']
        }
    
    # Run the service (consumes credits and executes)
    try:
        result = service.run(user, **kwargs)
        return result
    except InsufficientCreditsError as e:
        return {'error': str(e)}
    except ValueError as e:
        return {'error': f"Validation error: {str(e)}"}
    except Exception as e:
        return {'error': f"Service execution error: {str(e)}"}


def example_usage():
    """Example usage scenarios."""
    # Get a user (in real usage, this would come from request.user or similar)
    user = User.objects.first()
    if not user:
        print("No users found. Please create a user first.")
        return
    
    # Example 1: Basic usage
    result = use_$SERVICE_NAME_service(
        user,
        input_data="Example input data"  # TODO: Adjust based on your service needs
    )
    print("Result:", result)
    
    # Example 2: Error handling
    if 'error' in result:
        print(f"Service error: {result['error']}")
    else:
        print(f"Service succeeded: {result.get('result', {})}")
        print(f"Credits consumed: {result.get('credits_consumed', 0)}")


if __name__ == "__main__":
    # This would typically be called from views, management commands, or API endpoints
    example_usage()
'''


class ValidateServiceCommand(Command):
    """Command to validate service files and provide development assistance."""
    
    def execute(self, name_or_path: Optional[str] = None, show_tips: bool = False) -> Dict[str, Any]:
        """Validate a service file and show development tips."""
        from quickscale.utils.service_dev_utils import validate_service_file, ServiceDevelopmentHelper
        from quickscale.utils.error_manager import CommandError
        
        if show_tips:
            ServiceDevelopmentHelper.display_development_tips()
            MessageManager.info("")
        
        service_file_path: Optional[Path] = None

        if not name_or_path:
            raise CommandError("Missing service name or file path. Please provide a service name or full path to the service file.")

        path_obj = Path(name_or_path)

        if path_obj.exists() and path_obj.is_file():
            service_file_path = path_obj
        elif '/' in name_or_path or '\\' in name_or_path or name_or_path.endswith('.py'):
            # If it looks like a path but doesn't exist yet, assume it's an intended path
            service_file_path = path_obj
        else:
            # Assume it's a service name and construct the default path
            service_file_path = Path.cwd() / "services" / f"{name_or_path}_service.py"

        if not service_file_path or not service_file_path.exists():
            raise CommandError(f"Service file not found at: {service_file_path}\n\nSuggestion: Ensure the service name is correct or provide the full path to the service file.")

        validate_service_file(str(service_file_path))
        
        return {"validation_completed": True}


class ServiceExamplesCommand(Command):
    """Command to show available service examples."""
    
    def execute(self, example_type: Optional[str] = None) -> Dict[str, Any]:
        """Show available service examples."""
        from quickscale.utils.service_dev_utils import show_service_examples, ServiceDevelopmentHelper
        
        if example_type:
            examples = ServiceDevelopmentHelper.get_service_examples()
            filtered_examples = [ex for ex in examples if ex['type'] == example_type]
            
            if not filtered_examples:
                MessageManager.warning(f"No examples found for type: {example_type}")
                MessageManager.info("Available types: basic, text_processing, image_processing")
                return {"examples": [], "count": 0}
            
            MessageManager.info(f"📚 {example_type.title()} Service Examples:")
            MessageManager.info("")
            
            for example in filtered_examples:
                MessageManager.info(f"🔧 {example['name']}")
                MessageManager.info(f"   Description: {example['description']}")
                MessageManager.info(f"   Use case: {example['use_case']}")
                MessageManager.info(f"   Generate: quickscale generate-service {example['name']} --type {example['type']}")
                MessageManager.info("")
            
            return {"examples": filtered_examples, "count": len(filtered_examples)}
        else:
            show_service_examples()
            return {"examples_displayed": True} 