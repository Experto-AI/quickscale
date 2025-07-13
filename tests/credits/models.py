from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.contrib.auth.hashers import make_password, check_password
from django.core.exceptions import ValidationError
import secrets
import string

User = get_user_model()


class Service(models.Model):
    """Model representing services that consume credits."""
    
    name = models.CharField(
        _('name'),
        max_length=100,
        unique=True,
        help_text=_('Name of the service')
    )
    description = models.TextField(
        _('description'),
        help_text=_('Description of what this service does')
    )
    credit_cost = models.DecimalField(
        _('credit cost'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text=_('Number of credits required to use this service')
    )
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Whether this service is currently available for use')
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
        verbose_name = _('service')
        verbose_name_plural = _('services')
        ordering = ['name']

    def __str__(self):
        """Return string representation of the service."""
        name = self.name or "Unnamed Service"
        credit_cost = self.credit_cost or 0
        return f"{name} ({credit_cost} credits)"


class CreditAccount(models.Model):
    """Model representing a user's credit account with balance management."""
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='credit_account',
        verbose_name=_('user')
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
        verbose_name = _('credit account')
        verbose_name_plural = _('credit accounts')

    def __str__(self):
        """Return string representation of the credit account."""
        user_email = self.user.email if self.user else "No User"
        balance = self.get_balance()
        return f"{user_email} - {balance} credits"

    def get_balance(self) -> Decimal:
        """Calculate and return the current credit balance."""
        total = self.user.credit_transactions.aggregate(
            balance=models.Sum('amount')
        )['balance']
        return total or Decimal('0.00')

    def add_credits(self, amount: Decimal, description: str, credit_type: str = 'ADMIN', expires_at=None) -> 'CreditTransaction':
        """Add credits to the account and return the transaction."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if not description or description.strip() == "":
            raise ValueError("Description is required")
        
        # Set expiration for subscription credits if not provided
        if credit_type == 'SUBSCRIPTION' and expires_at is None:
            # Try to get user's current subscription to determine interval
            try:
                subscription = self.user.subscription
                stripe_product = subscription.get_stripe_product()
                
                if stripe_product and stripe_product.interval == 'year':
                    # Annual subscription: 365 days from now
                    expires_at = timezone.now() + timedelta(days=365)
                else:
                    # Monthly or unknown: 31 days from now (safe default)
                    expires_at = timezone.now() + timedelta(days=31)
            except:
                # No subscription or error: default to 31 days for subscription credits
                expires_at = timezone.now() + timedelta(days=31)
        
        with transaction.atomic():
            # Use select_for_update to prevent race conditions
            account = CreditAccount.objects.select_for_update().get(pk=self.pk)
            
            credit_transaction = CreditTransaction.objects.create(
                user=self.user,
                amount=amount,
                description=description.strip(),
                credit_type=credit_type,
                expires_at=expires_at
            )
            
            # Update account timestamp efficiently
            account.updated_at = models.functions.Now()
            account.save(update_fields=['updated_at'])
            
            return credit_transaction

    def consume_credits_with_priority(self, amount: Decimal, description: str) -> 'CreditTransaction':
        """Consume credits with priority: subscription credits first, then pay-as-you-go."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        if not description or description.strip() == "":
            raise ValueError("Description is required")
        
        with transaction.atomic():
            # Use select_for_update to prevent race conditions
            account = CreditAccount.objects.select_for_update().get(pk=self.pk)
            
            # Check if user has enough available balance
            available_balance = account.get_available_balance()
            if available_balance < amount:
                raise InsufficientCreditsError(
                    f"Insufficient credits. Available balance: {available_balance}, Required: {amount}"
                )
            
            # Create the consumption transaction
            credit_transaction = CreditTransaction.objects.create(
                user=self.user,
                amount=-amount,  # Negative amount for consumption
                description=description.strip(),
                credit_type='CONSUMPTION'
            )
            
            # Update account timestamp efficiently
            account.updated_at = models.functions.Now()
            account.save(update_fields=['updated_at'])
            
            return credit_transaction

    def get_available_balance(self) -> Decimal:
        """Get available balance excluding expired subscription credits."""
        from django.db.models import Sum, Q
        
        # Get all positive transactions (credits added)
        positive_transactions = self.user.credit_transactions.filter(amount__gt=0)
        
        # Filter out expired subscription credits
        available_transactions = positive_transactions.filter(
            Q(credit_type__in=['PURCHASE', 'ADMIN']) |  # Pay-as-you-go never expire
            Q(credit_type='SUBSCRIPTION', expires_at__isnull=True) |  # No expiration set
            Q(credit_type='SUBSCRIPTION', expires_at__gt=timezone.now())  # Not expired yet
        )
        
        # Calculate total available credits
        available_credits = available_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Subtract all consumption
        consumed_credits = self.user.credit_transactions.filter(
            amount__lt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        return available_credits + consumed_credits  # consumed_credits is negative

    def get_balance_by_type_available(self) -> dict:
        """Get balance breakdown by credit type, applying priority consumption logic."""
        from django.db.models import Sum, Q, Case, When, Value, DecimalField
        
        # Single query to get all necessary data with annotations
        transaction_summary = self.user.credit_transactions.aggregate(
            # Get non-expired subscription credits
            subscription_credits=Sum(
                Case(
                    When(
                        Q(credit_type='SUBSCRIPTION') & 
                        Q(amount__gt=0) & 
                        (Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())),
                        then='amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ),
            # Get pay-as-you-go credits (never expire)
            payg_credits=Sum(
                Case(
                    When(
                        Q(credit_type__in=['PURCHASE', 'ADMIN']) & Q(amount__gt=0),
                        then='amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            ),
            # Get total consumed credits
            total_consumed=Sum(
                Case(
                    When(
                        Q(credit_type='CONSUMPTION') & Q(amount__lt=0),
                        then='amount'
                    ),
                    default=Value(0),
                    output_field=DecimalField(max_digits=10, decimal_places=2)
                )
            )
        )
        
        subscription_credits = transaction_summary['subscription_credits'] or Decimal('0.00')
        payg_credits = transaction_summary['payg_credits'] or Decimal('0.00')
        total_consumed = abs(transaction_summary['total_consumed'] or Decimal('0.00'))
        
        # Apply consumption with priority: subscription credits first, then pay-as-you-go
        remaining_consumption = total_consumed
        
        # First consume from subscription credits
        subscription_consumed = min(subscription_credits, remaining_consumption)
        subscription_balance = subscription_credits - subscription_consumed
        remaining_consumption -= subscription_consumed
        
        # Then consume from pay-as-you-go credits
        payg_consumed = min(payg_credits, remaining_consumption)
        payg_balance = payg_credits - payg_consumed
        
        return {
            'subscription': subscription_balance,
            'pay_as_you_go': payg_balance,
            'total': subscription_balance + payg_balance
        }

    def cleanup_expired_credits(self) -> int:
        """Clean up expired subscription credits."""
        from django.db.models import Q
        
        # Find expired subscription credits
        expired_transactions = self.user.credit_transactions.filter(
            credit_type='SUBSCRIPTION',
            expires_at__isnull=False,
            expires_at__lte=timezone.now()
        )
        
        return expired_transactions.count()

    def get_expiring_credits(self, days_ahead: int = 7) -> dict:
        """Get credits that will expire soon."""
        from django.db.models import Sum
        
        cutoff_date = timezone.now() + timedelta(days=days_ahead)
        
        expiring_transactions = self.user.credit_transactions.filter(
            credit_type='SUBSCRIPTION',
            expires_at__isnull=False,
            expires_at__gt=timezone.now(),
            expires_at__lte=cutoff_date
        )
        
        total_amount = expiring_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Group by expiration date
        by_date = {}
        for transaction in expiring_transactions:
            date_key = transaction.expires_at.date()
            if date_key not in by_date:
                by_date[date_key] = Decimal('0.00')
            by_date[date_key] += transaction.amount
        
        return {
            'total_amount': total_amount,
            'transaction_count': expiring_transactions.count(),
            'by_date': by_date
        }

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create a credit account for the given user."""
        account, created = cls.objects.get_or_create(user=user)
        return account


class CreditTransaction(models.Model):
    """Model representing individual credit transactions."""
    
    CREDIT_TYPE_CHOICES = [
        ('PURCHASE', _('Purchase')),
        ('SUBSCRIPTION', _('Subscription')),
        ('CONSUMPTION', _('Consumption')),
        ('ADMIN', _('Admin Adjustment')),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='credit_transactions',
        verbose_name=_('user')
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Credit amount (positive for additions, negative for consumption)')
    )
    description = models.CharField(
        _('description'),
        max_length=255,
        help_text=_('Description of the transaction')
    )
    credit_type = models.CharField(
        _('credit type'),
        max_length=20,
        choices=CREDIT_TYPE_CHOICES,
        default='ADMIN',
        help_text=_('Type of credit transaction')
    )
    expires_at = models.DateTimeField(
        _('expires at'),
        null=True,
        blank=True,
        help_text=_('When these credits expire (for subscription credits)')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('credit transaction')
        verbose_name_plural = _('credit transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['-created_at']),
            models.Index(fields=['credit_type']),
            models.Index(fields=['expires_at']),
        ]

    def __str__(self):
        """Return string representation of the transaction."""
        user_email = self.user.email if self.user else "No User"
        amount = self.amount or Decimal('0.00')
        description = self.description or "No description"
        return f"{user_email}: {amount} credits - {description}"

    def clean(self):
        """Validate transaction data and enforce business rules."""
        # Validate amount based on credit type
        if self.credit_type == 'CONSUMPTION' and self.amount >= 0:
            raise ValidationError({
                'amount': _('Consumption transactions must have negative amounts')
            })
        
        if self.credit_type in ['PURCHASE', 'SUBSCRIPTION', 'ADMIN'] and self.amount <= 0:
            raise ValidationError({
                'amount': _('Credit addition transactions must have positive amounts')
            })
        
        # Validate expiration logic
        if self.credit_type == 'SUBSCRIPTION' and not self.expires_at:
            raise ValidationError({
                'expires_at': _('Subscription credits must have an expiration date')
            })
        
        if self.credit_type in ['PURCHASE', 'ADMIN'] and self.expires_at:
            raise ValidationError({
                'expires_at': _('Pay-as-you-go and admin credits should not have expiration dates')
            })
        
        # Validate expiration date is in the future
        if self.expires_at and self.expires_at <= timezone.now():
            raise ValidationError({
                'expires_at': _('Expiration date must be in the future')
            })

    def save(self, *args, **kwargs):
        """Override save to run validation."""
        self.clean()
        super().save(*args, **kwargs)

    @property
    def is_purchase(self):
        """Check if this is a purchase transaction."""
        return self.credit_type == 'PURCHASE'

    @property
    def is_subscription(self):
        """Check if this is a subscription transaction."""
        return self.credit_type == 'SUBSCRIPTION'

    @property
    def is_consumption(self):
        """Check if this is a consumption transaction."""
        return self.credit_type == 'CONSUMPTION'

    @property
    def is_admin_adjustment(self):
        """Check if this is an admin adjustment transaction."""
        return self.credit_type == 'ADMIN'

    @property
    def is_expired(self):
        """Check if these credits have expired."""
        if not self.expires_at:
            return False
        return timezone.now() > self.expires_at


class ServiceUsage(models.Model):
    """Model for tracking service usage by users."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='service_usages',
        verbose_name=_('user')
    )
    service = models.ForeignKey(
        Service,
        on_delete=models.CASCADE,
        related_name='usages',
        verbose_name=_('service')
    )
    credit_transaction = models.ForeignKey(
        CreditTransaction,
        on_delete=models.CASCADE,
        related_name='service_usage',
        verbose_name=_('credit transaction')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )

    class Meta:
        verbose_name = _('service usage')
        verbose_name_plural = _('service usages')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['service', '-created_at']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        """Return string representation of the service usage."""
        user_email = self.user.email if self.user else "No User"
        service_name = self.service.name if self.service else "No Service"
        return f"{user_email} used {service_name}"


class APIKey(models.Model):
    """Model representing API keys for authentication with secure hashing."""
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='api_keys',
        verbose_name=_('user')
    )
    prefix = models.CharField(
        _('prefix'),
        max_length=8,
        db_index=True,
        help_text=_('Short prefix for API key identification')
    )
    hashed_key = models.CharField(
        _('hashed key'),
        max_length=128,
        help_text=_('Hashed secret part of the API key')
    )
    name = models.CharField(
        _('name'),
        max_length=100,
        blank=True,
        help_text=_('Optional name for this API key')
    )
    created_at = models.DateTimeField(
        _('created at'),
        auto_now_add=True
    )
    last_used_at = models.DateTimeField(
        _('last used at'),
        null=True,
        blank=True,
        help_text=_('When this API key was last used')
    )
    is_active = models.BooleanField(
        _('is active'),
        default=True,
        help_text=_('Whether this API key is currently active')
    )
    expiry_date = models.DateTimeField(
        _('expiry date'),
        null=True,
        blank=True,
        help_text=_('Optional expiration date for this API key')
    )

    class Meta:
        verbose_name = _('API key')
        verbose_name_plural = _('API keys')
        indexes = [
            models.Index(fields=['prefix']),
            models.Index(fields=['user', 'is_active']),
            models.Index(fields=['is_active', 'expiry_date']),
        ]

    def __str__(self):
        """Return string representation of the API key."""
        user_email = self.user.email if self.user else "No User"
        name = self.name or "Unnamed API Key"
        status = "Active" if self.is_active else "Inactive"
        return f"{user_email} - {name} ({status})"

    @classmethod
    def generate_key(cls):
        """Generate a new API key with prefix and secret parts."""
        # Generate 4-character prefix (letters and numbers)
        prefix_chars = string.ascii_uppercase + string.digits
        prefix = ''.join(secrets.choice(prefix_chars) for _ in range(4))
        
        # Generate 32-character secret key (letters, numbers, and safe symbols)
        secret_chars = string.ascii_letters + string.digits + '_-'
        secret_key = ''.join(secrets.choice(secret_chars) for _ in range(32))
        
        # Return full key in format prefix.secret_key
        full_key = f"{prefix}.{secret_key}"
        return full_key, prefix, secret_key

    @classmethod
    def get_hashed_key(cls, secret_key):
        """Hash a secret key using Django's password hashers."""
        return make_password(secret_key)

    def update_last_used(self):
        """Update the last_used_at timestamp."""
        self.last_used_at = timezone.now()
        self.save(update_fields=['last_used_at'])

    def verify_secret_key(self, secret_key):
        """Verify a secret key against the stored hash."""
        return check_password(secret_key, self.hashed_key)

    @property
    def is_expired(self):
        """Check if this API key has expired."""
        if not self.expiry_date:
            return False
        return timezone.now() > self.expiry_date

    @property
    def is_valid(self):
        """Check if this API key is currently valid (active and not expired)."""
        return self.is_active and not self.is_expired


class UserSubscription(models.Model):
    """Model representing a user's subscription status and billing information."""
    
    STATUS_CHOICES = [
        ('active', _('Active')),
        ('canceled', _('Canceled')),
        ('past_due', _('Past Due')),
        ('unpaid', _('Unpaid')),
        ('incomplete', _('Incomplete')),
        ('incomplete_expired', _('Incomplete Expired')),
        ('trialing', _('Trialing')),
        ('paused', _('Paused')),
    ]
    
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='subscription',
        verbose_name=_('user')
    )
    stripe_subscription_id = models.CharField(
        _('stripe subscription id'),
        max_length=255,
        unique=True,
        blank=True,
        null=True,
        help_text=_('Stripe subscription ID')
    )
    stripe_product_id = models.CharField(
        _('stripe product id'),
        max_length=255,
        blank=True,
        help_text=_('Stripe product ID for this subscription')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='incomplete',
        help_text=_('Current subscription status')
    )
    current_period_start = models.DateTimeField(
        _('current period start'),
        null=True,
        blank=True,
        help_text=_('Start of the current billing period')
    )
    current_period_end = models.DateTimeField(
        _('current period end'),
        null=True,
        blank=True,
        help_text=_('End of the current billing period')
    )
    cancel_at_period_end = models.BooleanField(
        _('cancel at period end'),
        default=False,
        help_text=_('Whether the subscription will cancel at the end of the current period')
    )
    canceled_at = models.DateTimeField(
        _('canceled at'),
        null=True,
        blank=True,
        help_text=_('When the subscription was canceled')
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
        verbose_name = _('user subscription')
        verbose_name_plural = _('user subscriptions')
        indexes = [
            models.Index(fields=['stripe_subscription_id']),
            models.Index(fields=['status']),
            models.Index(fields=['current_period_end']),
        ]

    def __str__(self):
        """Return string representation of the subscription."""
        user_email = self.user.email if self.user else "No User"
        status = self.get_status_display()
        return f"{user_email} - {status}"

    @property
    def is_active(self):
        """Check if the subscription is currently active."""
        return self.status in ['active', 'trialing']

    @property
    def days_until_renewal(self):
        """Calculate days until next billing period."""
        if not self.current_period_end:
            return None
        
        now = timezone.now()
        if self.current_period_end > now:
            delta = self.current_period_end - now
            return delta.days
        return 0

    def get_stripe_product(self):
        """Get the associated StripeProduct for this subscription."""
        if not self.stripe_product_id:
            return None
        
        from stripe_manager.models import StripeProduct
        try:
            return StripeProduct.objects.get(stripe_id=self.stripe_product_id)
        except StripeProduct.DoesNotExist:
            return None

    def allocate_monthly_credits(self):
        """Allocate monthly credits for this subscription period."""
        if not self.is_active:
            return None
        
        stripe_product = self.get_stripe_product()
        if not stripe_product:
            return None
        
        # Create credit transaction for monthly allocation
        credit_account = CreditAccount.get_or_create_for_user(self.user)
        description = f"Monthly credits allocation - {stripe_product.name}"
        
        # Calculate expiration date based on current period end
        expires_at = self.current_period_end
        if not expires_at:
            # Intelligent fallback based on actual billing interval from Stripe
            now = timezone.now()
            
            if stripe_product.interval == 'month':
                # Monthly subscription: 31 days from now (favorable to user)
                expires_at = now + timedelta(days=31)
            elif stripe_product.interval == 'year':
                # Annual subscription: 365 days from now
                expires_at = now + timedelta(days=365)
            else:
                # One-time or unknown: default to 31 days (safe choice)
                expires_at = now + timedelta(days=31)
        
        with transaction.atomic():
            return credit_account.add_credits(
                amount=Decimal(str(stripe_product.credit_amount)),
                description=description,
                credit_type='SUBSCRIPTION',
                expires_at=expires_at
            )


class Payment(models.Model):
    """Model for tracking all payment transactions."""
    
    PAYMENT_TYPE_CHOICES = [
        ('CREDIT_PURCHASE', _('Credit Purchase')),
        ('SUBSCRIPTION', _('Subscription')),
        ('REFUND', _('Refund')),
    ]
    
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('succeeded', _('Succeeded')),
        ('failed', _('Failed')),
        ('refunded', _('Refunded')),
        ('cancelled', _('Cancelled')),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='payments',
        verbose_name=_('user')
    )
    stripe_payment_intent_id = models.CharField(
        _('stripe payment intent id'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Stripe Payment Intent ID')
    )
    stripe_subscription_id = models.CharField(
        _('stripe subscription id'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Stripe Subscription ID (for subscription payments)')
    )
    stripe_invoice_id = models.CharField(
        _('stripe invoice id'),
        max_length=255,
        blank=True,
        null=True,
        help_text=_('Stripe Invoice ID (for immediate charges like plan changes)')
    )
    amount = models.DecimalField(
        _('amount'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Payment amount in the specified currency')
    )
    currency = models.CharField(
        _('currency'),
        max_length=3,
        default='USD',
        help_text=_('Currency code (ISO 4217)')
    )
    payment_type = models.CharField(
        _('payment type'),
        max_length=20,
        choices=PAYMENT_TYPE_CHOICES,
        help_text=_('Type of payment')
    )
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending',
        help_text=_('Payment status')
    )
    description = models.CharField(
        _('description'),
        max_length=255,
        help_text=_('Payment description')
    )
    receipt_data = models.JSONField(
        _('receipt data'),
        blank=True,
        null=True,
        help_text=_('Receipt information in JSON format')
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
        verbose_name = _('payment')
        verbose_name_plural = _('payments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['status']),
            models.Index(fields=['payment_type']),
            models.Index(fields=['stripe_payment_intent_id']),
            models.Index(fields=['-created_at']),
        ]

    def __str__(self):
        """Return string representation of the payment."""
        user_email = self.user.email if self.user else "No User"
        amount = self.amount or Decimal('0.00')
        status = self.get_status_display()
        return f"{user_email}: ${amount} ({status})"

    @property
    def is_succeeded(self):
        """Check if the payment was successful."""
        return self.status == 'succeeded'


class InsufficientCreditsError(Exception):
    """Exception raised when a user has insufficient credits."""
    pass