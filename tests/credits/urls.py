"""URL configuration for credits and API key management."""
from django.urls import path
from .views import APIKeyListView, APIKeyCreateView

app_name = 'credits'

urlpatterns = [
    path('api/auth/keys/', APIKeyListView.as_view(), name='api_keys'),
    path('api/auth/keys/create/', APIKeyCreateView.as_view(), name='api_keys_create'),
]