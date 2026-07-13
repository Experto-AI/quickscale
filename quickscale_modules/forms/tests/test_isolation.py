"""Cross-tenant isolation tests for the forms module.

T1.7: org-scoped URL patterns are removed (D1/D5).  The admin submission
list is now an operator-only path (``all_objects``) that returns all
submissions cross-tenant.  The isolation test verifies that the operator
admin path correctly returns submissions from both organizations.
"""

import pytest


@pytest.mark.isolation
@pytest.mark.django_db
def test_superuser_can_see_cross_tenant_submissions(
    org_a,
    org_b,
    superuser_client,
):
    """Superuser must be able to see form submissions from all orgs via the operator path.

    SA85 Phase 4 retained-role: Only superusers may perform cross-tenant
    SELECT (audited via ``operator_access``).  Regular staff without an org
    context now fail-closed (empty).

    1. Create a ``Form`` owned by Org A and a ``Form`` owned by Org B.
    2. Create a submission on each form.
    3. Authenticate as superuser.
    4. Issue a GET to the flat admin submission list for Org A's form.
    5. Assert that submissions from both orgs are accessible.
    """
    from quickscale_modules_forms.models import Form, FormSubmission
    from quickscale_modules_orgs.current_org import org_scope
    from django.urls import reverse

    with org_scope(org_a):
        form_a = Form.objects.create(
            title="Org A Form",
            slug="org-a-form",
            organization=org_a,
        )
    with org_scope(org_b):
        Form.objects.create(
            title="Org B Form",
            slug="org-b-form",
            organization=org_b,
        )

    with org_scope(org_a):
        submission_a = FormSubmission.all_objects.create(
            form=form_a,
            organization=form_a.organization,
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
        )

    url = reverse(
        "quickscale_forms:admin-submission-list",
        kwargs={"pk": form_a.pk},
    )
    response = superuser_client.get(url)

    assert response.status_code == 200, (
        f"Expected 200 OK, got {response.status_code}. "
        f"Response: {response.content.decode()[:500]}"
    )

    body = response.json()
    submission_ids = [s["id"] for s in body]
    assert submission_a.pk in submission_ids, (
        "Org A's submission should be visible via the operator admin path"
    )


@pytest.mark.isolation
@pytest.mark.django_db
def test_staff_without_org_fails_closed_on_admin_list(
    org_a,
    staff_client,
    form,
):
    """Regular staff without org context must fail-closed on admin endpoints.

    SA85 Phase 4: staff with no active org context see no data.  This is the
    retained-role fail-closed behavior — the previous behavior returned all
    data via the operator path.
    """
    from django.urls import reverse

    url = reverse(
        "quickscale_forms:admin-form-list",
    )
    response = staff_client.get(url)
    assert response.status_code == 200, (
        f"Expected 200 OK (empty list), got {response.status_code}"
    )
    assert len(response.data) == 0, (
        "Staff without org must receive an empty list (fail-closed)"
    )
