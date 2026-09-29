"""Focused tests for the Jinja2 lint-context renderer's module discovery."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

import scripts.render_j2_template as render_j2_template


def _fake_script_path(tmp_path: Path) -> Path:
    """Return a script path whose sibling quickscale_modules/ lives in tmp_path."""
    return tmp_path / "scripts" / "render_j2_template.py"


def test_lint_context_discovers_every_shipped_module(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rendered lint context derives its module set from the manifests."""
    monkeypatch.delenv("SELECTED_MODULES", raising=False)
    modules_dir = Path(render_j2_template.__file__).resolve().parents[1] / "quickscale_modules"
    discovered = sorted(entry.parent.name for entry in modules_dir.glob("*/module.yml"))
    context = render_j2_template.get_lint_context()
    assert context["selected_modules"] == discovered
    assert "orgs" in context["selected_modules"]
    assert "social" in context["selected_modules"]


def test_discovery_fails_loudly_without_workspace(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A missing module workspace must fail rather than render nothing."""
    fake_script = _fake_script_path(tmp_path)
    fake_script.parent.mkdir()
    monkeypatch.setattr(render_j2_template, "__file__", str(fake_script))
    with pytest.raises(SystemExit, match="module workspace not found"):
        render_j2_template._discover_modules()


def test_discovery_rejects_incomplete_module_directory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A directory without module.yml fails closed instead of being skipped."""
    (tmp_path / "quickscale_modules" / "broken").mkdir(parents=True)
    fake_script = _fake_script_path(tmp_path)
    fake_script.parent.mkdir()
    monkeypatch.setattr(render_j2_template, "__file__", str(fake_script))
    with pytest.raises(SystemExit, match="without module.yml"):
        render_j2_template._discover_modules()


def test_list_modules_mode_emits_json_with_exclusion() -> None:
    """--list-modules prints the discovered set and honours --exclude."""
    script = Path(render_j2_template.__file__).resolve()
    result = subprocess.run(
        [sys.executable, str(script), "--list-modules", "--exclude", "social"],
        cwd=script.parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    names = json.loads(result.stdout)
    assert "social" not in names
    assert "orgs" in names
    assert names == sorted(names)
