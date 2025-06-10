# QuickScale AI Service Development Guide

Welcome to QuickScale AI Service Development! This guide will help you create powerful AI services that integrate seamlessly with the credit system and provide great user experiences.

## Quick Start

### 1. Generate a New Service

```bash
# Basic service template
quickscale generate-service my_ai_service

# Text processing service  
quickscale generate-service sentiment_analyzer --type text_processing

# Image processing service
quickscale generate-service image_classifier --type image_processing
```

### 2. Implement Your Service Logic

```python
@register_service("my_service_name")
class MyAIService(BaseService):
    """Your AI service description."""
    
    def execute_service(self, user: User, **kwargs):
        """Implement your AI logic here."""
        # 1. Validate inputs
        # 2. Process with your AI model/API
        # 3. Return structured results
        return {"result": "your_output"}
```

### 3. Configure Service in Database

```python
# In Django admin or management command
from credits.models import Service

Service.objects.create(
    name="my_service_name",
    description="Description of what your service does",
    credit_cost=1.0,  # How many credits this service costs
    is_active=True
)
```

### 4. Use Your Service

```python
from services.decorators import create_service_instance

service = create_service_instance("my_service_name")
result = service.run(user, input_data="your input")
```

## Service Framework Architecture

### BaseService Class

All services inherit from `BaseService` which provides:

- **Credit consumption**: Automatic credit deduction
- **Usage tracking**: Complete audit trail
- **Error handling**: Consistent error patterns
- **Validation**: Pre-flight credit checks

### Service Registry

The `@register_service` decorator automatically registers your service:

```python
@register_service("service_name")
class MyService(BaseService):
    pass

# Service is now available via:
service = create_service_instance("service_name")
```

### Credit System Integration

Services automatically integrate with the credit system:

1. **Pre-flight check**: `service.check_user_credits(user)`
2. **Credit consumption**: `service.consume_credits(user)`
3. **Usage recording**: Automatic `ServiceUsage` creation
4. **Priority system**: Subscription credits used first

## Best Practices

### 1. Input Validation

Always validate inputs early and provide clear error messages:

```python
def execute_service(self, user: User, text: str = "", **kwargs):
    if not text or not text.strip():
        raise ValueError("Text input is required and cannot be empty")
    
    if len(text) > 10000:
        raise ValueError("Text input too long (max 10,000 characters)")
```

### 2. Error Handling

Handle different types of errors appropriately:

```python
def execute_service(self, user: User, **kwargs):
    try:
        # Your AI processing here
        result = process_with_ai(kwargs['input'])
        return result
    except ValidationError as e:
        # Re-raise validation errors
        raise ValueError(f"Invalid input: {str(e)}")
    except ExternalAPIError as e:
        # Handle external service failures
        raise RuntimeError(f"AI service temporarily unavailable: {str(e)}")
    except Exception as e:
        # Log unexpected errors but don't expose internals
        logger.error(f"Unexpected error in {self.service_name}: {str(e)}")
        raise RuntimeError("Service processing failed")
```

### 3. Performance Optimization

- **Cache expensive operations**: Use Django's cache framework
- **Async processing**: For long-running tasks, consider Celery
- **Batch processing**: Group multiple items when possible
- **Connection pooling**: Reuse HTTP connections for external APIs

```python
from django.core.cache import cache

def execute_service(self, user: User, input_data: str, **kwargs):
    # Check cache first
    cache_key = f"service_result_{hash(input_data)}"
    cached_result = cache.get(cache_key)
    
    if cached_result:
        return cached_result
    
    # Process and cache result
    result = expensive_ai_processing(input_data)
    cache.set(cache_key, result, timeout=300)  # 5 minutes
    
    return result
```

### 4. External API Integration

When integrating with external AI services:

```python
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class ExternalAIService(BaseService):
    def __init__(self, service_name: str):
        super().__init__(service_name)
        # Configure session with retries
        self.session = requests.Session()
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
    
    def execute_service(self, user: User, **kwargs):
        try:
            response = self.session.post(
                "https://api.example.com/ai",
                json=kwargs,
                timeout=30
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"External AI service error: {str(e)}")
```

## Service Types and Examples

### Text Processing Services

Perfect for:
- Sentiment analysis
- Text summarization  
- Language detection
- Content classification
- Keyword extraction

```python
@register_service("sentiment_analysis")
class SentimentAnalysisService(BaseService):
    def execute_service(self, user: User, text: str = "", **kwargs):
        # Implement sentiment analysis logic
        return {
            "sentiment": "positive|negative|neutral",
            "confidence": 0.95,
            "details": {...}
        }
```

### Image Processing Services

Perfect for:
- Image classification
- Object detection
- Face recognition
- OCR (text extraction)
- Image enhancement

```python
@register_service("image_classifier")
class ImageClassifierService(BaseService):
    def execute_service(self, user: User, image_data: bytes = None, **kwargs):
        # Implement image classification logic
        return {
            "predictions": [
                {"class": "cat", "confidence": 0.89},
                {"class": "dog", "confidence": 0.11}
            ],
            "metadata": {...}
        }
```

### Data Processing Services

Perfect for:
- Data validation
- Format conversion
- Data enrichment
- Duplicate detection
- Quality scoring

## Advanced Patterns

### Service Chaining

Chain multiple services together:

```python
def text_analysis_pipeline(user, text):
    # Step 1: Validate
    validator = create_service_instance("data_validator")
    validation = validator.run(user, data=text, data_type="text")
    
    if not validation['result']['validation']['is_valid']:
        return {"error": "Validation failed", "details": validation}
    
    # Step 2: Extract keywords
    extractor = create_service_instance("keyword_extractor")
    keywords = extractor.run(user, text=text)
    
    # Step 3: Analyze sentiment
    sentiment = create_service_instance("sentiment_analyzer")
    sentiment_result = sentiment.run(user, text=text)
    
    return {
        "pipeline_result": {
            "validation": validation['result'],
            "keywords": keywords['result'],
            "sentiment": sentiment_result['result']
        },
        "total_credits": sum([
            validation['credits_consumed'],
            keywords['credits_consumed'], 
            sentiment_result['credits_consumed']
        ])
    }
```

### Batch Processing

Process multiple items efficiently:

```python
def batch_text_analysis(user, texts: List[str], service_name: str):
    service = create_service_instance(service_name)
    
    # Pre-check credits for entire batch
    credit_check = service.check_user_credits(user)
    total_needed = credit_check['required_credits'] * len(texts)
    
    if credit_check['available_credits'] < total_needed:
        return {"error": "Insufficient credits for batch"}
    
    results = []
    for text in texts:
        result = service.run(user, text=text)
        results.append(result['result'])
    
    return {"batch_results": results}
```

## Testing Your Services

### Unit Testing

```python
from django.test import TestCase
from django.contrib.auth import get_user_model
from services.decorators import create_service_instance
from credits.models import CreditAccount, Service

User = get_user_model()

class MyServiceTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="test@example.com")
        self.credit_account = CreditAccount.get_or_create_for_user(self.user)
        
        # Create service configuration
        self.service_config = Service.objects.create(
            name="my_service",
            credit_cost=1.0,
            is_active=True
        )
    
    def test_service_execution(self):
        # Add credits to user
        self.credit_account.add_credits(10.0)
        
        # Test service
        service = create_service_instance("my_service")
        result = service.run(self.user, input_data="test")
        
        self.assertTrue(result['success'])
        self.assertEqual(result['credits_consumed'], 1.0)
    
    def test_insufficient_credits(self):
        # No credits for user
        service = create_service_instance("my_service")
        
        with self.assertRaises(InsufficientCreditsError):
            service.run(self.user, input_data="test")
```

### Integration Testing

Test with real external services in development:

```python
def test_with_external_api(self):
    # Use test API keys or mock services
    service = create_service_instance("external_ai_service")
    
    # Test with known input/output
    result = service.run(self.user, test_input="known_test_case")
    self.assertIn("expected_field", result['result'])
```

## Deployment and Monitoring

### Configuration Management

Use environment variables for configuration:

```python
import os

class AIServiceConfig:
    API_KEY = os.getenv('AI_SERVICE_API_KEY')
    API_URL = os.getenv('AI_SERVICE_URL', 'https://api.default.com')
    TIMEOUT = int(os.getenv('AI_SERVICE_TIMEOUT', '30'))
```

### Logging and Monitoring

Add comprehensive logging:

```python
import logging

logger = logging.getLogger(__name__)

def execute_service(self, user: User, **kwargs):
    logger.info(f"Starting {self.service_name} for user {user.id}")
    
    try:
        result = process_ai_request(kwargs)
        logger.info(f"Completed {self.service_name} successfully")
        return result
    except Exception as e:
        logger.error(f"Error in {self.service_name}: {str(e)}")
        raise
```

### Performance Metrics

Track service performance:

```python
import time
from django.core.cache import cache

def execute_service(self, user: User, **kwargs):
    start_time = time.time()
    
    try:
        result = your_ai_processing(kwargs)
        
        # Track success metrics
        processing_time = time.time() - start_time
        cache.set(f"service_metrics_{self.service_name}_last_duration", processing_time)
        
        return result
    except Exception as e:
        # Track error metrics
        cache.incr(f"service_metrics_{self.service_name}_error_count", delta=1)
        raise
```

## Troubleshooting

### Common Issues

**Service not found**: Ensure `@register_service` decorator is used and the module is imported.

**Credits not consumed**: Check that you're using `service.run()` not just `service.execute_service()`.

**Performance issues**: Profile your code and consider caching, async processing, or optimization.

**External API failures**: Implement retry logic and graceful degradation.

### Debugging Commands

```bash
# Validate your service file
quickscale validate-service my_service.py --tips

# List registered services
quickscale list-services --details

# View service examples
quickscale service-examples --type text_processing
```

### Getting Help

1. **Check the examples**: `quickscale service-examples`
2. **Validate your code**: `quickscale validate-service your_file.py`
3. **Review logs**: Check Django logs for detailed error information
4. **Test in isolation**: Create unit tests to verify service behavior

## Next Steps

1. **Generate your first service**: `quickscale generate-service my_first_service`
2. **Configure in admin**: Add the service to the database
3. **Test thoroughly**: Write comprehensive tests
4. **Monitor performance**: Add logging and metrics
5. **Scale as needed**: Consider async processing for heavy workloads

Happy coding! 🚀 