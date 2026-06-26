"""T1.18 — RLS boot guard unit tests.

Tests for ``quickscale_modules_orgs.apps._check_rls_role`` — the
standalone function called by ``QuickscaleOrgsConfig.ready()`` that
raises ``ImproperlyConfigured`` when the connected PostgreSQL role has
BYPASSRLS in saas production mode.

Also tests the narrow migrate-command exemption in ``ready()``.
Per ``decisions.md`` line 1121, only ``manage.py migrate`` is exempt
from the boot guard — ``start.sh`` deliberately unsets
``RUNTIME_DATABASE_URL`` so DDL runs under the superuser
``DATABASE_URL``.  ``manage.py runserver``, gunicorn, and WSGI
startup must all still fail closed under BYPASSRLS.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured

import quickscale_modules_orgs

from quickscale_modules_orgs.apps import (
    QuickscaleOrgsConfig,
    _check_rls_role,
    _is_migrate_command,
)


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
# No-op: solo mode (regardless of DEBUG)
# ---------------------------------------------------------------------------


def test_rls_guard_noop_in_solo_mode(settings) -> None:
    """Solo mode must skip the check even with a BYPASSRLS role."""
    settings.QUICKSCALE_MODE = "solo"
    settings.DEBUG = False

    # Even with a mock that would raise, solo mode returns early.
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        _check_rls_role()  # must not raise


# ---------------------------------------------------------------------------
# No-op: DEBUG=True (regardless of mode)
# ---------------------------------------------------------------------------


def test_rls_guard_noop_when_debug_true(settings) -> None:
    """DEBUG=True must skip the check even with a BYPASSRLS role."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = True

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        _check_rls_role()  # must not raise


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
# No-op: default QUICKSCALE_MODE (solo fallback when attribute absent)
# ---------------------------------------------------------------------------


def test_rls_guard_noop_when_mode_unset(settings) -> None:
    """Unset QUICKSCALE_MODE defaults to solo — must skip the check."""
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        _check_rls_role()  # must not raise


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
