"""
Django Stripe URLs

This module contains URL patterns for Stripe-related functionality.
All URLs are prefixed with 'stripe/' and only enabled when STRIPE_ENABLED=True.
"""

from django.urls import path, include
from . import views, webhooks

app_name = 'djstripe'

urlpatterns = [
    # Webhook endpoint
    path('webhook/', webhooks.stripe_webhook, name='webhook'),
    
    # Status view
    path('status/', views.stripe_status, name='status'),
    
    # Customer management
    path('customer/create/', views.create_customer, name='create_customer'),
    
    # Product management
    path('products/', views.product_list, name='product_list'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    
    # Subscription management URLs
    # path('subscriptions/', views.subscription_list, name='subscription_list'),
    # path('subscriptions/<uuid:subscription_id>/', views.subscription_details, name='subscription_details'),
    # path('subscriptions/create/', views.create_subscription, name='create_subscription'),
    # path('subscriptions/<uuid:subscription_id>/cancel/', views.cancel_subscription, name='cancel_subscription'),
    
    # Payment method management
    # path('payment-methods/', views.payment_method_list, name='payment_method_list'),
    # path('payment-methods/add/', views.add_payment_method, name='add_payment_method'),
    # path('payment-methods/<uuid:payment_method_id>/delete/', views.delete_payment_method, name='delete_payment_method'),
    
    # Customer portal
    # path('portal/', views.customer_portal, name='customer_portal'),
    
    # Checkout session
    # path('checkout/session/', views.create_checkout_session, name='create_checkout_session'),
    # path('checkout/success/', views.checkout_success, name='checkout_success'),
    # path('checkout/cancel/', views.checkout_cancel, name='checkout_cancel'),
]

# Note: This URL file will be included in the main urls.py only when STRIPE_ENABLED=True 