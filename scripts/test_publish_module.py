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


# ---------------------------------------------------------------------------
# F-002: direct single-module selector must require authoritative-inventory
# membership before release-authority checks, origin prompts, subtree split,
# or push.
# ---------------------------------------------------------------------------


def _patch_selector_surroundings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the selector at *tmp_path* and neutralize git bootstrap calls."""
    monkeypatch.setattr(publish_module, "_REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        publish_module, "build_publication_git_runner", lambda git_executable: object()
    )
    monkeypatch.setattr(publish_module, "is_git_repo", lambda path, runner: True)


def _spy_post_guard_path(monkeypatch: pytest.MonkeyPatch, reached: list[str]) -> None:
    """Record any post-guard release/origin/prompt/mutation call that runs."""
    for name in (
        "_check_release_authoritative",
        "validate_publication_origin",
        "_confirm_uncommitted_changes",
        "_maybe_clean_subtree_cache",
        "_publish_module",
    ):
        monkeypatch.setattr(
            publish_module,
            name,
            lambda *args, _name=name, **kwargs: reached.append(_name),
        )


def test_direct_selector_rejects_placeholder_before_prompts_or_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-002: 'teams' fails closed before any release/prompt/split/push path."""
    base = tmp_path / "quickscale_modules"
    base.mkdir()
    _write_manifests(base, [f"module_{index:02d}" for index in range(12)])
    (base / "teams").mkdir()
    _patch_selector_surroundings(tmp_path, monkeypatch)

    reached: list[str] = []
    _spy_post_guard_path(monkeypatch, reached)

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(base)
        monkeypatch.setattr(
            sys,
            "argv",
            ["publish_module.py", "teams", "--expected-remote-sha", "ABSENT"],
        )
        with pytest.raises(SystemExit) as excinfo:
            publish_module.main()
        assert excinfo.value.code == 1
        assert reached == []
        out = capsys.readouterr().out
        assert "placeholder inventory only" in out
        assert "teams" in out
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_direct_selector_rejects_unapproved_thirteenth_before_prompts_or_mutation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-002: an unapproved thirteenth real module fails on inventory count drift."""
    base = tmp_path / "quickscale_modules"
    base.mkdir()
    _write_manifests(base, [f"module_{index:02d}" for index in range(12)] + ["reports"])
    _patch_selector_surroundings(tmp_path, monkeypatch)

    reached: list[str] = []
    _spy_post_guard_path(monkeypatch, reached)

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(base)
        monkeypatch.setattr(
            sys,
            "argv",
            ["publish_module.py", "reports", "--expected-remote-sha", "ABSENT"],
        )
        with pytest.raises(SystemExit) as excinfo:
            publish_module.main()
        assert excinfo.value.code == 1
        assert reached == []
        out = capsys.readouterr().out
        assert "count drift" in out
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_direct_selector_preserves_valid_authoritative_module_flow(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """F-002: a valid authoritative name proceeds past the guard unchanged."""
    names = [f"module_{index:02d}" for index in range(12)]
    base = tmp_path / "quickscale_modules"
    base.mkdir()
    _write_manifests(base, names)
    _patch_selector_surroundings(tmp_path, monkeypatch)

    reached: list[str] = []
    monkeypatch.setattr(
        publish_module,
        "_check_release_authoritative",
        lambda runner: reached.append("release"),
    )
    monkeypatch.setattr(
        publish_module,
        "validate_publication_origin",
        lambda path, runner: reached.append("origin"),
    )
    monkeypatch.setattr(
        publish_module,
        "_confirm_uncommitted_changes",
        lambda runner: True,
    )
    monkeypatch.setattr(
        publish_module,
        "_maybe_clean_subtree_cache",
        lambda clean: reached.append("clean"),
    )
    monkeypatch.setattr(
        publish_module,
        "_publish_module",
        lambda module_name, **kwargs: reached.append("publish"),
    )

    original_base = module_discovery._modules_base_path
    try:
        module_discovery.set_modules_base_path(base)
        monkeypatch.setattr(
            sys,
            "argv",
            ["publish_module.py", names[0], "--expected-remote-sha", "ABSENT"],
        )
        publish_module.main()
        assert reached == ["release", "origin", "clean", "publish"]
    finally:
        module_discovery.set_modules_base_path(original_base)


def test_require_authoritative_module_rejects_unknown_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-002: a name absent from a healthy inventory hits the generic rejection."""
    authoritative_names = [f"module_{index:02d}" for index in range(12)]
    monkeypatch.setattr(publish_module, "_list_modules", lambda: authoritative_names)

    with pytest.raises(SystemExit) as excinfo:
        publish_module._require_authoritative_module("nonexistent")
    assert excinfo.value.code == 1
    out = capsys.readouterr().out
    assert "not in the authoritative shipped-module inventory" in out
    assert "nonexistent" in out
    for name in authoritative_names:
        assert f"  - {name}" in out
