"""
Django management command to create default example services.

This command creates default example services for demonstration and testing purposes.
It's automatically run during project initialization to provide ready-to-use services.
"""

import logging
from decimal import Decimal

from credits.models import Service
from django.core.management.base import BaseCommand
from django.db import transaction

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Management command to create default example services."""

    help = 'Create default example services for demonstration'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            '--force',
            action='store_true',
            help='Force creation even if services already exist'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        force = options.get('force', False)

        try:
            with transaction.atomic():
                self.create_default_services(force)
        except Exception as e:
            logger.error(f"Error creating default services: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f"❌ Error creating default services: {str(e)}")
            )

    def create_default_services(self, force: bool = False):
        """Create default example services."""
        services_to_create = [
            {
                'name': 'text_sentiment_analysis',
                'description': 'Advanced text sentiment analysis service with keyword-based scoring. Analyzes text to determine positive, negative, or neutral sentiment with confidence scores.',
                'credit_cost': Decimal('1.0'),
                'is_active': True
            },
            {
                'name': 'image_metadata_extractor',
                'description': 'Extract metadata and basic information from uploaded images. Analyzes image properties, format details, and provides technical information.',
                'credit_cost': Decimal('10.0'),
                'is_active': True
            },
            {
                'name': 'demo_free_service',
                'description': 'Free demonstration service showing zero-cost AI operations. Perfect for testing the service framework without credit consumption.',
                'credit_cost': Decimal('0.0'),
                'is_active': True
            }
        ]

        created_count = 0
        skipped_count = 0

        for service_data in services_to_create:
            service, created = Service.objects.get_or_create(
                name=service_data['name'],
                defaults={
                    'description': service_data['description'],
                    'credit_cost': service_data['credit_cost'],
                    'is_active': service_data['is_active']
                }
            )

            if created:
                created_count += 1
                if service_data['credit_cost'] == 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Created free example service: '{service_data['name']}'"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"✅ Created example service: '{service_data['name']}' ({service_data['credit_cost']} credits)"
                        )
                    )
            else:
                if force:
                    # Update existing service
                    service.description = service_data['description']
                    service.credit_cost = service_data['credit_cost']
                    service.is_active = service_data['is_active']
                    service.save()
                    created_count += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"🔄 Updated example service: '{service_data['name']}' (forced)"
                        )
                    )
                else:
                    skipped_count += 1
                    self.stdout.write(
                        self.style.WARNING(
                            f"⚠️  Example service '{service_data['name']}' already exists"
                        )
                    )

        # Summary
        if created_count > 0:
            self.stdout.write(
                self.style.SUCCESS(
                    f"\n🎉 Successfully processed {created_count} example service(s)!"
                )
            )
            self.stdout.write(
                self.style.SUCCESS(
                    "You can now test these services at: http://localhost:8000/services/"
                )
            )

        if skipped_count > 0:
            self.stdout.write(
                self.style.WARNING(
                    f"⏭️  Skipped {skipped_count} existing service(s). Use --force to update them."
                )
            )

        if created_count == 0 and skipped_count == 0:
            self.stdout.write(
                self.style.WARNING("No services were processed.")
            )
