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
from .models import CreditAccount, CreditTransaction, Service, ServiceUsage, UserSubscription, Payment, APIKey
from .forms import AdminCreditAdjustmentForm


@admin.register(UserSubscription)
class UserSubscriptionAdmin(admin.ModelAdmin):
    """Admin interface for UserSubscription model."""
    
    list_display = ('user', 'status', 'get_stripe_product_name', 'current_period_start', 'current_period_end', 'cancel_at_period_end', 'days_until_renewal')
    list_filter = ('status', 'cancel_at_period_end', 'current_period_start', 'current_period_end')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'stripe_subscription_id', 'stripe_product_id')
    readonly_fields = ('created_at', 'updated_at', 'days_until_renewal', 'get_stripe_product_name')
    ordering = ('-updated_at',)
    
    fieldsets = (
        (_('User Information'), {
            'fields': ('user',),
        }),
        (_('Subscription Details'), {
            'fields': ('status', 'stripe_subscription_id', 'stripe_product_id', 'get_stripe_product_name'),
        }),
        (_('Billing Information'), {
            'fields': ('current_period_start', 'current_period_end', 'days_until_renewal'),
        }),
        (_('Cancellation'), {
            'fields': ('cancel_at_period_end', 'canceled_at'),
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_stripe_product_name(self, obj):
        """Display the Stripe product name for this subscription."""
        stripe_product = obj.get_stripe_product()
        if stripe_product:
            return stripe_product.name
        return "Unknown Product"
    get_stripe_product_name.short_description = _('Product Name')

    def days_until_renewal(self, obj):
        """Display days until next billing period."""
        days = obj.days_until_renewal
        if days is None:
            return "No renewal date"
        elif days == 0:
            return "Expires today"
        elif days < 0:
            return "Expired"
        else:
            return f"{days} days"
    days_until_renewal.short_description = _('Days Until Renewal')


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    """Admin interface for CreditAccount model."""
    
    list_display = ('user', 'get_balance', 'get_subscription_status', 'created_at', 'updated_at', 'credit_actions')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'get_balance', 'get_balance_breakdown', 'get_subscription_status')
    ordering = ('-updated_at',)
    actions = ['bulk_add_credits']

    def get_balance(self, obj):
        """Display the current credit balance."""
        return f"{obj.get_balance()} credits"
    get_balance.short_description = _('Current Balance')

    def get_balance_breakdown(self, obj):
        """Display balance breakdown by credit type."""
        breakdown = obj.get_balance_by_type_available()
        return format_html(
            "Subscription: {} credits<br>Pay-as-you-go: {} credits<br><strong>Total: {} credits</strong>",
            breakdown['subscription'],
            breakdown['pay_as_you_go'],
            breakdown['total']
        )
    get_balance_breakdown.short_description = _('Balance Breakdown')

    def get_subscription_status(self, obj):
        """Display user's subscription status."""
        try:
            subscription = obj.user.subscription
            if subscription.is_active:
                return format_html('<span style="color: green;">Active ({})</span>', subscription.get_status_display())
            else:
                return format_html('<span style="color: red;">{}</span>', subscription.get_status_display())
        except UserSubscription.DoesNotExist:
            return "No subscription"
    get_subscription_status.short_description = _('Subscription Status')

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
                        description=f"Admin Credit Addition: {reason} (by {request.user.email})",
                        credit_type='ADMIN'
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
                            description=f"Admin Credit Removal: {reason} (by {request.user.email})",
                            credit_type='ADMIN'
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
                            description=f"Bulk Admin Credit Addition: {reason} (by {request.user.email})",
                            credit_type='ADMIN'
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
    
    list_display = ('user', 'amount', 'description', 'credit_type', 'expires_at', 'created_at', 'transaction_type')
    list_filter = ('created_at', 'credit_type', 'amount', 'expires_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'description')
    readonly_fields = ('created_at', 'is_expired')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Transaction Details'), {
            'fields': ('user', 'amount', 'description', 'credit_type'),
        }),
        (_('Expiration'), {
            'fields': ('expires_at', 'is_expired'),
        }),
        (_('System Information'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def transaction_type(self, obj):
        """Display transaction type based on description and amount."""
        if obj.credit_type == 'PURCHASE':
            return "Credit Purchase"
        elif obj.credit_type == 'SUBSCRIPTION':
            return "Subscription Credits"
        elif obj.credit_type == 'CONSUMPTION':
            return "Service Usage"
        elif obj.credit_type == 'ADMIN':
            if obj.amount > 0:
                return "Admin Addition"
            else:
                return "Admin Removal"
        return "Unknown"
    transaction_type.short_description = _('Transaction Type')

    def is_expired(self, obj):
        """Display if the credits have expired."""
        if obj.expires_at:
            if obj.is_expired:
                return format_html('<span style="color: red;">Expired</span>')
            else:
                return format_html('<span style="color: green;">Valid</span>')
        return "No expiration"
    is_expired.short_description = _('Expiration Status')

    def has_add_permission(self, request):
        """Disable adding transactions through admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable changing transactions through admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deleting transactions through admin."""
        return False


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    """Admin interface for Service model."""
    
    list_display = ('name', 'credit_cost', 'is_active', 'usage_count', 'created_at', 'updated_at')
    list_filter = ('is_active', 'created_at', 'credit_cost')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at', 'usage_count')
    ordering = ('name',)
    
    fieldsets = (
        (_('Service Information'), {
            'fields': ('name', 'description', 'credit_cost', 'is_active'),
        }),
        (_('Statistics'), {
            'fields': ('usage_count',),
            'classes': ('collapse',),
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def usage_count(self, obj):
        """Display the number of times this service has been used."""
        return obj.usages.count()
    usage_count.short_description = _('Usage Count')


@admin.register(ServiceUsage)
class ServiceUsageAdmin(admin.ModelAdmin):
    """Admin interface for ServiceUsage model."""
    
    list_display = ('user', 'service', 'get_credit_cost', 'created_at')
    list_filter = ('service', 'created_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'service__name')
    readonly_fields = ('created_at', 'get_credit_cost')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Usage Information'), {
            'fields': ('user', 'service', 'credit_transaction', 'get_credit_cost'),
        }),
        (_('System Information'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def get_credit_cost(self, obj):
        """Display the credit cost for this service usage."""
        return f"{abs(obj.credit_transaction.amount)} credits"
    get_credit_cost.short_description = _('Credits Used')

    def has_add_permission(self, request):
        """Disable adding service usage through admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable changing service usage through admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deleting service usage through admin."""
        return False


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    """Admin interface for Payment model."""
    
    list_display = ('user', 'amount', 'currency', 'payment_type', 'status', 'created_at')
    list_filter = ('created_at', 'payment_type', 'status', 'currency')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'stripe_payment_intent_id', 'description')
    readonly_fields = ('created_at', 'updated_at', 'receipt_data')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('Payment Information'), {
            'fields': ('user', 'amount', 'currency', 'payment_type', 'status', 'description'),
        }),
        (_('Stripe Information'), {
            'fields': ('stripe_payment_intent_id', 'stripe_subscription_id'),
        }),
        (_('Links'), {
            'fields': ('credit_transaction', 'subscription'),
        }),
        (_('Receipt'), {
            'fields': ('receipt_data',),
            'classes': ('collapse',),
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def has_add_permission(self, request):
        """Disable adding payments through admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Disable changing payments through admin."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Disable deleting payments through admin."""
        return False


@admin.register(APIKey)
class APIKeyAdmin(admin.ModelAdmin):
    """Admin interface for APIKey model."""
    
    list_display = ('user', 'name', 'prefix', 'is_active', 'is_expired_status', 'last_used_at', 'created_at')
    list_filter = ('is_active', 'created_at', 'last_used_at', 'expiry_date')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'name', 'prefix')
    readonly_fields = ('prefix', 'hashed_key', 'created_at', 'last_used_at', 'is_expired_status')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('API Key Information'), {
            'fields': ('user', 'name', 'prefix', 'is_active'),
        }),
        (_('Security'), {
            'fields': ('hashed_key',),
            'classes': ('collapse',),
        }),
        (_('Expiration'), {
            'fields': ('expiry_date', 'is_expired_status'),
        }),
        (_('Usage Information'), {
            'fields': ('last_used_at',),
        }),
        (_('System Information'), {
            'fields': ('created_at',),
            'classes': ('collapse',),
        }),
    )

    def is_expired_status(self, obj):
        """Display if the API key has expired."""
        if not obj.expiry_date:
            return "No expiration"
        elif obj.is_expired:
            return format_html('<span style="color: red;">Expired</span>')
        else:
            return format_html('<span style="color: green;">Valid</span>')
    is_expired_status.short_description = _('Expiration Status')

    def has_add_permission(self, request):
        """Disable adding API keys through admin interface."""
        # API keys should be generated through proper interface to ensure security
        return False

    def has_change_permission(self, request, obj=None):
        """Allow limited changes to API keys."""
        return True

    def get_readonly_fields(self, request, obj=None):
        """Make critical fields read-only."""
        readonly = list(self.readonly_fields)
        if obj:  # Editing existing object
            readonly.extend(['user'])  # Don't allow changing the user
        return readonly