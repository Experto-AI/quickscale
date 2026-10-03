"""
Control-case tests for ``scripts/check_split_facade_imports.py``.

The gate fails when a private module (``_*.py``) imports its package's facade
and passes when it imports the sibling that defines the name.  Each case here
builds a throwaway repository layout and calls ``main([...])`` directly, so
the positive and negative controls both exercise the real detector.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
CHECKER_PATH = SCRIPTS_DIR / "check_split_facade_imports.py"


def _load_checker() -> Any:
    spec = importlib.util.spec_from_file_location("check_split_facade_imports", CHECKER_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load check_split_facade_imports.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_split_facade_imports", module)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()

_CLI_COMMANDS = "quickscale_cli/src/quickscale_cli/commands"
_CLI_UTILS = "quickscale_cli/src/quickscale_cli/utils"
_DR_ENGINE = "quickscale_core/src/quickscale_core/dr_engine"
_BILLING = "quickscale_modules/billing/src/quickscale_modules_billing"

_FAMILY_DIRS = (_CLI_COMMANDS, _CLI_UTILS, _DR_ENGINE, _BILLING)


def _make_repo(root: Path) -> None:
    """Create every scanned family directory so only the test files differ."""
    for relative in _FAMILY_DIRS:
        directory = root / relative
        directory.mkdir(parents=True)
        (directory / "__init__.py").write_text("", encoding="utf-8")


def _write(root: Path, relative_file: str, source: str) -> None:
    path = root / relative_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _split_family(root: Path) -> None:
    """Create a facade plus its private implementation, mirroring the real shape."""
    _write(
        root,
        f"{_CLI_COMMANDS}/facade.py",
        "from quickscale_cli.commands._impl import defined_here\n",
    )
    _write(root, f"{_CLI_COMMANDS}/_impl.py", "defined_here = 1\n")


def test_clean_tree_passes(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_clean.py",
        source="from quickscale_cli.commands._impl import defined_here\n",
    )
    assert checker.main([str(tmp_path)]) == 0


def test_private_module_importing_facade_fails(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad.py",
        source="import quickscale_cli.commands.facade as facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_from_package_import_facade_fails(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad_from.py",
        source="from quickscale_cli.commands import facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_relative_facade_import_fails(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad_relative.py",
        source="from . import facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_private_module_importing_a_definer_passes(tmp_path: Path) -> None:
    """A public module that defines its own names is not a facade."""
    _make_repo(tmp_path)
    _write(tmp_path, f"{_CLI_COMMANDS}/definer.py", "value = 1\n")
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_uses_definer.py",
        source="from quickscale_cli.commands.definer import value\n",
    )
    assert checker.main([str(tmp_path)]) == 0


def test_facade_across_sibling_directory_fails(tmp_path: Path) -> None:
    """The CLI family spans commands and utils: both facades are covered."""
    _make_repo(tmp_path)
    _write(
        tmp_path,
        f"{_CLI_UTILS}/facade.py",
        "from quickscale_cli.utils._impl import defined_here\n",
    )
    _write(tmp_path, f"{_CLI_UTILS}/_impl.py", "defined_here = 1\n")
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad_cross.py",
        source="from quickscale_cli.utils.facade import defined_here\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_missing_scan_family_fails_closed(tmp_path: Path) -> None:
    assert checker.main([str(tmp_path)]) == 2


def test_one_missing_family_root_fails_closed(tmp_path: Path) -> None:
    """A single absent directory in a family fails closed, not silently skipped."""
    _make_repo(tmp_path)
    import shutil

    shutil.rmtree(tmp_path / _CLI_UTILS)
    assert checker.main([str(tmp_path)]) == 2


def test_parse_failure_fails_closed(tmp_path: Path) -> None:
    _make_repo(tmp_path)
    _write(tmp_path, f"{_CLI_COMMANDS}/_broken.py", "def broken(:\n")
    assert checker.main([str(tmp_path)]) == 2


def test_reports_offending_file_and_import(tmp_path: Path, capsys: Any) -> None:
    _make_repo(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad.py",
        source="import quickscale_cli.commands.facade as facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1
    captured = capsys.readouterr()
    assert "_bad.py:1" in captured.out
    assert "quickscale_cli.commands.facade" in captured.out
