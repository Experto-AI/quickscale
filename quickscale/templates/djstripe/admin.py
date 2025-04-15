"""
Django Stripe Admin Configuration

This module contains any custom admin interfaces for Django Stripe models.
Most admin interfaces will be provided by the djstripe package itself.
"""

from django.contrib import admin
from django.contrib import messages
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import Product
from .services import ProductService

# Example of registering a custom admin interface for a model:
# 
# from djstripe.models import Customer
# 
# @admin.register(Customer)
# class CustomerAdmin(admin.ModelAdmin):
#     """
#     Custom admin interface for Stripe Customer model.
#     """
#     list_display = ('email', 'description', 'created', 'livemode')
#     search_fields = ('email', 'description')
#     readonly_fields = ('email', 'created')

@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    """
    Admin interface for Product model.
    """
    list_display = ('name', 'get_formatted_price', 'currency', 'status', 'stripe_status', 'created', 'updated')
    list_filter = ('status', 'currency', 'created', 'updated')
    search_fields = ('name', 'description', 'stripe_product_id')
    readonly_fields = ('created', 'updated', 'stripe_status')
    actions = ['sync_selected_to_stripe', 'sync_selected_from_stripe', 'mark_selected_as_inactive']
    
    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'description', 'image', 'status')
        }),
        ('Pricing', {
            'fields': ('base_price', 'currency')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_product_id', 'stripe_status', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        """Customize the queryset."""
        queryset = super().get_queryset(request)
        return queryset.order_by('-updated')  # Show most recently updated first
    
    def stripe_status(self, obj):
        """Display the Stripe sync status with colored indicators."""
        if obj.stripe_product_id:
            return format_html(
                '<span style="color: green; font-weight: bold;">✓</span> Synced (ID: {})',
                obj.stripe_product_id
            )
        return format_html(
            '<span style="color: orange;">○</span> Not synced with Stripe'
        )
    stripe_status.short_description = _('Stripe Status')
    
    def sync_selected_to_stripe(self, request, queryset):
        """Sync selected products to Stripe."""
        created = 0
        updated = 0
        failed = 0
        
        for product in queryset:
            if not product.stripe_product_id:
                # Create in Stripe
                if ProductService.create_in_stripe(product):
                    created += 1
                else:
                    failed += 1
            else:
                # Update in Stripe
                if ProductService.update_in_stripe(product):
                    updated += 1
                else:
                    failed += 1
        
        # Show summary message
        if created > 0 or updated > 0:
            self.message_user(
                request,
                f"{created} products created and {updated} products updated in Stripe. {failed} operations failed.",
                messages.SUCCESS if failed == 0 else messages.WARNING
            )
        else:
            self.message_user(
                request,
                f"No products were synced to Stripe. {failed} operations failed.",
                messages.WARNING if failed > 0 else messages.ERROR
            )
    sync_selected_to_stripe.short_description = _('Sync selected products to Stripe')
    
    def sync_selected_from_stripe(self, request, queryset):
        """Sync selected products from Stripe."""
        updated = 0
        failed = 0
        not_synced = 0
        
        for product in queryset:
            if product.stripe_product_id:
                # Sync from Stripe
                stripe_product = ProductService.sync_from_stripe(product.stripe_product_id)
                if stripe_product:
                    updated += 1
                else:
                    failed += 1
            else:
                not_synced += 1
        
        # Show summary message
        if updated > 0:
            self.message_user(
                request,
                f"{updated} products updated from Stripe. {failed} operations failed. {not_synced} products were not synced (no Stripe ID).",
                messages.SUCCESS if failed == 0 else messages.WARNING
            )
        else:
            self.message_user(
                request,
                f"No products were synced from Stripe. {failed} operations failed. {not_synced} products had no Stripe ID.",
                messages.WARNING if failed > 0 else messages.ERROR
            )
    sync_selected_from_stripe.short_description = _('Update selected products from Stripe')
    
    def mark_selected_as_inactive(self, request, queryset):
        """Mark selected products as inactive."""
        updated = queryset.update(status=Product.INACTIVE)
        
        # Show summary message
        if updated > 0:
            self.message_user(
                request,
                f"{updated} products marked as inactive.",
                messages.SUCCESS
            )
        else:
            self.message_user(
                request,
                "No products were marked as inactive.",
                messages.WARNING
            )
    mark_selected_as_inactive.short_description = _('Mark selected products as inactive') 