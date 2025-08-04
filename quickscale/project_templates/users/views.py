from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django import forms
from django.core.exceptions import ValidationError
from .forms import ProfileForm
from .models import AccountLockout
from credits.models import APIKey

User = get_user_model()

@login_required
def account_security_view(request: HttpRequest) -> HttpResponse:
    """Unified account security page: API Keys and 2FA."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    # API Keys
    api_keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
    # 2FA context
    from django.conf import settings
    two_factor_enabled = getattr(settings, 'TWO_FACTOR_AUTH_ENABLED', False)
    two_factor = None
    is_2fa_enabled = False
    has_backup_codes = False
    backup_codes_count = 0
    issuer_name = getattr(settings, 'TWO_FACTOR_AUTH_ISSUER', 'QuickScale')
    if two_factor_enabled:
        from users.models import TwoFactorAuth
        two_factor, _ = TwoFactorAuth.objects.get_or_create(user=request.user)
        is_2fa_enabled = two_factor.is_enabled
        has_backup_codes = bool(two_factor.backup_codes)
        backup_codes_count = len(two_factor.backup_codes) if two_factor.backup_codes else 0
    context = {
        'api_keys': api_keys,
        'two_factor_enabled': two_factor_enabled,
        'two_factor': two_factor,
        'is_2fa_enabled': is_2fa_enabled,
        'has_backup_codes': has_backup_codes,
        'backup_codes_count': backup_codes_count,
        'issuer_name': issuer_name,
        'is_htmx': is_htmx,
    }
    return render(request, 'users/account_security.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def profile_view(request: HttpRequest) -> HttpResponse:
    """Display and update user profile."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully!')
            
            if is_htmx:
                # Return the updated profile form for HTMX
                return render(request, 'users/profile_form.html', {
                    'form': form,
                    'is_htmx': is_htmx
                })
            return redirect('users:profile')
        else:
            # Form has errors
            if is_htmx:
                return render(request, 'users/profile_form.html', {
                    'form': form,
                    'is_htmx': is_htmx
                })
    else:
        form = ProfileForm(instance=request.user)
    
    return render(request, 'users/profile.html', {
        'form': form,
        'is_htmx': is_htmx
    })

@login_required
@require_http_methods(["GET"])


@login_required
@csrf_protect
@require_http_methods(["POST"])
def generate_api_key_view(request: HttpRequest) -> HttpResponse:
    """Generate a new API key for the user with proper error handling."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    try:
        # Get the optional name for the API key
        name = request.POST.get('name', '').strip()
        # Generate the API key
        full_key, prefix, secret_key = APIKey.generate_key()
        # Create the API key record
        api_key = APIKey.objects.create(
            user=request.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret_key),
            name=name
        )
        messages.success(request, 'API key generated successfully!')
        if is_htmx:
            # Return only the partial for HTMX requests
            return render(request, 'users/_api_key_generated_partial.html', {
                'api_key': api_key,
                'full_key': full_key,
                'is_htmx': is_htmx
            })
        # Return full page for normal requests
        return render(request, 'users/api_key_generated.html', {
            'api_key': api_key,
            'full_key': full_key,
            'is_htmx': is_htmx
        })
    except ValidationError as e:
        messages.error(request, f'Validation error: {str(e)}')
    except Exception as e:
        messages.error(request, f'Error generating API key: {str(e)}')
    if is_htmx:
        return render(request, 'users/api_keys.html', {
            'api_keys': APIKey.objects.filter(user=request.user).order_by('-created_at'),
            'is_htmx': is_htmx
        })
    return redirect('users:api_keys')
@login_required
@require_http_methods(["GET"])
def api_keys_list_partial(request: HttpRequest) -> HttpResponse:
    """Return only the API keys list partial for HTMX refresh."""
    api_keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'users/api_keys_list_partial.html', {
        'api_keys': api_keys
    })

@login_required
@csrf_protect
@require_http_methods(["POST"])
def revoke_api_key_view(request: HttpRequest) -> HttpResponse:
    """Revoke an API key with proper error handling."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    try:
        api_key_id = request.POST.get('api_key_id')
        if not api_key_id:
            raise ValidationError('API key ID is required.')
            
        api_key = get_object_or_404(APIKey, id=api_key_id, user=request.user)
        
        api_key.is_active = False
        api_key.save()
        
        messages.success(request, 'API key revoked successfully!')
        
    except ValidationError as e:
        messages.error(request, f'Validation error: {str(e)}')
    except Exception as e:
        messages.error(request, f'Error revoking API key: {str(e)}')
    
    if is_htmx:
        return render(request, 'users/api_keys.html', {
            'api_keys': APIKey.objects.filter(user=request.user).order_by('-created_at'),
            'is_htmx': is_htmx
        })
    
    return redirect('users:api_keys')

@login_required
@csrf_protect
@require_http_methods(["POST"])
def regenerate_api_key_view(request: HttpRequest) -> HttpResponse:
    """Regenerate an existing API key with proper error handling."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    try:
        api_key_id = request.POST.get('api_key_id')
        if not api_key_id:
            raise ValidationError('API key ID is required.')
            
        old_api_key = get_object_or_404(APIKey, id=api_key_id, user=request.user)
        
        # Revoke the old key
        old_api_key.is_active = False
        old_api_key.save()
        
        # Generate new key
        full_key, prefix, secret_key = APIKey.generate_key()
        
        # Create new API key record
        new_api_key = APIKey.objects.create(
            user=request.user,
            prefix=prefix,
            hashed_key=APIKey.get_hashed_key(secret_key),
            name=old_api_key.name
        )
        
        messages.success(request, 'API key regenerated successfully!')
        
        return render(request, 'users/api_key_generated.html', {
            'api_key': new_api_key,
            'full_key': full_key,
            'is_htmx': is_htmx
        })
        
    except ValidationError as e:
        messages.error(request, f'Validation error: {str(e)}')
    except Exception as e:
        messages.error(request, f'Error regenerating API key: {str(e)}')
        
    if is_htmx:
        return render(request, 'users/api_keys.html', {
            'api_keys': APIKey.objects.filter(user=request.user).order_by('-created_at'),
            'is_htmx': is_htmx
        })
    
    return redirect('users:api_keys')