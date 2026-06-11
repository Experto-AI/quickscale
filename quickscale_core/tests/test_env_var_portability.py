"""Tests for the centralized DR env-var portability helpers.

The legacy implementation lived inline in
``quickscale_cli.commands.dr_commands``. The helpers now live in
:mod:`quickscale_core.contracts.module_options` so the schema layer and
any future automation can share the same classification without
depending on the CLI package.

These tests cover the public API of the centralized module and prove
behaviour parity with the legacy ``dr_commands._classify_env_var``
function by re-running every test case that the CLI test suite uses
against the new location.
"""

from __future__ import annotations

import pytest

from quickscale_core.contracts import module_options
from quickscale_core.contracts.module_options import (
    ENV_VAR_PORTABILITY_IGNORED,
    ENV_VAR_PORTABILITY_MANUAL,
    ENV_VAR_PORTABILITY_PORTABLE,
    IGNORED_ENV_EXACT,
    IGNORED_ENV_PREFIXES,
    NON_PORTABLE_ENV_CONTAINS,
    NON_PORTABLE_ENV_EXACT,
    NON_PORTABLE_ENV_PREFIXES,
    PORTABLE_ENV_EXACT,
    PORTABLE_ENV_PREFIXES,
    get_env_var_portability,
)


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


def test_module_options_exports_env_var_portability_helpers() -> None:
    # The module re-exports the constants the CLI used to own so the
    # contract is discoverable from the package's public namespace.
    assert module_options.get_env_var_portability is get_env_var_portability
    assert module_options.IGNORED_ENV_EXACT is IGNORED_ENV_EXACT
    assert module_options.PORTABLE_ENV_PREFIXES is PORTABLE_ENV_PREFIXES
    assert module_options.NON_PORTABLE_ENV_CONTAINS is NON_PORTABLE_ENV_CONTAINS


def test_category_constants_are_distinct() -> None:
    assert (
        ENV_VAR_PORTABILITY_IGNORED
        != ENV_VAR_PORTABILITY_MANUAL
        != ENV_VAR_PORTABILITY_PORTABLE
    )


def test_constants_are_immutable() -> None:
    # The frozenset/tuple markers below guard against silent mutation
    # that would change the classification behaviour at runtime.
    assert isinstance(IGNORED_ENV_EXACT, frozenset)
    assert isinstance(PORTABLE_ENV_EXACT, frozenset)
    assert isinstance(NON_PORTABLE_ENV_EXACT, frozenset)
    for collection in (
        IGNORED_ENV_PREFIXES,
        PORTABLE_ENV_PREFIXES,
        NON_PORTABLE_ENV_PREFIXES,
        NON_PORTABLE_ENV_CONTAINS,
    ):
        assert isinstance(collection, tuple)


# ---------------------------------------------------------------------------
# Classification: blank and ignored names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["", "   ", "\t\n"])
def test_blank_or_whitespace_name_is_ignored(name: str) -> None:
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_IGNORED,
        "blank name",
    )


@pytest.mark.parametrize("name", sorted(IGNORED_ENV_EXACT))
def test_exact_ignored_names_are_ignored(name: str) -> None:
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_IGNORED,
        "shell/runtime noise",
    )


@pytest.mark.parametrize("name", sorted(IGNORED_ENV_PREFIXES))
def test_prefix_ignored_names_are_ignored(name: str) -> None:
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_IGNORED,
        "shell/runtime noise",
    )


def test_ignored_prefix_matches_case_insensitively() -> None:
    # The helper normalises to upper case before matching. We use a
    # prefix from the real list, lowercased, with extra characters that
    # are still part of the same family.
    assert get_env_var_portability("pythonpath") == (
        ENV_VAR_PORTABILITY_IGNORED,
        "shell/runtime noise",
    )
    assert get_env_var_portability("poetry_cache_dir") == (
        ENV_VAR_PORTABILITY_IGNORED,
        "shell/runtime noise",
    )


# ---------------------------------------------------------------------------
# Classification: manual-only restore gates
# ---------------------------------------------------------------------------


def test_quickscale_backups_allow_restore_is_manual() -> None:
    assert get_env_var_portability("QUICKSCALE_BACKUPS_ALLOW_RESTORE") == (
        ENV_VAR_PORTABILITY_MANUAL,
        "destructive restore gate must be set manually",
    )


@pytest.mark.parametrize(
    "name",
    [
        "QUICKSCALE_BACKUPS_ALLOW_RESTORE",
        "QUICKSCALE_BACKUPS_ALLOW_NIGHTLY_RESTORE",
        "QUICKSCALE_BACKUPS_ALLOW_PARTIAL_RESTORE",
    ],
)
def test_allow_restore_family_is_manual(name: str) -> None:
    # The destructive-restore gate rule fires before the portable
    # prefix rule, so a name like ``QUICKSCALE_BACKUPS_ALLOW_RESTORE``
    # is forced to manual even though the ``QUICKSCALE_`` prefix would
    # otherwise mark it portable.
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_MANUAL,
        "destructive restore gate must be set manually",
    )


# ---------------------------------------------------------------------------
# Classification: provider / target-owned names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(NON_PORTABLE_ENV_EXACT))
def test_exact_non_portable_names_are_manual(name: str) -> None:
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_MANUAL,
        "provider-owned or target-owned variable",
    )


@pytest.mark.parametrize("name", sorted(NON_PORTABLE_ENV_PREFIXES))
def test_prefix_non_portable_names_are_manual(name: str) -> None:
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_MANUAL,
        "provider-owned or target-owned variable",
    )


@pytest.mark.parametrize("token", NON_PORTABLE_ENV_CONTAINS)
def test_substring_non_portable_names_are_manual(token: str) -> None:
    # The contains-list match is substring-based, so a name that
    # contains the token anywhere is marked manual. We build a minimal
    # synthetic name that contains the token but is otherwise portable.
    name = f"APP_{token}_EXTRA"
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_MANUAL,
        "sensitive or environment-specific variable",
    )


def test_contains_match_takes_precedence_over_portable_prefix() -> None:
    # ``PUBLIC_BASE_URL`` contains the substring ``BASE_URL``/``URL`` so
    # the contains-list rule fires before the portable prefix rule.
    assert get_env_var_portability("PUBLIC_BASE_URL") == (
        ENV_VAR_PORTABILITY_MANUAL,
        "sensitive or environment-specific variable",
    )


# ---------------------------------------------------------------------------
# Classification: portable names
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(PORTABLE_ENV_EXACT))
def test_exact_portable_names_are_portable(name: str) -> None:
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_PORTABLE,
        "portable variable",
    )


@pytest.mark.parametrize("name", sorted(PORTABLE_ENV_PREFIXES))
def test_prefix_portable_names_are_portable(name: str) -> None:
    assert get_env_var_portability(name) == (
        ENV_VAR_PORTABILITY_PORTABLE,
        "portable variable",
    )


# ---------------------------------------------------------------------------
# Classification: fallthrough to manual
# ---------------------------------------------------------------------------


def test_unlisted_name_falls_through_to_manual() -> None:
    assert get_env_var_portability("UNLISTED_VAR") == (
        ENV_VAR_PORTABILITY_MANUAL,
        "outside the conservative portable allowlist",
    )


# ---------------------------------------------------------------------------
# Parity with the legacy CLI test cases
# ---------------------------------------------------------------------------


# These cases are the exact assertions the CLI test suite uses against
# ``dr_commands._classify_env_var``. Re-running them here proves that
# the centralized helper returns the same ``(category, reason)`` tuple.
LEGACY_PARITY_CASES: list[tuple[str, tuple[str, str]]] = [
    ("", (ENV_VAR_PORTABILITY_IGNORED, "blank name")),
    (
        "HOME",
        (ENV_VAR_PORTABILITY_IGNORED, "shell/runtime noise"),
    ),
    (
        "POETRY_CACHE_DIR",
        (ENV_VAR_PORTABILITY_IGNORED, "shell/runtime noise"),
    ),
    (
        "DATABASE_URL",
        (ENV_VAR_PORTABILITY_MANUAL, "provider-owned or target-owned variable"),
    ),
    (
        "AWS_ACCESS_KEY_ID",
        (ENV_VAR_PORTABILITY_MANUAL, "provider-owned or target-owned variable"),
    ),
    (
        "PUBLIC_BASE_URL",
        (ENV_VAR_PORTABILITY_MANUAL, "sensitive or environment-specific variable"),
    ),
    (
        "DEBUG",
        (ENV_VAR_PORTABILITY_PORTABLE, "portable variable"),
    ),
    (
        "BLOG_THEME",
        (ENV_VAR_PORTABILITY_PORTABLE, "portable variable"),
    ),
    (
        "UNLISTED_VAR",
        (ENV_VAR_PORTABILITY_MANUAL, "outside the conservative portable allowlist"),
    ),
]


@pytest.mark.parametrize(("name", "expected"), LEGACY_PARITY_CASES)
def test_classification_matches_legacy_dr_commands_cases(
    name: str, expected: tuple[str, str]
) -> None:
    assert get_env_var_portability(name) == expected


def test_classification_matches_legacy_allow_restore_case() -> None:
    # The destructive-restore gate case is asserted by the CLI test
    # suite in a slightly different shape, so we mirror the same shape
    # here.
    assert get_env_var_portability("QUICKSCALE_BACKUPS_ALLOW_RESTORE") == (
        ENV_VAR_PORTABILITY_MANUAL,
        "destructive restore gate must be set manually",
    )


# ---------------------------------------------------------------------------
# Round-trip with the CLI shim
# ---------------------------------------------------------------------------


def test_classify_env_var_legacy_shim_delegates_to_centralized_helper() -> None:
    # The CLI keeps a thin shim that calls into the centralized helper
    # so any caller that still reaches into ``dr_commands._classify_env_var``
    # continues to work. The shim must return the exact same tuple.
    from quickscale_cli.commands import dr_commands

    for name, expected in LEGACY_PARITY_CASES:
        assert dr_commands._classify_env_var(name) == expected
