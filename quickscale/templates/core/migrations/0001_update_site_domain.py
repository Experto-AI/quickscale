"""Custom site domain migration to avoid duplication errors.

This migration uses update_or_create instead of create to prevent
unique constraint violations when the site with ID=1 already exists.
"""
from django.db import migrations


def update_site_forward(apps, schema_editor):
    """Update the default site or create it if it doesn't exist."""
    Site = apps.get_model('sites', 'Site')
    # Use update_or_create to handle cases where the site already exists
    Site.objects.update_or_create(
        id=1,
        defaults={
            'domain': 'example.com',
            'name': 'example.com'
        }
    )


def update_site_backward(apps, schema_editor):
    """Backward migration - no action needed."""
    pass


def create_site_permissions(apps, schema_editor):
    """Create permissions for the Site model if they don't exist.
    
    This function handles the creation of permissions in a way that prevents
    the 'duplicate key value violates unique constraint' error that can occur
    when Django tries to create permissions that already exist.
    """
    ContentType = apps.get_model('contenttypes', 'ContentType')
    Permission = apps.get_model('auth', 'Permission')
    
    # Get content type for the Site model
    try:
        site_content_type = ContentType.objects.get(app_label='sites', model='site')
        
        # Define the permissions we need to ensure exist
        permissions = [
            ('add_site', 'Can add site'),
            ('change_site', 'Can change site'),
            ('delete_site', 'Can delete site'),
            ('view_site', 'Can view site'),
        ]
        
        # Create permissions one by one, skipping if they already exist
        for codename, name in permissions:
            Permission.objects.get_or_create(
                content_type=site_content_type,
                codename=codename,
                defaults={'name': name}
            )
    except ContentType.DoesNotExist:
        # If the content type doesn't exist, we can't create permissions
        pass


class Migration(migrations.Migration):
    """Migration to update site domain safely."""

    dependencies = [
        ('sites', '0001_initial'),
        ('auth', '0012_alter_user_first_name_max_length'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.RunPython(update_site_forward, update_site_backward),
        migrations.RunPython(create_site_permissions, update_site_backward),
    ] 