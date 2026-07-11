"""Cross-tenant isolation tests for the social module.

T1.9 — social adopt contract.  Tenant scoping is now ambient via the
TenantManager (ContextVar).  ``list_published_social_links()`` and
``list_published_social_embeds()`` no longer accept an ``organization_id``
parameter — the caller sets the org context before calling.
"""

from __future__ import annotations

import pytest

from quickscale_modules_social.models import SocialEmbed, SocialLink
from quickscale_modules_social.services import (
    list_published_social_embeds,
    list_published_social_links,
)


def _set_org_context(org_id: object) -> None:
    """Activate a tenant context for TenantManager auto-scoping."""
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(org_id)


def _reset_org_context() -> None:
    """Reset tenant context to None (fail-closed)."""
    from quickscale_modules_orgs.current_org import set_current_org_id

    set_current_org_id(None)


@pytest.mark.isolation
@pytest.mark.django_db
class TestSocialIsolation:
    """Cross-tenant isolation tests for social module service queries."""

    def test_org_a_cannot_see_org_b_social_links(
        self,
        org_a,
        org_b,
    ) -> None:
        """Org A must not be able to read Org B's social links via auto-scoped query.

        T1.9 — TenantManager auto-scopes by contextvar:
        1. Create a social link owned by Org A and one owned by Org B.
        2. Set context to Org A, then call ``list_published_social_links()``.
        3. Assert that only Org A's link is returned.
        """
        try:
            _set_org_context(org_a.id)
            SocialLink.objects.create(
                title="Org A Link",
                provider_name="",
                url="https://www.linkedin.com/company/org-a/",
                description="Org A link",
                display_order=10,
                is_published=True,
                organization=org_a,
            )

            _set_org_context(org_b.id)
            SocialLink.objects.create(
                title="Org B Link",
                provider_name="",
                url="https://www.linkedin.com/company/org-b/",
                description="Org B link",
                display_order=20,
                is_published=True,
                organization=org_b,
            )

            _set_org_context(org_a.id)
            org_a_links = list_published_social_links()
            org_a_titles = {r.title for r in org_a_links}

            assert "Org A Link" in org_a_titles, (
                "Org A's own link should be visible to Org A"
            )
            assert "Org B Link" not in org_a_titles, (
                "Org B's link must not be visible to Org A. "
                "This confirms the cross-tenant isolation gap (Finding 11)."
            )
        finally:
            _reset_org_context()

    def test_org_a_cannot_see_org_b_social_embeds(
        self,
        org_a,
        org_b,
    ) -> None:
        """Org A must not be able to read Org B's social embeds via auto-scoped query.

        T1.9 — TenantManager auto-scopes by contextvar:
        1. Create a social embed owned by Org A and one owned by Org B.
        2. Set context to Org A, then call ``list_published_social_embeds()``.
        3. Assert that only Org A's embed is returned.
        """
        try:
            _set_org_context(org_a.id)
            SocialEmbed.objects.create(
                title="Org A Embed",
                provider_name="",
                url="https://www.youtube.com/shorts/aaa111",
                description="Org A embed",
                display_order=10,
                is_published=True,
                organization=org_a,
            )

            _set_org_context(org_b.id)
            SocialEmbed.objects.create(
                title="Org B Embed",
                provider_name="",
                url="https://www.youtube.com/shorts/bbb222",
                description="Org B embed",
                display_order=20,
                is_published=True,
                organization=org_b,
            )

            _set_org_context(org_a.id)
            org_a_embeds = list_published_social_embeds()
            org_a_titles = {r.title for r in org_a_embeds}

            assert "Org A Embed" in org_a_titles, (
                "Org A's own embed should be visible to Org A"
            )
            assert "Org B Embed" not in org_a_titles, (
                "Org B's embed must not be visible to Org A. "
                "This confirms the cross-tenant isolation gap (Finding 11)."
            )
        finally:
            _reset_org_context()

    def test_operator_manager_escape_hatch(self, org_a, org_b) -> None:
        """``all_objects`` with ``operator_access`` should return all rows
        regardless of org.

        The operator escape hatch provides unfiltered cross-tenant access
        for admin/operator paths.  Under ``NOBYPASSRLS`` the FOR ALL RLS
        policy restricts cross-org reads; ``operator_access`` extends the
        FOR SELECT sub-policy (SA14.5) so that ``all_objects`` queries
        can see rows from any organization.
        """
        from quickscale_modules_orgs.current_org import operator_access

        try:
            _set_org_context(org_a.id)
            SocialLink.objects.create(
                title="Org A Link",
                provider_name="",
                url="https://www.linkedin.com/company/org-a/",
                display_order=10,
                is_published=True,
                organization=org_a,
            )

            _set_org_context(org_b.id)
            SocialLink.objects.create(
                title="Org B Link",
                provider_name="",
                url="https://www.linkedin.com/company/org-b/",
                display_order=20,
                is_published=True,
                organization=org_b,
            )

            with operator_access(reason="all_objects cross-org read"):
                all_rows = SocialLink.all_objects.all()
                assert all_rows.count() == 2
        finally:
            _reset_org_context()
