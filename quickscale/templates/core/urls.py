"""URL configuration for QuickScale project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path
import os
from .env_utils import get_env, is_feature_enabled

# Simple health check view for Docker healthcheck
def health_check(request):
    """Return 200 OK response for container health checks."""
    return HttpResponse("OK")

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('public.urls')),
    path('users/', include('users.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('common/', include('common.urls')),
    path('accounts/', include('allauth.urls')),  # django-allauth URLs
    path('health/', health_check, name='health_check'),  # Health check endpoint for container monitoring
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Include djstripe URLs only if Stripe is enabled
stripe_enabled = is_feature_enabled(get_env('STRIPE_ENABLED', 'False'))
if stripe_enabled:
    urlpatterns += [
        path('stripe/', include('djstripe.urls')),
    ]
