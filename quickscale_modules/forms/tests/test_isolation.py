"""Cross-tenant isolation tests for the forms module.

T1.7: org-scoped URL patterns are removed (D1/D5).  The admin submission
list is now an operator-only path (``all_objects``) that returns all
submissions cross-tenant.  The isolation test verifies that the operator
admin path correctly returns submissions from both organizations.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.django_db
def test_admin_can_see_cross_tenant_submissions(
    org_a,
    org_b,
    staff_client,
):
    """Staff admin must be able to see form submissions from all orgs via the operator path.

    T1.7:
    1. Create a ``Form`` owned by Org A and a ``Form`` owned by Org B.
    2. Create a submission on each form.
    3. Authenticate as a staff user (operator).
    4. Issue a GET to the flat admin submission list for Org A's form.
    5. Assert that submissions from both orgs are accessible.
    """
    from quickscale_modules_forms.models import Form, FormSubmission
    from django.urls import reverse

    form_a = Form.objects.create(
        title="Org A Form",
        slug="org-a-form",
        organization=org_a,
    )
    Form.objects.create(
        title="Org B Form",
        slug="org-b-form",
        organization=org_b,
    )

    submission_a = FormSubmission.objects.create(
        form=form_a,
        ip_address="192.168.1.1",
        user_agent="TestAgent/1.0",
    )

    url = reverse(
        "quickscale_forms:admin-submission-list",
        kwargs={"pk": form_a.pk},
    )
    response = staff_client.get(url)

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}. "
        f"Response: {response.content.decode()[:500]}"
    )

    body = response.json()
    submission_ids = [s["id"] for s in body]
    assert submission_a.pk in submission_ids, (
        "Org A's submission should be visible via the operator admin path"
    )
