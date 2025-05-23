from django.urls import path
from . import views

app_name = 'credits'

urlpatterns = [
    path('', views.credits_dashboard, name='dashboard'),
    path('balance/', views.credit_balance_api, name='balance_api'),
] 