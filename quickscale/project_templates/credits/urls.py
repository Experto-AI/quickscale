from django.urls import path
from . import views

app_name = 'credits'

urlpatterns = [
    path('', views.credits_dashboard, name='dashboard'),
    path('balance/', views.credit_balance_api, name='balance_api'),
    path('buy/', views.buy_credits, name='buy_credits'),
    path('checkout/', views.create_checkout_session, name='create_checkout'),
    path('success/', views.purchase_success, name='purchase_success'),
    path('cancel/', views.purchase_cancel, name='purchase_cancel'),
    path('services/', views.services_list, name='services'),
    path('services/<int:service_id>/use/', views.use_service, name='use_service'),
    path('services/<int:service_id>/use-priority/', views.use_service_with_priority, name='use_service_with_priority'),
    path('services/<int:service_id>/api/', views.service_usage_api, name='service_usage_api'),
] 