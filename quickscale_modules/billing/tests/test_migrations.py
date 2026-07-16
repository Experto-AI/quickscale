"""Fresh-0001 contract tests for the Billing final-schema migration.

Phase 3 SA92: verifies the consolidated 0001 migration applies cleanly,
produces the correct final unique constraints, and installs FORCE RLS
on tenant-scoped billing tables (CreditBalance, CreditTransaction,
Subscription) while system-wide tables (Plan, WebhookEvent) do not
receive RLS.
"""

from __future__ import annotations

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor


pytestmark = [
    pytest.mark.bypass_rls,
    pytest.mark.django_db(transaction=True),
]

APP_LABEL = "quickscale_modules_billing"
MIG_0001 = "0001_initial"

# Dependencies for clean migration apply.
ORGS_MIG_LATEST = ("quickscale_modules_orgs", "0001_initial")


# ---------------------------------------------------------------------------
# PostgreSQL expression normalization (CR-SA90-MSQ-003)
# ---------------------------------------------------------------------------


def _normalize_pg_expr(expr: str | None) -> str:
    """Normalize a PostgreSQL expression for exact comparison.

    Normalizes only PostgreSQL syntactic formatting (whitespace,
    case of keywords and unquoted names) while preserving the content
    and case of single-quoted string literals and double-quoted
    identifiers.  Strips balanced outer parentheses that PostgreSQL's
    ``pg_policies`` view wraps around the entire expression.

    CR-SA90-MSQ-003: Both case normalization and whitespace collapse
    are quote-aware — ``.lower()`` and whitespace substitution are only
    applied outside string literals and quoted identifiers so that
    literal content, identifier casing, and whitespace inside quotes
    are preserved exactly.
    """
    if expr is None:
        return ""
    s = expr.strip()
    while len(s) > 1 and s.startswith("(") and s.endswith(")"):
        depth = 0
        outer_balanced = True
        for i, ch in enumerate(s):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            if depth == 0 and i < len(s) - 1:
                outer_balanced = False
                break
        if outer_balanced:
            s = s[1:-1].strip()
        else:
            break
    # Quote-aware lowercasing AND whitespace collapse
    result: list[str] = []
    in_sq = False
    in_dq = False
    for ch in s:
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        if in_sq or in_dq:
            result.append(ch)
        else:
            result.append(ch.lower())
    s = "".join(result)
    # Quote-aware whitespace collapse
    result2: list[str] = []
    in_sq = False
    in_dq = False
    prev_was_space = False
    for ch in s:
        if ch == "'" and not in_dq:
            in_sq = not in_sq
        elif ch == '"' and not in_sq:
            in_dq = not in_dq
        if in_sq or in_dq:
            result2.append(ch)
            prev_was_space = False
        else:
            if ch.isspace():
                if not prev_was_space:
                    result2.append(" ")
                prev_was_space = True
            else:
                result2.append(ch)
                prev_was_space = False
    s = "".join(result2).strip()
    return s


# Expected normalized RLS predicates (same _FORCE_RLS_FORWARD_SQL template)
_EXPECTED_BILLING_FORALL_QUAL = _normalize_pg_expr(
    "((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id)"
)
_EXPECTED_BILLING_FORALL_WC = _EXPECTED_BILLING_FORALL_QUAL
_EXPECTED_BILLING_SELECT_QUAL = _normalize_pg_expr(
    "(((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id) "
    "OR (NULLIF(current_setting('app.operator_access'::text, true), ''::text) = 'on'::text))"
)

# Expected normalized partial-index predicates (from pg_get_expr output).
# Derived from the migration's UniqueConstraint conditions as rendered by
# PostgreSQL 18, normalized for version-robust comparison.
_EXPECTED_PARTIAL_PREDICATES: dict[str, str] = {
    "quickscale_billing_unique_stripe_subscription_id_when_populated": _normalize_pg_expr(
        "(stripe_subscription_id IS NOT NULL) AND (NOT (((stripe_subscription_id)::text = ''::text) AND (stripe_subscription_id IS NOT NULL)))"
    ),
    "quickscale_billing_unique_stripe_checkout_session_id_present": _normalize_pg_expr(
        "(stripe_checkout_session_id IS NOT NULL) AND (NOT (((stripe_checkout_session_id)::text = ''::text) AND (stripe_checkout_session_id IS NOT NULL)))"
    ),
    "quickscale_billing_unique_current_subscription_per_organization": _normalize_pg_expr(
        "((status)::text = ANY ((ARRAY['incomplete'::character varying, 'trialing'::character varying, 'active'::character varying, 'past_due'::character varying, 'unpaid'::character varying, 'paused'::character varying])::text[]))"
    ),
    "quickscale_billing_unique_stripe_event_id_per_type": _normalize_pg_expr(
        "(stripe_event_id IS NOT NULL) AND (NOT ((stripe_event_id)::text = ''::text))"
    ),
}


def test_initial_migration_applies_cleanly() -> None:
    """The consolidated 0001 migration applies cleanly from a fresh state."""
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    applied_migrations = executor.loader.applied_migrations
    billing_migrations = [m for m in applied_migrations if m[0] == APP_LABEL]
    assert billing_migrations, "No billing migrations were applied"


# ---------------------------------------------------------------------------
# Unique constraint proofs — Django Meta.constraints check
# ---------------------------------------------------------------------------


def test_subscription_unique_stripe_subscription_id_constraint() -> None:
    """The ``quickscale_billing_unique_stripe_subscription_id_when_populated``
    partial unique constraint exists on Subscription."""
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    Subscription = apps.get_model(APP_LABEL, "Subscription")
    constraint_names = {c.name for c in Subscription._meta.constraints}

    assert (
        "quickscale_billing_unique_stripe_subscription_id_when_populated"
        in constraint_names
    ), (
        "Missing partial unique constraint "
        "quickscale_billing_unique_stripe_subscription_id_when_populated on Subscription"
    )


def test_subscription_unique_checkout_session_id_constraint() -> None:
    """The ``quickscale_billing_unique_stripe_checkout_session_id_present``
    partial unique constraint exists on Subscription."""
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    Subscription = apps.get_model(APP_LABEL, "Subscription")
    constraint_names = {c.name for c in Subscription._meta.constraints}

    assert (
        "quickscale_billing_unique_stripe_checkout_session_id_present"
        in constraint_names
    ), (
        "Missing partial unique constraint "
        "quickscale_billing_unique_stripe_checkout_session_id_present on Subscription"
    )


def test_subscription_unique_current_per_org_constraint() -> None:
    """The ``quickscale_billing_unique_current_subscription_per_organization``
    partial unique constraint exists on Subscription."""
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    Subscription = apps.get_model(APP_LABEL, "Subscription")
    constraint_names = {c.name for c in Subscription._meta.constraints}

    assert (
        "quickscale_billing_unique_current_subscription_per_organization"
        in constraint_names
    ), (
        "Missing partial unique constraint "
        "quickscale_billing_unique_current_subscription_per_organization on Subscription"
    )


def test_credittransaction_unique_stripe_event_per_type_constraint() -> None:
    """The ``quickscale_billing_unique_stripe_event_id_per_type`` partial
    unique constraint exists on CreditTransaction."""
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    CreditTransaction = apps.get_model(APP_LABEL, "CreditTransaction")
    constraint_names = {c.name for c in CreditTransaction._meta.constraints}

    assert "quickscale_billing_unique_stripe_event_id_per_type" in constraint_names, (
        "Missing partial unique constraint "
        "quickscale_billing_unique_stripe_event_id_per_type on CreditTransaction"
    )


def test_webhookevent_unique_stripe_event_id_constraint() -> None:
    """The ``quickscale_billing_unique_stripe_event_id`` unique constraint
    exists on WebhookEvent."""
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    apps = executor.loader.project_state([(APP_LABEL, MIG_0001)]).apps
    WebhookEvent = apps.get_model(APP_LABEL, "WebhookEvent")
    constraint_names = {c.name for c in WebhookEvent._meta.constraints}

    assert "quickscale_billing_unique_stripe_event_id" in constraint_names, (
        "Missing unique constraint "
        "quickscale_billing_unique_stripe_event_id on WebhookEvent"
    )


# ---------------------------------------------------------------------------
# FORCE RLS proofs — PostgreSQL pg_policy catalog check
# ---------------------------------------------------------------------------

try:
    from django.db import connection as _billing_dj_connection

    _BILLING_IS_POSTGRES = _billing_dj_connection.vendor == "postgresql"
except Exception:
    _BILLING_IS_POSTGRES = False


@pytest.mark.skipif(
    not _BILLING_IS_POSTGRES,
    reason="RLS policy check requires PostgreSQL.",
)
def test_force_rls_installed_on_tenant_scoped_billing_tables() -> None:
    """FORCE RLS policies exist for tenant-scoped billing tables only.

    CreditBalance, CreditTransaction, and Subscription receive FORCE RLS.
    Plan and WebhookEvent (system-wide) do not.
    """
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    expected_policies = {
        (
            "quickscale_modules_billing_creditbalance",
            "billing_credit_balance_org_isolation",
        ),
        (
            "quickscale_modules_billing_credittransaction",
            "billing_credit_transaction_org_isolation",
        ),
        (
            "quickscale_modules_billing_subscription",
            "billing_subscription_org_isolation",
        ),
    }

    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT c.relname, pc.polname
            FROM pg_policy pc
            JOIN pg_class c ON c.oid = pc.polrelid
            WHERE c.relname LIKE 'quickscale_modules_billing_%'
            """,
        )
        found_policies = set(cursor.fetchall())

    for table, policy in expected_policies:
        assert (table, policy) in found_policies, (
            f"FORCE RLS policy '{policy}' on {table} not found."
        )
        # Verify _select policy exists (SA14.5 operator_access OR clause)
        assert (table, f"{policy}_select") in found_policies, (
            f"FORCE RLS SELECT policy '{policy}_select' on {table} not found."
        )

    # Verify Plan and WebhookEvent do NOT have RLS policies.
    tables_without_rls = (
        "quickscale_modules_billing_plan",
        "quickscale_modules_billing_webhookevent",
    )
    for table in tables_without_rls:
        policies_on_table = {(t, p) for (t, p) in found_policies if t == table}
        assert len(policies_on_table) == 0, (
            f"System-wide table {table} has unexpected RLS policies: {policies_on_table}"
        )


@pytest.mark.skipif(
    not _BILLING_IS_POSTGRES,
    reason="Physical partial constraint check requires PostgreSQL.",
)
def test_billing_partial_unique_constraints_have_correct_predicates() -> None:
    """Physical partial unique constraints have the correct ``WHERE``
    predicates.

    CR-SA90-MSQ-003: Uses exact normalized comparison via
    ``pg_get_expr``, not permissive fragment matching.
    """
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    with connection.cursor() as cursor:
        for (
            constraint_name,
            expected_normalized,
        ) in _EXPECTED_PARTIAL_PREDICATES.items():
            cursor.execute(
                """
                SELECT pg_get_expr(i.indpred, i.indrelid) AS predicate
                FROM pg_index i
                JOIN pg_class c ON c.oid = i.indexrelid
                WHERE c.relname = %s
                """,
                [constraint_name],
            )
            row = cursor.fetchone()
            assert row is not None, (
                f"Partial unique index {constraint_name} not found in pg_index"
            )
            actual_normalized = _normalize_pg_expr(row[0])
            assert actual_normalized == expected_normalized, (
                f"Index {constraint_name} predicate mismatch.\n"
                f"  Actual normalized:   {actual_normalized!r}\n"
                f"  Expected normalized: {expected_normalized!r}"
            )


# ---------------------------------------------------------------------------
# Allowed / forbidden uniqueness behavior proofs
# ---------------------------------------------------------------------------


@pytest.mark.django_db(transaction=True)
@pytest.mark.skipif(
    not _BILLING_IS_POSTGRES,
    reason="Uniqueness behavior proof requires PostgreSQL enforcement.",
)
class TestBillingPartialUniqueBehavior:
    """Prove partial unique constraints allow NULL rows but reject
    duplicates on non-NULL values."""

    def test_stripe_subscription_id_allows_duplicate_nulls(self) -> None:
        """Multiple Subscription rows with NULL stripe_subscription_id
        are allowed (partial index excludes NULLs)."""
        from quickscale_modules_billing.models import Plan, Subscription
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org_a = Organization.objects.create(
            name="Billing Test Org A", slug="billing-test-a"
        )
        org_b = Organization.objects.create(
            name="Billing Test Org B", slug="billing-test-b"
        )
        plan = Plan.objects.create(
            name="Test Plan",
            slug="test-plan",
            stripe_price_id="price_test",
            credits_per_period=0,
            price_cents=0,
        )

        with org_scope(org_a):
            sub1 = Subscription.objects.create(
                organization=org_a,
                plan=plan,
                stripe_subscription_id=None,
            )
        with org_scope(org_b):
            sub2 = Subscription.objects.create(
                organization=org_b,
                plan=plan,
                stripe_subscription_id=None,
            )
        assert sub1.pk != sub2.pk, (
            "Two Subscriptions with NULL stripe_subscription_id should both succeed"
        )

    def test_stripe_subscription_id_rejects_non_null_duplicates(self) -> None:
        """Duplicate non-NULL stripe_subscription_id values are rejected."""
        import django.db.utils

        from django.db import transaction

        from quickscale_modules_billing.models import Plan, Subscription
        from quickscale_modules_orgs.current_org import org_scope
        from quickscale_modules_orgs.models import Organization

        org = Organization.objects.create(
            name="Billing Test Org 2", slug="billing-test-2"
        )
        plan = Plan.objects.create(
            name="Test Plan 2",
            slug="test-plan-2",
            stripe_price_id="price_test_2",
            credits_per_period=0,
            price_cents=0,
        )

        with org_scope(org):
            Subscription.objects.create(
                organization=org,
                plan=plan,
                stripe_subscription_id="sub_unique_test",
            )
            # Wrap the duplicate insert in a sub-transaction so the
            # integrity error doesn't break the org_scope block.
            with transaction.atomic():
                with pytest.raises(django.db.utils.IntegrityError):
                    Subscription.objects.create(
                        organization=org,
                        plan=plan,
                        stripe_subscription_id="sub_unique_test",
                    )


@pytest.mark.skipif(
    not _BILLING_IS_POSTGRES,
    reason="RLS table-level check requires PostgreSQL.",
)
def test_billing_tenant_tables_have_force_rls_enabled() -> None:
    """Billing tenant-scoped tables have ``relrowsecurity`` AND
    ``relforcerowsecurity`` in ``pg_class`` while system-wide tables
    do not."""
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    tenant_tables = [
        "quickscale_modules_billing_creditbalance",
        "quickscale_modules_billing_credittransaction",
        "quickscale_modules_billing_subscription",
    ]
    system_tables = [
        "quickscale_modules_billing_plan",
        "quickscale_modules_billing_webhookevent",
    ]

    with connection.cursor() as cursor:
        for table in tenant_tables:
            cursor.execute(
                """
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = %s
                """,
                [table],
            )
            row = cursor.fetchone()
            assert row is not None, f"Table {table} not found in pg_class"
            relrowsecurity, relforcerowsecurity = row
            assert relrowsecurity is True, (
                f"Tenant table {table} has relrowsecurity={relrowsecurity}, "
                f"expected True"
            )
            assert relforcerowsecurity is True, (
                f"Tenant table {table} has relforcerowsecurity={relforcerowsecurity}, "
                f"expected True"
            )

        for table in system_tables:
            cursor.execute(
                """
                SELECT relrowsecurity, relforcerowsecurity
                FROM pg_class
                WHERE relname = %s
                """,
                [table],
            )
            row = cursor.fetchone()
            assert row is not None, f"Table {table} not found in pg_class"
            relrowsecurity, relforcerowsecurity = row
            # System-wide tables should NOT have RLS enabled
            assert relrowsecurity is False, (
                f"System table {table} has relrowsecurity={relrowsecurity}, "
                f"expected False"
            )
            assert relforcerowsecurity is False, (
                f"System table {table} has relforcerowsecurity={relforcerowsecurity}, "
                f"expected False"
            )


@pytest.mark.skipif(
    not _BILLING_IS_POSTGRES,
    reason="Policy predicate check requires PostgreSQL.",
)
def test_billing_rls_policy_has_org_predicate() -> None:
    """Billing tenant-scoped RLS policies have correct predicates.

    The FOR ALL policy must reference current_setting or organization_id
    in both USING and WITH CHECK.  The _select policy must have an
    operator_access OR clause.

    CR-SA90-MSQ-003: Exact normalized predicate comparison — the
    normalized form must match the expected canonical expression from
    ``_FORCE_RLS_FORWARD_SQL``, not merely contain permissive fragments.
    """
    executor = MigrationExecutor(connection)
    executor.migrate([ORGS_MIG_LATEST, (APP_LABEL, MIG_0001)])

    tables = [
        "quickscale_modules_billing_creditbalance",
        "quickscale_modules_billing_credittransaction",
        "quickscale_modules_billing_subscription",
    ]

    with connection.cursor() as cursor:
        for table in tables:
            cursor.execute(
                "SELECT policyname, cmd, qual, with_check "
                "FROM pg_policies "
                "WHERE tablename = %s "
                "ORDER BY policyname",
                [table],
            )
            policies = cursor.fetchall()
            assert len(policies) == 2, (
                f"Expected 2 policies on {table}, got {len(policies)}"
            )

            forall = [p for p in policies if not p[0].endswith("_select")]
            select_pol = [p for p in policies if p[0].endswith("_select")]
            assert len(forall) == 1, f"Expected 1 FOR ALL on {table}"
            assert len(select_pol) == 1, f"Expected 1 _select on {table}"

            polname, cmd, qual, with_check = forall[0]
            assert cmd in ("ALL", "*"), f"FOR ALL {polname} cmd={cmd!r}"
            assert qual is not None, f"FOR ALL {polname} has NULL USING"
            assert (
                "current_setting" in qual.lower() or "organization_id" in qual.lower()
            ), f"FOR ALL {polname} USING lacks current_setting/org_id: {qual}"
            assert with_check is not None, f"FOR ALL {polname} has NULL WITH CHECK"
            assert (
                "current_setting" in with_check.lower()
                or "organization_id" in with_check.lower()
            ), (
                f"FOR ALL {polname} WITH CHECK lacks current_setting/org_id: {with_check}"
            )
            # CR-SA90-MSQ-003: exact normalized predicate comparison
            nqual = _normalize_pg_expr(qual)
            assert nqual == _EXPECTED_BILLING_FORALL_QUAL, (
                f"{table}/{polname} normalized qual {nqual!r} "
                f"does not match expected {_EXPECTED_BILLING_FORALL_QUAL!r}"
            )
            nwc = _normalize_pg_expr(with_check)
            assert nwc == _EXPECTED_BILLING_FORALL_WC, (
                f"{table}/{polname} normalized with_check {nwc!r} "
                f"does not match expected {_EXPECTED_BILLING_FORALL_WC!r}"
            )

            sname, scmd, squal, swc = select_pol[0]
            assert scmd in ("SELECT", "s"), f"SELECT {sname} cmd={scmd!r}"
            assert swc is None, f"SELECT {sname} has unexpected WITH CHECK"
            # CR-SA90-MSQ-003: assert squal is not None BEFORE comparison
            # so NULL predicates cannot silently pass exact-match checks.
            assert squal is not None, (
                f"SELECT {sname} has NULL USING — must have a predicate"
            )
            assert "operator_access" in squal.lower(), (
                f"SELECT {sname} USING lacks operator_access: {squal}"
            )
            # CR-SA90-MSQ-003: exact normalized predicate comparison
            nsqual = _normalize_pg_expr(squal)
            assert nsqual == _EXPECTED_BILLING_SELECT_QUAL, (
                f"{table}/{sname} normalized SELECT qual {nsqual!r} "
                f"does not match expected {_EXPECTED_BILLING_SELECT_QUAL!r}"
            )

        # System tables must have no policies at all
        for table in (
            "quickscale_modules_billing_plan",
            "quickscale_modules_billing_webhookevent",
        ):
            cursor.execute(
                "SELECT COUNT(*) FROM pg_policies WHERE tablename = %s",
                [table],
            )
            count = cursor.fetchone()[0]
            assert count == 0, (
                f"System table {table} has {count} policies; expected none"
            )


# ---------------------------------------------------------------------------
# CR-SA90-MSQ-003: negative controls for _normalize_pg_expr
# ---------------------------------------------------------------------------


def test_billing_normalize_pg_expr_null_qual() -> None:
    """NULL input normalizes to empty string."""
    assert _normalize_pg_expr(None) == "", "NULL qual should normalize to ''"


def test_billing_normalize_pg_expr_extra_clause_detected() -> None:
    """Tampered predicate with extra clause must NOT match canonical."""
    tampered = (
        "((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id "
        "AND extra_condition = true)"
    )
    n = _normalize_pg_expr(tampered)
    assert n != _EXPECTED_BILLING_FORALL_QUAL, (
        "Extra clause should produce a different normalized form"
    )


def test_billing_normalize_pg_expr_literal_case_preserved() -> None:
    """Changing literal case must NOT match the canonical form."""
    n_modified = _normalize_pg_expr(
        "(((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = organization_id) "
        "OR (NULLIF(current_setting('app.operator_access'::text, true), ''::text) = 'ON'::text))"
    )
    assert n_modified != _EXPECTED_BILLING_SELECT_QUAL, (
        "Uppercase literal should produce different normalized form"
    )


def test_billing_normalize_pg_expr_identifier_case_preserved() -> None:
    """A double-quoted identifier with mixed case must be preserved."""
    n = _normalize_pg_expr(
        "((NULLIF(current_setting('app.current_org_id'::text, true), ''::text))::uuid = \"Organization_Id\")"
    )
    assert '"organization_id"' not in n, (
        "Double-quoted 'Organization_Id' should NOT be lowercased by normalizer"
    )


def test_billing_normalize_pg_expr_whitespace_in_quotes_preserved() -> None:
    """Extra whitespace inside a single-quoted literal must NOT be
    collapsed, producing a different normalized form."""
    with_extra_space = (
        "((NULLIF(current_setting('app.current_org_id'::text, true), "
        "' '::text))::uuid = organization_id)"
    )
    n = _normalize_pg_expr(with_extra_space)
    assert n != _EXPECTED_BILLING_FORALL_QUAL, (
        "Whitespace inside a quoted literal must produce a different normalized form"
    )


def test_billing_normalize_pg_expr_parentheses_in_quotes_preserved() -> None:
    """Extra parentheses inside a single-quoted literal must NOT be
    stripped or altered by the normalizer."""
    with_paren_in_literal = (
        "((NULLIF(current_setting('app.current_org_id'::text, true), "
        "'(default)'::text))::uuid = organization_id)"
    )
    n = _normalize_pg_expr(with_paren_in_literal)
    assert n != _EXPECTED_BILLING_FORALL_QUAL, (
        "Parentheses inside a quoted literal must produce a different normalized form"
    )


def test_billing_partial_predicate_altered_status_set() -> None:
    """An altered status ARRAY in the current-subscription partial
    predicate must NOT match the expected canonical form."""
    # Snapshot constraint name so we know which expected value to tamper.
    status_constraint = (
        "quickscale_billing_unique_current_subscription_per_organization"
    )
    expected = _EXPECTED_PARTIAL_PREDICATES[status_constraint]

    # Tamper: remove 'paused' and add 'expired'
    tampered_sql = (
        "((status)::text = ANY "
        "((ARRAY['incomplete'::character varying, 'trialing'::character varying, "
        "'active'::character varying, 'past_due'::character varying, "
        "'unpaid'::character varying, 'expired'::character varying])::text[]))"
    )
    n_tampered = _normalize_pg_expr(tampered_sql)
    assert n_tampered != expected, (
        "Altered status set (removed paused, added expired) must NOT match "
        "the expected canonical predicate"
    )


def test_billing_partial_predicate_extra_status() -> None:
    """Adding an extra status to the ARRAY must NOT match the canonical."""
    status_constraint = (
        "quickscale_billing_unique_current_subscription_per_organization"
    )
    expected = _EXPECTED_PARTIAL_PREDICATES[status_constraint]

    tampered_sql = (
        "((status)::text = ANY "
        "((ARRAY['incomplete'::character varying, 'trialing'::character varying, "
        "'active'::character varying, 'past_due'::character varying, "
        "'unpaid'::character varying, 'paused'::character varying, "
        "'expired'::character varying])::text[]))"
    )
    n_tampered = _normalize_pg_expr(tampered_sql)
    assert n_tampered != expected, (
        "Extra status in ARRAY must NOT match the expected canonical predicate"
    )
