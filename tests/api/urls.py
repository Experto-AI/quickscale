"""URL configuration for API endpoints."""
from django.urls import path
from .views import TextProcessingView
from django.http import HttpResponse

# Simple dummy view for API docs
def api_docs(request):
    return HttpResponse("Test API Documentation")

app_name = 'api'

urlpatterns = [
    path('v1/text/process/', TextProcessingView.as_view(), name='text_process'),
    path('docs/', api_docs, name='api_docs'),
]