"""URL configuration for user account management."""
from django.urls import path

from . import views

app_name = 'users'

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('signup/', views.signup_view, name='signup'),
    path('profile/', views.profile_view, name='profile'),
    path('api-keys/', views.api_keys_view, name='api_keys'),
    path('api-keys/generate/', views.generate_api_key_view, name='generate_api_key'),
    path('api-keys/revoke/', views.revoke_api_key_view, name='revoke_api_key'),
    path('api-keys/regenerate/', views.regenerate_api_key_view, name='regenerate_api_key'),
]