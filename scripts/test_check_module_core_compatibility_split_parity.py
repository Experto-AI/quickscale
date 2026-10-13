"""
Parity controls for the SA267(d) ``check_module_core_compatibility`` script split.

``check_module_core_compatibility`` keeps its pre-split surface through private
``_module_core_compat_*`` siblings.  These controls pin the preserved surface,
the split's structural invariants, the module homes of the moved callables,
and the exact gate diagnostics captured from the pre-split module, so a later
slice cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast as ast
import inspect
import os as os
import re as re
import subprocess as subprocess
import sys as sys
import tempfile as tempfile
import tomllib as tomllib
from collections.abc import Callable
from pathlib import Path
from typing import Any
from typing import Final as Final
from typing import cast as cast

import _module_core_compat_ast as ast_module
import _module_core_compat_probe as probe_module
import _module_core_compat_versions as versions_module
import check_module_core_compatibility as compat
import pytest

FROZEN_FACADE_SURFACE = (
    "CORE_DEP_NAME",
    "CORE_SRC_RELATIVE",
    "Final",
    "MODULES_DIR_RELATIVE",
    "MODULE_YML",
    "Path",
    "REPO_ROOT_ENV",
    "SKIP_INSTALL_PROBE_FLAG",
    "SKIP_INSTALL_PROBE_MODULES",
    "_CoreImportVisitor",
    "_DEFAULT_REPO_ROOT",
    "_MIN_VERSION_PATTERN",
    "_build_probe_script",
    "_collect_core_imports",
    "_collect_defined_names",
    "_collect_defined_names_internal",
    "_collect_getattr_dynamic_submodules",
    "_collect_lazy_symbol_names",
    "_collect_submodule_aliases",
    "_declared_core_spec",
    "_expected_core_spec",
    "_extract_min_core_version",
    "_get_core_dep_spec",
    "_get_management_command_modules",
    "_get_module_non_core_deps",
    "_get_module_package_name",
    "_get_pyproject_core_dep",
    "_module_path_to_fs_path",
    "_parse_module_yml",
    "_parse_version_tuple",
    "_poetry_spec_to_pep440",
    "_probe_module_install_import",
    "_read_version_file",
    "_resolve_import",
    "_resolve_name_via_getattr_chain",
    "annotations",
    "ast",
    "cast",
    "main",
    "os",
    "re",
    "subprocess",
    "sys",
    "tempfile",
    "tomllib",
)
FROZEN_WILDCARD_SURFACE = (
    "CORE_DEP_NAME",
    "CORE_SRC_RELATIVE",
    "MODULES_DIR_RELATIVE",
    "MODULE_YML",
    "REPO_ROOT_ENV",
    "SKIP_INSTALL_PROBE_FLAG",
    "SKIP_INSTALL_PROBE_MODULES",
    "main",
)
FROZEN_INCIDENTAL_BINDINGS = (
    "Final",
    "Path",
    "annotations",
    "ast",
    "cast",
    "os",
    "re",
    "subprocess",
    "sys",
    "tempfile",
    "tomllib",
)
FROZEN_HOMES = {
    "_CoreImportVisitor": "_module_core_compat_ast",
    "_build_probe_script": "_module_core_compat_probe",
    "_collect_core_imports": "_module_core_compat_ast",
    "_collect_defined_names": "_module_core_compat_ast",
    "_collect_defined_names_internal": "_module_core_compat_ast",
    "_collect_getattr_dynamic_submodules": "_module_core_compat_ast",
    "_collect_lazy_symbol_names": "_module_core_compat_ast",
    "_collect_submodule_aliases": "_module_core_compat_ast",
    "_declared_core_spec": "_module_core_compat_versions",
    "_expected_core_spec": "_module_core_compat_versions",
    "_extract_min_core_version": "_module_core_compat_versions",
    "_get_core_dep_spec": "_module_core_compat_versions",
    "_get_management_command_modules": "_module_core_compat_versions",
    "_get_module_non_core_deps": "_module_core_compat_versions",
    "_get_module_package_name": "_module_core_compat_versions",
    "_get_pyproject_core_dep": "_module_core_compat_versions",
    "_module_path_to_fs_path": "_module_core_compat_ast",
    "_parse_module_yml": "_module_core_compat_versions",
    "_parse_version_tuple": "_module_core_compat_versions",
    "_poetry_spec_to_pep440": "_module_core_compat_versions",
    "_probe_module_install_import": "_module_core_compat_probe",
    "_read_version_file": "_module_core_compat_versions",
    "_resolve_import": "_module_core_compat_ast",
    "_resolve_name_via_getattr_chain": "_module_core_compat_ast",
    "main": "check_module_core_compatibility",
}
FROZEN_SIGNATURES = {
    "_build_probe_script": "(package_name: 'str', src_dir: 'Path', has_django: 'bool', "
    "management_commands: 'list[str] | None' = None) -> 'str'",
    "_collect_core_imports": "(source_dir: 'Path') -> 'dict[Path, list[tuple[str, list[str] | "
    "None]]]'",
    "_collect_defined_names": "(py_file: 'Path') -> 'set[str]'",
    "_collect_defined_names_internal": "(tree: 'ast.AST') -> 'set[str]'",
    "_collect_getattr_dynamic_submodules": "(tree: 'ast.AST') -> 'set[str]'",
    "_collect_lazy_symbol_names": "(tree: 'ast.AST') -> 'set[str]'",
    "_collect_submodule_aliases": "(tree: 'ast.AST') -> 'dict[str, str]'",
    "_declared_core_spec": "(dep_spec: 'str') -> 'str'",
    "_expected_core_spec": "(version_str: 'str') -> 'str'",
    "_extract_min_core_version": "(dep_spec: 'str') -> 'str | None'",
    "_get_core_dep_spec": "(data: 'dict') -> 'str | None'",
    "_get_management_command_modules": "(package_name: 'str', src_dir: 'Path') -> 'list[str]'",
    "_get_module_non_core_deps": "(module_dir: 'Path') -> 'list[str]'",
    "_get_module_package_name": "(module_dir: 'Path') -> 'str | None'",
    "_get_pyproject_core_dep": "(mod_dir: 'Path') -> 'object | None'",
    "_module_path_to_fs_path": "(core_src_root: 'Path', module_path: 'str') -> 'Path | None'",
    "_parse_module_yml": "(module_yml: 'Path') -> 'dict'",
    "_parse_version_tuple": "(version_str: 'str') -> 'tuple[int, ...]'",
    "_poetry_spec_to_pep440": "(spec: 'str') -> 'str'",
    "_probe_module_install_import": "(mod_name: 'str', package_name: 'str', min_version: 'str', "
    "src_dir: 'Path', module_dir: 'Path') -> 'list[str]'",
    "_read_version_file": "(repo_root: 'Path') -> 'str'",
    "_resolve_import": "(core_src_root: 'Path', module_path: 'str', imported_names: 'list[str] | "
    "None') -> 'list[str]'",
    "_resolve_name_via_getattr_chain": (
        "(name: 'str', target_file: 'Path', core_src_root: 'Path', *, "
        "_visited: 'set[Path] | None' = None) -> 'bool'"
    ),
    "main": "(argv: 'list[str] | None' = None) -> 'int'",
}


#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_module_core_compat_ast": "check_module_core_compatibility",
    "_module_core_compat_probe": "check_module_core_compatibility",
    "_module_core_compat_versions": "check_module_core_compatibility",
}


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function))


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every consumer-reachable pre-split name stays on the facade."""
    missing = [name for name in FROZEN_FACADE_SURFACE if not hasattr(compat, name)]
    assert missing == []


def test_facade_wildcard_surface_keeps_the_pre_split_public_names() -> None:
    """``__all__`` keeps every non-underscore pre-split definition."""
    missing = [name for name in FROZEN_WILDCARD_SURFACE if name not in compat.__all__]
    assert missing == []
    for name in compat.__all__:
        assert hasattr(compat, name), name


def test_facade_wildcard_surface_excludes_incidental_bindings() -> None:
    """
    The narrower wildcard contract is explicit, documented, and tested.

    Pre-split, ``from check_module_core_compatibility import *`` also bound
    incidental imported names.  decisions.md § Split-Facade Seams has facades
    re-export public names only, so those names stay attributes of the facade
    but are deliberately excluded from the wildcard surface.
    """
    for name in FROZEN_INCIDENTAL_BINDINGS:
        assert hasattr(compat, name), name
        assert name not in compat.__all__, name


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert compat.ast is ast
    assert compat.os is os
    assert compat.re is re
    assert compat.subprocess is subprocess
    assert compat.sys is sys
    assert compat.tempfile is tempfile
    assert compat.tomllib is tomllib
    assert compat.Path is Path
    assert compat.Final is Final
    assert compat.cast is cast


def test_facade_attributes_are_the_defining_sibling_objects() -> None:
    """The facade re-exports the sibling objects instead of copying them."""
    assert compat.CORE_DEP_NAME == versions_module.CORE_DEP_NAME
    assert compat._MIN_VERSION_PATTERN is versions_module._MIN_VERSION_PATTERN
    assert compat._expected_core_spec is versions_module._expected_core_spec
    assert compat._get_module_non_core_deps is versions_module._get_module_non_core_deps
    assert compat._collect_defined_names is ast_module._collect_defined_names
    assert compat._resolve_import is ast_module._resolve_import
    assert compat._CoreImportVisitor is ast_module._CoreImportVisitor
    assert compat._probe_module_install_import is probe_module._probe_module_install_import
    assert compat._build_probe_script is probe_module._build_probe_script


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {name: _normalized_signature(getattr(compat, name)) for name in FROZEN_SIGNATURES}
    assert observed == FROZEN_SIGNATURES


def test_helpers_keep_their_homes() -> None:
    """Facade-owned orchestration stays in the facade; split helpers keep their sibling."""
    observed = {name: getattr(compat, name).__module__ for name in FROZEN_HOMES}
    assert observed == FROZEN_HOMES


def test_split_siblings_never_import_their_facade() -> None:
    """Siblings reach collaborators through defining siblings, never the facade."""
    for module_name, facade in SPLIT_SIBLINGS.items():
        module = __import__(module_name)
        tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[-1] != facade, (module_name, node.lineno)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name.split(".")[-1] != facade, (module_name, node.lineno)


# ---------------------------------------------------------------------------
# Diagnostics captured from the pre-split module
# ---------------------------------------------------------------------------


def test_version_helpers_keep_their_pre_split_semantics() -> None:
    """The lockstep-spec derivation keeps its exact pre-split results."""
    assert compat._expected_core_spec("0.88.0") == ">=0.88.0,<0.89.0"
    assert compat._extract_min_core_version(">=0.86.0,<0.87.0") == "0.86.0"
    assert compat._extract_min_core_version("^0.86") is None
    assert compat._declared_core_spec("quickscale-core>=0.1.0") == ">=0.1.0"


def test_poetry_spec_conversion_is_exact() -> None:
    """The Poetry-to-PEP 440 conversion keeps its pre-split forms."""
    assert compat._poetry_spec_to_pep440("^1.2.3") == ">=1.2.3,<2.0.0"
    assert compat._poetry_spec_to_pep440("^0.5") == ">=0.5,<0.6.0"
    assert compat._poetry_spec_to_pep440("~1.2.3") == ">=1.2.3,<1.3.0"
    assert compat._poetry_spec_to_pep440(">=1.0") == ">=1.0"


def test_missing_version_file_keeps_exact_diagnostic(tmp_path: Path) -> None:
    """A missing VERSION file keeps its pre-split fail-closed wording."""
    with pytest.raises(SystemExit) as excinfo:
        compat._read_version_file(tmp_path)
    assert str(excinfo.value) == f"VERSION file not found: {tmp_path / 'VERSION'}"


def test_stale_pin_report_is_byte_identical(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A stale lockstep pin keeps its pre-split report lines and exit code."""
    (tmp_path / "VERSION").write_text("0.89.0", encoding="utf-8")
    (tmp_path / "quickscale_core" / "src").mkdir(parents=True)
    module_dir = tmp_path / "quickscale_modules" / "demo"
    module_dir.mkdir(parents=True)
    (module_dir / "module.yml").write_text(
        "name: demo\ndependencies:\n  - quickscale-core\n", encoding="utf-8"
    )
    (module_dir / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\nquickscale-core = ">=0.1.0,<0.2.0"\n',
        encoding="utf-8",
    )
    assert compat.main([str(tmp_path)]) == 1
    assert capsys.readouterr().out == (
        "Repository core version: 0.89.0\n"
        "\n"
        "[demo] quickscale-core dependency: quickscale-core\n"
        "  FAIL: lockstep pin is >=0.1.0,<0.2.0; expected >=0.89.0,<0.90.0 "
        "for core 0.89.0.\n"
        "  SKIP: No src/ directory — cannot check imports.\n"
        "One or more compatibility issues found.\n"
    )
