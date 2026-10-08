"""Diagnostic: trace SET LOCAL behavior under Django transaction."""

from __future__ import annotations
import pytest
from django.db import connection, transaction


@pytest.mark.django_db(transaction=True)
def test_diag_setlocal():
    if connection.vendor != "postgresql":
        pytest.skip("PostgreSQL required")

    print(f"\nDB name: {connection.settings_dict['NAME']}")
    print(f"in_atomic_block: {connection.in_atomic_block}")

    # Test 1: SET LOCAL in a plain cursor (no explicit atomic)
    print("\n--- Test 1: SET LOCAL in plain cursor (should be inside test atomic) ---")
    with connection.cursor() as c:
        c.execute("SELECT current_setting('app.current_org_id', true)")
        before = c.fetchone()
        print(f"Before SET LOCAL: {before}")

        c.execute(
            "SET LOCAL app.current_org_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'"
        )
        print("SET LOCAL executed without error")

        c.execute("SELECT current_setting('app.current_org_id', true)")
        after = c.fetchone()
        print(f"After SET LOCAL (same cursor): {after}")

    # Test 2: SET LOCAL inside explicit transaction.atomic
    print("\n--- Test 2: SET LOCAL inside explicit transaction.atomic() ---")
    with connection.cursor() as c:
        c.execute("SELECT current_setting('app.current_org_id', true)")
        before = c.fetchone()
        print(f"Before SET LOCAL: {before}")

    with transaction.atomic():
        with connection.cursor() as c:
            c.execute(
                "SET LOCAL app.current_org_id = 'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb'"
            )
            print("SET LOCAL inside atomic executed without error")
            c.execute("SELECT current_setting('app.current_org_id', true)")
            after = c.fetchone()
            print(f"After SET LOCAL (same atomic+cursor): {after}")

    # Test 3: SET LOCAL inside atomic, read on different cursor
    print("\n--- Test 3: SET LOCAL in atomic, read on new cursor in same atomic ---")
    with transaction.atomic():
        with connection.cursor() as c1:
            c1.execute(
                "SET LOCAL app.current_org_id = 'cccccccc-cccc-cccc-cccc-cccccccccccc'"
            )
            print("SET LOCAL inside atomic executed without error")
        with connection.cursor() as c2:
            c2.execute("SELECT current_setting('app.current_org_id', true)")
            after = c2.fetchone()
            print(f"After SET LOCAL (new cursor, same atomic): {after}")

    # Test 4: psycopg2 direct connection with autocommit=False
    print("\n--- Test 4: psycopg2 direct with autocommit=False ---")
    import psycopg2

    db = connection.settings_dict
    conn = psycopg2.connect(
        dbname=db["NAME"],
        user=db["USER"],
        password=db["PASSWORD"],
        host=db.get("HOST", "localhost"),
        port=db.get("PORT", "5432"),
    )
    conn.autocommit = False
    with conn.cursor() as c:
        c.execute(
            "SET LOCAL app.current_org_id = 'dddddddd-dddd-dddd-dddd-dddddddddddd'"
        )
        print("SET LOCAL (raw psycopg2, autocommit=False) executed without error")
        c.execute("SELECT current_setting('app.current_org_id', true)")
        after = c.fetchone()
        print(f"After SET LOCAL (raw psycopg2, autocommit=False): {after}")
    conn.close()
