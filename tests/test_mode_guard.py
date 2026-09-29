"""QUICKSCALE_MODE boot guard unit tests.

Tests for ``quickscale_modules_orgs.checks.check_quickscale_mode`` — the
function run by ``QuickscaleOrgsConfig.ready()`` through
``quickscale_core.runtime.register_module_checks`` that fails startup when
``QUICKSCALE_MODE`` is unset or has an invalid value.

The guard runs on every startup path (including migrate) before the
BYPASSRLS guard so that a saas-mode generated project cannot silently
default to solo-mode tenancy when ``QUICKSCALE_MODE`` is omitted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver
from django.test.utils import override_settings

import quickscale_modules_orgs

from quickscale_modules_orgs.apps import QuickscaleOrgsConfig
from quickscale_modules_orgs.checks import check_quickscale_mode


# ---------------------------------------------------------------------------
# check_quickscale_mode: solo / saas pass
# ---------------------------------------------------------------------------


def test_mode_guard_passes_for_solo(settings) -> None:
    """``QUICKSCALE_MODE = "solo"`` must not report a failure."""
    settings.QUICKSCALE_MODE = "solo"
    assert check_quickscale_mode() == []


def test_mode_guard_passes_for_saas(settings) -> None:
    """``QUICKSCALE_MODE = "saas"`` must not report a failure."""
    settings.QUICKSCALE_MODE = "saas"
    assert check_quickscale_mode() == []


# ---------------------------------------------------------------------------
# check_quickscale_mode: missing / None reports
# ---------------------------------------------------------------------------


@override_settings(QUICKSCALE_MODE=None)
def test_mode_guard_reports_when_none() -> None:
    """``QUICKSCALE_MODE = None`` (unset) must report a failure."""
    messages = check_quickscale_mode()
    assert messages
    assert "QUICKSCALE_MODE" in messages[0].msg
    assert "required" in messages[0].msg.lower()


# ---------------------------------------------------------------------------
# check_quickscale_mode: invalid values report
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "invalid_mode",
    [
        "Solo",
        "SAAS",
        "",
        "invalid",
        "multi",
        "hybrid",
    ],
)
def test_mode_guard_reports_for_invalid_values(invalid_mode: str, settings) -> None:
    """Invalid ``QUICKSCALE_MODE`` values must report a failure."""
    settings.QUICKSCALE_MODE = invalid_mode
    messages = check_quickscale_mode()
    assert messages
    assert "QUICKSCALE_MODE" in messages[0].msg
    assert invalid_mode in messages[0].msg


# ---------------------------------------------------------------------------
# check_quickscale_mode: case sensitivity enforced
# ---------------------------------------------------------------------------


def test_mode_guard_wrong_case_reports(settings) -> None:
    """Case variants like ``"Solo"`` must be rejected (case-sensitive)."""
    settings.QUICKSCALE_MODE = "Solo"
    messages = check_quickscale_mode()
    assert messages
    assert "Solo" in messages[0].msg


# ---------------------------------------------------------------------------
# ready() lifecycle: QUICKSCALE_MODE guard runs before BYPASSRLS guard
# ---------------------------------------------------------------------------


def _mock_non_postgres_connection() -> MagicMock:
    """Build a mock connection that is NOT PostgreSQL (bypasses RLS check)."""
    mock_conn = MagicMock()
    mock_conn.vendor = "sqlite"
    return mock_conn


def test_ready_passes_when_mode_set(settings) -> None:
    """``ready()`` must pass when ``QUICKSCALE_MODE`` is set and no BYPASSRLS."""
    settings.QUICKSCALE_MODE = "solo"
    mock_conn = _mock_non_postgres_connection()

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        config = QuickscaleOrgsConfig(
            "quickscale_modules_orgs", quickscale_modules_orgs
        )
        config.ready()  # must not raise


@override_settings(QUICKSCALE_MODE=None)
def test_ready_raises_when_mode_unset() -> None:
    """``ready()`` MUST raise when ``QUICKSCALE_MODE`` is unset."""
    mock_conn = _mock_non_postgres_connection()

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        config = QuickscaleOrgsConfig(
            "quickscale_modules_orgs", quickscale_modules_orgs
        )
        with pytest.raises(ImproperlyConfigured) as exc_info:
            config.ready()

    assert "QUICKSCALE_MODE" in str(exc_info.value)
    assert "required" in str(exc_info.value).lower()


def test_ready_raises_when_mode_set_to_invalid(settings) -> None:
    """``ready()`` MUST raise when ``QUICKSCALE_MODE`` has invalid value."""
    settings.QUICKSCALE_MODE = "invalid"
    mock_conn = _mock_non_postgres_connection()

    with patch("quickscale_modules_orgs.checks.connection", mock_conn):
        config = QuickscaleOrgsConfig(
            "quickscale_modules_orgs", quickscale_modules_orgs
        )
        with pytest.raises(ImproperlyConfigured) as exc_info:
            config.ready()

    assert "QUICKSCALE_MODE" in str(exc_info.value)
    assert "invalid" in str(exc_info.value)


# ---------------------------------------------------------------------------
# Registered-check path: manage.py check, migrate, and runserver fail alike
# ---------------------------------------------------------------------------


@override_settings(QUICKSCALE_MODE=None)
@pytest.mark.django_db
def test_missing_mode_fails_check_migrate_and_runserver() -> None:
    """The registered guard fails ``manage.py check``, ``migrate``, and
    ``runserver`` alike while ``QUICKSCALE_MODE`` is unset."""
    with pytest.raises(SystemCheckError, match="QUICKSCALE_MODE"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_MODE"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_MODE"):
        runserver.Command().check()
