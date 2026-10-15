"""
Behavioral controls for the SA267(b) ``publish_module`` script split.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the split's structural invariants and the exact CLI and seal diagnostics
captured from the pre-split module as behavioral tests, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import sys
from collections.abc import Callable
from pathlib import Path

import _publish_module_core as core_module
import _publish_module_git as git_module
import publish_module
import pytest

_ROOT = publish_module

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

VERSION = "0.88.0"
HEAD_SHA = "a" * 40
OTHER_SHA = "b" * 40


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
