"""URL configuration for QuickScale project."""
from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('public.urls')),
    path('users/', include('users.urls')),
    path('dashboard/', include('dashboard.urls')),
    path('common/', include('common.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
