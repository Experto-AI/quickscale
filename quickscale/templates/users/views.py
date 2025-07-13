"""User authentication and account management views."""
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_protect
from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.core.exceptions import ValidationError

from .forms import ProfileForm, EnhancedSignupForm, EnhancedLoginForm
from .models import AccountLockout
from .security_logger import log_login_failure
from credits.models import APIKey

User = get_user_model()

@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    """Handle user login with enhanced security and error handling."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if request.method == "POST":
        form = EnhancedLoginForm(data=request.POST)
        if form.is_valid():
            email = form.cleaned_data['username']  # username field contains email
            password = form.cleaned_data['password']
            
            # Check if user exists and get lockout status
            try:
                user_obj = User.objects.get(email=email)
                lockout, created = AccountLockout.objects.get_or_create(user=user_obj)
                
                # Check if account is locked
                if lockout.is_locked:
                    if not lockout.check_lockout_expired():
                        # Account is still locked
                        time_remaining = lockout.time_until_unlock
                        minutes_remaining = int(time_remaining.total_seconds() / 60) if time_remaining else 0
                        
                        form.add_error(None, f'Account locked due to too many failed attempts. Try again in {minutes_remaining} minutes.')
                        
                        # Log the blocked login attempt
                        log_login_failure(email, request, 'account_locked')
                        
                        if is_htmx:
                            return render(request, 'users/login_form.html', {'form': form, 'is_htmx': is_htmx})
                        return render(request, 'users/login.html', {'form': form, 'is_htmx': is_htmx})
                
                # Attempt authentication
                user = authenticate(request, email=email, password=password)
                
                if user is not None:
                    # Reset failed attempts on successful login
                    lockout.reset_failed_attempts()
                    login(request, user)
                    messages.success(request, 'Successfully logged in!')
                    
                    if is_htmx:
                        response = HttpResponse()
                        response['HX-Redirect'] = '/'
                        return response
                    return redirect('public:index')
                else:
                    # Failed login - increment attempts
                    is_now_locked = lockout.increment_failed_attempts(request)
                    
                    if is_now_locked:
                        form.add_error(None, 'Too many failed attempts. Your account has been temporarily locked.')
                    else:
                        remaining_attempts = 5 - lockout.failed_attempts  # Default max attempts
                        form.add_error(None, f'Invalid email or password. {remaining_attempts} attempts remaining.')
                    
            except User.DoesNotExist:
                # User doesn't exist - still show generic error and log the attempt
                form.add_error(None, 'Invalid email or password. Please try again.')
                log_login_failure(email, request, 'user_not_found')
        
        # If we get here, there were form errors
        if is_htmx:
            return render(request, 'users/login_form.html', {'form': form, 'is_htmx': is_htmx})
        return render(request, 'users/login.html', {'form': form, 'is_htmx': is_htmx})
    
    # GET request - show empty form
    form = EnhancedLoginForm()
    return render(request, 'users/login.html', {'form': form, 'is_htmx': is_htmx})

@require_http_methods(["GET", "POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    """Handle user logout."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    logout(request)
    messages.success(request, 'Successfully logged out!')
    
    if is_htmx:
        response = HttpResponse()
        response['HX-Redirect'] = '/'
        return response
    
    return redirect('public:index')

@require_http_methods(["GET", "POST"])
def signup_view(request: HttpRequest) -> HttpResponse:
    """Handle user registration with enhanced validation and error handling."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if request.method == "POST":
        form = EnhancedSignupForm(request.POST)
        if form.is_valid():
            try:
                # Save the user
                user = form.save()
                messages.success(request, 
                    'Account created successfully! Please check your email to verify your account before logging in.')
                
                # For HTMX requests, send a redirect header
                if is_htmx:
                    response = HttpResponse()
                    response['HX-Redirect'] = '/users/login/'
                    return response
                return redirect('users:login')
                
            except ValidationError as e:
                # Handle validation errors from the model
                form.add_error(None, str(e))
            except Exception:
                # Handle any unexpected errors during user creation
                form.add_error(None, 'An error occurred while creating your account. Please try again.')
                
        # Form has errors - render with error messages
        if is_htmx:
            return render(request, 'users/signup_form.html', {
                'form': form,
                'is_htmx': is_htmx
            })
        return render(request, 'users/signup.html', {
            'form': form,
            'is_htmx': is_htmx
        })
    
    # GET request - show empty form
    form = EnhancedSignupForm()
    return render(request, 'users/signup.html', {
        'form': form,
        'is_htmx': is_htmx
    })

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
def api_keys_view(request: HttpRequest) -> HttpResponse:
    """Display user's API keys."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    api_keys = APIKey.objects.filter(user=request.user).order_by('-created_at')
    
    return render(request, 'users/api_keys.html', {
        'api_keys': api_keys,
        'is_htmx': is_htmx
    })

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
        
        # Return the generated key template (shows raw key once)
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