"""Tests for admin configuration"""

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite

from quickscale_modules_listings.admin import AbstractListingAdmin
from tests.models import ConcreteListing


@pytest.mark.django_db
class TestAbstractListingAdmin:
    """Tests for AbstractListingAdmin class"""

    def test_admin_class_exists(self):
        """Test AbstractListingAdmin class is defined"""
        assert AbstractListingAdmin is not None

    def test_list_display_fields(self):
        """Test admin list_display contains expected fields"""
        expected = [
            "title",
            "price",
            "location",
            "status",
            "published_date",
            "created_at",
        ]
        assert AbstractListingAdmin.list_display == expected

    def test_list_filter_fields(self):
        """Test admin list_filter contains expected fields"""
        expected = ["status", "created_at", "published_date"]
        assert AbstractListingAdmin.list_filter == expected

    def test_search_fields(self):
        """Test admin search_fields contains expected fields"""
        expected = ["title", "description", "location"]
        assert AbstractListingAdmin.search_fields == expected

    def test_prepopulated_fields(self):
        """Test admin prepopulated_fields is set correctly"""
        assert AbstractListingAdmin.prepopulated_fields == {"slug": ("title",)}

    def test_date_hierarchy(self):
        """Test admin date_hierarchy is set correctly"""
        assert AbstractListingAdmin.date_hierarchy == "published_date"

    def test_ordering(self):
        """Test admin ordering is set correctly"""
        assert AbstractListingAdmin.ordering == ["-created_at"]

    def test_fieldsets_structure(self):
        """Test admin fieldsets has expected structure"""
        fieldsets = AbstractListingAdmin.fieldsets
        assert len(fieldsets) == 4

        # Check section names
        section_names = [fs[0] for fs in fieldsets]
        assert "Basic Information" in section_names
        assert "Pricing & Location" in section_names
        assert "Media" in section_names
        assert "Status" in section_names

    def test_readonly_fields(self):
        """Test admin readonly_fields is set correctly"""
        expected = ["created_at", "updated_at"]
        assert AbstractListingAdmin.readonly_fields == expected


@pytest.mark.django_db
class TestConcreteListingAdmin:
    """Tests for registering a concrete listing model with admin"""

    def test_concrete_model_can_be_registered(self):
        """Test that ConcreteListing can be registered with AbstractListingAdmin"""
        # Create a custom admin site for testing
        test_site = AdminSite()

        # Create a concrete admin class
        @admin.register(ConcreteListing, site=test_site)
        class ConcreteListingAdmin(AbstractListingAdmin):
            pass

        # Check it was registered
        assert ConcreteListing in test_site._registry

    def test_concrete_admin_inherits_list_display(self):
        """Test concrete admin inherits list_display"""
        test_site = AdminSite()

        class ConcreteListingAdmin(AbstractListingAdmin):
            pass

        test_site.register(ConcreteListing, ConcreteListingAdmin)
        admin_instance = test_site._registry[ConcreteListing]

        assert admin_instance.list_display == AbstractListingAdmin.list_display

    def test_concrete_admin_can_override_settings(self):
        """Test concrete admin can override settings"""
        test_site = AdminSite()

        class ConcreteListingAdmin(AbstractListingAdmin):
            list_display = ["title", "status"]  # Override

        test_site.register(ConcreteListing, ConcreteListingAdmin)
        admin_instance = test_site._registry[ConcreteListing]

        assert admin_instance.list_display == ["title", "status"]
