"""Tests for the ``scripts/check_module_core_imports.py`` import-linter gate.

These tests are colocated with the rest of the ``quickscale_core`` test
suite so normal ``make test-unit`` / ``make test`` flows exercise them.
The script lives under ``scripts/`` because it is a CI/build-time tool,
not a runtime dependency, but the Python API it exposes is unit-testable
in isolation.

SA89b review-driven additions:
  - CR-005: Ensure ``_is_quickscale_modules`` matches actual underscore-
    prefixed module packages (``quickscale_modules_backups`` etc.).
  - CR-006: Verify ``main()`` exits nonzero when a required scan root
    (``quickscale_modules/`` or ``quickscale_core/src/quickscale_core/``)
    is absent.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module import helper
# ---------------------------------------------------------------------------

SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
CHECKER_PATH = SCRIPTS_DIR / "check_module_core_imports.py"


def _load_checker() -> Any:
    """Import ``check_module_core_imports.py`` as a module by file path."""
    spec = importlib.util.spec_from_file_location(
        "check_module_core_imports", CHECKER_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load check_module_core_imports.py from scripts/")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("check_module_core_imports", module)
    spec.loader.exec_module(module)
    return module


checker = _load_checker()


# ---------------------------------------------------------------------------
# CR-005: _is_quickscale_modules — actual package matching
# ---------------------------------------------------------------------------


class TestIsQuickscaleModules:
    """``_is_quickscale_modules`` must detect dotted forms (quickscale_modules.name)
    AND actual installed package names (quickscale_modules_backups)."""

    @staticmethod
    def _is_qm(module: str | None) -> bool:
        """Wrapper to avoid descriptor-binding issues with staticmethod lookup."""
        return checker._ModulesImportLinterVisitor._is_quickscale_modules(module)

    @pytest.mark.parametrize(
        "module",
        [
            "quickscale_modules",
            "quickscale_modules.auth",
            "quickscale_modules.backups",
            "quickscale_modules.social",
            "quickscale_modules.storage",
            "quickscale_modules.notifications",
        ],
    )
    def test_dotted_form_matches(self, module: str) -> None:
        assert self._is_qm(module), f"Dotted form {module!r} should match"

    @pytest.mark.parametrize(
        "module",
        [
            "quickscale_modules_auth",
            "quickscale_modules_backups",
            "quickscale_modules_social",
            "quickscale_modules_storage",
            "quickscale_modules_notifications",
            "quickscale_modules_listings",
            "quickscale_modules_blog",
            "quickscale_modules_forms",
            "quickscale_modules_crm",
        ],
    )
    def test_underscore_package_matches(self, module: str) -> None:
        """CR-005 regression: underscore-prefixed actual packages must match."""
        assert self._is_qm(module), f"Underscore package {module!r} should match"

    @pytest.mark.parametrize(
        "module",
        [
            None,
            "",
            "quickscale",
            "quickscale_core",
            "quickscale_core.runtime",
            "quickscale_cli",
            "os",
            "django",
            "some_other_package",
        ],
    )
    def test_non_quickscale_modules_does_not_match(self, module: str | None) -> None:
        assert not self._is_qm(module), f"Non-module {module!r} should not match"


# ---------------------------------------------------------------------------
# CR-005: AST visitor — actual import statements
# ---------------------------------------------------------------------------


class TestModulesImportLinterVisitor:
    """Integration-level tests that the linter visitor detects real
    ``import quickscale_modules_<name>`` statements."""

    def _collect(self, source: str) -> list[tuple[int, str]]:
        import ast

        tree = ast.parse(source)
        visitor = checker._ModulesImportLinterVisitor()
        visitor.visit(tree)
        return visitor.violations

    def test_dotted_import_caught(self) -> None:
        violations = self._collect("import quickscale_modules.auth")
        assert len(violations) == 1
        assert violations[0][1] == "quickscale_modules.auth"

    def test_underscore_package_import_caught(self) -> None:
        """CR-005 regression: ``import quickscale_modules_backups`` is caught."""
        violations = self._collect("import quickscale_modules_backups")
        assert len(violations) == 1
        assert violations[0][1] == "quickscale_modules_backups"

    def test_underscore_package_from_import_caught(self) -> None:
        """CR-005 regression: ``from quickscale_modules_backups import ...``."""
        violations = self._collect("from quickscale_modules_backups import something")
        assert len(violations) == 1
        assert violations[0][1] == "quickscale_modules_backups"

    def test_multiple_underscore_imports_caught(self) -> None:
        violations = self._collect(
            "import quickscale_modules_auth, quickscale_modules_backups"
        )
        assert len(violations) == 2

    def test_core_import_not_caught(self) -> None:
        violations = self._collect("import quickscale_core.runtime")
        assert len(violations) == 0

    def test_stdlib_import_not_caught(self) -> None:
        violations = self._collect("import os\nimport sys\nfrom pathlib import Path")
        assert len(violations) == 0


# ---------------------------------------------------------------------------
# CR-006: Missing-root fail-hard behavior
# ---------------------------------------------------------------------------


class TestMainMissingRoot:
    """``main()`` must return nonzero when either required scan root is absent."""

    def test_both_roots_missing_returns_nonzero(self, tmp_path: Path) -> None:
        """When neither modules nor core source exists, main returns 1."""
        exit_code = checker.main([str(tmp_path)])
        assert exit_code != 0, "Expected nonzero exit when both scan roots are missing"

    def test_modules_root_missing_returns_nonzero(self, tmp_path: Path) -> None:
        """When only core source exists but modules is absent, main returns 1."""
        core_src = tmp_path / "quickscale_core" / "src" / "quickscale_core"
        core_src.mkdir(parents=True)
        (core_src / "__init__.py").write_text("# core\n", encoding="utf-8")

        exit_code = checker.main([str(tmp_path)])
        assert exit_code != 0, "Expected nonzero exit when modules root is missing"

    def test_core_src_missing_returns_nonzero(self, tmp_path: Path) -> None:
        """When only modules exists but core src is absent, main returns 1."""
        mod_dir = tmp_path / "quickscale_modules" / "test_mod" / "src"
        mod_dir.mkdir(parents=True)

        exit_code = checker.main([str(tmp_path)])
        assert exit_code != 0, "Expected nonzero exit when core source root is missing"

    def test_both_roots_present_returns_zero(self, tmp_path: Path) -> None:
        """When both roots exist with no violations, main returns 0."""
        core_src = tmp_path / "quickscale_core" / "src" / "quickscale_core"
        core_src.mkdir(parents=True)
        (core_src / "__init__.py").write_text("# core\n", encoding="utf-8")

        mod_dir = tmp_path / "quickscale_modules" / "test_mod" / "src"
        mod_dir.mkdir(parents=True)
        mod_pkg = mod_dir / "quickscale_modules_test_mod"
        mod_pkg.mkdir(parents=True)
        (mod_pkg / "__init__.py").write_text(
            "import quickscale_core.runtime\n", encoding="utf-8"
        )

        exit_code = checker.main([str(tmp_path)])
        assert exit_code == 0, (
            f"Expected zero exit when both roots present, got {exit_code}"
        )
