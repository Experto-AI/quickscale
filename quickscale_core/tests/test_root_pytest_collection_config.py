"""Regression coverage for root-level pytest collection configuration."""

from __future__ import annotations

from pathlib import Path
import tomllib

from _pytest.pathlib import resolve_pkg_root_and_module_name


ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = ROOT / "quickscale_modules"


def test_root_pytest_collects_module_conftests_under_unique_namespace_names() -> None:
    """All module conftests must resolve uniquely during bare-root collection."""
    root_config = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    pytest_config = root_config["tool"]["pytest"]["ini_options"]

    assert pytest_config["consider_namespace_packages"] is True

    conftests = sorted(MODULES_ROOT.glob("*/tests/conftest.py"))
    assert len(conftests) == 12

    module_names = [
        resolve_pkg_root_and_module_name(
            conftest,
            consider_namespace_packages=pytest_config["consider_namespace_packages"],
        )[1]
        for conftest in conftests
    ]
    assert len(set(module_names)) == len(conftests)
    assert all(name.endswith(".tests.conftest") for name in module_names)
