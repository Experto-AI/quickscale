from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('user/', views.user_dashboard, name='user_dashboard'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
] 