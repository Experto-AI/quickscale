"""URL configuration for staff dashboard."""
from django.urls import path

from . import views

app_name = 'dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('user/', views.user_dashboard, name='user_dashboard'),
    path('products/', views.product_admin, name='product_admin'),
    path('products/sync/', views.sync_products, name='sync_products'),
    path('products/<str:product_id>/sync/', views.product_sync, name='product_sync'),
    path('products/<int:product_id>/update_order/', views.update_product_order, name='update_product_order'),
    path('products/<str:product_id>/', views.product_detail, name='product_detail'),
]