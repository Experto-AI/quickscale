"""
Parity controls for the SA267(d) ``check_sa117_scope`` script split.

``check_sa117_scope`` keeps its pre-split surface through private ``_sa117_*``
siblings.  These controls pin the preserved surface, the split's structural
invariants, the module homes of the moved callables, and the exact gate
diagnostics captured from the pre-split module, so a later slice cannot
silently drop, reorder, or reword them.
"""

from __future__ import annotations

import argparse as argparse
import ast as ast
import copy as copy
import datetime as datetime
import hashlib as hashlib
import inspect
import json as json
import os as os
import re as re
import shlex as shlex
import stat as stat
import subprocess as subprocess
import sys as sys
import tempfile as tempfile
import tomllib as tomllib
from collections.abc import Callable
from collections.abc import Hashable as Hashable
from collections.abc import Mapping as Mapping
from pathlib import Path
from typing import Any as Any
from typing import Final as Final

import _sa117_lock_diff as diff_module
import _sa117_lock_parse as parse_module
import _sa117_scope_contract as contract_module
import check_sa117_scope as scope_check
import pytest
import yaml as yaml
from yaml.events import AliasEvent as AliasEvent
from yaml.nodes import MappingNode as MappingNode

#: Repo-root placeholder for default arguments that embed the checkout path.
_REPO_ROOT = str(Path(scope_check.__file__).resolve().parent.parent)

FROZEN_FACADE_SURFACE = (
    "AliasEvent",
    "Any",
    "DEFAULT_EVIDENCE_PATH",
    "DEFAULT_SCOPE_PATH",
    "Final",
    "Hashable",
    "LockDiffError",
    "Mapping",
    "MappingNode",
    "Path",
    "SCOPE_DIR",
    "_LOCKED_MODULE_PACKAGES",
    "_LOCK_VERSION_SENTINEL",
    "_MODULE_DISCOVERY_RELATIVE_PATH",
    "_StrictYamlLoader",
    "_authoritative_module_names",
    "_build_parser",
    "_candidate_contents",
    "_collect_differences",
    "_contract_mode",
    "_expected_inventory",
    "_filter_scope_paths",
    "_git_baseline_contents",
    "_git_top_level",
    "_inventory_digest",
    "_json_without_duplicate_keys",
    "_load_scope_document",
    "_locked_module_packages",
    "_normalise",
    "_normalise_candidate",
    "_normalise_lock",
    "_parse_canonical_version",
    "_parse_inventory",
    "_parse_lock_data",
    "_parse_manifest",
    "_parse_project_version",
    "_parse_python_version",
    "_parse_toml",
    "_parse_version_file",
    "_read_git_tracked_files",
    "_reject_toml_temporal_values",
    "_remove_evidence",
    "_render_make_help",
    "_requested_scope_path",
    "_required_inputs",
    "_resolve_git_ref",
    "_sha256",
    "_tokenise_make_paths",
    "_validate_contract",
    "_validate_no_nul",
    "_write_evidence_atomic",
    "annotations",
    "argparse",
    "ast",
    "build_allowlist",
    "copy",
    "datetime",
    "hashlib",
    "json",
    "load_scope",
    "main",
    "mode_emit",
    "mode_lock",
    "mode_verify_lock_diff",
    "mode_worktree",
    "os",
    "re",
    "shlex",
    "stat",
    "subprocess",
    "sys",
    "tempfile",
    "tomllib",
    "yaml",
)
FROZEN_WILDCARD_SURFACE = (
    "DEFAULT_EVIDENCE_PATH",
    "DEFAULT_SCOPE_PATH",
    "LockDiffError",
    "SCOPE_DIR",
    "build_allowlist",
    "load_scope",
    "main",
    "mode_emit",
    "mode_lock",
    "mode_verify_lock_diff",
    "mode_worktree",
)
FROZEN_INCIDENTAL_BINDINGS = (
    "AliasEvent",
    "Any",
    "Final",
    "Hashable",
    "Mapping",
    "MappingNode",
    "Path",
    "annotations",
    "argparse",
    "ast",
    "copy",
    "datetime",
    "hashlib",
    "json",
    "os",
    "re",
    "shlex",
    "stat",
    "subprocess",
    "sys",
    "tempfile",
    "tomllib",
    "yaml",
)
FROZEN_HOMES = {
    "LockDiffError": "_sa117_lock_parse",
    "_StrictYamlLoader": "_sa117_lock_parse",
    "_authoritative_module_names": "_sa117_lock_parse",
    "_build_parser": "check_sa117_scope",
    "_candidate_contents": "_sa117_lock_parse",
    "_collect_differences": "_sa117_lock_diff",
    "_contract_mode": "_sa117_scope_contract",
    "_expected_inventory": "_sa117_lock_parse",
    "_filter_scope_paths": "_sa117_scope_contract",
    "_git_baseline_contents": "_sa117_lock_parse",
    "_git_top_level": "_sa117_lock_parse",
    "_inventory_digest": "_sa117_lock_parse",
    "_json_without_duplicate_keys": "_sa117_scope_contract",
    "_load_scope_document": "_sa117_scope_contract",
    "_locked_module_packages": "_sa117_lock_parse",
    "_normalise": "_sa117_scope_contract",
    "_normalise_candidate": "_sa117_scope_contract",
    "_normalise_lock": "_sa117_lock_diff",
    "_parse_canonical_version": "_sa117_lock_parse",
    "_parse_inventory": "_sa117_lock_parse",
    "_parse_lock_data": "_sa117_lock_parse",
    "_parse_manifest": "_sa117_lock_parse",
    "_parse_project_version": "_sa117_lock_parse",
    "_parse_python_version": "_sa117_lock_parse",
    "_parse_toml": "_sa117_lock_parse",
    "_parse_version_file": "_sa117_lock_parse",
    "_read_git_tracked_files": "check_sa117_scope",
    "_reject_toml_temporal_values": "_sa117_lock_parse",
    "_remove_evidence": "_sa117_lock_diff",
    "_render_make_help": "check_sa117_scope",
    "_requested_scope_path": "check_sa117_scope",
    "_required_inputs": "_sa117_scope_contract",
    "_resolve_git_ref": "_sa117_lock_parse",
    "_sha256": "_sa117_lock_parse",
    "_tokenise_make_paths": "_sa117_scope_contract",
    "_validate_contract": "_sa117_scope_contract",
    "_validate_no_nul": "_sa117_scope_contract",
    "_write_evidence_atomic": "_sa117_lock_diff",
    "build_allowlist": "_sa117_scope_contract",
    "load_scope": "_sa117_scope_contract",
    "main": "check_sa117_scope",
    "mode_emit": "check_sa117_scope",
    "mode_lock": "check_sa117_scope",
    "mode_verify_lock_diff": "check_sa117_scope",
    "mode_worktree": "check_sa117_scope",
}
FROZEN_SIGNATURES = {
    "_authoritative_module_names": "(repo_root: 'Path | None' = None) -> 'list[str]'",
    "_build_parser": "(scope_path: 'Path' = PosixPath('<root>/scripts/sa117_scope.json')) -> "
    "'argparse.ArgumentParser'",
    "_candidate_contents": "(root: 'Path', paths: 'list[str]') -> 'dict[str, bytes]'",
    "_collect_differences": (
        "(left: 'Any', right: 'Any', path: 'str' = '') -> 'list[dict[str, Any]]'"
    ),
    "_contract_mode": "(scope_path: 'Path', mode: 'str') -> 'dict[str, Any]'",
    "_expected_inventory": "(repo_root: 'Path | None' = None, module_names: 'list[str] | None' = "
    "None) -> 'list[str]'",
    "_filter_scope_paths": "(paths: 'set[str]', *, scripts_only: 'bool') -> 'set[str]'",
    "_git_baseline_contents": "(repo_root: 'Path', resolved_sha: 'str', paths: 'list[str]') -> "
    "'dict[str, bytes]'",
    "_git_top_level": "(repo_path: 'Path') -> 'Path | None'",
    "_inventory_digest": "(contents: 'dict[str, bytes]', paths: 'list[str]') -> 'str'",
    "_json_without_duplicate_keys": "(pairs: 'list[tuple[str, Any]]') -> 'dict[str, Any]'",
    "_load_scope_document": (
        "(scope_path: 'Path' = PosixPath('<root>/scripts/sa117_scope.json')) -> 'dict[str, Any]'"
    ),
    "_locked_module_packages": "(module_names: 'list[str]') -> 'list[str]'",
    "_normalise": "(path: 'str') -> 'str'",
    "_normalise_candidate": "(path: 'str') -> 'str'",
    "_normalise_lock": "(lock_data: 'dict[str, Any]', module_packages: 'list[str]') -> "
    "'tuple[dict[str, Any], list[str]]'",
    "_parse_canonical_version": "(value: 'Any') -> 'str'",
    "_parse_inventory": (
        "(contents: 'dict[str, bytes]', label: 'str', module_names: 'list[str]') -> "
        "'dict[str, Any]'"
    ),
    "_parse_lock_data": (
        "(content: 'bytes', path: 'str', module_packages: 'list[str]') -> 'dict[str, Any]'"
    ),
    "_parse_manifest": "(content: 'bytes', path: 'str', module_name: 'str') -> 'str'",
    "_parse_project_version": "(content: 'bytes', path: 'str', expected_name: 'str') -> 'str'",
    "_parse_python_version": "(content: 'bytes', path: 'str') -> 'str'",
    "_parse_toml": "(content: 'bytes', path: 'str') -> 'dict[str, Any]'",
    "_parse_version_file": "(content: 'bytes', path: 'str') -> 'str'",
    "_read_git_tracked_files": "(repo_root: 'Path') -> 'list[str]'",
    "_reject_toml_temporal_values": "(value: 'Any', path: 'str', location: 'str' = '$') -> 'None'",
    "_remove_evidence": "(path: 'Path') -> 'None'",
    "_render_make_help": "(scope_path: 'Path' = PosixPath('<root>/scripts/sa117_scope.json')) -> "
    "'None'",
    "_requested_scope_path": "(argv: 'list[str]') -> 'Path'",
    "_required_inputs": "(scope_path: 'Path', mode: 'str', profile: 'str', values: 'Mapping[str, "
    "Any]') -> 'None'",
    "_resolve_git_ref": "(ref: 'str', repo_path: 'Path | None' = None) -> 'str | None'",
    "_sha256": "(content: 'bytes') -> 'str'",
    "_tokenise_make_paths": "(paths: 'list[str] | None') -> 'list[str] | None'",
    "_validate_contract": "(contract: 'Any') -> 'None'",
    "_validate_no_nul": "(path: 'str') -> 'str'",
    "_write_evidence_atomic": "(path: 'Path', evidence: 'dict[str, Any]') -> 'None'",
    "build_allowlist": "(scope_entries: 'list[dict[str, Any]]') -> 'dict[str, dict[str, Any]]'",
    "load_scope": "(scope_path: 'Path' = PosixPath('<root>/scripts/sa117_scope.json')) -> "
    "'list[dict[str, Any]]'",
    "main": "(argv: 'list[str] | None' = None) -> 'int'",
    "mode_emit": (
        "(scope_path: 'Path', *, phase: 'str | None' = None, profile: 'str' = 'direct') -> 'int'"
    ),
    "mode_lock": (
        "(scope_path: 'Path', *, paths: 'list[str] | None' = None, repo_root: 'Path | None' "
        "= None, scripts_only: 'bool' = False, profile: 'str' = 'direct') -> 'int'"
    ),
    "mode_verify_lock_diff": (
        "(candidate_path: 'Path', *, baseline_ref: 'str', expected_version: 'str "
        "| None' = None, output_path: 'Path | None' = None) -> 'int'"
    ),
    "mode_worktree": "(scope_path: 'Path', *, paths: 'list[str] | None' = None, repo_root: 'Path | "
    "None' = None, allow_untracked: 'bool' = False, scripts_only: 'bool' = False, "
    "profile: 'str' = 'direct') -> 'int'",
}


#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_sa117_lock_diff": "check_sa117_scope",
    "_sa117_lock_parse": "check_sa117_scope",
    "_sa117_scope_contract": "check_sa117_scope",
}


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function)).replace(_REPO_ROOT, "<root>")


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every consumer-reachable pre-split name stays on the facade."""
    missing = [name for name in FROZEN_FACADE_SURFACE if not hasattr(scope_check, name)]
    assert missing == []


def test_facade_wildcard_surface_keeps_the_pre_split_public_names() -> None:
    """``__all__`` keeps every non-underscore pre-split definition."""
    missing = [name for name in FROZEN_WILDCARD_SURFACE if name not in scope_check.__all__]
    assert missing == []
    for name in scope_check.__all__:
        assert hasattr(scope_check, name), name


def test_facade_wildcard_surface_excludes_incidental_bindings() -> None:
    """
    The narrower wildcard contract is explicit, documented, and tested.

    Pre-split, ``from check_sa117_scope import *`` also bound incidental
    imported names.  decisions.md § Split-Facade Seams has facades re-export
    public names only, so those names stay attributes of the facade but are
    deliberately excluded from the wildcard surface.
    """
    for name in FROZEN_INCIDENTAL_BINDINGS:
        assert hasattr(scope_check, name), name
        assert name not in scope_check.__all__, name


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    assert scope_check.argparse is argparse
    assert scope_check.ast is ast
    assert scope_check.copy is copy
    assert scope_check.datetime is datetime
    assert scope_check.hashlib is hashlib
    assert scope_check.json is json
    assert scope_check.os is os
    assert scope_check.re is re
    assert scope_check.shlex is shlex
    assert scope_check.stat is stat
    assert scope_check.subprocess is subprocess
    assert scope_check.sys is sys
    assert scope_check.tempfile is tempfile
    assert scope_check.tomllib is tomllib
    assert scope_check.Path is Path


def test_facade_preserves_the_pre_split_yaml_and_typing_bindings() -> None:
    """The YAML and typing imports stay importable through the facade."""
    assert scope_check.yaml is yaml
    assert scope_check.AliasEvent is AliasEvent
    assert scope_check.MappingNode is MappingNode
    assert scope_check.Hashable is Hashable
    assert scope_check.Mapping is Mapping
    assert scope_check.Any is Any
    assert scope_check.Final is Final


def test_facade_attributes_are_the_defining_sibling_objects() -> None:
    """The facade re-exports the sibling objects instead of copying them."""
    assert scope_check.SCOPE_DIR is contract_module.SCOPE_DIR
    assert scope_check.DEFAULT_SCOPE_PATH is contract_module.DEFAULT_SCOPE_PATH
    assert scope_check._validate_contract is contract_module._validate_contract
    assert scope_check.build_allowlist is contract_module.build_allowlist
    assert scope_check.LockDiffError is parse_module.LockDiffError
    assert scope_check._LOCKED_MODULE_PACKAGES is parse_module._LOCKED_MODULE_PACKAGES
    assert scope_check._LOCK_VERSION_SENTINEL is parse_module._LOCK_VERSION_SENTINEL
    assert scope_check._authoritative_module_names is parse_module._authoritative_module_names
    assert scope_check._parse_python_version is parse_module._parse_python_version
    assert scope_check._expected_inventory is parse_module._expected_inventory
    assert scope_check._normalise_lock is diff_module._normalise_lock
    assert scope_check._collect_differences is diff_module._collect_differences
    assert scope_check._write_evidence_atomic is diff_module._write_evidence_atomic


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {
        name: _normalized_signature(getattr(scope_check, name)) for name in FROZEN_SIGNATURES
    }
    assert observed == FROZEN_SIGNATURES


def test_helpers_keep_their_homes() -> None:
    """Facade-owned orchestration stays in the facade; split helpers keep their sibling."""
    observed = {name: getattr(scope_check, name).__module__ for name in FROZEN_HOMES}
    assert observed == FROZEN_HOMES


def test_lock_diff_orchestration_stays_patchable_on_the_facade() -> None:
    """
    ``mode_verify_lock_diff`` calls the facade-bound discovery name.

    The pre-split module's tests patch ``_authoritative_module_names`` on the
    module and call ``mode_verify_lock_diff``; keeping both in the facade
    preserves that seam.
    """
    assert scope_check.mode_verify_lock_diff.__module__ == "check_sa117_scope"
    assert scope_check._authoritative_module_names.__module__ == "_sa117_lock_parse"


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


def test_contract_rejections_keep_exact_messages() -> None:
    """Malformed contracts keep their pre-split fail-closed wording."""
    with pytest.raises(ValueError) as excinfo:
        scope_check._validate_contract(None)
    assert str(excinfo.value) == "SA117 contract must be a JSON object"
    with pytest.raises(ValueError) as excinfo:
        scope_check._validate_contract({})
    assert str(excinfo.value) == "SA117 contract has missing or unknown fields"


def test_path_normalisation_is_exact() -> None:
    """The lexical path helpers keep their pre-split results."""
    assert scope_check._normalise("./a//b/../c/") == "a/c"
    with pytest.raises(ValueError) as excinfo:
        scope_check._normalise_candidate("/absolute/path")
    assert str(excinfo.value) == "candidate path must be relative: '/absolute/path'"


def test_python_version_reader_keeps_exact_acceptance_and_rejection() -> None:
    """The ``__version__`` reader keeps its pre-split acceptance and messages."""
    assert (
        scope_check._parse_python_version(b"__version__ = '1.2.3'\nimport os\n", "probe.py")
        == "1.2.3"
    )
    with pytest.raises(scope_check.LockDiffError) as excinfo:
        scope_check._parse_python_version(
            b"__version__ = '1.2.3'\n__version__ = '9.9.9'\n", "probe.py"
        )
    assert str(excinfo.value) == "probe.py: expected exactly one direct __version__ literal"
    with pytest.raises(scope_check.LockDiffError) as excinfo:
        scope_check._parse_python_version(b"__version__ = '1.2.3'\ndel __version__\n", "probe.py")
    assert str(excinfo.value) == (
        "probe.py: every other __version__ binding or deletion is forbidden"
    )


def test_expected_inventory_is_exact() -> None:
    """The expected inventory keeps its pre-split shape for one module."""
    assert scope_check._expected_inventory(None, ["auth"]) == [
        "VERSION",
        "poetry.lock",
        "quickscale/pyproject.toml",
        "quickscale_core/pyproject.toml",
        "quickscale_cli/pyproject.toml",
        "quickscale_core/src/quickscale_core/_version.py",
        "quickscale_cli/src/quickscale_cli/_version.py",
        "quickscale_modules/auth/pyproject.toml",
        "quickscale_modules/auth/src/quickscale_modules_auth/__init__.py",
        "quickscale_modules/auth/module.yml",
        "quickscale_core/src/quickscale_core/data/manifests/auth/module.yml",
    ]


def test_missing_mode_keeps_exact_message(capsys: pytest.CaptureFixture[str]) -> None:
    """A missing checker mode keeps its pre-split usage error and exit code."""
    assert scope_check.main([]) == 2
    assert capsys.readouterr().err == "ERROR: a checker mode is required\n"


def test_make_help_keeps_its_first_line(capsys: pytest.CaptureFixture[str]) -> None:
    """The rendered Make help keeps its pre-split heading."""
    scope_check._render_make_help()
    assert capsys.readouterr().out.splitlines()[0] == "SA117 scope / publication gates:"
