from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
] 