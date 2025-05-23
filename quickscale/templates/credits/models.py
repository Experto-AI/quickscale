from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

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
        """Consume credits from the account and return the transaction."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        with transaction.atomic():
            current_balance = self.get_balance()
            if current_balance < amount:
                raise InsufficientCreditsError(
                    f"Insufficient credits. Current balance: {current_balance}, Required: {amount}"
                )
            
            credit_transaction = CreditTransaction.objects.create(
                user=self.user,
                amount=-amount,  # Negative amount for consumption
                description=description,
                credit_type='CONSUMPTION'
            )
            self.updated_at = models.functions.Now()
            self.save(update_fields=['updated_at'])
            return credit_transaction

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create a credit account for the given user."""
        account, created = cls.objects.get_or_create(user=user)
        return account


class CreditTransaction(models.Model):
    """Model representing individual credit transactions."""
    
    CREDIT_TYPE_CHOICES = [
        ('PURCHASE', _('Purchase')),
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
    def is_consumption(self):
        """Check if this is a consumption transaction."""
        return self.credit_type == 'CONSUMPTION'

    @property
    def is_admin_adjustment(self):
        """Check if this is an admin adjustment transaction."""
        return self.credit_type == 'ADMIN'


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
    """Custom exception for insufficient credits."""
    pass 