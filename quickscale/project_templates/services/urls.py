from django.urls import path
from . import views

app_name = 'services'

urlpatterns = [
    path('', views.service_list, name='list'),
    path('<int:service_id>/use/', views.service_usage_form, name='use_form'),
    path('<int:service_id>/execute/', views.use_service, name='use_service'),
    path('<int:service_id>/status/', views.service_status_api, name='status_api'),
]