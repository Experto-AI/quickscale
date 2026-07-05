"""SA14.6 — QUICKSCALE_MODE boot guard unit tests.

Tests for ``quickscale_modules_orgs.apps._check_quickscale_mode`` — the
standalone function called by ``QuickscaleOrgsConfig.ready()`` that raises
``ImproperlyConfigured`` when ``QUICKSCALE_MODE`` is unset or has an
invalid value.

The guard runs on every startup path (including migrate) before the
BYPASSRLS guard so that a saas-mode generated project cannot silently
default to solo-mode tenancy when ``QUICKSCALE_MODE`` is omitted.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from django.core.exceptions import ImproperlyConfigured
from django.test.utils import override_settings

import quickscale_modules_orgs

from quickscale_modules_orgs.apps import (
    QuickscaleOrgsConfig,
    _check_quickscale_mode,
)


# ---------------------------------------------------------------------------
# _check_quickscale_mode: solo / saas pass
# ---------------------------------------------------------------------------


def test_mode_guard_passes_for_solo(settings) -> None:
    """``QUICKSCALE_MODE = "solo"`` must not raise."""
    settings.QUICKSCALE_MODE = "solo"
    _check_quickscale_mode()  # must not raise


def test_mode_guard_passes_for_saas(settings) -> None:
    """``QUICKSCALE_MODE = "saas"`` must not raise."""
    settings.QUICKSCALE_MODE = "saas"
    _check_quickscale_mode()  # must not raise


# ---------------------------------------------------------------------------
# _check_quickscale_mode: missing / None raises
# ---------------------------------------------------------------------------


@override_settings(QUICKSCALE_MODE=None)
def test_mode_guard_raises_when_none() -> None:
    """``QUICKSCALE_MODE = None`` (unset) must raise ``ImproperlyConfigured``."""
    with pytest.raises(ImproperlyConfigured) as exc_info:
        _check_quickscale_mode()
    assert "QUICKSCALE_MODE" in str(exc_info.value)
    assert "required" in str(exc_info.value).lower()


# ---------------------------------------------------------------------------
# _check_quickscale_mode: invalid values raise
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
def test_mode_guard_raises_for_invalid_values(invalid_mode: str, settings) -> None:
    """Invalid ``QUICKSCALE_MODE`` values must raise ``ImproperlyConfigured``."""
    settings.QUICKSCALE_MODE = invalid_mode
    with pytest.raises(ImproperlyConfigured) as exc_info:
        _check_quickscale_mode()
    assert "QUICKSCALE_MODE" in str(exc_info.value)
    assert invalid_mode in str(exc_info.value)


# ---------------------------------------------------------------------------
# _check_quickscale_mode: case sensitivity enforced
# ---------------------------------------------------------------------------


def test_mode_guard_wrong_case_raises(settings) -> None:
    """Case variants like ``"Solo"`` must be rejected (case-sensitive)."""
    settings.QUICKSCALE_MODE = "Solo"
    with pytest.raises(ImproperlyConfigured) as exc_info:
        _check_quickscale_mode()
    assert "Solo" in str(exc_info.value)


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

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        config = QuickscaleOrgsConfig(
            "quickscale_modules_orgs", quickscale_modules_orgs
        )
        config.ready()  # must not raise


@override_settings(QUICKSCALE_MODE=None)
def test_ready_raises_when_mode_unset() -> None:
    """``ready()`` MUST raise when ``QUICKSCALE_MODE`` is unset."""
    mock_conn = _mock_non_postgres_connection()

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
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

    with patch("quickscale_modules_orgs.apps.connection", mock_conn):
        config = QuickscaleOrgsConfig(
            "quickscale_modules_orgs", quickscale_modules_orgs
        )
        with pytest.raises(ImproperlyConfigured) as exc_info:
            config.ready()

    assert "QUICKSCALE_MODE" in str(exc_info.value)
    assert "invalid" in str(exc_info.value)
