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
    """The gate reports findings as exit 1."""
    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(
        gate,
        "scan",
        lambda executable, target, config: [
            {"RuleID": "stripe-access-token", "File": "leak.py", "StartLine": 3}
        ],
    )
    assert gate.main([str(tmp_path)]) == gate.EXIT_FINDINGS


def test_main_exits_zero_when_clean(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A clean scan exits 0."""
    monkeypatch.setattr(gate, "acquire_gitleaks", lambda: Path("gitleaks"))
    monkeypatch.setattr(gate, "scan", lambda executable, target, config: [])
    assert gate.main([str(tmp_path)]) == 0


def test_every_allowlist_entry_states_a_reason() -> None:
    """Each exemption in the shipped config carries a description and a narrow scope."""
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    allowlists = config.get("allowlists")
    assert allowlists, "the secret-scanning config must declare its allowlists"
    for entry in allowlists:
        assert entry.get("description", "").strip(), f"allowlist without a reason: {entry}"
        assert entry.get("paths") or entry.get("regexes"), f"allowlist without scope: {entry}"
    assert config.get("extend", {}).get("useDefault") is True


def test_false_positive_allowlists_are_value_scoped() -> None:
    """Verified false positives are exempted by value, never by whole file path."""
    config = tomllib.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    value_scoped = [
        entry for entry in config["allowlists"] if entry.get("regexes") and not entry.get("paths")
    ]
    assert value_scoped, "the verified false positives must be value-scoped"
    for entry in value_scoped:
        assert all(not pattern.endswith("$") for pattern in entry["regexes"]), (
            f"value-scoped allowlist looks path-shaped: {entry}"
        )


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
