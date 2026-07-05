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
            [
                app
                for app in settings.INSTALLED_APPS
                if app != "quickscale_modules_billing"
            ],
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
