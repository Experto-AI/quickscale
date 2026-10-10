"""Rule 1 (D3) off/on parity for every shipped module adapter.

Switching a module off keeps its Django apps and middleware: an adapter's
``enabled: false`` branch must never return fewer apps or middleware than its
``enabled: true`` branch (coherence proposal 1, merged into decisions rule 1).
The check is closed-world over the shipped modules under ``quickscale_modules``
and calls each module's real adapter.
"""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any, Callable

import pytest

from quickscale_core.module_wiring import ModuleWiringSpec

REPO_ROOT = Path(__file__).resolve().parents[2]
MODULES_ROOT = REPO_ROOT / "quickscale_modules"

Adapter = Callable[[dict[str, Any]], ModuleWiringSpec]


def _module_names() -> list[str]:
    """Return the shipped module names, sorted."""
    return sorted(
        path.name
        for path in MODULES_ROOT.iterdir()
        if path.is_dir() and (path / "module.yml").is_file()
    )


def _shipped_adapter(module_name: str) -> Adapter:
    module = importlib.import_module(f"quickscale_modules_{module_name}.adapter")
    return module.get_manifest_adapter()


def parity_violations(adapter: Adapter) -> list[str]:
    """Return the wiring an off spec drops relative to its on spec."""
    off = adapter({"enabled": False}, project_package="parity_probe")
    on = adapter({"enabled": True}, project_package="parity_probe")
    violations: list[str] = []
    missing_apps = [app for app in on.apps if app not in off.apps]
    if missing_apps:
        violations.append(f"off drops apps: {missing_apps}")
    missing_middleware = [mw for mw in on.middleware if mw not in off.middleware]
    if missing_middleware:
        violations.append(f"off drops middleware: {missing_middleware}")
    missing_settings = sorted(set(on.settings) - set(off.settings))
    if missing_settings:
        violations.append(f"off drops settings: {missing_settings}")
    return violations


def test_shipped_module_set_is_closed_world() -> None:
    """The parity check covers the full shipped module set."""
    assert len(_module_names()) == 12


@pytest.mark.parametrize("module_name", _module_names())
def test_off_keeps_apps_and_middleware(module_name: str) -> None:
    """Every shipped adapter keeps its apps and middleware while off."""
    assert parity_violations(_shipped_adapter(module_name)) == []


def test_parity_comparison_detects_a_dropping_adapter() -> None:
    """Control: an off branch that drops apps or settings fails the check."""

    def breaking_adapter(
        options: dict[str, Any], *, project_package: str | None = None
    ) -> ModuleWiringSpec:
        del project_package
        enabled = bool(options.get("enabled", True))
        return ModuleWiringSpec(
            apps=("quickscale_modules_demo",) if enabled else (),
            settings={"QUICKSCALE_DEMO_ENABLED": enabled} if enabled else {},
        )

    assert parity_violations(breaking_adapter) == [
        "off drops apps: ['quickscale_modules_demo']",
        "off drops settings: ['QUICKSCALE_DEMO_ENABLED']",
    ]
