"""Test URL configuration that provides complete QuickScale URLs for authentication tests."""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse

# Import URL patterns from QuickScale templates to get proper structure
import sys
from pathlib import Path

# Add the project templates to Python path to import URL modules
template_path = Path(__file__).parent.parent / 'quickscale' / 'project_templates'
sys.path.insert(0, str(template_path))

# Simple views for testing
def home_view(request):
    return HttpResponse("Home")

def about_view(request):
    return HttpResponse("About")

def contact_view(request):
    return HttpResponse("Contact") 

def privacy_view(request):
    return HttpResponse("Privacy")

def terms_view(request):
    return HttpResponse("Terms")

def index_view(request):
    return HttpResponse("Index")

def signup_view(request):
    return HttpResponse("Signup")

# Health check view
def health_check(request):
    return HttpResponse("OK", content_type="text/plain")

# Create minimal public URLs that allauth templates expect
public_patterns = [
    path('', home_view, name='home'),
    path('about/', about_view, name='about'),
    path('contact/', contact_view, name='contact'),
    path('privacy/', privacy_view, name='privacy'),
    path('terms/', terms_view, name='terms'),
    path('index/', index_view, name='index'),
    path('signup/', signup_view, name='signup'),
        # Stripe integration patterns
        path('subscription/', lambda request: HttpResponse("Subscription page"), name='subscription'),
        path('buy-credits/', lambda request: HttpResponse("Buy credits page"), name='buy_credits'),
        path('use-service/', lambda request: HttpResponse("Use service page"), name='use_service'),
    ]
# Empty URL patterns for namespaces
users_patterns = [
    path('profile/', lambda r: HttpResponse("User Profile"), name='profile'),
    path('security/', lambda r: HttpResponse("Account Security"), name='account_security'),
]
empty_users_patterns = (users_patterns, 'users')
admin_dashboard_patterns = [
    path('', lambda r: HttpResponse("Admin Dashboard"), name='user_dashboard'),
    path('index/', lambda r: HttpResponse("Admin Dashboard Index"), name='index'),
    path('subscription/', lambda r: HttpResponse("Subscription page\nPremium Plan"), name='subscription'),
    path('subscription/checkout/', lambda r: HttpResponse("Create subscription checkout"), name='create_subscription_checkout'),
]
empty_admin_dashboard_patterns = (admin_dashboard_patterns, 'admin_dashboard')
empty_credits_patterns = ([
    path('buy/', lambda r: HttpResponse("Buy credits page"), name='buy_credits'),
    path('checkout/', lambda r: HttpResponse("Create checkout session"), name='create_checkout'),
    path('use/<int:service_id>/', lambda r, service_id: HttpResponse(f"Use service {service_id}\ninsufficient credits"), name='use_service'),
], 'credits')
empty_common_patterns = ([], 'common')

# Minimal API patterns
api_patterns = [
    path('docs/', lambda r: HttpResponse("API Docs"), name='api_docs'),
]
empty_api_patterns = (api_patterns, 'api')

# Minimal service patterns
services_patterns = [
    path('', lambda r: HttpResponse("Services List"), name='list'),
    path('use/', lambda r: HttpResponse("Use service page"), name='use_service'),
]
empty_services_patterns = (services_patterns, 'services')

# Main URL patterns - simplified to avoid import issues
urlpatterns = [
    path('admin/', admin.site.urls),
    # django-allauth URLs for authentication
    path('accounts/', include('allauth.urls')),
    # Include public URLs with namespace as expected by templates
    path('', include((public_patterns, 'public'), namespace='public')),
    # Minimal namespaces for template compatibility - these are just empty patterns
    path('users/', include(empty_users_patterns, namespace='users')),
    path('dashboard/', include(empty_admin_dashboard_patterns, namespace='admin_dashboard')),
    path('dashboard/credits/', include(empty_credits_patterns, namespace='credits')),
    path('services/', include(empty_services_patterns, namespace='services')),
    path('common/', include(empty_common_patterns, namespace='common')),
    path('api/', include(empty_api_patterns, namespace='api')),
    path('health/', health_check, name='health_check'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
