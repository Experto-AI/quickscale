from django.db import models
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

User = get_user_model()


class StripeCustomer(models.Model):
    """Model for linking Django users with Stripe customers."""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='stripe_customer',
        verbose_name=_('User')
    )
    stripe_id = models.CharField(
        _('Stripe Customer ID'),
        max_length=255,
        unique=True,
        blank=True,
        help_text=_('Stripe customer ID')
    )
    email = models.EmailField(
        _('Email'),
        help_text=_('Email address used in Stripe')
    )
    name = models.CharField(
        _('Name'),
        max_length=255,
        blank=True,
        help_text=_('Customer name in Stripe')
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
        verbose_name = _('Stripe Customer')
        verbose_name_plural = _('Stripe Customers')
        indexes = [
            models.Index(fields=['stripe_id']),
            models.Index(fields=['user']),
        ]

    def __str__(self):
        return f"{self.user.email} ({self.stripe_id or 'No Stripe ID'})"


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

    # Credit Configuration
    credit_amount = models.IntegerField(
        _('Credit Amount'),
        validators=[MinValueValidator(1)],
        default=1000,
        help_text=_('Number of credits provided by this product')
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

    @property
    def price_per_credit(self):
        """Calculate price per credit for this product."""
        if self.credit_amount and self.credit_amount > 0 and self.price:
            return self.price / self.credit_amount
        return 0

    @property
    def is_subscription(self):
        """Check if this is a subscription product."""
        return self.interval in ['month', 'year']

    @property
    def is_one_time(self):
        """Check if this is a one-time purchase product."""
        return self.interval == 'one-time'

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