from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    path('', views.index, name='index'),
    path('user/', views.user_dashboard, name='user_dashboard'),
    path('subscription/', views.subscription_page, name='subscription'),
    path('subscription/checkout/', views.create_subscription_checkout, name='create_subscription_checkout'),
    path('subscription/success/', views.subscription_success, name='subscription_success'),
    path('subscription/cancel/', views.subscription_cancel, name='subscription_cancel'),
    path('analytics/', views.analytics_dashboard, name='analytics_dashboard'),
] 