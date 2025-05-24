from django.urls import path
from . import views

app_name = 'credits'

urlpatterns = [
    path('', views.credits_dashboard, name='dashboard'),
    path('balance/', views.credit_balance_api, name='balance_api'),
    path('services/', views.services_list, name='services'),
    path('services/<int:service_id>/use/', views.use_service, name='use_service'),
    path('services/<int:service_id>/api/', views.service_usage_api, name='service_usage_api'),
] 