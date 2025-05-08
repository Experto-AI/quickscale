"""Context processors for Django templates."""
from django.conf import settings

def project_settings(request):
    """Make project settings available in templates."""
    return {
        'project_name': settings.PROJECT_NAME,
    }