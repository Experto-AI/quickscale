"""
Control-case tests for ``scripts/check_split_facade_imports.py``.

The gate fails when a private module (``_*.py``) reaches a facade of its own
distribution and passes when it imports the sibling that defines the name.
Each case builds a throwaway repository layout with its own ``pyproject.toml``
and ``src/`` tree and calls ``main([...])`` directly, so the positive and
negative controls both exercise the real detector.  One case runs over the
real repository and fails when a package carrying ``_*.py`` split files sits
outside the layout-derived scope.
"""

from __future__ import annotations

import importlib.util
import os
import sys
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
CHECKER_PATH = SCRIPTS_DIR / "check_split_facade_imports.py"

_SKIP_DIRS = frozenset({"node_modules", "__pycache__", ".venv", "venv"})

_CLI = "quickscale_cli"
_CLI_COMMANDS = f"{_CLI}/src/{_CLI}/commands"
_CLI_UTILS = f"{_CLI}/src/{_CLI}/utils"


def _load_checker() -> Any:
    spec = importlib.util.spec_from_file_location("check_split_facade_imports", CHECKER_PATH)
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load check_split_facade_imports.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_split_facade_imports", module)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


def _write(root: Path, relative_file: str, source: str) -> None:
    path = root / relative_file
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")


def _make_distribution(
    root: Path,
    family: str = _CLI,
    packages: tuple[str, ...] = ("commands", "utils"),
) -> None:
    """Create a minimal first-party distribution with the named packages."""
    _write(root, f"{family}/pyproject.toml", '[project]\nname = "fixture"\n')
    _write(root, f"{family}/src/{family}/__init__.py", "")
    for package in packages:
        _write(root, f"{family}/src/{family}/{package}/__init__.py", "")


def _split_family(root: Path) -> None:
    """Create a facade plus its private implementation, mirroring the real shape."""
    _write(
        root,
        f"{_CLI_COMMANDS}/facade.py",
        "from quickscale_cli.commands._impl import defined_here\n",
    )
    _write(root, f"{_CLI_COMMANDS}/_impl.py", "defined_here = 1\n")


def test_clean_tree_passes(tmp_path: Path) -> None:
    _make_distribution(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_clean.py",
        source="from quickscale_cli.commands._impl import defined_here\n",
    )
    assert checker.main([str(tmp_path)]) == 0


def test_private_module_importing_facade_module_fails(tmp_path: Path) -> None:
    _make_distribution(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad.py",
        source="import quickscale_cli.commands.facade as facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_from_package_import_facade_fails(tmp_path: Path) -> None:
    _make_distribution(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad_from.py",
        source="from quickscale_cli.commands import facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_relative_facade_import_fails(tmp_path: Path) -> None:
    _make_distribution(tmp_path)
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad_relative.py",
        source="from . import facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_private_module_importing_a_definer_passes(tmp_path: Path) -> None:
    """A public module that defines its own names is not a facade."""
    _make_distribution(tmp_path)
    _write(tmp_path, f"{_CLI_COMMANDS}/definer.py", "value = 1\n")
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_uses_definer.py",
        source="from quickscale_cli.commands.definer import value\n",
    )
    assert checker.main([str(tmp_path)]) == 0


def test_facade_across_sibling_directory_fails(tmp_path: Path) -> None:
    """The CLI family spans commands and utils: both facades are covered."""
    _make_distribution(tmp_path)
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


def test_re_exported_name_import_fails(tmp_path: Path) -> None:
    """Importing a name the facade only re-exports reaches the facade surface."""
    _make_distribution(tmp_path)
    _write(
        tmp_path,
        f"{_CLI_COMMANDS}/facade.py",
        "from quickscale_cli.commands._impl import defined_here as defined_here\n",
    )
    _write(tmp_path, f"{_CLI_COMMANDS}/_impl.py", "defined_here = 1\n")
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_bad_name.py",
        source="from quickscale_cli.commands.facade import defined_here\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_name_the_facade_defines_itself_passes(tmp_path: Path) -> None:
    """A name the public module defines is that name's definer."""
    _make_distribution(tmp_path)
    _write(
        tmp_path,
        f"{_CLI_COMMANDS}/facade.py",
        "from quickscale_cli.commands._impl import defined_here as defined_here\n"
        "\n"
        "def helper() -> int:\n"
        "    return 1\n",
    )
    _write(tmp_path, f"{_CLI_COMMANDS}/_impl.py", "defined_here = 1\n")
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_ok_name.py",
        source="from quickscale_cli.commands.facade import helper\n",
    )
    assert checker.main([str(tmp_path)]) == 0


def test_from_package_private_module_import_marks_a_facade(tmp_path: Path) -> None:
    """``from . import _impl`` is an ordinary private-sibling import form."""
    _make_distribution(tmp_path)
    _write(
        tmp_path,
        f"{_CLI_COMMANDS}/facade.py",
        "from . import _impl\n\nvalue = _impl.defined_here\n",
    )
    _write(tmp_path, f"{_CLI_COMMANDS}/_impl.py", "defined_here = 1\n")
    _write(
        root=tmp_path,
        relative_file=f"{_CLI_COMMANDS}/_consumer.py",
        source="import quickscale_cli.commands.facade as facade\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_new_distribution_is_discovered_without_a_hand_list(tmp_path: Path) -> None:
    """Scope is the layout: a distribution the gate never named is still scanned."""
    _make_distribution(tmp_path, family="quickscale_extra", packages=("extras",))
    _write(
        tmp_path,
        "quickscale_extra/src/quickscale_extra/extras/facade.py",
        "from quickscale_extra.extras._impl import defined_here\n",
    )
    _write(
        tmp_path,
        "quickscale_extra/src/quickscale_extra/extras/_impl.py",
        "defined_here = 1\n",
    )
    _write(
        tmp_path,
        "quickscale_extra/src/quickscale_extra/extras/_bad.py",
        "from quickscale_extra.extras.facade import defined_here\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_package_without_its_own_facade_is_still_scanned(tmp_path: Path) -> None:
    """A private module reaching a sibling package's facade still fails."""
    _make_distribution(tmp_path, packages=("commands", "solo"))
    _split_family(tmp_path)
    _write(
        root=tmp_path,
        relative_file=f"{_CLI}/src/{_CLI}/solo/_private.py",
        source="from quickscale_cli.commands.facade import defined_here\n",
    )
    assert checker.main([str(tmp_path)]) == 1


def test_cross_distribution_facade_import_passes(tmp_path: Path) -> None:
    """A facade in another distribution is not this package's facade."""
    _make_distribution(tmp_path, family="quickscale_a", packages=("alpha",))
    _make_distribution(tmp_path, family="quickscale_b", packages=("beta",))
    _write(
        tmp_path,
        "quickscale_a/src/quickscale_a/alpha/facade.py",
        "from quickscale_a.alpha._impl import defined_here\n",
    )
    _write(tmp_path, "quickscale_a/src/quickscale_a/alpha/_impl.py", "defined_here = 1\n")
    _write(
        tmp_path,
        "quickscale_b/src/quickscale_b/beta/_user.py",
        "from quickscale_a.alpha.facade import defined_here\n",
    )
    assert checker.main([str(tmp_path)]) == 0


def test_no_distribution_fails_closed(tmp_path: Path) -> None:
    """Layout discovery finding nothing is an inspection failure, not a pass."""
    assert checker.main([str(tmp_path)]) == 2


def test_parse_failure_fails_closed(tmp_path: Path) -> None:
    _make_distribution(tmp_path)
    _write(tmp_path, f"{_CLI_COMMANDS}/_broken.py", "def broken(:\n")
    assert checker.main([str(tmp_path)]) == 2


def test_reports_offending_file_and_import(tmp_path: Path, capsys: Any) -> None:
    _make_distribution(tmp_path)
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


def _split_packages_in(package: Path) -> set[Path]:
    """Independently collect packages carrying ``_*.py`` split files."""
    found: set[Path] = set()
    if not (package / "__init__.py").is_file():
        return found
    if any(path.stem.startswith("_") and path.stem != "__init__" for path in package.glob("*.py")):
        found.add(package.resolve())
    for child in sorted(package.iterdir()):
        if child.is_dir() and child.name != "__pycache__":
            found |= _split_packages_in(child)
    return found


def test_every_real_split_package_is_inside_the_derived_scope() -> None:
    """A package with ``_*.py`` split files must never sit outside the scope."""
    repo_root = SCRIPTS_DIR.parent
    scope = {package.directory.resolve() for package in checker.discover_scope(repo_root).values()}
    split_packages: set[Path] = set()
    for directory, dirnames, _ in os.walk(repo_root):
        dirnames[:] = sorted(
            name for name in dirnames if not name.startswith(".") and name not in _SKIP_DIRS
        )
        src = Path(directory)
        if src.name != "src":
            continue
        for candidate in sorted(src.iterdir()):
            if candidate.is_dir():
                split_packages |= _split_packages_in(candidate)
    assert split_packages, "real-tree scan found no split package"
    missing = sorted(str(package.relative_to(repo_root)) for package in split_packages - scope)
    assert not missing, f"split packages outside the derived scope: {missing}"
