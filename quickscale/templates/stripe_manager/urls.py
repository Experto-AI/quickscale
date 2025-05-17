"""URL patterns for the Stripe app."""
from django.urls import path
from . import views

app_name = 'stripe'

urlpatterns = [
    path('webhook/', views.webhook, name='webhook'),
    path('status/', views.status, name='status'),
    path('products/', views.product_list, name='product_list'),
    path('products/<str:product_id>/', views.product_detail, name='product_detail'),
] 