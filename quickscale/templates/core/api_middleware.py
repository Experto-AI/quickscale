"""API authentication middleware for QuickScale."""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
import logging
from django.contrib.auth.models import AnonymousUser

logger = logging.getLogger(__name__)


class APIKeyAuthenticationMiddleware(MiddlewareMixin):
    """Middleware to authenticate API requests using API keys."""

    def process_request(self, request):
        """Process API requests and validate API keys."""
        # Only apply to /api/ routes
        if not request.path.startswith('/api/'):
            return None

        logger.debug(f"APIKeyAuthenticationMiddleware processing path: {request.path}")

        # Allow /api/docs/ to be accessed without API key
        if request.path == '/api/docs/':
            # Attach a dummy user to allow AllowAny to work for documentation
            request.user = AnonymousUser()
            request.api_authenticated = False # Explicitly set to False as no API key was used
            return None

        # Extract API key from Authorization header
        api_key_data = self._extract_api_key(request)
        
        if not api_key_data:
            logger.debug("API key not provided or malformed")
            return JsonResponse({
                'error': 'API key required',
                'message': 'Please provide a valid API key in the Authorization header as "Bearer <prefix.secret-key>"'
            }, status=401)

        # Validate API key
        try:
            user = self._validate_api_key(api_key_data)
        except Exception as e:
            # Only catch exceptions during development/testing
            # In production, let unexpected errors bubble up to error handlers
            from django.conf import settings
            if settings.DEBUG:
                logger.error(f"APIKeyAuthenticationMiddleware: Unexpected error in process_request: {e}", exc_info=True)
                return JsonResponse({
                    'error': 'Internal server error',
                    'message': 'An unexpected error occurred during authentication'
                }, status=500)
            else:
                # In production, re-raise to let proper error handling deal with it
                raise
        
        if not user:
            return JsonResponse({
                'error': 'Invalid API key',
                'message': 'The provided API key is invalid or inactive'
            }, status=401)

        # Attach user to request for API views
        request.user = user
        request.api_authenticated = True
        
        return None

    def _extract_api_key(self, request):
        """Extract API key from Authorization header and parse prefix.secret format."""
        auth_header = request.META.get('HTTP_AUTHORIZATION', '')
        
        if not auth_header:
            return None
            
        if not auth_header.startswith('Bearer '):
            logger.debug("Authorization header does not use Bearer format")
            return None
            
        full_key = auth_header[7:]  # Remove 'Bearer ' prefix
        
        # Parse prefix.secret_key format
        if '.' not in full_key:
            logger.debug("API key missing required '.' separator")
            return None
            
        prefix, secret_key = full_key.split('.', 1)
        return {'full_key': full_key, 'prefix': prefix, 'secret_key': secret_key}

    def _validate_api_key(self, api_key_data):
        """Validate the API key using secure hash comparison and return associated user."""
        from credits.models import APIKey
        
        prefix = api_key_data['prefix']
        secret_key = api_key_data['secret_key']
        
        try:
            # Find API key by prefix
            api_key_obj = APIKey.objects.select_related('user').get(
                prefix=prefix,
                is_active=True
            )
        except APIKey.DoesNotExist:
            logger.warning(f"API key not found for prefix: {prefix}")
            return None
        
        # Check if API key is expired
        if api_key_obj.is_expired:
            logger.warning(f"Expired API key attempt: {prefix}")
            return None
        
        # Verify secret key using secure hash comparison
        if not api_key_obj.verify_secret_key(secret_key):
            logger.warning(f"Invalid secret key attempt for prefix: {prefix}")
            return None
        
        # Update last used timestamp
        api_key_obj.update_last_used()
        
        return api_key_obj.user