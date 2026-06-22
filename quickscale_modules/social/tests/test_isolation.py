"""Cross-tenant isolation tests for the social module.

Phase F11.13a delivers tenant isolation for the social module with an
``organization`` FK on ``BaseSocialItem``, a dual-manager contract
(``TenantScopedManager`` + ``OperatorManager``), and org-scoped query
support in ``services.py``.

The ``test_org_a_cannot_see_org_b_social_links`` test is now active
(skip marker removed).  It validates that org-scoped service queries
return only the requesting org's social items.

Since the social module is model-only (no URLs/views), isolation is
verified at the service layer via ``list_published_social_links()`` and
``list_published_social_embeds()`` with the ``organization_id`` parameter.
"""

import pytest

from quickscale_modules_social.models import SocialEmbed, SocialLink
from quickscale_modules_social.services import (
    list_published_social_embeds,
    list_published_social_links,
)


@pytest.mark.isolation
@pytest.mark.django_db
class TestSocialIsolation:
    """Cross-tenant isolation tests for social module service queries."""

    def test_org_a_cannot_see_org_b_social_links(
        self,
        org_a,
        org_b,
    ) -> None:
        """Org A must not be able to read Org B's social links via org-scoped query.

        Phase F11.13a:
        1. Create a social link owned by Org A and one owned by Org B.
        2. Query via ``list_published_social_links(organization_id=org_a.id)``.
        3. Assert that only Org A's link is returned.
        """
        SocialLink.objects.create(
            title="Org A Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-a/",
            description="Org A link",
            display_order=10,
            is_published=True,
            organization=org_a,
        )
        SocialLink.objects.create(
            title="Org B Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-b/",
            description="Org B link",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        org_a_links = list_published_social_links(organization_id=org_a.id)
        org_a_titles = {r.title for r in org_a_links}

        assert "Org A Link" in org_a_titles, (
            "Org A's own link should be visible to Org A"
        )
        assert "Org B Link" not in org_a_titles, (
            "Org B's link must not be visible to Org A. "
            "This confirms the cross-tenant isolation gap (Finding 11)."
        )

    def test_org_a_cannot_see_org_b_social_embeds(
        self,
        org_a,
        org_b,
    ) -> None:
        """Org A must not be able to read Org B's social embeds via org-scoped query.

        Phase F11.13a:
        1. Create a social embed owned by Org A and one owned by Org B.
        2. Query via ``list_published_social_embeds(organization_id=org_a.id)``.
        3. Assert that only Org A's embed is returned.
        """
        SocialEmbed.objects.create(
            title="Org A Embed",
            provider_name="",
            url="https://www.youtube.com/shorts/aaa111",
            description="Org A embed",
            display_order=10,
            is_published=True,
            organization=org_a,
        )
        SocialEmbed.objects.create(
            title="Org B Embed",
            provider_name="",
            url="https://www.youtube.com/shorts/bbb222",
            description="Org B embed",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        org_a_embeds = list_published_social_embeds(organization_id=org_a.id)
        org_a_titles = {r.title for r in org_a_embeds}

        assert "Org A Embed" in org_a_titles, (
            "Org A's own embed should be visible to Org A"
        )
        assert "Org B Embed" not in org_a_titles, (
            "Org B's embed must not be visible to Org A. "
            "This confirms the cross-tenant isolation gap (Finding 11)."
        )

    def test_unscoped_query_returns_all_links(self, org_a, org_b) -> None:
        """Calling ``list_published_social_links()`` without org_id returns all.

        This verifies backward compatibility: the default (no org_id) still
        returns all published items across all tenants.
        """
        SocialLink.objects.create(
            title="Org A Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-a/",
            description="Org A link",
            display_order=10,
            is_published=True,
            organization=org_a,
        )
        SocialLink.objects.create(
            title="Org B Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-b/",
            description="Org B link",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        all_links = list_published_social_links()
        all_titles = {r.title for r in all_links}

        assert "Org A Link" in all_titles
        assert "Org B Link" in all_titles

    def test_operator_manager_escape_hatch(self, org_a, org_b) -> None:
        """``all_objects`` should return all rows regardless of org.

        The operator escape hatch provides unfiltered cross-tenant access
        for admin/operator paths.
        """
        SocialLink.objects.create(
            title="Org A Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-a/",
            display_order=10,
            is_published=True,
            organization=org_a,
        )
        SocialLink.objects.create(
            title="Org B Link",
            provider_name="",
            url="https://www.linkedin.com/company/org-b/",
            display_order=20,
            is_published=True,
            organization=org_b,
        )

        all_rows = SocialLink.all_objects.all()
        assert all_rows.count() == 2
