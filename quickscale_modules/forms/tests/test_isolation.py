"""Cross-tenant isolation tests for the forms module.

Phase F11.12a adds an ``organization`` FK to the ``Form`` model and
org-scoped URL patterns.  The ``test_org_a_cannot_see_org_b_form_submissions``
test is now active (skip marker removed).  It validates that the org-scoped
admin submission list returns only the requesting org's submissions.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.django_db
def test_org_a_cannot_see_org_b_form_submissions(
    org_a,
    org_b,
    org_a_admin,
    client,
):
    """Org A must not be able to read Org B's form submissions via an org-scoped path.

    Phase F11.12a:
    1. Create a ``Form`` owned by Org A and a ``Form`` owned by Org B.
    2. Create a submission on each form.
    3. Authenticate as an Org A admin (member of Org A).
    4. Issue a GET to the org-scoped admin submission list for Org A's form.
    5. Assert that only Org A's submission is visible.
    """
    from quickscale_modules_forms.models import Form, FormSubmission

    form_a = Form.objects.create(
        title="Org A Form",
        slug="org-a-form",
        organization=org_a,
    )
    form_b = Form.objects.create(
        title="Org B Form",
        slug="org-b-form",
        organization=org_b,
    )

    submission_a = FormSubmission.objects.create(
        form=form_a,
        ip_address="192.168.1.1",
        user_agent="TestAgent/1.0",
    )
    FormSubmission.objects.create(
        form=form_b,
        ip_address="10.0.0.1",
        user_agent="TestAgent/2.0",
    )

    client.force_login(org_a_admin)
    response = client.get(
        f"/orgs/{org_a.slug}/forms/api/admin/forms/{form_a.pk}/submissions/"
    )

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}. "
        f"Response: {response.content.decode()[:500]}"
    )

    body = response.json()
    submission_ids = [s["id"] for s in body]
    assert submission_a.pk in submission_ids, "Org A's own submission should be visible"
    # Org B's submissions should not be in Org A's org-scoped list
    assert all(
        FormSubmission.objects.get(pk=sid).form.organization_id == org_a.pk
        for sid in submission_ids
    ), "All returned submissions must belong to Org A"
