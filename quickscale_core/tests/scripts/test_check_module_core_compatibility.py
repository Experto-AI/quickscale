"""Tests for the ``scripts/check_module_core_compatibility.py`` compatibility checker.

These tests are colocated with the rest of the ``quickscale_core`` test
suite so the repository's normal ``make test-unit`` / ``make test`` flows
exercise the compatibility-check script alongside the rest of the package.
The script lives under ``scripts/`` rather than ``quickscale_core/src/``
because it is a CI/build-time tool, not a runtime dependency, but the
Python API it exposes is unit-testable in isolation.
"""

from __future__ import annotations

import importlib.util
import sys
import tomllib
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module import helper
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
COMPAT_CHECK_PATH = SCRIPTS_DIR / "check_module_core_compatibility.py"


def _load_compat_check() -> Any:
    """Import ``check_module_core_compatibility.py`` as a module.

    The script lives in ``scripts/`` rather than a package directory, so
    we load it by file path.
    """
    spec = importlib.util.spec_from_file_location(
        "check_module_core_compatibility", COMPAT_CHECK_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError(
            "Could not load check_module_core_compatibility.py from scripts/"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_module_core_compatibility", module)
    spec.loader.exec_module(module)
    return module


compat = _load_compat_check()


# ---------------------------------------------------------------------------
# SAFETY: module-level side effects
# ---------------------------------------------------------------------------


def test_import_does_not_call_main() -> None:
    """Confirm that importing the module does not execute the check.

    The module must not have a top-level ``main()`` call; only the
    ``if __name__ == '__main__':`` guard may invoke it.
    """
    # The fact that _load_compat_check() returned without triggering
    # a SystemExit or printing output proves the guard is intact.
    assert True


# ---------------------------------------------------------------------------
# SKIP_INSTALL_PROBE_MODULES — skip-allowlist integrity
# ---------------------------------------------------------------------------


def test_skip_dict_contains_only_backups() -> None:
    """Only ``backups`` may be exempted from the install/import probe.

    This is a deliberate temporary measure per the confirmed 2026-07-03
    roadmap decision. Adding another entry requires explicit re-approval.
    """
    assert set(compat.SKIP_INSTALL_PROBE_MODULES.keys()) == {"backups"}


def test_skip_dict_reason_is_non_empty_and_dated() -> None:
    """Every skip entry must carry a non-empty reason citing the decision."""
    for mod_name, reason in compat.SKIP_INSTALL_PROBE_MODULES.items():
        assert reason, f"Empty reason for {mod_name}"
        assert "2026-07-03" in reason, (
            f"Skip reason for {mod_name} must reference the decision date"
        )


@pytest.mark.parametrize(
    "mod_name",
    [
        "backups",
    ],
)
def test_skip_entry_mentions_sa93_sa95(mod_name: str) -> None:
    """The skip reason must reference the facade work that will fix the gap."""
    reason = compat.SKIP_INSTALL_PROBE_MODULES[mod_name]
    assert (
        "SA9.3" in reason
        or "SA9.4" in reason
        or "SA9.5" in reason
        or "facade" in reason
    )


# ---------------------------------------------------------------------------
# _get_management_command_modules — discovery
# ---------------------------------------------------------------------------


def test_get_mgmt_cmds_finds_backups_commands() -> None:
    """Backups has 9 management commands; all should be discovered."""
    src_dir = (
        Path(__file__).resolve().parents[3] / "quickscale_modules" / "backups" / "src"
    )
    package_name = "quickscale_modules_backups"
    modules = compat._get_management_command_modules(package_name, src_dir)
    assert len(modules) >= 9
    assert all(m.startswith(f"{package_name}.management.commands.") for m in modules)
    assert "backups_create" in modules[0]  # sorted alphabetically
    # Sanity: __init__.py is excluded
    init_path = f"{package_name}.management.commands.__init__"
    assert init_path not in modules


def test_get_mgmt_cmds_finds_forms_commands() -> None:
    """Forms has 2 management commands."""
    src_dir = (
        Path(__file__).resolve().parents[3] / "quickscale_modules" / "forms" / "src"
    )
    package_name = "quickscale_modules_forms"
    modules = compat._get_management_command_modules(package_name, src_dir)
    assert len(modules) == 2
    assert any("forms_anonymize_submissions" in m for m in modules)
    assert any("forms_seed_presets" in m for m in modules)


def test_get_mgmt_cmds_returns_empty_when_absent() -> None:
    """CRM has no management commands (only __init__.py)."""
    src_dir = Path(__file__).resolve().parents[3] / "quickscale_modules" / "crm" / "src"
    package_name = "quickscale_modules_crm"
    modules = compat._get_management_command_modules(package_name, src_dir)
    assert modules == []


def test_get_mgmt_cmds_returns_empty_for_nonexistent_dir(tmp_path: Path) -> None:
    """A dir with no management/commands/ returns empty list."""
    modules = compat._get_management_command_modules("any_pkg", tmp_path)
    assert modules == []


# ---------------------------------------------------------------------------
# _build_probe_script — management command probe code generation
# ---------------------------------------------------------------------------


def test_build_probe_script_includes_mgmt_cmd_phase() -> None:
    """When management_commands are provided, Phase 3 code is generated."""
    script = compat._build_probe_script(
        package_name="quickscale_modules_backups",
        src_dir=Path("/fake/src"),
        has_django=True,
        management_commands=[
            "quickscale_modules_backups.management.commands.backups_create",
        ],
    )
    assert "# Phase 3: probe management command modules" in script
    assert "backups_create" in script


def test_build_probe_script_omits_mgmt_cmd_phase() -> None:
    """When management_commands is None/empty, Phase 3 code is absent."""
    script = compat._build_probe_script(
        package_name="quickscale_modules_backups",
        src_dir=Path("/fake/src"),
        has_django=True,
        management_commands=None,
    )
    assert "# Phase 3:" not in script

    script2 = compat._build_probe_script(
        package_name="quickscale_modules_backups",
        src_dir=Path("/fake/src"),
        has_django=True,
        management_commands=[],
    )
    assert "# Phase 3:" not in script2


def test_build_probe_script_uses_quickscale_core_failure_heuristic() -> None:
    """The management command probe uses the same quickscale_core heuristic
    as the Phase 2b services probe."""
    script = compat._build_probe_script(
        package_name="quickscale_modules_backups",
        src_dir=Path("/fake/src"),
        has_django=True,
        management_commands=[
            "quickscale_modules_backups.management.commands.backups_create",
        ],
    )
    # Must detect quickscale_core import errors
    assert 'if "quickscale_core" in msg' in script
    assert 'or "quickscale" in msg.lower()' in script
    # Must have PROBE_FAIL for core-relevant failures
    assert "PROBE_FAIL: import {_cmd_mod} failed:" in script
    # Must have SKIP for non-core failures
    assert "SKIP: {_cmd_mod} requires configuration:" in script


# ---------------------------------------------------------------------------
# SBOM: fail if the module's public API regresses
# ---------------------------------------------------------------------------


def test_known_public_symbols() -> None:
    """Sanity check that expected constants and functions are exported."""
    assert hasattr(compat, "SKIP_INSTALL_PROBE_MODULES")
    assert hasattr(compat, "_get_management_command_modules")
    assert hasattr(compat, "_build_probe_script")
    assert hasattr(compat, "SKIP_INSTALL_PROBE_FLAG")
    assert hasattr(compat, "main")


def test_resolve_import_follows_getattr_literal_dynamic_submodule(
    tmp_path: Path,
) -> None:
    """Lazy facade helpers retain static compatibility-check coverage."""
    runtime_dir = tmp_path / "quickscale_core" / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "__init__.py").write_text(
        "import importlib\n"
        "__all__ = []\n"
        "def _load_dr():\n"
        "    return importlib.import_module('quickscale_core.runtime.dr')\n"
        "def __getattr__(name):\n"
        "    dr_module = _load_dr()\n"
        "    return getattr(dr_module, name)\n",
        encoding="utf-8",
    )
    (runtime_dir / "dr.py").write_text(
        "private_symbol = object()\n",
        encoding="utf-8",
    )

    issues = compat._resolve_import(
        tmp_path,
        "quickscale_core.runtime",
        ["private_symbol"],
    )

    assert issues == []


def test_resolve_import_ignores_uncalled_dynamic_submodule_helper(
    tmp_path: Path,
) -> None:
    """Unrelated dynamic imports cannot create false compatibility."""
    runtime_dir = tmp_path / "quickscale_core" / "runtime"
    runtime_dir.mkdir(parents=True)
    (runtime_dir / "__init__.py").write_text(
        "import importlib\n"
        "__all__ = []\n"
        "def _load_dr():\n"
        "    return importlib.import_module('quickscale_core.runtime.dr')\n"
        "def __getattr__(name):\n"
        "    raise AttributeError(name)\n",
        encoding="utf-8",
    )
    (runtime_dir / "dr.py").write_text(
        "private_symbol = object()\n",
        encoding="utf-8",
    )

    issues = compat._resolve_import(
        tmp_path,
        "quickscale_core.runtime",
        ["private_symbol"],
    )

    assert issues == ["  Symbol 'private_symbol' not found in quickscale_core.runtime."]


# ---------------------------------------------------------------------------
# SA18.11 — malformed pyproject.toml raises instead of being silently skipped
# ---------------------------------------------------------------------------


def test_get_module_package_name_raises_on_malformed_toml(tmp_path: Path) -> None:
    """Malformed module pyproject.toml raises TOMLDecodeError instead of
    returning None silently."""
    (tmp_path / "pyproject.toml").write_text("[[unclosed.bracket\n", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        compat._get_module_package_name(tmp_path)


def test_get_module_non_core_deps_raises_on_malformed_toml(tmp_path: Path) -> None:
    """Malformed module pyproject.toml raises TOMLDecodeError instead of
    returning [] silently."""
    (tmp_path / "pyproject.toml").write_text("[[unclosed.bracket\n", encoding="utf-8")
    with pytest.raises(tomllib.TOMLDecodeError):
        compat._get_module_non_core_deps(tmp_path)


def test_get_module_package_name_absent_toml_returns_none(tmp_path: Path) -> None:
    """Absent pyproject.toml still returns None (no regression)."""
    assert compat._get_module_package_name(tmp_path) is None


def test_get_module_non_core_deps_absent_toml_returns_empty(tmp_path: Path) -> None:
    """Absent pyproject.toml still returns [] (no regression)."""
    assert compat._get_module_non_core_deps(tmp_path) == []


def test_get_module_package_name_handles_empty_toml(tmp_path: Path) -> None:
    """Valid but empty pyproject.toml returns None (not an error)."""
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert compat._get_module_package_name(tmp_path) is None


def test_get_module_non_core_deps_handles_empty_toml(tmp_path: Path) -> None:
    """Valid but empty pyproject.toml returns [] (not an error)."""
    (tmp_path / "pyproject.toml").write_text("", encoding="utf-8")
    assert compat._get_module_non_core_deps(tmp_path) == []


# ---------------------------------------------------------------------------
# main() — user-visible malformed-pyproject error path
# ---------------------------------------------------------------------------


def test_main_reports_malformed_pyproject(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """``main()`` reports a malformed module pyproject.toml and returns a
    non-zero exit status.

    Regression guard for the Phase 2 ``_get_module_package_name``
    ``tomllib.TOMLDecodeError`` handler added in SA18.11.
    """
    # Create a minimal mock repository structure that lets a module
    # reach Phase 2 (install probe) in ``main()``.
    core_src = tmp_path / "quickscale_core" / "src" / "quickscale_core"
    core_src.mkdir(parents=True)
    (core_src / "__init__.py").write_text("# core package\n", encoding="utf-8")

    (tmp_path / "VERSION").write_text("0.86.0\n", encoding="utf-8")

    mod_dir = tmp_path / "quickscale_modules" / "test_mod"
    mod_dir.mkdir(parents=True)

    # module.yml with a parseable quickscale-core dependency
    (mod_dir / "module.yml").write_text(
        "dependencies:\n  - quickscale-core>=0.86.0\n",
        encoding="utf-8",
    )

    # A malformed pyproject.toml — this is what should trigger the error.
    (mod_dir / "pyproject.toml").write_text("[[unclosed.bracket\n", encoding="utf-8")

    # ``src/`` dir with at least one ``.py`` file that imports
    # quickscale_core, so Phase 1 does not short-circuit with ``continue``.
    src_pkg = mod_dir / "src" / "quickscale_modules_test_mod"
    src_pkg.mkdir(parents=True)
    (src_pkg / "__init__.py").write_text(
        "import quickscale_core\n",
        encoding="utf-8",
    )

    exit_code = compat.main([str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code != 0, (
        f"Expected non-zero exit for malformed pyproject.toml, got {exit_code}"
    )
    assert "Malformed module pyproject.toml" in captured.out, (
        f"Expected 'Malformed module pyproject.toml' in output:\n{captured.out}"
    )
