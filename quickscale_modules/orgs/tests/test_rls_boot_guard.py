"""T1.18 / SA2.1 — RLS boot guard unit tests.

Tests for ``quickscale_modules_orgs.apps._check_rls_role`` — the
standalone function called by ``QuickscaleOrgsConfig.ready()`` that
raises ``ImproperlyConfigured`` when the connected PostgreSQL role has
BYPASSRLS.

The guard is always active (regardless of ``QUICKSCALE_MODE`` or
``DEBUG``) with two narrow exemptions:

1. ``manage.py migrate`` — ``start.sh`` deliberately unsets
   ``RUNTIME_DATABASE_URL`` so DDL runs under the superuser
   ``DATABASE_URL``.
2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` env-var escape hatch — for
   intentional single-tenant or development use.

``manage.py runserver``, gunicorn, and WSGI startup must all still
fail closed under BYPASSRLS.
"""

from __future__ import annotations

import os
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured

import quickscale_modules_orgs

from quickscale_modules_orgs.apps import (
    QuickscaleOrgsConfig,
    _check_rls_role,
    _is_migrate_command,
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


def _mock_postgres_connection(rolbypassrls: bool) -> MagicMock:
    """Build a mock ``connection`` object for a PostgreSQL backend.

    ``rolbypassrls`` controls the value returned by the pg_roles query.
    """
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (rolbypassrls,)

    mock_conn = MagicMock()
    mock_conn.vendor = "postgresql"
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor
    mock_conn.cursor.return_value.__exit__ = MagicMock(return_value=None)
    return mock_conn


# ---------------------------------------------------------------------------
# Raise: saas + DEBUG=False + PostgreSQL + rolbypassrls = true
# ---------------------------------------------------------------------------


def test_rls_guard_raises_for_bypassrls_role(settings) -> None:
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


def test_rls_guard_passes_for_nobypassrls_role(settings) -> None:
    """Saas + DEBUG=False + PostgreSQL + NOBYPASSRLS role passes."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=False)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        _check_rls_role()  # must not raise


# ---------------------------------------------------------------------------
# Raise: solo mode (SA2.1 — always-on, no longer exempt)
# ---------------------------------------------------------------------------


def test_rls_guard_raises_in_solo_mode(settings) -> None:
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


def test_rls_guard_raises_when_debug_true(settings) -> None:
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


def test_rls_guard_noop_on_sqlite(settings) -> None:
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


def test_rls_guard_escape_hatch_bypasses_in_saas_prod(settings) -> None:
    """Escape hatch ``QUICKSCALE_ALLOW_BYPASSRLS=1`` bypasses the guard."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            _check_rls_role()  # must not raise


def test_rls_guard_escape_hatch_bypasses_in_solo(settings) -> None:
    """Escape hatch also bypasses in solo mode."""
    settings.QUICKSCALE_MODE = "solo"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            _check_rls_role()  # must not raise


def test_rls_guard_escape_hatch_bypasses_with_debug(settings) -> None:
    """Escape hatch also bypasses when DEBUG=True."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = True

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.apps.connection", mock_conn):
            _check_rls_role()  # must not raise


def test_rls_guard_escape_hatch_exact_value(settings) -> None:
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


def test_rls_guard_escape_hatch_empty_value_does_not_bypass(settings) -> None:
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


def test_rls_guard_raises_when_mode_unset(settings) -> None:
    """Unset QUICKSCALE_MODE must now raise with a BYPASSRLS role."""
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with pytest.raises(ImproperlyConfigured) as exc_info:
            _check_rls_role()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


# ---------------------------------------------------------------------------
# _is_migrate_command: only manage.py migrate is exempt
# ---------------------------------------------------------------------------


def test_is_migrate_command_true_for_migrate() -> None:
    """``manage.py migrate`` is detected as the exempt command."""
    with patch("quickscale_modules_orgs.apps.sys.argv", ["manage.py", "migrate"]):
        assert _is_migrate_command() is True


def test_is_migrate_command_true_for_migrate_with_flags() -> None:
    """``manage.py migrate --noinput`` is also detected."""
    with patch(
        "quickscale_modules_orgs.apps.sys.argv",
        ["manage.py", "migrate", "--noinput"],
    ):
        assert _is_migrate_command() is True


def test_is_migrate_command_false_for_runserver() -> None:
    """``manage.py runserver`` must NOT be detected — still catastrophic."""
    with patch("quickscale_modules_orgs.apps.sys.argv", ["manage.py", "runserver"]):
        assert _is_migrate_command() is False


def test_is_migrate_command_false_for_other_management_commands() -> None:
    """Other management commands (collectstatic, shell, etc.) must NOT be exempt."""
    with patch(
        "quickscale_modules_orgs.apps.sys.argv",
        ["manage.py", "collectstatic", "--noinput"],
    ):
        assert _is_migrate_command() is False


def test_is_migrate_command_false_for_gunicorn() -> None:
    """Gunicorn WSGI startup is NOT a management command."""
    with patch(
        "quickscale_modules_orgs.apps.sys.argv",
        ["/usr/local/bin/gunicorn", "myapp.wsgi:application"],
    ):
        assert _is_migrate_command() is False


def test_is_migrate_command_false_for_bare_python() -> None:
    """Bare python invocation (no argv command) is not a management command."""
    with patch("quickscale_modules_orgs.apps.sys.argv", ["script.py"]):
        assert _is_migrate_command() is False


# ---------------------------------------------------------------------------
# ready() lifecycle seam: only migrate exempt; runserver + gunicorn fail-closed
# ---------------------------------------------------------------------------


def test_ready_skips_check_for_migration_command(settings) -> None:
    """``ready()`` must NOT raise for ``manage.py migrate`` even with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch(
            "quickscale_modules_orgs.apps.sys.argv",
            ["manage.py", "migrate", "--noinput"],
        ):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            config.ready()  # must not raise


def test_ready_raises_for_runserver_command(settings) -> None:
    """``ready()`` MUST raise for ``manage.py runserver`` with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch(
            "quickscale_modules_orgs.apps.sys.argv",
            ["manage.py", "runserver", "0.0.0.0:8000"],
        ):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            with pytest.raises(ImproperlyConfigured) as exc_info:
                config.ready()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


def test_ready_raises_for_collectstatic_command(settings) -> None:
    """``ready()`` MUST raise for non-migrate management commands with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch(
            "quickscale_modules_orgs.apps.sys.argv",
            ["manage.py", "collectstatic", "--noinput"],
        ):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            with pytest.raises(ImproperlyConfigured) as exc_info:
                config.ready()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


def test_ready_raises_for_gunicorn_startup(settings) -> None:
    """``ready()`` must STILL raise for gunicorn WSGI startup with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        with patch(
            "quickscale_modules_orgs.apps.sys.argv",
            ["/usr/local/bin/gunicorn", "myapp.wsgi:application"],
        ):
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


def test_rls_guard_noop_when_query_returns_none(settings) -> None:
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
