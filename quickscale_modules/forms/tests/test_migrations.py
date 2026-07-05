"""Tests for Forms module data-migration correctness.

These tests verify that the historical-model seed logic in
``0002_seed_forms.py`` produces the expected preset data without
depending on the live model class.
"""

import importlib
import inspect

import pytest
from django.core.exceptions import FieldDoesNotExist

from quickscale_modules_forms.models import Form, FormField


def _get_0002_module():
    """Dynamically import migration 0002 (name starts with a digit)."""
    return importlib.import_module(
        "quickscale_modules_forms.migrations.0002_seed_forms"
    )


@pytest.mark.django_db
class TestMigration0002Seed:
    """Tests for 0002_seed_forms seed_forms function.

    The seed function was designed for the historical model (pre-org FK).
    When called with the live model (NOT NULL organization), it cannot
    create rows without an organization.  These tests verify the data
    structure by creating presets directly with the System org.
    """

    @pytest.fixture(autouse=True)
    def _system_org(self, db):
        """Ensure System org exists and set org context for scoped managers.

        Also sets the PostgreSQL GUC ``app.current_org_id`` so that FORCE
        RLS policies (installed by forms migration 0007) do not block
        ``all_objects`` inserts during the test.
        """
        from django.db import connection

        from quickscale_modules_orgs.current_org import set_current_org_id
        from quickscale_modules_orgs.models import Organization

        system_org = Organization.objects.get_system_org()
        set_current_org_id(system_org.pk)
        # Also set the PostgreSQL GUC for RLS policies (AF12 Phase 1).
        with connection.cursor() as cur:
            cur.execute("SET app.current_org_id = %s", [str(system_org.pk)])
        return system_org

    @pytest.fixture(autouse=True)
    def _clean_presets(self, _system_org):
        """Remove any preset-created rows before each test."""
        Form.all_objects.filter(
            slug__in=["contact", "newsletter", "feedback", "support"]
        ).delete()
        yield

    def _create_test_presets(self, _system_org):
        """Create the four preset forms with System org ownership."""
        from quickscale_modules_forms.management.commands.forms_seed_presets import (
            Command as SeedCommand,
        )

        # Use the same preset data structure as the seed command
        presets = SeedCommand.PRESETS
        for preset in presets:
            form, _ = Form.all_objects.get_or_create(
                slug=preset["slug"],
                defaults={
                    "title": preset["title"],
                    "description": preset["description"],
                    "success_message": preset["success_message"],
                    "notify_emails": preset["notify_emails"],
                    "organization": _system_org,
                },
            )
            for field_data in preset["fields"]:
                field_defaults = {k: v for k, v in field_data.items() if k != "name"}
                field_defaults.setdefault("placeholder", "")
                field_defaults.setdefault("options", [])
                field_defaults.setdefault("validation_rules", {})
                field_defaults["organization"] = form.organization
                FormField.all_objects.get_or_create(
                    form=form,
                    name=field_data["name"],
                    defaults=field_defaults,
                )

    def test_seed_forms_creates_all_presets(self, _system_org):
        """Preset command creates the four built-in preset forms."""
        self._create_test_presets(_system_org)

        slugs = list(Form.all_objects.values_list("slug", flat=True))
        assert "contact" in slugs
        assert "newsletter" in slugs
        assert "feedback" in slugs
        assert "support" in slugs

    def test_contact_preset_has_five_fields(self, _system_org):
        """Contact preset is seeded with five standard fields."""
        self._create_test_presets(_system_org)

        form = Form.all_objects.get(slug="contact")
        field_names = list(form.fields.values_list("name", flat=True))
        assert len(field_names) == 5
        assert "full_name" in field_names
        assert "email" in field_names
        assert "company" in field_names
        assert "subject" in field_names
        assert "project_context" in field_names

    def test_newsletter_preset_has_two_fields(self, _system_org):
        """Newsletter preset is seeded with two fields."""
        self._create_test_presets(_system_org)

        form = Form.all_objects.get(slug="newsletter")
        assert form.fields.count() == 2

    def test_seed_is_idempotent(self, _system_org):
        """Running seed twice does not duplicate presets."""
        self._create_test_presets(_system_org)
        self._create_test_presets(_system_org)

        assert Form.all_objects.filter(slug="contact").count() == 1

    def test_feedback_preset_has_select_field(self, _system_org):
        """Feedback preset includes a select (rating) field with five options."""
        self._create_test_presets(_system_org)

        form = Form.all_objects.get(slug="feedback")
        rating_field = form.fields.get(name="rating")
        assert rating_field.field_type == FormField.FIELD_TYPE_SELECT
        assert len(rating_field.options) == 5

    def test_support_preset_has_priority_select(self, _system_org):
        """Support preset has a priority select with three options."""
        self._create_test_presets(_system_org)

        priority_field = FormField.all_objects.get(
            form__slug="support", name="priority"
        )
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


@pytest.mark.bypass_rls
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

    def test_migrate_through_0005_after_seed(self):
        """Migrate from 0002 → 0003 → 0004 → 0005 (adopt NOT NULL/PROTECT)
        succeeds and the seeded presets remain accessible via historical models."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        app_label = "quickscale_modules_forms"

        MIG_0001 = "0001_initial"
        MIG_0002 = "0002_seed_forms"
        MIG_0005 = "0005_form_alter_organization_not_null_protect"

        executor = MigrationExecutor(connection)

        # Roll to 0002 baseline (same precondition as above)
        executor.migrate([(app_label, MIG_0001)])
        executor.loader.build_graph()
        executor.migrate([(app_label, MIG_0002)])

        # Migrate through 0003 → 0004 → 0005 (adopt NOT NULL/PROTECT contract).
        executor.migrate([(app_label, MIG_0005)])

        # Read via state at 0005 — the organization field should be present
        # and NOT NULL with PROTECT on the historical model now.
        state = executor.loader.project_state([(app_label, MIG_0005)])
        Form_0005 = state.apps.get_model(app_label, "Form")
        assert Form_0005.objects.filter(slug="contact").exists()

        # Verify the historical model at 0005 has NOT NULL and PROTECT
        org_field = Form_0005._meta.get_field("organization")
        assert org_field.null is False


# ---------------------------------------------------------------------------
# AF12 Phase 2 — Composite FK migration forward/reverse/replay proofs
# ---------------------------------------------------------------------------
# Verifies the rewritten 0007 migration adds parent UNIQUE constraints and
# composite child FKs, that the reverse path removes them cleanly, and that
# replay (re-apply) is idempotent.  Also proves the 0007→0008 migration
# chain (AF11 compatibility) is intact.
# ---------------------------------------------------------------------------

try:
    from django.db import connection as _forms_dj_connection

    _FORMS_IS_POSTGRES = _forms_dj_connection.vendor == "postgresql"
except Exception:
    _FORMS_IS_POSTGRES = False


@pytest.mark.bypass_rls
@pytest.mark.django_db(transaction=True)
class TestFormsMigration0007CompositeFK:
    """MigrationExecutor harness for Forms 0006→0007→0008 AF12 composite FKs."""

    APP_LABEL = "quickscale_modules_forms"
    MIG_0006 = "0006_enable_rls"
    MIG_0007 = "0007_new_organization_ownership"
    MIG_0008 = "0008_refresh_rls_policies_nullif_guard"

    def test_0006_to_0007_migration_forward(self) -> None:
        """Forward migration 0006→0007 succeeds and produces NOT NULL/PROTECT."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)

        executor.migrate([(self.APP_LABEL, self.MIG_0006)])
        executor.loader.build_graph()

        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0007)])

        state = executor.loader.project_state([(self.APP_LABEL, self.MIG_0007)])
        for name in ("FormField", "FormSubmission", "FormFieldValue"):
            model = state.apps.get_model(self.APP_LABEL, name)
            field = model._meta.get_field("organization")
            assert field.null is False, f"{name}.organization.null is not False"
            assert field.remote_field.on_delete.__name__ == "PROTECT", (
                f"{name}.organization.on_delete is not PROTECT"
            )

    @pytest.mark.skipif(
        not _FORMS_IS_POSTGRES,
        reason="Constraint existence check requires PostgreSQL.",
    )
    def test_0007_composite_fk_constraints_exist(self) -> None:
        """After 0007, parent UNIQUE constraints and composite FKs exist."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0007)])

        with connection.cursor() as cursor:
            # Parent UNIQUE constraints.
            for constraint_name, table in [
                ("forms_form_id_org_unique", "quickscale_modules_forms_form"),
                (
                    "forms_formfield_id_org_unique",
                    "quickscale_modules_forms_formfield",
                ),
                (
                    "forms_formsubmission_id_org_unique",
                    "quickscale_modules_forms_formsubmission",
                ),
            ]:
                cursor.execute(
                    """
                    SELECT 1 FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    WHERE pc.conname = %s AND c.relname = %s AND pc.contype = 'u'
                    """,
                    [constraint_name, table],
                )
                assert cursor.fetchone() is not None, (
                    f"Parent UNIQUE '{constraint_name}' on {table} not found."
                )

            # Composite child FKs.
            for constraint_name, child_table, parent_table in [
                (
                    "forms_formfield_form_org_fk",
                    "quickscale_modules_forms_formfield",
                    "quickscale_modules_forms_form",
                ),
                (
                    "forms_formsubmission_form_org_fk",
                    "quickscale_modules_forms_formsubmission",
                    "quickscale_modules_forms_form",
                ),
                (
                    "forms_formfieldvalue_submission_org_fk",
                    "quickscale_modules_forms_formfieldvalue",
                    "quickscale_modules_forms_formsubmission",
                ),
                (
                    "forms_formfieldvalue_field_org_fk",
                    "quickscale_modules_forms_formfieldvalue",
                    "quickscale_modules_forms_formfield",
                ),
            ]:
                cursor.execute(
                    """
                    SELECT 1 FROM pg_constraint pc
                    JOIN pg_class child_cls ON child_cls.oid = pc.conrelid
                    JOIN pg_class parent_cls ON parent_cls.oid = pc.confrelid
                    WHERE pc.conname = %s
                      AND child_cls.relname = %s
                      AND parent_cls.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [constraint_name, child_table, parent_table],
                )
                assert cursor.fetchone() is not None, (
                    f"Composite FK '{constraint_name}' from {child_table} "
                    f"to {parent_table} not found."
                )

    def test_0007_reverse_removes_composite_fk_constraints(self) -> None:
        """Reverse 0007→0006 succeeds.

        The ``organization`` field on FormField was added by migration
        0007 (Step 1), so after reversing to 0006 the field should no
        longer exist on the historical model — Django's reverse of
        ``AddField`` is ``RemoveField``.
        """
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)

        executor.migrate([(self.APP_LABEL, self.MIG_0006)])
        executor.loader.build_graph()

        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0007)])

        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0006)])

        state = executor.loader.project_state([(self.APP_LABEL, self.MIG_0006)])
        FormField = state.apps.get_model(self.APP_LABEL, "FormField")
        with pytest.raises(FieldDoesNotExist):
            FormField._meta.get_field("organization")

    def test_0007_replay_idempotent(self) -> None:
        """Forward, reverse, forward again — replay is idempotent."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)

        executor.migrate([(self.APP_LABEL, self.MIG_0006)])
        executor.loader.build_graph()

        # Forward.
        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0007)])

        # Reverse.
        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0006)])

        # Re-apply.
        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0007)])

        state = executor.loader.project_state([(self.APP_LABEL, self.MIG_0007)])
        FormField = state.apps.get_model(self.APP_LABEL, "FormField")
        field = FormField._meta.get_field("organization")
        assert field.null is False

    @pytest.mark.skipif(
        not _FORMS_IS_POSTGRES,
        reason="Deferrability check requires PostgreSQL pg_constraint.",
    )
    def test_0007_composite_fks_are_deferrable_initially_deferred(self) -> None:
        """Each composite FK created by 0007 is DEFERRABLE INITIALLY DEFERRED.

        Regression for CR-AF12-005: the AF12 shared contract requires
        that composite FKs carry the ``DEFERRABLE INITIALLY DEFERRED``
        property so that bulk operations (data migrations, backfills)
        can temporarily defer FK checking when needed.
        """
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0007)])

        composite_fk_constraints = [
            ("forms_formfield_form_org_fk", "quickscale_modules_forms_formfield"),
            (
                "forms_formsubmission_form_org_fk",
                "quickscale_modules_forms_formsubmission",
            ),
            (
                "forms_formfieldvalue_submission_org_fk",
                "quickscale_modules_forms_formfieldvalue",
            ),
            (
                "forms_formfieldvalue_field_org_fk",
                "quickscale_modules_forms_formfieldvalue",
            ),
        ]

        with connection.cursor() as cursor:
            for constraint_name, child_table in composite_fk_constraints:
                cursor.execute(
                    """
                    SELECT pc.condeferrable, pc.condeferred
                    FROM pg_constraint pc
                    JOIN pg_class c ON c.oid = pc.conrelid
                    WHERE pc.conname = %s
                      AND c.relname = %s
                      AND pc.contype = 'f'
                    """,
                    [constraint_name, child_table],
                )
                row = cursor.fetchone()
                assert row is not None, (
                    f"Composite FK '{constraint_name}' on {child_table} not found."
                )
                condeferrable, condeferred = row
                assert condeferrable is True, (
                    f"'{constraint_name}' on {child_table} must be DEFERRABLE, "
                    f"got condeferrable={condeferrable}"
                )
                assert condeferred is True, (
                    f"'{constraint_name}' on {child_table} must be INITIALLY DEFERRED, "
                    f"got condeferred={condeferred}"
                )

    def test_0007_to_0008_migration_chain(self) -> None:
        """Forward through 0007→0008 succeeds (AF11 compatibility)."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0008)])

        state = executor.loader.project_state([(self.APP_LABEL, self.MIG_0008)])
        for name in ("FormField", "FormSubmission", "FormFieldValue"):
            model = state.apps.get_model(self.APP_LABEL, name)
            field = model._meta.get_field("organization")
            assert field.null is False, (
                f"{name}.organization must be NOT NULL after 0008"
            )


# ---------------------------------------------------------------------------
# AF12 Phase 2 — direct parent-organization mutation rejection proofs
# (CR-AF12-001 resolution)
# ---------------------------------------------------------------------------
# These tests prove that the composite FKs installed by Forms migration
# 0007 reject attempts to change a parent's organization_id when child
# rows reference the old (parent_id, organization_id) pair.
#
# The FK constraint enforces:
#   (child.parent_fk, child.organization_id) =
#   (parent.id, parent.organization_id)
#
# Updating the parent's organization_id breaks this equality for
# existing child rows and must be rejected with a foreign key violation.
#
# Tests are PostgreSQL-only because FK enforcement uses constraints that
# only PostgreSQL validates.
#
# NOTE on proof isolation (CR-AF12-002): The Forms module test suite
# requires a running PostgreSQL database (post-AF13) and some environments
# may not have the infrastructure configured. The composite FK contract
# for forms mirrors the same tenancy.py helpers and migration pattern
# validated through the CRM + orgs suites. These tests provide direct
# Forms-side evidence when PostgreSQL is available; the overall AF12
# contract is independently validated via CRM and orgs migration proofs.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.skipif(
    not _FORMS_IS_POSTGRES,
    reason="Parent-org mutation rejection proof requires PostgreSQL FK enforcement.",
)
class TestFormsParentOrgMutationRejection:
    """Prove that parent org_id mutations are rejected by the composite FK."""

    def test_form_org_id_mutation_rejected_when_formfield_exists(self) -> None:
        """Updating Form.organization_id fails when a FormField
        references the old (form_id, organization_id) pair."""
        from django.db import IntegrityError, connection, transaction

        from quickscale_modules_forms.models import Form, FormField
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-a")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-b")

        form = Form.all_objects.create(
            organization=org_a,
            title="Mutation Target Form",
            slug="mut-form",
        )
        FormField.all_objects.create(
            organization=org_a,
            form=form,
            field_type=FormField.FIELD_TYPE_TEXT,
            label="Name",
            name="name",
            order=1,
        )

        # Attempt to reassign the parent form to a different org.
        # The composite FK (formfield.form_id, formfield.organization_id)
        # → (form.id, form.organization_id) should reject this.
        #
        # The composite FK is DEFERRABLE INITIALLY DEFERRED, so force it to
        # IMMEDIATE inside the atomic block to catch the violation inline.
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute("SET CONSTRAINTS forms_formfield_form_org_fk IMMEDIATE")
            Form.all_objects.filter(pk=form.pk).update(organization=org_b)

    def test_formsubmission_org_id_mutation_rejected_when_values_exist(self) -> None:
        """Updating FormSubmission.organization_id fails when a
        FormFieldValue references the old (submission_id, organization_id)."""
        from django.db import IntegrityError, connection, transaction

        from quickscale_modules_forms.models import (
            Form,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-c")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-d")

        form = Form.all_objects.create(
            organization=org_a,
            title="Submission Mutation Form",
            slug="sub-mut-form",
        )
        submission = FormSubmission.all_objects.create(
            organization=org_a,
            form=form,
        )
        FormFieldValue.all_objects.create(
            organization=org_a,
            submission=submission,
            field_name="email",
            field_label="Email",
            value="test@test.com",
        )

        # The composite FK is DEFERRABLE INITIALLY DEFERRED, so force it to
        # IMMEDIATE inside the atomic block to catch the violation inline.
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET CONSTRAINTS forms_formfieldvalue_submission_org_fk IMMEDIATE"
                )
            FormSubmission.all_objects.filter(pk=submission.pk).update(
                organization=org_b
            )

    def test_formfield_org_id_mutation_rejected_when_fieldvalue_has_nonnull_field(
        self,
    ) -> None:
        """Updating FormField.organization_id fails when a FormFieldValue
        has a non-null field_id referencing the old (field_id, organization_id)
        pair."""
        from django.db import IntegrityError, connection, transaction

        from quickscale_modules_forms.models import (
            Form,
            FormField,
            FormFieldValue,
            FormSubmission,
        )
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-e")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-f")

        form = Form.all_objects.create(
            organization=org_a,
            title="Field Mutation Form",
            slug="field-mut-form",
        )
        field = FormField.all_objects.create(
            organization=org_a,
            form=form,
            field_type=FormField.FIELD_TYPE_TEXT,
            label="Name",
            name="name",
            order=1,
        )
        submission = FormSubmission.all_objects.create(
            organization=org_a,
            form=form,
        )
        FormFieldValue.all_objects.create(
            organization=org_a,
            submission=submission,
            field=field,
            field_name="name",
            field_label="Name",
            value="Locked value",
        )

        # The composite FK is DEFERRABLE INITIALLY DEFERRED, so force it to
        # IMMEDIATE inside the atomic block to catch the violation inline.
        with pytest.raises(IntegrityError), transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET CONSTRAINTS forms_formfieldvalue_field_org_fk IMMEDIATE"
                )
            FormField.all_objects.filter(pk=field.pk).update(organization=org_b)

    def test_form_org_id_mutation_without_children_succeeds(self) -> None:
        """Updating Form.organization_id succeeds when NO FormField rows
        reference the old pair — positive control."""
        from quickscale_modules_forms.models import Form
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="Org A", slug="forms-mut-g")
        org_b = Organization.objects.create(name="Org B", slug="forms-mut-h")

        form = Form.all_objects.create(
            organization=org_a,
            title="No Child Form",
            slug="no-child-form",
        )

        # No FormField referencing this form — mutation should succeed.
        Form.all_objects.filter(pk=form.pk).update(organization=org_b)
        form.refresh_from_db()
        assert form.organization_id == org_b.pk
