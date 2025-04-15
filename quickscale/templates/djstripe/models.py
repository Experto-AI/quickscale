"""
Django Stripe Models

This module can contain custom models extending the djstripe package.
Most models will be provided by the djstripe package itself.
"""

# Import Django base models
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _

# Placeholder for future custom models extending djstripe
# For example:

# class CustomerProxy(djstripe.models.Customer):
#     """
#     Proxy model for djstripe Customer to add custom methods.
#     """
#     class Meta:
#         proxy = True
#
#     def get_subscription_status(self):
#         # Custom method example
#         pass


class Product(models.Model):
    """
    Model representing a purchasable product or service.
    
    This model stores information about products that can be purchased
    through Stripe, including pricing details and product status.
    """
    # Basic product information
    name = models.CharField(
        _('name'),
        max_length=255,
        help_text=_('Product name')
    )
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Detailed product description')
    )
    image = models.ImageField(
        _('image'),
        upload_to='product_images',
        blank=True,
        null=True,
        help_text=_('Product image')
    )
    
    # Price configuration
    base_price = models.DecimalField(
        _('base price'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Base price of the product')
    )
    currency = models.CharField(
        _('currency'),
        max_length=3,
        default='USD',
        help_text=_('Three-letter currency code (e.g., USD, EUR)')
    )
    
    # Product status
    ACTIVE = 'active'
    INACTIVE = 'inactive'
    STATUS_CHOICES = (
        (ACTIVE, _('Active')),
        (INACTIVE, _('Inactive')),
    )
    status = models.CharField(
        _('status'),
        max_length=10,
        choices=STATUS_CHOICES,
        default=ACTIVE,
        help_text=_('Product availability status')
    )
    
    # Metadata and timestamps
    created = models.DateTimeField(
        _('created'),
        auto_now_add=True,
        help_text=_('Date and time when the product was created')
    )
    updated = models.DateTimeField(
        _('updated'),
        auto_now=True,
        help_text=_('Date and time when the product was last updated')
    )
    
    # Additional product metadata
    stripe_product_id = models.CharField(
        _('stripe product ID'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Associated Stripe product identifier, if applicable')
    )
    metadata = models.JSONField(
        _('metadata'),
        blank=True,
        null=True,
        help_text=_('Additional product metadata stored as JSON')
    )
    
    class Meta:
        verbose_name = _('product')
        verbose_name_plural = _('products')
        ordering = ['-created']
    
    def __str__(self):
        """Return string representation of the product."""
        return self.name
    
    def is_active(self):
        """Check if the product is active."""
        return self.status == self.ACTIVE
    
    def get_formatted_price(self):
        """Return the formatted price with currency symbol."""
        # Simple currency symbol mapping for common currencies
        currency_symbols = {
            'USD': '$',
            'EUR': '€',
            'GBP': '£',
            'JPY': '¥',
            'AUD': 'A$',
            'CAD': 'C$',
        }
        
        symbol = currency_symbols.get(self.currency, self.currency)
        
        if self.currency == 'JPY':  # JPY doesn't use decimal places
            return f"{symbol}{int(self.base_price)}"
        
        return f"{symbol}{self.base_price:.2f}" 