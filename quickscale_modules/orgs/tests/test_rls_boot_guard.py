"""SA68 Phase 1 — RLS boot guard unit tests.

Tests for ``quickscale_modules_orgs.apps._check_rls_role`` — the
standalone function called by ``QuickscaleOrgsConfig.ready()`` that
raises ``ImproperlyConfigured`` when the connected PostgreSQL role has
BYPASSRLS or SUPERUSER (either alone suffices to fail the guard).

The guard is always active (regardless of ``QUICKSCALE_MODE`` or
``DEBUG``) with two narrow exemptions:

1. ``QUICKSCALE_PRIVILEGED_COMMAND`` set to a sanctioned privileged
   DB command (``migrate``, ``createcachetable``) — ``start.sh`` sets
   this env var alongside ``RUNTIME_DATABASE_URL=""`` so DDL/DML runs
   under the superuser ``DATABASE_URL``.
2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
   intentional single-tenant or development use.

The sanctioned command set is defined by ``_PRIVILEGED_COMMANDS`` and
checked via ``_is_privileged_command()`` (formerly ``_is_migrate_command()``,
widened in CR-SA68-001).

``manage.py runserver``, gunicorn, and WSGI startup must all still
fail closed under BYPASSRLS or SUPERUSER.  The old ``sys.argv``-based
``_is_migrate_command`` has been replaced by the explicit env-var
contract (SA68 Phase 1).
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured

import quickscale_modules_orgs
from quickscale_modules_orgs.apps import (
    QuickscaleOrgsConfig,
    _check_rls_role,
    _is_privileged_command,
)


@pytest.fixture(autouse=True)
def _clear_escape_hatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the SA2.1 escape hatch before each test.

    The env var is a shell-level opt-in (set before running
    pytest — no module test code primes it).  This autouse
    fixture clears it before every test so that tests
    exercising the guard (expecting ``ImproperlyConfigured``)
    work correctly without the env var interfering.
    """
    monkeypatch.delenv("QUICKSCALE_ALLOW_BYPASSRLS", raising=False)


def _mock_postgres_connection(rolbypassrls: bool, rolsuper: bool = False) -> MagicMock:
    """Build a mock ``connection`` object for a PostgreSQL backend.

    ``rolbypassrls`` and ``rolsuper`` control the values returned by
    the ``pg_roles`` query.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (rolbypassrls, rolsuper)

    mock_conn = MagicMock()
    mock_conn.vendor = "postgresql"
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
    return mock_conn


# ---------------------------------------------------------------------------
# Raise: saas + DEBUG=False + PostgreSQL + rolbypassrls = true
# ---------------------------------------------------------------------------


def test_rls_guard_raises_for_bypassrls_role(settings: Any) -> None:
    """Saas + DEBUG=False + PostgreSQL + BYPASSRLS role raises."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            _check_rls_role()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Pass: saas + DEBUG=False + PostgreSQL + rolbypassrls = false
# ---------------------------------------------------------------------------


def test_rls_guard_passes_for_nobypassrls_role(settings: Any) -> None:
    """Saas + DEBUG=False + PostgreSQL + NOBYPASSRLS role passes."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=False)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        _check_rls_role()  # must not raise


# ---------------------------------------------------------------------------
# Raise: SA58 — rolsuper=True + rolbypassrls=False also raises
# ---------------------------------------------------------------------------


def test_rls_guard_raises_for_superuser_role(settings: Any) -> None:
    """SUPERUSER role without BYPASSRLS must also raise."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=False, rolsuper=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            _check_rls_role()

    assert "SUPERUSER" in str(exc_info.value)
    assert "NOSUPERUSER" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Raise: solo mode (SA2.1 — always-on, no longer exempt)
# ---------------------------------------------------------------------------


def test_rls_guard_raises_in_solo_mode(settings: Any) -> None:
    """Solo mode must now raise with a BYPASSRLS role."""
    settings.QUICKSCALE_MODE = "solo"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            _check_rls_role()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Raise: DEBUG=True (SA2.1 — always-on, no longer exempt)
# ---------------------------------------------------------------------------


def test_rls_guard_raises_when_debug_true(settings: Any) -> None:
    """DEBUG=True must now raise with a BYPASSRLS role."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = True

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            _check_rls_role()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# No-op: non-PostgreSQL vendor (SQLite, etc.)
# ---------------------------------------------------------------------------


def test_rls_guard_noop_on_sqlite(settings: Any) -> None:
    """Non-PostgreSQL vendor must skip the check entirely."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = MagicMock()
    mock_conn.vendor = "sqlite"

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        _check_rls_role()  # must not raise


# ---------------------------------------------------------------------------
# SA2.1 — Escape hatch: QUICKSCALE_ALLOW_BYPASSRLS=1
# ---------------------------------------------------------------------------


def test_rls_guard_escape_hatch_bypasses_in_saas_prod(settings: Any) -> None:
    """Escape hatch ``QUICKSCALE_ALLOW_BYPASSRLS=1`` bypasses the guard."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            _check_rls_role()  # must not raise


def test_rls_guard_escape_hatch_bypasses_in_solo(settings: Any) -> None:
    """Escape hatch also bypasses in solo mode."""
    settings.QUICKSCALE_MODE = "solo"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            _check_rls_role()  # must not raise


def test_rls_guard_escape_hatch_bypasses_with_debug(settings: Any) -> None:
    """Escape hatch also bypasses when DEBUG=True."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = True

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            _check_rls_role()  # must not raise


def test_rls_guard_escape_hatch_exact_value(settings: Any) -> None:
    """Only the exact value ``\"1\"`` triggers the escape hatch."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    # Value "0" must NOT bypass
    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "0"}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                _check_rls_role()

    assert "BYPASSRLS" in str(exc_info.value)


def test_rls_guard_escape_hatch_empty_value_does_not_bypass(settings: Any) -> None:
    """Empty string must NOT bypass the guard."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": ""}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            with pytest.raises(ImproperlyConfigured) as exc_info:
                _check_rls_role()

    assert "BYPASSRLS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Raise: unset QUICKSCALE_MODE (SA2.1 — always-on, no longer exempt)
# ---------------------------------------------------------------------------


def test_rls_guard_raises_when_mode_unset(settings: Any) -> None:
    """Unset QUICKSCALE_MODE must now raise with a BYPASSRLS role."""
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            _check_rls_role()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# _is_privileged_command: sanctioned QUICKSCALE_PRIVILEGED_COMMAND values
# are exempt; unrecognised, empty, and non-DB vars are not
# ---------------------------------------------------------------------------


def test_is_privileged_command_true_for_migrate() -> None:
    """``QUICKSCALE_PRIVILEGED_COMMAND=migrate`` is a sanctioned value."""
    with patch.dict(
        os.environ,
        {"QUICKSCALE_PRIVILEGED_COMMAND": "migrate"},
        clear=True,
    ):
        assert _is_privileged_command() is True


def test_is_privileged_command_true_for_createcachetable() -> None:
    """``QUICKSCALE_PRIVILEGED_COMMAND=createcachetable`` is now sanctioned
    (CR-SA68-001)."""
    with patch.dict(
        os.environ,
        {"QUICKSCALE_PRIVILEGED_COMMAND": "createcachetable"},
        clear=True,
    ):
        assert _is_privileged_command() is True


def test_is_privileged_command_false_when_privileged_command_unset() -> None:
    """No env var set must NOT be detected — still catastrophic."""
    with patch.dict(os.environ, {}, clear=True):
        assert _is_privileged_command() is False


def test_is_privileged_command_false_for_non_db_command() -> None:
    """Non-DB command env vars must NOT be exempt."""
    with patch.dict(
        os.environ,
        {"QUICKSCALE_NON_DB_COMMAND": "collectstatic"},
        clear=True,
    ):
        assert _is_privileged_command() is False


def test_is_privileged_command_false_for_empty_privileged_command() -> None:
    """Empty string value must NOT be exempt."""
    with patch.dict(
        os.environ,
        {"QUICKSCALE_PRIVILEGED_COMMAND": ""},
        clear=True,
    ):
        assert _is_privileged_command() is False


def test_is_privileged_command_false_for_unrecognised_value() -> None:
    """Unrecognised ``QUICKSCALE_PRIVILEGED_COMMAND`` values must NOT be
    exempt — the set is not a catch-all escape hatch."""
    with patch.dict(
        os.environ,
        {"QUICKSCALE_PRIVILEGED_COMMAND": "unknown_value"},
        clear=True,
    ):
        assert _is_privileged_command() is False


# ---------------------------------------------------------------------------
# ready() lifecycle seam: sanctioned QUICKSCALE_PRIVILEGED_COMMAND values
# are exempt; all other commands fail-closed
# ---------------------------------------------------------------------------


def test_ready_skips_check_for_migration_command(settings: Any) -> None:
    """``ready()`` must NOT raise for ``QUICKSCALE_PRIVILEGED_COMMAND=migrate``
    even with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch.dict(
            os.environ,
            {"QUICKSCALE_PRIVILEGED_COMMAND": "migrate"},
            clear=True,
        ):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            config.ready()  # must not raise


def test_ready_skips_check_for_createcachetable_command(settings: Any) -> None:
    """``ready()`` must NOT raise for
    ``QUICKSCALE_PRIVILEGED_COMMAND=createcachetable`` even with BYPASSRLS
    (CR-SA68-001)."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch.dict(
            os.environ,
            {"QUICKSCALE_PRIVILEGED_COMMAND": "createcachetable"},
            clear=True,
        ):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            config.ready()  # must not raise


def test_ready_raises_for_runserver_command(settings: Any) -> None:
    """``ready()`` MUST raise for ``manage.py runserver`` with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch.dict(os.environ, {}, clear=True):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            with pytest.raises(ImproperlyConfigured) as exc_info:
                config.ready()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


def test_ready_raises_for_collectstatic_command(settings: Any) -> None:
    """``ready()`` MUST raise for non-DB management commands with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch.dict(os.environ, {}, clear=True):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            with pytest.raises(ImproperlyConfigured) as exc_info:
                config.ready()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


def test_ready_raises_for_gunicorn_startup(settings: Any) -> None:
    """``ready()`` must STILL raise for gunicorn WSGI startup with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch.dict(os.environ, {}, clear=True):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            with pytest.raises(ImproperlyConfigured) as exc_info:
                config.ready()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Edge case: fetchone returns None (defensive)
# ---------------------------------------------------------------------------


def test_rls_guard_noop_when_query_returns_none(settings: Any) -> None:
    """Defensive: no rows returned should not raise."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = None

    mock_conn = MagicMock()
    mock_conn.vendor = "postgresql"
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        _check_rls_role()  # must not raise
