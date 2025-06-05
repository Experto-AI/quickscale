"""Views for API key management interface."""
import json
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.contrib.auth.decorators import login_required
from .models import APIKey


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class APIKeyListView(View):
    """View for listing and managing API keys."""

    def get(self, request):
        """List user's API keys."""
        api_keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
        
        keys_data = []
        for key in api_keys:
            keys_data.append({
                'id': key.id,
                'name': key.name or 'Unnamed Key',
                'prefix': key.prefix,
                'is_active': key.is_active,
                'created_at': key.created_at.isoformat(),
                'last_used_at': key.last_used_at.isoformat() if key.last_used_at else None,
                'expiry_date': key.expiry_date.isoformat() if key.expiry_date else None
            })
        
        return JsonResponse({
            'success': True,
            'data': {
                'api_keys': keys_data,
                'total_count': len(keys_data)
            }
        })


@method_decorator(csrf_exempt, name='dispatch')
@method_decorator(login_required, name='dispatch')
class APIKeyCreateView(View):
    """View for creating new API keys."""

    def post(self, request):
        """Create a new API key."""
        try:
            data = json.loads(request.body) if request.body else {}
            name = data.get('name', '')
            
            # Check for duplicate names if name is provided
            if name:
                existing_key = APIKey.objects.filter(user=request.user, name=name).first()
                if existing_key:
                    return JsonResponse({
                        'success': False,
                        'error': 'Duplicate name',
                        'details': {'name': 'API key with this name already exists'}
                    }, status=400)
            
            # Generate new API key
            full_key, prefix, secret_key = APIKey.generate_key()
            hashed_key = APIKey.get_hashed_key(secret_key)
            
            # Create API key record
            api_key = APIKey.objects.create(
                user=request.user,
                prefix=prefix,
                hashed_key=hashed_key,
                name=name
            )
            
            return JsonResponse({
                'success': True,
                'status': 'created',
                'data': {
                    'api_key': api_key.id,
                    'prefix': api_key.prefix,
                    'secret_key': secret_key,
                    'full_key': full_key,
                    'name': api_key.name or 'Unnamed Key',
                    'is_active': api_key.is_active,
                    'created_at': api_key.created_at.isoformat()
                }
            }, status=201)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON',
                'details': {'error': 'Invalid JSON format'}
            }, status=400)
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': 'Internal server error',
                'details': {'error': str(e)}
            }, status=500)