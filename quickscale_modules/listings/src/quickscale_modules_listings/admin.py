"""Admin configuration for QuickScale listings module"""

from typing import Any

from django import forms
from django.contrib import admin
from django.db.models import Model
from django.http import HttpRequest
from markdownx.widgets import AdminMarkdownxWidget

from quickscale_modules_orgs.admin import TenantModelAdmin

from .models import Listing


class AbstractListingAdmin(TenantModelAdmin):
    """Base admin class for listing models - extend for concrete models

    SA14.3: inherits from ``TenantModelAdmin`` which provides org-scoped
    querysets via ``_org_db_context`` view wrappers.  Concrete subclasses
    (e.g. ``PropertyListingAdmin``) inherit the same scoping without
    additional overrides.
    """

    list_display = [
        "title",
        "price",
        "location",
        "organization",
        "status",
        "published_date",
        "created_at",
    ]
    list_filter = ["organization", "status", "created_at", "published_date"]
    search_fields = ["title", "description", "location"]
    prepopulated_fields = {"slug": ("title",)}
    date_hierarchy = "published_date"
    ordering = ["-created_at"]

    fieldsets = [
        (
            "Basic Information",
            {
                "fields": ["title", "slug", "organization", "description"],
            },
        ),
        (
            "Pricing & Location",
            {
                "fields": ["price", "location"],
            },
        ),
        (
            "Media",
            {
                "fields": ["featured_image", "featured_image_alt"],
            },
        ),
        (
            "Status",
            {
                "fields": ["status", "published_date"],
            },
        ),
    ]

    readonly_fields = ["created_at", "updated_at"]

    def get_form(
        self,
        request: HttpRequest,
        obj: Model | None = None,
        change: bool = False,
        **kwargs: Any,
    ) -> type[forms.ModelForm]:
        """Return an admin form with a Markdown editor for description"""
        form_class = super().get_form(request, obj=obj, change=change, **kwargs)
        description_field = form_class.base_fields.get("description")
        if description_field is not None:
            description_field.widget = AdminMarkdownxWidget()
        return form_class


@admin.register(Listing)
class ListingAdmin(AbstractListingAdmin):
    """Admin for the default Listing model"""

    pass


# Note: This module provides AbstractListing and AbstractListingAdmin.
# To use custom listings in your project:
#
# 1. Create a concrete model extending AbstractListing:
#    class PropertyListing(AbstractListing):
#        bedrooms = models.IntegerField()
#        class Meta(AbstractListing.Meta):
#            abstract = False
#
# 2. Register with admin:
#    @admin.register(PropertyListing)
#    class PropertyListingAdmin(AbstractListingAdmin):
#        list_display = AbstractListingAdmin.list_display + ['bedrooms']
