from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.urls import path, reverse
from django.http import HttpResponseRedirect
from django.contrib import messages
from .models import StripeProduct

@admin.register(StripeProduct)
class StripeProductAdmin(admin.ModelAdmin):
    """Admin interface for StripeProduct model."""
    
    list_display = ('name', 'price', 'currency', 'interval', 'active', 'display_order')
    list_filter = ('active', 'interval', 'currency')
    search_fields = ('name', 'description', 'stripe_id')
    ordering = ('display_order', 'name')
    readonly_fields = ('stripe_id', 'created_at', 'updated_at')
    
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'description', 'active'),
            'classes': ('wide',),
        }),
        (_('Pricing'), {
            'fields': ('price', 'currency', 'interval'),
            'classes': ('wide',),
        }),
        (_('Display Settings'), {
            'fields': ('display_order',),
            'classes': ('wide',),
        }),
        (_('System Information'), {
            'fields': ('stripe_id', 'created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )

    def get_urls(self):
        """Add custom URLs for sync functionality."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'sync_all/',
                self.admin_site.admin_view(self.sync_all_products_view),
                name='%s_%s_sync_all' % (
                    self.model._meta.app_label,
                    self.model._meta.model_name
                ),
            ),
            path(
                '<path:object_id>/sync/',
                self.admin_site.admin_view(self.sync_product),
                name='stripe_product_sync',
            ),
        ]
        return custom_urls + urls

    def sync_product(self, request, object_id):
        """Handle product sync with Stripe."""
        try:
            product = self.get_object(request, object_id)
            product.sync_with_stripe()
            self.message_user(
                request,
                _('Product successfully synced with Stripe.'),
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                _('Error syncing product: %s') % str(e),
                messages.ERROR
            )
        return HttpResponseRedirect(request.META.get('HTTP_REFERER', '/'))

    def get_actions(self, request):
        """Add custom admin actions."""
        actions = super().get_actions(request)
        actions['sync_selected'] = (
            self.sync_selected,
            'sync_selected',
            _('Sync selected products with Stripe')
        )
        return actions

    def sync_selected(self, request, queryset):
        """Sync multiple selected products with Stripe."""
        success_count = 0
        error_count = 0
        for product in queryset:
            try:
                product.sync_with_stripe()
                success_count += 1
            except Exception:
                error_count += 1
        
        if success_count:
            self.message_user(
                request,
                _('Successfully synced %d products.') % success_count,
                messages.SUCCESS
            )
        if error_count:
            self.message_user(
                request,
                _('Failed to sync %d products.') % error_count,
                messages.ERROR
            )

    def sync_all_products_view(self, request):
        """Admin view to sync all products from Stripe."""
        from stripe_manager.stripe_manager import StripeManager
        try:
            sync_count = StripeManager.get_instance().sync_products_from_stripe(StripeProduct)
            self.message_user(
                request,
                _('Successfully synced %d products from Stripe.') % sync_count,
                messages.SUCCESS
            )
        except Exception as e:
            self.message_user(
                request,
                _('Error syncing all products: %s') % str(e),
                messages.ERROR
            )
        # Redirect back to the changelist view
        return HttpResponseRedirect("../")

    def changelist_view(self, request, extra_context=None):
        """Add sync all button to changelist view."""
        if extra_context is None:
            extra_context = {}
        # Get the URL for the sync_all_products_view
        sync_all_url = reverse('admin:%s_%s_sync_all' % (
            self.model._meta.app_label,
            self.model._meta.model_name
        ))
        extra_context['sync_all_url'] = sync_all_url
        # Pass the custom template name to the context
        extra_context['change_list_template'] = 'admin/stripe_manager/stripeproduct/change_list.html'
        return super().changelist_view(request, extra_context=extra_context) 