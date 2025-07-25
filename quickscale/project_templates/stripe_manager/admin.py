from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import StripeProduct, StripeCustomer

@admin.register(StripeCustomer)
class StripeCustomerAdmin(admin.ModelAdmin):
    """Admin interface for StripeCustomer model."""
    
    list_display = ('user', 'email', 'name', 'stripe_id', 'created_at', 'updated_at')
    list_filter = ('created_at', 'updated_at')
    search_fields = ('user__email', 'user__first_name', 'user__last_name', 'email', 'name', 'stripe_id')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('-created_at',)
    
    fieldsets = (
        (_('User Information'), {
            'fields': ('user', 'email', 'name'),
        }),
        (_('Stripe Information'), {
            'fields': ('stripe_id',),
        }),
        (_('System Information'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        """Make user field readonly when editing existing customer."""
        readonly_fields = list(self.readonly_fields)
        if obj:  # Editing existing object
            readonly_fields.append('user')
        return readonly_fields

@admin.register(StripeProduct)
class StripeProductAdmin(admin.ModelAdmin):
    """Admin interface for StripeProduct model."""
    
    list_display = ('name', 'price', 'credit_amount', 'price_per_credit_display', 'currency', 'interval', 'active', 'display_order')
    list_filter = ('active', 'interval', 'currency')
    search_fields = ('name', 'description', 'stripe_id')
    ordering = ('display_order', 'name')
    readonly_fields = ('stripe_id', 'price_per_credit_display', 'created_at', 'updated_at')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'description', 'active'),
            'classes': ('wide',),
        }),
        (_('Pricing & Credits'), {
            'fields': ('price', 'currency', 'interval', 'credit_amount', 'price_per_credit_display'),
            'classes': ('wide',),
        }),
        (_('Display Settings'), {
            'fields': ('display_order',),
            'classes': ('wide',),
        }),
        (_('System Information'), {
            'fields': ('stripe_id', 'stripe_price_id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def price_per_credit_display(self, obj):
        """Display price per credit for this product."""
        return f"${obj.price_per_credit:.3f}" if obj.price_per_credit else "N/A"
    price_per_credit_display.short_description = _('Price per Credit')

    def get_urls(self):
        """Add custom URLs for admin actions."""
        urls = super().get_urls()
        custom_urls = [
            path(
                '<int:object_id>/sync-from-stripe/',
                self.sync_product_from_stripe,
                name='stripe_manager_stripeproduct_sync_from_stripe',
            ),
            path(
                'sync-all/',
                self.sync_all_products_view,
                name='stripe_manager_stripeproduct_sync_all',
            ),
        ]
        return custom_urls + urls

    def sync_product_from_stripe(self, request, object_id):
        """Handle product sync from Stripe."""
        try:
            product = self.get_object(request, object_id)
            from stripe_manager.stripe_manager import StripeManager
            stripe_manager = StripeManager.get_instance()
            synced_product = stripe_manager.sync_product_from_stripe(product.stripe_id, StripeProduct)
            
            if synced_product:
                self.message_user(
                    request,
                    _('Product successfully synced from Stripe.'),
                    messages.SUCCESS
                )
            else:
                self.message_user(
                    request,
                    _('Product sync completed but no changes were made.'),
                    messages.WARNING
                )
        except Exception as e:
            self.message_user(
                request,
                _('Error syncing product from Stripe: {}').format(str(e)),
                messages.ERROR
            )
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

    def get_actions(self, request):
        """Add custom admin actions."""
        actions = super().get_actions(request)
        actions['sync_selected_from_stripe'] = (
            self.sync_selected_from_stripe,
            'sync_selected_from_stripe',
            _('Sync selected products from Stripe')
        )
        return actions

    def sync_selected_from_stripe(self, request, queryset):
        """Sync multiple selected products from Stripe."""
        success_count = 0
        error_count = 0
        for product in queryset:
            try:
                from stripe_manager.stripe_manager import StripeManager
                stripe_manager = StripeManager.get_instance()
                synced_product = stripe_manager.sync_product_from_stripe(product.stripe_id, StripeProduct)
                if synced_product:
                    success_count += 1
                else:
                    error_count += 1
            except Exception:
                error_count += 1
        
        if success_count:
            self.message_user(
                request,
                _('Successfully synced {} products from Stripe.').format(success_count),
                messages.SUCCESS
            )
        if error_count:
            self.message_user(
                request,
                _('Failed to sync {} products from Stripe.').format(error_count),
                messages.ERROR
            )

    def sync_all_products_view(self, request):
        """Admin view to sync all products from Stripe."""
        from stripe_manager.stripe_manager import StripeManager
        try:
            sync_count = StripeManager.get_instance().sync_products_from_stripe(StripeProduct)
            self.message_user(
                request,
                _('Successfully synced {} products from Stripe.').format(sync_count),
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                _('Error syncing all products: {}').format(str(e)),
                messages.ERROR
            )
        # Redirect back to the changelist view
        return HttpResponseRedirect("../")

    def has_add_permission(self, request):
        """Disable adding products manually - they should be synced from Stripe."""
        return False

    def changelist_view(self, request, extra_context=None):
        """Add sync all button to changelist view."""
        if extra_context is None:
            extra_context = {}
        # Get the URL for the sync_all_products_view
        sync_all_url = reverse(f'admin:{self.model._meta.app_label}_{self.model._meta.model_name}_sync_all')
        extra_context['sync_all_url'] = sync_all_url
        # Pass the custom template name to the context
        extra_context['change_list_template'] = 'admin/stripe_manager/stripeproduct/change_list.html'
        return super().changelist_view(request, extra_context=extra_context) 