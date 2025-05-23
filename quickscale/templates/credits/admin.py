from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from .models import CreditAccount, CreditTransaction


@admin.register(CreditAccount)
class CreditAccountAdmin(admin.ModelAdmin):
    """Admin interface for CreditAccount model."""
    
    list_display = ('user', 'get_balance', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name')
    readonly_fields = ('created_at', 'updated_at', 'get_balance')
    ordering = ('-updated_at',)

    def get_balance(self, obj):
        """Display the current credit balance."""
        return f"{obj.get_balance()} credits"
    get_balance.short_description = _('Current Balance')


@admin.register(CreditTransaction)
class CreditTransactionAdmin(admin.ModelAdmin):
    """Admin interface for CreditTransaction model."""
    
    list_display = ('user', 'amount', 'description', 'created_at')
    list_filter = ('created_at',)
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