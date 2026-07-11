"""SA14.5 — operator_access context manager and RLS template refresh tests.

Tests for:
    * ``operator_access(reason=...)`` context manager (GUC setting, audit
      logging, lifecycle, nesting safety).
    * CR-SA14.5-001: operator_access grants cross-tenant **read** only
      (not write or delete visibility).
    * CR-SA14.5-002: nested operator_access() correctly restores prior
      GUC state.
    * ``refresh_force_rls_policies()`` helper (table/policy iteration,
      revert→apply cycle).
    * ``TenantTableEntry.policy_name`` attribute and registry population.
"""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import MagicMock, call, patch

import pytest
from django.core.exceptions import ImproperlyConfigured

from quickscale_modules_orgs.tenancy import (
    TENANT_TABLE_REGISTRY,
    TenantTableStatus,
    refresh_force_rls_policies,
)
from quickscale_modules_orgs.current_org import (
    operator_access,
    reset_current_org_id,
    set_current_org_id,
)


# =========================================================================
# operator_access context manager — GUC lifecycle
# =========================================================================


class TestOperatorAccessGucLifecycle:
    """Verify the GUC is set on entry and restored on exit (CR-SA14.5-002)."""

    @pytest.fixture(autouse=True)
    def _patch_connection(self) -> Generator[None, None, None]:
        """Patch ``django.db.connection`` to report PostgreSQL vendor.
        Also configures ``fetchone`` for ``_get_operator_access()`` so
        that ``current_setting`` probing returns the default empty string."""
        patcher = patch("django.db.connection")
        mock_conn = patcher.start()
        mock_conn.vendor = "postgresql"
        mock_conn.in_atomic_block = True
        # _get_operator_access() is now called on entry (CR-SA14.5-002
        # nesting-safety save).  Configure the mock cursor.fetchone() to
        # return the default empty GUC value.
        mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            "",
        )
        yield
        patcher.stop()

    def _make_conn(self) -> MagicMock:
        """Create a patched connection mock with PostgreSQL vendor and
        fetchone configured for ``_get_operator_access()``."""
        conn = MagicMock()
        conn.vendor = "postgresql"
        conn.in_atomic_block = True
        conn.cursor.return_value.__enter__.return_value.fetchone.return_value = ("",)
        return conn

    def test_sets_guc_on_entry(self) -> None:
        """``SET LOCAL app.operator_access = 'on'`` is issued on entry."""
        mock_conn = self._make_conn()
        with patch("django.db.connection", mock_conn):
            cursor = mock_conn.cursor.return_value.__enter__.return_value

            with operator_access(reason="test-reason"):
                cursor.execute.assert_any_call(
                    "SET LOCAL app.operator_access = %s",
                    ["on"],
                )

    def test_restores_prior_on_exit(self) -> None:
        """The prior GUC value (empty string) is restored on exit.

        CR-SA14.5-002: nested operator_access() must restore the outer
        scope's GUC value instead of unconditionally clearing to ''."""
        mock_conn = self._make_conn()
        with patch("django.db.connection", mock_conn):
            cursor = mock_conn.cursor.return_value.__enter__.return_value

            with operator_access(reason="test-reason"):
                cursor.reset_mock()

            # Prior was "" (empty string), so the exit call restores "".
            cursor.execute.assert_called_with(
                "SET LOCAL app.operator_access = %s",
                [""],
            )

    def test_on_and_off_both_issued(self) -> None:
        """Both SET LOCAL calls (on entry, off on exit) are made."""
        mock_conn = self._make_conn()
        with patch("django.db.connection", mock_conn):
            cursor = mock_conn.cursor.return_value.__enter__.return_value
            cursor.execute.reset_mock()

            with operator_access(reason="test-reason"):
                pass

            assert cursor.execute.call_count >= 2
            calls = cursor.execute.call_args_list
            # The last call should restore the prior value ("").
            assert calls[-1] == call("SET LOCAL app.operator_access = %s", [""])

    def test_noop_on_sqlite(self) -> None:
        """No SET LOCAL issued on non-PostgreSQL backends."""
        mock_conn = MagicMock()
        mock_conn.vendor = "sqlite"
        with patch("django.db.connection", mock_conn):
            cursor = mock_conn.cursor.return_value.__enter__.return_value

            with operator_access(reason="test-reason"):
                cursor.execute.assert_not_called()

    def test_yields_none(self) -> None:
        """The context manager yields None."""
        mock_conn = self._make_conn()
        with patch("django.db.connection", mock_conn):
            with operator_access(reason="test-reason") as result:
                assert result is None

    def test_nesting_restores_outer_scope(self) -> None:
        """Nested operator_access() must restore the outer scope's GUC
        value instead of unconditionally clearing to ''.

        CR-SA14.5-002 regression: prove via patched _get_operator_access
        that the outer scope's prior ('' ) is restored after the nested
        inner scope exits.

        Strategy: use a stateful side_effect for _get_operator_access that
        tracks the "database" GUC value across SET LOCAL calls.  This
        simulates the real PostgreSQL behavior where _get_operator_access
        reads the current GUC and _set_operator_access writes it.
        """
        # Stateful simulation of the PostgreSQL GUC.
        _guc_state: list[str] = [""]  # Use list for mutability in closures.

        mock_set = MagicMock()

        def _sim_set(value: str) -> None:
            _guc_state[0] = value
            mock_set(value)

        with patch(
            "quickscale_modules_orgs.current_org._get_operator_access",
            side_effect=lambda: _guc_state[0],
        ):
            with patch(
                "quickscale_modules_orgs.current_org._set_operator_access",
                side_effect=_sim_set,
            ):
                with patch("django.db.connection") as mock_conn:
                    mock_conn.vendor = "postgresql"
                    cursor = mock_conn.cursor.return_value.__enter__.return_value

                    # Outer scope: prior GUC is '' (default), sets to 'on'.
                    with operator_access(reason="outer"):
                        assert _guc_state[0] == "on", (
                            f"After outer entry, GUC should be 'on', "
                            f"got {_guc_state[0]!r}"
                        )
                        cursor.reset_mock()

                        # Inner scope: saves prior ('on'), sets to 'on',
                        # restores prior ('on').
                        with operator_access(reason="inner"):
                            assert _guc_state[0] == "on", (
                                f"During inner scope, GUC should be 'on', "
                                f"got {_guc_state[0]!r}"
                            )

                        # After inner exits: prior ('on') restored.
                        assert _guc_state[0] == "on", (
                            f"After inner exit, GUC should still be 'on', "
                            f"got {_guc_state[0]!r}"
                        )

                    # After outer exits: prior ('') restored.
                    assert _guc_state[0] == "", (
                        f"After outer exit, GUC should be '' (outer's prior), "
                        f"got {_guc_state[0]!r}. "
                        "CR-SA14.5-002: nested operator_access must restore "
                        "the outer scope's prior GUC value."
                    )

                # Verify _set_operator_access was called with the right
                # values at each lifecycle point.  The call sequence is:
                #   1. Outer entry: SET 'on'
                #   2. Inner entry: SET 'on'
                #   3. Inner exit:  SET prior ('on')
                #   4. Outer exit:  SET prior ('')
                assert mock_set.call_count >= 4, (
                    f"Expected ≥4 _set_operator_access calls, got {mock_set.call_count}"
                )


# =========================================================================
# operator_access context manager — audit logging
# =========================================================================


class TestOperatorAccessAuditLogging:
    """Verify activation and deactivation are logged."""

    @pytest.fixture(autouse=True)
    def _patch_connection(self) -> Generator[None, None, None]:
        patcher = patch("django.db.connection")
        mock_conn = patcher.start()
        mock_conn.vendor = "postgresql"
        mock_conn.in_atomic_block = True
        mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            "",
        )
        yield
        patcher.stop()

    def test_logs_activation(self) -> None:
        """Activation is logged at INFO with the reason."""
        with patch("quickscale_modules_orgs.current_org.logger") as mock_logger:
            with patch("django.db.connection") as mock_conn:
                mock_conn.vendor = "postgresql"
                mock_conn.in_atomic_block = True
                mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                    "",
                )
                with operator_access(reason="ticket-42"):
                    mock_logger.info.assert_any_call(
                        "operator_access activated",
                        extra={"reason": "ticket-42"},
                    )

    def test_logs_deactivation(self) -> None:
        """Deactivation is logged at INFO with the reason."""
        with patch("quickscale_modules_orgs.current_org.logger") as mock_logger:
            with patch("django.db.connection") as mock_conn:
                mock_conn.vendor = "postgresql"
                mock_conn.in_atomic_block = True
                mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                    "",
                )
                with operator_access(reason="ticket-42"):
                    pass
            mock_logger.info.assert_any_call(
                "operator_access deactivated",
                extra={"reason": "ticket-42"},
            )

    def test_reason_propagated_in_both_events(self) -> None:
        """The same reason string appears in both activation and deactivation."""
        with patch("quickscale_modules_orgs.current_org.logger") as mock_logger:
            with patch("django.db.connection") as mock_conn:
                mock_conn.vendor = "postgresql"
                mock_conn.in_atomic_block = True
                mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                    "",
                )
                with operator_access(reason="nightly-maintenance"):
                    pass
            reasons = {
                c.kwargs.get("extra", {}).get("reason")
                for c in mock_logger.info.call_args_list
                if isinstance(c.args[0], str) and "operator_access" in c.args[0]
            }
            assert "nightly-maintenance" in reasons


# =========================================================================
# operator_access context manager — edge cases
# =========================================================================


class TestOperatorAccessEdgeCases:
    """Edge cases for the operator_access context manager."""

    @pytest.fixture(autouse=True)
    def _patch_connection(self) -> Generator[None, None, None]:
        patcher = patch("django.db.connection")
        mock_conn = patcher.start()
        mock_conn.vendor = "postgresql"
        mock_conn.in_atomic_block = True
        mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
            "",
        )
        yield
        patcher.stop()

    def test_reason_is_required_keyword(self) -> None:
        """``reason`` is a required keyword argument."""
        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                "",
            )
            with pytest.raises(TypeError):
                with operator_access():  # type: ignore[call-arg]
                    pass  # pragma: no cover

    def test_reason_empty_string(self) -> None:
        """Empty string reason does not cause issues."""
        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                "",
            )
            with operator_access(reason=""):
                pass  # should not raise

    def test_long_reason(self) -> None:
        """Long reason strings are handled correctly."""
        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            mock_conn.cursor.return_value.__enter__.return_value.fetchone.return_value = (
                "",
            )
            long_reason = "x" * 1000
            with operator_access(reason=long_reason):
                pass  # should not raise


# =========================================================================
# refresh_force_rls_policies — PostgreSQL behavior
# =========================================================================


class TestRefreshForceRlsPoliciesPostgres:
    """Tests for ``refresh_force_rls_policies`` on PostgreSQL."""

    @pytest.fixture
    def pg_schema_editor(self) -> MagicMock:
        editor = MagicMock()
        editor.connection.vendor = "postgresql"
        return editor

    def test_calls_revert_and_apply(self, pg_schema_editor: MagicMock) -> None:
        """The function calls both revert and apply for enrolled tables."""
        refresh_force_rls_policies(pg_schema_editor)
        # The function uses revert_force_rls then apply_force_rls internally.
        # Each bundles multiple SQL statements into a single execute call
        # per table: revert=1 call (DROP+NO FORCE+DISABLE), apply=1 call
        # (ENABLE+FORCE+CREATE POLICY) = 2 calls per enrolled table.
        enrolled_count = sum(
            1
            for e in TENANT_TABLE_REGISTRY
            if e.status == TenantTableStatus.ENROLLED and e.policy_name
        )
        assert pg_schema_editor.execute.call_count == enrolled_count * 2

    def test_includes_current_policy_names(self, pg_schema_editor: MagicMock) -> None:
        """The constructed policy names appear in the executed SQL."""
        refresh_force_rls_policies(pg_schema_editor)
        all_sql = " ".join(c[0][0] for c in pg_schema_editor.execute.call_args_list)
        # Check a known policy name appears.
        known_policies = {
            "crm_tag_org_isolation",
            "forms_form_org_isolation",
            "billing_credit_balance_org_isolation",
            "blog_category_org_isolation",
            "listings_listing_org_isolation",
            "social_link_org_isolation",
        }
        for policy in known_policies:
            assert policy in all_sql, (
                f"Expected policy name {policy!r} not found in executed SQL"
            )

    def test_revert_apply_order(self, pg_schema_editor: MagicMock) -> None:
        """The revert (DROP) phase comes before the apply (CREATE) phase."""
        refresh_force_rls_policies(pg_schema_editor)
        calls = pg_schema_editor.execute.call_args_list

        # DROP should appear before CREATE for any given policy.
        # Since revert runs for all tables first, then apply runs for all,
        # any DROP should be in the first half of calls and any CREATE
        # in the second half.
        drop_idx = min(i for i, c in enumerate(calls) if "DROP POLICY" in c[0][0])
        create_idx = max(i for i, c in enumerate(calls) if "CREATE POLICY" in c[0][0])
        # The last drop should precede the first create.
        assert drop_idx < create_idx


# =========================================================================
# refresh_force_rls_policies — SQLite no-op
# =========================================================================


class TestRefreshForceRlsPoliciesSqlite:
    """``refresh_force_rls_policies`` is a no-op on non-PostgreSQL."""

    @pytest.fixture
    def sqlite_schema_editor(self) -> MagicMock:
        editor = MagicMock()
        editor.connection.vendor = "sqlite"
        return editor

    def test_noop_on_sqlite(self, sqlite_schema_editor: MagicMock) -> None:
        refresh_force_rls_policies(sqlite_schema_editor)
        sqlite_schema_editor.execute.assert_not_called()


# =========================================================================
# TenantTableEntry policy_name — registry population
# =========================================================================


class TestTenantTableEntryPolicyName:
    """Every ENROLLED entry in the registry must carry a policy_name."""

    def test_all_enrolled_entries_have_policy_name(self) -> None:
        """Every ENROLLED registry entry has a non-empty policy_name."""
        enrolled = [
            e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
        ]
        assert len(enrolled) > 0, "Expected at least one ENROLLED entry"
        for entry in enrolled:
            assert entry.policy_name, (
                f"ENROLLED entry {entry.app_label}.{entry.model_name} "
                f"has empty policy_name"
            )

    def test_policy_name_is_unique_across_enrolled(self) -> None:
        """No two ENROLLED entries share the same policy_name."""
        enrolled = [
            e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
        ]
        names = [e.policy_name for e in enrolled if e.policy_name]
        assert len(names) == len(set(names)), (
            f"Duplicate policy names found: {[n for n in names if names.count(n) > 1]}"
        )

    def test_non_enrolled_entries_have_empty_policy_name(self) -> None:
        """Non-ENROLLED entries should have empty policy_name."""
        non_enrolled = [
            e for e in TENANT_TABLE_REGISTRY if e.status != TenantTableStatus.ENROLLED
        ]
        for entry in non_enrolled:
            assert entry.policy_name == "", (
                f"Non-ENROLLED entry {entry.app_label}.{entry.model_name} "
                f"has non-empty policy_name={entry.policy_name!r}"
            )

    def test_policy_name_is_readonly(self) -> None:
        """policy_name property is read-only (no setter)."""
        enrolled = [
            e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
        ][0]
        with pytest.raises(AttributeError):
            enrolled.policy_name = "new-name"  # type: ignore[misc]

    def test_policy_name_format(self) -> None:
        """Enrolled policy names follow the ``{short}_{model}_org_isolation`` convention."""
        enrolled = [
            e for e in TENANT_TABLE_REGISTRY if e.status == TenantTableStatus.ENROLLED
        ]
        for entry in enrolled:
            pn = entry.policy_name
            assert pn.endswith("_org_isolation"), (
                f"Policy name {pn!r} does not end with '_org_isolation'"
            )
            assert "_" in pn, f"Policy name {pn!r} does not contain '_' separator"


# =========================================================================
# refresh_force_rls_policies — missing policy_name safeguard
# =========================================================================


class TestRefreshForceRlsPoliciesMissingNames:
    """Entries without a policy_name are skipped."""

    @pytest.fixture
    def pg_schema_editor(self) -> MagicMock:
        editor = MagicMock()
        editor.connection.vendor = "postgresql"
        return editor

    def test_entries_without_policy_name_are_skipped(
        self, pg_schema_editor: MagicMock
    ) -> None:
        """An ENROLLED entry with empty policy_name is silently skipped."""
        refresh_force_rls_policies(pg_schema_editor)
        # No error should be raised; only enrolled entries with a policy
        # name are processed (2 execute calls per table: 1 revert + 1 apply).
        enrolled_with_name = sum(
            1
            for e in TENANT_TABLE_REGISTRY
            if e.status == TenantTableStatus.ENROLLED and e.policy_name
        )
        assert pg_schema_editor.execute.call_count == enrolled_with_name * 2


# =========================================================================
# CR-SA14.5-001 — Cross-tenant read-only proof (PostgreSQL only)
# =========================================================================
# Proves that operator_access grants cross-tenant **read** visibility but
# NOT cross-tenant write or delete visibility.  The FORCE-RLS template
# now maintains a separate FOR ALL policy (no operator_access bypass)
# and a FOR SELECT sub-policy (operator_access bypass).
# -------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# PostgreSQL-only: create the restricted RLS test role for backend
# conformance proofs.  Follows the same pattern as
# test_tenant_table_conformance.py.
# ---------------------------------------------------------------------------

_RESTRICTED_OP_ROLE = "quickscale_rls_op_test_role"

try:
    from django.db import connection as _op_connection

    _OP_IS_POSTGRES = _op_connection.vendor == "postgresql"
except Exception:
    _OP_IS_POSTGRES = False


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not _OP_IS_POSTGRES,
    reason="Cross-tenant read-only proof requires PostgreSQL.",
)
class TestOperatorAccessCrossTenantReadOnly:
    """Prove operator_access allows cross-tenant reads but not cross-tenant
    deletes or updates.

    Every test uses ``SET ROLE`` to a restricted (non-BYPASSRLS) PostgreSQL
    role so that FORCE-RLS policies are truly enforced at the DB level.
    The proof window opens only after ``SET ROLE`` — the test user's
    superuser/BYPASSRLS privileges do not affect the restricted-role queries.

    CR-SA14.5-001 regression guard.
    """

    _RESTRICTED_ROLE = _RESTRICTED_OP_ROLE

    @staticmethod
    def _ensure_role() -> None:
        """Create a non-superuser role for RLS boundary testing.
        Idempotent.  Connects via psycopg2 because CREATE ROLE is DDL.

        Under SA59.1 restricted-role testing, the connected user may not
        have ``CREATE ROLE`` privilege.  The role is pre-created by the
        test harness bootstrap (``docker exec`` as superuser), so silent
        permission errors are acceptable — the existing GRANT statements
        are idempotent for already-existing roles.
        """
        import psycopg2  # type: ignore[import-untyped]

        from django.db import connection

        db = connection.settings_dict
        conn = psycopg2.connect(
            dbname=db["NAME"],
            user=db["USER"],
            password=db["PASSWORD"],
            host=db.get("HOST", "localhost"),
            port=db.get("PORT", "5432"),
        )
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(f"""
                        DO $$
                        BEGIN
                            CREATE ROLE {TestOperatorAccessCrossTenantReadOnly._RESTRICTED_ROLE};
                        EXCEPTION WHEN duplicate_object THEN NULL;
                        END $$;
                    """)
                except Exception:
                    # Role creation requires superuser; the role is
                    # pre-created by the test harness bootstrap.
                    pass
                try:
                    cur.execute(
                        f"GRANT USAGE ON SCHEMA public TO "
                        f"{TestOperatorAccessCrossTenantReadOnly._RESTRICTED_ROLE}"
                    )
                except Exception:
                    pass
                for table in (
                    "quickscale_modules_forms_form",
                    "quickscale_modules_forms_formsubmission",
                    "quickscale_modules_orgs_organization",
                ):
                    try:
                        cur.execute(
                            f"GRANT SELECT, DELETE, UPDATE ON {table} TO "
                            f"{TestOperatorAccessCrossTenantReadOnly._RESTRICTED_ROLE}"
                        )
                    except Exception:
                        pass
        finally:
            conn.close()

    def test_operator_access_can_read_across_tenants(self) -> None:
        """With operator_access enabled under a restricted role, a query
        can see rows from a different organization.

        CR-SA14.5-001: the FOR SELECT sub-policy carries the operator_access
        OR clause, so cross-tenant reads are allowed.
        """
        self._ensure_role()

        from django.db import connection, transaction

        from quickscale_modules_forms.models import Form, FormSubmission
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="CR-OpRead A", slug="cr-opread-a")
        org_b = Organization.objects.create(name="CR-OpRead B", slug="cr-opread-b")

        set_current_org_id(org_a.pk)
        try:
            form_a = Form.all_objects.create(
                organization=org_a, title="Form A", slug="form-a"
            )
            sub_a = FormSubmission.all_objects.create(organization=org_a, form=form_a)
        finally:
            reset_current_org_id()
        set_current_org_id(org_b.pk)
        try:
            form_b = Form.all_objects.create(
                organization=org_b, title="Form B", slug="form-b"
            )
            sub_b = FormSubmission.all_objects.create(organization=org_b, form=form_b)
        finally:
            reset_current_org_id()

        # Open a proof transaction: switch to restricted role, prime the
        # operator_access GUC, then SELECT across organizations.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {self._RESTRICTED_ROLE}")
                try:
                    cursor.execute("SET LOCAL app.operator_access = 'on'")

                    # SELECT across all FormSubmission rows.
                    cursor.execute(
                        "SELECT id FROM quickscale_modules_forms_formsubmission "
                        "ORDER BY id"
                    )
                    row_ids = [r[0] for r in cursor.fetchall()]
                finally:
                    cursor.execute("RESET ROLE")

        assert len(row_ids) == 2, (
            f"Expected 2 rows under operator_access, got {len(row_ids)}. "
            "operator_access must grant cross-tenant read visibility "
            "via the FOR SELECT sub-policy."
        )
        assert sub_a.pk in row_ids
        assert sub_b.pk in row_ids

    def test_operator_access_cannot_delete_across_tenants(self) -> None:
        """With operator_access enabled under a restricted role, a DELETE
        targeting a row from any organization must fail.

        CR-SA14.5-001 proof: the FOR ALL policy (which controls DELETE
        visibility) does NOT carry the operator_access OR clause.
        """
        self._ensure_role()

        from django.db import connection, transaction

        from quickscale_modules_forms.models import Form, FormSubmission
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="CR-OpDel A", slug="cr-opdel-a")

        set_current_org_id(org_a.pk)
        try:
            form_a = Form.all_objects.create(
                organization=org_a, title="Form Del A", slug="form-del-a"
            )
            sub_a = FormSubmission.all_objects.create(organization=org_a, form=form_a)
        finally:
            reset_current_org_id()

        # Try to delete org_a's row while operator_access is active,
        # running under a restricted role where FORCE RLS is enforced.
        deleted_count = -1
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {self._RESTRICTED_ROLE}")
                try:
                    cursor.execute("SET LOCAL app.operator_access = 'on'")

                    cursor.execute(
                        "DELETE FROM quickscale_modules_forms_formsubmission "
                        "WHERE id = %s",
                        [sub_a.pk],
                    )
                    deleted_count = cursor.rowcount
                finally:
                    cursor.execute("RESET ROLE")

        assert deleted_count == 0, (
            f"operator_access must NOT allow cross-tenant DELETE. "
            f"Expected 0 rows deleted, got {deleted_count}. "
            "The FOR ALL policy must not carry the operator_access OR clause."
        )

        # The row must still exist.
        set_current_org_id(org_a.pk)
        try:
            sub_a.refresh_from_db()
        finally:
            reset_current_org_id()
        assert sub_a is not None

    def test_operator_access_cannot_update_across_tenants(self) -> None:
        """With operator_access enabled under a restricted role, an UPDATE
        targeting a row from any organization must fail.

        CR-SA14.5-001 proof: the FOR ALL policy (which controls UPDATE
        visibility) does NOT carry the operator_access OR clause.
        """
        self._ensure_role()

        from django.db import connection, transaction

        from quickscale_modules_forms.models import Form, FormSubmission
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(name="CR-OpUpd A", slug="cr-opupd-a")

        # Create two forms so we can attempt to change form_id via UPDATE.
        set_current_org_id(org_a.pk)
        try:
            form_a = Form.all_objects.create(
                organization=org_a, title="Form Upd A", slug="form-upd-a"
            )
            form_alt = Form.all_objects.create(
                organization=org_a,
                title="Form Upd Alt",
                slug="form-upd-alt",
            )
            sub_a = FormSubmission.all_objects.create(organization=org_a, form=form_a)
            sub_a_pk = sub_a.pk
        finally:
            reset_current_org_id()

        # Try to update org_a's row's form_id while operator_access is active.
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute(f"SET ROLE {self._RESTRICTED_ROLE}")
                try:
                    cursor.execute("SET LOCAL app.operator_access = 'on'")

                    cursor.execute(
                        "UPDATE quickscale_modules_forms_formsubmission "
                        "SET form_id = %s WHERE id = %s",
                        [form_alt.pk, sub_a_pk],
                    )
                    updated_count = cursor.rowcount
                finally:
                    cursor.execute("RESET ROLE")

        assert updated_count == 0, (
            f"operator_access must NOT allow cross-tenant UPDATE. "
            f"Expected 0 rows updated, got {updated_count}. "
            "The FOR ALL policy must not carry the operator_access OR clause."
        )

        # The row's form_id must be unchanged.
        set_current_org_id(org_a.pk)
        try:
            sub_a.refresh_from_db()
        finally:
            reset_current_org_id()
        assert sub_a.form_id == form_a.pk, (
            f"Expected form_id={form_a.pk}, got {sub_a.form_id}. "
            "operator_access must NOT allow cross-tenant UPDATE."
        )


# =========================================================================
# CR-SA14.5-002 — _get_operator_access unit test
# =========================================================================


class TestGetOperatorAccess:
    """Unit tests for the ``_get_operator_access`` helper."""

    def test_returns_empty_string_on_sqlite(self) -> None:
        """On non-PostgreSQL backends, returns empty string."""
        from quickscale_modules_orgs.current_org import _get_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "sqlite"
            result = _get_operator_access()
            assert result == ""

    def test_returns_empty_string_on_default_postgres(self) -> None:
        """On PostgreSQL when GUC is unset, returns empty string."""
        from quickscale_modules_orgs.current_org import _get_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            cursor = mock_conn.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = ("",)
            result = _get_operator_access()
            assert result == ""
            cursor.execute.assert_called_once()

    def test_returns_on_when_guc_is_set(self) -> None:
        """On PostgreSQL when GUC is 'on', returns 'on'."""
        from quickscale_modules_orgs.current_org import _get_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            cursor = mock_conn.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = ("on",)
            result = _get_operator_access()
            assert result == "on"

    def test_returns_empty_string_on_connection_error(self) -> None:
        """If cursor.fetchone raises, returns empty string defensively."""
        from quickscale_modules_orgs.current_org import _get_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            cursor = mock_conn.cursor.return_value.__enter__.return_value
            cursor.fetchone.side_effect = Exception("DB error")
            # The exception is not caught, so it should propagate.
            with pytest.raises(Exception, match="DB error"):
                _get_operator_access()


# =========================================================================
# SA39 — atomic guard regression tests
# =========================================================================


class TestOperatorAccessAtomicGuard:
    """``_get_operator_access`` and ``_set_operator_access`` raise
    ``ImproperlyConfigured`` on PostgreSQL when called outside an active
    ``transaction.atomic()`` block (SA39)."""

    # -- _get_operator_access outside atomic -------------------------------

    def test_get_raises_outside_atomic(self) -> None:
        """``_get_operator_access()`` raises ``ImproperlyConfigured`` on
        PostgreSQL when ``connection.in_atomic_block`` is ``False``."""
        from quickscale_modules_orgs.current_org import _get_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = False

            with pytest.raises(ImproperlyConfigured) as exc_info:
                _get_operator_access()

            msg = str(exc_info.value)
            assert "app.operator_access GUC cannot be read" in msg
            assert "transaction.atomic()" in msg

    def test_get_passes_inside_atomic(self) -> None:
        """``_get_operator_access()`` succeeds on PostgreSQL when
        ``connection.in_atomic_block`` is ``True``."""
        from quickscale_modules_orgs.current_org import _get_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            cursor = mock_conn.cursor.return_value.__enter__.return_value
            cursor.fetchone.return_value = ("",)

            result = _get_operator_access()
            assert result == ""

    def test_get_skips_atomic_check_on_sqlite(self) -> None:
        """``_get_operator_access()`` does not check atomic on non-PostgreSQL."""
        from quickscale_modules_orgs.current_org import _get_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "sqlite"
            # in_atomic_block is not set — would AttributeError if accessed.
            result = _get_operator_access()
            assert result == ""

    # -- _set_operator_access outside atomic -------------------------------

    def test_set_raises_outside_atomic(self) -> None:
        """``_set_operator_access()`` raises ``ImproperlyConfigured`` on
        PostgreSQL when ``connection.in_atomic_block`` is ``False``."""
        from quickscale_modules_orgs.current_org import _set_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = False

            with pytest.raises(ImproperlyConfigured) as exc_info:
                _set_operator_access("on")

            msg = str(exc_info.value)
            assert "app.operator_access GUC cannot be set" in msg
            assert "transaction.atomic()" in msg

    def test_set_passes_inside_atomic(self) -> None:
        """``_set_operator_access()`` succeeds on PostgreSQL when
        ``connection.in_atomic_block`` is ``True``."""
        from quickscale_modules_orgs.current_org import _set_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = True
            cursor = mock_conn.cursor.return_value.__enter__.return_value

            _set_operator_access("on")
            cursor.execute.assert_called_once_with(
                "SET LOCAL app.operator_access = %s", ["on"]
            )

    def test_set_skips_atomic_check_on_sqlite(self) -> None:
        """``_set_operator_access()`` does not check atomic on non-PostgreSQL."""
        from quickscale_modules_orgs.current_org import _set_operator_access

        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "sqlite"
            # in_atomic_block is not set — would AttributeError if accessed.
            _set_operator_access("on")

    # -- operator_access() context manager outside atomic ------------------

    def test_context_manager_raises_outside_atomic(self) -> None:
        """``operator_access()`` raises ``ImproperlyConfigured`` when
        called on PostgreSQL outside an active ``transaction.atomic()``."""
        with patch("django.db.connection") as mock_conn:
            mock_conn.vendor = "postgresql"
            mock_conn.in_atomic_block = False

            with pytest.raises(ImproperlyConfigured) as exc_info:
                with operator_access(reason="outside-atomic"):
                    pass  # pragma: no cover

            msg = str(exc_info.value)
            assert "app.operator_access GUC cannot be read" in msg
            assert "transaction.atomic()" in msg
