"""Core URL Configuration for QuickScale."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.shortcuts import render
from django.views.decorators.csrf import ensure_csrf_cookie
import os
from .env_utils import get_env, is_feature_enabled
from django.views.generic import RedirectView

# Simple health check view for Docker healthcheck
def health_check(request):
    """A simple health check endpoint for container monitoring."""
    return HttpResponse("OK", content_type="text/plain")

@ensure_csrf_cookie
def admin_test(request):
    """A test page for checking admin CSRF functionality."""
    return render(request, 'admin_test.html', {
        'settings': settings,
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    # Include public app URLs, but at the root level
    path('', include('public.urls')),
    path('users/', include('users.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('dashboard/credits/', include('credits.urls', namespace='credits')),
    path('common/', include('common.urls')),
    path('accounts/', include('allauth.urls')),  # django-allauth URLs
    path('health/', health_check, name='health_check'),  # Health check endpoint
    path('admin-test/', admin_test, name='admin_test'),  # Admin CSRF test page
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Include stripe URLs only if Stripe is enabled AND fully configured
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
if stripe_enabled:
    # Also check that all required settings are present
    stripe_public_key = get_env('STRIPE_PUBLIC_KEY', '')
    stripe_secret_key = get_env('STRIPE_SECRET_KEY', '')
    stripe_webhook_secret = get_env('STRIPE_WEBHOOK_SECRET', '')
    
    if stripe_public_key and stripe_secret_key and stripe_webhook_secret:
        urlpatterns += [
            path('stripe/', include('stripe_manager.urls', namespace='stripe')),
        ]

# Static and media files for development environment
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
