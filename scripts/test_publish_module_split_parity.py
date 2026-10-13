"""
Parity controls for the SA267(b) ``publish_module`` script split.

``publish_module`` keeps its pre-split surface through private
``_publish_module_*`` siblings.  These controls pin the preserved surface, the
split's structural invariants, the module homes of the moved callables, and
the exact CLI and seal diagnostics captured from the pre-split module, so a
later slice cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import inspect
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import _publish_module_core as core_module
import _publish_module_git as git_module
import publish_module
import pytest

_ROOT = publish_module

#: Every pre-split name consumers reach through the facade.  The facade must
#: keep every one of them.
FROZEN_FACADE_SURFACE = (
    "BLUE",
    "GREEN",
    "GitError",
    "GitRunner",
    "NC",
    "RED",
    "RemoteBranchAbsentError",
    "SealBatchOutcome",
    "SealError",
    "SealOutcome",
    "SealResult",
    "YELLOW",
    "Path",
    "_CORE_SRC",
    "_REPO_ROOT",
    "_SEAL_SHA_RE",
    "_build_parser",
    "_check_release_authoritative",
    "_cleanup_created_tag",
    "_confirm_uncommitted_changes",
    "_get_local_split_sha",
    "_get_module_publish_state",
    "_get_module_seal_state",
    "_has_uncommitted_changes",
    "_head_tree",
    "_invoke_seal_module",
    "_list_modules",
    "_maybe_clean_subtree_cache",
    "_observe_remote_branch_sha",
    "_parse_remote_records",
    "_print_error",
    "_print_info",
    "_print_seal_batch_summary",
    "_print_success",
    "_print_warning",
    "_publish_all",
    "_publish_module",
    "_read_repository_version",
    "_report_publish_outdated_disabled",
    "_require_authoritative_module",
    "_require_fast_forward",
    "_run_release_gates",
    "_seal_all",
    "_seal_error",
    "_seal_module",
    "_seal_sha",
    "_show_provenance_diagnostics",
    "_show_status",
    "_validate_cli_args",
    "_validate_seal_version",
    "_warn_uncommitted_changes",
    "argparse",
    "build_publication_git_runner",
    "create_annotated_tag",
    "dataclass",
    "delete_local_tag",
    "get_local_tag_commit",
    "get_tree_sha",
    "inspect",
    "is_git_repo",
    "is_release_authoritative",
    "is_working_directory_clean",
    "main",
    "push_split_branch",
    "push_tag",
    "re",
    "resolve_module_path",
    "resolve_remote_ref",
    "resolve_split_branch",
    "resolve_split_tag",
    "run_git_subtree_split",
    "shutil",
    "sys",
    "validate_expected_sha",
    "validate_module_name",
    "validate_publication_local_config",
    "validate_publication_origin",
    "validate_tag_name",
)

#: Every non-underscore name the pre-split module defined; the facade's
#: ``__all__`` must keep all of them so a wildcard import keeps its surface.
FROZEN_WILDCARD_SURFACE = (
    "BLUE",
    "GREEN",
    "NC",
    "RED",
    "YELLOW",
    "RemoteBranchAbsentError",
    "SealBatchOutcome",
    "SealError",
    "SealOutcome",
    "SealResult",
    "create_annotated_tag",
    "delete_local_tag",
    "get_local_tag_commit",
    "get_tree_sha",
    "main",
    "push_tag",
    "resolve_remote_ref",
)

#: Non-underscore imported bindings the pre-split wildcard import also bound;
#: the facade keeps them as attributes but excludes them from ``__all__``.
FROZEN_INCIDENTAL_BINDINGS = (
    "GitError",
    "GitRunner",
    "Path",
    "argparse",
    "build_publication_git_runner",
    "dataclass",
    "inspect",
    "is_git_repo",
    "is_release_authoritative",
    "is_working_directory_clean",
    "push_split_branch",
    "re",
    "resolve_module_path",
    "resolve_split_branch",
    "resolve_split_tag",
    "run_git_subtree_split",
    "shutil",
    "sys",
    "validate_expected_sha",
    "validate_module_name",
    "validate_publication_local_config",
    "validate_publication_origin",
    "validate_tag_name",
)

#: ``(name, expected ``__module__``)`` for the split's callables and classes.
#: Facade-owned orchestration stays in the facade; moved helpers keep their
#: defining sibling.
FROZEN_HOMES = {
    "main": "publish_module",
    "_dispatch_action": "publish_module",
    "_run_seal_action": "publish_module",
    "_run_seal_all_action": "publish_module",
    "_run_publish_all_action": "publish_module",
    "_run_single_publish_action": "publish_module",
    "_run_status_action": "publish_module",
    "_list_modules": "_publish_module_core",
    "_require_authoritative_module": "_publish_module_core",
    "_read_repository_version": "_publish_module_core",
    "_validate_seal_version": "_publish_module_core",
    "_print_info": "_publish_module_core",
    "_print_success": "_publish_module_core",
    "_print_warning": "_publish_module_core",
    "_print_error": "_publish_module_core",
    "SealError": "_publish_module_git",
    "RemoteBranchAbsentError": "_publish_module_git",
    "_seal_error": "_publish_module_git",
    "_seal_sha": "_publish_module_git",
    "_parse_remote_records": "_publish_module_git",
    "resolve_remote_ref": "_publish_module_git",
    "get_tree_sha": "_publish_module_git",
    "get_local_tag_commit": "_publish_module_git",
    "create_annotated_tag": "_publish_module_git",
    "push_tag": "_publish_module_git",
    "delete_local_tag": "_publish_module_git",
    "_has_uncommitted_changes": "_publish_module_git",
    "_warn_uncommitted_changes": "_publish_module_git",
    "_confirm_uncommitted_changes": "_publish_module_git",
    "_maybe_clean_subtree_cache": "_publish_module_git",
    "_get_local_split_sha": "_publish_module_git",
    "_observe_remote_branch_sha": "_publish_module_git",
    "SealOutcome": "_publish_module_seal",
    "SealBatchOutcome": "_publish_module_seal",
    "_cleanup_created_tag": "_publish_module_seal",
    "_seal_module": "_publish_module_seal",
    "_invoke_seal_module": "_publish_module_seal",
    "_print_seal_batch_summary": "_publish_module_seal",
    "_seal_all": "_publish_module_seal",
    "_check_release_authoritative": "_publish_module_publish",
    "_require_fast_forward": "_publish_module_publish",
    "_publish_module": "_publish_module_publish",
    "_publish_all": "_publish_module_publish",
    "_head_tree": "_publish_module_publish",
    "_run_release_gates": "_publish_module_publish",
    "_show_provenance_diagnostics": "_publish_module_status",
    "_get_module_publish_state": "_publish_module_status",
    "_get_module_seal_state": "_publish_module_status",
    "_show_status": "_publish_module_status",
    "_build_parser": "_publish_module_cli",
    "_validate_cli_args": "_publish_module_cli",
    "_report_publish_outdated_disabled": "_publish_module_cli",
}

#: ``(module, facet module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_publish_module_cli": "publish_module",
    "_publish_module_core": "publish_module",
    "_publish_module_git": "publish_module",
    "_publish_module_publish": "publish_module",
    "_publish_module_seal": "publish_module",
    "_publish_module_status": "publish_module",
}

#: The pre-split signature of every callable consumers invoke.
FROZEN_SIGNATURES = {
    "main": "() -> 'None'",
    "_build_parser": "() -> 'argparse.ArgumentParser'",
    "_validate_cli_args": (
        "(parser: 'argparse.ArgumentParser', args: 'argparse.Namespace') -> 'None'"
    ),
    "_list_modules": "() -> 'list[str]'",
    "_require_authoritative_module": "(module_name: 'str') -> 'None'",
    "_has_uncommitted_changes": "(runner: 'GitRunner') -> 'bool'",
    "_warn_uncommitted_changes": "(runner: 'GitRunner') -> 'None'",
    "_confirm_uncommitted_changes": "(runner: 'GitRunner') -> 'bool'",
    "_maybe_clean_subtree_cache": "(clean: 'bool') -> 'None'",
    "_read_repository_version": "() -> 'str'",
    "_validate_seal_version": "(requested_version: 'str') -> 'None'",
    "_seal_error": (
        "(message: 'str', *, module: 'str', version: 'str', "
        "cleanup_error: 'str | None' = None) -> 'SealError'"
    ),
    "_seal_sha": (
        "(value: 'object', *, description: 'str', module: 'str', version: 'str') -> 'str'"
    ),
    "_parse_remote_records": (
        "(output: 'object', *, expected_refs: 'set[str]', description: 'str', "
        "module: 'str', version: 'str') -> 'dict[str, str]'"
    ),
    "resolve_remote_ref": (
        "(remote: 'str', ref: 'str', path: 'Path | None' = None, *, runner: 'GitRunner') -> 'str'"
    ),
    "get_tree_sha": (
        "(commit: 'str', path: 'Path | None' = None, *, runner: 'GitRunner') -> 'str'"
    ),
    "get_local_tag_commit": (
        "(tag: 'str', path: 'Path | None' = None, *, runner: 'GitRunner') -> 'str | None'"
    ),
    "create_annotated_tag": (
        "(tag: 'str', commit: 'str', path: 'Path | None' = None, *, runner: 'GitRunner') -> 'None'"
    ),
    "push_tag": (
        "(tag: 'str', remote: 'str' = 'origin', path: 'Path | None' = None, "
        "*, refspec: 'str | None' = None, runner: 'GitRunner') -> 'None'"
    ),
    "delete_local_tag": (
        "(tag: 'str', path: 'Path | None' = None, *, runner: 'GitRunner') -> 'None'"
    ),
    "_cleanup_created_tag": "(tag: 'str', *, armed: 'bool', runner: 'GitRunner') -> 'str | None'",
    "_seal_module": (
        "(module: 'str', version: 'str', *, previous_version: 'str | None' = None, "
        "runner: 'GitRunner') -> 'SealOutcome'"
    ),
    "_invoke_seal_module": (
        "(module: 'str', version: 'str', *, previous_version: 'str | None', "
        "runner: 'GitRunner') -> 'SealOutcome'"
    ),
    "_print_seal_batch_summary": "(outcome: 'SealBatchOutcome') -> 'None'",
    "_seal_all": (
        "(version: 'str', *, previous_version: 'str | None' = None, runner: 'GitRunner', "
        "modules: 'list[str] | tuple[str, ...] | None' = None) -> 'SealBatchOutcome'"
    ),
    "_check_release_authoritative": "(runner: 'GitRunner') -> 'None'",
    "_get_local_split_sha": "(module_path: 'str', runner: 'GitRunner') -> 'str | None'",
    "_require_fast_forward": (
        "(expected_remote_sha: 'str', local_split_sha: 'str', *, runner: 'GitRunner') -> 'None'"
    ),
    "_publish_module": (
        "(module_name: 'str', *, expected_remote_sha: 'str', runner: 'GitRunner') -> 'None'"
    ),
    "_show_provenance_diagnostics": "(runner: 'GitRunner') -> 'bool'",
    "_observe_remote_branch_sha": "(module_name: 'str', runner: 'GitRunner') -> 'str | None'",
    "_get_module_publish_state": (
        "(module_name: 'str', runner: 'GitRunner') -> 'tuple[str, str, str, str]'"
    ),
    "_get_module_seal_state": (
        "(module_name: 'str', version: 'str', published_sha: 'str', runner: 'GitRunner') -> 'str'"
    ),
    "_show_status": (
        "(runner: 'GitRunner', *, version: 'str | None' = None, "
        "modules: 'list[str] | tuple[str, ...] | None' = None) -> 'bool'"
    ),
    "_publish_all": "(runner: 'GitRunner', *, modules: 'list[str]') -> 'None'",
    "_head_tree": "(runner: 'GitRunner') -> 'str'",
    "_run_release_gates": "(runner: 'GitRunner') -> 'None'",
    "_report_publish_outdated_disabled": "() -> 'None'",
}

VERSION = "0.88.0"
HEAD_SHA = "a" * 40
OTHER_SHA = "b" * 40


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function))


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every consumer-reachable pre-split name stays on the facade."""
    missing = [name for name in FROZEN_FACADE_SURFACE if not hasattr(_ROOT, name)]
    assert missing == []


def test_facade_wildcard_surface_keeps_the_pre_split_public_names() -> None:
    """``__all__`` keeps every non-underscore pre-split definition."""
    missing = [name for name in FROZEN_WILDCARD_SURFACE if name not in _ROOT.__all__]
    assert missing == []
    for name in _ROOT.__all__:
        assert hasattr(_ROOT, name), name


def test_facade_wildcard_surface_excludes_incidental_bindings() -> None:
    """
    The narrower wildcard contract is explicit, documented, and tested.

    Pre-split, ``from publish_module import *`` also bound incidental imported
    names.  decisions.md § Split-Facade Seams has facades re-export public
    names only, so those names stay attributes of the facade but are
    deliberately excluded from the wildcard surface.
    """
    for name in FROZEN_INCIDENTAL_BINDINGS:
        assert hasattr(_ROOT, name), name
        assert name not in _ROOT.__all__, name


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    import argparse as argparse_module
    import dataclasses as dataclasses_module
    import re as re_module
    import shutil as shutil_module
    import sys as sys_module
    from pathlib import Path as Path_class

    assert _ROOT.argparse is argparse_module
    assert _ROOT.dataclass is dataclasses_module.dataclass
    assert _ROOT.inspect is inspect
    assert _ROOT.re is re_module
    assert _ROOT.shutil is shutil_module
    assert _ROOT.sys is sys_module
    assert _ROOT.Path is Path_class
    assert _ROOT.GitError is git_module.GitError
    assert _ROOT.GitRunner is git_module.GitRunner
    assert _ROOT.resolve_split_branch is git_module.resolve_split_branch
    assert _ROOT.resolve_module_path is git_module.resolve_module_path


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {name: _normalized_signature(getattr(_ROOT, name)) for name in FROZEN_SIGNATURES}
    assert observed == FROZEN_SIGNATURES


def test_helpers_keep_their_homes() -> None:
    """Facade-owned orchestration stays in the facade; split helpers keep their sibling."""
    observed = {name: getattr(getattr(_ROOT, name), "__module__") for name in FROZEN_HOMES}
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
# CLI diagnostics captured from the pre-split module
# ---------------------------------------------------------------------------

CLI_ERROR_CASES = (
    (["--status", "auth"], "--status does not accept a module name"),
    (["--status", "--clean"], "--clean is only supported with publish actions"),
    (
        ["--status", "--expected-remote-sha", "a" * 40],
        "--expected-remote-sha is not supported with --status",
    ),
    (
        ["--status", "--previous-version", "0.87.0"],
        "--previous-version is only supported with --seal or --seal-all",
    ),
    (["--seal", "--version", VERSION], "--seal requires a module name"),
    (["--seal", "--version", VERSION, "--clean"], "--seal requires a module name"),
    (
        ["auth", "--seal", "--clean", "--version", VERSION],
        "--clean is only supported with publish actions",
    ),
    (
        ["auth", "--seal", "--version", VERSION, "--expected-remote-sha", "a" * 40],
        "--expected-remote-sha is not supported with --seal",
    ),
    (["auth", "--seal"], "--seal requires --version VERSION"),
    (["--seal-all", "--version", VERSION, "auth"], "--seal-all does not accept a module name"),
    (["--seal-all"], "--seal-all requires --version VERSION"),
    (
        ["--seal-all", "--version", VERSION, "--clean"],
        "--clean is only supported with publish actions",
    ),
    (
        ["--seal-all", "--version", VERSION, "--expected-remote-sha", "a" * 40],
        "--expected-remote-sha is not supported with --seal-all",
    ),
    (["--publish-all", "auth"], "--publish-all does not accept a module name"),
    (
        ["--publish-all", "--expected-remote-sha", "a" * 40],
        "--expected-remote-sha is not supported with --publish-all",
    ),
    (["--publish-all", "--version", VERSION], "--version is not supported with --publish-all"),
    (["--clean"], "publish options require a module name"),
    (["--expected-remote-sha", "a" * 40], "publish options require a module name"),
    (["--version", VERSION], "--version is only supported with --seal, --seal-all, or --status"),
    (
        ["--previous-version", "0.87.0"],
        "--previous-version is only supported with --seal or --seal-all",
    ),
)

SINGLE_PUBLISH_ERROR_CASES = (
    (
        ["auth"],
        "\x1b[0;31m❌ --expected-remote-sha is required for single-module publish "
        "(use a freshly observed exact 40-hex remote SHA)\x1b[0m",
    ),
    (
        ["auth", "--expected-remote-sha", "not-a-sha"],
        "\x1b[0;31m❌ Invalid --expected-remote-sha: expected_remote_sha must be exactly "
        "40 hex characters; got 9-char value\x1b[0m",
    ),
)


def _run_cli_validation(monkeypatch: pytest.MonkeyPatch, argv: list[str]) -> tuple[int, str]:
    """Return ``(exit code, combined output)`` for one argument-validation run."""
    monkeypatch.setattr(sys, "argv", ["publish_module.py", *argv])
    parser = _ROOT._build_parser()
    args = parser.parse_args()
    try:
        _ROOT._validate_cli_args(parser, args)
    except SystemExit as exc:
        return int(exc.code or 0), ""
    return 0, "accepted"


@pytest.mark.parametrize(
    ("argv", "message"), CLI_ERROR_CASES, ids=[repr(c[0]) for c in CLI_ERROR_CASES]
)
def test_cli_rejections_keep_their_exact_messages(
    argv: list[str],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every invalid combination keeps its pre-split exit code and message."""
    code, _ = _run_cli_validation(monkeypatch, argv)
    captured = capsys.readouterr()
    assert code == 2
    assert captured.err.splitlines()[-1] == f"publish_module.py: error: {message}"


@pytest.mark.parametrize(
    ("argv", "message"),
    SINGLE_PUBLISH_ERROR_CASES,
    ids=["missing-sha", "malformed-sha"],
)
def test_single_publish_rejections_keep_their_exact_messages(
    argv: list[str],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The required and validated --expected-remote-sha diagnostics are exact."""
    code, _ = _run_cli_validation(monkeypatch, argv)
    captured = capsys.readouterr()
    assert code == 1
    assert captured.out == f"{message}\n"


def test_publish_outdated_precedes_every_conflicting_option_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The disabled action stays parseable with otherwise conflicting options."""
    argv = [
        "--publish-outdated",
        "--status",
        "--clean",
        "--version",
        VERSION,
        "--previous-version",
        "0.87.0",
        "--expected-remote-sha",
        "a" * 40,
        "auth",
    ]
    assert _run_cli_validation(monkeypatch, argv) == (0, "accepted")


def test_seal_version_mismatch_keeps_its_exact_message(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The F-007 version binding keeps its pre-split diagnostic."""
    monkeypatch.setattr(core_module, "_read_repository_version", lambda: "0.87.0")
    with pytest.raises(SystemExit) as excinfo:
        _ROOT._validate_seal_version(VERSION)
    assert excinfo.value.code == 1
    assert capsys.readouterr().out == (
        "\x1b[0;31m❌ Seal version mismatch: requested 0.88.0, repository VERSION 0.87.0\x1b[0m\n"
    )


def test_authoritative_module_rejection_keeps_its_exact_diagnostic(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The F-002 inventory rejection keeps its pre-split wording and order."""
    monkeypatch.setattr(
        core_module, "_list_modules", lambda: [f"module_{index:02d}" for index in range(3)]
    )
    with pytest.raises(SystemExit) as excinfo:
        _ROOT._require_authoritative_module("nonexistent")
    assert excinfo.value.code == 1
    assert capsys.readouterr().out == (
        "\x1b[0;31m❌ Module 'nonexistent' is not in the authoritative shipped-module "
        "inventory.\x1b[0m\n"
        "\n"
        "\x1b[0;34mℹ️  Available modules:\x1b[0m\n"
        "  - module_00\n"
        "  - module_01\n"
        "  - module_02\n"
    )


# ---------------------------------------------------------------------------
# Seal error composition captured from the pre-split module
# ---------------------------------------------------------------------------


def _raiser(error: Exception) -> Callable[..., None]:
    def _raise(*args: object, **kwargs: object) -> None:
        del args, kwargs
        raise error

    return _raise


class _Probe:
    """Scripted remote resolver that distinguishes the initial read from the probe."""

    def __init__(self, *, probe_value: str | None = None, probe_error: str | None = None) -> None:
        self.push_attempted = False
        self.probe_value = probe_value
        self.probe_error = probe_error

    def resolve(self, remote: str, ref: str, path: Path | None = None, *, runner: object) -> str:
        del remote, path, runner
        if ref == "splits/auth-module":
            return HEAD_SHA
        if ref == "splits/auth-module/0.88.0":
            if self.push_attempted:
                if self.probe_error is not None:
                    raise git_module.GitError(self.probe_error)
                return self.probe_value or ""
            return ""
        raise AssertionError(f"unexpected ref {ref!r}")

    def push(self, *args: object, **kwargs: object) -> None:
        del args, kwargs
        self.push_attempted = True
        raise git_module.GitError("remote rejected tag")


def _install_seal_probe(
    monkeypatch: pytest.MonkeyPatch, probe: _Probe, *, push_seam: Callable[..., None] | None = None
) -> None:
    monkeypatch.setattr(git_module, "resolve_split_branch", lambda module: "splits/auth-module")
    monkeypatch.setattr(
        git_module, "resolve_split_tag", lambda module, version: f"splits/auth-module/{version}"
    )
    monkeypatch.setattr(git_module, "resolve_remote_ref", probe.resolve)
    monkeypatch.setattr(git_module, "get_local_tag_commit", lambda tag, path=None, *, runner: None)
    monkeypatch.setattr(git_module, "create_annotated_tag", lambda *args, **kwargs: None)
    monkeypatch.setattr(git_module, "push_tag", push_seam or probe.push)
    monkeypatch.setattr(git_module, "delete_local_tag", lambda *args, **kwargs: None)


def test_create_failure_with_cleanup_failure_composes_the_exact_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Primary error, then the cleanup suffix, exactly as before the split."""
    probe = _Probe()
    _install_seal_probe(monkeypatch, probe)
    monkeypatch.setattr(
        git_module,
        "create_annotated_tag",
        _raiser(git_module.GitError("local tag creation failed")),
    )
    monkeypatch.setattr(
        git_module,
        "delete_local_tag",
        _raiser(git_module.GitError("local tag deletion failed")),
    )

    with pytest.raises(publish_module.SealError) as excinfo:
        _ROOT._seal_module("auth", VERSION, runner=object())

    assert str(excinfo.value) == (
        "local tag creation failed; local cleanup also failed: local tag deletion failed"
    )
    assert excinfo.value.cleanup_error == "local tag deletion failed"


def test_push_failure_with_conflicting_probe_composes_the_exact_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A conflicting remote probe stays a secondary suffix on the push failure."""
    probe = _Probe(probe_value=OTHER_SHA)
    _install_seal_probe(monkeypatch, probe)

    with pytest.raises(publish_module.SealError) as excinfo:
        _ROOT._seal_module("auth", VERSION, runner=object())

    assert str(excinfo.value) == (
        "Tag push failed for 'splits/auth-module/0.88.0': remote rejected tag; "
        f"remote tag probe found conflicting commit {OTHER_SHA} != {HEAD_SHA}"
    )
    assert excinfo.value.cleanup_error is None


def test_push_failure_with_probe_error_composes_the_exact_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An unreadable probe reports its own failure without masking the push error."""
    probe = _Probe(probe_error="probe unavailable")
    _install_seal_probe(monkeypatch, probe)

    with pytest.raises(publish_module.SealError) as excinfo:
        _ROOT._seal_module("auth", VERSION, runner=object())

    assert str(excinfo.value) == (
        "Tag push failed for 'splits/auth-module/0.88.0': remote rejected tag; "
        "remote tag probe failed: probe unavailable"
    )


def test_push_failure_with_empty_probe_keeps_only_the_push_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An empty probe adds no suffix."""
    probe = _Probe()
    _install_seal_probe(monkeypatch, probe)

    with pytest.raises(publish_module.SealError) as excinfo:
        _ROOT._seal_module("auth", VERSION, runner=object())

    assert str(excinfo.value) == (
        "Tag push failed for 'splits/auth-module/0.88.0': remote rejected tag"
    )
