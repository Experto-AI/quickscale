"""The shared conftest plugin for the module suites (decisions rule 18).

Every module's ``tests/conftest.py`` imports :func:`pytest_configure` and
:func:`pytest_collection_modifyitems` from here, so the ``bypass_rls`` marker
contract is defined once.  A module that needs extra setup -- notifications
forces ``reuse_db`` -- defines its own wrapper that calls the shared hook
first.
"""

from __future__ import annotations

import os

import pytest

__all__ = [
    "ALLOW_BYPASS_RLS_ENV_VAR",
    "BYPASS_RLS_MARKER",
    "pytest_collection_modifyitems",
    "pytest_configure",
]

#: The marker description registered by :func:`pytest_configure`.
BYPASS_RLS_MARKER = (
    "bypass_rls: test requires BYPASSRLS database privilege "
    "(superuser / migration DDL). Deselected unless QUICKSCALE_ALLOW_BYPASSRLS "
    "is exactly '1'."
)

#: The environment variable that opts BYPASSRLS-dependent tests in; exactly
#: ``"1"`` runs them, anything else (including unset) deselects them.
ALLOW_BYPASS_RLS_ENV_VAR = "QUICKSCALE_ALLOW_BYPASSRLS"


def pytest_configure(config: pytest.Config) -> None:
    """Register the bypass_rls marker to prevent PytestUnknownMarkWarning."""
    config.addinivalue_line("markers", BYPASS_RLS_MARKER)


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Deselect bypass_rls tests unless QUICKSCALE_ALLOW_BYPASSRLS is exactly "1".

    Under NOBYPASSRLS (the default), migration tests and other
    BYPASSRLS-dependent tests are deselected so the suite passes
    cleanly with a restricted DB role.
    """
    if os.environ.get(ALLOW_BYPASS_RLS_ENV_VAR) == "1":
        return  # Explicit BYPASSRLS authorization — run all tests
    selected: list[pytest.Item] = []
    deselected: list[pytest.Item] = []
    for item in items:
        if item.get_closest_marker("bypass_rls"):
            deselected.append(item)
        else:
            selected.append(item)
    items[:] = selected
    if deselected:
        config.hook.pytest_deselected(items=deselected)
