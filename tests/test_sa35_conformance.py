"""SA35 cross-module user-FK conformance gate.

This test lives in the orgs test suite because ``orgs/tests/settings.py``
is the smallest truthful cross-module harness: it includes blog, crm,
billing, and all other ``quickscale_modules_*`` apps.  The previous
auth-side conformance gate could only inspect the subset installed in
``auth/tests/settings.py``, which excluded blog and crm modules.
"""

from __future__ import annotations

import pytest
from django.apps import apps
from django.conf import settings
from django.db.models import CASCADE, PROTECT, SET_NULL
from django.test import Client


@pytest.mark.django_db
class TestUserFkDeleteRuleConformance:
    """Verify every user-FK in quickscale_modules_* is SET_NULL or
    PROTECT, unless explicitly allowlisted.

    This is a conformance / regression gate for SA35: FK referential
    actions bypass RLS, so a CASCADE user-FK in any tenant-scoped model
    would destroy org content when a user's account is deleted.
    """

    # ---- Required modules: all quickscale_modules_* apps with user-FKs ---
    # CR-SA35-001: This set acts as a registration guard so that adding a
    # new user-FK-bearing module to INSTALLED_APPS requires an explicit
    # entry here (and removing one produces a clear test failure).
    REQUIRED_MODULES: frozenset[str] = frozenset(
        {
            "quickscale_modules_auth",
            "quickscale_modules_orgs",
            "quickscale_modules_billing",
            "quickscale_modules_social",
            "quickscale_modules_forms",
            "quickscale_modules_listings",
            "quickscale_modules_blog",
            "quickscale_modules_crm",
            "quickscale_modules_backups",
        }
    )

    # ---- Allowlist: user-FKs that intentionally use CASCADE ----------
    # OrganizationMembership.user:  membership records should disappear
    #   with the user — there is no meaningful "orphan membership"; the
    #   org may still have other members, and the user is gone.
    # OrganizationInvitation.invited_by:  a pending invite disappearing
    #   with its sender is acceptable — the invitation represents an
    #   action by that specific user (documented in decisions.md §SA35).
    # AuthorProfile.user:  OneToOneField — the profile has no independent
    #   meaning without the user.  (Defined in blog, only checked when
    #   the blog module is installed.)
    ALLOWLISTED_CASCADE = frozenset(
        {
            ("OrganizationMembership", "user"),
            ("OrganizationInvitation", "invited_by"),
            ("AuthorProfile", "user"),
        }
    )

    def test_required_modules_installed(self) -> None:
        """CR-SA35-001: Verify every user-FK-bearing module is loaded.

        If this test fails, add the missing module to both
        ``REQUIRED_MODULES`` (here) and ``INSTALLED_APPS``
        (``tests/settings.py``).  Removing a module requires
        removing it from both sets intentionally.
        """
        installed_labels = frozenset(
            app.label
            for app in apps.get_app_configs()
            if app.label.startswith("quickscale_modules_")
        )
        missing = self.REQUIRED_MODULES - installed_labels
        assert not missing, (
            f"Required user-FK-bearing modules missing from INSTALLED_APPS: "
            f"{sorted(missing)}.  Add them to tests/settings.py INSTALLED_APPS."
        )

    def test_all_user_fk_delete_rules_conform(self) -> None:
        """Assert every FK to AUTH_USER_MODEL in installed
        quickscale_modules_* apps is SET_NULL or PROTECT, or is
        explicitly allowlisted."""
        User = apps.get_model(settings.AUTH_USER_MODEL)
        user_label = User._meta.label_lower

        violations: list[str] = []

        for model in apps.get_models():
            meta = model._meta
            app_label = meta.app_label

            # Only check models in our module workspace.
            if not app_label.startswith("quickscale_modules_"):
                continue

            for field in meta.local_fields:
                if not field.is_relation:
                    continue
                if field.remote_field is None:
                    continue
                related_model = field.remote_field.model
                # After the None check above, django-stubs guarantees
                # remote_field.model is a model class (not a lazy string
                # reference), because apps are fully loaded at test time.
                # Check if this FK targets AUTH_USER_MODEL.
                if related_model._meta.label_lower != user_label:
                    continue

                key = (meta.model.__name__, field.name)

                if field.remote_field.on_delete in (SET_NULL, PROTECT):
                    continue  # Acceptable — no CASCADE risk.
                if (
                    field.remote_field.on_delete is CASCADE
                    and key in self.ALLOWLISTED_CASCADE
                ):
                    continue  # Intentional — documented in decisions.md.

                violations.append(
                    f"{app_label}.{meta.model.__name__}.{field.name}: "
                    f"on_delete={field.remote_field.on_delete!r} "
                    f"(expected SET_NULL or PROTECT). "
                    f"Add to ALLOWLISTED_CASCADE only after documenting "
                    f"the rationale in decisions.md."
                )

        assert not violations, (
            f"{len(violations)} user-FK(s) with unexpected on_delete:\n"
            + "\n".join(violations)
        )

    def test_user_delete_survivor_regression(self) -> None:
        """Regression: ORM-level user.delete() does not cascade-destroy
        cross-module content (blog Post).

        All user-FKs in quickscale_modules_* are SET_NULL, PROTECT, or
        explicitly allowlisted CASCADE, so deleting a user must not
        destroy content authored by that user.  This test exercises the
        ORM path directly (bypassing auth view-layer guards already
        covered in the auth module's own test suite).
        """
        from quickscale_modules_blog.models import Post
        from quickscale_modules_orgs.models import Organization

        User = apps.get_model(settings.AUTH_USER_MODEL)
        user = User.objects.create_user(
            username="sa35_survivor",
            email="sa35_survivor@example.com",
            password="Sa35Survivor1!",
        )

        org = Organization.objects.create(
            name="SA35 Survivor Org",
            slug="sa35-survivor-org",
        )
        post = Post.objects.create(
            title="SA35 Survivor Post",
            author=user,
            organization=org,
        )
        post_id = post.pk
        user_id = user.pk

        # ORM-level delete — no auth view guards.
        user.delete()

        # Post must survive with author set to NULL.
        post.refresh_from_db()
        assert post.author is None
        # Verify the user is actually gone.
        assert not User.objects.filter(pk=user_id).exists()
        # Verify the post record itself still exists.
        # Use all_objects to bypass TenantManager auto-scoping — the test
        # does not set an org contextvar, so Post.objects would scope to
        # NULL org and miss this record.
        assert Post.all_objects.filter(pk=post_id).exists()


# ---------------------------------------------------------------------------
# SA35 — AccountDeleteView-level survivor regression (view + cross-module)
#
# The conformance tests above prove user-FKs are SET_NULL at the schema
# level.  This test proves the full AccountDeleteView path preserves
# cross-module content (blog Post and CRM ContactNote/DealNote) when a
# real user account is deleted through the view.
#
# This lives in the orgs harness because it needs blog, crm, and auth
# all installed simultaneously.
# ---------------------------------------------------------------------------


@pytest.fixture
def _sa35_user(db: None) -> object:
    """Create a test user for AccountDeleteView survivor regression."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    return User.objects.create_user(
        username="sa35_survivor_view",
        email="sa35_survivor_view@example.com",
        password="Sa35Survivor1!",
    )


@pytest.fixture
def _sa35_authenticated_client(db: None, _sa35_user: object) -> Client:
    """Return a client authenticated as the SA35 survivor test user."""
    client = Client()
    client.force_login(_sa35_user)
    return client


# Inheriting from object, not pytest-django's TestCase, so pytest fixtures
# from the conftest (reset_current_org_id) apply automatically.
@pytest.mark.django_db
class TestAccountDeleteViewSurvivorRegression:
    """SA35 regression: AccountDeleteView preserves blog + CRM content."""

    def _setup_org_and_membership(self, user: object) -> tuple[object, object]:
        """Create a personal org and membership so deletion is permitted.

        The personal org has the user as sole owner and sole member, so
        the last-owner guard in AccountDeleteView passes (no other members
        to protect).  The model-level last-owner guard is bypassed because
        CASCADE bulk-deletes the membership row during user.delete()
        without calling Membership.delete().
        """
        from quickscale_modules_orgs.models import (
            OrgRole,
            Organization,
            OrganizationMembership,
        )

        org = Organization.objects.create(
            name="SA35 Survivor View Org",
            slug="sa35-survivor-view-org",
            is_personal=False,
        )
        OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role=OrgRole.OWNER,
        )
        return org, OrganizationMembership

    def _create_blog_post(self, user: object, org: object) -> object:
        """Create a blog Post authored by *user* in *org*."""
        from quickscale_modules_blog.models import Post

        return Post.objects.create(
            title="SA35 Survivor View Post",
            author=user,
            organization=org,
        )

    def _create_crm_contact_note(self, user: object, org: object) -> object:
        """Create a CRM ContactNote whose created_by points to *user*."""
        from quickscale_modules_crm.models import (
            Company,
            Contact,
            ContactNote,
        )

        company = Company.objects.create(
            name="SA35 Survivor Co",
            organization=org,
        )
        contact = Contact.objects.create(
            first_name="Sa35",
            last_name="Contact",
            email="sa35_contact@example.com",
            company=company,
            organization=org,
        )
        return ContactNote.objects.create(
            contact=contact,
            created_by=user,
            text="SA35 survivor regression note",
            organization=org,
        )

    def _create_crm_deal_note(self, user: object, org: object) -> object:
        """Create a CRM DealNote whose created_by points to *user*."""
        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )

        company = Company.objects.create(
            name="SA35 Survivor Deal Co",
            organization=org,
        )
        contact = Contact.objects.create(
            first_name="Sa35",
            last_name="DealContact",
            email="sa35_deal_contact@example.com",
            company=company,
            organization=org,
        )
        stage = Stage.objects.create(
            name="SA35 Pipeline",
            order=1,
            organization=org,
        )
        deal = Deal.objects.create(
            title="SA35 Survivor Deal",
            contact=contact,
            stage=stage,
            organization=org,
        )
        return DealNote.objects.create(
            deal=deal,
            created_by=user,
            text="SA35 survivor deal note",
            organization=org,
        )

    def test_account_delete_view_preserves_blog_and_crm_content(
        self, _sa35_user: object, _sa35_authenticated_client: Client
    ) -> None:
        """AccountDeleteView must not destroy blog Post or CRM notes.

        This is the view-level end-to-end regression that the ORM-only
        survivor test cannot cover: it exercises the full auth view stack
        (session, authentication, last-owner guard, form_valid dispatch,
        user.delete()) with cross-module content present on the user
        being deleted.
        """
        user = _sa35_user
        client = _sa35_authenticated_client
        from django.contrib.auth import get_user_model

        User = get_user_model()

        # ---- Setup ----
        org, _ = self._setup_org_and_membership(user)
        post = self._create_blog_post(user, org)
        contact_note = self._create_crm_contact_note(user, org)
        deal_note = self._create_crm_deal_note(user, org)

        post_id = post.pk
        user_id = user.pk

        # ---- Act: delete via AccountDeleteView ----
        from django.urls import reverse

        response = client.post(reverse("quickscale_auth:account-delete"))

        # ---- Assert: deletion succeeded ----
        assert response.status_code == 302, (
            f"Expected 302 redirect on account deletion, got {response.status_code}"
        )
        assert not User.objects.filter(pk=user_id).exists(), "User should be deleted"

        # ---- Assert: blog Post survives with author=NULL ----
        from quickscale_modules_blog.models import Post

        post.refresh_from_db()
        assert post.author is None, (
            "Blog Post.author should be NULL after user deletion"
        )
        assert Post.all_objects.filter(pk=post_id).exists(), (
            "Blog Post record should still exist"
        )

        # ---- Assert: CRM ContactNote survives with created_by=NULL ----
        contact_note.refresh_from_db()
        assert contact_note.created_by is None, (
            "CRM ContactNote.created_by should be NULL after user deletion"
        )

        # ---- Assert: CRM DealNote survives with created_by=NULL ----
        deal_note.refresh_from_db()
        assert deal_note.created_by is None, (
            "CRM DealNote.created_by should be NULL after user deletion"
        )
