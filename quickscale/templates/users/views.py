"""User authentication and account management views."""
from django.contrib import messages
from django.contrib.auth import authenticate, get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

User = get_user_model()

@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    """Handle user login."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if request.method == "POST":
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Successfully logged in!')
            
            if is_htmx:
                response = HttpResponse()
                response['HX-Redirect'] = '/'
                return response
            return redirect('public:index')
            
        messages.error(request, 'Invalid username or password.')
        return render(request, 'users/login_form.html', {'is_htmx': is_htmx})
    
    return render(request, 'users/login.html', {'is_htmx': is_htmx})

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
    """Handle user registration."""
    is_htmx = request.headers.get('HX-Request') == 'true'
    
    if request.method == "POST":
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        email = request.POST.get('email')
        
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, 'users/signup.html')
        
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'users/signup.html')
        
        try:
            User.objects.create_user(
                username=username,
                email=email,
                password=password1
            )
            messages.success(request, 'Account created successfully!')
            
            if is_htmx:
                response = HttpResponse()
                response['HX-Redirect'] = '/users/login/'
                return response
            
            return redirect('users:login')
            
        except Exception:
            messages.error(request, 'Error creating account. Please try again.')
            return render(request, 'users/signup.html')
    
    return render(request, 'users/signup.html')

@login_required
def profile_view(request: HttpRequest) -> HttpResponse:
    """Display user profile."""
    return render(request, 'users/profile.html')