# API Authentication & Basic Endpoints - Test Suite

This document describes the comprehensive test suite for Sprint 11's API Authentication & Basic Endpoints implementation.

## Test Files Overview

### 1. `test_api_key_model.py`
Tests the APIKey model functionality including:
- **Secure key generation**: Validates 4-char prefix + 32-char secret format
- **Cryptographic hashing**: Tests Django password hasher integration
- **Key verification**: Tests secure secret key validation
- **Expiration handling**: Tests key expiry logic and `is_valid` property
- **Prefix uniqueness**: Validates uniqueness across multiple generations
- **Model validation**: Tests field constraints and default values
- **Usage tracking**: Tests `update_last_used()` functionality
- **Multi-key support**: Tests users having multiple API keys

### 2. `test_api_middleware.py`
Tests the APIKeyAuthenticationMiddleware including:
- **Valid authentication**: Tests successful API key authentication flow
- **Invalid key formats**: Tests rejection of malformed authorization headers
- **Expired keys**: Tests rejection of expired API keys
- **Deactivated keys**: Tests rejection of inactive API keys
- **Route scoping**: Tests middleware only applies to `/api/` routes
- **Header parsing**: Tests Bearer token format parsing
- **Nonexistent keys**: Tests handling of keys not in database
- **Wrong secrets**: Tests rejection when prefix exists but secret is wrong
- **Error logging**: Tests proper logging of authentication failures
- **Exception handling**: Tests graceful handling of database errors

### 3. `test_api_endpoints.py`
Tests the Text Processing API endpoints including:
- **Text operations**: Tests all 4 operations (count_words, count_characters, analyze, summarize)
- **Credit consumption**: Tests proper credit deduction for each operation
- **Insufficient credits**: Tests 402 Payment Required responses
- **Authentication required**: Tests 401 Unauthorized for missing auth
- **Input validation**: Tests validation of required fields and text length
- **JSON format**: Tests JSON request/response handling
- **Content type**: Tests content-type validation
- **Endpoint info**: Tests GET requests for API documentation
- **Service tracking**: Tests ServiceUsage record creation
- **Concurrent usage**: Tests credit consumption under concurrent requests
- **Request logging**: Tests successful request logging

### 4. `test_api_key_management.py`
Tests the frontend API key management interface including:
- **Key listing**: Tests web interface for viewing user's API keys
- **Key creation**: Tests API key creation through web forms
- **Duplicate names**: Tests handling of duplicate key names
- **Missing names**: Tests optional name field handling
- **Key deactivation**: Tests deactivating keys via web interface
- **Key deletion**: Tests deleting keys via web interface
- **Authorization**: Tests that management requires user authentication
- **User isolation**: Tests users only see their own keys
- **Usage statistics**: Tests display of key usage information
- **Security**: Tests that sensitive data is not exposed in responses
- **Response format**: Tests consistent JSON response structure
- **Rate limiting**: Tests reasonable limits on key creation
- **Error handling**: Tests graceful handling of key generation failures
- **Expiry display**: Tests proper display of key expiration information

### 5. `test_api_integration.py`
Tests complete end-to-end workflows including:
- **Complete workflow**: Tests key creation → authentication → API usage → tracking
- **Credit depletion**: Tests behavior when user runs out of credits
- **Key lifecycle**: Tests full API key management lifecycle
- **Concurrent usage**: Tests concurrent API requests with credit limits
- **Authentication edge cases**: Tests various authentication failure scenarios
- **Key expiry workflow**: Tests behavior when keys expire during usage
- **Endpoint info**: Tests API documentation retrieval
- **Error handling**: Tests comprehensive error scenarios and logging
- **Request logging**: Tests that successful requests are properly logged

## Test Coverage Areas

### Security Testing
- ✅ Cryptographic key generation and hashing
- ✅ Secure authentication flow validation
- ✅ Proper authorization header parsing
- ✅ User isolation and access control
- ✅ Sensitive data protection in responses

### Business Logic Testing
- ✅ Credit consumption and balance management
- ✅ Service usage tracking and history
- ✅ API operation validation and processing
- ✅ Insufficient credits handling
- ✅ Concurrent request handling

### Integration Testing
- ✅ End-to-end user workflows
- ✅ Database transaction integrity
- ✅ Middleware and view layer interaction
- ✅ Authentication and authorization flow
- ✅ Error handling and logging

### Edge Case Testing
- ✅ Malformed authentication headers
- ✅ Expired and inactive API keys
- ✅ Invalid JSON and content types
- ✅ Text length boundary conditions
- ✅ Database error scenarios

## Running the Tests

### Run All API Tests
```bash
python manage.py test tests.test_api_key_model tests.test_api_middleware tests.test_api_endpoints tests.test_api_key_management tests.test_api_integration
```

### Run Individual Test Categories
```bash
# API Key Model Tests
python manage.py test tests.test_api_key_model

# Middleware Tests
python manage.py test tests.test_api_middleware

# Endpoint Tests
python manage.py test tests.test_api_endpoints

# Management Interface Tests
python manage.py test tests.test_api_key_management

# Integration Tests
python manage.py test tests.test_api_integration
```

### Run with Coverage
```bash
coverage run --source='.' manage.py test tests.test_api_*
coverage report
coverage html
```

## Test Dependencies

### Required Models
- `User` (Django auth)
- `APIKey` (credits.models)
- `CreditAccount` (credits.models)
- `CreditTransaction` (credits.models)
- `Service` (credits.models)
- `ServiceUsage` (credits.models)

### Required Middleware
- `APIKeyAuthenticationMiddleware` (core.api_middleware)

### Required Views
- `TextProcessingView` (api.views)
- API key management views (credits.api_views - if implemented)

### Required URLs
- `/api/v1/text/process/` - Text processing endpoint
- `/dashboard/credits/api/auth/keys/` - API key management endpoints

## Test Data Patterns

### User Creation
```python
self.user = User.objects.create_user(
    email='testuser@example.com',
    password='testpass123'
)
```

### API Key Creation
```python
full_key, prefix, secret = APIKey.generate_key()
api_key = APIKey.objects.create(
    user=self.user,
    prefix=prefix,
    hashed_key=APIKey.get_hashed_key(secret),
    name='Test Key'
)
```

### Credit Account Setup
```python
credit_account = CreditAccount.get_or_create_for_user(self.user)
credit_account.add_credits(
    amount=Decimal('10.0'),
    description='Test credits',
    credit_type='ADMIN'
)
```

### Authenticated API Request
```python
response = self.client.post(
    '/api/v1/text/process/',
    data=json.dumps({'text': 'test', 'operation': 'count_words'}),
    content_type='application/json',
    HTTP_AUTHORIZATION=f'Bearer {full_key}'
)
```

## Implementation Notes

### Following CONTRIBUTING.md Guidelines
- ✅ **Implementation-first testing**: Tests written after Sprint 11 implementation
- ✅ **Behavior focus**: Tests verify observable behavior, not implementation details
- ✅ **Arrange-Act-Assert**: Clear test structure with explicit sections
- ✅ **Mocking**: External dependencies mocked for isolation
- ✅ **Edge cases**: Comprehensive boundary and error condition testing
- ✅ **Fixtures**: Reusable test data setup in setUp() methods

### Test Organization
- Each test file focuses on a specific component or layer
- Integration tests cover end-to-end workflows
- Subtests used for parameterized testing scenarios
- Clear test method names describe the behavior being tested
- Comprehensive docstrings explain test purpose and expectations

### Error Scenarios Covered
- Invalid authentication credentials
- Malformed request data
- Insufficient credits for operations
- Database connection failures
- Key generation failures
- Concurrent access scenarios
- Rate limiting conditions
- Network and timeout scenarios

This test suite provides comprehensive coverage of the API Authentication & Basic Endpoints feature, ensuring reliability, security, and proper functionality across all components.