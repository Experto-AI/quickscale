"""API authentication middleware for QuickScale."""
from django.http import JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class APIKeyAuthenticationMiddleware(MiddlewareMixin):
    """Middleware to authenticate API requests using API keys."""

    def process_request(self, request):
        """Process API requests and validate API keys."""
        # Only apply to /api/ routes
        if not request.path.startswith('/api/'):
            return None

        # Extract API key from Authorization header
        api_key_data = self._extract_api_key(request)
        
        if not api_key_data:
            return JsonResponse({
                'error': 'API key required',
                'message': 'Please provide a valid API key in the Authorization header as "Bearer <prefix.secret-key>"'
            }, status=401)

        # Validate API key
        user = self._validate_api_key(api_key_data)
        
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
        
        if auth_header.startswith('Bearer '):
            full_key = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Parse prefix.secret_key format
            if '.' in full_key:
                prefix, secret_key = full_key.split('.', 1)
                return {'full_key': full_key, 'prefix': prefix, 'secret_key': secret_key}
            
        return None

    def _validate_api_key(self, api_key_data):
        """Validate the API key using secure hash comparison and return associated user."""
        try:
            from credits.models import APIKey
            
            prefix = api_key_data['prefix']
            secret_key = api_key_data['secret_key']
            full_key = api_key_data['full_key']
            
            # Find API key by prefix
            api_key_obj = APIKey.objects.select_related('user').get(
                prefix=prefix,
                is_active=True
            )
            
            # Check if API key is expired
            if api_key_obj.is_expired:
                logger.warning(f"Expired API key attempt: {prefix}...")
                return None
            
            # Verify secret key using secure hash comparison
            if not api_key_obj.verify_secret_key(secret_key):
                logger.warning(f"Invalid secret key attempt for prefix: {prefix}")
                return None
            
            # Update last used timestamp
            api_key_obj.update_last_used()
            
            return api_key_obj.user
            
        except APIKey.DoesNotExist:
            logger.warning(f"API key not found for prefix: {api_key_data.get('prefix', 'unknown')}")
            return None
        except KeyError:
            logger.warning("Malformed API key data")
            return None
        except Exception as e:
            logger.error(f"Error validating API key: {e}")
            return None