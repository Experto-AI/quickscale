"""
Management command to sync Products with Stripe.

This command allows synchronizing products with Stripe in both directions.
It can:
1. Push local products to Stripe
2. Pull Stripe products to the local database
3. Update existing products

Example usage:
    python manage.py sync_products_with_stripe --push
    python manage.py sync_products_with_stripe --pull
    python manage.py sync_products_with_stripe --push --product-id=1
"""

import logging
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from djstripe.models import Product
from djstripe.services import ProductService
from djstripe.utils import get_stripe
from core.env_utils import get_env, is_feature_enabled

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    """Command to sync products with Stripe."""
    
    help = 'Sync products with Stripe in either direction'
    
    def add_arguments(self, parser):
        """Add command arguments."""
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument('--push', action='store_true', help='Push local products to Stripe')
        group.add_argument('--pull', action='store_true', help='Pull products from Stripe')
        
        parser.add_argument('--product-id', type=int, help='Sync only the specified product ID')
        parser.add_argument('--all-products', action='store_true', help='Sync all products including inactive ones')
        parser.add_argument('--verbose', action='store_true', help='Enable verbose output')
    
    def handle(self, *args, **options):
        """Execute the command."""
        # Check if Stripe is enabled
        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            raise CommandError('Stripe is not enabled. Set STRIPE_ENABLED=true in your environment.')
        
        # Get Stripe API client
        stripe = get_stripe()
        if not stripe:
            raise CommandError('Stripe API client not available. Check your installation.')
        
        # Set up logging verbosity
        verbosity = 2 if options['verbose'] else 1
        
        if options['push']:
            self.push_to_stripe(options, verbosity)
        else:  # pull
            self.pull_from_stripe(options, verbosity)
    
    def push_to_stripe(self, options, verbosity):
        """Push local products to Stripe."""
        product_id = options.get('product_id')
        all_products = options.get('all_products')
        
        # Get products to sync
        if product_id:
            try:
                products = [Product.objects.get(id=product_id)]
                self.stdout.write(f"Found product: {products[0].name}")
            except Product.DoesNotExist:
                raise CommandError(f"Product with ID {product_id} not found")
        else:
            # Get all products or only active ones
            if all_products:
                products = Product.objects.all()
            else:
                products = Product.objects.filter(status=Product.ACTIVE)
            
            self.stdout.write(f"Found {products.count()} products to sync")
        
        # Sync each product
        created = 0
        updated = 0
        failed = 0
        
        for product in products:
            product_display = f"'{product.name}' (ID: {product.id})"
            
            if verbosity >= 2:
                self.stdout.write(f"Processing {product_display}...")
            
            try:
                if product.stripe_product_id:
                    # Update existing product
                    if ProductService.update_in_stripe(product):
                        updated += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"Updated product {product_display} in Stripe (ID: {product.stripe_product_id})"
                        ))
                    else:
                        failed += 1
                        self.stdout.write(self.style.ERROR(
                            f"Failed to update product {product_display} in Stripe"
                        ))
                else:
                    # Create new product
                    stripe_id = ProductService.create_in_stripe(product)
                    if stripe_id:
                        created += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"Created product {product_display} in Stripe (ID: {stripe_id})"
                        ))
                    else:
                        failed += 1
                        self.stdout.write(self.style.ERROR(
                            f"Failed to create product {product_display} in Stripe"
                        ))
            except Exception as e:
                failed += 1
                self.stdout.write(self.style.ERROR(
                    f"Error processing product {product_display}: {str(e)}"
                ))
        
        # Show summary
        self.stdout.write(self.style.SUCCESS(
            f"Sync complete: {created} created, {updated} updated, {failed} failed"
        ))
    
    def pull_from_stripe(self, options, verbosity):
        """Pull products from Stripe to local database."""
        product_id = options.get('product_id')
        all_products = options.get('all_products')
        
        stripe = get_stripe()
        stripe.api_key = get_env('STRIPE_SECRET_KEY')
        
        if product_id:
            # Sync specific local product from Stripe
            try:
                product = Product.objects.get(id=product_id)
                if not product.stripe_product_id:
                    raise CommandError(f"Product {product_id} does not have a Stripe ID")
                
                stripe_product_id = product.stripe_product_id
                self.stdout.write(f"Syncing product ID {product_id} from Stripe ID {stripe_product_id}")
                
                updated_product = ProductService.sync_from_stripe(stripe_product_id)
                if updated_product:
                    self.stdout.write(self.style.SUCCESS(
                        f"Successfully synced product '{updated_product.name}' from Stripe"
                    ))
                else:
                    self.stdout.write(self.style.ERROR(
                        f"Failed to sync product from Stripe ID {stripe_product_id}"
                    ))
            except Product.DoesNotExist:
                raise CommandError(f"Product with ID {product_id} not found")
        else:
            # Sync all products from Stripe
            # Get all products from Stripe
            stripe_products = stripe.Product.list(limit=100)
            
            created = 0
            updated = 0
            failed = 0
            
            # Filter active products if needed
            if not all_products:
                stripe_products.data = [p for p in stripe_products.data if p.active]
            
            self.stdout.write(f"Found {len(stripe_products.data)} products in Stripe")
            
            for stripe_product in stripe_products.data:
                if verbosity >= 2:
                    self.stdout.write(f"Processing Stripe product: {stripe_product.name} (ID: {stripe_product.id})...")
                
                try:
                    # Check if product exists locally
                    try:
                        product = Product.objects.get(stripe_product_id=stripe_product.id)
                        is_new = False
                    except Product.DoesNotExist:
                        product = None
                        is_new = True
                    
                    # Sync from Stripe
                    result = ProductService.sync_from_stripe(stripe_product.id)
                    
                    if result:
                        if is_new:
                            created += 1
                            self.stdout.write(self.style.SUCCESS(
                                f"Created local product '{result.name}' from Stripe (ID: {stripe_product.id})"
                            ))
                        else:
                            updated += 1
                            self.stdout.write(self.style.SUCCESS(
                                f"Updated local product '{result.name}' from Stripe (ID: {stripe_product.id})"
                            ))
                    else:
                        failed += 1
                        self.stdout.write(self.style.ERROR(
                            f"Failed to sync product '{stripe_product.name}' from Stripe"
                        ))
                except Exception as e:
                    failed += 1
                    self.stdout.write(self.style.ERROR(
                        f"Error processing Stripe product {stripe_product.id}: {str(e)}"
                    ))
            
            # Show summary
            self.stdout.write(self.style.SUCCESS(
                f"Sync complete: {created} created, {updated} updated, {failed} failed"
            ))