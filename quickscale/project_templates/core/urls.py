"""Core URL Configuration for QuickScale."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.shortcuts import render
from django.urls import include, path
from django.views.decorators.csrf import ensure_csrf_cookie

from .configuration import config


# Simple health check view for Docker healthcheck
def health_check(request) -> HttpResponse:
    """A simple health check endpoint for container monitoring."""
    return HttpResponse("OK", content_type="text/plain")

@ensure_csrf_cookie
def admin_test(request) -> HttpResponse:
    """A test page for checking admin CSRF functionality."""
    return render(request, 'admin_test.html', {
        'settings': settings,
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    # django-allauth URLs must come before our custom user URLs
    path('accounts/', include('allauth.urls')),
    # Core URLs (always included)
    path('', include('public.urls', namespace='public')),
    path('users/', include('users.urls', namespace='users')),
    path('common/', include('common.urls', namespace='common')),
    path('health/', health_check, name='health_check'),  # Health check endpoint
    path('admin-test/', admin_test, name='admin_test'),  # Admin CSRF test page
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Feature-flagged URL patterns using configuration singleton
if config.feature_flags.enable_basic_admin or config.feature_flags.enable_advanced_admin:
    urlpatterns.append(path('dashboard/', include('admin_dashboard.urls', namespace='admin_dashboard')))

if config.feature_flags.enable_basic_credits or config.feature_flags.enable_credit_types:
    urlpatterns.append(path('dashboard/credits/', include('credits.urls', namespace='credits')))

if config.feature_flags.enable_demo_service or config.feature_flags.enable_service_marketplace:
    urlpatterns.append(path('services/', include('services.urls', namespace='services')))

if config.feature_flags.enable_api_endpoints:
    urlpatterns.append(path('api/', include('api.urls', namespace='api')))

# Include stripe URLs only if Stripe is enabled and fully configured
if config.is_stripe_enabled_and_configured():
    urlpatterns += [
        path('stripe/', include('stripe_manager.urls', namespace='stripe')),
    ]

# Static and media files for development environment
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
