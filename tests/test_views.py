"""Tests for auth module views"""

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
        response = anonymous_client.get(reverse("quickscale_auth:profile-edit"))
        assert response.status_code == 302

    def test_profile_update_get(self, authenticated_client):
        """Test profile update GET displays form"""
        response = authenticated_client.get(reverse("quickscale_auth:profile-edit"))
        assert response.status_code == 200

    def test_profile_update_post_valid(self, authenticated_client, user):
        """Test profile update with valid data"""
        response = authenticated_client.post(
            reverse("quickscale_auth:profile-edit"),
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
        response = anonymous_client.get(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 302

    def test_account_delete_get(self, authenticated_client):
        """Test account delete GET displays confirmation"""
        response = authenticated_client.get(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 200

    def test_account_delete_post(self, authenticated_client, user):
        """Test account deletion — permitted when user has no blocking orgs"""
        from django.contrib.auth import get_user_model

        user_model = get_user_model()
        user_id = user.id
        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 302
        assert not user_model.objects.filter(id=user_id).exists()

    # ------------------------------------------------------------------
    # SA28 — last-owner guard
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

        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
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

        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
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

        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
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

        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 302

    def test_account_delete_blocked_when_sole_owner_of_memberful_personal_org(
        self, authenticated_client, user, user_data
    ):
        """Deletion is blocked when the user is the sole owner of a
        personal org that has other members — CR-SA28-001 last-owner
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

        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
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
        subscription cancellation for that org — CR-SA28-001 non-owner
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
            "quickscale_modules_billing.services.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
            )
        assert response.status_code == 302
        # The cancel function must NOT be called — user is not an owner
        # of any personal org, only a member of someone else's.
        mock_cancel.assert_not_called()

    # ------------------------------------------------------------------
    # SA28 — personal-org subscription cancellation
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
            "quickscale_modules_billing.services.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
            "quickscale_modules_billing.services.cancel_current_subscription",
            side_effect=record_atomic_state,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
                "quickscale_modules_billing.services.get_stripe_client",
                return_value=stripe_client,
            ),
            patch(
                "quickscale_modules_billing.services.cancel_current_subscription"
            ) as mock_cancel,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
            "quickscale_modules_billing.services.get_stripe_client",
            return_value=stripe_client,
        ):
            authenticated_client.post(reverse("quickscale_auth:account-delete"))

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
                "quickscale_modules_billing.services.get_stripe_client",
                return_value=stripe_client,
            ),
            patch(
                "quickscale_modules_billing.services.cancel_current_subscription"
            ) as mock_cancel,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
            "quickscale_modules_billing.services.get_stripe_client",
            return_value=stripe_client,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
                reverse("quickscale_auth:account-delete")
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
                reverse("quickscale_auth:account-delete")
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
            "quickscale_modules_billing.services.subscription_provider_mutation_lock",
            side_effect=record_provider_lock,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
                "quickscale_modules_billing.services."
                "subscription_provider_mutation_lock",
                side_effect=record_provider_lock,
            ),
            patch(
                "quickscale_modules_billing.services.cancel_current_subscription",
                side_effect=add_concurrent_owner,
            ) as mock_cancel,
            patch(
                "quickscale_modules_billing.services.resume_current_subscription",
                side_effect=record_resume,
            ) as mock_resume,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
                "quickscale_modules_billing.services.cancel_current_subscription",
                side_effect=preserve_existing_state,
            ),
            patch(
                "quickscale_modules_billing.services.resume_current_subscription"
            ) as mock_resume,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
                "quickscale_modules_billing.services.cancel_current_subscription",
                side_effect=fail_second_cancellation,
            ),
            patch(
                "quickscale_modules_billing.services.resume_current_subscription"
            ) as mock_resume,
            pytest.raises(RuntimeError, match="provider response lost"),
        ):
            authenticated_client.post(reverse("quickscale_auth:account-delete"))

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
                "quickscale_modules_billing.services.cancel_current_subscription",
                return_value=transition,
            ),
            patch(
                "quickscale_modules_billing.services.resume_current_subscription"
            ) as mock_resume,
            patch.object(
                type(user), "delete", side_effect=RuntimeError("delete failed")
            ),
            pytest.raises(RuntimeError, match="delete failed"),
        ):
            authenticated_client.post(reverse("quickscale_auth:account-delete"))

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
                "quickscale_modules_billing.services.cancel_current_subscription",
                side_effect=change_membership,
            ),
            patch(
                "quickscale_modules_billing.services.resume_current_subscription",
                side_effect=[RuntimeError("resume failed"), None],
            ) as mock_resume,
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
            )

        assert response.status_code == 200
        assert mock_resume.call_count == 2
        assert any(
            "Manual billing reconciliation" in message for message in caplog.messages
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
        with patch("quickscale_modules_billing.services.cancel_current_subscription"):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
        with patch("quickscale_modules_billing.services.cancel_current_subscription"):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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

    def test_account_delete_graceful_when_billing_not_installed(
        self, authenticated_client, user
    ):
        """Deletion does not fail when the billing module is not
        installed."""
        # Patch INSTALLED_APPS so the billing guard in
        # _cancel_personal_org_subscriptions skips the billing code.
        from unittest.mock import patch

        from django.conf import settings

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

        with patch.object(
            settings,
            "INSTALLED_APPS",
            [app for app in settings.INSTALLED_APPS if app != "quickscale_billing"],
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
            )
        # Deletion proceeds even though billing is not installed.
        assert response.status_code == 302

    def test_account_delete_cancels_only_owned_personal_org(
        self, authenticated_client, user
    ):
        """When the user is an owner of one personal org and a mere
        member of another, only the owned personal org's subscription
        is cancelled — CR-SA28-001 multi-personal-org guard."""
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
            "quickscale_modules_billing.services.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
    # SA28 — multi-eligible-org cancellation (CR-SA28-001)
    # ------------------------------------------------------------------

    def test_account_delete_cancels_two_sole_member_personal_orgs(
        self, authenticated_client, user
    ):
        """When the user is the sole member of two personal orgs, both
        subscriptions are cancelled — CR-SA28-001 multi-org fix."""
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
            "quickscale_modules_billing.services.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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

        CR-SA28-001 surviving-org exclusion fix.
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
            "quickscale_modules_billing.services.cancel_current_subscription"
        ) as mock_cancel:
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
            )
        assert response.status_code == 302
        # Only the sole-member org must be cancelled.
        mock_cancel.assert_called_once_with(
            ANY,
            organization=sole_org,
            capture_transition=True,
        )

    # ------------------------------------------------------------------
    # SA41 — missing-Stripe-id anomaly blocks destructive account deletion
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
        from quickscale_modules_billing.services import (
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
            "quickscale_modules_billing.services.cancel_current_subscription",
            side_effect=BillingSubscriptionAnomalyError(
                "Current recurring subscription is missing a Stripe subscription id."
            ),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
        from quickscale_modules_billing.services import (
            BillingValidationError,
        )
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
            "quickscale_modules_billing.services.cancel_current_subscription",
            side_effect=BillingValidationError(
                "Organization does not have a current recurring subscription."
            ),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
        from quickscale_modules_billing.services import BillingConfigurationError
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
            "quickscale_modules_billing.services.get_stripe_client",
            side_effect=BillingConfigurationError("Stripe secret key is missing."),
        ):
            response = authenticated_client.post(
                reverse("quickscale_auth:account-delete")
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
        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))

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
                reverse("quickscale_auth:account-delete")
            )

        assert response.status_code == 200
        assert get_user_model().objects.filter(pk=user.pk).exists()
        assert any(
            "Billing references changed" in str(message.message)
            for message in messages_framework.get_messages(response.wsgi_request)
        )

    # ------------------------------------------------------------------
    # SA28 — success-message fix
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
                reverse("quickscale_auth:account-delete")
            )
        assert response.status_code == 302
        mock_success.assert_called_once_with(
            ANY,
            "Your account has been deleted successfully.",
        )


# ------------------------------------------------------------------
# SA35 — account-deletion must not CASCADE-destroy org content
#
# The cross-module user-FK conformance gate now lives in
# ``orgs/tests/test_sa35_conformance.py``, where the test harness
# includes blog, crm, and all other ``quickscale_modules_*`` apps.
# ------------------------------------------------------------------


@pytest.mark.django_db
class TestAccountDeleteViewSA35:
    """SA35 regression: account deletion preserves content authored by
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
        membership (CASCADE-on-membership is intentional — SA35).  This
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

        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
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

        response = authenticated_client.post(reverse("quickscale_auth:account-delete"))
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
