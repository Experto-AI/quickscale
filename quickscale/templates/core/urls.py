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
    path('', include('public.urls')),
    path('users/', include('users.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('common/', include('common.urls')),
    path('accounts/', include('allauth.urls')),  # django-allauth URLs
    path('health/', health_check, name='health_check'),  # Health check endpoint
    path('admin-test/', admin_test, name='admin_test'),  # Admin CSRF test page
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Include djstripe URLs only if Stripe is enabled
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
if stripe_enabled:
    urlpatterns += [
        path('stripe/', include('djstripe.urls')),
    ]
