"""Focused tests for quickscale_cli package init fallback branches."""

from __future__ import annotations

import builtins
import importlib
from pathlib import Path
import sys

import quickscale_cli


def _reload_quickscale_cli_without_embedded_version(
    monkeypatch,
    *,
    version_file_exists: bool,
    version_text: str = "0.0.0\n",
) -> None:
    real_import = builtins.__import__
    real_exists = Path.exists
    real_read_text = Path.read_text

    monkeypatch.delitem(sys.modules, "quickscale_cli._version", raising=False)

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        package = globals.get("__package__") if globals else None
        if name == "quickscale_cli._version" or (
            level == 1 and name == "_version" and package == "quickscale_cli"
        ):
            raise ImportError("embedded _version unavailable")
        return real_import(name, globals, locals, fromlist, level)

    def fake_exists(path: Path) -> bool:
        if path.name == "VERSION":
            return version_file_exists
        return real_exists(path)

    def fake_read_text(path: Path, encoding: str = "utf8") -> str:
        if path.name == "VERSION":
            return version_text
        return real_read_text(path, encoding=encoding)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    monkeypatch.setattr(Path, "exists", fake_exists)
    monkeypatch.setattr(Path, "read_text", fake_read_text)

    importlib.reload(quickscale_cli)


def test_init_reads_repository_version_file_when_embedded_version_is_missing(
    monkeypatch,
) -> None:
    _reload_quickscale_cli_without_embedded_version(
        monkeypatch,
        version_file_exists=True,
        version_text="2.3.4\n",
    )

    assert quickscale_cli.__version__ == "2.3.4"
    assert quickscale_cli.VERSION == (2, 3, 4)

    monkeypatch.undo()
    importlib.reload(quickscale_cli)


def test_init_falls_back_to_zero_version_without_embedded_or_repo_version(
    monkeypatch,
) -> None:
    _reload_quickscale_cli_without_embedded_version(
        monkeypatch,
        version_file_exists=False,
    )

    assert quickscale_cli.__version__ == "0.0.0"
    assert quickscale_cli.VERSION == (0, 0, 0)

    monkeypatch.undo()
    importlib.reload(quickscale_cli)
