from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from django.shortcuts import render, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.utils.decorators import method_decorator
from django.views.decorators.http import require_http_methods
from django.utils.html import format_html
from decimal import Decimal
from .models import CreditAccount, CreditTransaction
from .forms import AdminCreditAdjustmentForm


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    """Admin interface for CreditAccount model."""
    
    list_display = ('user', 'get_balance', 'created_at', 'updated_at', 'credit_actions')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'get_balance')
    ordering = ('-updated_at',)
    actions = ['bulk_add_credits']

    def get_balance(self, obj):
        """Display the current credit balance."""
        return f"{obj.get_balance()} credits"
    get_balance.short_description = _('Current Balance')

    def credit_actions(self, obj):
        """Display action buttons for credit management."""
        add_url = reverse('admin:credits_add_credits', args=[obj.pk])
        remove_url = reverse('admin:credits_remove_credits', args=[obj.pk])
        return format_html(
            '<a href="{}" class="button" style="margin-right: 5px; padding: 2px 8px; font-size: 11px;">Add Credits</a>'
            '<a href="{}" class="button" style="padding: 2px 8px; font-size: 11px;">Remove Credits</a>',
            add_url, remove_url
        )
    credit_actions.short_description = _('Credit Actions')

    def get_urls(self):
        """Add custom URLs for credit management."""
        urls = super().get_urls()
        custom_urls = [
            path('<int:account_id>/add-credits/', 
                 self.admin_site.admin_view(self.add_credits_view), 
                 name='credits_add_credits'),
            path('<int:account_id>/remove-credits/', 
                 self.admin_site.admin_view(self.remove_credits_view), 
                 name='credits_remove_credits'),
        ]
        return custom_urls + urls

    def add_credits_view(self, request, account_id):
        """Admin view to add credits to a user account."""
        account = get_object_or_404(CreditAccount, pk=account_id)
        
        if request.method == 'POST':
            form = AdminCreditAdjustmentForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                reason = form.cleaned_data['reason']
                
                try:
                    transaction = account.add_credits(
                        amount=amount,
                        description=f"Admin Credit Addition: {reason} (by {request.user.email})"
                    )
                    messages.success(
                        request, 
                        f"Successfully added {amount} credits to {account.user.email}. "
                        f"New balance: {account.get_balance()} credits."
                    )
                    return HttpResponseRedirect(reverse('admin:credits_creditaccount_changelist'))
                except ValueError as e:
                    messages.error(request, f"Error adding credits: {e}")
        else:
            form = AdminCreditAdjustmentForm()

        context = {
            'form': form,
            'account': account,
            'current_balance': account.get_balance(),
            'action_type': 'Add',
            'title': f'Add Credits to {account.user.email}',
        }
        return render(request, 'admin/credits/credit_adjustment.html', context)

    def remove_credits_view(self, request, account_id):
        """Admin view to remove credits from a user account."""
        account = get_object_or_404(CreditAccount, pk=account_id)
        
        if request.method == 'POST':
            form = AdminCreditAdjustmentForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                reason = form.cleaned_data['reason']
                current_balance = account.get_balance()
                
                # Validate sufficient balance for removal
                if amount > current_balance:
                    messages.error(
                        request, 
                        f"Cannot remove {amount} credits. Current balance is only {current_balance} credits."
                    )
                else:
                    try:
                        transaction = account.add_credits(
                            amount=-amount,
                            description=f"Admin Credit Removal: {reason} (by {request.user.email})"
                        )
                        messages.success(
                            request, 
                            f"Successfully removed {amount} credits from {account.user.email}. "
                            f"New balance: {account.get_balance()} credits."
                        )
                        return HttpResponseRedirect(reverse('admin:credits_creditaccount_changelist'))
                    except ValueError as e:
                        messages.error(request, f"Error removing credits: {e}")
        else:
            form = AdminCreditAdjustmentForm()

        context = {
            'form': form,
            'account': account,
            'current_balance': account.get_balance(),
            'action_type': 'Remove',
            'title': f'Remove Credits from {account.user.email}',
        }
        return render(request, 'admin/credits/credit_adjustment.html', context)

    def bulk_add_credits(self, request, queryset):
        """Admin action to bulk add credits to multiple accounts."""
        if request.POST.get('post'):
            form = AdminCreditAdjustmentForm(request.POST)
            if form.is_valid():
                amount = form.cleaned_data['amount']
                reason = form.cleaned_data['reason']
                
                updated_count = 0
                for account in queryset:
                    try:
                        account.add_credits(
                            amount=amount,
                            description=f"Bulk Admin Credit Addition: {reason} (by {request.user.email})"
                        )
                        updated_count += 1
                    except ValueError:
                        continue
                
                self.message_user(
                    request, 
                    f"Successfully added {amount} credits to {updated_count} accounts."
                )
                return HttpResponseRedirect(request.get_full_path())
        else:
            form = AdminCreditAdjustmentForm()

        context = {
            'form': form,
            'queryset': queryset,
            'action_type': 'Bulk Add',
            'title': f'Bulk Add Credits to {len(queryset)} Accounts',
        }
        return render(request, 'admin/credits/bulk_credit_adjustment.html', context)

    bulk_add_credits.short_description = _('Add credits to selected accounts')


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    """Admin interface for CreditTransaction model."""
    
    list_display = ('user', 'amount', 'description', 'created_at', 'transaction_type')
    list_filter = ('created_at', 'amount')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'description')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Transaction Details'), {
            'fields': ('user', 'amount', 'description'),
        }),
        (_('System Information'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def transaction_type(self, obj):
        """Display transaction type based on description and amount."""
        if 'Admin Credit Addition' in obj.description:
            return "Admin Addition"
        elif 'Admin Credit Removal' in obj.description:
            return "Admin Removal"
        elif 'Bulk Admin Credit Addition' in obj.description:
            return "Bulk Admin Addition"
        elif obj.amount > 0:
            return "Credit Addition"
        else:
            return "Credit Consumption"
    transaction_type.short_description = _('Transaction Type')

    def has_add_permission(self, request):
        """Disable direct addition of transactions through admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable editing of transactions through admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deletion of transactions through admin for data integrity."""
        return False 