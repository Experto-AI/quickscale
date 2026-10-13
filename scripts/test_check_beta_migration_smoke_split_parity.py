"""
Parity controls for the SA267(d) ``check_beta_migration_smoke`` script split.

``check_beta_migration_smoke`` keeps its pre-split surface through private
``_beta_migration_smoke_*`` siblings.  These controls pin the preserved
surface, the split's structural invariants, the module homes of the moved
callables, and the exact gate diagnostics captured from the pre-split module,
so a later slice cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import hashlib as hashlib
import inspect
import json as json
import os as os
import subprocess as subprocess
import sys as sys
import tempfile as tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any as Any

import _beta_migration_smoke_cases as cases
import _beta_migration_smoke_support as support
import check_beta_migration_smoke as smoke
import pytest

from quickscale_core.generator import ProjectGenerator as ProjectGenerator
from quickscale_core.schema.state_schema import (
    ManagedFileRecord as ManagedFileRecord,
)
from quickscale_core.schema.state_schema import (
    ProjectState as ProjectState,
)
from quickscale_core.schema.state_schema import (
    QuickScaleState as QuickScaleState,
)
from quickscale_core.schema.state_schema import (
    StateManager as StateManager,
)
from quickscale_core.utils.project_identity import (
    resolve_project_identity as resolve_project_identity,
)

#: Every pre-split name consumers reach through the facade.  The facade must
#: keep every one of them.
FROZEN_FACADE_SURFACE = (
    "Any",
    "BETA_MIGRATE",
    "ManagedFileRecord",
    "Path",
    "ProjectGenerator",
    "ProjectState",
    "QuickScaleState",
    "ROOT",
    "SHIM_NAMES",
    "SmokeError",
    "StateManager",
    "_assert_common_report",
    "_assert_non_mutating_run",
    "_assert_recipient_services_lifecycle",
    "_assert_successful_execution",
    "_case_fresh_first",
    "_case_iterate",
    "_case_pre_port_surfaces",
    "_case_project_apps",
    "_generate_project",
    "_install_verification_shims",
    "_probe_generated_runtime",
    "_require",
    "_run_migration",
    "_snapshot_tree",
    "_text_paths_containing",
    "_write_project_app",
    "_write_quickscale_yml",
    "annotations",
    "hashlib",
    "json",
    "main",
    "os",
    "resolve_project_identity",
    "subprocess",
    "sys",
    "tempfile",
)

#: Every non-underscore name the pre-split module defined; the facade's
#: ``__all__`` must keep all of them so a wildcard import keeps its surface.
FROZEN_WILDCARD_SURFACE = (
    "BETA_MIGRATE",
    "ROOT",
    "SHIM_NAMES",
    "SmokeError",
    "main",
)

#: Non-underscore imported bindings the pre-split wildcard import also bound;
#: the facade keeps them as attributes but excludes them from ``__all__``.
FROZEN_INCIDENTAL_BINDINGS = (
    "Any",
    "ManagedFileRecord",
    "Path",
    "ProjectGenerator",
    "ProjectState",
    "QuickScaleState",
    "StateManager",
    "annotations",
    "hashlib",
    "json",
    "os",
    "resolve_project_identity",
    "subprocess",
    "sys",
    "tempfile",
)

#: ``(name, expected ``__module__``)`` for the pre-split callables and classes.
#: Facade-owned orchestration stays in the facade; moved names keep their
#: defining sibling.
FROZEN_HOMES = {
    "main": "check_beta_migration_smoke",
    "SmokeError": "_beta_migration_smoke_support",
    "_require": "_beta_migration_smoke_support",
    "_write_quickscale_yml": "_beta_migration_smoke_support",
    "_generate_project": "_beta_migration_smoke_support",
    "_snapshot_tree": "_beta_migration_smoke_support",
    "_text_paths_containing": "_beta_migration_smoke_support",
    "_install_verification_shims": "_beta_migration_smoke_support",
    "_probe_generated_runtime": "_beta_migration_smoke_support",
    "_run_migration": "_beta_migration_smoke_support",
    "_assert_non_mutating_run": "_beta_migration_smoke_support",
    "_assert_common_report": "_beta_migration_smoke_support",
    "_assert_successful_execution": "_beta_migration_smoke_support",
    "_assert_recipient_services_lifecycle": "_beta_migration_smoke_support",
    "_case_fresh_first": "_beta_migration_smoke_cases",
    "_case_iterate": "_beta_migration_smoke_cases",
    "_case_project_apps": "_beta_migration_smoke_cases",
    "_case_pre_port_surfaces": "_beta_migration_smoke_cases",
    "_write_project_app": "_beta_migration_smoke_cases",
}

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_beta_migration_smoke_cases": "check_beta_migration_smoke",
    "_beta_migration_smoke_support": "check_beta_migration_smoke",
}

#: The pre-split signature of every callable consumers invoke.
FROZEN_SIGNATURES = {
    "main": "() -> 'int'",
    "_require": "(condition: 'bool', message: 'str') -> 'None'",
    "_write_quickscale_yml": "(project: 'Path', slug: 'str') -> 'None'",
    "_generate_project": "(root: 'Path', slug: 'str') -> 'Path'",
    "_snapshot_tree": "(project: 'Path') -> 'dict[str, str]'",
    "_text_paths_containing": "(project: 'Path', token: 'str') -> 'list[str]'",
    "_install_verification_shims": "(root: 'Path', spy_log: 'Path') -> 'Path'",
    "_probe_generated_runtime": "(project: 'Path') -> 'None'",
    "_run_migration": (
        "(*, mode: 'str' = 'fresh-first', donor: 'Path', recipient: 'Path', "
        "report_path: 'Path', environment: 'dict[str, str]', dry_run: 'bool' = False, "
        "expected_exit: 'int' = 0) -> 'tuple[dict[str, Any], str]'"
    ),
    "_assert_non_mutating_run": (
        "(*, donor: 'Path', recipient: 'Path', before_donor: 'dict[str, str]', "
        "before_recipient: 'dict[str, str]', spy_log: 'Path') -> 'None'"
    ),
    "_assert_common_report": "(report: 'dict[str, Any]') -> 'None'",
    "_assert_successful_execution": (
        "(report: 'dict[str, Any]', *, donor: 'Path', recipient: 'Path', "
        "before_donor: 'dict[str, str]', before_recipient: 'dict[str, str]', "
        "label: 'str' = 'fresh-first', expected_verification_count: 'int' = 7) -> 'None'"
    ),
    "_assert_recipient_services_lifecycle": (
        "(report: 'dict[str, Any]', spy_log: 'Path', *, label: 'str') -> 'None'"
    ),
    "_case_fresh_first": "(root: 'Path', environment: 'dict[str, str]', spy_log: 'Path') -> 'None'",
    "_case_iterate": "(root: 'Path', environment: 'dict[str, str]', spy_log: 'Path') -> 'None'",
    "_case_project_apps": (
        "(root: 'Path', environment: 'dict[str, str]', spy_log: 'Path') -> 'None'"
    ),
    "_case_pre_port_surfaces": (
        "(root: 'Path', environment: 'dict[str, str]', spy_log: 'Path') -> 'None'"
    ),
    "_write_project_app": "(project: 'Path', name: 'str') -> 'None'",
}


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function))


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every consumer-reachable pre-split name stays on the facade."""
    missing = [name for name in FROZEN_FACADE_SURFACE if not hasattr(smoke, name)]
    assert missing == []


def test_facade_wildcard_surface_keeps_the_pre_split_public_names() -> None:
    """``__all__`` keeps every non-underscore pre-split definition."""
    missing = [name for name in FROZEN_WILDCARD_SURFACE if name not in smoke.__all__]
    assert missing == []
    for name in smoke.__all__:
        assert hasattr(smoke, name), name


def test_facade_wildcard_surface_excludes_incidental_bindings() -> None:
    """
    The narrower wildcard contract is explicit, documented, and tested.

    Pre-split, ``from check_beta_migration_smoke import *`` also bound
    incidental imported names.  decisions.md § Split-Facade Seams has facades
    re-export public names only, so those names stay attributes of the facade
    but are deliberately excluded from the wildcard surface.
    """
    for name in FROZEN_INCIDENTAL_BINDINGS:
        assert hasattr(smoke, name), name
        assert name not in smoke.__all__, name


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert smoke.Any is Any
    assert smoke.Path is Path
    assert smoke.hashlib is hashlib
    assert smoke.json is json
    assert smoke.os is os
    assert smoke.subprocess is subprocess
    assert smoke.sys is sys
    assert smoke.tempfile is tempfile
    assert smoke.ProjectGenerator is ProjectGenerator
    assert smoke.ManagedFileRecord is ManagedFileRecord
    assert smoke.ProjectState is ProjectState
    assert smoke.QuickScaleState is QuickScaleState
    assert smoke.StateManager is StateManager
    assert smoke.resolve_project_identity is resolve_project_identity


def test_facade_attributes_are_the_defining_sibling_objects() -> None:
    """The facade re-exports the sibling objects instead of copying them."""
    assert smoke.ROOT is support.ROOT
    assert smoke.BETA_MIGRATE is support.BETA_MIGRATE
    assert smoke.SHIM_NAMES is support.SHIM_NAMES
    assert smoke.SmokeError is support.SmokeError
    assert smoke._require is support._require
    assert smoke._generate_project is support._generate_project
    assert smoke._run_migration is support._run_migration
    assert smoke._assert_successful_execution is support._assert_successful_execution
    assert smoke._case_fresh_first is cases._case_fresh_first
    assert smoke._case_iterate is cases._case_iterate
    assert smoke._case_project_apps is cases._case_project_apps
    assert smoke._case_pre_port_surfaces is cases._case_pre_port_surfaces
    assert smoke._write_project_app is cases._write_project_app


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {name: _normalized_signature(getattr(smoke, name)) for name in FROZEN_SIGNATURES}
    assert observed == FROZEN_SIGNATURES


def test_helpers_keep_their_homes() -> None:
    """Facade-owned orchestration stays in the facade; split helpers keep their sibling."""
    observed = {name: getattr(smoke, name).__module__ for name in FROZEN_HOMES}
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


def test_require_keeps_its_exact_diagnostic() -> None:
    """The shared assertion helper keeps its pre-split exception and text."""
    with pytest.raises(smoke.SmokeError) as excinfo:
        smoke._require(False, "synthetic smoke failure")
    assert str(excinfo.value) == "synthetic smoke failure"


def test_fixture_generation_guard_keeps_exact_message(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Generating a fixture without the lock guard keeps its pre-split wording."""
    monkeypatch.delenv("QS_SKIP_POETRY_LOCK", raising=False)
    with pytest.raises(smoke.SmokeError) as excinfo:
        smoke._generate_project(tmp_path, "guard-probe")
    assert str(excinfo.value) == (
        "smoke fixture generation must disable real Poetry lock execution"
    )


def test_project_app_guard_keeps_exact_message(tmp_path: Path) -> None:
    """Re-writing an existing project app keeps its pre-split wording."""
    app = tmp_path / "properties"
    app.mkdir()
    (app / "__init__.py").write_text("")
    with pytest.raises(smoke.SmokeError) as excinfo:
        smoke._write_project_app(tmp_path, "properties")
    assert str(excinfo.value) == f"project app properties already exists in {tmp_path}"
