"""URL configuration for user account management."""
from django.urls import path

from . import views
from .views_2fa import (
    two_factor_settings, 
    two_factor_setup_prepare, 
    two_factor_generate_backup_codes,
    two_factor_disable,
    two_factor_status
)

app_name = 'users'

urlpatterns = [
    path('profile/', views.profile_view, name='profile'),
    path('account-security/', views.account_security_view, name='account_security'),
    path('account-security/generate-api-key/', views.generate_api_key_view, name='generate_api_key'),
    path('account-security/revoke-api-key/', views.revoke_api_key_view, name='revoke_api_key'),
    path('account-security/regenerate-api-key/', views.regenerate_api_key_view, name='regenerate_api_key'),
    path('account-security/api-keys-list-partial/', views.api_keys_list_partial, name='api_keys_list_partial'),
    path('account-security/api-keys/', views.account_security_view, name='api_keys'),  # Added for reverse('users:api_keys')
    # Two-Factor Authentication (preparation)
    # path('2fa/', two_factor_settings, name='two_factor_settings'),
    path('2fa/setup/', two_factor_setup_prepare, name='two_factor_setup_prepare'),
    path('2fa/backup-codes/', two_factor_generate_backup_codes, name='two_factor_generate_backup_codes'),
    path('2fa/disable/', two_factor_disable, name='two_factor_disable'),
    path('2fa/status/', two_factor_status, name='two_factor_status'),
]