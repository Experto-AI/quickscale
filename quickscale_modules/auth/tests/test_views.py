"""Tests for auth module views"""

from contextlib import contextmanager
from typing import Any

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestProfileView:
    """Tests for ProfileView"""

    def test_profile_view_requires_authentication(self, anonymous_client):
        """Test profile view redirects anonymous users"""
        response = anonymous_client.get(reverse("quickscale_auth:profile"))
        assert response.status_code == 302  # Redirect to login

    def test_profile_view_authenticated(self, authenticated_client, user):
        """Test profile view displays user info"""
        response = authenticated_client.get(reverse("quickscale_auth:profile"))
        assert response.status_code == 200
        assert user.username.encode() in response.content


@pytest.mark.django_db
class TestProfileUpdateView:
    """Tests for ProfileUpdateView"""

    def test_profile_update_requires_authentication(self, anonymous_client):
        """Test profile update redirects anonymous users"""
        response = anonymous_client.get(reverse("quickscale_auth:profile_edit"))
        assert response.status_code == 302

    def test_profile_update_get(self, authenticated_client):
        """Test profile update GET displays form"""
        response = authenticated_client.get(reverse("quickscale_auth:profile_edit"))
        assert response.status_code == 200

    def test_profile_update_post_valid(self, authenticated_client, user):
        """Test profile update with valid data"""
        response = authenticated_client.post(
            reverse("quickscale_auth:profile_edit"),
            {
                "first_name": "Updated",
                "last_name": "Name",
                "email": user.email,
            },
        )
        assert response.status_code == 302
        user.refresh_from_db()
        assert user.first_name == "Updated"


@pytest.mark.django_db
class TestAccountDeleteView:
    """Tests for AccountDeleteView"""

    def test_account_delete_requires_authentication(self, anonymous_client):
        """Test account delete redirects anonymous users"""
        response = anonymous_client.get(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 302

    def test_account_delete_get(self, authenticated_client):
        """Test account delete GET displays confirmation"""
        response = authenticated_client.get(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 200

    def test_account_delete_post(self, authenticated_client, user):
        """Test account deletion — permitted when user has no blocking orgs"""
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        user_id = user.id
        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 302
        assert not user_model.objects.filter(id=user_id).exists()

    # ------------------------------------------------------------------
    # last-owner guard
    # ------------------------------------------------------------------

    def test_account_delete_blocked_when_sole_owner_of_shared_org_with_members(
        self, authenticated_client, user, user_data
    ):
        """Deletion is rejected when the user is the sole owner of a
        shared org that still has other members."""
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # Create a shared org where *user* is the sole owner.
        org = Organization.objects.create(
            name="Shared Org",
            slug="shared-org",
            is_personal=False,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )
        # Add another member (not an owner) so the org has "other members".
        from django.contrib.auth import get_user_model

        User = get_user_model()
        other_user = User.objects.create_user(
            username="otheruser",
            email="other@example.com",
            password="OtherPass123!",
        )
        OrganizationMembership.objects.create(
            user=other_user,
            organization=org,
            role=OrgRole.MEMBER,
        )

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 200  # re-renders confirmation with error
        from django.contrib import messages as messages_framework

        message_list = list(messages_framework.get_messages(response.wsgi_request))
        assert any("sole owner" in str(m.message) for m in message_list)
        from django.contrib.auth import get_user_model as g_user_model

        assert g_user_model().objects.filter(id=user.id).exists()

    def test_account_delete_allowed_when_other_owner_exists(
        self, authenticated_client, user, user_data
    ):
        """Deletion is allowed when another owner exists on the shared org."""
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        org = Organization.objects.create(
            name="Shared Org",
            slug="shared-org-2",
            is_personal=False,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )
        # Second owner — deletion should proceed.
        from django.contrib.auth import get_user_model

        User = get_user_model()
        other_owner = User.objects.create_user(
            username="otherowner",
            email="otherowner@example.com",
            password="OtherOwner123!",
        )
        OrganizationMembership.objects.create(
            user=other_owner,
            organization=org,
            role=OrgRole.OWNER,
        )

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 302
        from django.contrib.auth import get_user_model as g_user_model

        assert not g_user_model().objects.filter(id=user.id).exists()

    def test_account_delete_allowed_when_sole_member_of_shared_org(
        self, authenticated_client, user
    ):
        """Deletion is allowed when the user is the sole owner and sole
        member — no other members to protect."""
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        org = Organization.objects.create(
            name="Solo Shared",
            slug="solo-shared",
            is_personal=False,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )
        # No other members — user can leave without stranding anyone.

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 302

    def test_account_delete_allowed_when_personal_org_only(
        self, authenticated_client, user
    ):
        """Deletion is allowed when the user only belongs to a personal
        org — personal orgs are not blocked by the last-owner guard."""
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        OrganizationMembership.objects.create(
            user=user,
            organization=Organization.objects.create(
                name="Personal",
                slug="personal-test",
                is_personal=True,
            ),
            role=OrgRole.OWNER,
        )

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 302

    def test_account_delete_blocked_when_sole_owner_of_memberful_personal_org(
        self, authenticated_client, user, user_data
    ):
        """Deletion is blocked when the user is the sole owner of a
        personal org that has other members — last-owner
        protection applies to memberful personal orgs too."""
        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # Create a personal org where *user* is the sole owner.
        personal_org = Organization.objects.create(
            name="Personal with Members",
            slug="personal-w-members",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        # Add another member so the org is memberful.
        User = get_user_model()
        other_user = User.objects.create_user(
            username="othermember",
            email="othermember@example.com",
            password="OtherMember123!",
        )
        OrganizationMembership.objects.create(
            user=other_user,
            organization=personal_org,
            role=OrgRole.MEMBER,
        )

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 200  # re-renders confirmation with error
        from django.contrib import messages as messages_framework

        message_list = list(messages_framework.get_messages(response.wsgi_request))
        assert any("sole owner" in str(m.message) for m in message_list)
        from django.contrib.auth import get_user_model as g_user_model

        assert g_user_model().objects.filter(id=user.id).exists()

    def test_account_delete_does_not_cancel_others_personal_org_subscription(
        self, authenticated_client, user
    ):
        """A member on someone else's personal org must NOT trigger
        subscription cancellation for that org — non-owner
        personal-org guard."""
        from unittest.mock import patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # Create a personal org owned by a *different* user.
        from django.contrib.auth import get_user_model

        User = get_user_model()
        other_user = User.objects.create_user(
            username="other_owner",
            email="other_owner@example.com",
            password="OtherOwner123!",
        )
        other_personal_org = Organization.objects.create(
            name="Other Personal",
            slug="other-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=other_user,
            organization=other_personal_org,
            role=OrgRole.OWNER,
        )
        # Authenticated *user* is a MEMBER on that org.
        OrganizationMembership.objects.create(
            user=user,
            organization=other_personal_org,
            role=OrgRole.MEMBER,
        )

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )
        assert response.status_code == 302
        # The cancel function must NOT be called — user is not an owner
        # of any personal org, only a member of someone else's.
        mock_cancel.assert_not_called()

    # ------------------------------------------------------------------
    # personal-org subscription cancellation
    # ------------------------------------------------------------------

    def test_account_delete_cancels_personal_org_subscription(
        self, authenticated_client, user
    ):
        """Deletion triggers subscription cancellation on the user's
        personal org when an active subscription exists."""
        from unittest.mock import ANY, patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Personal",
            slug="personal-cancel",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )
        assert response.status_code == 302
        # The ``user`` argument arrives as a SimpleLazyObject wrapper
        # (Django defers request.user resolution), so we match with
        # ANY and verify the organization instead.
        mock_cancel.assert_called_once_with(
            ANY,
            organization=personal_org,
            capture_transition=True,
        )

    def test_account_delete_reconciles_billing_outside_database_transaction(
        self, authenticated_client, user
    ):
        """Stripe reconciliation must not run inside an atomic block."""
        from unittest.mock import patch

        from django.db import connection

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Outside Transaction",
            slug="outside-transaction",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        baseline_atomic_depth = len(connection.atomic_blocks)
        atomic_depths = []

        def record_atomic_state(*args, **kwargs):
            del args, kwargs
            atomic_depths.append(len(connection.atomic_blocks))

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
            side_effect=record_atomic_state,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302
        assert atomic_depths == [baseline_atomic_depth]

    def test_account_delete_blocks_open_subscription_checkout(
        self, authenticated_client, user
    ):
        """An actual provider-open Checkout Session keeps the account intact."""
        from unittest.mock import MagicMock, patch

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model
        from django.utils import timezone

        from quickscale_modules_billing.models import Plan, Subscription
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Pending Checkout",
            slug="pending-checkout-account-delete",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        plan = Plan.objects.create(
            name="Pending Checkout Plan",
            slug="pending-checkout-account-delete",
            stripe_price_id="price_pending_checkout_account_delete",
            credits_per_period=100,
            price_cents=1900,
            currency="usd",
            billing_interval=Plan.BillingInterval.MONTHLY,
        )
        with org_scope(personal_org):
            Subscription.objects.create(
                organization=personal_org,
                user=user,
                plan=plan,
                status=Subscription.Status.INCOMPLETE,
                stripe_checkout_session_id="cs_pending_account_delete",
                checkout_expires_at=timezone.now() + timezone.timedelta(minutes=30),
            )
        stripe_client = MagicMock()
        stripe_client.retrieve_checkout_session.return_value = {
            "id": "cs_pending_account_delete",
            "status": "open",
        }

        with (
            patch(
                "quickscale_modules_billing._stripe_client.get_stripe_client",
                return_value=stripe_client,
            ),
            patch(
                "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
            ) as mock_cancel,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "is still open" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )
        stripe_client.retrieve_checkout_session.assert_called_once_with(
            checkout_session_id="cs_pending_account_delete"
        )
        mock_cancel.assert_not_called()

    def test_account_delete_ignores_a_retained_orgs_open_checkout(
        self, authenticated_client, user
    ):
        """Another owner's retained-organization checkout does not block deletion."""
        from unittest.mock import MagicMock, patch

        from django.contrib.auth import get_user_model
        from django.utils import timezone

        from quickscale_modules_billing.models import Plan, Subscription
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        other_user = get_user_model().objects.create_user(
            username="retained-owner",
            email="retained-owner@example.com",
            password="test-pass-123",
        )
        personal_org = Organization.objects.create(
            name="Deleting Member Personal",
            slug="deleting-member-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        shared_org = Organization.objects.create(
            name="Retained Shared",
            slug="retained-shared-open-checkout",
        )
        OrganizationMembership.objects.create(
            user=other_user,
            organization=shared_org,
            role=OrgRole.OWNER,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=shared_org,
            role=OrgRole.MEMBER,
        )
        plan = Plan.objects.create(
            name="Retained Checkout Plan",
            slug="retained-checkout-plan",
            stripe_price_id="price_retained_checkout",
            credits_per_period=100,
            price_cents=1900,
            currency="usd",
            billing_interval=Plan.BillingInterval.MONTHLY,
        )
        with org_scope(shared_org):
            Subscription.objects.create(
                organization=shared_org,
                user=other_user,
                plan=plan,
                status=Subscription.Status.INCOMPLETE,
                stripe_checkout_session_id="cs_retained_shared_open",
                checkout_expires_at=timezone.now() + timezone.timedelta(minutes=30),
            )
        stripe_client = MagicMock()
        stripe_client.retrieve_checkout_session.return_value = {
            "id": "cs_retained_shared_open",
            "status": "open",
        }

        with patch(
            "quickscale_modules_billing._stripe_client.get_stripe_client",
            return_value=stripe_client,
        ):
            authenticated_client.post(reverse("quickscale_auth:account_delete"))

        assert not get_user_model().objects.filter(pk=user.pk).exists()
        stripe_client.retrieve_checkout_session.assert_not_called()

    def test_account_delete_blocks_open_purchase_checkout(
        self, authenticated_client, user
    ):
        """An actual provider-open one-time Checkout keeps the account intact."""
        from unittest.mock import MagicMock, patch

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model

        from quickscale_modules_billing.models import Plan, PurchaseCheckout
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Pending Purchase Checkout",
            slug="pending-purchase-checkout-account-delete",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        plan = Plan.objects.create(
            name="Pending Purchase Plan",
            slug="pending-purchase-checkout-account-delete",
            stripe_price_id="price_pending_purchase_checkout_account_delete",
            credits_per_period=100,
            price_cents=1900,
            currency="usd",
            billing_interval=Plan.BillingInterval.ONE_TIME,
        )
        with org_scope(personal_org):
            PurchaseCheckout.objects.create(
                organization=personal_org,
                user=user,
                plan=plan,
                status=PurchaseCheckout.Status.OPEN,
                stripe_checkout_session_id="cs_pending_purchase_account_delete",
            )
        stripe_client = MagicMock()
        stripe_client.retrieve_checkout_session.return_value = {
            "id": "cs_pending_purchase_account_delete",
            "status": "open",
        }

        with (
            patch(
                "quickscale_modules_billing._stripe_client.get_stripe_client",
                return_value=stripe_client,
            ),
            patch(
                "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
            ) as mock_cancel,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "purchase checkout session" in str(message.message).lower()
            and "is still open" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )
        stripe_client.retrieve_checkout_session.assert_called_once_with(
            checkout_session_id="cs_pending_purchase_account_delete"
        )
        mock_cancel.assert_not_called()

    def test_account_delete_cancels_active_subscription_without_tenant_middleware(
        self, authenticated_client, user
    ):
        """The exempt accounts route establishes RLS context for billing rows."""
        from unittest.mock import MagicMock, patch

        from django.contrib.auth import get_user_model

        from quickscale_modules_billing.models import Plan, Subscription
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Account Cancellation RLS",
            slug="account-cancellation-rls",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        plan = Plan.objects.create(
            name="Account Cancellation RLS Plan",
            slug="account-cancellation-rls",
            stripe_price_id="price_account_cancellation_rls",
            credits_per_period=100,
            price_cents=1900,
            currency="usd",
            billing_interval=Plan.BillingInterval.MONTHLY,
        )
        with org_scope(personal_org):
            Subscription.objects.create(
                organization=personal_org,
                user=user,
                plan=plan,
                status=Subscription.Status.ACTIVE,
                stripe_subscription_id="sub_account_cancellation_rls",
            )
        stripe_client = MagicMock()
        stripe_client.retrieve_subscription.return_value = {
            "id": "sub_account_cancellation_rls",
            "status": "active",
            "cancel_at_period_end": False,
        }
        stripe_client.cancel_subscription.return_value = {
            "id": "sub_account_cancellation_rls",
            "status": "active",
            "cancel_at_period_end": True,
        }

        with patch(
            "quickscale_modules_billing._stripe_client.get_stripe_client",
            return_value=stripe_client,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302
        assert not get_user_model().objects.filter(pk=user.pk).exists()
        stripe_client.retrieve_subscription.assert_called_once_with(
            stripe_subscription_id="sub_account_cancellation_rls"
        )
        stripe_client.cancel_subscription.assert_called_once_with(
            stripe_subscription_id="sub_account_cancellation_rls"
        )

    def test_account_delete_blocks_active_subscription_when_billing_disabled(
        self, authenticated_client, user
    ):
        """Disabling billing cannot turn a live provider subscription into no-op."""
        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model
        from django.test import override_settings

        from quickscale_modules_billing.models import Plan, Subscription
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Disabled Billing Account Delete",
            slug="disabled-billing-account-delete",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        plan = Plan.objects.create(
            name="Disabled Billing Plan",
            slug="disabled-billing-account-delete",
            stripe_price_id="price_disabled_billing_account_delete",
            credits_per_period=100,
            price_cents=1900,
            currency="usd",
            billing_interval=Plan.BillingInterval.MONTHLY,
        )
        with org_scope(personal_org):
            Subscription.objects.create(
                organization=personal_org,
                user=user,
                plan=plan,
                status=Subscription.Status.ACTIVE,
                stripe_subscription_id="sub_disabled_billing_account_delete",
            )

        with override_settings(QUICKSCALE_BILLING_ENABLED=False):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "Billing module is disabled" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    def test_account_delete_allows_disabled_billing_without_subscription(
        self, authenticated_client, user
    ):
        """Disabled billing is harmless when no current provider state exists."""
        from django.test import override_settings

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Disabled Billing No Subscription",
            slug="disabled-billing-no-subscription",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )

        with override_settings(QUICKSCALE_BILLING_ENABLED=False):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302

    def test_account_delete_holds_provider_lock_for_surviving_member_org(
        self,
        authenticated_client,
        user,
    ):
        """A retained shared org cannot start provider work during deletion."""
        from contextlib import contextmanager
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Retained Shared Organization",
            slug="retained-shared-organization",
        )
        other_owner = get_user_model().objects.create_user(
            username="retained-shared-owner",
            email="retained-shared-owner@example.com",
            password="RetainedSharedOwner123!",
        )
        OrganizationMembership.objects.create(
            user=other_owner,
            organization=organization,
            role=OrgRole.OWNER,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.MEMBER,
        )
        events: list[tuple[str, object]] = []

        @contextmanager
        def record_provider_lock(organization_id):
            events.append(("lock-enter", organization_id))
            yield
            events.append(("lock-exit", organization_id))

        with patch(
            "quickscale_modules_billing._locks.subscription_provider_mutation_lock",
            side_effect=record_provider_lock,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302
        assert not get_user_model().objects.filter(pk=user.pk).exists()
        assert Organization.objects.filter(pk=organization.pk).exists()
        assert events == [
            ("lock-enter", organization.pk),
            ("lock-exit", organization.pk),
        ]

    def test_account_delete_compensates_cancellation_when_membership_changes(
        self, authenticated_client, user
    ):
        """A concurrent co-owner addition rejects deletion and resumes billing."""
        from contextlib import contextmanager
        from types import SimpleNamespace
        from unittest.mock import ANY, patch

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Concurrent Personal",
            slug="concurrent-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        other_owner = get_user_model().objects.create_user(
            username="concurrent-owner",
            email="concurrent-owner@example.com",
            password="ConcurrentOwner123!",
        )
        transition = SimpleNamespace(changed=True)
        events = []

        @contextmanager
        def record_provider_lock(organization_id):
            events.append(("lock-enter", organization_id))
            yield
            events.append(("lock-exit", organization_id))

        def add_concurrent_owner(*args, **kwargs):
            del args, kwargs
            events.append(("cancel", personal_org.pk))
            OrganizationMembership.objects.create(
                user=other_owner,
                organization=personal_org,
                role=OrgRole.OWNER,
            )
            return transition

        def record_resume(*args, **kwargs):
            del args
            events.append(("resume", kwargs["organization"].pk))

        with (
            patch(
                "quickscale_modules_billing._locks.subscription_provider_mutation_lock",
                side_effect=record_provider_lock,
            ),
            patch(
                "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
                side_effect=add_concurrent_owner,
            ) as mock_cancel,
            patch(
                "quickscale_modules_billing._subscription_mutations.resume_current_subscription",
                side_effect=record_resume,
            ) as mock_resume,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        mock_cancel.assert_called_once_with(
            ANY,
            organization=personal_org,
            capture_transition=True,
        )
        mock_resume.assert_called_once_with(
            ANY,
            organization=personal_org,
            transition=transition,
        )
        assert events == [
            ("lock-enter", personal_org.pk),
            ("cancel", personal_org.pk),
            ("resume", personal_org.pk),
            ("lock-exit", personal_org.pk),
        ]

    def test_account_delete_preserves_preexisting_scheduled_cancellation(
        self, authenticated_client, user
    ):
        """A rejected deletion does not resume an already-canceling subscription."""
        from types import SimpleNamespace
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        personal_org = Organization.objects.create(
            name="Already Canceling",
            slug="already-canceling",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )
        other_owner = get_user_model().objects.create_user(
            username="already-canceling-owner",
            email="already-canceling-owner@example.com",
            password="AlreadyCanceling123!",
        )

        def preserve_existing_state(*args, **kwargs):
            del args, kwargs
            OrganizationMembership.objects.create(
                user=other_owner,
                organization=personal_org,
                role=OrgRole.OWNER,
            )
            return SimpleNamespace(changed=False)

        with (
            patch(
                "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
                side_effect=preserve_existing_state,
            ),
            patch(
                "quickscale_modules_billing._subscription_mutations.resume_current_subscription"
            ) as mock_resume,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        mock_resume.assert_not_called()

    def test_account_delete_compensates_partial_cancellation_on_provider_error(
        self, authenticated_client, user
    ):
        """A provider failure still compensates earlier completed transitions."""
        from types import SimpleNamespace
        from unittest.mock import patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organizations = [
            Organization.objects.create(
                name=f"Provider Failure {index}",
                slug=f"provider-failure-{index}",
                is_personal=True,
            )
            for index in range(2)
        ]
        for organization in organizations:
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrgRole.OWNER,
            )

        cancellation_calls = []
        first_transition = SimpleNamespace(changed=True)

        def fail_second_cancellation(*args, **kwargs):
            del args
            cancellation_calls.append(kwargs["organization"])
            if len(cancellation_calls) == 2:
                raise RuntimeError("provider response lost")
            return first_transition

        with (
            patch(
                "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
                side_effect=fail_second_cancellation,
            ),
            patch(
                "quickscale_modules_billing._subscription_mutations.resume_current_subscription"
            ) as mock_resume,
            pytest.raises(RuntimeError, match="provider response lost"),
        ):
            authenticated_client.post(reverse("quickscale_auth:account_delete"))

        assert [call.kwargs["organization"] for call in mock_resume.call_args_list] == [
            cancellation_calls[0]
        ]
        assert mock_resume.call_args.kwargs["transition"] is first_transition

    def test_account_delete_compensates_when_local_delete_fails(
        self, authenticated_client, user
    ):
        """A rolled-back local deletion resumes its successful cancellation."""
        from types import SimpleNamespace
        from unittest.mock import ANY, patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Delete Failure",
            slug="delete-failure",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.OWNER,
        )
        transition = SimpleNamespace(changed=True)

        with (
            patch(
                "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
                return_value=transition,
            ),
            patch(
                "quickscale_modules_billing._subscription_mutations.resume_current_subscription"
            ) as mock_resume,
            patch.object(
                type(user), "delete", side_effect=RuntimeError("delete failed")
            ),
            pytest.raises(RuntimeError, match="delete failed"),
        ):
            authenticated_client.post(reverse("quickscale_auth:account_delete"))

        assert type(user).objects.filter(pk=user.pk).exists()
        mock_resume.assert_called_once_with(
            ANY,
            organization=organization,
            transition=transition,
        )

    def test_account_delete_isolates_compensation_failures(
        self, authenticated_client, user, caplog
    ):
        """One failed resume is logged without skipping later compensation."""
        import logging
        from types import SimpleNamespace
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organizations = [
            Organization.objects.create(
                name=f"Resume Failure {index}",
                slug=f"resume-failure-{index}",
                is_personal=True,
            )
            for index in range(2)
        ]
        for organization in organizations:
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrgRole.OWNER,
            )
        other_owner = get_user_model().objects.create_user(
            username="resume-race-owner",
            email="resume-race-owner@example.com",
            password="ResumeRaceOwner123!",
        )

        def change_membership(*args, **kwargs):
            del args
            organization = kwargs["organization"]
            if not OrganizationMembership.objects.filter(user=other_owner).exists():
                OrganizationMembership.objects.create(
                    user=other_owner,
                    organization=organization,
                    role=OrgRole.OWNER,
                )
            return SimpleNamespace(changed=True)

        caplog.set_level(logging.ERROR, logger="quickscale_modules_auth.views")
        with (
            patch(
                "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
                side_effect=change_membership,
            ),
            patch(
                "quickscale_modules_billing._subscription_mutations.resume_current_subscription",
                side_effect=[RuntimeError("resume failed"), None],
            ) as mock_resume,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert mock_resume.call_count == 2
        assert any(
            "Manual provider reconciliation" in message for message in caplog.messages
        )

    def test_account_delete_records_retained_organization_obligation_skips(
        self, authenticated_client, user, caplog
    ):
        """Retained organization data is an explicit, named skip."""
        import logging
        from unittest.mock import patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_orgs.removal import (
            OWNED_TENANT_ROWS,
            PURGE_TOMBSTONE,
            SOCIAL_CACHE_STATE,
        )

        personal_org = Organization.objects.create(
            name="Retained Personal",
            slug="retained-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=personal_org,
            role=OrgRole.OWNER,
        )

        caplog.set_level(logging.INFO, logger="quickscale_modules_auth.views")
        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302
        for obligation_name in (
            OWNED_TENANT_ROWS,
            SOCIAL_CACHE_STATE,
            PURGE_TOMBSTONE,
        ):
            assert any(obligation_name in message for message in caplog.messages)

    def test_account_delete_records_skips_for_member_only_organization(
        self, authenticated_client, user, caplog
    ):
        """Retention skips cover organizations where the user is only a member."""
        import logging
        from unittest.mock import patch

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_orgs.removal import (
            OWNED_TENANT_ROWS,
            PURGE_TOMBSTONE,
            SOCIAL_CACHE_STATE,
        )

        organization = Organization.objects.create(
            name="Member Retained",
            slug="member-retained",
        )
        owner = get_user_model().objects.create_user(
            username="retained-owner",
            email="retained-owner@example.com",
            password="RetainedOwner123!",
        )
        OrganizationMembership.objects.create(
            user=owner,
            organization=organization,
            role=OrgRole.OWNER,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.MEMBER,
        )

        caplog.set_level(logging.INFO, logger="quickscale_modules_auth.views")
        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302
        for obligation_name in (
            OWNED_TENANT_ROWS,
            SOCIAL_CACHE_STATE,
            PURGE_TOMBSTONE,
        ):
            assert any(
                obligation_name in message and str(organization.pk) in message
                for message in caplog.messages
            )

    def test_account_delete_graceful_without_a_declared_provider(
        self, authenticated_client, user
    ):
        """Deletion does not fail when no account-deletion provider is installed.

        A project without billing declares no handler through the rule 4
        ``account_deletion_handlers`` capability; patching the collection
        simulates that absence, because the app registry is process-wide and
        cannot be re-derived inside one test.
        """
        from unittest.mock import patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        OrganizationMembership.objects.create(
            user=user,
            organization=Organization.objects.create(
                name="Personal",
                slug="personal-no-billing",
                is_personal=True,
            ),
            role=OrgRole.OWNER,
        )

        with patch(
            "quickscale_modules_auth.views.collect_capabilities",
            return_value=(),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )
        # Deletion proceeds even though no provider is declared.
        assert response.status_code == 302

    def test_account_delete_cancels_only_owned_personal_org(
        self, authenticated_client, user
    ):
        """When the user is an owner of one personal org and a mere
        member of another, only the owned personal org's subscription
        is cancelled — multi-personal-org guard."""
        from unittest.mock import ANY, patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # Owned personal org.
        owned_org = Organization.objects.create(
            name="My Personal",
            slug="my-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=owned_org,
            role=OrgRole.OWNER,
        )

        # Another user's personal org where *user* is only a member.
        from django.contrib.auth import get_user_model

        User = get_user_model()
        other_user = User.objects.create_user(
            username="other_owner2",
            email="other_owner2@example.com",
            password="OtherOwner456!",
        )
        other_org = Organization.objects.create(
            name="Other Personal 2",
            slug="other-personal-2",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=other_user,
            organization=other_org,
            role=OrgRole.OWNER,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=other_org,
            role=OrgRole.MEMBER,
        )

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )
        assert response.status_code == 302
        # cancel_current_subscription must be called exactly once, for
        # the user's OWN personal org, not for the one they only belong
        # to as a member.
        mock_cancel.assert_called_once_with(
            ANY,
            organization=owned_org,
            capture_transition=True,
        )

    # ------------------------------------------------------------------
    # multi-eligible-org cancellation
    # ------------------------------------------------------------------

    def test_account_delete_cancels_two_sole_member_personal_orgs(
        self, authenticated_client, user
    ):
        """When the user is the sole member of two personal orgs, both
        subscriptions are cancelled — multi-org fix."""
        from unittest.mock import patch

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # First sole-member personal org.
        org_a = Organization.objects.create(
            name="Personal A",
            slug="personal-a",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org_a,
            role=OrgRole.OWNER,
        )

        # Second sole-member personal org.
        org_b = Organization.objects.create(
            name="Personal B",
            slug="personal-b",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org_b,
            role=OrgRole.OWNER,
        )

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )
        assert response.status_code == 302
        # Both orgs must be cancelled.
        assert mock_cancel.call_count == 2
        # Order of iteration over the queryset is not guaranteed, so we
        # check that both orgs appear in the call arguments.
        called_orgs = {
            call.kwargs["organization"] for call in mock_cancel.call_args_list
        }
        assert called_orgs == {org_a, org_b}

    def test_account_delete_cancels_only_sole_member_personal_org(
        self, authenticated_client, user, user_data
    ):
        """When the user owns two personal orgs — one sole-member and one
        that will survive (has other members and another owner) — only
        the sole-member org's subscription is cancelled.

        Surviving-org exclusion fix.
        """
        from unittest.mock import ANY, patch

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # Sole-member personal org — will be cancelled.
        sole_org = Organization.objects.create(
            name="Sole Personal",
            slug="sole-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=sole_org,
            role=OrgRole.OWNER,
        )

        # Surviving personal org: user is an owner, but there is another
        # owner AND another member so the org survives the deletion.
        # This org has other_owners_exist (not blocked by last-owner
        # guard) AND has other members (should be excluded from
        # cancellation by the fix).
        surviving_org = Organization.objects.create(
            name="Surviving Personal",
            slug="surviving-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=surviving_org,
            role=OrgRole.OWNER,
        )
        User = get_user_model()
        other_owner = User.objects.create_user(
            username="other_owner3",
            email="other_owner3@example.com",
            password="OtherOwner789!",
        )
        OrganizationMembership.objects.create(
            user=other_owner,
            organization=surviving_org,
            role=OrgRole.OWNER,
        )
        other_member = User.objects.create_user(
            username="other_member",
            email="other_member@example.com",
            password="OtherMember123!",
        )
        OrganizationMembership.objects.create(
            user=other_member,
            organization=surviving_org,
            role=OrgRole.MEMBER,
        )

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )
        assert response.status_code == 302
        # Only the sole-member org must be cancelled.
        mock_cancel.assert_called_once_with(
            ANY,
            organization=sole_org,
            capture_transition=True,
        )

    # ------------------------------------------------------------------
    # missing-Stripe-id anomaly blocks destructive account deletion
    # ------------------------------------------------------------------

    def test_account_delete_blocks_missing_stripe_id_anomaly(
        self, authenticated_client, user
    ):
        """When ``cancel_current_subscription`` raises
        ``BillingSubscriptionAnomalyError`` (subscription row exists but
        has no Stripe id), account deletion fails closed."""
        from unittest.mock import patch

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model
        from quickscale_modules_billing.exceptions import (
            BillingSubscriptionAnomalyError,
        )
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        org = Organization.objects.create(
            name="SA41 Personal",
            slug="sa41-personal",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
            side_effect=BillingSubscriptionAnomalyError(
                "Current recurring subscription is missing a Stripe subscription id."
            ),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "missing a Stripe subscription id" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    def test_account_delete_blocks_billing_validation_error(
        self, authenticated_client, user
    ):
        """Typed billing validation failures block deletion instead of disappearing."""
        from unittest.mock import patch

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model
        from quickscale_modules_billing.exceptions import BillingValidationError
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        org = Organization.objects.create(
            name="SA41 No Sub",
            slug="sa41-no-sub",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )

        with patch(
            "quickscale_modules_billing._subscription_mutations.cancel_current_subscription",
            side_effect=BillingValidationError(
                "Organization does not have a current recurring subscription."
            ),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "does not have a current recurring subscription" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    def test_account_delete_blocks_billing_configuration_error(
        self, authenticated_client, user
    ):
        """Known billing configuration failures render a fail-closed response."""
        from unittest.mock import patch

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model
        from quickscale_modules_billing.models import Plan, Subscription
        from quickscale_modules_billing.exceptions import BillingConfigurationError
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Missing Billing Configuration",
            slug="missing-billing-configuration",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.OWNER,
        )
        plan = Plan.objects.create(
            name="Missing Billing Configuration Plan",
            slug="missing-billing-configuration",
            stripe_price_id="price_missing_billing_configuration",
            credits_per_period=100,
            price_cents=1900,
            currency="usd",
            billing_interval=Plan.BillingInterval.MONTHLY,
        )
        with org_scope(organization):
            Subscription.objects.create(
                organization=organization,
                user=user,
                plan=plan,
                status=Subscription.Status.ACTIVE,
                stripe_subscription_id="sub_missing_billing_configuration",
            )

        with patch(
            "quickscale_modules_billing._stripe_client.get_stripe_client",
            side_effect=BillingConfigurationError("Stripe secret key is missing."),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "Stripe secret key is missing" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    def test_account_delete_detaches_former_member_billing_provenance(
        self, authenticated_client, user, caplog
    ):
        """Billing references survive a former member with nullable provenance."""
        import logging

        from django.contrib.auth import get_user_model
        from quickscale_modules_billing.models import (
            CreditBalance,
            CreditTransaction,
            Plan,
            PurchaseCheckout,
            Subscription,
        )
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )
        from quickscale_modules_orgs.removal import (
            OWNED_TENANT_ROWS,
            PURGE_TOMBSTONE,
            SOCIAL_CACHE_STATE,
        )

        organization = Organization.objects.create(
            name="Former Member Billing",
            slug="former-member-billing",
        )
        owner = get_user_model().objects.create_user(
            username="former-member-owner",
            email="former-member-owner@example.com",
            password="FormerMemberOwner123!",
        )
        OrganizationMembership.objects.create(
            user=owner,
            organization=organization,
            role=OrgRole.OWNER,
        )
        former_membership = OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.MEMBER,
        )
        plan = Plan.objects.create(
            name="Former Member Plan",
            slug="former-member-plan",
            stripe_price_id="price_former_member",
            credits_per_period=100,
            price_cents=1900,
            currency="usd",
            billing_interval=Plan.BillingInterval.MONTHLY,
        )
        with org_scope(organization):
            balance = CreditBalance.all_objects.create(
                user=user,
                organization=organization,
                balance=25,
            )
            transaction_row = CreditTransaction.all_objects.create(
                user=user,
                organization=organization,
                amount=25,
                transaction_type=CreditTransaction.TransactionType.PURCHASE,
                balance_after=25,
            )
            purchase_checkout = PurchaseCheckout.all_objects.create(
                user=user,
                organization=organization,
                plan=plan,
                status=PurchaseCheckout.Status.EXPIRED,
            )
            subscription = Subscription.all_objects.create(
                user=user,
                organization=organization,
                plan=plan,
                status=Subscription.Status.CANCELED,
            )
        former_membership.delete()

        caplog.set_level(logging.INFO, logger="quickscale_modules_auth.views")
        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))

        assert response.status_code == 302
        assert not get_user_model().objects.filter(pk=user.pk).exists()
        with org_scope(organization):
            balance.refresh_from_db()
            transaction_row.refresh_from_db()
            purchase_checkout.refresh_from_db()
            subscription.refresh_from_db()
        assert balance.user_id is None
        assert transaction_row.user_id is None
        assert purchase_checkout.user_id is None
        assert subscription.user_id is None
        for obligation_name in (
            OWNED_TENANT_ROWS,
            SOCIAL_CACHE_STATE,
            PURGE_TOMBSTONE,
        ):
            assert any(
                obligation_name in message and str(organization.pk) in message
                for message in caplog.messages
            )

    def test_account_delete_retries_when_billing_reference_changes(
        self, authenticated_client, user
    ):
        """A late FK reference rolls back cleanly and asks the user to retry."""
        from unittest.mock import patch

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model
        from django.db import IntegrityError

        with patch.object(
            type(user),
            "delete",
            side_effect=IntegrityError("late billing reference"),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "Provider references changed" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    # ------------------------------------------------------------------
    # success-message fix
    # ------------------------------------------------------------------

    def test_account_delete_success_message(self, authenticated_client, user):
        """A permitted deletion fires the success message.

        We spy on ``messages.success`` rather than reading from the
        session after the redirect because Django's auth middleware
        calls ``logout()`` → ``session.flush()`` when the deleted user
        cannot be resolved on the next request, which clears messages.
        """
        from unittest.mock import patch, ANY

        with patch("django.contrib.messages.success") as mock_success:
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )
        assert response.status_code == 302
        mock_success.assert_called_once_with(
            ANY,
            "Your account has been deleted successfully.",
        )


# ------------------------------------------------------------------
# account-deletion must not CASCADE-destroy org content
#
# The cross-module user-FK conformance gate now lives in
# ``orgs/tests/test_user_fk_conformance.py``, where the test harness
# includes blog, crm, and all other ``quickscale_modules_*`` apps.
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountDeleteViewSA35:
    """Regression: account deletion preserves content authored by
    the deleted user in org records that are reachable from the auth
    test suite (orgs module installed).

    Full end-to-end coverage for blog Post and CRM ContactNote /
    DealNote requires the respective modules to be installed — those
    tests live in each module's own test suite.
    """

    def test_account_delete_succeeds_with_personal_org_membership(
        self, authenticated_client, user
    ):
        """Account deletion succeeds when the user has a personal org
        membership (CASCADE-on-membership is intentional). This
        is the simplest case: a personal org where the user is the sole
        member; no other members or shared-org protection applies."""
        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        # Create an org and membership so the user has a personal org.
        org = Organization.objects.create(
            name="SA35 Test Org",
            slug="sa35-test-org",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        # Deletion must succeed — no last-owner or other guard blocks it.
        assert response.status_code == 302
        assert not get_user_model().objects.filter(id=user.id).exists()

    def test_account_delete_preserves_other_membership_records(
        self, authenticated_client, user, user_data
    ):
        """When a user is one of multiple owners of a shared org, their
        deletion removes only *their* membership record without affecting
        other members or the org itself."""
        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        org = Organization.objects.create(
            name="SA35 Shared Org",
            slug="sa35-shared-org",
            is_personal=False,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )
        User = get_user_model()
        other_user = User.objects.create_user(
            username="sa35_other",
            email="sa35_other@example.com",
            password="SA35Other123!",
        )
        OrganizationMembership.objects.create(
            user=other_user,
            organization=org,
            role=OrgRole.OWNER,
        )

        user_id = user.id
        org_id = org.id
        other_user_id = other_user.id

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))
        assert response.status_code == 302
        # User is gone.
        assert not get_user_model().objects.filter(id=user_id).exists()
        # Org still exists.
        assert Organization.objects.filter(id=org_id).exists()
        # Other user still exists.
        assert get_user_model().objects.filter(id=other_user_id).exists()
        # Other user's membership survives.
        assert OrganizationMembership.objects.filter(
            user=other_user,
            organization=org,
        ).exists()


class _StubProviderError(Exception):
    """A provider-state error a stub handler declares as fail-closed."""


class _IncompleteAccountDeletionHandler:
    """A declared handler missing the operations the capability requires."""

    label = "incomplete_provider"

    def account_deletion_handled_app_labels(self):
        return (self.label,)

    def account_deletion_fail_closed_errors(self):
        return (_StubProviderError,)


class _StubAccountDeletionHandler:
    """A rule 4 account-deletion handler that records the calls it receives."""

    label = "stub_provider"

    def __init__(
        self,
        calls: list[Any],
        *,
        reference_organization_ids: tuple[int, ...] = (),
        reconcile_scope: str = "cancellation",
        cancel_error: Exception | None = None,
        lock_error: Exception | None = None,
        transition: object | None = None,
        on_cancel=None,
    ) -> None:
        self._calls = calls
        self._reference_organization_ids = reference_organization_ids
        self._reconcile_scope = reconcile_scope
        self._cancel_error = cancel_error
        self._lock_error = lock_error
        self._transition = transition
        self._on_cancel = on_cancel
        self.reconciled_organization_ids: list[Any] = []

    def account_deletion_handled_app_labels(self) -> tuple[str, ...]:
        return (self.label,)

    def account_deletion_fail_closed_errors(self) -> tuple[type[BaseException], ...]:
        return (_StubProviderError,)

    def account_deletion_reconcile_scope(self) -> str:
        return self._reconcile_scope

    def account_deletion_user_reference_organization_ids(self, user_id):
        self._calls.append("discover")
        return self._reference_organization_ids

    def account_deletion_subscription_mutation_lock(self, organization_id):
        from contextlib import contextmanager, nullcontext

        self._calls.append("lock")
        if self._lock_error is None:
            return nullcontext()

        @contextmanager
        def raise_on_enter():
            raise self._lock_error
            yield

        return raise_on_enter()

    def reconcile_account_deletion_purchase_provider_state(
        self, organization_id, user_id
    ) -> None:
        self._calls.append("purchase")

    def reconcile_account_deletion_provider_state(self, organization_id) -> None:
        self._calls.append("reconcile")
        self.reconciled_organization_ids.append(organization_id)

    def cancel_account_deletion_subscription(self, user, organization):
        self._calls.append("cancel")
        if self._on_cancel is not None:
            self._on_cancel(organization)
        if self._cancel_error is not None:
            raise self._cancel_error
        return self._transition

    def resume_account_deletion_subscription(
        self, user, organization, transition
    ) -> None:
        self._calls.append(("resume", transition))

    def detach_account_deletion_user_references(self, user_id, organization_ids) -> int:
        self._calls.append("detach")
        return 0


@contextmanager
def _declared_handlers(*handlers):
    """Install *handlers* as the declared account-deletion providers for one request.

    The app-config lookup answers with each handler for the labels it claims,
    mirroring the identity between a provider and its own app config.
    """
    from unittest.mock import patch

    def resolve(label):
        return next(
            handler
            for handler in handlers
            if label in handler.account_deletion_handled_app_labels()
        )

    with (
        patch(
            "quickscale_modules_auth.views.collect_capabilities",
            return_value=handlers,
        ),
        patch(
            "quickscale_modules_auth.views._installed_app_config",
            side_effect=resolve,
        ),
    ):
        yield


@pytest.mark.django_db
class TestAccountDeleteViewDeclaredHandlers:
    """Rule 4: account deletion drives declared handlers, not module names."""

    def test_account_delete_drives_the_declared_handler(
        self, authenticated_client, user
    ):
        """Every declared operation runs in order for the user's personal org."""

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Declared Handler",
            slug="declared-handler",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.OWNER,
        )
        calls: list[str] = []
        handler = _StubAccountDeletionHandler(
            calls,
            reference_organization_ids=(organization.pk,),
        )

        with _declared_handlers(handler):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302
        assert not get_user_model().objects.filter(pk=user.pk).exists()
        assert calls == [
            "discover",
            "lock",
            "purchase",
            "reconcile",
            "cancel",
            "discover",
            "detach",
        ]

    def test_account_delete_blocks_when_a_declared_handler_is_incomplete(
        self, authenticated_client, user
    ):
        """A handler missing a protocol operation fails the deletion closed."""

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model

        with _declared_handlers(_IncompleteAccountDeletionHandler()):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        message_text = " ".join(
            str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )
        assert "account-deletion capability" in message_text
        assert "cancel_account_deletion_subscription" in message_text

    def test_account_delete_blocks_on_a_declared_provider_error(
        self, authenticated_client, user
    ):
        """A fail-closed error declared by the handler renders a blocked response."""

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Declared Error",
            slug="declared-error",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.OWNER,
        )
        handler = _StubAccountDeletionHandler(
            [],
            cancel_error=_StubProviderError("provider state is not terminal"),
        )

        with _declared_handlers(handler):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "provider state is not terminal" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    def test_account_delete_reraises_an_undeclared_provider_error(
        self, authenticated_client, user
    ):
        """An error outside the declared set propagates instead of being masked."""

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Undeclared Error",
            slug="undeclared-error",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.OWNER,
        )
        handler = _StubAccountDeletionHandler(
            [],
            cancel_error=ValueError("unexpected provider defect"),
        )

        with (
            _declared_handlers(handler),
            pytest.raises(ValueError, match="unexpected provider defect"),
        ):
            authenticated_client.post(reverse("quickscale_auth:account_delete"))

    def test_account_delete_blocks_on_an_unknown_reconcile_scope(
        self, authenticated_client, user
    ):
        """A handler declaring an unknown reconcile scope fails closed."""

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model

        handler = _StubAccountDeletionHandler([], reconcile_scope="everywhere")

        with _declared_handlers(handler):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "unknown reconcile scope" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    def test_account_delete_reconciles_a_touched_scope_handler_for_retained_orgs(
        self, authenticated_client, user
    ):
        """A touched-scope handler reconciles every organization the deletion touches."""

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        shared_org = Organization.objects.create(
            name="Retained Touched",
            slug="retained-touched",
        )
        owner = get_user_model().objects.create_user(
            username="touched-owner",
            email="touched-owner@example.com",
            password="TouchedOwner123!",
        )
        OrganizationMembership.objects.create(
            user=owner,
            organization=shared_org,
            role=OrgRole.OWNER,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=shared_org,
            role=OrgRole.MEMBER,
        )
        calls: list[Any] = []
        handler = _StubAccountDeletionHandler(calls, reconcile_scope="touched")

        with _declared_handlers(handler):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 302
        assert handler.reconciled_organization_ids == [shared_org.pk]

    def test_account_delete_compensates_each_handler_with_its_own_transition(
        self, authenticated_client, user
    ):
        """Each declared handler is resumed with the transition it produced."""
        from types import SimpleNamespace

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Shared Compensation",
            slug="shared-compensation",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.OWNER,
        )
        other_owner = get_user_model().objects.create_user(
            username="compensation-owner",
            email="compensation-owner@example.com",
            password="CompensationOwner123!",
        )
        first_transition = SimpleNamespace(changed=True)
        second_transition = SimpleNamespace(changed=True)
        first_calls: list[Any] = []
        second_calls: list[Any] = []

        def reject_deletion(org):
            OrganizationMembership.objects.create(
                user=other_owner,
                organization=org,
                role=OrgRole.OWNER,
            )

        first = _StubAccountDeletionHandler(
            first_calls,
            transition=first_transition,
        )
        second = _StubAccountDeletionHandler(
            second_calls,
            transition=second_transition,
            on_cancel=reject_deletion,
        )
        second.label = "stub_provider_second"

        with _declared_handlers(first, second):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert first_calls[-1] == ("resume", first_transition)
        assert second_calls[-1] == ("resume", second_transition)

    def test_account_delete_blocks_a_handler_that_is_not_its_app_config(
        self, authenticated_client, user
    ):
        """A handler claiming an app's label must be that app's own config."""
        from unittest.mock import patch

        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model

        handler = _StubAccountDeletionHandler([])
        handler.label = "quickscale_billing"

        with patch(
            "quickscale_modules_auth.views.collect_capabilities",
            return_value=(handler,),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "not that app's config" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    def test_account_delete_blocks_on_a_declared_lock_error(
        self, authenticated_client, user
    ):
        """A declared provider error while acquiring a lock blocks the deletion."""
        from django.contrib import messages as messages_framework
        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organization = Organization.objects.create(
            name="Declared Lock Error",
            slug="declared-lock-error",
            is_personal=True,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=organization,
            role=OrgRole.OWNER,
        )
        handler = _StubAccountDeletionHandler(
            [],
            lock_error=_StubProviderError("provider lock unavailable"),
        )

        with _declared_handlers(handler):
            response = authenticated_client.post(
                reverse("quickscale_auth:account_delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "provider lock unavailable" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    @pytest.mark.parametrize("lock_error_type", [ValueError, KeyboardInterrupt])
    def test_account_delete_releases_acquired_locks_on_an_undeclared_lock_error(
        self, authenticated_client, user, lock_error_type
    ):
        """An unexpected acquisition failure releases every acquired lock."""
        from contextlib import contextmanager

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organizations = [
            Organization.objects.create(
                name=f"Lock Release {index}",
                slug=f"lock-release-{index}",
                is_personal=True,
            )
            for index in range(2)
        ]
        for organization in organizations:
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrgRole.OWNER,
            )
        events: list[tuple[str, Any]] = []
        handler = _StubAccountDeletionHandler([])
        acquisitions = {"count": 0}

        @contextmanager
        def recording_lock(organization_id):
            events.append(("enter", organization_id))
            yield
            events.append(("exit", organization_id))

        def fail_second_lock(organization_id):
            acquisitions["count"] += 1
            if acquisitions["count"] == 2:
                raise lock_error_type("unexpected lock defect")
            return recording_lock(organization_id)

        handler.account_deletion_subscription_mutation_lock = fail_second_lock
        first_organization_id = sorted(
            (organization.pk for organization in organizations), key=str
        )[0]

        with (
            _declared_handlers(handler),
            pytest.raises(lock_error_type, match="unexpected lock defect"),
        ):
            authenticated_client.post(reverse("quickscale_auth:account_delete"))

        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert events == [
            ("enter", first_organization_id),
            ("exit", first_organization_id),
        ]

    def test_account_delete_preserves_the_acquisition_error_when_cleanup_fails(
        self, authenticated_client, user
    ):
        """A failing lock release cannot replace the error that triggered it."""
        from contextlib import contextmanager

        from django.contrib.auth import get_user_model

        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        organizations = [
            Organization.objects.create(
                name=f"Cleanup Failure {index}",
                slug=f"cleanup-failure-{index}",
                is_personal=True,
            )
            for index in range(2)
        ]
        for organization in organizations:
            OrganizationMembership.objects.create(
                user=user,
                organization=organization,
                role=OrgRole.OWNER,
            )
        events: list[tuple[str, Any]] = []
        handler = _StubAccountDeletionHandler([])
        acquisitions = {"count": 0}

        @contextmanager
        def failing_release_lock(organization_id):
            events.append(("enter", organization_id))
            try:
                yield
            finally:
                events.append(("exit", organization_id))
                raise RuntimeError("unlock failed")

        def fail_second_lock(organization_id):
            acquisitions["count"] += 1
            if acquisitions["count"] == 2:
                raise ValueError("unexpected lock defect")
            return failing_release_lock(organization_id)

        handler.account_deletion_subscription_mutation_lock = fail_second_lock
        first_organization_id = sorted(
            (organization.pk for organization in organizations), key=str
        )[0]

        with (
            _declared_handlers(handler),
            pytest.raises(ValueError, match="unexpected lock defect"),
        ):
            authenticated_client.post(reverse("quickscale_auth:account_delete"))

        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert events == [
            ("enter", first_organization_id),
            ("exit", first_organization_id),
        ]


@pytest.mark.django_db
class TestAccountDeleteViewAnonymization:
    """The declared anonymize executors run inside the deletion transaction."""

    def test_account_delete_scrubs_declared_module_personal_data(
        self, authenticated_client, user
    ):
        """A later handler receives the pre-scrub identity, not the scrubbed row."""
        from quickscale_modules_billing.models import WebhookEvent

        event = WebhookEvent.objects.create(
            stripe_event_id="evt-account-close",
            event_type="customer.updated",
            payload={"customer_details": {"email": user.email, "name": "Test User"}},
        )

        response = authenticated_client.post(reverse("quickscale_auth:account_delete"))

        assert response.status_code == 302
        event.refresh_from_db()
        assert event.payload["customer_details"] == {
            "email": "[redacted]",
            "name": "[redacted]",
        }

    def test_account_delete_rolls_back_anonymization_when_an_executor_fails(
        self, authenticated_client, user, monkeypatch
    ):
        """A failing executor rolls the whole deletion back, scrubs included."""
        from django.contrib.auth import get_user_model

        import quickscale_modules_billing._anonymization as billing_anonymization
        from quickscale_modules_billing.models import WebhookEvent

        event = WebhookEvent.objects.create(
            stripe_event_id="evt-account-close-failure",
            event_type="customer.updated",
            payload={"customer_details": {"email": user.email, "name": "Test User"}},
        )
        scrub = billing_anonymization.anonymize_account

        def redact_then_fail(
            user_arg, original_email, original_name, original_username
        ):
            scrub(user_arg, original_email, original_name, original_username)
            raise RuntimeError("post-redaction failure")

        monkeypatch.setattr(
            billing_anonymization, "anonymize_account", redact_then_fail
        )

        with pytest.raises(RuntimeError, match="post-redaction failure"):
            authenticated_client.post(reverse("quickscale_auth:account_delete"))

        event.refresh_from_db()
        assert event.payload["customer_details"]["email"] == user.email
        account = get_user_model().objects.filter(pk=user.pk).first()
        assert account is not None
        assert account.email == user.email
        assert account.is_active is True
