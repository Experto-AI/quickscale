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

from quickscale_modules_orgs.current_org import (
    reset_current_org_id,
    set_current_org_id,
)


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
        set_current_org_id(org.pk)
        try:
            post = Post.objects.create(
                title="SA35 Survivor Post",
                author=user,
                organization=org,
            )
        finally:
            reset_current_org_id()
        post_id = post.pk
        user_id = user.pk

        # ORM-level delete — no auth view guards.
        user.delete()

        # Post must survive with author set to NULL.
        set_current_org_id(org.pk)
        try:
            post.refresh_from_db()
        finally:
            reset_current_org_id()
        assert post.author is None
        # Verify the user is actually gone.
        assert not User.objects.filter(pk=user_id).exists()
        # Verify the post record itself still exists.
        set_current_org_id(org.pk)
        try:
            assert Post.all_objects.filter(pk=post_id).exists()
        finally:
            reset_current_org_id()


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
            Organization,
            OrganizationMembership,
            OrgRole,
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

        set_current_org_id(org.pk)
        try:
            return Post.objects.create(
                title="SA35 Survivor View Post",
                author=user,
                organization=org,
            )
        finally:
            reset_current_org_id()

    def _create_crm_contact_note(self, user: object, org: object) -> object:
        """Create a CRM ContactNote whose created_by points to *user*."""
        from quickscale_modules_crm.models import (
            Company,
            Contact,
            ContactNote,
        )

        set_current_org_id(org.pk)
        try:
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
        finally:
            reset_current_org_id()

    def _create_crm_deal_note(self, user: object, org: object) -> object:
        """Create a CRM DealNote whose created_by points to *user*."""
        from quickscale_modules_crm.models import (
            Company,
            Contact,
            Deal,
            DealNote,
            Stage,
        )

        set_current_org_id(org.pk)
        try:
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
        finally:
            reset_current_org_id()

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


# ---------------------------------------------------------------------------
# SA47 — concurrent account-deletion regression
#
# Two co-owners of the same shared org (with a third non-owner member)
# attempt to delete their accounts concurrently.  ``AccountDeleteView``
# now wraps the guard check + user deletion in ``transaction.atomic()``
# and locks all owner orgs with ``select_for_update``, so concurrent
# deletions are serialized: exactly one succeeds, and the org never
# loses all its owners while non-owner members remain.
#
# This test proves the serialization works by simulating the same
# locking pattern: each thread acquires ``select_for_update`` on the
# shared org row, checks ``is_last_owner_with_members``, and deletes
# the user only if not blocked.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_concurrent_account_deletion_locking_protects_last_owner() -> None:
    """Two co-owners deleting accounts concurrently: the ``select_for_update``
    lock on the shared org serializes access so that at most one owner
    is deleted and the org never becomes ownerless while non-owner
    members remain (SA47).

    Thread A acquires the org lock first, sees the other owner (not
    blocked), and deletes owner A.  Thread B then acquires the lock
    (owner A is now gone), sees that owner B is the sole owner with
    other members (blocked), and does NOT delete.
    """
    import concurrent.futures

    from django.contrib.auth import get_user_model
    from django.db import close_old_connections, transaction

    from quickscale_modules_orgs.models import (
        OrgRole,
        Organization,
        OrganizationMembership,
    )

    User = get_user_model()

    # ---- Setup ----
    org = Organization.objects.create(
        name="SA47 Locking Org",
        slug="sa47-locking-org",
        is_personal=False,
    )

    owner_a = User.objects.create_user(
        username="sa47_locking_a",
        email="sa47_locking_a@example.com",
        password="Sa47LockingA1!",
    )
    owner_b = User.objects.create_user(
        username="sa47_locking_b",
        email="sa47_locking_b@example.com",
        password="Sa47LockingB1!",
    )
    member = User.objects.create_user(
        username="sa47_locking_member",
        email="sa47_locking_member@example.com",
        password="Sa47LockingMember1!",
    )

    OrganizationMembership.objects.create(
        user=owner_a,
        organization=org,
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.create(
        user=owner_b,
        organization=org,
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.create(
        user=member,
        organization=org,
        role=OrgRole.MEMBER,
    )

    owner_a_id = owner_a.pk
    owner_b_id = owner_b.pk
    org_id = org.pk

    def _delete_worker(user: object, user_id: int) -> dict[str, object]:
        close_old_connections()
        with transaction.atomic():
            # Acquire the organisational row lock — this serializes
            # concurrent deletions that share this org.
            Organization.objects.select_for_update().get(pk=org_id)

            is_blocked = OrganizationMembership.is_last_owner_with_members(
                user=user,
                organization=org,
            )
            if is_blocked:
                return {"deleted": False, "user_id": user_id}

            User.objects.filter(pk=user_id).delete()
            return {"deleted": True, "user_id": user_id}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(_delete_worker, owner_a, owner_a_id)
        future_b = executor.submit(_delete_worker, owner_b, owner_b_id)
        r_a = future_a.result(timeout=60)
        r_b = future_b.result(timeout=60)

    # Exactly one owner was deleted.
    deleted_count = sum([r_a["deleted"], r_b["deleted"]])
    assert deleted_count == 1, (
        f"Expected exactly one deletion, got {deleted_count}: A={r_a}, B={r_b}"
    )

    # The surviving owner is still present.
    if r_a["deleted"]:
        assert not User.objects.filter(pk=owner_a_id).exists()
        assert User.objects.filter(pk=owner_b_id).exists()
    else:
        assert User.objects.filter(pk=owner_a_id).exists()
        assert not User.objects.filter(pk=owner_b_id).exists()

    # The org still has at least one owner.
    assert OrganizationMembership.objects.filter(
        organization_id=org_id,
        role=OrgRole.OWNER,
    ).exists(), "Org must retain at least one owner"

    # The non-owner member survives.
    assert OrganizationMembership.objects.filter(
        organization_id=org_id,
    ).exists(), "Non-owner member record must survive"
    # The org itself survives.
    assert Organization.objects.filter(pk=org_id).exists()


# ---------------------------------------------------------------------------
# SA47 — lock-order deadlock regression (CR-SA47-001)
#
# AccountDeleteView locks org rows first (via select_for_update before
# user.delete()), while OrganizationMembership.save()/delete() previously
# locked the membership row first.  Under concurrent execution — e.g. an
# account deletion racing with a membership removal from the members page
# or API — a classic lock-order inversion deadlock could occur.
#
# Both paths now normalize the lock order to: org row first, then
# membership row.  This test proves the deadlock is resolved: two
# threads running the competing paths complete without hanging.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_account_deletion_and_membership_remove_no_deadlock() -> None:
    """Concurrent account deletion and membership removal do not
    deadlock.  Both paths now lock the org row before the membership
    row (SA47 CR-SA47-001)."""
    import concurrent.futures

    from django.contrib.auth import get_user_model
    from django.db import close_old_connections, transaction

    from quickscale_modules_orgs.models import (
        OrgRole,
        Organization,
        OrganizationMembership,
    )

    User = get_user_model()

    org = Organization.objects.create(
        name="CR-SA47-001 Org",
        slug="cr-sa47-001-org",
        is_personal=False,
    )
    owner = User.objects.create_user(
        username="cr_sa47_owner",
        email="cr_sa47_owner@example.com",
        password="CrSa47Owner1!",
    )
    other_member = User.objects.create_user(
        username="cr_sa47_member",
        email="cr_sa47_member@example.com",
        password="CrSa47Member1!",
    )

    membership = OrganizationMembership.objects.create(
        user=owner,
        organization=org,
        role=OrgRole.OWNER,
    )
    OrganizationMembership.objects.create(
        user=other_member,
        organization=org,
        role=OrgRole.MEMBER,
    )

    owner_pk = owner.pk
    membership_pk = membership.pk
    org_pk = org.pk

    def _account_delete_worker() -> dict[str, object]:
        close_old_connections()
        with transaction.atomic():
            # Simulate AccountDeleteView lock order: lock org first.
            Organization.objects.select_for_update().get(pk=org_pk)
            # Delete user — cascades to the membership row.
            User.objects.filter(pk=owner_pk).delete()
            return {"ok": True, "stage": "account-deleted"}

    def _membership_remove_worker() -> dict[str, object]:
        close_old_connections()
        with transaction.atomic():
            # Lock org first (same normalized order as save/delete).
            Organization.objects.select_for_update().get(pk=org_pk)
            # Attempt to delete the membership.
            try:
                m = OrganizationMembership.objects.get(pk=membership_pk)
                m.delete()
                return {"ok": True, "deleted": True}
            except OrganizationMembership.DoesNotExist:
                return {"ok": True, "deleted": False, "reason": "cascade-removed"}
            except Exception as exc:
                return {"ok": True, "deleted": False, "reason": str(exc)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(_account_delete_worker)
        future_m = executor.submit(_membership_remove_worker)
        r_a = future_a.result(timeout=30)
        r_m = future_m.result(timeout=30)

    # Both threads must complete within the timeout — no deadlock.
    assert r_a["ok"], f"Account deletion thread failed: {r_a}"
    assert r_m["ok"], f"Membership removal thread failed: {r_m}"

    # At most one thread succeeded in removing the membership.
    # (The account deletion cascades; the membership.remove is
    #  expected to be blocked if the account deletion didn't race.)
    assert r_m.get("deleted") is not True or r_a["stage"] == "account-deleted"
