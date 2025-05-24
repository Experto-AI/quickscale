from django import forms
from django.core.validators import MinValueValidator
from django.utils.translation import gettext_lazy as _
from decimal import Decimal


class AdminCreditAdjustmentForm(forms.Form):
    """Form for admin credit adjustment operations."""
    
    amount = forms.DecimalField(
        label=_('Amount'),
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text=_('Enter the amount of credits to add or remove (must be positive)'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter amount (e.g., 100.00)',
            'step': '0.01',
            'min': '0.01'
        })
    )
    
    reason = forms.CharField(
        label=_('Reason'),
        max_length=255,
        help_text=_('Provide a reason for this credit adjustment'),
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'placeholder': 'Enter reason for credit adjustment...',
            'rows': 3,
            'maxlength': 255
        })
    )

    def clean_amount(self):
        """Validate that amount is positive."""
        amount = self.cleaned_data.get('amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError(_('Amount must be greater than zero.'))
        return amount

    def clean_reason(self):
        """Validate and clean the reason field."""
        reason = self.cleaned_data.get('reason', '').strip()
        if not reason:
            raise forms.ValidationError(_('Reason is required for credit adjustments.'))
        return reason 