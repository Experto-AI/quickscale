from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _

class StripeProduct(models.Model):
    """Model for storing Stripe products with display configuration."""
    
    # Basic Info
    name = models.CharField(
        _('Name'),
        max_length=255,
        help_text=_('Product name as shown to customers')
    )
    description = models.TextField(
        _('Description'),
        blank=True,
        help_text=_('Product description')
    )
    active = models.BooleanField(
        _('Active'),
        default=True,
        help_text=_('Whether this product is available for purchase')
    )

    # Pricing
    price = models.DecimalField(
        _('Price'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text=_('Product price')
    )
    currency = models.CharField(
        _('Currency'),
        max_length=3,
        default='USD',
        help_text=_('Price currency (ISO 4217 code)')
    )
    interval = models.CharField(
        _('Billing Interval'),
        max_length=20,
        choices=[
            ('month', _('Monthly')),
            ('year', _('Yearly')),
            ('one-time', _('One Time')),
        ],
        default='month',
        help_text=_('Billing interval for subscription products')
    )

    # Display
    display_order = models.IntegerField(
        _('Display Order'),
        default=0,
        help_text=_('Order in which to display this product')
    )

    # System
    stripe_id = models.CharField(
        _('Stripe ID'),
        max_length=255,
        unique=True,
        help_text=_('Stripe product ID')
    )
    stripe_price_id = models.CharField(
        _('Stripe Price ID'),
        max_length=255,
        blank=True,
        default='',
        help_text=_('Stripe price ID')
    )
    created_at = models.DateTimeField(
        _('Created At'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('Updated At'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('Stripe Product')
        verbose_name_plural = _('Stripe Products')
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['stripe_id']),
            models.Index(fields=['active']),
            models.Index(fields=['display_order']),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_interval_display()})"

    def sync_with_stripe(self):
        """Sync product data with Stripe."""
        from stripe_manager.stripe_manager import StripeManager
        
        # Get the stripe manager instance
        stripe_manager = StripeManager.get_instance()
        
        # Sync this product to Stripe
        result = stripe_manager.sync_product_to_stripe(self)
        
        if result:
            stripe_product_id, stripe_price_id = result
            
            # If successful, ensure the local object has the Stripe IDs
            if stripe_product_id and self.stripe_id != stripe_product_id:
                self.stripe_id = stripe_product_id
            
            if stripe_price_id and self.stripe_price_id != stripe_price_id:
                self.stripe_price_id = stripe_price_id
                
            self.save()

    def clean(self):
        """Validate model data."""
        super().clean()
        # TODO: Add validation logic
        pass 