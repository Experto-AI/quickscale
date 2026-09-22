"""Tests for billing module admin configuration."""

from __future__ import annotations

from typing import cast
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.http import HttpResponse
from django.test import RequestFactory

from quickscale_modules_billing.admin import (
    CreditBalanceAdmin,
    CreditTransactionAdmin,
    PlanAdmin,
    PurchaseCheckoutAdmin,
    SubscriptionAdmin,
    WebhookEventAdmin,
)
from quickscale_modules_billing.models import (
    CreditBalance,
    CreditTransaction,
    Plan,
    PurchaseCheckout,
    Subscription,
    WebhookEvent,
)

from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware

from quickscale_modules_orgs.current_org import org_scope
from quickscale_modules_orgs.models import Organization

User = get_user_model()


def _add_session(request):
    """Add session support to a RequestFactory-generated request."""
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    return request


def _plan_admin() -> PlanAdmin:
    return cast(PlanAdmin, admin.site._registry[Plan])


def _credit_balance_admin() -> CreditBalanceAdmin:
    return cast(CreditBalanceAdmin, admin.site._registry[CreditBalance])


def _credit_transaction_admin() -> CreditTransactionAdmin:
    return cast(CreditTransactionAdmin, admin.site._registry[CreditTransaction])


def _webhook_event_admin() -> WebhookEventAdmin:
    return cast(WebhookEventAdmin, admin.site._registry[WebhookEvent])


def _purchase_checkout_admin() -> PurchaseCheckoutAdmin:
    return cast(PurchaseCheckoutAdmin, admin.site._registry[PurchaseCheckout])


@pytest.mark.django_db
class TestAdminRegistration:
    def test_models_are_registered(self) -> None:
        assert admin.site.is_registered(Plan)
        assert admin.site.is_registered(CreditBalance)
        assert admin.site.is_registered(CreditTransaction)
        assert admin.site.is_registered(PurchaseCheckout)
        assert admin.site.is_registered(Subscription)
        assert admin.site.is_registered(WebhookEvent)


@pytest.mark.django_db
class TestReadOnlyAdminModels:
    def test_credit_balance_admin_is_read_only(self, superuser) -> None:
        balance_admin = _credit_balance_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        readonly_fields = balance_admin.get_readonly_fields(request)
        model_field_names = [field.name for field in CreditBalance._meta.fields]

        assert balance_admin.has_add_permission(request) is False
        assert balance_admin.has_delete_permission(request) is False
        assert set(model_field_names).issubset(set(readonly_fields))

    def test_credit_balance_admin_change_view_hides_mutation_actions(
        self,
        superuser,
    ) -> None:
        balance_admin = _credit_balance_admin()
        request = _add_session(RequestFactory().get("/admin/"))
        request.user = superuser

        with patch.object(
            admin.ModelAdmin,
            "change_view",
            autospec=True,
            return_value=HttpResponse("ok"),
        ) as mock_change_view:
            response = balance_admin.change_view(
                request,
                object_id="1",
                extra_context={"existing": True},
            )

        assert response.content == b"ok"
        extra_context = mock_change_view.call_args.kwargs["extra_context"]
        assert extra_context == {
            "existing": True,
            "show_delete": False,
            "show_save": False,
            "show_save_and_add_another": False,
            "show_save_and_continue": False,
        }

    def test_credit_transaction_admin_is_read_only(self, superuser) -> None:
        transaction_admin = _credit_transaction_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        assert transaction_admin.has_add_permission(request) is False

    def test_webhook_event_admin_is_read_only(self, superuser) -> None:
        webhook_admin = _webhook_event_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        readonly_fields = webhook_admin.get_readonly_fields(request)
        model_field_names = [field.name for field in WebhookEvent._meta.fields]

        assert webhook_admin.has_add_permission(request) is False
        assert set(model_field_names).issubset(set(readonly_fields))

    def test_purchase_checkout_admin_is_read_only(self, superuser) -> None:
        checkout_admin = _purchase_checkout_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        readonly_fields = checkout_admin.get_readonly_fields(request)
        model_field_names = [field.name for field in PurchaseCheckout._meta.fields]

        assert checkout_admin.has_add_permission(request) is False
        assert checkout_admin.has_delete_permission(request) is False
        assert set(model_field_names).issubset(set(readonly_fields))


@pytest.mark.django_db
class TestPlanAdmin:
    def test_plan_admin_allows_add(self, superuser) -> None:
        plan_admin = _plan_admin()
        request = RequestFactory().get("/admin/")
        request.user = superuser

        assert plan_admin.has_add_permission(request) is True


@pytest.mark.django_db
class TestBillingAdminTenantScopedQueryset:
    """CR-SA14.3-002: verify billing TenantModelAdmin querysets scope to org context."""

    def test_credit_balance_admin_fail_closed_without_org(self):
        """CreditBalanceAdmin.get_queryset returns empty when no org context."""
        from django.contrib.admin.sites import AdminSite

        site = AdminSite()
        admin_instance = CreditBalanceAdmin(CreditBalance, site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            "cb-admin", "cb@example.com", "adminpass"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.count() == 0

    def test_credit_transaction_admin_fail_closed_without_org(self):
        """CreditTransactionAdmin.get_queryset returns empty when no org context."""
        from django.contrib.admin.sites import AdminSite

        site = AdminSite()
        admin_instance = CreditTransactionAdmin(CreditTransaction, site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            "ct-admin", "ct@example.com", "adminpass"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.count() == 0

    def test_subscription_admin_fail_closed_without_org(self):
        """SubscriptionAdmin.get_queryset returns empty when no org context."""
        from django.contrib.admin.sites import AdminSite

        site = AdminSite()
        admin_instance = SubscriptionAdmin(Subscription, site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            "sub-admin", "sub@example.com", "adminpass"
        )
        qs = admin_instance.get_queryset(request)
        assert qs.count() == 0

    def test_subscription_admin_scopes_to_org(self, organization, org_context):
        """SubscriptionAdmin.get_queryset returns only subscriptions from the scoped org."""
        from django.contrib.admin.sites import AdminSite

        org_b = Organization.objects.create(name="Org B", slug="org-b")

        plan = Plan.objects.create(
            name="Test Plan",
            slug="test-plan",
            stripe_price_id="price_test",
            credits_per_period=100,
            price_cents=1000,
        )

        # Create subscriptions in different orgs using all_objects
        Subscription.all_objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
        with org_scope(org_b):
            Subscription.all_objects.create(
                organization=org_b,
                plan=plan,
                status=Subscription.Status.ACTIVE,
            )

        site = AdminSite()
        admin_instance = SubscriptionAdmin(Subscription, site)
        request = RequestFactory().get("/admin/")
        request.user = User.objects.create_superuser(
            "scope-admin", "scope@example.com", "adminpass"
        )
        request._validated_org_id = organization.pk

        qs = admin_instance.get_queryset(request)
        # With TenantManager, only the scoped org's subscription should appear
        assert qs.count() == 1

    def test_subscription_admin_is_read_only(
        self,
        organization,
        org_context,
        superuser,
    ) -> None:
        """Provider state cannot be made terminal through local admin edits."""
        from django.contrib.admin.sites import AdminSite

        plan = Plan.objects.create(
            name="Admin Lock Plan",
            slug="admin-lock-plan",
            stripe_price_id="price_admin_lock",
            credits_per_period=100,
            price_cents=1000,
        )
        subscription = Subscription.all_objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
        request = RequestFactory().get("/admin/")
        request.user = superuser
        admin_instance = SubscriptionAdmin(Subscription, AdminSite())
        readonly_fields = admin_instance.get_readonly_fields(request, subscription)
        model_field_names = [field.name for field in Subscription._meta.fields]

        assert admin_instance.has_add_permission(request) is False
        assert admin_instance.has_delete_permission(request, subscription) is False
        assert set(model_field_names).issubset(set(readonly_fields))
        assert "status" in readonly_fields
        assert "stripe_subscription_id" in readonly_fields

    def test_subscription_admin_forbids_delete_and_org_reassignment(
        self,
        organization,
        org_context,
        superuser,
    ) -> None:
        plan = Plan.objects.create(
            name="Admin Immutable Org Plan",
            slug="admin-immutable-org-plan",
            stripe_price_id="price_admin_immutable_org",
            credits_per_period=100,
            price_cents=1000,
        )
        subscription = Subscription.all_objects.create(
            organization=organization,
            plan=plan,
            status=Subscription.Status.ACTIVE,
        )
        request = RequestFactory().get("/admin/")
        request.user = superuser
        admin_instance = SubscriptionAdmin(Subscription, admin.site)

        assert admin_instance.has_delete_permission(request, subscription) is False
        assert "organization" in admin_instance.get_readonly_fields(
            request,
            subscription,
        )
