from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal

User = get_user_model()


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
        return f"{self.user.email} - {self.get_balance()} credits"

    def get_balance(self) -> Decimal:
        """Calculate and return the current credit balance."""
        total = self.user.credit_transactions.aggregate(
            balance=models.Sum('amount')
        )['balance']
        return total or Decimal('0.00')

    def add_credits(self, amount: Decimal, description: str) -> 'CreditTransaction':
        """Add credits to the account and return the transaction."""
        if amount <= 0:
            raise ValueError("Amount must be positive")
        
        with transaction.atomic():
            credit_transaction = CreditTransaction.objects.create(
                user=self.user,
                amount=amount,
                description=description
            )
            self.updated_at = models.functions.Now()
            self.save(update_fields=['updated_at'])
            return credit_transaction

    @classmethod
    def get_or_create_for_user(cls, user):
        """Get or create a credit account for a user."""
        account, created = cls.objects.get_or_create(user=user)
        return account


class CreditTransaction(models.Model):
    """Model representing individual credit transactions."""
    
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
        ]

    def __str__(self):
        """Return string representation of the transaction."""
        return f"{self.user.email}: {self.amount} credits - {self.description}"

    @property
    def transactions(self):
        """Return related transactions for balance calculation."""
        return CreditTransaction.objects.filter(user=self.user) 