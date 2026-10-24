"""Pytest configuration for quickscale_cli tests."""

import os
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from click.testing import CliRunner


# Prefer workspace source trees over any stale user-site installs.
_REPO_ROOT = Path(__file__).resolve().parents[2]
for _src_path in (
    _REPO_ROOT / "quickscale/src",
    _REPO_ROOT / "quickscale_core/src",
    _REPO_ROOT / "quickscale_cli/src",
):
    _src_path_str = str(_src_path)
    if _src_path_str in sys.path:
        sys.path.remove(_src_path_str)
    sys.path.insert(0, _src_path_str)

# Make module adapter packages importable so that managed-wiring regeneration
# (refresh_managed_adapters) can import quickscale_modules_{name}.adapter.
for _module_entry in sorted((_REPO_ROOT / "quickscale_modules").iterdir()):
    _module_src = _module_entry / "src"
    if _module_src.is_dir():
        _src_str = str(_module_src.resolve())
        if _src_str not in sys.path:
            sys.path.insert(0, _src_str)


def _materialize_bundled_manifests() -> None:
    """Derive the bundled manifests before CLI tests read them (SA280 (b)).

    A fresh clone does not track ``quickscale_core/data/manifests/``; the CLI
    suites exercise managed-wiring regeneration and wheel builds that read the
    bundled inventory, so the repository materializes it here exactly as a
    build does.  Runs at conftest import time.
    """
    script = _REPO_ROOT / "scripts" / "sync_module_manifests.py"
    if not (_REPO_ROOT / "quickscale_modules").is_dir() or not script.is_file():
        return
    result = subprocess.run(  # noqa: S603 - fixed argv list, shell disabled
        [sys.executable, str(script), str(_REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "failed to materialize the bundled module manifests:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )


_materialize_bundled_manifests()


@pytest.fixture(scope="session")
def local_core_wheelhouse(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Return a wheelhouse holding the repository's own quickscale-core wheel.

    The repository version is unpublished while it is still in development, so a
    generated project's bounded ``quickscale-core`` lockstep pin cannot resolve
    from PyPI.  E2E tests must exercise the same local-artifact path a
    development install uses: ``make install`` stages ``<venv>/quickscale_wheels``
    (read by ``quickscale_cli.utils.module_dependency_sync``) and every generated
    project resolves its own unpublished core from those wheels.  The wheel is
    built once per session from the source under test.
    """
    from quickscale_core.utils.poetry_env import build_isolated_poetry_env

    version = (_REPO_ROOT / "VERSION").read_text(encoding="utf-8").strip()
    source_copy = tmp_path_factory.mktemp("quickscale-core-wheel") / "quickscale_core"
    shutil.copytree(
        _REPO_ROOT / "quickscale_core",
        source_copy,
        ignore=shutil.ignore_patterns(
            ".venv", "dist", "__pycache__", ".pytest_cache", "*.pyc", "*.pyo"
        ),
    )
    build_result = subprocess.run(
        ["poetry", "build", "--format", "wheel"],
        cwd=source_copy,
        capture_output=True,
        text=True,
        timeout=300,
        env=build_isolated_poetry_env(),
    )
    assert build_result.returncode == 0, (
        "Local quickscale-core wheel build failed:\n"
        f"stdout: {build_result.stdout}\nstderr: {build_result.stderr}"
    )
    wheelhouse = source_copy / "dist"
    wheels = sorted(wheelhouse.glob("quickscale_core-*.whl"))
    assert len(wheels) == 1, (
        "Expected exactly one local quickscale-core wheel, got "
        f"{[wheel.name for wheel in wheels]}"
    )
    assert wheels[0].name.startswith(f"quickscale_core-{version}-"), (
        f"Local core wheel does not match VERSION {version}: {wheels[0].name}"
    )
    return wheelhouse


@pytest.fixture
def local_core_wheelhouse_env(
    local_core_wheelhouse: Path, monkeypatch: pytest.MonkeyPatch
) -> Path:
    """Point the CLI's wheelhouse resolution at the local core wheel.

    Apply-side dependency sync reads ``QUICKSCALE_LOCAL_WHEELHOUSE`` and pins
    the generated project to the matching wheel, exactly as a locally installed
    CLI does for an unpublished development version.
    """
    monkeypatch.setenv("QUICKSCALE_LOCAL_WHEELHOUSE", str(local_core_wheelhouse))
    return local_core_wheelhouse


@pytest.fixture
def pin_generated_project_core(local_core_wheelhouse: Path):
    """Return a callable that pins a generated project to the local core wheel.

    Project generation runs before any CLI dependency sync, so tests that build
    or install a generated project directly must apply the same local-artifact
    pin themselves.
    """
    from quickscale_cli.utils._dependency_sync_ops import sync_project_core_dependency

    def _pin(project_path: Path) -> None:
        assert sync_project_core_dependency(project_path, local_core_wheelhouse), (
            "the generated project should declare the bounded quickscale-core "
            "lockstep pin that the local wheel replaces"
        )

    return _pin


@pytest.fixture(autouse=True)
def _skip_generator_poetry_lock(request: pytest.FixtureRequest) -> None:
    """Stop ``generate()`` from shelling out to real ``poetry lock`` in the unit lane.

    Mirrors the fixture in ``quickscale_core/tests/conftest.py``: CLI tests also
    drive real project generation, and the generator runs ``poetry lock`` during
    ``generate()`` (see ``generator._generate_poetry_lock``). Left unset, those
    tests spawn a network ``poetry lock`` (up to 300s) that hangs the unit run —
    now surfaced as a ``--timeout`` kill/node-down. ``QS_SKIP_POETRY_LOCK`` makes
    the generator skip it. Cleared for e2e tests, which need real generation.
    """
    if request.node.get_closest_marker("e2e"):
        os.environ.pop("QS_SKIP_POETRY_LOCK", None)
    else:
        os.environ["QS_SKIP_POETRY_LOCK"] = "1"


@pytest.fixture(autouse=True)
def _stub_module_update_seal_preflight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep update suites hermetic and focused on their own mechanism.

    Sealed-tag resolution, the whole-set preflight, and the ``poetry.lock``
    refresh have focused coverage in ``test_update_seal.py``.  Other update
    suites would otherwise reach the network for a tag lookup, or run a real
    ``poetry lock``.  The update command still resolves each module's branch
    ref through ``resolve_remote_ref``, which those suites patch explicitly.
    """
    monkeypatch.setattr(
        "quickscale_core.utils.git_tags.resolve_remote_tag",
        lambda remote, tag: "a" * 40,
    )
    monkeypatch.setattr(
        "quickscale_cli.commands._module_update_seal._remote_trees",
        lambda remote, first_commit, second_commit: ("sealed-tree", "sealed-tree"),
    )
    from quickscale_cli.commands._module_update_seal import _UpdateSealPlan

    def _stub_preflight(state, remote, version):
        del remote
        return (
            {
                name: _UpdateSealPlan(
                    module=name,
                    version=version,
                    tag=f"splits/{name}-module/{version}",
                    tag_sha="a" * 40,
                    branch=f"splits/{name}-module",
                    branch_sha="a" * 40,
                )
                for name in state.modules
            },
            None,
        )

    monkeypatch.setattr(
        "quickscale_cli.commands._module_update_seal._preflight_update_seals",
        _stub_preflight,
    )
    # The stub plans use a fixed SHA, so the requirement preflight cannot read
    # a target manifest.  Its production behavior has focused coverage in
    # test_update_journal.py and test_update_wiring_regeneration.py.
    monkeypatch.setattr(
        "quickscale_cli.commands._module_update._missing_required_module_error",
        lambda project_path, state, seal_plans: None,
    )
    monkeypatch.setattr(
        "quickscale_cli.commands._module_update_io._refresh_update_lockfile",
        lambda project_path: True,
    )


@pytest.fixture
def cli_runner() -> CliRunner:
    """Provide a Click CLI test runner for testing CLI commands."""
    return CliRunner()


@pytest.fixture
def sample_project_name() -> str:
    """Provide a sample project name for testing."""
    return "testproject"


@pytest.fixture(autouse=True)
def mock_dependencies(monkeypatch):
    """Mock system dependency checks to always pass in tests."""
    from quickscale_cli.utils.dependency_utils import DependencyStatus

    monkeypatch.setenv("QUICKSCALE_SKIP_DEPENDENCY_CHECKS", "1")

    mock_deps = [
        DependencyStatus("Python", True, "3.14.0", True, "Runtime"),
        DependencyStatus("Poetry", True, "1.8.0", True, "Dependency management"),
        DependencyStatus("Git", True, "2.40.0", True, "Version control"),
        DependencyStatus("Docker", True, "24.0.0", True, "Containerization"),
        DependencyStatus("PostgreSQL", True, "18.0", True, "Database"),
    ]

    with patch(
        "quickscale_cli.utils.dependency_utils.check_all_dependencies",
        return_value=mock_deps,
    ):
        yield


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers", "e2e: mark test as full end-to-end test (requires Docker)"
    )
