"""
Behavioral controls for the SA267(c) ``check_security_gates`` script split.

SA267 has closed, so SA278 retired the pre-split surface pins; these controls
keep the split's structural invariants and the exact gate diagnostics
captured from the pre-split module as behavioral tests, so a later change
cannot silently drop, reorder, or reword them.
"""

from __future__ import annotations

import ast
import fnmatch
import json
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import _security_gates_adjudication as adjudication
import _security_gates_probes as probes_module
import _security_gates_support as support
import _security_gates_trivy as trivy_module
import check_security_gates as gates
import pytest

#: ``(module, facade module name)`` for every private sibling; a sibling must
#: never import its own facade back.
SPLIT_SIBLINGS = {
    "_security_gates_adjudication": "check_security_gates",
    "_security_gates_bandit": "check_security_gates",
    "_security_gates_probes": "check_security_gates",
    "_security_gates_support": "check_security_gates",
    "_security_gates_trivy": "check_security_gates",
}


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
