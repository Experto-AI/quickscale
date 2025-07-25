"""URL configuration for admin dashboard."""
from django.urls import path

from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('user/', views.user_dashboard, name='user_dashboard'),
    path('subscription/', views.subscription_page, name='subscription'),
    path('subscription/checkout/', views.create_subscription_checkout, name='create_subscription_checkout'),
    path('subscription/change-checkout/', views.create_plan_change_checkout, name='create_plan_change_checkout'),

    path('subscription/cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('subscription/plan-change-success/', views.plan_change_success, name='plan_change_success'),
    path('subscription/cancel/', views.subscription_cancel, name='subscription_cancel'),
    path('products/', views.product_admin, name='product_admin'),
    path('products/sync/', views.sync_products, name='sync_products'),
    path('products/<str:product_id>/sync/', views.product_sync, name='product_sync'),
    path('products/<int:product_id>/update_order/', views.update_product_order, name='update_product_order'),
    path('products/<str:product_id>/', views.product_detail, name='product_detail'),
    path('payments/', views.payment_history, name='payment_history'),
    path('payments/<int:payment_id>/', views.payment_detail, name='payment_detail'),
    path('payments/<int:payment_id>/receipt/', views.download_receipt, name='download_receipt'),
    # Service management URLs
    path('services/', views.service_admin, name='service_admin'),
    path('services/<int:service_id>/', views.service_detail, name='service_detail'),
    path('services/<int:service_id>/toggle/', views.service_toggle_status, name='service_toggle_status'),
    # User management URLs
    path('users/search/', views.user_search, name='user_search'),
    path('users/<int:user_id>/', views.user_detail, name='user_detail'),
    path('users/<int:user_id>/credit-adjustment/', views.user_credit_adjustment, name='user_credit_adjustment'),
    path('users/<int:user_id>/credit-history/', views.user_credit_history, name='user_credit_history'),
    # Audit log URLs
    path('audit/', views.audit_log, name='audit_log'),
    # Payment admin tools
    path('payments/search/', views.payment_search, name='payment_search'),
    path('payments/<int:payment_id>/investigate/', views.payment_investigation, name='payment_investigation'),
    path('payments/<int:payment_id>/refund/', views.initiate_refund, name='initiate_refund'),
    # Analytics dashboard
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
]