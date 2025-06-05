"""URL configuration for API endpoints."""
from django.urls import path
from .views import TextProcessingView

app_name = 'api'

urlpatterns = [
    path('v1/text/process/', TextProcessingView.as_view(), name='text_process'),
]