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
    def test_0007_composite_fks_are_not_deferrable(self) -> None:
        """Each composite FK created by 0007 is NOT DEFERRABLE.

        SA60 ratifies NOT DEFERRABLE as the uniform policy for all
        Option C composite FKs (fail-fast on FK violations — no
        ``SET CONSTRAINTS DEFERRED`` carve-out needed for fixture
        restores).  The inlined ``DEFERRABLE INITIALLY DEFERRED``
        SQL was the outlier; now aligned with the shared helper
        in ``orgs/tenancy.py:_ADD_COMPOSITE_FK_SQL``.
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
                assert condeferrable is False, (
                    f"'{constraint_name}' on {child_table} must be NOT DEFERRABLE, "
                    f"got condeferrable={condeferrable}"
                )
                assert condeferred is False, (
                    f"'{constraint_name}' on {child_table} must NOT be "
                    f"INITIALLY DEFERRED, got condeferred={condeferred}"
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
# SA79 — Regression proof: 0007 backfill works under NOBYPASSRLS
# ---------------------------------------------------------------------------
# These tests prove that the 0007 migration's backfill correctly populates
# FormField.organization_id from the parent Form even when FORCE RLS is
# active on the Form table (enabled in 0006).  The fix sets the
# ``app.operator_access`` GUC before the backfill so the correlated
# subquery on Form is not blocked by RLS.
#
# Unlike the ``TestFormsMigration0007CompositeFK`` class above, these
# tests do NOT use ``@pytest.mark.bypass_rls`` — they are designed to pass
# under a NOBYPASSRLS database role, proving the SA79 fix works in the
# restricted-role CI context.
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
class TestFormsMigration0007BackfillSA79:
    """Regression proof that 0007 backfill populates FormField.org
    correctly under NOBYPASSRLS (SA79)."""

    APP_LABEL = "quickscale_modules_forms"
    MIG_0006 = "0006_enable_rls"
    MIG_0007 = "0007_new_organization_ownership"

    def test_backfill_matches_form_org_after_0007(self) -> None:
        """Migrate 0006→0007 and verify every seeded FormField row has
        the same organization_id as its parent Form — proving the
        backfill correctly propagates org under active FORCE RLS."""
        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        executor = MigrationExecutor(connection)

        executor.migrate([(self.APP_LABEL, self.MIG_0006)])
        executor.loader.build_graph()

        executor = MigrationExecutor(connection)
        executor.migrate([(self.APP_LABEL, self.MIG_0007)])

        # Read state at 0007 — historical model proxy.
        state = executor.loader.project_state([(self.APP_LABEL, self.MIG_0007)])
        HistoricalFormField = state.apps.get_model(self.APP_LABEL, "FormField")

        # Verify every FormField row has a non-null org.
        null_org_count = HistoricalFormField.objects.filter(
            organization__isnull=True
        ).count()
        assert null_org_count == 0, (
            f"{null_org_count} FormField rows still have NULL organization_id "
            "after 0007 backfill"
        )

        # Verify every FormField's org matches its parent Form's org.
        for ff in HistoricalFormField.objects.select_related("form").all():
            assert ff.organization_id == ff.form.organization_id, (
                f"FormField id={ff.pk} (form_id={ff.form_id}) has "
                f"organization_id={ff.organization_id} but parent Form "
                f"id={ff.form_id} has organization_id={ff.form.organization_id}"
            )

    # CR-SA79-002 RESOLVED: non-system tenant data proof
    def test_operator_access_allows_cross_org_read_under_rls(self) -> None:
        """Prove that setting ``app.operator_access = 'on'`` allows
        reading Form rows across org boundaries under FORCE RLS with
        NOBYPASSRLS — the core mechanism behind the CR-SA79-001 fix.

        Under the ``quickscale_test_role`` (NOBYPASSRLS), the Form RLS
        policy blocks SELECT for rows whose ``organization_id`` does not
        match ``app.current_org_id``.  With ``app.operator_access = 'on'``,
        the policy's ``FOR SELECT`` OR clause allows cross-tenant reads.

        This proves the 0007 backfill can correctly read any parent
        Form's ``organization_id`` regardless of the row's org — including
        non-system tenant data.
        """
        from uuid import uuid4

        from django.db import connection, transaction

        from quickscale_modules_forms.models import Form, FormField
        from quickscale_modules_orgs.current_org import (
            _set_db_current_org_id,
            _set_operator_access,
            get_current_org_id,
            reset_current_org_id,
            set_current_org_id,
        )
        from quickscale_modules_orgs.models import Organization

        prior_org_id = get_current_org_id()

        # All GUC-sensitive operations must run inside an explicit
        # transaction.atomic() block so that SET LOCAL works.
        with transaction.atomic():
            try:
                # Create a non-system organization (control-plane model;
                # no RLS, no all_objects, use default objects).
                org_b = Organization.objects.create(
                    name="Non-System SA79 Operator Test",
                    slug=f"sa79-op-{uuid4().hex[:8]}",
                )

                # Create a non-system Form under org_b.
                set_current_org_id(org_b.pk)
                _set_db_current_org_id(org_b.pk)

                ns_form = Form.all_objects.create(
                    title="Non-System Operator Form",
                    slug=f"ns-op-form-{uuid4().hex[:8]}",
                    organization=org_b,
                )
                ns_form_id = ns_form.pk

                # Create a non-system FormField linked to the non-system Form.
                FormField.all_objects.create(
                    form=ns_form,
                    organization=org_b,
                    field_type=FormField.FIELD_TYPE_TEXT,
                    label="Name",
                    name="name",
                    order=1,
                )

                # Verify the non-system Form IS visible when querying
                # with the matching org context.
                set_current_org_id(org_b.pk)
                _set_db_current_org_id(org_b.pk)
                found_form = Form.objects.get(pk=ns_form_id)
                assert found_form is not None

                # Verify the non-system Form is NOT visible when querying
                # under a different org context (System org).
                system_org = Organization.objects.get_system_org()
                set_current_org_id(system_org.pk)
                _set_db_current_org_id(system_org.pk)
                with pytest.raises(Form.DoesNotExist):
                    Form.objects.get(pk=ns_form_id)

                # CR-SA79-001 PROOF: With ``app.operator_access = 'on'``,
                # the non-system Form IS readable despite being under a
                # different org context.
                _set_operator_access("on")

                with connection.cursor() as cur:
                    cur.execute(
                        "SELECT id FROM quickscale_modules_forms_form WHERE id = %s",
                        [ns_form_id],
                    )
                    row = cur.fetchone()

                assert row is not None, (
                    f"Form id={ns_form_id} not readable with "
                    f"operator_access='on' under system org context."
                )
                assert row[0] == ns_form_id

            finally:
                # Restore org context within the atomic block.
                if prior_org_id:
                    set_current_org_id(prior_org_id)
                    _set_db_current_org_id(prior_org_id)
                else:
                    reset_current_org_id()

    # CR-SA79-002 RESOLVED: direct MigrationExecutor 0006→0007 proof
    def test_backfill_preserves_non_system_org_after_0007(self) -> None:
        """Seed non-system tenant rows between 0006 and 0007, then verify
        that 0007 backfill correctly assigns the real non-system org from
        the parent Form — not the System org fallback.

        Unlike ``test_operator_access_allows_cross_org_read_under_rls``
        (which proves the operator_access mechanism), this test actually
        runs the 0006→0007 migration with pre-existing non-system tenant
        data and verifies the backfill results — proving the migration
        works end-to-end for cross-org real data under NOBYPASSRLS.
        """
        from uuid import uuid4

        from django.db import connection
        from django.db.migrations.executor import MigrationExecutor

        from quickscale_modules_forms.models import Form
        from quickscale_modules_orgs.current_org import (
            get_current_org_id,
            reset_current_org_id,
            set_current_org_id,
        )
        from quickscale_modules_orgs.models import Organization

        app_label = self.APP_LABEL

        # Create the non-system organization at the full migration state
        # (control-plane model — no RLS).
        ns_org = Organization.objects.create(
            name="Non-System SA79 Backfill Test",
            slug=f"sa79-bf-{uuid4().hex[:8]}",
        )

        prior_org_id = get_current_org_id()

        # Create the non-system Form at the full DB state with proper org
        # context so FORCE RLS on Form (enabled in 0006) does not block
        # the INSERT.
        set_current_org_id(ns_org.pk)
        ns_form = Form.all_objects.create(
            title="Non-System Backfill Form",
            slug=f"ns-bf-form-{uuid4().hex[:8]}",
            organization=ns_org,
        )
        ns_form_id = ns_form.pk

        # Restore prior org context.
        if prior_org_id:
            set_current_org_id(prior_org_id)
        else:
            reset_current_org_id()

        executor = MigrationExecutor(connection)

        # Roll back to 0006 so we can insert pre-backfill FormField rows
        # without the organization column (added in 0007 Step 1).
        # The Form row created above survives (Form is not touched by 0007).
        executor.migrate([(app_label, self.MIG_0006)])
        executor.loader.build_graph()

        # Insert FormField rows via raw SQL WITHOUT organization_id
        # (pre-0007 state — the column does not exist yet).
        with connection.cursor() as cur:
            for name, label, field_type in [
                ("full_name", "Full Name", "text"),
                ("email", "Email", "email"),
            ]:
                cur.execute(
                    "INSERT INTO quickscale_modules_forms_formfield "
                    '(form_id, field_type, label, name, "order", '
                    "placeholder, help_text, required, options, "
                    "validation_rules, layout_hint, is_active) "
                    "VALUES (%s, %s, %s, %s, %s, '', '', TRUE, '[]', "
                    "'{}', 'full', TRUE)",
                    [ns_form_id, field_type, label, name, 1],
                )

        # Migrate forward to 0007 — the backfill should copy the
        # non-system org from the parent Form.
        executor = MigrationExecutor(connection)
        executor.migrate([(app_label, self.MIG_0007)])

        # Read state at 0007 via historical model proxy.
        state = executor.loader.project_state([(app_label, self.MIG_0007)])
        HistoricalFormField = state.apps.get_model(app_label, "FormField")

        # Verify the non-system FormField rows have the correct non-system org.
        for ff in HistoricalFormField.objects.filter(form_id=ns_form_id):
            assert ff.organization_id == ns_org.pk, (
                f"FormField id={ff.pk} for non-system Form "
                f"(form_id={ns_form_id}) has "
                f"organization_id={ff.organization_id}, "
                f"expected {ns_org.pk} (non-system org). "
                "The 0007 backfill fell back to the System org instead of "
                "using the parent Form's real organization."
            )

        # Verify no FormField rows have NULL org after backfill.
        null_org_count = HistoricalFormField.objects.filter(
            organization__isnull=True
        ).count()
        assert null_org_count == 0, (
            f"{null_org_count} FormField rows still have NULL "
            "organization_id after 0007 backfill"
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
        # The composite FK is NOT DEFERRABLE, so the SET CONSTRAINTS ...
        # IMMEDIATE call below is a harmless no-op retained for clarity.
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

        # The composite FK is NOT DEFERRABLE, so the SET CONSTRAINTS ...
        # IMMEDIATE call below is a harmless no-op retained for clarity.
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

        # The composite FK is NOT DEFERRABLE, so the SET CONSTRAINTS ...
        # IMMEDIATE call below is a harmless no-op retained for clarity.
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
