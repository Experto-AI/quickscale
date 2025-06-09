"""
Service templates for the QuickScale service generator.

These templates provide the foundation for creating AI services that integrate
with the QuickScale credit system.
"""

from typing import Dict, Any
import string


def get_basic_service_template() -> str:
    """Get the basic service template."""
    return """\"\"\"
${service_description}

This service demonstrates the basic pattern for creating AI services in QuickScale.
\"\"\"

from typing import Dict, Any, Optional
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service

User = get_user_model()


@register_service("${service_name}")
class ${service_class_name}(BaseService):
    \"\"\"${service_description}\"\"\"
    
    def execute_service(self, user: User, **kwargs) -> Dict[str, Any]:
        \"\"\"Execute the ${service_name} service.\"\"\"
        # TODO: Implement your service logic here
        
        # Example input validation
        input_data = kwargs.get('input_data')
        if not input_data:
            raise ValueError("input_data is required")
        
        # TODO: Add your AI/processing logic here
        # Example:
        # result = your_ai_function(input_data)
        
        # Placeholder result
        result = {
            'processed': True,
            'input_received': str(input_data),
            'message': 'Service executed successfully',
            'service_name': '${service_name}'
        }
        
        return result


# Usage example:
\"\"\"
from services.decorators import create_service_instance
from django.contrib.auth import get_user_model

User = get_user_model()

def use_${service_name}(user, input_data):
    # Create service instance
    service = create_service_instance("${service_name}")
    
    if not service:
        return {'error': 'Service not available'}
    
    # Check credits before processing
    credit_check = service.check_user_credits(user)
    if not credit_check['has_sufficient_credits']:
        return {
            'error': f"Insufficient credits. Need {credit_check['shortfall']} more credits."
        }
    
    try:
        # Run the service (consumes credits and executes)
        result = service.run(user, input_data=input_data)
        return result
    except Exception as e:
        return {'error': str(e)}

# Example usage:
# user = User.objects.get(email='user@example.com')
# result = use_${service_name}(user, "your input data")
# print(result)
\"\"\"
"""


def get_text_processing_template() -> str:
    """Get the text processing service template."""
    return """\"\"\"
${service_description}

This service provides text processing capabilities using the QuickScale framework.
Optimized for analyzing and processing text data.
\"\"\"

import re
from typing import Dict, Any, List, Optional
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service

User = get_user_model()


@register_service("${service_name}")
class ${service_class_name}(BaseService):
    \"\"\"${service_description}\"\"\"
    
    def execute_service(self, user: User, text: str = "", **kwargs) -> Dict[str, Any]:
        \"\"\"Process text and return analysis results.\"\"\"
        # Input validation
        if not text or not isinstance(text, str):
            raise ValueError("Text input is required and must be a string")
        
        if len(text.strip()) == 0:
            raise ValueError("Text input cannot be empty")
        
        # Optional parameters
        max_length = kwargs.get('max_length', 10000)
        if len(text) > max_length:
            raise ValueError(f"Text too long (max {max_length} characters)")
        
        # TODO: Implement your text processing logic here
        # Examples:
        # - Sentiment analysis
        # - Text classification
        # - Language detection
        # - Keyword extraction
        # - Text summarization
        
        # Basic text analysis (placeholder)
        word_count = len(text.split())
        char_count = len(text)
        sentence_count = len(re.findall(r'[.!?]+', text))
        
        # Extract basic features
        words = text.lower().split()
        unique_words = len(set(words))
        avg_word_length = sum(len(word) for word in words) / len(words) if words else 0
        
        # TODO: Replace with your AI model results
        result = {
            'analysis': {
                'word_count': word_count,
                'character_count': char_count,
                'sentence_count': sentence_count,
                'unique_words': unique_words,
                'avg_word_length': round(avg_word_length, 2),
                'readability_score': self._calculate_readability(text)
            },
            'features': {
                'has_questions': '?' in text,
                'has_exclamations': '!' in text,
                'has_urls': bool(re.search(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', text)),
                'has_emails': bool(re.search(r'\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b', text))
            },
            'metadata': {
                'service_name': '${service_name}',
                'processing_time_ms': 0,  # TODO: Add actual timing
                'model_version': '1.0',
                'language': 'unknown'  # TODO: Add language detection
            }
        }
        
        return result
    
    def _calculate_readability(self, text: str) -> float:
        \"\"\"Calculate a simple readability score.\"\"\"
        words = text.split()
        sentences = len(re.findall(r'[.!?]+', text))
        
        if not words or sentences == 0:
            return 0.0
        
        avg_words_per_sentence = len(words) / sentences
        avg_chars_per_word = sum(len(word) for word in words) / len(words)
        
        # Simple readability score (lower is easier to read)
        score = (avg_words_per_sentence * 0.39) + (avg_chars_per_word * 11.8)
        return round(score, 2)


# Advanced usage example:
\"\"\"
from services.decorators import create_service_instance
from django.contrib.auth import get_user_model

User = get_user_model()

def analyze_text_content(user, text_content, options=None):
    options = options or {}
    
    service = create_service_instance("${service_name}")
    if not service:
        return {'error': 'Text processing service not available'}
    
    try:
        # Run with options
        result = service.run(
            user, 
            text=text_content,
            max_length=options.get('max_length', 5000)
        )
        
        # Add custom post-processing if needed
        analysis = result['result']['analysis']
        if analysis['word_count'] > 1000:
            result['result']['complexity'] = 'high'
        elif analysis['word_count'] > 100:
            result['result']['complexity'] = 'medium' 
        else:
            result['result']['complexity'] = 'low'
        
        return result
    except Exception as e:
        return {'error': f'Text processing failed: {str(e)}'}

# Batch processing example:
def batch_process_texts(user, texts: List[str]):
    service = create_service_instance("${service_name}")
    results = []
    
    for i, text in enumerate(texts):
        try:
            result = service.run(user, text=text)
            results.append({
                'index': i,
                'success': True,
                'result': result['result']
            })
        except Exception as e:
            results.append({
                'index': i,
                'success': False,
                'error': str(e)
            })
    
    return {
        'batch_results': results,
        'total_processed': len(texts),
        'successful': sum(1 for r in results if r['success'])
    }
\"\"\"
"""


def get_image_processing_template() -> str:
    """Get the image processing service template."""
    return """\"\"\"
${service_description}

This service provides image processing capabilities using the QuickScale framework.
Optimized for analyzing and processing image data.
\"\"\"

import base64
import io
from typing import Dict, Any, Union, Optional
from django.contrib.auth import get_user_model
from services.base import BaseService
from services.decorators import register_service

User = get_user_model()


@register_service("${service_name}")
class ${service_class_name}(BaseService):
    \"\"\"${service_description}\"\"\"
    
    def execute_service(self, user: User, image_data: Union[str, bytes] = None, **kwargs) -> Dict[str, Any]:
        \"\"\"Process image and return analysis results.\"\"\"
        # Input validation
        if not image_data:
            raise ValueError("Image data is required")
        
        # Handle different input formats
        if isinstance(image_data, str):
            # Handle base64 encoded images
            if image_data.startswith('data:image/'):
                # Extract base64 data from data URL
                image_data = image_data.split(',')[1]
            
            try:
                # Decode base64 to bytes
                image_bytes = base64.b64decode(image_data)
            except Exception as e:
                raise ValueError(f"Invalid base64 image data: {str(e)}")
        else:
            # Already bytes
            image_bytes = image_data
        
        # Validate image size
        max_size = kwargs.get('max_size_mb', 10)  # 10MB default
        if len(image_bytes) > max_size * 1024 * 1024:
            raise ValueError(f"Image too large (max {max_size}MB)")
        
        # TODO: Implement your image processing logic here
        # Examples:
        # - Image classification
        # - Object detection
        # - Face recognition
        # - OCR (text extraction)
        # - Image enhancement
        # - Style transfer
        
        # Basic image analysis (placeholder)
        image_info = self._analyze_image_data(image_bytes)
        
        # TODO: Replace with your AI model results
        result = {
            'image_info': image_info,
            'analysis': {
                'detected_objects': [],  # TODO: Add object detection
                'classification': {
                    'categories': [],  # TODO: Add classification results
                    'confidence_scores': []
                },
                'features': {
                    'has_faces': False,  # TODO: Add face detection
                    'has_text': False,   # TODO: Add OCR
                    'dominant_colors': [],  # TODO: Add color analysis
                    'brightness': 0.5,   # TODO: Add brightness analysis
                    'contrast': 0.5      # TODO: Add contrast analysis
                }
            },
            'metadata': {
                'service_name': '${service_name}',
                'processing_time_ms': 0,  # TODO: Add actual timing
                'model_version': '1.0',
                'processing_resolution': image_info.get('estimated_dimensions', 'unknown')
            }
        }
        
        return result
    
    def _analyze_image_data(self, image_bytes: bytes) -> Dict[str, Any]:
        \"\"\"Analyze basic image properties from byte data.\"\"\"
        file_size = len(image_bytes)
        
        # Detect image format from headers
        format_info = self._detect_image_format(image_bytes)
        
        # Estimate dimensions based on file size (rough estimation)
        estimated_dimensions = self._estimate_dimensions(file_size, format_info['format'])
        
        return {
            'file_size_bytes': file_size,
            'file_size_mb': round(file_size / (1024 * 1024), 2),
            'format': format_info['format'],
            'estimated_dimensions': estimated_dimensions,
            'quality_estimate': self._estimate_quality(file_size, format_info['format'])
        }
    
    def _detect_image_format(self, image_bytes: bytes) -> Dict[str, Any]:
        \"\"\"Detect image format from file headers.\"\"\"
        if image_bytes.startswith(b'\\xFF\\xD8\\xFF'):
            return {'format': 'jpeg', 'mime_type': 'image/jpeg'}
        elif image_bytes.startswith(b'\\x89PNG\\r\\n\\x1a\\n'):
            return {'format': 'png', 'mime_type': 'image/png'}
        elif image_bytes.startswith(b'GIF8'):
            return {'format': 'gif', 'mime_type': 'image/gif'}
        elif image_bytes.startswith(b'RIFF') and b'WEBP' in image_bytes[:12]:
            return {'format': 'webp', 'mime_type': 'image/webp'}
        else:
            return {'format': 'unknown', 'mime_type': 'application/octet-stream'}
    
    def _estimate_dimensions(self, file_size: int, format_type: str) -> str:
        \"\"\"Estimate image dimensions based on file size and format.\"\"\"
        # Very rough estimation based on typical compression ratios
        if format_type == 'png':
            # PNG is typically less compressed
            if file_size < 100000:  # < 100KB
                return "small (< 800x600)"
            elif file_size < 1000000:  # < 1MB
                return "medium (800x600 - 1920x1080)"
            else:
                return "large (> 1920x1080)"
        else:
            # JPEG and others are more compressed
            if file_size < 50000:  # < 50KB
                return "small (< 640x480)"
            elif file_size < 500000:  # < 500KB
                return "medium (640x480 - 1920x1080)"
            else:
                return "large (> 1920x1080)"
    
    def _estimate_quality(self, file_size: int, format_type: str) -> str:
        \"\"\"Estimate image quality based on size and format.\"\"\"
        if format_type == 'jpeg':
            if file_size < 50000:
                return "low"
            elif file_size < 200000:
                return "medium"
            else:
                return "high"
        elif format_type == 'png':
            return "lossless"
        else:
            return "unknown"


# Advanced usage example:
\"\"\"
from services.decorators import create_service_instance
from django.contrib.auth import get_user_model
import base64

User = get_user_model()

def process_uploaded_image(user, image_file):
    # Read image file
    image_data = image_file.read()
    
    service = create_service_instance("${service_name}")
    if not service:
        return {'error': 'Image processing service not available'}
    
    try:
        result = service.run(
            user,
            image_data=image_data,
            max_size_mb=5  # 5MB limit
        )
        
        # Add custom metadata
        result['result']['upload_info'] = {
            'original_filename': getattr(image_file, 'name', 'unknown'),
            'upload_size': len(image_data)
        }
        
        return result
    except Exception as e:
        return {'error': f'Image processing failed: {str(e)}'}

def process_base64_image(user, base64_string):
    service = create_service_instance("${service_name}")
    
    try:
        result = service.run(user, image_data=base64_string)
        return result
    except Exception as e:
        return {'error': f'Base64 image processing failed: {str(e)}'}

# Batch image processing:
def batch_process_images(user, image_files):
    service = create_service_instance("${service_name}")
    results = []
    
    for i, image_file in enumerate(image_files):
        try:
            image_data = image_file.read()
            result = service.run(user, image_data=image_data)
            results.append({
                'index': i,
                'filename': getattr(image_file, 'name', f'image_{i}'),
                'success': True,
                'result': result['result']
            })
        except Exception as e:
            results.append({
                'index': i,
                'filename': getattr(image_file, 'name', f'image_{i}'),
                'success': False,
                'error': str(e)
            })
    
    return {
        'batch_results': results,
        'total_processed': len(image_files),
        'successful': sum(1 for r in results if r['success'])
    }
\"\"\"
"""


def generate_service_file(service_name: str, service_type: str = "basic", 
                         service_description: str = None) -> str:
    """Generate a service file from templates."""
    
    # Convert service name to class name (PascalCase)
    service_class_name = ''.join(word.capitalize() for word in service_name.split('_'))
    if not service_class_name.endswith('Service'):
        service_class_name += 'Service'
    
    # Default description if not provided
    if not service_description:
        service_description = f"AI service: {service_name.replace('_', ' ').title()}"
    
    # Template variables
    template_vars = {
        'service_name': service_name,
        'service_class_name': service_class_name,
        'service_description': service_description
    }
    
    # Get appropriate template
    if service_type == "text_processing":
        template = get_text_processing_template()
    elif service_type == "image_processing":
        template = get_image_processing_template()
    else:
        template = get_basic_service_template()
    
    # Substitute variables in template
    return string.Template(template).substitute(template_vars)


def get_service_readme_template() -> str:
    """Get README template for generated services."""
    return """# ${service_name} Service

${service_description}

## Setup

1. **Configure the service in the database:**
   ```bash
   python manage.py configure_service ${service_name} \\
       --description "${service_description}" \\
       --credit-cost 1.0
   ```

2. **Import in your Django app:**
   ```python
   # Add to your app's __init__.py or apps.py
   from services.${service_name} import ${service_class_name}
   ```

## Usage

### Basic Usage

```python
from services.decorators import create_service_instance
from django.contrib.auth import get_user_model

User = get_user_model()

def use_service(user, input_data):
    service = create_service_instance("${service_name}")
    
    # Check credits
    credit_check = service.check_user_credits(user)
    if not credit_check['has_sufficient_credits']:
        return {'error': 'Insufficient credits'}
    
    # Run service
    try:
        result = service.run(user, input_data=input_data)
        return result
    except Exception as e:
        return {'error': str(e)}
```

### Error Handling

```python
from credits.exceptions import InsufficientCreditsError

try:
    result = service.run(user, input_data="your data")
    print("Success:", result['result'])
except InsufficientCreditsError as e:
    print("Need more credits:", str(e))
except ValueError as e:
    print("Invalid input:", str(e))
except Exception as e:
    print("Service error:", str(e))
```

## Configuration

Service configuration is managed through the Django admin or management commands:

```bash
# List all services
python manage.py configure_service --list

# Update service
python manage.py configure_service ${service_name} \\
    --description "Updated description" \\
    --credit-cost 2.0 \\
    --update

# Deactivate service
python manage.py configure_service ${service_name} --inactive --update
```

## Development

### Testing

Create tests in `tests/test_${service_name}.py`:

```python
from django.test import TestCase
from services.decorators import create_service_instance
from credits.models import CreditAccount, Service

class ${service_class_name}Tests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com")
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Ensure service is configured
        Service.objects.get_or_create(
            name="${service_name}",
            defaults={'credit_cost': 1.0, 'is_active': True}
        )
    
    def test_service_execution(self):
        self.credit_account.add_credits(10.0)
        
        service = create_service_instance("${service_name}")
        result = service.run(self.user, input_data="test")
        
        self.assertTrue(result['success'])
        self.assertIn('result', result)
```

### Validation

Validate your service implementation:

```bash
quickscale validate-service services/${service_name}.py --tips
```

## TODO

- [ ] Implement core service logic
- [ ] Add comprehensive input validation
- [ ] Add error handling for edge cases
- [ ] Write unit tests
- [ ] Add performance optimizations
- [ ] Add monitoring and logging
- [ ] Update documentation with actual functionality
""" 