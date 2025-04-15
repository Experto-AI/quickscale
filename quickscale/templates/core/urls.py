"""URL configuration for QuickScale project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
import os

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('public.urls')),
    path('users/', include('users.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('common/', include('common.urls')),
    path('accounts/', include('allauth.urls')),  # django-allauth URLs
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Include djstripe URLs only if Stripe is enabled
stripe_enabled = os.getenv('STRIPE_ENABLED', 'False').lower() == 'true'
if stripe_enabled:
    urlpatterns += [
        path('stripe/', include('djstripe.urls')),
    ]
