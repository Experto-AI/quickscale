"""
The focused-run passthrough (`make test-unit K=...` / `ARGS=...`).

The behaviour under test is the reason the feature exists: the per-package
pyproject.toml addopts carry ``--cov-fail-under=90``, so a narrowed selection
used to fail on coverage even when every selected test passed. These assertions
pin the fix, and pin that an unnarrowed run is left exactly as it was.

``make -n`` is used so nothing is executed; only the recipe text is inspected.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]


def _recipe(*make_args: str) -> str:
    # These suites run inside `make check-gate-suites`, so an outer `make ci
    # ONLY=...` would reach the nested make through MAKEFLAGS (which carries
    # command-line variable assignments to sub-makes regardless of `unexport`)
    # and contaminate the recipe under test. Each invocation must stand alone.
    environment = {
        key: value
        for key, value in os.environ.items()
        if key not in {"MAKEFLAGS", "MFLAGS", "MAKELEVEL", "K", "ARGS", "ONLY", "FROM"}
    }
    result = subprocess.run(
        ["make", "-n", *make_args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=180,
        env=environment,
    )
    assert result.returncode == 0, result.stderr
    # Recipes are backslash-continued; flatten so flags are greppable.
    return " ".join(result.stdout.replace("\\\n", " ").split())


@pytest.mark.parametrize("target", ["test-unit", "test"])
def test_default_run_keeps_the_coverage_gate(target: str) -> None:
    recipe = _recipe(target)
    assert "--cov-fail-under=90" in recipe
    assert "--no-cov" not in recipe


def test_focused_run_drops_the_coverage_gate() -> None:
    """A narrowed selection measures almost no code; the 90% gate is noise."""
    recipe = _recipe("test-unit", "K=test_example")
    assert "--cov-fail-under" not in recipe
    assert "--no-cov" in recipe
    # -o addopts= is required: the gate is re-imposed by pyproject addopts
    # regardless of what the recipe passes.
    assert "-o addopts=" in recipe
    assert "-k 'test_example'" in recipe


def test_focused_run_still_excludes_integration_and_e2e_markers() -> None:
    """Clearing addopts must not widen the selection to slow or DB-bound tests."""
    recipe = _recipe("test-unit", "K=test_example")
    assert '-m "not integration and not e2e"' in recipe


def test_raw_args_are_word_split_for_pytest() -> None:
    recipe = _recipe("test-unit", "ARGS=-x --lf")
    assert "-x --lf" in recipe


def test_focused_run_defaults_to_serial() -> None:
    """A one-test selection should not pay for a 16-worker xdist fan-out."""
    assert "--dist loadfile" not in _recipe("test-unit", "K=test_example")


def test_explicit_worker_count_still_wins_in_focused_mode() -> None:
    recipe = _recipe("test-unit", "K=test_example", "PYTEST_XDIST_WORKERS=4")
    assert "-n 4 --dist loadfile" in recipe


def test_focused_run_warns_that_it_is_not_a_gate() -> None:
    assert "coverage gate disabled" in _recipe("test-unit", "K=test_example")


def test_unfocused_run_prints_no_warning() -> None:
    """An unscoped run keeps the gate, so it must not claim the gate is off."""
    assert "coverage gate disabled" not in _recipe("test-unit")


@pytest.mark.parametrize(
    ("make_args", "expected"),
    [
        (("ONLY=integration",), "--only 'integration'"),
        (("FROM=coverage",), "--from 'coverage'"),
        (("SKIP_INSTALL=1",), "--skip-install"),
    ],
)
def test_ci_forwards_stage_selection(make_args: tuple[str, ...], expected: str) -> None:
    assert expected in _recipe("ci", *make_args)


def test_ci_without_selection_forwards_no_stage_flags() -> None:
    """The default `make ci` invocation must stay exactly as it was."""
    recipe = _recipe("ci")
    for flag in ("--only", "--from", "--skip-install"):
        assert flag not in recipe


def test_full_ci_e2e_runs_privileged_lane_once_after_restricted_ci() -> None:
    recipe = _recipe("ci-e2e")
    restricted = "scripts/check_ci_locally.sh --e2e"
    privileged = "make test-bypassrls"
    assert recipe.count(privileged) == 1
    assert recipe.index(restricted) < recipe.index(privileged)


@pytest.mark.parametrize(
    "selector",
    ["ONLY=integration", "FROM=coverage", "SKIP_INSTALL=1"],
)
def test_partial_ci_e2e_does_not_run_privileged_lane(selector: str) -> None:
    assert "make test-bypassrls" not in _recipe("ci-e2e", selector)


def test_release_gate_does_not_repeat_ci_e2e_privileged_lane() -> None:
    assert "make test-bypassrls" not in _recipe("release-gate")


def test_integration_focus_disables_the_module_coverage_gate() -> None:
    """The per-module mean-coverage check is as meaningless on a subset."""
    recipe = _recipe("test-integration", "K=test_example")
    assert "QS_SKIP_COVERAGE_GATE=1" in recipe
    assert "-- -k 'test_example'" in recipe


def test_integration_without_focus_keeps_its_coverage_gate() -> None:
    recipe = _recipe("test-integration")
    assert "QS_SKIP_COVERAGE_GATE=1" not in recipe


# --- Failure recording safety properties -----------------------------------


def test_recording_trap_restores_the_original_exit_status() -> None:
    """
    Pin the exit-status restore in the recording trap.

    A shell that leaves an EXIT trap on a failing command adopts that command's
    status, so without the explicit re-exit a recorder hiccup could rewrite a
    failing test run's exit code -- including turning a red run green.
    """
    recipe = _recipe("test-unit")
    assert 'exit "$qs_status"' in recipe


def test_stale_failure_caches_are_cleared_before_a_recorded_run() -> None:
    """
    Pin the pre-run cache reset.

    Pytest only rewrites lastfailed for tests a run collected, so entries for
    deselected tests persist across sessions. Without this reset, a narrowed run
    records dozens of unrelated failures for `make retry` to replay.
    """
    recipe = _recipe("test-unit")
    assert "rm -f quickscale_core/.pytest_cache/v/cache/lastfailed" in recipe
    assert "quickscale_modules/*/.pytest_cache/v/cache/lastfailed" in recipe


@pytest.mark.parametrize("flag", ["--lf", "--last-failed", "--ff", "--stepwise"])
def test_cache_dependent_flags_suppress_the_reset(flag: str) -> None:
    """`ARGS='--lf'` needs pytest's cache intact, so the reset must stand down."""
    recipe = _recipe("test-unit", f"ARGS={flag}")
    assert "rm -f quickscale_core/.pytest_cache" not in recipe
