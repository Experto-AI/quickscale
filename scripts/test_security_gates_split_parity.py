"""
Parity controls for the SA267(c) ``check_security_gates`` script split.

``check_security_gates`` keeps its pre-split surface through private
``_security_gates_*`` siblings.  These controls pin the preserved surface, the
split's structural invariants, the module homes of the moved callables, and
the exact gate diagnostics captured from the pre-split module, so a later
slice cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import argparse as argparse
import ast
import atexit as atexit
import fnmatch
import hashlib as hashlib
import inspect
import json as json
import os as os
import platform as platform
import re as re
import shutil as shutil
import signal as signal
import stat as stat
import subprocess as subprocess
import sys as sys
import tarfile as tarfile
import tempfile as tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any as Any
from urllib.parse import urlparse as urlparse
from urllib.request import Request as Request
from urllib.request import urlopen as urlopen

import _security_gates_adjudication as adjudication
import _security_gates_bandit as bandit_module
import _security_gates_probes as probes_module
import _security_gates_support as support
import _security_gates_trivy as trivy_module
import check_security_gates as gates
import pytest

#: Every pre-split name consumers reach through the facade.  The facade must
#: keep every one of them.
FROZEN_FACADE_SURFACE = (
    "Any",
    "BAD_DOCKERFILE_PROBE",
    "BANDIT_TESTS",
    "BANDIT_VERSION",
    "CATEGORY_TESTS",
    "COMMAND_TIMEOUT",
    "Completed",
    "EXCLUDED_PARTS",
    "FindingsError",
    "GENERATED_PROJECT_SLUG",
    "GateError",
    "LOCK_NAME",
    "MISCONFIG_SEVERITIES",
    "MODULES_ROOT",
    "PROBES_PATH",
    "Path",
    "ROOT",
    "Request",
    "SUPPRESSIONS_PATH",
    "SUPPRESSION_KEYS",
    "TRIVY_ASSETS",
    "TRIVY_RELEASE_URL",
    "TRIVY_VERSION",
    "_adjudicate",
    "_bandit_findings",
    "_bandit_fingerprint",
    "_bandit_project",
    "_bandit_scan",
    "_cleanup",
    "_discover_module_source_roots",
    "_download",
    "_generated_dockerfile",
    "_load_suppressions",
    "_load_toml",
    "_lock_inventory",
    "_misconfig_command",
    "_new_temp_dir",
    "_probe_lock",
    "_run_dependency_gate",
    "_safe_archive_members",
    "_signal_handler",
    "_source_files",
    "_source_roots",
    "_terminate_process_group",
    "_trivy_asset",
    "_trivy_finding",
    "_trivy_misconfig_scan",
    "_trivy_scan",
    "acquire_trivy",
    "argparse",
    "atexit",
    "dataclass",
    "date",
    "dependency_gate",
    "hashlib",
    "json",
    "main",
    "negative_probes",
    "os",
    "platform",
    "re",
    "run_command",
    "shutil",
    "signal",
    "stat",
    "static_gate",
    "strict_json",
    "subprocess",
    "sys",
    "tarfile",
    "tempfile",
    "urlopen",
    "urlparse",
)

#: Every non-underscore name the pre-split module defined; the facade's
#: ``__all__`` must keep all of them so a wildcard import keeps its surface.
FROZEN_WILDCARD_SURFACE = (
    "BAD_DOCKERFILE_PROBE",
    "BANDIT_TESTS",
    "BANDIT_VERSION",
    "CATEGORY_TESTS",
    "COMMAND_TIMEOUT",
    "Completed",
    "EXCLUDED_PARTS",
    "FindingsError",
    "GENERATED_PROJECT_SLUG",
    "GateError",
    "LOCK_NAME",
    "MISCONFIG_SEVERITIES",
    "MODULES_ROOT",
    "PROBES_PATH",
    "ROOT",
    "SUPPRESSIONS_PATH",
    "SUPPRESSION_KEYS",
    "TRIVY_ASSETS",
    "TRIVY_RELEASE_URL",
    "TRIVY_VERSION",
    "acquire_trivy",
    "dependency_gate",
    "main",
    "negative_probes",
    "run_command",
    "static_gate",
    "strict_json",
)

#: Non-underscore imported bindings the pre-split wildcard import also bound;
#: the facade keeps them as attributes but excludes them from ``__all__``.
FROZEN_INCIDENTAL_BINDINGS = (
    "Any",
    "Path",
    "Request",
    "argparse",
    "atexit",
    "dataclass",
    "date",
    "hashlib",
    "json",
    "os",
    "platform",
    "re",
    "shutil",
    "signal",
    "stat",
    "subprocess",
    "sys",
    "tarfile",
    "tempfile",
    "urlopen",
    "urlparse",
)

#: ``(name, expected ``__module__``)`` for the pre-split callables and classes.
#: Facade-owned orchestration stays in the facade; moved names keep their
#: defining sibling.
FROZEN_HOMES = {
    "main": "check_security_gates",
    "Completed": "_security_gates_support",
    "FindingsError": "_security_gates_support",
    "GateError": "_security_gates_support",
    "_cleanup": "_security_gates_support",
    "_new_temp_dir": "_security_gates_support",
    "_signal_handler": "_security_gates_support",
    "_terminate_process_group": "_security_gates_support",
    "run_command": "_security_gates_support",
    "strict_json": "_security_gates_support",
    "_adjudicate": "_security_gates_adjudication",
    "_load_suppressions": "_security_gates_adjudication",
    "_bandit_findings": "_security_gates_bandit",
    "_bandit_fingerprint": "_security_gates_bandit",
    "_bandit_project": "_security_gates_bandit",
    "_bandit_scan": "_security_gates_bandit",
    "_discover_module_source_roots": "_security_gates_bandit",
    "_source_files": "_security_gates_bandit",
    "_source_roots": "_security_gates_bandit",
    "static_gate": "_security_gates_bandit",
    "_probe_lock": "_security_gates_probes",
    "negative_probes": "_security_gates_probes",
    "_download": "_security_gates_trivy",
    "_generated_dockerfile": "_security_gates_trivy",
    "_load_toml": "_security_gates_trivy",
    "_lock_inventory": "_security_gates_trivy",
    "_misconfig_command": "_security_gates_trivy",
    "_run_dependency_gate": "_security_gates_trivy",
    "_safe_archive_members": "_security_gates_trivy",
    "_trivy_asset": "_security_gates_trivy",
    "_trivy_finding": "_security_gates_trivy",
    "_trivy_misconfig_scan": "_security_gates_trivy",
    "_trivy_scan": "_security_gates_trivy",
    "acquire_trivy": "_security_gates_trivy",
    "dependency_gate": "_security_gates_trivy",
}

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_security_gates_adjudication": "check_security_gates",
    "_security_gates_bandit": "check_security_gates",
    "_security_gates_probes": "check_security_gates",
    "_security_gates_support": "check_security_gates",
    "_security_gates_trivy": "check_security_gates",
}

#: The pre-split signature of every callable consumers invoke.
FROZEN_SIGNATURES = {
    "main": "(argv: 'list[str] | None' = None) -> 'int'",
    "run_command": (
        "(argv: 'list[str]', *, cwd: 'Path | None' = None, timeout: 'float' = 180.0) -> 'Completed'"
    ),
    "strict_json": "(text: 'str', *, source: 'str') -> 'Any'",
    "acquire_trivy": "() -> 'Path'",
    "dependency_gate": "() -> 'int'",
    "static_gate": "() -> 'int'",
    "negative_probes": "() -> 'int'",
    "_adjudicate": (
        "(findings: 'list[dict[str, Any]]', *, executed_scanners: 'set[str]') -> "
        "'tuple[list[dict[str, Any]], list[dict[str, Any]]]'"
    ),
    "_load_suppressions": "() -> 'list[dict[str, Any]]'",
    "_new_temp_dir": "(prefix: 'str') -> 'Path'",
    "_terminate_process_group": "(process: 'subprocess.Popen[str]') -> 'None'",
    "_cleanup": "() -> 'None'",
    "_signal_handler": "(signum: 'int', _frame: 'Any') -> 'None'",
    "_trivy_asset": "() -> 'tuple[str, str]'",
    "_download": "(url: 'str', destination: 'Path') -> 'None'",
    "_safe_archive_members": (
        "(archive: 'tarfile.TarFile', destination: 'Path') -> 'list[tarfile.TarInfo]'"
    ),
    "_load_toml": "(path: 'Path') -> 'dict[str, Any]'",
    "_lock_inventory": "(lock_path: 'Path') -> 'tuple[set[tuple[str, str]], str, bool]'",
    "_trivy_scan": (
        "(trivy: 'Path', project: 'str', lock_path: 'Path') -> "
        "'tuple[list[dict[str, Any]], dict[str, Any]]'"
    ),
    "_generated_dockerfile": "(destination: 'Path') -> 'Path'",
    "_misconfig_command": "(trivy: 'Path', dockerfile: 'Path') -> 'list[str]'",
    "_trivy_misconfig_scan": (
        "(trivy: 'Path', dockerfile: 'Path') -> 'tuple[list[dict[str, Any]], dict[str, Any]]'"
    ),
    "_bandit_project": "(path: 'Path') -> 'str'",
    "_bandit_fingerprint": "(project: 'str', path: 'str', test_id: 'str', line: 'int') -> 'str'",
    "_bandit_findings": "(report: 'dict[str, Any]') -> 'list[dict[str, Any]]'",
    "_source_files": "() -> 'list[Path]'",
    "_bandit_scan": "() -> 'tuple[list[dict[str, Any]], dict[str, Any]]'",
    "_discover_module_source_roots": "() -> 'tuple[Path, ...]'",
    "_source_roots": "() -> 'tuple[Path, ...]'",
    "_trivy_finding": "(item: 'dict[str, Any]', project: 'str') -> 'dict[str, Any]'",
    "_run_dependency_gate": "(trivy: 'Path', dockerfile: 'Path') -> 'int'",
    "_probe_lock": "(path: 'Path') -> 'None'",
}


def _normalized_signature(function: Callable[..., Any]) -> str:
    return str(inspect.signature(function))


def test_facade_publishes_the_pre_split_surface() -> None:
    """Every consumer-reachable pre-split name stays on the facade."""
    missing = [name for name in FROZEN_FACADE_SURFACE if not hasattr(gates, name)]
    assert missing == []


def test_facade_wildcard_surface_keeps_the_pre_split_public_names() -> None:
    """``__all__`` keeps every non-underscore pre-split definition."""
    missing = [name for name in FROZEN_WILDCARD_SURFACE if name not in gates.__all__]
    assert missing == []
    for name in gates.__all__:
        assert hasattr(gates, name), name


def test_facade_wildcard_surface_excludes_incidental_bindings() -> None:
    """
    The narrower wildcard contract is explicit, documented, and tested.

    Pre-split, ``from check_security_gates import *`` also bound incidental
    imported names.  decisions.md § Split-Facade Seams has facades re-export
    public names only, so those names stay attributes of the facade but are
    deliberately excluded from the wildcard surface.
    """
    for name in FROZEN_INCIDENTAL_BINDINGS:
        assert hasattr(gates, name), name
        assert name not in gates.__all__, name


def test_facade_preserves_the_pre_split_imported_bindings() -> None:
    """The pre-split module's own imports stay importable through the facade."""
    from dataclasses import dataclass as dataclasses_dataclass
    from datetime import date as datetime_date
    from pathlib import Path as Path_class
    from typing import Any as Any_type
    from urllib.request import Request as Request_class
    from urllib.request import urlopen as urlopen_function

    expected = {
        "argparse": argparse,
        "atexit": atexit,
        "hashlib": hashlib,
        "json": json,
        "os": os,
        "platform": platform,
        "re": re,
        "shutil": shutil,
        "signal": signal,
        "stat": stat,
        "subprocess": subprocess,
        "sys": sys,
        "tarfile": tarfile,
        "tempfile": tempfile,
        "dataclass": dataclasses_dataclass,
        "date": datetime_date,
        "Path": Path_class,
        "Any": Any_type,
        "urlparse": urlparse,
        "Request": Request_class,
        "urlopen": urlopen_function,
    }
    mismatched = [name for name, value in expected.items() if getattr(gates, name) is not value]
    assert mismatched == []


def test_facade_attributes_are_the_defining_sibling_objects() -> None:
    """The facade re-exports the sibling objects instead of copying them."""
    assert gates.ROOT is support.ROOT
    assert gates.GateError is support.GateError
    assert gates.FindingsError is support.FindingsError
    assert gates.Completed is support.Completed
    assert gates.run_command is support.run_command
    assert gates._adjudicate is adjudication._adjudicate
    assert gates._load_suppressions is adjudication._load_suppressions
    assert gates.TRIVY_VERSION is trivy_module.TRIVY_VERSION
    assert gates.acquire_trivy is trivy_module.acquire_trivy
    assert gates._trivy_scan is trivy_module._trivy_scan
    assert gates.BANDIT_VERSION is bandit_module.BANDIT_VERSION
    assert gates.static_gate is bandit_module.static_gate
    assert gates.PROBES_PATH is probes_module.PROBES_PATH
    assert gates.negative_probes is probes_module.negative_probes


def test_frozen_callable_signatures_are_unchanged() -> None:
    """Each callable consumers invoke keeps its pre-split signature."""
    observed = {name: _normalized_signature(getattr(gates, name)) for name in FROZEN_SIGNATURES}
    assert observed == FROZEN_SIGNATURES


def test_helpers_keep_their_homes() -> None:
    """Facade-owned orchestration stays in the facade; split helpers keep their sibling."""
    observed = {name: getattr(gates, name).__module__ for name in FROZEN_HOMES}
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

_STANDARD_LOCK = ({("sentinel", "1")}, "sentinel", False)
_SENTINEL_ONLY_LOCK = (set(), "sentinel", False)


def _valid_trivy_report() -> dict[str, Any]:
    return {
        "SchemaVersion": 2,
        "Trivy": {"Version": "0.74.0"},
        "ArtifactName": "poetry.lock",
        "Results": [
            {
                "Target": "poetry.lock",
                "Type": "poetry",
                "Packages": [{"Name": "sentinel", "Version": "1"}],
                "Vulnerabilities": [],
            }
        ],
    }


def _mutated_report(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    report = _valid_trivy_report()
    change(report)
    return report


#: ``(case, report, lock inventory, expected exact message)`` captured from the
#: pre-split ``_trivy_scan``.
TRIVY_REJECTION_CASES = (
    ("schema", lambda: [], _STANDARD_LOCK, "unexpected Trivy JSON schema for probe"),
    (
        "version",
        lambda: _mutated_report(lambda report: report["Trivy"].__setitem__("Version", "0.73.0")),
        _STANDARD_LOCK,
        "Trivy JSON version mismatch for probe",
    ),
    (
        "artifact",
        lambda: _mutated_report(lambda report: report.__setitem__("ArtifactName", "other.lock")),
        _STANDARD_LOCK,
        "Trivy scanned the wrong artifact for probe",
    ),
    (
        "target",
        lambda: _mutated_report(
            lambda report: report["Results"][0].__setitem__("Target", "other.lock")
        ),
        _STANDARD_LOCK,
        "Trivy report contains an unexpected target for probe",
    ),
    (
        "no-inventory",
        lambda: _mutated_report(lambda report: report["Results"][0].pop("Packages")),
        _STANDARD_LOCK,
        "Trivy report has no package inventory for probe",
    ),
    (
        "sentinel",
        lambda: _mutated_report(lambda report: report["Results"][0].__setitem__("Packages", [])),
        _SENTINEL_ONLY_LOCK,
        "Trivy dev/package sentinel is missing for probe: sentinel",
    ),
    (
        "findings",
        lambda: _mutated_report(
            lambda report: report["Results"][0].__setitem__("Vulnerabilities", "nope")
        ),
        _STANDARD_LOCK,
        "invalid Trivy findings for probe",
    ),
)


@pytest.mark.parametrize(
    ("report_factory", "lock_inventory", "message"),
    [case[1:] for case in TRIVY_REJECTION_CASES],
    ids=[case[0] for case in TRIVY_REJECTION_CASES],
)
def test_trivy_scan_rejections_keep_their_exact_messages(
    report_factory: Callable[[], Any],
    lock_inventory: tuple[set[tuple[str, str]], str, bool],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every Trivy validation failure keeps its pre-split wording."""
    monkeypatch.setattr(trivy_module, "_lock_inventory", lambda _path: lock_inventory)
    monkeypatch.setattr(
        support,
        "run_command",
        lambda *_args, **_kwargs: support.Completed(0, json.dumps(report_factory()), ""),
    )
    with pytest.raises(support.GateError) as excinfo:
        gates._trivy_scan(Path("trivy"), "probe", Path("poetry.lock"))
    assert str(excinfo.value) == message


def test_adjudication_stale_message_is_exact(monkeypatch: pytest.MonkeyPatch) -> None:
    """A stale suppression keeps its pre-split cardinality diagnostic."""
    entry = {
        "scanner": "bandit",
        "finding_id": "B105",
        "project": "probe",
        "path": "probe.py",
        "code_identity": "line=1",
        "fingerprint": "stale",
    }
    finding = {
        "scanner": "bandit",
        "finding_id": "B105",
        "project": "probe",
        "path": "probe.py",
        "code_identity": "line=1",
        "fingerprint": "unrelated",
    }
    monkeypatch.setattr(adjudication, "_load_suppressions", lambda: [entry])
    with pytest.raises(support.GateError) as excinfo:
        gates._adjudicate([finding], executed_scanners={"bandit"})
    assert str(excinfo.value) == "suppression cardinality failure (zero or multiple matches): stale"


def test_adjudication_scanner_message_is_exact() -> None:
    """A finding from an unexecuted scanner keeps its pre-split diagnostic."""
    with pytest.raises(support.GateError) as excinfo:
        gates._adjudicate([{"scanner": "trivy"}], executed_scanners={"bandit"})
    assert str(excinfo.value) == "findings include a scanner that was not executed"


def _probe_case_document(**overrides: Any) -> dict[str, Any]:
    document: dict[str, Any] = {
        "schema_version": 1,
        "trivy": {
            "scanner_version": "0.74.0",
            "package": "sqlparse",
            "version": "0.5.5",
            "advisory": "CVE-1",
        },
        "trivy_config": {"scanner_version": "0.74.0", "check_id": "DS-0002", "severity": "HIGH"},
        "bandit": {"version": "1.9.4", "test_id": "B602", "line": 1},
    }
    document.update(overrides)
    return document


_TRIVY_PROBE_RECORD = {
    "scanner_version": "0.74.0",
    "package": "sqlparse",
    "version": "0.5.5",
    "advisory": "CVE-1",
}
_TRIVY_CONFIG_RECORD = {"scanner_version": "0.74.0", "check_id": "DS-0002", "severity": "HIGH"}

#: ``(case, overrides, expected exact message)`` captured from the pre-split
#: probe-case validation inside ``negative_probes``.
PROBE_REJECTION_CASES = (
    ("schema", {"schema_version": 2}, "invalid security probe case schema"),
    (
        "missing-record",
        {"trivy": None},
        "security probe cases must contain Trivy, Trivy-config, and Bandit records",
    ),
    ("missing-identity", {"trivy": {}}, "security probe cases omit required finding identities"),
    (
        "version",
        {"trivy": {**_TRIVY_PROBE_RECORD, "scanner_version": "0.73.0"}},
        "security probe scanner versions do not match the pinned tools",
    ),
    (
        "severity",
        {"trivy_config": {**_TRIVY_CONFIG_RECORD, "severity": "LOW"}},
        "security probe misconfiguration severity is not blocking",
    ),
)


@pytest.mark.parametrize(
    ("overrides", "message"),
    [case[1:] for case in PROBE_REJECTION_CASES],
    ids=[case[0] for case in PROBE_REJECTION_CASES],
)
def test_probe_case_rejections_keep_their_exact_messages(
    overrides: dict[str, Any],
    message: str,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Every probe-case schema failure keeps its pre-split wording."""
    document = _probe_case_document(**overrides)
    probes_path = tmp_path / "probe_cases.json"
    probes_path.write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setattr(probes_module, "PROBES_PATH", probes_path)
    with pytest.raises(support.GateError) as excinfo:
        probes_module._load_probe_cases()
    assert str(excinfo.value) == message


def test_main_requires_a_scanner_mode(capsys: pytest.CaptureFixture[str]) -> None:
    """The CLI keeps its pre-split usage error and exit code."""
    with pytest.raises(SystemExit) as excinfo:
        gates.main([])
    assert excinfo.value.code == 2
    assert capsys.readouterr().err.splitlines()[-1].endswith("error: a scanner mode is required")


def test_main_rejects_conflicting_mode_selectors(capsys: pytest.CaptureFixture[str]) -> None:
    """Contradictory positional and option modes fail with the pre-split message."""
    with pytest.raises(SystemExit) as excinfo:
        gates.main(["static", "--mode", "dependency"])
    assert excinfo.value.code == 2
    assert "error: positional mode and --mode must agree" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# CLI description captured from the pre-split module
# ---------------------------------------------------------------------------

#: The pre-split docstring is the ``--help`` description (``main`` passes
#: ``__doc__`` to ``ArgumentParser``), so it is a user-visible contract and
#: pinned byte-for-byte here.
V89_CLI_DESCRIPTION = (
    "\n"
    "Run QuickScale's fail-closed dependency and static-security gates.\n"
    "\n"
    "The wrapper intentionally owns scanner acquisition and adjudication.  Callers\n"
    "must not need to know how Trivy is downloaded, which files are scanned, or how\n"
    "the accountable suppression ledger is interpreted.\n"
)

#: The complete ``--help`` output of the pre-split module, captured with
#: ``prog == "check_security_gates.py"``.
V89_HELP_TEXT = (
    "usage: check_security_gates.py [-h]\n"
    "                               [--mode {dependency,dependency-vulnerabilities,static,"
    "static-analysis,security-static-analysis,negative-probes,security-negative-probes}]\n"
    "                               [{dependency,dependency-vulnerabilities,static,"
    "static-analysis,security-static-analysis,negative-probes,security-negative-probes}]\n"
    "\n"
    "Run QuickScale's fail-closed dependency and static-security gates. The wrapper\n"
    "intentionally owns scanner acquisition and adjudication. Callers must not need\n"
    "to know how Trivy is downloaded, which files are scanned, or how the\n"
    "accountable suppression ledger is interpreted.\n"
    "\n"
    "positional arguments:\n"
    "  {dependency,dependency-vulnerabilities,static,static-analysis,"
    "security-static-analysis,negative-probes,security-negative-probes}\n"
    "\n"
    "options:\n"
    "  -h, --help            show this help message and exit\n"
    "  --mode {dependency,dependency-vulnerabilities,static,static-analysis,"
    "security-static-analysis,negative-probes,security-negative-probes}\n"
)


def test_module_docstring_is_the_pre_split_cli_description() -> None:
    """The docstring that backs ``--help`` stays the pre-split text."""
    assert gates.__doc__ == V89_CLI_DESCRIPTION


def test_help_output_is_byte_identical_to_the_pre_split_text(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """The complete ``--help`` output is a user-visible contract."""
    monkeypatch.setattr(sys, "argv", ["check_security_gates.py"])
    with pytest.raises(SystemExit) as excinfo:
        gates.main(["--help"])
    assert excinfo.value.code == 0
    assert capsys.readouterr().out == V89_HELP_TEXT


def test_e2e_trigger_inputs_watch_every_split_sibling() -> None:
    """A sibling-only implementation change still matches the generated E2E trigger."""
    repo_root = Path(gates.__file__).resolve().parent.parent
    registry = json.loads(
        (repo_root / "scripts" / "gate_registry.json").read_text(encoding="utf-8")
    )
    gate = next(
        entry for entry in registry["gates"] if entry["id"] == "check-security-static-analysis"
    )
    patterns = gate["trigger_inputs"]
    siblings = sorted((repo_root / "scripts").glob("_security_gates_*.py"))
    assert siblings
    unmatched = [
        path.relative_to(repo_root).as_posix()
        for path in siblings
        if not any(
            fnmatch.fnmatchcase(path.relative_to(repo_root).as_posix(), pattern)
            for pattern in patterns
        )
    ]
    assert unmatched == []
    sibling_patterns = [pattern for pattern in patterns if pattern.startswith("scripts/_")]
    assert sibling_patterns
    workflow = (repo_root / ".github" / "workflows" / "e2e.yml").read_text(encoding="utf-8")
    for pattern in sibling_patterns:
        assert f"- '{pattern}'" in workflow, pattern
