"""W004/W007 stay quiet while a tenant model's schema is still pending.

``migrate`` runs Django's system checks before it applies anything, so a fresh
generated project would otherwise report the FORCE-RLS and composite-FK
warnings on the tables its ``0001_initial`` is about to create.  These tests
pin the skip for an unapplied migration or an absent table, the control that a
migrated non-compliant table still warns, and the migration-state read.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from django.db import connection

import quickscale_modules_orgs._tenancy_references as _tenancy_references
import quickscale_modules_orgs._tenancy_schema as _tenancy_schema
from quickscale_modules_orgs import checks
from quickscale_modules_orgs._tenancy_schema import (
    apps_with_unapplied_migrations,
    models_awaiting_schema,
)
from quickscale_modules_orgs.checks import (
    check_tenant_isolation,
    check_tenant_reference_equality,
)
from quickscale_modules_orgs.tenancy import apply_force_rls, get_tenant_models


def _mock_model(
    name: str = "PendingModel",
    app_label: str = "pending_app",
) -> MagicMock:
    """Build a model-like object with an uninstalled app label."""
    model = MagicMock(spec=[])
    model.__name__ = name
    model._meta = MagicMock()
    model._meta.app_label = app_label
    model._meta.db_table = f"{app_label}_{name.lower()}"
    model._meta.label_lower = f"{app_label}.{name.lower()}"
    return model


def _isolation_result(model: MagicMock, *, has_force_rls: bool | None) -> dict:
    """Return the isolation result for *model* with the policy state forced."""
    return {
        "model": model,
        "app_label": model._meta.app_label,
        "model_name": model.__name__,
        "db_table": model._meta.db_table,
        "has_organization_id": True,
        "has_force_rls": has_force_rls,
        "passed": has_force_rls is True,
    }


# ---------------------------------------------------------------------------
# W004 — FORCE-RLS policy check
# ---------------------------------------------------------------------------


def test_w004_is_skipped_when_the_model_awaits_its_migration() -> None:
    """A model whose app migration is unapplied reports no W004."""
    model = _mock_model()

    with (
        patch.object(checks, "get_tenant_models", return_value=[model]),
        patch.object(
            checks,
            "check_tenant_model_isolation",
            return_value=_isolation_result(model, has_force_rls=False),
        ),
        patch.object(
            checks,
            "_models_awaiting_schema",
            return_value=frozenset({model._meta.label_lower}),
        ),
    ):
        assert check_tenant_isolation(app_configs=None) == []


def test_w004_is_skipped_when_the_table_is_absent() -> None:
    """The schema helper reports a model whose table does not exist yet."""
    from quickscale_modules_crm.models import Tag

    with (
        patch.object(
            _tenancy_schema, "apps_with_unapplied_migrations", lambda: frozenset()
        ),
        patch.object(_tenancy_schema, "existing_table_names", lambda: frozenset()),
    ):
        assert models_awaiting_schema([Tag]) == frozenset({"quickscale_crm.tag"})


def test_w004_still_warns_for_a_migrated_model() -> None:
    """A migrated table outside the policy contract keeps its W004."""
    model = _mock_model()

    with (
        patch.object(checks, "get_tenant_models", return_value=[model]),
        patch.object(
            checks,
            "check_tenant_model_isolation",
            return_value=_isolation_result(model, has_force_rls=False),
        ),
        patch.object(checks, "_models_awaiting_schema", return_value=frozenset()),
    ):
        messages = check_tenant_isolation(app_configs=None)

    assert [message.id for message in messages] == ["quickscale_orgs.W004"]


def test_w003_still_reports_while_the_model_awaits_schema() -> None:
    """The metadata-only organization_id warning is not schema state."""
    model = _mock_model()
    result = _isolation_result(model, has_force_rls=None)
    result["has_organization_id"] = False

    with (
        patch.object(checks, "get_tenant_models", return_value=[model]),
        patch.object(checks, "check_tenant_model_isolation", return_value=result),
        patch.object(
            checks,
            "_models_awaiting_schema",
            return_value=frozenset({model._meta.label_lower}),
        ),
    ):
        messages = check_tenant_isolation(app_configs=None)

    assert [message.id for message in messages] == ["quickscale_orgs.W003"]


@pytest.mark.django_db(transaction=True)
def test_migrated_non_compliant_table_still_warns_in_the_real_walk() -> None:
    """The skip does not hide a real gap on a fully migrated table."""
    from tests.project_tenant_app.models import ProjectListing

    table = ProjectListing._meta.db_table
    quoted_table = connection.ops.quote_name(table)
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT policyname
            FROM pg_policies
            WHERE schemaname = current_schema()
              AND tablename = %s
              AND cmd = 'ALL'
            """,
            [table],
        )
        policy_rows = cursor.fetchall()
    assert len(policy_rows) == 1
    policy_name = policy_rows[0][0]

    try:
        with connection.cursor() as cursor:
            cursor.execute(f"ALTER TABLE {quoted_table} NO FORCE ROW LEVEL SECURITY")

        with patch.object(checks, "get_tenant_models", return_value=[ProjectListing]):
            messages = check_tenant_isolation(app_configs=None)

        assert any(message.id == "quickscale_orgs.W004" for message in messages), (
            "a migrated table outside the FORCE-RLS contract must keep warning"
        )
    finally:
        with connection.schema_editor() as schema_editor:
            apply_force_rls(schema_editor, ((table, policy_name),))


# ---------------------------------------------------------------------------
# W007 — composite tenant-reference constraint check
# ---------------------------------------------------------------------------


def test_w007_is_skipped_for_a_pending_child_or_parent() -> None:
    """A reference that waits for either side's migration reports no gap."""
    from quickscale_modules_crm.models import Contact, ContactNote

    candidates = [Contact, ContactNote]
    with patch.object(
        _tenancy_references,
        "find_composite_reference_constraint",
        return_value=None,
    ):
        pending = _tenancy_references.tenant_reference_equality_gaps(
            candidates,
            pending_labels=frozenset({"quickscale_crm.contactnote"}),
        )
        migrated = _tenancy_references.tenant_reference_equality_gaps(candidates)

    assert not any("contactnote.contact" in gap for gap in pending)
    assert any("contactnote.contact" in gap for gap in migrated)


def test_pending_model_exemption_declarations_are_not_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pending model's malformed declaration waits for its migration too."""
    from quickscale_modules_crm.models import Contact, ContactNote

    monkeypatch.setattr(
        ContactNote,
        "tenant_reference_exemptions",
        ["contact"],
        raising=False,
    )
    candidates = [Contact, ContactNote]

    assert (
        _tenancy_references.tenant_reference_equality_gaps(
            candidates,
            pending_labels=frozenset({"quickscale_crm.contactnote"}),
        )
        == ()
    )

    with patch.object(
        _tenancy_references,
        "find_composite_reference_constraint",
        return_value=None,
    ):
        migrated = _tenancy_references.tenant_reference_equality_gaps(candidates)

    assert any("non-mapping" in gap for gap in migrated)


def test_pending_parent_keeps_a_non_pending_child_exemption_valid(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pending parent stays discoverable, so the child's exemption is real."""
    from quickscale_modules_crm.models import Contact, ContactNote

    monkeypatch.setattr(
        ContactNote,
        "tenant_reference_exemptions",
        {"contact": "Reviewed retention while the parent migrates."},
        raising=False,
    )

    gaps = _tenancy_references.tenant_reference_equality_gaps(
        [Contact, ContactNote],
        pending_labels=frozenset({"quickscale_crm.contact"}),
    )

    assert gaps == ()


def test_check_tenant_reference_equality_skips_pending_models() -> None:
    """The registered check passes pending labels into the discovery walk."""
    tenant_models = get_tenant_models()
    awaiting = frozenset(model._meta.label_lower for model in tenant_models)

    with (
        patch.object(checks, "get_tenant_models", return_value=tenant_models),
        patch.object(checks, "_models_awaiting_schema", return_value=awaiting),
        patch.object(
            _tenancy_references,
            "find_composite_reference_constraint",
            return_value=None,
        ),
    ):
        assert check_tenant_reference_equality(app_configs=None) == []

    with (
        patch.object(checks, "get_tenant_models", return_value=tenant_models),
        patch.object(checks, "_models_awaiting_schema", return_value=frozenset()),
        patch.object(
            _tenancy_references,
            "find_composite_reference_constraint",
            return_value=None,
        ),
    ):
        assert check_tenant_reference_equality(app_configs=None)


# ---------------------------------------------------------------------------
# Schema readiness helper
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_migrated_database_has_no_awaiting_models() -> None:
    """After the test database is migrated, the helper skips nothing."""
    assert apps_with_unapplied_migrations() == frozenset()
    assert models_awaiting_schema(get_tenant_models()) == frozenset()


def test_unapplied_migration_marks_its_app(monkeypatch: pytest.MonkeyPatch) -> None:
    """The migration plan's app labels become the pending set."""

    class _FakeExecutor:
        def __init__(self, connection: object) -> None:
            del connection
            self.loader = SimpleNamespace(
                graph=SimpleNamespace(leaf_nodes=lambda: []),
            )

        def migration_plan(self, targets: list) -> list:
            assert targets == []
            return [(SimpleNamespace(app_label="quickscale_forms"), False)]

    monkeypatch.setattr(_tenancy_schema, "MigrationExecutor", _FakeExecutor)

    assert apps_with_unapplied_migrations() == frozenset({"quickscale_forms"})


def test_uninstalled_probe_never_reads_the_database(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A unit-test probe app has no migration history to consult."""

    def _unexpected_read() -> frozenset[str]:
        raise AssertionError("probe models must not reach the database")

    monkeypatch.setattr(_tenancy_schema, "existing_table_names", _unexpected_read)

    assert models_awaiting_schema([_mock_model()]) == frozenset()


def test_non_postgres_database_skips_schema_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The catalog checks do not run on SQLite, so nothing is pending there."""

    class _SqliteConnection:
        vendor = "sqlite"

    monkeypatch.setattr(_tenancy_schema, "connection", _SqliteConnection())

    assert apps_with_unapplied_migrations() == frozenset()
    assert models_awaiting_schema([_mock_model()]) == frozenset()
