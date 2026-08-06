"""Direct regressions for publish-module inventory selection."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

import scripts.publish_module as publish_module
from quickscale_core.contracts import module_discovery


def _write_manifests(root: Path, names: list[str]) -> None:
    for name in names:
        module = root / name
        module.mkdir()
        (module / "module.yml").write_text(f"name: {name}\n")


def test_list_modules_uses_authoritative_inventory_and_picks_up_thirteenth(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A real manifest is picked up while a bare placeholder is excluded."""
    names = [f"module_{index:02d}" for index in range(12)] + ["reports"]
    _write_manifests(tmp_path, names)
    (tmp_path / "teams").mkdir()

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(tmp_path)
        monkeypatch.setattr(module_discovery, "AUTHORITATIVE_MODULE_COUNT", 13)
        assert publish_module._list_modules() == sorted(names)
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_list_modules_rejects_placeholder_manifest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "teams").mkdir()
    (tmp_path / "teams" / "module.yml").write_text("name: teams\n")

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(tmp_path)
        monkeypatch.setattr(module_discovery, "AUTHORITATIVE_MODULE_COUNT", 1)
        with pytest.raises(module_discovery.ImproperlyConfigured, match="placeholder"):
            publish_module._list_modules()
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_list_modules_fails_closed_when_authoritative_contract_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A missing inventory contract cannot fall back to directory names."""
    (tmp_path / "billing").mkdir()
    (tmp_path / "teams").mkdir()
    monkeypatch.setattr(publish_module, "_REPO_ROOT", tmp_path)
    monkeypatch.setitem(sys.modules, "quickscale_core.contracts.module_discovery", None)

    with pytest.raises(ModuleNotFoundError):
        publish_module._list_modules()
