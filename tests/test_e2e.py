"""End-to-end tests for the Forms module.

These tests exercise the full user journey:
  seed presets → fetch schema → submit form → verify in DB

They run against the in-memory SQLite test database and do not require
Docker, Playwright, or any external services.  They are marked with
``@pytest.mark.e2e`` so the CI matrix can run them in a dedicated step.
"""

import pytest
from django.core.cache import cache
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from rest_framework.test import APIClient

from quickscale_modules_forms.models import Form, FormFieldValue, FormSubmission


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def clear_rate_limit_cache():
    """Reset the throttle cache before and after every test."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def seeded_contact_form(db):
    """Seed the contact preset and return the resulting Form instance."""
    call_command("forms_seed_presets", verbosity=0)
    return Form.objects.get(slug="contact")


@pytest.fixture
def api_client():
    """Unauthenticated DRF API client."""
    return APIClient()


@pytest.fixture
def staff_client(db):
    """DRF API client authenticated as a staff user."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    staff = User.objects.create_user(
        username="admin_e2e",
        email="admin_e2e@example.com",
        password="adminpass",
        is_staff=True,
    )
    client = APIClient()
    client.force_authenticate(user=staff)
    return client


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.e2e
@pytest.mark.django_db
class TestContactFormE2EWorkflow:
    """Full end-to-end workflow: seed → schema → submit → verify."""

    # ------------------------------------------------------------------
    # 1. Seeding
    # ------------------------------------------------------------------

    def test_seed_creates_contact_form_with_required_fields(self, seeded_contact_form):
        """forms_seed_presets creates the contact form with all five expected fields."""
        field_names = list(seeded_contact_form.fields.values_list("name", flat=True))
        assert seeded_contact_form.slug == "contact"
        assert seeded_contact_form.is_active is True
        for expected in ("full_name", "email", "company", "subject", "project_context"):
            assert expected in field_names, f"Expected field '{expected}' not found"

    def test_seed_is_idempotent(self, db):
        """Running forms_seed_presets twice does not create duplicate forms."""
        call_command("forms_seed_presets", verbosity=0)
        call_command("forms_seed_presets", verbosity=0)
        assert Form.objects.filter(slug="contact").count() == 1

    # ------------------------------------------------------------------
    # 2. Schema endpoint
    # ------------------------------------------------------------------

    def test_schema_endpoint_returns_200_with_fields(
        self, api_client, seeded_contact_form
    ):
        """Public schema endpoint returns the form structure."""
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "contact"})
        response = api_client.get(url)

        assert response.status_code == 200
        assert response.data["slug"] == "contact"
        assert "fields" in response.data
        field_names = [
            f["name"] for f in response.data["fields"] if f["name"] != "_hp_name"
        ]
        assert "full_name" in field_names
        assert "email" in field_names

    def test_schema_includes_honeypot_field(self, api_client, seeded_contact_form):
        """Schema injects the hidden honeypot marker field."""
        url = reverse("quickscale_forms:form-schema", kwargs={"slug": "contact"})
        response = api_client.get(url)

        assert response.status_code == 200
        all_names = [f["name"] for f in response.data["fields"]]
        assert "_hp_name" in all_names
        honeypot = next(f for f in response.data["fields"] if f["name"] == "_hp_name")
        assert honeypot["field_type"] == "hidden"

    # ------------------------------------------------------------------
    # 3. Submission — happy path
    # ------------------------------------------------------------------

    def test_valid_submission_returns_201_and_persists_to_db(
        self, api_client, seeded_contact_form
    ):
        """Submitting a valid contact form returns 201 and creates a submission record."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "contact"})
        payload = {
            "full_name": "Alice Example",
            "email": "alice@example.com",
            "company": "Example Corp",
            "subject": "Project inquiry",
            "project_context": "We need a custom SaaS dashboard.",
        }
        response = api_client.post(url, data=payload, format="json")

        assert response.status_code == 201
        assert "message" in response.data

        submission = FormSubmission.objects.filter(form=seeded_contact_form).first()
        assert submission is not None
        assert submission.is_spam is False

    def test_submission_stores_all_field_values(self, api_client, seeded_contact_form):
        """All submitted field values are persisted as FormFieldValue records."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "contact"})
        payload = {
            "full_name": "Bob Builder",
            "email": "bob@builder.com",
            "company": "Builder Inc",
            "subject": "Building things",
            "project_context": "I build things professionally.",
        }
        api_client.post(url, data=payload, format="json")

        submission = FormSubmission.objects.filter(form=seeded_contact_form).latest(
            "submitted_at"
        )
        stored_names = list(
            FormFieldValue.objects.filter(submission=submission).values_list(
                "field_name", flat=True
            )
        )
        for field in ("full_name", "email", "company", "subject", "project_context"):
            assert field in stored_names, f"Field value '{field}' not stored"

    def test_missing_required_field_returns_400(self, api_client, seeded_contact_form):
        """Submitting without a required field returns 400 with field errors."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "contact"})
        payload = {
            "full_name": "Alice",
            # email is required but missing
            "subject": "Test",
            "project_context": "Test context.",
        }
        response = api_client.post(url, data=payload, format="json")

        assert response.status_code == 400
        assert "errors" in response.data

    # ------------------------------------------------------------------
    # 4. Spam protection
    # ------------------------------------------------------------------

    def test_honeypot_submission_silently_marks_spam(
        self, api_client, seeded_contact_form
    ):
        """Submissions with a filled honeypot field are flagged as spam in the DB."""
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "contact"})
        payload = {
            "full_name": "Spambot",
            "email": "spam@bot.com",
            "subject": "Buy cheap!",
            "project_context": "Spam spam spam.",
            "_hp_name": "I am definitely a bot",  # filled honeypot
        }
        response = api_client.post(url, data=payload, format="json")

        # Returns 201 to fool bots — but marks submission as spam
        assert response.status_code == 201
        latest = FormSubmission.objects.filter(form=seeded_contact_form).latest(
            "submitted_at"
        )
        assert latest.is_spam is True

    # ------------------------------------------------------------------
    # 5. Rate limiting
    # ------------------------------------------------------------------

    @override_settings(FORMS_RATE_LIMIT="2/minute")
    def test_rate_limit_returns_429_after_threshold(
        self, api_client, seeded_contact_form
    ):
        """Submitting more times than the rate limit returns 429."""
        cache.clear()
        url = reverse("quickscale_forms:form-submit", kwargs={"slug": "contact"})
        payload = {
            "full_name": "Rate Tester",
            "email": "ratelimit@test.com",
            "subject": "Rate test",
            "project_context": "Testing rate limiting.",
        }

        first = api_client.post(url, data=payload, format="json")
        second = api_client.post(url, data=payload, format="json")
        third = api_client.post(url, data=payload, format="json")

        assert first.status_code == 201
        assert second.status_code == 201
        assert third.status_code == 429

    # ------------------------------------------------------------------
    # 6. Admin retrieval
    # ------------------------------------------------------------------

    def test_admin_can_list_submissions(
        self, staff_client, api_client, seeded_contact_form
    ):
        """Staff user can retrieve the list of form submissions via the admin API."""
        # Create a submission first
        submit_url = reverse("quickscale_forms:form-submit", kwargs={"slug": "contact"})
        api_client.post(
            submit_url,
            data={
                "full_name": "Charlie",
                "email": "charlie@example.com",
                "subject": "Admin retrieval test",
                "project_context": "Checking admin API visibility.",
            },
            format="json",
        )

        list_url = reverse(
            "quickscale_forms:admin-submission-list",
            kwargs={"pk": seeded_contact_form.pk},
        )
        response = staff_client.get(list_url)

        assert response.status_code == 200
        assert len(response.data) >= 1
        submission_data = response.data[0]
        assert "submitted_at" in submission_data
        assert "is_spam" in submission_data

    def test_anonymous_user_cannot_list_submissions(
        self, api_client, seeded_contact_form
    ):
        """Unauthenticated requests to admin submission list return 403."""
        url = reverse(
            "quickscale_forms:admin-submission-list",
            kwargs={"pk": seeded_contact_form.pk},
        )
        response = api_client.get(url)
        assert response.status_code == 403
