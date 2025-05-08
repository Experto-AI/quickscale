"""
Django Stripe Services

Service classes that encapsulate business logic for interacting with Stripe.
These services create a clean separation between the application's data models
and external API interactions with Stripe.
"""

import logging
from typing import Optional, Dict, Any, List, Tuple
from django.conf import settings
from core.env_utils import get_env, is_feature_enabled
from .models import Product
from .utils import get_stripe

logger = logging.getLogger(__name__)


class ProductService:
    """
    Service for managing products in both the local database and Stripe.
    
    This service handles synchronization between local Product models
    and Stripe's product/price API, ensuring data consistency across systems.
    """
    
    @staticmethod
    def create_in_stripe(product: Product) -> Optional[str]:
        """
        Create a product in Stripe based on local product data.
        
        Args:
            product: The Product model instance to create in Stripe
            
        Returns:
            The Stripe product ID if successful, None otherwise
        """
        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe is not enabled. Skipping product creation in Stripe.")
            return None
            
        stripe = get_stripe()
        if not stripe:
            logger.error("Stripe API not available. Cannot create product.")
            return None
            
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Create product in Stripe
            stripe_product = stripe.Product.create(
                name=product.name,
                description=product.description or "",
                active=product.is_active(),
                metadata={
                    'product_id': str(product.id),
                }
            )
            
            # Create price for the product
            stripe_price = stripe.Price.create(
                product=stripe_product.id,
                unit_amount=int(product.base_price * 100),  # Stripe uses cents
                currency=product.currency.lower(),
                active=product.is_active(),
                metadata={
                    'product_id': str(product.id),
                }
            )
            
            # Update product with Stripe ID
            product.stripe_product_id = stripe_product.id
            if not product.metadata:
                product.metadata = {}
            product.metadata['stripe_price_id'] = stripe_price.id
            product.save(update_fields=['stripe_product_id', 'metadata'])
            
            logger.info(f"Created product in Stripe: {stripe_product.id} with price: {stripe_price.id}")
            return stripe_product.id
            
        except Exception as e:
            logger.error(f"Error creating product in Stripe: {str(e)}")
            return None
    
    @staticmethod
    def update_in_stripe(product: Product) -> bool:
        """
        Update a product in Stripe based on local product data.
        
        Args:
            product: The Product model instance to update in Stripe
            
        Returns:
            True if the update was successful, False otherwise
        """
        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe is not enabled. Skipping product update in Stripe.")
            return False
            
        if not product.stripe_product_id:
            logger.warning(f"Product {product.id} does not have a Stripe product ID. Creating instead of updating.")
            return bool(ProductService.create_in_stripe(product))
            
        stripe = get_stripe()
        if not stripe:
            logger.error("Stripe API not available. Cannot update product.")
            return False
            
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Update product in Stripe
            stripe_product = stripe.Product.modify(
                product.stripe_product_id,
                name=product.name,
                description=product.description or "",
                active=product.is_active(),
                metadata={
                    'product_id': str(product.id),
                }
            )
            
            # Update or create price for the product
            price_id = product.metadata.get('stripe_price_id') if product.metadata else None
            
            if price_id:
                # Cannot update amount of existing price, must create a new one
                # and archive the old one if needed
                current_price = stripe.Price.retrieve(price_id)
                
                # Only create a new price if details have changed
                if (int(product.base_price * 100) != current_price.unit_amount or 
                    product.currency.lower() != current_price.currency):
                    
                    # Create new price
                    new_price = stripe.Price.create(
                        product=product.stripe_product_id,
                        unit_amount=int(product.base_price * 100),  # Stripe uses cents
                        currency=product.currency.lower(),
                        active=product.is_active(),
                        metadata={
                            'product_id': str(product.id),
                        }
                    )
                    
                    # Update price ID in metadata
                    if not product.metadata:
                        product.metadata = {}
                    product.metadata['stripe_price_id'] = new_price.id
                    product.save(update_fields=['metadata'])
                    
                    logger.info(f"Created new price in Stripe: {new_price.id} for product: {product.stripe_product_id}")
            else:
                # No existing price, create one
                new_price = stripe.Price.create(
                    product=product.stripe_product_id,
                    unit_amount=int(product.base_price * 100),  # Stripe uses cents
                    currency=product.currency.lower(),
                    active=product.is_active(),
                    metadata={
                        'product_id': str(product.id),
                    }
                )
                
                # Update price ID in metadata
                if not product.metadata:
                    product.metadata = {}
                product.metadata['stripe_price_id'] = new_price.id
                product.save(update_fields=['metadata'])
                
                logger.info(f"Created price in Stripe: {new_price.id} for product: {product.stripe_product_id}")
            
            logger.info(f"Updated product in Stripe: {product.stripe_product_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating product in Stripe: {str(e)}")
            return False
    
    @staticmethod
    def sync_from_stripe(stripe_product_id: str) -> Optional[Product]:
        """
        Sync a product from Stripe to the local database.
        
        Args:
            stripe_product_id: The Stripe product ID to sync
            
        Returns:
            The synced Product model instance if successful, None otherwise
        """
        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe is not enabled. Skipping product sync from Stripe.")
            return None
            
        stripe = get_stripe()
        if not stripe:
            logger.error("Stripe API not available. Cannot sync product.")
            return None
            
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Retrieve product from Stripe
            stripe_product = stripe.Product.retrieve(stripe_product_id)
            
            # Find or create product in local database
            try:
                product = Product.objects.get(stripe_product_id=stripe_product_id)
                is_new = False
            except Product.DoesNotExist:
                product = Product(stripe_product_id=stripe_product_id)
                is_new = True
            
            # Update product details
            product.name = stripe_product.name
            product.description = stripe_product.description or ""
            product.status = Product.ACTIVE if stripe_product.active else Product.INACTIVE
            
            # Get prices for the product
            prices = stripe.Price.list(product=stripe_product_id, active=True, limit=1)
            
            if prices.data:
                # Use the first active price
                price = prices.data[0]
                product.base_price = price.unit_amount / 100  # Convert from cents
                product.currency = price.currency.upper()
                
                # Store price ID in metadata
                if not product.metadata:
                    product.metadata = {}
                product.metadata['stripe_price_id'] = price.id
            
            # Save the product
            product.save()
            
            if is_new:
                logger.info(f"Created product from Stripe: {stripe_product_id}")
            else:
                logger.info(f"Updated product from Stripe: {stripe_product_id}")
                
            return product
            
        except Exception as e:
            logger.error(f"Error syncing product from Stripe: {str(e)}")
            return None
    
    @staticmethod
    def delete_from_stripe(product: Product) -> bool:
        """
        Delete a product from Stripe.
        
        Args:
            product: The Product model instance to delete from Stripe
            
        Returns:
            True if the deletion was successful, False otherwise
        """
        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe is not enabled. Skipping product deletion in Stripe.")
            return False
            
        if not product.stripe_product_id:
            logger.warning(f"Product {product.id} does not have a Stripe product ID. Nothing to delete.")
            return True
            
        stripe = get_stripe()
        if not stripe:
            logger.error("Stripe API not available. Cannot delete product.")
            return False
            
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Archive product in Stripe instead of deleting
            stripe.Product.modify(
                product.stripe_product_id,
                active=False
            )
            
            logger.info(f"Archived product in Stripe: {product.stripe_product_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting product in Stripe: {str(e)}")
            return False
    
    @staticmethod
    def sync_all_to_stripe() -> Tuple[int, int, int]:
        """
        Sync all local products to Stripe.
        
        Returns:
            A tuple containing (created_count, updated_count, failed_count)
        """
        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe is not enabled. Skipping product sync to Stripe.")
            return (0, 0, 0)
            
        created = 0
        updated = 0
        failed = 0
        
        # Process all active products
        for product in Product.objects.filter(status=Product.ACTIVE):
            if not product.stripe_product_id:
                # Create product in Stripe
                if ProductService.create_in_stripe(product):
                    created += 1
                else:
                    failed += 1
            else:
                # Update product in Stripe
                if ProductService.update_in_stripe(product):
                    updated += 1
                else:
                    failed += 1
        
        logger.info(f"Synced products to Stripe: {created} created, {updated} updated, {failed} failed")
        return (created, updated, failed)
    
    @staticmethod
    def sync_all_from_stripe() -> int:
        """
        Sync all products from Stripe to the local database.
        
        This method retrieves all products from Stripe and creates or updates
        corresponding records in the local database.
        
        Returns:
            The number of products successfully synced
        """
        if not is_feature_enabled(get_env('STRIPE_ENABLED', 'False')):
            logger.warning("Stripe is not enabled. Skipping product sync from Stripe.")
            return 0
            
        stripe = get_stripe()
        if not stripe:
            logger.error("Stripe API not available. Cannot sync products.")
            return 0
            
        try:
            stripe.api_key = settings.STRIPE_SECRET_KEY
            
            # Retrieve all active products from Stripe
            stripe_products = stripe.Product.list(limit=100, active=True)
            
            # Also get inactive products
            stripe_inactive_products = stripe.Product.list(limit=100, active=False)
            
            # Combine the lists
            all_stripe_products = list(stripe_products.auto_paging_iter()) + list(stripe_inactive_products.auto_paging_iter())
            
            synced_count = 0
            
            # Process each Stripe product
            for stripe_product in all_stripe_products:
                try:
                    # Try to find corresponding product in database
                    try:
                        product = Product.objects.get(stripe_product_id=stripe_product.id)
                        # Product exists, update its details
                        product.name = stripe_product.name
                        product.description = stripe_product.description or ""
                        product.status = Product.ACTIVE if stripe_product.active else Product.INACTIVE
                        
                        # Set default values if not already populated
                        if not product.base_price or not product.currency:
                            # Get the price for this product
                            prices = stripe.Price.list(product=stripe_product.id, active=True, limit=1)
                            if prices and prices.data:
                                price = prices.data[0]
                                product.base_price = price.unit_amount / 100.0  # Convert cents to dollars
                                product.currency = price.currency.upper()
                        
                        if product.metadata is None:
                            product.metadata = {}
                            
                        # Store additional Stripe data in metadata
                        product.metadata.update({
                            'stripe_updated': stripe_product.updated,
                            'price_count': len(stripe.Price.list(product=stripe_product.id, limit=100).data)
                        })
                        
                        product.save()
                        logger.info(f"Updated product from Stripe: {stripe_product.id}")
                        
                    except Product.DoesNotExist:
                        # Product doesn't exist in database, create it
                        # Get the price for this product
                        prices = stripe.Price.list(product=stripe_product.id, active=True, limit=1)
                        
                        if prices and prices.data:
                            price = prices.data[0]
                            
                            # Create new product
                            product = Product(
                                name=stripe_product.name,
                                description=stripe_product.description or "",
                                status=Product.ACTIVE if stripe_product.active else Product.INACTIVE,
                                stripe_product_id=stripe_product.id,
                                base_price=price.unit_amount / 100.0,  # Convert cents to dollars
                                currency=price.currency.upper(),
                                metadata={
                                    'stripe_created': stripe_product.created,
                                    'stripe_updated': stripe_product.updated,
                                    'stripe_price_id': price.id,
                                    'price_count': len(stripe.Price.list(product=stripe_product.id, limit=100).data)
                                }
                            )
                            product.save()
                            logger.info(f"Created product from Stripe: {stripe_product.id}")
                        else:
                            # Skip products without active prices
                            logger.warning(f"Skipped product without active prices: {stripe_product.id}")
                            continue
                    
                    synced_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing Stripe product {stripe_product.id}: {str(e)}")
            
            logger.info(f"Synced {synced_count} products from Stripe")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing products from Stripe: {str(e)}")
            return 0