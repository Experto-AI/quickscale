"""
Hermetic contracts for the secret-scanning gate (SA202).

The suite covers acquisition safety, report adjudication, and the fail-closed
exit contract without downloading a release or scanning the tree.  A live
end-to-end scan is available to maintainers by setting
``QUICKSCALE_LIVE_SECRET_SCAN=1``; the registered gate itself runs the live scan
in local CI, hosted CI, and the publish workflow.
"""

from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest

import scripts.check_secret_scanning as gate
from scripts.check_secret_scanning import GateError

REPO_ROOT = Path(__file__).resolve().parent.parent
CHECKER = REPO_ROOT / "scripts" / "check_secret_scanning.py"
CONFIG_PATH = REPO_ROOT / "scripts" / "gitleaks.toml"


def _completed(returncode: int, stdout: str, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(["gitleaks"], returncode, stdout, stderr)


def test_unsupported_host_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hosts outside the contributor contract fail closed."""
    monkeypatch.setattr(gate.platform, "system", lambda: "Windows")
    monkeypatch.setattr(gate.platform, "machine", lambda: "AMD64")
    with pytest.raises(GateError, match="unsupported gitleaks host"):
        gate._asset()


def test_checksum_mismatch_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A downloaded archive whose digest differs from the pinned manifest fails closed."""
    monkeypatch.setattr(gate, "_asset", lambda: ("gitleaks_8.30.1_linux_x64.tar.gz", "0" * 64))
    monkeypatch.setattr(gate, "_download", lambda url, destination: destination.write_bytes(b"x"))
    with pytest.raises(GateError, match="checksum mismatch"):
        gate.acquire_gitleaks()


def test_archive_member_path_traversal_is_rejected(tmp_path: Path) -> None:
    """Archives may not write outside their extraction directory."""
    archive = tarfile.open(fileobj=io.BytesIO(), mode="w")
    member = tarfile.TarInfo("../../outside")
    member.size = 1
    archive.addfile(member, io.BytesIO(b"x"))
    try:
        with pytest.raises(GateError, match="escapes extraction directory"):
            gate._safe_archive_members(archive, tmp_path)
    finally:
        archive.close()


def test_archive_symlink_is_rejected(tmp_path: Path) -> None:
    """Archives may not install symlink members."""
    archive = tarfile.open(fileobj=io.BytesIO(), mode="w")
    member = tarfile.TarInfo("gitleaks")
    member.type = tarfile.SYMTYPE
    member.linkname = "/usr/bin/env"
    archive.addfile(member)
    try:
        with pytest.raises(GateError, match="unsafe gitleaks archive member"):
            gate._safe_archive_members(archive, tmp_path)
    finally:
        archive.close()


def test_clean_report_returns_no_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean exit with an empty report returns no findings."""
    monkeypatch.setattr(gate, "_run", lambda command: _completed(0, "[]"))
    assert gate.scan(Path("gitleaks"), REPO_ROOT, CONFIG_PATH) == []


def test_findings_report_is_returned(monkeypatch: pytest.MonkeyPatch) -> None:
    """A findings exit status with a populated report returns the findings."""
    report = json.dumps([{"RuleID": "stripe-access-token", "File": "leak.py", "StartLine": 1}])
    monkeypatch.setattr(gate, "_run", lambda command: _completed(gate.FINDINGS_EXIT_CODE, report))
    findings = gate.scan(Path("gitleaks"), REPO_ROOT, CONFIG_PATH)
    assert [finding["RuleID"] for finding in findings] == ["stripe-access-token"]


def test_unexpected_exit_status_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Any exit status other than clean or findings fails closed."""
    monkeypatch.setattr(gate, "_run", lambda command: _completed(1, "", "boom"))
    with pytest.raises(GateError, match="gitleaks exited 1"):
        gate.scan(Path("gitleaks"), REPO_ROOT, CONFIG_PATH)


def test_unparseable_report_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A report that is not JSON fails closed."""
    monkeypatch.setattr(gate, "_run", lambda command: _completed(0, "not json"))
    with pytest.raises(GateError, match="unparseable gitleaks report"):
        gate.scan(Path("gitleaks"), REPO_ROOT, CONFIG_PATH)


def test_missing_report_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A scanner that writes no report fails closed instead of passing silently."""
    monkeypatch.setattr(gate, "_run", lambda command: _completed(0, ""))
    with pytest.raises(GateError, match="no report on stdout"):
        gate.scan(Path("gitleaks"), REPO_ROOT, CONFIG_PATH)


def test_findings_status_with_empty_report_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A findings exit status with an empty report fails closed."""
    monkeypatch.setattr(gate, "_run", lambda command: _completed(gate.FINDINGS_EXIT_CODE, "[]"))
    with pytest.raises(GateError, match="empty report"):
        gate.scan(Path("gitleaks"), REPO_ROOT, CONFIG_PATH)


def test_clean_status_with_findings_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A clean exit status with a populated report fails closed."""
    report = json.dumps([{"RuleID": "stripe-access-token", "File": "leak.py", "StartLine": 1}])
    monkeypatch.setattr(gate, "_run", lambda command: _completed(0, report))
    with pytest.raises(GateError, match="clean exit status"):
        gate.scan(Path("gitleaks"), REPO_ROOT, CONFIG_PATH)


def test_missing_config_fails_closed(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A missing allowlist config fails closed instead of scanning unscoped."""
    monkeypatch.setattr(gate, "_run", lambda command: _completed(0, "[]"))
    with pytest.raises(GateError, match="config not found"):
        gate.scan(Path("gitleaks"), REPO_ROOT, tmp_path / "absent.toml")


def test_main_exits_one_on_findings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """The gate reports an unsuppressed finding as exit 1."""
    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(
        gate,
        "scan",
        lambda executable, target, config: [
            {
                "RuleID": "stripe-access-token",
                "File": "leak.py",
                "StartLine": 3,
                "Fingerprint": "leak.py:stripe-access-token:3",
            }
        ],
    )
    monkeypatch.setattr(gate, "scan_history", lambda executable, target, config: [])
    monkeypatch.setattr(gate, "_load_suppressions", lambda path: [])
    assert gate.main([str(tmp_path)]) == gate.EXIT_FINDINGS


def test_main_exits_zero_when_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A clean tree and history exit 0."""
    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(gate, "scan", lambda executable, target, config: [])
    monkeypatch.setattr(gate, "scan_history", lambda executable, target, config: [])
    monkeypatch.setattr(gate, "_load_suppressions", lambda path: [])
    assert gate.main([str(tmp_path)]) == 0


def test_main_exits_two_on_a_stale_suppression(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A suppression that matches no finding fails closed as infrastructure."""
    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(gate, "scan", lambda executable, target, config: [])
    monkeypatch.setattr(gate, "scan_history", lambda executable, target, config: [])
    monkeypatch.setattr(
        gate,
        "_load_suppressions",
        lambda path: [
            {
                "scanner": "gitleaks",
                "rule_id": "generic-api-key",
                "path": "gone.py",
                "mode": "tree",
                "fingerprints": ["gone.py:generic-api-key:1"],
                "owner": "maintainers",
                "rationale": "removed fixture",
                "decision_ref": "TEST",
                "expires": "2099-01-01",
            }
        ],
    )
    assert gate.main([str(tmp_path)]) == gate.EXIT_INFRASTRUCTURE


def test_shallow_clone_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A shallow clone cannot claim a clean history scan."""
    monkeypatch.setattr(gate, "_run", lambda command: _completed(0, "true\n"))
    with pytest.raises(GateError, match="full-history clone"):
        gate._ensure_full_history(REPO_ROOT)


def test_scan_history_runs_git_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The history scan invokes gitleaks git, not a second working-tree walk."""
    commands: list[list[str]] = []

    def _record(command: list[str]) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        return _completed(0, "[]")

    monkeypatch.setattr(gate, "_ensure_full_history", lambda repo_root: None)
    monkeypatch.setattr(gate, "_run", _record)
    assert gate.scan_history(Path("gitleaks"), REPO_ROOT, CONFIG_PATH) == []
    assert commands[0][1] == "git"


def _ledger(path: Path, entries: list[dict[str, object]]) -> Path:
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "description": "test ledger",
                "suppressions": entries,
            }
        ),
        encoding="utf-8",
    )
    return path


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "scanner": "gitleaks",
        "rule_id": "generic-api-key",
        "path": "fixture.py",
        "mode": "tree",
        "fingerprints": ["fixture.py:generic-api-key:1"],
        "owner": "maintainers",
        "rationale": "test fixture placeholder",
        "decision_ref": "TEST",
        "expires": "2099-01-01",
    }
    entry.update(overrides)
    return entry


def test_expired_suppression_fails_closed(tmp_path: Path) -> None:
    """An entry whose expiry has passed is not an exemption."""
    ledger = _ledger(tmp_path / "ledger.json", [_entry(expires="2000-01-01")])
    with pytest.raises(GateError, match="expired"):
        gate._load_suppressions(ledger)


def test_duplicate_fingerprint_fails_closed(tmp_path: Path) -> None:
    """A fingerprint may be claimed by exactly one entry."""
    ledger = _ledger(
        tmp_path / "ledger.json",
        [_entry(), _entry(path="other.py", rationale="duplicate")],
    )
    with pytest.raises(GateError, match="duplicate secret suppression fingerprint"):
        gate._load_suppressions(ledger)


def test_unknown_entry_key_fails_closed(tmp_path: Path) -> None:
    """An entry with an unexpected key is refused instead of ignored."""
    ledger = _ledger(tmp_path / "ledger.json", [_entry(extra="x")])
    with pytest.raises(GateError, match="exactly"):
        gate._load_suppressions(ledger)


def test_bad_mode_fails_closed(tmp_path: Path) -> None:
    """Only tree, history, and any are scan modes."""
    ledger = _ledger(tmp_path / "ledger.json", [_entry(mode="working-tree")])
    with pytest.raises(GateError, match="mode"):
        gate._load_suppressions(ledger)


def test_non_string_mode_fails_closed(tmp_path: Path) -> None:
    """A non-string mode is a controlled error, never an uncaught TypeError."""
    ledger = _ledger(tmp_path / "ledger.json", [_entry(mode=[])])
    with pytest.raises(GateError, match="mode"):
        gate._load_suppressions(ledger)


def _history_finding(fingerprint: str = "abc123:deleted.py:generic-api-key:7") -> dict:
    """Return a finding shaped like gitleaks' history report."""
    return {
        "RuleID": "generic-api-key",
        "File": "deleted.py",
        "StartLine": 7,
        "Fingerprint": fingerprint,
    }


def test_history_only_finding_fails_without_a_suppression(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A credential present only in history is still a finding."""
    finding = _history_finding()
    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(gate, "scan", lambda executable, target, config: [])
    monkeypatch.setattr(gate, "scan_history", lambda executable, target, config: [finding])
    monkeypatch.setattr(gate, "_load_suppressions", lambda path: [])
    assert gate.main([str(tmp_path)]) == gate.EXIT_FINDINGS


def test_history_only_finding_is_suppressed_by_an_exact_entry(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An exact history fingerprint exemption permits only that finding."""
    finding = _history_finding()
    entry = _entry(
        mode="history",
        path="deleted.py",
        fingerprints=[finding["Fingerprint"]],
    )
    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(gate, "scan", lambda executable, target, config: [])
    monkeypatch.setattr(gate, "scan_history", lambda executable, target, config: [finding])
    monkeypatch.setattr(gate, "_load_suppressions", lambda path: [entry])
    assert gate.main([str(tmp_path)]) == 0


def test_adjudicate_matches_by_fingerprint_and_reports_the_rest() -> None:
    """A fingerprint match suppresses one finding; a sibling still fails."""
    findings = {
        "tree": [
            {"RuleID": "generic-api-key", "File": "a.py", "Fingerprint": "a.py:generic-api-key:1"},
            {"RuleID": "generic-api-key", "File": "a.py", "Fingerprint": "a.py:generic-api-key:2"},
        ],
        "history": [],
    }
    unsuppressed, stale = gate.adjudicate(
        findings,
        [_entry(path="a.py", fingerprints=["a.py:generic-api-key:1"])],
    )
    assert [finding["Fingerprint"] for _mode, finding in unsuppressed] == ["a.py:generic-api-key:2"]
    assert stale == []


def test_absolute_fingerprint_is_normalized() -> None:
    """An absolute scan-target prefix is stripped before matching."""
    absolute = {"Fingerprint": f"{REPO_ROOT}/a.py:generic-api-key:1"}
    assert gate._repo_relative_fingerprint(absolute["Fingerprint"]) == "a.py:generic-api-key:1"


def test_every_allowlist_entry_states_a_reason() -> None:
    """Each exemption in the shipped config carries a description and a narrow scope."""
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    allowlists = config.get("allowlists")
    assert allowlists, "the secret-scanning config must declare its allowlists"
    for entry in allowlists:
        assert entry.get("description", "").strip(), f"allowlist without a reason: {entry}"
        assert entry.get("paths") or entry.get("regexes"), f"allowlist without scope: {entry}"
    assert config.get("extend", {}).get("useDefault") is True


def test_config_holds_only_structural_path_allowlists() -> None:
    """Value-level exemptions belong in the expiring ledger, not the config."""
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    allowlists = config.get("allowlists")
    assert allowlists, "the secret-scanning config must declare its structural allowlists"
    for entry in allowlists:
        assert entry.get("description", "").strip(), f"allowlist without a reason: {entry}"
        assert entry.get("paths"), f"allowlist without a path scope: {entry}"
        assert "regexes" not in entry, f"value-scoped exemption in the config: {entry}"
    assert config.get("extend", {}).get("useDefault") is True


@pytest.mark.skipif(
    os.environ.get("QUICKSCALE_LIVE_SECRET_SCAN") != "1",
    reason="set QUICKSCALE_LIVE_SECRET_SCAN=1 to run the live acquisition and scan",
)
def test_live_repository_scan_is_clean() -> None:
    """The live gate acquires gitleaks and reports the repository clean."""
    completed = subprocess.run(
        [sys.executable, str(CHECKER), str(REPO_ROOT)],
        capture_output=True,
        text=True,
        timeout=900,
        check=False,
    )
    assert completed.returncode == 0, completed.stderr


def _git(repo: Path, *arguments: str) -> None:
    """Run one git command in a fixture repository."""
    environment = {
        **os.environ,
        "GIT_AUTHOR_NAME": "Gate Test",
        "GIT_AUTHOR_EMAIL": "gate@example.invalid",
        "GIT_COMMITTER_NAME": "Gate Test",
        "GIT_COMMITTER_EMAIL": "gate@example.invalid",
    }
    subprocess.run(
        ["git", "-C", str(repo), *arguments],
        check=True,
        capture_output=True,
        text=True,
        env=environment,
    )


@pytest.mark.skipif(
    os.environ.get("QUICKSCALE_LIVE_SECRET_SCAN") != "1",
    reason="set QUICKSCALE_LIVE_SECRET_SCAN=1 to run the live acquisition and scan",
)
def test_live_deleted_credential_is_found_in_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A credential committed and then deleted still fails the history scan."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    # Build the fixture key at runtime: the literal must not appear in this file,
    # or the working-tree scan would flag the test source itself.
    secret = "sk_" + "test_" + "51ExampleTestKeyDummyValue"
    secret_file = repo / "leak.py"
    secret_file.write_text(f"STRIPE_KEY = {secret!r}\n", encoding="utf-8")
    _git(repo, "add", "leak.py")
    _git(repo, "commit", "-qm", "add fixture")
    secret_file.unlink()
    _git(repo, "commit", "-qam", "remove fixture")

    findings = gate.scan_history(gate.acquire_gitleaks(), repo, CONFIG_PATH)
    assert any(finding.get("RuleID") == "stripe-access-token" for finding in findings)
    finding = next(
        finding for finding in findings if finding.get("RuleID") == "stripe-access-token"
    )

    unsuppressed, stale = gate.adjudicate({"history": findings}, [])
    assert [item["Fingerprint"] for _mode, item in unsuppressed] == [finding["Fingerprint"]]
    assert stale == []

    entry = _entry(
        mode="history",
        rule_id="stripe-access-token",
        path="leak.py",
        fingerprints=[finding["Fingerprint"]],
    )
    unsuppressed, stale = gate.adjudicate({"history": findings}, [entry])
    assert unsuppressed == []
    assert stale == []

    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(gate, "scan", lambda executable, target, config: [])
    monkeypatch.setattr(gate, "scan_history", lambda executable, target, config: findings)
    monkeypatch.setattr(gate, "_load_suppressions", lambda path: [])
    assert gate.main([str(tmp_path)]) == gate.EXIT_FINDINGS
    monkeypatch.setattr(gate, "_load_suppressions", lambda path: [entry])
    assert gate.main([str(tmp_path)]) == 0
