"""Tests for Forms module data-migration correctness.

These tests verify that the historical-model seed logic in
``0002_seed_forms.py`` produces the expected preset data without
depending on the live model class.
"""

import importlib
import inspect

import pytest
from django.apps import apps as django_apps

from quickscale_modules_forms.models import Form, FormField


def _get_0002_module():
    """Dynamically import migration 0002 (name starts with a digit)."""
    return importlib.import_module(
        "quickscale_modules_forms.migrations.0002_seed_forms"
    )


@pytest.mark.django_db
class TestMigration0002Seed:
    """Tests for 0002_seed_forms seed_forms function."""

    @pytest.fixture(autouse=True)
    def _clean_presets(self):
        """Remove any preset-created rows before each test."""
        Form.objects.filter(
            slug__in=["contact", "newsletter", "feedback", "support"]
        ).delete()
        yield

    def test_seed_forms_creates_all_presets(self):
        """seed_forms creates the four built-in preset forms."""
        mod = _get_0002_module()
        mod.seed_forms(django_apps, None)

        slugs = list(Form.objects.values_list("slug", flat=True))
        assert "contact" in slugs
        assert "newsletter" in slugs
        assert "feedback" in slugs
        assert "support" in slugs

    def test_contact_preset_has_five_fields(self):
        """Contact preset is seeded with five standard fields."""
        mod = _get_0002_module()
        mod.seed_forms(django_apps, None)

        form = Form.objects.get(slug="contact")
        field_names = list(form.fields.values_list("name", flat=True))
        assert len(field_names) == 5
        assert "full_name" in field_names
        assert "email" in field_names
        assert "company" in field_names
        assert "subject" in field_names
        assert "project_context" in field_names

    def test_newsletter_preset_has_two_fields(self):
        """Newsletter preset is seeded with two fields."""
        mod = _get_0002_module()
        mod.seed_forms(django_apps, None)

        form = Form.objects.get(slug="newsletter")
        assert form.fields.count() == 2

    def test_seed_is_idempotent(self):
        """Running seed_forms twice does not duplicate presets."""
        mod = _get_0002_module()
        mod.seed_forms(django_apps, None)
        mod.seed_forms(django_apps, None)

        assert Form.objects.filter(slug="contact").count() == 1

    def test_feedback_preset_has_select_field(self):
        """Feedback preset includes a select (rating) field with five options."""
        mod = _get_0002_module()
        mod.seed_forms(django_apps, None)

        form = Form.objects.get(slug="feedback")
        rating_field = form.fields.get(name="rating")
        assert rating_field.field_type == FormField.FIELD_TYPE_SELECT
        assert len(rating_field.options) == 5

    def test_support_preset_has_priority_select(self):
        """Support preset has a priority select with three options."""
        mod = _get_0002_module()
        mod.seed_forms(django_apps, None)

        priority_field = FormField.objects.get(form__slug="support", name="priority")
        assert priority_field.field_type == FormField.FIELD_TYPE_SELECT
        assert len(priority_field.options) == 3

    def test_seed_uses_apps_get_model_not_live_import(self):
        """The seed function uses ``apps.get_model()`` so it works with
        historical model states that lack the ``organization`` FK column."""
        mod = _get_0002_module()
        source = inspect.getsource(mod.seed_forms)
        # Must NOT import the live model or call_command
        assert "call_command" not in source
        assert "from quickscale_modules_forms.models" not in source
        # Must use apps.get_model()
        assert "apps.get_model" in source
        assert "Form = apps.get_model" in source
        assert "FormField = apps.get_model" in source

    def test_migration_module_has_no_command_import(self):
        """The migration module must not import the live management command."""
        mod = _get_0002_module()
        source = inspect.getsource(mod)
        assert "call_command" not in source
        assert "from django.core.management" not in source


@pytest.mark.django_db(transaction=True)
class TestMigrationExecutorHarness:
    """Verify migration 0002 seed data via MigrationExecutor through a
    pre-0004 historical state.

    Unlike test classes above that source-inspect the migration module,
    this harness actually migrates the database through ``0001 → 0002``
    and reads seeded data via ``state.apps.get_model()`` (historical model
    proxy).  This proves the migration works end-to-end against the real
    migration state — including the scenario where the ``organization`` FK
    column (added in 0004) does not yet exist.
    """

    def test_migrate_0001_to_0002_produces_presets(self):
        """Migrate forms app to 0002 from 0001 baseline and verify presets
        via historical models (pre-organization FK column)."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        app_label = "quickscale_modules_forms"

        # Full migration names as they appear on disk
        MIG_0001 = "0001_initial"
        MIG_0002 = "0002_seed_forms"

        executor = MigrationExecutor(connection)

        # Roll back to migration 0001 to establish a baseline before the
        # seed and before the organization FK column existed.
        executor.migrate([(app_label, MIG_0001)])
        executor.loader.build_graph()

        # Migrate forward to 0002 (seed forms) on top of the 0001 state
        executor.migrate([(app_label, MIG_0002)])

        # Retrieve historical model via state.apps — this is the model as
        # it existed at migration 0002, i.e. without the organization FK
        # column that 0004 introduces.
        state = executor.loader.project_state([(app_label, MIG_0002)])
        HistoricalForm = state.apps.get_model(app_label, "Form")
        HistoricalFormField = state.apps.get_model(app_label, "FormField")

        # Verify all four presets were seeded
        slugs = list(HistoricalForm.objects.values_list("slug", flat=True))
        assert "contact" in slugs
        assert "newsletter" in slugs
        assert "feedback" in slugs
        assert "support" in slugs

        # Verify contact preset has its five fields
        contact = HistoricalForm.objects.get(slug="contact")
        field_names = list(
            HistoricalFormField.objects.filter(form=contact).values_list(
                "name", flat=True
            )
        )
        assert "full_name" in field_names
        assert "email" in field_names
        assert "company" in field_names
        assert "subject" in field_names
        assert "project_context" in field_names

        # Verify idempotent re-apply
        executor = MigrationExecutor(connection)
        executor.loader.build_graph()
        executor.migrate([(app_label, MIG_0002)])
        assert HistoricalForm.objects.filter(slug="contact").count() == 1

    def test_migrate_through_0004_after_seed(self):
        """Migrate from 0002 → 0003 → 0004 (add organization FK) succeeds
        and the seeded presets remain accessible via historical models."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        app_label = "quickscale_modules_forms"

        MIG_0001 = "0001_initial"
        MIG_0002 = "0002_seed_forms"
        MIG_0004 = "0004_form_organization_alter_form_slug_and_more"

        executor = MigrationExecutor(connection)

        # Roll to 0002 baseline (same precondition as above)
        executor.migrate([(app_label, MIG_0001)])
        executor.loader.build_graph()
        executor.migrate([(app_label, MIG_0002)])

        # Migrate through 0003 (data_retention_days default change) and
        # 0004 (organization FK addition).
        executor.migrate([(app_label, MIG_0004)])

        # Read via state at 0004 — the organization field should be present
        # on the historical model now.
        state = executor.loader.project_state([(app_label, MIG_0004)])
        Form_0004 = state.apps.get_model(app_label, "Form")
        assert Form_0004.objects.filter(slug="contact").exists()

        # Verify the historical model at 0004 has the organization FK field
        org_field = Form_0004._meta.get_field("organization")
        assert org_field.null is True
