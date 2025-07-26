"""URL patterns for the Stripe app."""
from django.urls import path
from . import views

app_name = 'stripe'

urlpatterns = [
    path('webhook/', views.webhook, name='webhook'),
    path('status/', views.status, name='status'),
    path('products/', views.product_list, name='product_list'),
    path('products/<str:product_id>/', views.product_detail, name='product_detail'),
    path('plans/compare/', views.PublicPlanListView.as_view(), name='plan_comparison'),
    path('create-checkout-session/', views.CheckoutView.as_view(), name='create_checkout_session'),
    path('checkout/success/', views.checkout_success_view, name='checkout_success'),
    path('checkout/cancel/', views.checkout_cancel_view, name='checkout_cancel'),
] 