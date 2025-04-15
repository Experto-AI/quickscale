"""URL configuration for staff dashboard."""
from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('products/', views.product_admin, name='product_admin'),
    path('products/refresh/', views.product_admin_refresh, name='product_admin_refresh'),
]