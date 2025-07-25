# Generated migration for Sprint 11: API Endpoints and Services Layer
# This migration adds the Text Processing service for API endpoints

from django.db import migrations
from decimal import Decimal


def create_text_processing_service(apps, schema_editor):
    """Create the Text Processing service."""
    Service = apps.get_model('credits', 'Service')
    
    # Create Text Processing service if it doesn't exist
    Service.objects.get_or_create(
        name='Text Processing',
        defaults={
            'description': 'AI-powered text processing service including analysis, summarization, and counting operations',
            'credit_cost': Decimal('1.00'),  # Base cost - individual operations may vary
            'is_active': True,
        }
    )


def remove_text_processing_service(apps, schema_editor):
    """Remove the Text Processing service."""
    Service = apps.get_model('credits', 'Service')
    
    try:
        service = Service.objects.get(name='Text Processing')
        service.delete()
    except Service.DoesNotExist:
        pass


class Migration(migrations.Migration):

    dependencies = [
        ('credits', '0006_add_api_key_model'),
    ]

    operations = [
        migrations.RunPython(
            create_text_processing_service,
            remove_text_processing_service,
        ),
    ]