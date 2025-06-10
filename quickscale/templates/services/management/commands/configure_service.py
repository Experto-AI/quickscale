"""
Django management command to configure services in the database.

This command allows easy configuration of AI services without using the admin interface.
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from credits.models import Service
from decimal import Decimal


class Command(BaseCommand):
    """Management command to configure AI services."""
    
    help = 'Configure AI services in the database'

    def add_arguments(self, parser):
        """Add command arguments."""
        parser.add_argument(
            'service_name',
            type=str,
            nargs='?',  # Make service_name optional
            help='Name of the service to configure'
        )
        parser.add_argument(
            '--description',
            type=str,
            help='Description of the service',
            default=''
        )
        parser.add_argument(
            '--credit-cost',
            type=float,
            help='Credit cost for using this service',
            default=1.0
        )
        parser.add_argument(
            '--active',
            action='store_true',
            help='Set service as active (default: True)',
            default=True
        )
        parser.add_argument(
            '--inactive',
            action='store_true', 
            help='Set service as inactive'
        )
        parser.add_argument(
            '--update',
            action='store_true',
            help='Update existing service instead of creating new one'
        )
        parser.add_argument(
            '--list',
            action='store_true',
            help='List all configured services'
        )

    def handle(self, *args, **options):
        """Handle the command execution."""
        if options['list']:
            if options['service_name']:
                raise CommandError("Cannot specify service_name with --list option.")
            self.list_services()
            return

        service_name = options['service_name']
        if not service_name:
            raise CommandError("The following arguments are required: service_name for create/update operations.")

        description = options['description'] or f"AI service: {service_name}"
        credit_cost = Decimal(str(options['credit_cost']))
        is_active = not options['inactive']  # Default to active unless --inactive is set

        try:
            with transaction.atomic():
                if options['update']:
                    self.update_service(service_name, description, credit_cost, is_active)
                else:
                    self.create_service(service_name, description, credit_cost, is_active)
        except Exception as e:
            raise CommandError(f"Error configuring service: {str(e)}")

    def create_service(self, name: str, description: str, credit_cost: Decimal, is_active: bool):
        """Create a new service."""
        service, created = Service.objects.get_or_create(
            name=name,
            defaults={
                'description': description,
                'credit_cost': credit_cost,
                'is_active': is_active
            }
        )

        if created:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Created service '{name}' with {credit_cost} credit cost"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    f"⚠️  Service '{name}' already exists. Use --update to modify it."
                )
            )
            self.display_service_info(service)

    def update_service(self, name: str, description: str, credit_cost: Decimal, is_active: bool):
        """Update an existing service."""
        try:
            service = Service.objects.get(name=name)
            
            # Store old values for comparison
            old_cost = service.credit_cost
            old_active = service.is_active
            old_description = service.description
            
            # Update the service
            service.description = description
            service.credit_cost = credit_cost
            service.is_active = is_active
            service.save()

            self.stdout.write(
                self.style.SUCCESS(f"✅ Updated service '{name}'")
            )
            
            # Show what changed
            if old_cost != credit_cost:
                self.stdout.write(f"   Credit cost: {old_cost} → {credit_cost}")
            if old_active != is_active:
                status = "active" if is_active else "inactive"
                old_status = "active" if old_active else "inactive"
                self.stdout.write(f"   Status: {old_status} → {status}")
            if old_description != description:
                self.stdout.write(f"   Description updated")

        except Service.DoesNotExist:
            self.stdout.write(
                self.style.ERROR(
                    f"❌ Service '{name}' does not exist. Remove --update to create it."
                )
            )

    def list_services(self):
        """List all configured services."""
        services = Service.objects.all().order_by('name')
        
        if not services.exists():
            self.stdout.write(
                self.style.WARNING("No services configured yet.")
            )
            return

        self.stdout.write(self.style.SUCCESS("📋 Configured Services:"))
        self.stdout.write("")
        
        for service in services:
            status_icon = "✅" if service.is_active else "❌"
            status_text = "active" if service.is_active else "inactive"
            
            self.stdout.write(f"{status_icon} {service.name}")
            self.stdout.write(f"   Cost: {service.credit_cost} credits")
            self.stdout.write(f"   Status: {status_text}")
            if service.description:
                self.stdout.write(f"   Description: {service.description}")
            self.stdout.write("")

    def display_service_info(self, service):
        """Display information about a service."""
        status_icon = "✅" if service.is_active else "❌"
        status_text = "active" if service.is_active else "inactive"
        
        self.stdout.write(f"   {status_icon} Current configuration:")
        self.stdout.write(f"     Name: {service.name}")
        self.stdout.write(f"     Cost: {service.credit_cost} credits")
        self.stdout.write(f"     Status: {status_text}")
        if service.description:
            self.stdout.write(f"     Description: {service.description}") 