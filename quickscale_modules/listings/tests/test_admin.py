"""Tests for admin configuration"""

from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db import models
from django.test import RequestFactory
from markdownx.widgets import AdminMarkdownxWidget

from quickscale_modules_listings.admin import AbstractListingAdmin, ListingAdmin
from quickscale_modules_listings.models import Listing
from tests.models import ConcreteListing

User = get_user_model()


@pytest.mark.django_db
class TestAbstractListingAdmin:
    """Tests for AbstractListingAdmin class"""

    def test_admin_class_exists(self):
        """Test AbstractListingAdmin class is defined"""
        assert AbstractListingAdmin is not None

    def test_description_field_remains_text_field(self):
        """Test description model field remains a standard text field"""
        description_field = ConcreteListing._meta.get_field("description")
        assert isinstance(description_field, models.TextField)

    def test_list_display_fields(self):
        """Test admin list_display contains expected fields"""
        expected = [
            "title",
            "price",
            "location",
            "organization",
            "status",
            "published_date",
            "created_at",
        ]
        assert AbstractListingAdmin.list_display == expected

    def test_list_filter_fields(self):
        """Test admin list_filter contains expected fields"""
        expected = ["organization", "status", "created_at", "published_date"]
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

    def test_get_form_uses_markdownx_widget_for_description(self):
        """Test description uses the markdown admin widget"""
        test_site = AdminSite()
        admin_instance = AbstractListingAdmin(ConcreteListing, test_site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            username="listings-admin",
            email="listings-admin@example.com",
            password="pass123",
        )

        form_class = admin_instance.get_form(request)
        form = form_class()

        assert isinstance(form.fields["description"].widget, AdminMarkdownxWidget)

    def test_get_form_keeps_non_description_widgets_unchanged(self):
        """Test markdown widget is only applied to description"""
        test_site = AdminSite()
        admin_instance = AbstractListingAdmin(ConcreteListing, test_site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            username="listings-admin-widgets",
            email="listings-admin-widgets@example.com",
            password="pass123",
        )

        form_class = admin_instance.get_form(request)
        form = form_class()

        assert not isinstance(form.fields["title"].widget, AdminMarkdownxWidget)


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


@pytest.mark.django_db
class TestListingAdminOperatorPath:
    """Phase F11.12b: verify listing admin surfaces use all_objects for cross-tenant visibility."""

    def test_abstract_listing_admin_uses_operator_or_default_queryset(self):
        """AbstractListingAdmin.get_queryset uses all_objects when available, falls back to _default_manager."""
        test_site = AdminSite()
        admin_instance = AbstractListingAdmin(ConcreteListing, test_site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            username="listing-op", email="listing-op@example.com", password="pass123"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.model == ConcreteListing
        # ConcreteListing now defines all_objects (TenantManager, super_scope)
        # and _default_manager is the scoped TenantManager. The admin's
        # get_queryset retrieves the operator-manager queryset.
        assert str(qs.query) == str(ConcreteListing.all_objects.all().query)

    def test_listing_admin_registered_uses_operator_queryset(self):
        """ListingAdmin (concrete) inherits operator queryset from AbstractListingAdmin."""
        test_site = AdminSite()
        admin_instance = ListingAdmin(Listing, test_site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            username="listing-admin-op",
            email="listing-admin-op@example.com",
            password="pass123",
        )
        qs = admin_instance.get_queryset(request)
        assert qs.model == Listing
        assert str(qs.query) == str(Listing.all_objects.all().query)

    def test_admin_queryset_returns_cross_tenant_listings(
        self, org_a, org_b, listing_factory
    ):
        """Operator admin queryset returns listings from all organizations."""
        listing_factory(title="Listing A", organization=org_a)
        listing_factory(title="Listing B", organization=org_b)

        test_site = AdminSite()
        admin_instance = AbstractListingAdmin(ConcreteListing, test_site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            username="cross-listing",
            email="cross-listing@example.com",
            password="pass123",
        )
        qs = admin_instance.get_queryset(request)
        titles = list(qs.values_list("title", flat=True))
        assert "Listing A" in titles
        assert "Listing B" in titles

    # ------------------------------------------------------------------
    # Spy-based seam verification: prove all_objects is actually called
    # ------------------------------------------------------------------

    def test_listing_admin_get_queryset_calls_all_objects(self):
        """ListingAdmin.get_queryset actually calls Listing.all_objects.all()."""
        with patch.object(Listing, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = Listing.objects.none()
            test_site = AdminSite()
            admin_instance = ListingAdmin(Listing, test_site)
            request = RequestFactory().get("/admin/")
            request.user = User.objects.create_superuser(
                username="listing-spy",
                email="listing-spy@example.com",
                password="pass123",
            )
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()

    def test_abstract_listing_admin_calls_all_objects_when_present(self):
        """AbstractListingAdmin.get_queryset calls all_objects when model has it."""
        with patch.object(Listing, "all_objects") as mock_mgr:
            mock_mgr.all.return_value = Listing.objects.none()
            test_site = AdminSite()
            admin_instance = AbstractListingAdmin(Listing, test_site)
            request = RequestFactory().get("/admin/")
            request.user = User.objects.create_superuser(
                username="abstract-spy",
                email="abstract-spy@example.com",
                password="pass123",
            )
            admin_instance.get_queryset(request)
            mock_mgr.all.assert_called_once()
