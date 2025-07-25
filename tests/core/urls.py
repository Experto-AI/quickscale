from django.urls import path, include
from django.http import HttpResponse

# Simple dummy views for test URLs
def dummy_home(request):
    return HttpResponse("Test Home Page")

def dummy_contact(request):
    return HttpResponse("Test Contact Page")

def dummy_about(request):
    return HttpResponse("Test About Page")

def dummy_profile(request):
    return HttpResponse("Test Profile Page")


def dummy_logout(request):
    return HttpResponse("Test Logout")

def dummy_signup(request):
    return HttpResponse("Test Signup")

def dummy_account_security(request):
    return HttpResponse("Test Account Security Page")

def dummy_login(request):
    return HttpResponse("Test Login")

def dummy_user_dashboard(request):
    return HttpResponse("Test User Dashboard")

def dummy_service_list(request):
    return HttpResponse("Test Service List")

def dummy_service_use_form(request, service_id):
    return HttpResponse(f"Test Service Use Form {service_id}")

def dummy_service_use(request, service_id):
    return HttpResponse(f"Test Service Use {service_id}")

urlpatterns = [
    path('accounts/', include('allauth.account.urls')),
    path('api/', include('api.urls')),
    path('dashboard/credits/', include('credits.urls')),
    path('admin_dashboard/', include('admin_dashboard.urls')),
    # Add dummy public URLs for tests
    path('', dummy_home, name='home'),
    path('contact/', dummy_contact, name='contact'),
    path('about/', dummy_about, name='about'),
    path('dashboard/', dummy_user_dashboard, name='user_dashboard'),
]

# Create public namespace for template compatibility
public_urls = [
    path('', dummy_home, name='index'),  # Use 'index' name that the navbar template expects
    path('contact/', dummy_contact, name='contact'),
    path('about/', dummy_about, name='about'),
]

# Create users namespace for template compatibility
users_urls = [
    path('profile/', dummy_profile, name='profile'),
    path('logout/', dummy_logout, name='logout'),
    path('signup/', dummy_signup, name='signup'),
    path('login/', dummy_login, name='login'),
    path('account-security/', dummy_account_security, name='account_security'),
]

# Create services namespace for template compatibility
services_urls = [
    path('', dummy_service_list, name='list'),
    path('<int:service_id>/use/', dummy_service_use_form, name='use_form'),
    path('<int:service_id>/execute/', dummy_service_use, name='use_service'),
]

urlpatterns += [
    path('', include((public_urls, 'public'), namespace='public')),
    path('users/', include((users_urls, 'users'), namespace='users')),
    path('services/', include((services_urls, 'services'), namespace='services')),
]

# Import settings to check if Stripe is enabled
from django.conf import settings

# Add Stripe URLs if Stripe is enabled in settings
if getattr(settings, 'STRIPE_ENABLED', False):
    try:
        # Import and add stripe URLs
        urlpatterns += [
            path('stripe/', include('stripe_manager.urls', namespace='stripe')),
        ]
    except ImportError:
        # If stripe_manager is not available, ignore
        pass