"""SA68 Phase 1 — RLS boot guard unit tests.

Tests for ``quickscale_modules_orgs.checks.check_rls_role`` — the function
run by ``QuickscaleOrgsConfig.ready()`` through
``quickscale_core.runtime.register_module_checks`` that fails startup when the
connected PostgreSQL role has BYPASSRLS or SUPERUSER (either alone suffices
to fail the guard).

The guard is always active (regardless of ``QUICKSCALE_MODE`` or
``DEBUG``) with two narrow exemptions:

1. ``QUICKSCALE_PRIVILEGED_COMMAND`` set to a sanctioned privileged
   DB command (``migrate``, ``createcachetable``) — ``start.sh`` sets
   this env var alongside ``RUNTIME_DATABASE_URL=""`` so DDL/DML runs
   under the superuser ``DATABASE_URL``.
2. ``QUICKSCALE_ALLOW_BYPASSRLS=1`` non-serving env-var escape hatch — for
   intentional single-tenant/development use.

The module guard declares its sanctioned command set in
``_PRIVILEGED_COMMANDS`` and checks it via ``_is_privileged_command()``
(formerly ``_is_migrate_command()``, widened in CR-SA68-001).  The generated
production-settings validator, CLI producer, and launcher independently
declare the same fail-closed contract.

``manage.py runserver``, gunicorn, and WSGI startup must all still
fail closed under BYPASSRLS or SUPERUSER.  The old ``sys.argv``-based
``_is_migrate_command`` has been replaced by the explicit env-var
contract (SA68 Phase 1).

SA203 — the privileged-command exemption narrows to ``check_rls_role()``
alone: the AF9 priming install, the SA70 ``pre_delete`` last-owner backstop,
and the check registration install on every startup path, including a
privileged command.
"""

from __future__ import annotations

import importlib
import os
import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver
from django.db.backends.signals import connection_created
from django.db.models.signals import pre_delete

import quickscale_modules_orgs
from quickscale_modules_orgs.apps import (
    QuickscaleOrgsConfig,
    _install_priming_on_connection,
)
from quickscale_modules_orgs.checks import (
    _PRIVILEGED_COMMANDS,
    _is_privileged_command,
    check_rls_role,
)
from quickscale_modules_orgs.models import OrganizationMembership


@pytest.fixture(autouse=True)
def _clear_escape_hatch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove the SA2.1 escape hatch before each test.

    The env var is a shell-level opt-in (set before running
    pytest — no module test code primes it).  This autouse
    fixture clears it before every test so that tests
    exercising the guard work correctly without the env var interfering.
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


def _assert_reports(messages: list, *fragments: str) -> None:
    """Assert the guard reported a failure whose text carries *fragments*."""
    assert messages, "expected the guard to report a failure"
    text = " ".join(str(message.msg) for message in messages)
    for fragment in fragments:
        assert fragment in text


# ---------------------------------------------------------------------------
# Report: saas + DEBUG=False + PostgreSQL + rolbypassrls = true
# ---------------------------------------------------------------------------


def test_rls_guard_reports_bypassrls_role(settings: Any) -> None:
    """Saas + DEBUG=False + PostgreSQL + BYPASSRLS role reports a failure."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        messages = check_rls_role()

    _assert_reports(messages, "BYPASSRLS", "NOBYPASSRLS")


# ---------------------------------------------------------------------------
# Pass: saas + DEBUG=False + PostgreSQL + rolbypassrls = false
# ---------------------------------------------------------------------------


def test_rls_guard_passes_for_nobypassrls_role(settings: Any) -> None:
    """Saas + DEBUG=False + PostgreSQL + NOBYPASSRLS role passes."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=False)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        assert check_rls_role() == []


# ---------------------------------------------------------------------------
# Report: SA58 — rolsuper=True + rolbypassrls=False also reports
# ---------------------------------------------------------------------------


def test_rls_guard_reports_superuser_role(settings: Any) -> None:
    """SUPERUSER role without BYPASSRLS must also report a failure."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=False, rolsuper=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        messages = check_rls_role()

    _assert_reports(messages, "SUPERUSER", "NOSUPERUSER")


# ---------------------------------------------------------------------------
# Report: solo mode (SA2.1 — always-on, no longer exempt)
# ---------------------------------------------------------------------------


def test_rls_guard_reports_in_solo_mode(settings: Any) -> None:
    """Solo mode must now report a failure with a BYPASSRLS role."""
    settings.QUICKSCALE_MODE = "solo"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        messages = check_rls_role()

    _assert_reports(messages, "BYPASSRLS", "NOBYPASSRLS")


# ---------------------------------------------------------------------------
# Report: DEBUG=True (SA2.1 — always-on, no longer exempt)
# ---------------------------------------------------------------------------


def test_rls_guard_reports_when_debug_true(settings: Any) -> None:
    """DEBUG=True must now report a failure with a BYPASSRLS role."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = True

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        messages = check_rls_role()

    _assert_reports(messages, "BYPASSRLS", "NOBYPASSRLS")


# ---------------------------------------------------------------------------
# No-op: non-PostgreSQL vendor (SQLite, etc.)
# ---------------------------------------------------------------------------


def test_rls_guard_noop_on_sqlite(settings: Any) -> None:
    """Non-PostgreSQL vendor must skip the check entirely."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = MagicMock()
    mock_conn.vendor = "sqlite"

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        assert check_rls_role() == []


# ---------------------------------------------------------------------------
# SA2.1 — Escape hatch: QUICKSCALE_ALLOW_BYPASSRLS=1
# ---------------------------------------------------------------------------


def test_rls_guard_escape_hatch_bypasses_in_saas_prod(settings: Any) -> None:
    """Escape hatch ``QUICKSCALE_ALLOW_BYPASSRLS=1`` bypasses the guard."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.checks.connection", mock_conn):
            assert check_rls_role() == []


def test_rls_guard_escape_hatch_bypasses_in_solo(settings: Any) -> None:
    """Escape hatch also bypasses in solo mode."""
    settings.QUICKSCALE_MODE = "solo"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.checks.connection", mock_conn):
            assert check_rls_role() == []


def test_rls_guard_escape_hatch_bypasses_with_debug(settings: Any) -> None:
    """Escape hatch also bypasses when DEBUG=True."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = True

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "1"}):
        with patch("quickscale_modules_orgs.checks.connection", mock_conn):
            assert check_rls_role() == []


def test_rls_guard_escape_hatch_exact_value(settings: Any) -> None:
    """Only the exact value ``\"1\"`` triggers the escape hatch."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    # Value "0" must NOT bypass
    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": "0"}):
        with patch("quickscale_modules_orgs.checks.connection", mock_conn):
            messages = check_rls_role()

    _assert_reports(messages, "BYPASSRLS")


def test_rls_guard_escape_hatch_empty_value_does_not_bypass(settings: Any) -> None:
    """Empty string must NOT bypass the guard."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch.dict(os.environ, {"QUICKSCALE_ALLOW_BYPASSRLS": ""}):
        with patch("quickscale_modules_orgs.checks.connection", mock_conn):
            messages = check_rls_role()

    _assert_reports(messages, "BYPASSRLS")


# ---------------------------------------------------------------------------
# Report: unset QUICKSCALE_MODE (SA2.1 — always-on, no longer exempt)
# ---------------------------------------------------------------------------


def test_rls_guard_reports_when_mode_unset(settings: Any) -> None:
    """Unset QUICKSCALE_MODE must now report a failure with a BYPASSRLS role."""
    settings.DEBUG = False

    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        messages = check_rls_role()

    _assert_reports(messages, "BYPASSRLS", "NOBYPASSRLS")


# ---------------------------------------------------------------------------
# _is_privileged_command: sanctioned QUICKSCALE_PRIVILEGED_COMMAND values
# are exempt; unrecognised, empty, and non-DB vars are not
# ---------------------------------------------------------------------------


def test_privileged_command_set_names_every_sanctioned_member() -> None:
    """The module guard permits exactly the two stable Django built-ins."""
    assert _PRIVILEGED_COMMANDS == frozenset({"migrate", "createcachetable"})


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

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
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

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        with patch.dict(
            os.environ,
            {"QUICKSCALE_PRIVILEGED_COMMAND": "createcachetable"},
            clear=True,
        ):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            config.ready()  # must not raise


def test_ready_installs_backstops_under_privileged_command(settings: Any) -> None:
    """SA203: a privileged command skips only ``check_rls_role()``.

    ``ready()`` must still connect the SA70 last-owner ``pre_delete``
    backstop and the AF9 ``connection_created`` priming install when
    ``QUICKSCALE_PRIVILEGED_COMMAND=migrate``.  The backstop is connected
    sender-free, so it also fires for the historical model class a data
    migration deletes through (covered by
    ``test_models.test_historical_model_delete_of_last_owner_in_multi_member_org_is_refused``).
    Both receivers are disconnected first so the assertions observe this
    ``ready()`` call rather than Django's startup ``ready()``, then
    reconnected so the rest of the suite sees the normal wiring.  The
    receivers module is dropped from ``sys.modules`` first, because the
    ``@receiver`` decorator runs on import and a cached import would not
    reconnect the disconnected backstop.
    """
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    receivers_module = importlib.import_module("quickscale_modules_orgs.receivers")
    pre_delete.disconnect(receivers_module._protect_last_owner_on_membership_delete)
    connection_created.disconnect(_install_priming_on_connection)
    try:
        with patch("quickscale_modules_orgs.checks.connection", mock_conn):
            with patch.dict(
                os.environ,
                {"QUICKSCALE_PRIVILEGED_COMMAND": "migrate"},
                clear=True,
            ):
                sys.modules.pop("quickscale_modules_orgs.receivers", None)
                config = QuickscaleOrgsConfig(
                    "quickscale_modules_orgs", quickscale_modules_orgs
                )
                config.ready()  # must not raise — the guard is skipped

        # ``_live_receivers`` returns ``(sync_receivers, async_receivers)``;
        # both installs connect synchronous receivers.  A sender-free
        # connection matches the live membership sender as well.  The
        # receiver is matched by name, not by the module attribute, so a
        # test-side import is what must not be able to hide a missing
        # ``ready()`` import: the assertion runs before any import here.
        membership_receivers, _membership_async = pre_delete._live_receivers(
            sender=OrganizationMembership
        )
        priming_receivers, _priming_async = connection_created._live_receivers(
            sender=None
        )
        assert any(
            getattr(receiver, "__name__", "")
            == "_protect_last_owner_on_membership_delete"
            for receiver in membership_receivers
        ), "privileged ready() skipped the SA70 last-owner pre_delete backstop"
        assert _install_priming_on_connection in priming_receivers, (
            "privileged ready() skipped the AF9 connection_created priming install"
        )
    finally:
        # Re-import in case an assertion fired before the fresh module was
        # bound, then reconnect so the rest of the suite sees normal wiring.
        receivers_module = importlib.import_module("quickscale_modules_orgs.receivers")
        pre_delete.connect(receivers_module._protect_last_owner_on_membership_delete)
        connection_created.connect(_install_priming_on_connection)


def test_ready_rejects_unrecognised_command_under_bypassrls(settings: Any) -> None:
    """An unrecognised command cannot use a BYPASSRLS connection through ready()."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        with patch.dict(
            os.environ,
            {"QUICKSCALE_PRIVILEGED_COMMAND": "not_a_sanctioned_command"},
            clear=True,
        ):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            with pytest.raises(ImproperlyConfigured):
                config.ready()


def test_ready_raises_for_runserver_command(settings: Any) -> None:
    """``ready()`` MUST raise for ``manage.py runserver`` with BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
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

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
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

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        with patch.dict(os.environ, {}, clear=True):
            config = QuickscaleOrgsConfig(
                "quickscale_modules_orgs", quickscale_modules_orgs
            )
            with pytest.raises(ImproperlyConfigured) as exc_info:
                config.ready()

    assert "BYPASSRLS" in str(exc_info.value)
    assert "NOBYPASSRLS" in str(exc_info.value)


@pytest.mark.django_db
def test_bypassrls_role_fails_check_migrate_and_runserver(settings: Any) -> None:
    """The registered guard fails ``manage.py check``, ``migrate``, and
    ``runserver`` alike while the role has BYPASSRLS."""
    settings.QUICKSCALE_MODE = "saas"
    settings.DEBUG = False
    mock_conn = _mock_postgres_connection(rolbypassrls=True)

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemCheckError, match="BYPASSRLS"):
                call_command("check")
            with pytest.raises(SystemCheckError, match="BYPASSRLS"):
                migrate.Command().check()
            with pytest.raises(SystemCheckError, match="BYPASSRLS"):
                runserver.Command().check()


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

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        assert check_rls_role() == []
