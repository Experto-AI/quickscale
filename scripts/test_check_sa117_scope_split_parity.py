"""
Behavioral controls for the SA267(d) ``check_sa117_scope`` script split.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the split's structural invariants and the exact gate diagnostics
captured from the pre-split module as behavioral tests, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
from pathlib import Path

import check_sa117_scope as scope_check
import pytest

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_sa117_lock_diff": "check_sa117_scope",
    "_sa117_lock_parse": "check_sa117_scope",
    "_sa117_scope_contract": "check_sa117_scope",
}


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
