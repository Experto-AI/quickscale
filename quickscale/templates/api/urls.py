"""URL configuration for API application."""
from django.urls import path, include
from . import views

app_name = 'api'

# API v1 URL patterns
v1_patterns = [
    path('text/process/', views.TextProcessingView.as_view(), name='text_process'),
    path('execute-service/', views.execute_service, name='execute_service'),
    path('list-services/', views.list_services, name='list_services'),
]

urlpatterns = [
    path('docs/', views.api_docs, name='api_docs'),  # API documentation
    path('v1/', include((v1_patterns, 'v1'), namespace='v1')),
]