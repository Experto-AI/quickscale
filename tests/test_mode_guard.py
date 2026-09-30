"""QUICKSCALE_MODE boot guard tests.

Rule 3: ``QuickscaleOrgsConfig.ready()`` registers the generic settings
check, which validates ``QUICKSCALE_MODE`` (presence, type, choices) through
``quickscale_core.runtime`` before the BYPASSRLS guard runs.  The guard runs
on every startup path (including migrate), so a saas-mode generated project
cannot silently default to solo-mode tenancy when ``QUICKSCALE_MODE`` is
omitted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command
from django.core.management.base import SystemCheckError
from django.core.management.commands import migrate, runserver

import quickscale_modules_orgs

from quickscale_modules_orgs.apps import QuickscaleOrgsConfig


def _orgs_config() -> QuickscaleOrgsConfig:
    return QuickscaleOrgsConfig("quickscale_modules_orgs", quickscale_modules_orgs)


def _mock_non_postgres_connection() -> MagicMock:
    """Build a mock connection that is NOT PostgreSQL (bypasses RLS check)."""
    mock_conn = MagicMock()
    mock_conn.vendor = "sqlite"
    return mock_conn


@pytest.mark.parametrize("mode", ["solo", "saas"])
def test_ready_passes_for_a_supported_mode(settings, mode: str) -> None:
    """``ready()`` must pass for each supported ``QUICKSCALE_MODE``."""
    settings.QUICKSCALE_MODE = mode

    with patch(
        "quickscale_modules_orgs.checks.connection",
        _mock_non_postgres_connection(),
    ):
        _orgs_config().ready()  # must not raise


def test_ready_raises_when_mode_missing(settings) -> None:
    """``ready()`` MUST raise when ``QUICKSCALE_MODE`` is unset."""
    del settings.QUICKSCALE_MODE

    with patch(
        "quickscale_modules_orgs.checks.connection",
        _mock_non_postgres_connection(),
    ):
        with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_MODE"):
            _orgs_config().ready()


@pytest.mark.parametrize(
    "invalid_mode",
    ["Solo", "SAAS", "", "invalid", "multi", "hybrid"],
)
def test_ready_raises_for_invalid_values(settings, invalid_mode: str) -> None:
    """Invalid ``QUICKSCALE_MODE`` values MUST raise at startup."""
    settings.QUICKSCALE_MODE = invalid_mode

    with patch(
        "quickscale_modules_orgs.checks.connection",
        _mock_non_postgres_connection(),
    ):
        with pytest.raises(ImproperlyConfigured, match="QUICKSCALE_MODE"):
            _orgs_config().ready()


# ---------------------------------------------------------------------------
# Registered-check path: manage.py check, migrate, and runserver fail alike
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_invalid_mode_fails_check_migrate_and_runserver(settings) -> None:
    """The registered generic check fails check, migrate, and runserver alike."""
    settings.QUICKSCALE_MODE = "invalid"

    with pytest.raises(SystemCheckError, match="QUICKSCALE_MODE"):
        call_command("check")
    with pytest.raises(SystemCheckError, match="QUICKSCALE_MODE"):
        migrate.Command().check()
    with pytest.raises(SystemCheckError, match="QUICKSCALE_MODE"):
        runserver.Command().check()
