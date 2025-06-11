from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

User = get_user_model()


class StripeProduct(models.Model):
    """Model representing Stripe products with local caching and enhanced metadata."""
    
    name = models.CharField(
        _('name'),
        max_length=255,
        help_text=_('Product name')
    )
    description = models.TextField(
        _('description'),
        blank=True,
        help_text=_('Product description')
    )
    price = models.DecimalField(
        _('price'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Product price')
    )
    currency = models.CharField(
        _('currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    interval = models.CharField(
        _('interval'),
        max_length=20,
        choices=[
            ('month', _('Monthly')),
            ('year', _('Yearly')),
            ('one-time', _('One-time')),
        ],
        default='one-time',
        help_text=_('Billing interval')
    )
    credit_amount = models.IntegerField(
        _('credit amount'),
        default=0,
        help_text=_('Number of credits this product provides')
    )
    display_order = models.IntegerField(
        _('display order'),
        default=0,
        help_text=_('Order for displaying products')
    )
    active = models.BooleanField(
        _('active'),
        default=True,
        help_text=_('Whether this product is currently available')
    )
    stripe_id = models.CharField(
        _('stripe id'),
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text=_('Stripe Product ID')
    )
    stripe_price_id = models.CharField(
        _('stripe price id'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Stripe Price ID')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('stripe product')
        verbose_name_plural = _('stripe products')
        ordering = ['display_order', 'name']
        indexes = [
            models.Index(fields=['stripe_id']),
            models.Index(fields=['active']),
            models.Index(fields=['interval']),
            models.Index(fields=['display_order']),
        ]

    def __str__(self):
        """Return string representation of the product."""
        name = self.name or "Unnamed Product"
        price = self.price or Decimal('0.00')
        return f"{name} - ${price}"

    @property
    def price_per_credit(self):
        """Calculate price per credit."""
        if self.credit_amount and self.credit_amount > 0:
            return self.price / self.credit_amount
        return Decimal('0.00')

    @property
    def is_subscription(self):
        """Check if this is a subscription product."""
        return self.interval in ['month', 'year']

    @property
    def is_one_time(self):
        """Check if this is a one-time purchase product."""
        return self.interval == 'one-time'


class StripeCustomer(models.Model):
    """Model representing Stripe customers linked to Django users."""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='stripe_customer',
        verbose_name=_('user')
    )
    stripe_id = models.CharField(
        _('stripe id'),
        max_length=255,
        unique=True,
        help_text=_('Stripe Customer ID')
    )
    email = models.EmailField(
        _('email'),
        help_text=_('Customer email address')
    )
    name = models.CharField(
        _('name'),
        max_length=255,
        blank=True,
        help_text=_('Customer name')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    updated_at = models.DateTimeField(
        _('updated at'),
        auto_now=True
    )

    class Meta:
        verbose_name = _('stripe customer')
        verbose_name_plural = _('stripe customers')
        indexes = [
            models.Index(fields=['stripe_id']),
            models.Index(fields=['email']),
        ]

    def __str__(self):
        """Return string representation of the customer."""
        email = self.email or "No Email"
        name = self.name or "No Name"
        return f"{name} ({email})" 