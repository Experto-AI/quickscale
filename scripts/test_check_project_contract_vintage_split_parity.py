"""
Parity controls for the SA267(d) ``check_project_contract_vintage`` script split.

``check_project_contract_vintage`` keeps its pre-split surface through private
``_vintage_*`` siblings.  These controls pin the preserved surface, the split's
structural invariants, the module homes of the moved callables, and the exact
gate diagnostics captured from the pre-split module, so a later slice cannot
silently drop, reorder, or reword them.
"""

from __future__ import annotations

import argparse as argparse
import ast
import inspect
import io as io
import json as json
import os as os
import re as re
import subprocess as subprocess
import sys as sys
import tarfile as tarfile
import tempfile as tempfile
from collections.abc import Callable
from dataclasses import dataclass as dataclass
from pathlib import Path
from typing import Any

import _vintage_emission as emission
import _vintage_git as git_module
import _vintage_manifest as manifest_module
import check_project_contract_vintage as vintage
import pytest
import yaml as yaml

FROZEN_FACADE_SURFACE = (
    "Callable",
    "DECLARATION_PATH",
    "GENERATOR_PACKAGE_ROOT",
    "MODULE_MANIFEST_FILENAME",
    "MODULE_MANIFEST_ROOTS",
    "ModuleVintage",
    "PACKAGE_ROOT",
    "Path",
    "REPO_ROOT",
    "TEMPLATE_ROOT",
    "VintageError",
    "Violation",
    "ZERO_SHA_RE",
    "_DECLARATION_IDS_AT",
    "_EMITTED_TEMPLATE_SOURCES_AT",
    "_EMIT_SOURCES_SNIPPET",
    "_EVER_PRESENT_MANIFEST_PATHS",
    "_FILES_AT_COMMIT",
    "_MANIFEST_PATHS_AT",
    "_MANIFEST_VINTAGES_AT",
    "_MODULE_DECLARED_IDS_AT",
    "_REVISION_EMISSION_MAPPINGS",
    "_WATCHED_TEMPLATE_PATHS",
    "_commit_paths",
    "_declaration_id_collision",
    "_declaration_ids_at",
    "_declared_step_ids",
    "_declared_step_ids_at",
    "_declares_new_step",
    "_declares_vintage",
    "_emitted_sources_from_mapping",
    "_emitted_template_sources_at",
    "_event_base_ref",
    "_file_at_commit",
    "_file_in_index",
    "_first_parent",
    "_foreign_declared_step_ids",
    "_generator_emission_mapping",
    "_generator_paths",
    "_git",
    "_git_bytes",
    "_historical_manifest_ids",
    "_historical_step_ids",
    "_index_declared_module_ids",
    "_index_declared_step_ids",
    "_introduction_commit",
    "_is_ancestor",
    "_is_module_manifest_path",
    "_manifest_identity_violation",
    "_manifest_ids_at",
    "_manifest_module_name",
    "_manifest_paths_at",
    "_manifest_paths_present_at",
    "_manifest_vintage_at",
    "_merge_combined_id_violations",
    "_merge_declaration_id_collision",
    "_merge_declares_new_step",
    "_merge_manifest_violation",
    "_merge_resolution_paths",
    "_merged_tree_declared_ids",
    "_module_declared_ids_at",
    "_module_manifest_violation",
    "_module_vintage",
    "_parents",
    "_path_exists_at",
    "_path_exists_in_index",
    "_range_base",
    "_report",
    "_resolve_commit",
    "_revision_emission_mapping",
    "_revision_emission_mapping_changed",
    "_revision_emitted_sources",
    "_revision_mappings_available",
    "_select_base_ref",
    "_source_reference_path",
    "_staged_manifest_violation",
    "_staged_paths",
    "_staged_violation",
    "_template_contract_paths",
    "_tree_declared_module_ids_at",
    "_tree_entry_exists",
    "_violations",
    "_watched_template_paths",
    "annotations",
    "argparse",
    "dataclass",
    "io",
    "json",
    "main",
    "os",
    "re",
    "subprocess",
    "sys",
    "tarfile",
    "tempfile",
    "yaml",
)
FROZEN_WILDCARD_SURFACE = (
    "DECLARATION_PATH",
    "GENERATOR_PACKAGE_ROOT",
    "MODULE_MANIFEST_FILENAME",
    "MODULE_MANIFEST_ROOTS",
    "ModuleVintage",
    "PACKAGE_ROOT",
    "REPO_ROOT",
    "TEMPLATE_ROOT",
    "VintageError",
    "Violation",
    "ZERO_SHA_RE",
    "main",
)
FROZEN_INCIDENTAL_BINDINGS = (
    "Callable",
    "Path",
    "annotations",
    "argparse",
    "dataclass",
    "io",
    "json",
    "os",
    "re",
    "subprocess",
    "sys",
    "tarfile",
    "tempfile",
    "yaml",
)
FROZEN_HOMES = {
    "ModuleVintage": "_vintage_manifest",
    "VintageError": "_vintage_git",
    "Violation": "_vintage_manifest",
    "_commit_paths": "_vintage_git",
    "_declaration_id_collision": "_vintage_manifest",
    "_declaration_ids_at": "_vintage_manifest",
    "_declared_step_ids": "_vintage_manifest",
    "_declared_step_ids_at": "_vintage_manifest",
    "_declares_new_step": "_vintage_manifest",
    "_declares_vintage": "_vintage_manifest",
    "_emitted_sources_from_mapping": "_vintage_emission",
    "_emitted_template_sources_at": "_vintage_emission",
    "_event_base_ref": "_vintage_git",
    "_file_at_commit": "_vintage_git",
    "_file_in_index": "_vintage_git",
    "_first_parent": "_vintage_git",
    "_foreign_declared_step_ids": "_vintage_manifest",
    "_generator_emission_mapping": "_vintage_emission",
    "_generator_paths": "_vintage_emission",
    "_git": "_vintage_git",
    "_git_bytes": "_vintage_git",
    "_historical_manifest_ids": "_vintage_manifest",
    "_historical_step_ids": "_vintage_manifest",
    "_index_declared_module_ids": "_vintage_manifest",
    "_index_declared_step_ids": "_vintage_manifest",
    "_introduction_commit": "_vintage_manifest",
    "_is_ancestor": "_vintage_git",
    "_is_module_manifest_path": "_vintage_manifest",
    "_manifest_identity_violation": "_vintage_manifest",
    "_manifest_ids_at": "_vintage_manifest",
    "_manifest_module_name": "_vintage_manifest",
    "_manifest_paths_at": "_vintage_manifest",
    "_manifest_paths_present_at": "_vintage_manifest",
    "_manifest_vintage_at": "_vintage_manifest",
    "_merge_combined_id_violations": "_vintage_manifest",
    "_merge_declaration_id_collision": "_vintage_manifest",
    "_merge_declares_new_step": "_vintage_manifest",
    "_merge_manifest_violation": "_vintage_manifest",
    "_merge_resolution_paths": "_vintage_git",
    "_merged_tree_declared_ids": "_vintage_manifest",
    "_module_declared_ids_at": "_vintage_manifest",
    "_module_manifest_violation": "_vintage_manifest",
    "_module_vintage": "_vintage_manifest",
    "_parents": "_vintage_git",
    "_path_exists_at": "_vintage_git",
    "_path_exists_in_index": "_vintage_git",
    "_range_base": "_vintage_git",
    "_report": "check_project_contract_vintage",
    "_resolve_commit": "_vintage_git",
    "_revision_emission_mapping": "_vintage_emission",
    "_revision_emission_mapping_changed": "_vintage_emission",
    "_revision_emitted_sources": "_vintage_emission",
    "_revision_mappings_available": "_vintage_emission",
    "_select_base_ref": "_vintage_git",
    "_source_reference_path": "_vintage_manifest",
    "_staged_manifest_violation": "check_project_contract_vintage",
    "_staged_paths": "_vintage_git",
    "_staged_violation": "check_project_contract_vintage",
    "_template_contract_paths": "_vintage_emission",
    "_tree_declared_module_ids_at": "_vintage_manifest",
    "_tree_entry_exists": "_vintage_git",
    "_violations": "check_project_contract_vintage",
    "_watched_template_paths": "_vintage_emission",
    "main": "check_project_contract_vintage",
}
FROZEN_SIGNATURES = {
    "_commit_paths": "(commit: 'str') -> 'tuple[str, ...]'",
    "_declaration_id_collision": "(commit: 'str') -> 'set[str]'",
    "_declaration_ids_at": "(commit: 'str') -> 'frozenset[str]'",
    "_declared_step_ids": "(content: 'str', label: 'str') -> 'set[str]'",
    "_declared_step_ids_at": "(commit: 'str') -> 'set[str]'",
    "_declares_new_step": "(commit: 'str') -> 'bool'",
    "_declares_vintage": "(commit: 'str', paths: 'tuple[str, ...]') -> 'bool'",
    "_emitted_sources_from_mapping": "(mapping: 'dict[str, str]') -> 'frozenset[str]'",
    "_emitted_template_sources_at": "(commit: 'str') -> 'frozenset[str]'",
    "_event_base_ref": "() -> 'str | None'",
    "_file_at_commit": "(commit: 'str', path: 'str') -> 'str'",
    "_file_in_index": "(path: 'str') -> 'str'",
    "_first_parent": "(commit: 'str') -> 'str | None'",
    "_foreign_declared_step_ids": "(commit: 'str', path: 'str') -> 'frozenset[str]'",
    "_generator_emission_mapping": "(template_root: 'Path') -> 'dict[str, str]'",
    "_generator_paths": "(paths: 'tuple[str, ...]') -> 'tuple[str, ...]'",
    "_git": "(*args: 'str') -> 'str'",
    "_git_bytes": "(*args: 'str') -> 'bytes'",
    "_historical_manifest_ids": "(commit: 'str', path: 'str') -> 'set[str]'",
    "_historical_step_ids": "(commit: 'str') -> 'set[str]'",
    "_index_declared_module_ids": "(*, exclude_module: 'str | None' = None) -> 'frozenset[str]'",
    "_index_declared_step_ids": "() -> 'set[str]'",
    "_introduction_commit": "(head: 'str') -> 'str | None'",
    "_is_ancestor": "(commit: 'str', descendant: 'str') -> 'bool'",
    "_is_module_manifest_path": "(path: 'str') -> 'bool'",
    "_manifest_identity_violation": "(*, parents: 'list[ModuleVintage | None]', current: "
    "'ModuleVintage | None', historical: 'set[str]', foreign: "
    "'frozenset[str]', commit: 'str', subject: 'str', paths: "
    "'tuple[str, ...]') -> 'Violation | None'",
    "_manifest_ids_at": "(commit: 'str', path: 'str') -> 'set[str]'",
    "_manifest_module_name": "(path: 'str') -> 'str'",
    "_manifest_paths_at": "(commit: 'str') -> 'tuple[str, ...]'",
    "_manifest_paths_present_at": "(commit: 'str') -> 'tuple[str, ...]'",
    "_manifest_vintage_at": "(commit: 'str', path: 'str') -> 'ModuleVintage | None'",
    "_merge_combined_id_violations": "(commit: 'str', parents: 'tuple[str, ...]') -> "
    "'list[Violation]'",
    "_merge_declaration_id_collision": "(commit: 'str', parents: 'tuple[str, ...]') -> 'set[str]'",
    "_merge_declares_new_step": "(commit: 'str', parents: 'tuple[str, ...]') -> 'bool'",
    "_merge_manifest_violation": "(commit: 'str', path: 'str', parents: 'tuple[str, ...]') -> "
    "'Violation | None'",
    "_merge_resolution_paths": "(commit: 'str') -> 'tuple[str, ...]'",
    "_merged_tree_declared_ids": "(commit: 'str') -> 'dict[str, frozenset[str]]'",
    "_module_declared_ids_at": "(commit: 'str', module_name: 'str') -> 'frozenset[str]'",
    "_module_manifest_violation": "(commit: 'str', path: 'str') -> 'Violation | None'",
    "_module_vintage": "(content: 'str', label: 'str') -> 'ModuleVintage | None'",
    "_parents": "(commit: 'str') -> 'tuple[str, ...]'",
    "_path_exists_at": "(commit: 'str', path: 'str') -> 'bool'",
    "_path_exists_in_index": "(path: 'str') -> 'bool'",
    "_range_base": "(base: 'str', head: 'str') -> 'str'",
    "_report": "(violations: 'tuple[Violation, ...]') -> 'None'",
    "_resolve_commit": "(ref: 'str') -> 'str'",
    "_revision_emission_mapping": "(commit: 'str') -> 'dict[str, str] | None'",
    "_revision_emission_mapping_changed": "(commit: 'str') -> 'bool'",
    "_revision_emitted_sources": "(commit: 'str') -> 'frozenset[str]'",
    "_revision_mappings_available": "(revisions: 'tuple[str | None, ...]') -> 'bool'",
    "_select_base_ref": "(explicit: 'str | None') -> 'str'",
    "_source_reference_path": "(module_name: 'str') -> 'str'",
    "_staged_manifest_violation": "(path: 'str', *, revisions: 'tuple[str, ...]', foreign_extra: "
    "'frozenset[str]' = frozenset()) -> 'Violation | None'",
    "_staged_paths": "() -> 'tuple[str, ...]'",
    "_staged_violation": "() -> 'tuple[Violation, ...]'",
    "_template_contract_paths": "(paths: 'tuple[str, ...]', *, emitted_before: 'Callable[[str], "
    "bool]', emitted_after: 'Callable[[str], bool]', "
    "checked_out_fallback: 'bool') -> 'tuple[str, ...]'",
    "_tree_declared_module_ids_at": "(commit: 'str', *, exclude_module: 'str | None' = None) -> "
    "'frozenset[str]'",
    "_tree_entry_exists": "(commit: 'str', path: 'str') -> 'bool'",
    "_violations": "(base: 'str', head: 'str') -> 'tuple[Violation, ...]'",
    "_watched_template_paths": "() -> 'frozenset[str]'",
    "main": "(argv: 'list[str] | None' = None) -> 'int'",
}


#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_vintage_emission": "check_project_contract_vintage",
    "_vintage_git": "check_project_contract_vintage",
    "_vintage_manifest": "check_project_contract_vintage",
}


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function))


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every consumer-reachable pre-split name stays on the facade."""
    missing = [name for name in FROZEN_FACADE_SURFACE if not hasattr(vintage, name)]
    assert missing == []


def test_facade_wildcard_surface_keeps_the_pre_split_public_names() -> None:
    """``__all__`` keeps every non-underscore pre-split definition."""
    missing = [name for name in FROZEN_WILDCARD_SURFACE if name not in vintage.__all__]
    assert missing == []
    for name in vintage.__all__:
        assert hasattr(vintage, name), name


def test_facade_wildcard_surface_excludes_incidental_bindings() -> None:
    """
    The narrower wildcard contract is explicit, documented, and tested.

    Pre-split, ``from check_project_contract_vintage import *`` also bound
    incidental imported names.  decisions.md § Split-Facade Seams has facades
    re-export public names only, so those names stay attributes of the facade
    but are deliberately excluded from the wildcard surface.
    """
    for name in FROZEN_INCIDENTAL_BINDINGS:
        assert hasattr(vintage, name), name
        assert name not in vintage.__all__, name


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert vintage.argparse is argparse
    assert vintage.io is io
    assert vintage.json is json
    assert vintage.os is os
    assert vintage.re is re
    assert vintage.subprocess is subprocess
    assert vintage.sys is sys
    assert vintage.tarfile is tarfile
    assert vintage.tempfile is tempfile
    assert vintage.yaml is yaml
    assert vintage.Path is Path
    assert vintage.Callable is Callable
    assert vintage.dataclass is dataclass


def test_facade_attributes_are_the_defining_sibling_objects() -> None:
    """The facade re-exports the sibling objects instead of copying them."""
    assert vintage.REPO_ROOT is git_module.REPO_ROOT
    assert vintage.ZERO_SHA_RE is git_module.ZERO_SHA_RE
    assert vintage._FILES_AT_COMMIT is git_module._FILES_AT_COMMIT
    assert vintage._git is git_module._git
    assert vintage._first_parent is git_module._first_parent
    assert vintage.TEMPLATE_ROOT == emission.TEMPLATE_ROOT
    assert vintage._EMIT_SOURCES_SNIPPET == emission._EMIT_SOURCES_SNIPPET
    assert vintage._generator_paths is emission._generator_paths
    assert vintage._watched_template_paths is emission._watched_template_paths
    assert vintage.DECLARATION_PATH == manifest_module.DECLARATION_PATH
    assert vintage._MANIFEST_VINTAGES_AT is manifest_module._MANIFEST_VINTAGES_AT
    assert vintage.Violation is manifest_module.Violation
    assert vintage.ModuleVintage is manifest_module.ModuleVintage
    assert vintage._module_vintage is manifest_module._module_vintage
    assert vintage._merge_combined_id_violations is manifest_module._merge_combined_id_violations


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {name: _normalized_signature(getattr(vintage, name)) for name in FROZEN_SIGNATURES}
    assert observed == FROZEN_SIGNATURES


def test_helpers_keep_their_homes() -> None:
    """Facade-owned orchestration stays in the facade; split helpers keep their sibling."""
    observed = {name: getattr(vintage, name).__module__ for name in FROZEN_HOMES}
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


def test_unsafe_ref_message_is_exact() -> None:
    """An unsafe or empty ref keeps its pre-split fail-closed wording."""
    with pytest.raises(vintage.VintageError) as excinfo:
        vintage._resolve_commit("")
    assert str(excinfo.value) == "unsafe or empty Git ref: ''"


def test_declaration_malformed_message_is_exact() -> None:
    """A declaration without a steps list keeps its pre-split wording."""
    with pytest.raises(vintage.VintageError) as excinfo:
        vintage._declared_step_ids("steps: notalist\n", "at deadbeef")
    assert str(excinfo.value) == (
        f"{vintage.DECLARATION_PATH} at deadbeef must declare a 'steps' list"
    )


def test_module_vintage_malformed_message_is_exact() -> None:
    """A manifest that is not valid YAML keeps its pre-split wording."""
    with pytest.raises(vintage.VintageError) as excinfo:
        vintage._module_vintage("not: [valid", "probe")
    assert str(excinfo.value).startswith("cannot parse module manifest probe:")


def test_generator_paths_classification_is_exact() -> None:
    """The generator-path filter keeps its pre-split classification."""
    assert vintage._generator_paths(
        (
            "quickscale_core/src/quickscale_core/generator/x.py",
            "quickscale_core/src/quickscale_core/generator/templates/y.j2",
            "other.py",
        )
    ) == ("quickscale_core/src/quickscale_core/generator/x.py",)


def test_manifest_path_classification_is_exact() -> None:
    """The manifest-path predicate keeps its pre-split classification."""
    assert vintage._is_module_manifest_path("quickscale_modules/auth/module.yml") is True
    assert (
        vintage._is_module_manifest_path(
            "quickscale_core/src/quickscale_core/data/manifests/auth/module.yml"
        )
        is True
    )
    assert vintage._is_module_manifest_path("scripts/module.yml") is False


def test_report_output_is_byte_identical(capsys: pytest.CaptureFixture[str]) -> None:
    """The failure report keeps its pre-split text byte for byte."""
    violation = vintage.Violation(
        "a" * 40,
        "subject line",
        ("quickscale_core/src/quickscale_core/generator/templates/x.j2",),
        reason="no new adoption step id",
    )
    vintage._report((violation,))
    assert capsys.readouterr().err == (
        "ERROR: [PROJECT_CONTRACT_VINTAGE] generated-project contract changes "
        "without a new adoption step id:\n"
        "  aaaaaaaaaaaa subject line (no new adoption step id)\n"
        "    quickscale_core/src/quickscale_core/generator/templates/x.j2\n"
        "\n"
        f"Declare the change in {vintage.DECLARATION_PATH} under a new adoption step id "
        "in the same commit, or give the changed module manifest step a new id "
        "(see the SA207/SA211 declaration blocks).\n"
    )
