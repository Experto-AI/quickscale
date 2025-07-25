"""API URLs for credits app."""
from django.urls import path
from . import api_views

app_name = 'api'

urlpatterns = [
    # Text processing service endpoint
    path('text/analyze/', api_views.text_analysis_service, name='text_analysis'),
    
    # Credit balance endpoint
    path('credits/balance/', api_views.credit_balance, name='credit_balance'),
    
    # API key management endpoints
    path('auth/keys/', api_views.list_api_keys, name='list_api_keys'),
    path('auth/keys/create/', api_views.create_api_key, name='create_api_key'),
]