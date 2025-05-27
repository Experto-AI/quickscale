from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone

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
        
        return credit_account.add_credits(
            amount=Decimal(str(stripe_product.credit_amount)),
            description=description,
            credit_type='SUBSCRIPTION'
        )


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

    def get_balance_by_type(self) -> dict:
        """Get balance breakdown by credit type."""
        from django.db.models import Sum, Q
        
        subscription_balance = self.user.credit_transactions.filter(
            credit_type='SUBSCRIPTION'
        ).aggregate(balance=Sum('amount'))['balance'] or Decimal('0.00')
        
        pay_as_you_go_balance = self.user.credit_transactions.filter(
            credit_type__in=['PURCHASE', 'ADMIN']
        ).aggregate(balance=Sum('amount'))['balance'] or Decimal('0.00')
        
        return {
            'subscription': subscription_balance,
            'pay_as_you_go': pay_as_you_go_balance,
            'total': subscription_balance + pay_as_you_go_balance
        }

    def add_credits(self, amount: Decimal, description: str, credit_type: str = 'ADMIN') -> 'CreditTransaction':
        """Add credits to the account and return the transaction."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        with transaction.atomic():
            credit_transaction = CreditTransaction.objects.create(
                user=self.user,
                amount=amount,
                description=description,
                credit_type=credit_type
            )
            self.updated_at = models.functions.Now()
            self.save(update_fields=['updated_at'])
            return credit_transaction

    def consume_credits(self, amount: Decimal, description: str) -> 'CreditTransaction':
        """Consume credits from the account (simple version for backward compatibility)."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        current_balance = self.get_balance()
        if current_balance < amount:
            raise InsufficientCreditsError(
                f"Insufficient credits. Current balance: {current_balance}, Required: {amount}"
            )
        
        with transaction.atomic():
            credit_transaction = CreditTransaction.objects.create(
                user=self.user,
                amount=-amount,  # Negative amount for consumption
                description=description,
                credit_type='CONSUMPTION'
            )
            self.updated_at = models.functions.Now()
            self.save(update_fields=['updated_at'])
            return credit_transaction

    def consume_credits_with_priority(self, amount: Decimal, description: str) -> 'CreditTransaction':
        """Consume credits with priority: subscription credits first, then pay-as-you-go."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        with transaction.atomic():
            # Check if user has enough available balance
            available_balance = self.get_available_balance()
            if available_balance < amount:
                raise InsufficientCreditsError(
                    f"Insufficient credits. Current balance: {available_balance}, Required: {amount}"
                )
            
            # Create the consumption transaction
            # This is the simple, correct approach - just record the consumption as a single transaction
            # The balance calculation methods already handle the priority logic correctly
            credit_transaction = CreditTransaction.objects.create(
                user=self.user,
                amount=-amount,  # Negative amount for consumption
                description=description,
                credit_type='CONSUMPTION'
            )
            
            # Update account timestamp
            self.updated_at = models.functions.Now()
            self.save(update_fields=['updated_at'])
            
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
        from django.db.models import Sum, Q
        
        # Get all subscription credits (non-expired only) 
        subscription_credits = self.user.credit_transactions.filter(
            credit_type='SUBSCRIPTION',
            amount__gt=0
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get all pay-as-you-go credits (never expire)
        payg_credits = self.user.credit_transactions.filter(
            credit_type__in=['PURCHASE', 'ADMIN'],
            amount__gt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get total consumed credits
        total_consumed = abs(self.user.credit_transactions.filter(
            credit_type='CONSUMPTION',
            amount__lt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
        
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

    def get_balance_details(self) -> dict:
        """Get detailed balance breakdown with expiration information using priority consumption logic."""
        from django.db.models import Sum, Q
        
        # Get subscription credits with expiration info
        subscription_transactions = self.user.credit_transactions.filter(
            credit_type='SUBSCRIPTION',
            amount__gt=0
        ).filter(
            Q(expires_at__isnull=True) | Q(expires_at__gt=timezone.now())
        )
        
        subscription_amount = subscription_transactions.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Get earliest expiration date for subscription credits
        subscription_expiry = None
        if subscription_transactions.exists():
            earliest_expiry = subscription_transactions.filter(
                expires_at__isnull=False
            ).order_by('expires_at').first()
            if earliest_expiry:
                subscription_expiry = earliest_expiry.expires_at
        
        # Get pay-as-you-go credits (never expire)
        pay_as_you_go_amount = self.user.credit_transactions.filter(
            credit_type__in=['PURCHASE', 'ADMIN'],
            amount__gt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        # Get total consumed credits
        total_consumption = abs(self.user.credit_transactions.filter(
            credit_type='CONSUMPTION',
            amount__lt=0
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00'))
        
        # Apply consumption with priority: subscription credits first, then pay-as-you-go
        remaining_consumption = total_consumption
        
        # First consume from subscription credits
        subscription_consumed = min(subscription_amount, remaining_consumption)
        subscription_balance = subscription_amount - subscription_consumed
        remaining_consumption -= subscription_consumed
        
        # Then consume from pay-as-you-go credits
        payg_consumed = min(pay_as_you_go_amount, remaining_consumption)
        pay_as_you_go_balance = pay_as_you_go_amount - payg_consumed
        
        return {
            'subscription': {
                'amount': subscription_balance,
                'expires_at': subscription_expiry
            },
            'pay_as_you_go': {
                'amount': pay_as_you_go_balance,
                'expires_at': None
            },
            'total': subscription_balance + pay_as_you_go_balance
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

    @property
    def transactions(self):
        """Return related transactions for balance calculation."""
        return CreditTransaction.objects.filter(user=self.user)

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
        ]

    def __str__(self):
        """Return string representation of the service usage."""
        user_email = self.user.email if self.user else "No User"
        service_name = self.service.name if self.service else "No Service"
        return f"{user_email} used {service_name}"


class InsufficientCreditsError(Exception):
    """Exception raised when a user has insufficient credits for an operation."""
    pass 