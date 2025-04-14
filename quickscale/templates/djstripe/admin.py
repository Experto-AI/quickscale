"""
Django Stripe Admin Configuration

This module contains any custom admin interfaces for Django Stripe models.
Most admin interfaces will be provided by the djstripe package itself.
"""

from django.contrib import admin

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