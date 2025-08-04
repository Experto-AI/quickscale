# API Authentication

## Overview

QuickScale provides a secure API key authentication system for programmatic access to generated project APIs. The system integrates with the credit system and provides role-based access control.

## API Key System

### Key Format
API keys follow a structured format for security and usability:
- **Format**: `qs_xxxx_yyyyyyyyyyyyyyyyyyyyyyyyyyyy`
- **Prefix**: 4-character identifier (`qs_xxxx`)
- **Secret**: 32-character cryptographic secret
- **Example**: `qs_test_a1b2c3d4e5f6789012345678901234567890`

### Security Features
- **Cryptographic Hashing**: Keys stored using Django's password hasher
- **Prefix Identification**: Quick key type identification without exposing secrets
- **Secure Generation**: Cryptographically secure random generation
- **No Plain Text Storage**: Only hashed versions stored in database

## Authentication Implementation

### Middleware
The API authentication middleware processes all API requests:

```python
class APIKeyAuthenticationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/api/'):
            api_key = self.extract_api_key(request)
            if api_key:
                try:
                    user = self.authenticate_api_key(api_key)
                    request.user = user
                    request.api_authenticated = True
                except AuthenticationError:
                    return JsonResponse({'error': 'Invalid API key'}, status=401)
            else:
                return JsonResponse({'error': 'API key required'}, status=401)
        
        return self.get_response(request)
```

### Key Extraction
API keys can be provided via:
1. **Authorization Header**: `Authorization: Bearer qs_test_...`
2. **Custom Header**: `X-API-Key: qs_test_...`
3. **Query Parameter**: `?api_key=qs_test_...` (not recommended for production)

## Database Models

### APIKey Model
```python
class APIKey(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=8, unique=True)
    key_hash = models.CharField(max_length=128)
    is_active = models.BooleanField(default=True)
    last_used = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    # Usage tracking
    total_requests = models.PositiveIntegerField(default=0)
    
    # Permissions and limitations
    rate_limit_per_minute = models.PositiveIntegerField(default=60)
    allowed_endpoints = models.JSONField(default=list, blank=True)
    
    class Meta:
        verbose_name = "API Key"
        verbose_name_plural = "API Keys"
```

### Key Generation
```python
import secrets
import string
from django.contrib.auth.hashers import make_password

class APIKeyManager:
    @staticmethod
    def generate_api_key(user, name, rate_limit=60):
        # Generate prefix
        prefix = 'qs_' + ''.join(secrets.choice(string.ascii_lowercase) 
                                for _ in range(4))
        
        # Generate secret
        secret = ''.join(secrets.choice(string.ascii_letters + string.digits) 
                        for _ in range(32))
        
        # Full key
        full_key = f"{prefix}_{secret}"
        
        # Create database record
        api_key = APIKey.objects.create(
            user=user,
            name=name,
            prefix=prefix,
            key_hash=make_password(full_key),
            rate_limit_per_minute=rate_limit
        )
        
        return full_key, api_key
```

## Admin Interface

### Management Features
The Django admin provides comprehensive API key management:

#### Key Overview
- **Active Keys**: List of all active API keys
- **Usage Statistics**: Request counts and last usage
- **User Association**: Which user owns each key
- **Rate Limits**: Current rate limiting settings

#### Key Operations
- **Generate New Key**: Create API keys for users
- **Revoke Keys**: Deactivate compromised or unused keys
- **Update Permissions**: Modify allowed endpoints
- **View Usage**: Detailed usage analytics

#### Bulk Operations
- **Bulk Revocation**: Deactivate multiple keys
- **Usage Reports**: Export usage data
- **Security Audit**: Review key access patterns

### Admin Actions
```python
@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    list_display = ['prefix', 'user', 'name', 'is_active', 'last_used', 'total_requests']
    list_filter = ['is_active', 'created_at', 'last_used']
    search_fields = ['user__email', 'name', 'prefix']
    readonly_fields = ['prefix', 'key_hash', 'created_at', 'last_used', 'total_requests']
    
    actions = ['revoke_keys', 'reset_usage_counters']
    
    def revoke_keys(self, request, queryset):
        queryset.update(is_active=False)
    
    def reset_usage_counters(self, request, queryset):
        queryset.update(total_requests=0, last_used=None)
```

## Rate Limiting

### Implementation
```python
from django.core.cache import cache
from django.http import JsonResponse

class RateLimitMiddleware:
    def process_api_request(self, request, api_key_obj):
        # Create rate limit key
        rate_key = f"rate_limit:{api_key_obj.prefix}:{self.get_current_minute()}"
        
        # Get current count
        current_count = cache.get(rate_key, 0)
        
        # Check limit
        if current_count >= api_key_obj.rate_limit_per_minute:
            return JsonResponse({
                'error': 'Rate limit exceeded',
                'limit': api_key_obj.rate_limit_per_minute,
                'window': '1 minute'
            }, status=429)
        
        # Increment counter
        cache.set(rate_key, current_count + 1, 60)  # 60 second expiry
        
        return None  # Allow request
```

### Rate Limit Headers
API responses include rate limiting information:
```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 45
X-RateLimit-Reset: 1640995200
```

## Endpoint Protection

### Protected Endpoints
All API endpoints under `/api/` require authentication:

```python
# API views automatically protected
urlpatterns = [
    path('api/v1/credits/', CreditAPIView.as_view()),
    path('api/v1/usage/', UsageAPIView.as_view()),
    path('api/v1/services/', ServiceAPIView.as_view()),
]
```

### Permission Decorators
```python
from functools import wraps
from django.http import JsonResponse

def require_api_key(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not getattr(request, 'api_authenticated', False):
            return JsonResponse({'error': 'API authentication required'}, status=401)
        return view_func(request, *args, **kwargs)
    return wrapper

# Usage
@require_api_key
def api_endpoint(request):
    # Authenticated API logic
    pass
```

## Integration with Credit System

### Credit Consumption via API
```python
from credits.services import CreditService

class AIGenerationAPIView(APIView):
    def post(self, request):
        # Calculate credit cost
        prompt = request.data.get('prompt')
        cost = self.calculate_cost(prompt)
        
        # Consume credits
        try:
            CreditService.consume_credits(
                user=request.user,
                amount=cost,
                service="ai_generation_api",
                metadata={
                    "api_key": request.api_key.prefix,
                    "endpoint": "generation",
                    "prompt_length": len(prompt)
                }
            )
        except InsufficientCreditsError:
            return JsonResponse({'error': 'Insufficient credits'}, status=402)
        
        # Process request
        result = self.generate_content(prompt)
        return JsonResponse({'result': result})
```

## Security Best Practices

### Key Management
- **Rotation**: Regular key rotation recommendations
- **Scope Limitation**: Principle of least privilege
- **Monitoring**: Unusual usage pattern detection
- **Revocation**: Immediate revocation capabilities

### Transport Security
- **HTTPS Only**: All API communication over HTTPS
- **No URL Parameters**: Avoid API keys in URLs for production
- **Header Validation**: Strict header format validation
- **Request Logging**: Comprehensive audit logging

### Error Handling
- **Generic Errors**: No sensitive information in error messages
- **Rate Limiting**: Prevent brute force attacks
- **Audit Logging**: Log all authentication attempts
- **Alerting**: Monitor for suspicious activity

## Usage Examples

### Python Client
```python
import requests

class QuickScaleClient:
    def __init__(self, api_key, base_url):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    def check_credits(self):
        response = self.session.get(f"{self.base_url}/api/v1/credits/balance/")
        return response.json()
    
    def generate_content(self, prompt):
        data = {'prompt': prompt}
        response = self.session.post(f"{self.base_url}/api/v1/ai/generate/", json=data)
        return response.json()
```

### cURL Examples
```bash
# Check credit balance
curl -H "Authorization: Bearer qs_test_abcd1234567890..." \
     https://your-app.com/api/v1/credits/balance/

# Generate content
curl -H "Authorization: Bearer qs_test_abcd1234567890..." \
     -H "Content-Type: application/json" \
     -d '{"prompt": "Generate a product description"}' \
     https://your-app.com/api/v1/ai/generate/
```

This API authentication system provides secure, scalable access control for QuickScale-generated applications while integrating seamlessly with the credit and billing systems.
