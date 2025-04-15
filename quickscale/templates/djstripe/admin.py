"""
Django Stripe Admin Configuration

This module contains any custom admin interfaces for Django Stripe models.
Most admin interfaces will be provided by the djstripe package itself.
"""

from django.contrib import admin
from .models import Product

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
    list_display = ('name', 'get_formatted_price', 'currency', 'status', 'created', 'updated')
    list_filter = ('status', 'currency', 'created', 'updated')
    search_fields = ('name', 'description', 'stripe_product_id')
    readonly_fields = ('created', 'updated')
    fieldsets = (
        ('Product Information', {
            'fields': ('name', 'description', 'image', 'status')
        }),
        ('Pricing', {
            'fields': ('base_price', 'currency')
        }),
        ('Stripe Integration', {
            'fields': ('stripe_product_id', 'metadata')
        }),
        ('Timestamps', {
            'fields': ('created', 'updated'),
            'classes': ('collapse',)
        }),
    ) 