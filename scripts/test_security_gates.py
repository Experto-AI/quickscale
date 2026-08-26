"""
Focused tests for the fail-closed security gate infrastructure.

These tests cover the wrapper's contract and adjudication logic without
requiring network access or rerunning the scanners.
"""

from __future__ import annotations

import hashlib
import io
import json
import sys
import tarfile
import tomllib
from pathlib import Path

import pytest

import scripts.check_security_gates as gates
from scripts.check_security_gates import (
    ROOT,
    GateError,
    _adjudicate,
    _load_suppressions,
    _lock_inventory,
    _probe_lock,
    _safe_archive_members,
    strict_json,
)


def test_strict_json_rejects_duplicate_keys() -> None:
    """Duplicate JSON keys must not be silently accepted."""
    with pytest.raises(GateError, match="duplicate JSON key"):
        strict_json('{"version": "1", "version": "2"}', source="probe")


def test_strict_json_rejects_trailing_data() -> None:
    """Trailing JSON data must fail closed."""
    with pytest.raises(GateError, match="malformed JSON"):
        strict_json('{"ok": true}\nfalse', source="probe")


def test_archive_member_path_traversal_is_rejected(tmp_path: Path) -> None:
    """Trivy archives may not write outside their extraction directory."""
    archive = tarfile.open(fileobj=io.BytesIO(), mode="w")
    member = tarfile.TarInfo("../../outside")
    member.size = 1
    archive.addfile(member, io.BytesIO(b"x"))
    try:
        with pytest.raises(GateError, match="escapes extraction directory"):
            _safe_archive_members(archive, tmp_path)
    finally:
        archive.close()


def test_archive_symlink_is_rejected(tmp_path: Path) -> None:
    """Trivy archives may not install symlink members."""
    archive = tarfile.open(fileobj=io.BytesIO(), mode="w")
    archive.addfile(tarfile.TarInfo("trivy"))
    member = tarfile.TarInfo("link")
    member.type = tarfile.SYMTYPE
    member.linkname = "/etc/passwd"
    archive.addfile(member)
    try:
        with pytest.raises(GateError, match="unsafe Trivy archive member"):
            _safe_archive_members(archive, tmp_path)
    finally:
        archive.close()


def test_probe_lock_is_parseable_and_contains_exact_probe_package(tmp_path: Path) -> None:
    """The synthetic Trivy probe lock must identify the observed package/version."""
    lock_path = tmp_path / "poetry.lock"
    _probe_lock(lock_path)
    document = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    package = document["package"][0]
    assert (package["name"], package["version"]) == ("sqlparse", "0.5.5")


def test_lock_inventory_uses_dev_only_sentinel() -> None:
    """The dependency gate must prove that a dev-only package was scanned."""
    _inventory, sentinel, expects_dev = _lock_inventory(ROOT / "poetry.lock")
    assert (sentinel, expects_dev) == ("ast-serialize", True)


def test_adjudication_ignores_unrelated_scanner_entries() -> None:
    """A static run must not fail because dependency suppressions are unused."""
    findings = [
        {
            "scanner": entry["scanner"],
            "finding_id": entry["finding_id"],
            "project": entry["project"],
            "path": entry["path"],
            "package": entry["package"],
            "installed_version": entry["installed_version"],
            "code_identity": entry["code_identity"],
            "fingerprint": entry["fingerprint"],
        }
        for entry in _load_suppressions()
        if entry["scanner"] == "bandit"
    ]
    unsuppressed, suppressed = _adjudicate(findings, executed_scanners={"bandit"})
    assert unsuppressed == []
    assert suppressed == findings


def test_adjudication_rejects_stale_entries(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every suppression for an executed scanner must match exactly once."""
    entry = {
        "scanner": "bandit",
        "finding_id": "B105",
        "project": "probe",
        "path": "probe.py",
        "code_identity": "line=1",
        "fingerprint": "stale",
    }
    monkeypatch.setattr(gates, "_load_suppressions", lambda: [entry])
    with pytest.raises(GateError, match="suppression cardinality failure"):
        _adjudicate(
            [
                {
                    "scanner": "bandit",
                    "finding_id": "B105",
                    "project": "probe",
                    "path": "probe.py",
                    "code_identity": "line=1",
                    "fingerprint": "unrelated",
                }
            ],
            executed_scanners={"bandit"},
        )


def test_adjudication_rejects_stale_entry_when_scanner_is_clean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A clean executed scanner must not make its stale suppressions disappear."""
    entry = {
        "scanner": "bandit",
        "fingerprint": "stale",
    }
    monkeypatch.setattr(gates, "_load_suppressions", lambda: [entry])
    with pytest.raises(GateError, match="suppression cardinality failure"):
        _adjudicate([], executed_scanners={"bandit"})


def test_trivy_scan_accepts_clean_report(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A valid clean report returns no findings and preserves scan evidence."""
    report = {
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
    monkeypatch.setattr(
        gates, "_lock_inventory", lambda _path: ({("sentinel", "1")}, "sentinel", False)
    )
    monkeypatch.setattr(
        gates,
        "run_command",
        lambda *_args, **_kwargs: gates.Completed(0, json.dumps(report), ""),
    )
    findings, evidence = gates._trivy_scan(Path("trivy"), "probe", tmp_path / "poetry.lock")
    assert findings == []
    assert evidence["include_dev_deps"] is True


def test_trivy_scan_rejects_infrastructure_exit(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Unexpected scanner exits are infrastructure failures, not findings."""
    monkeypatch.setattr(gates, "_lock_inventory", lambda _path: (set(), "sentinel", False))
    monkeypatch.setattr(
        gates,
        "run_command",
        lambda *_args, **_kwargs: gates.Completed(2, "", "database unavailable"),
    )
    with pytest.raises(GateError, match="infrastructure failure"):
        gates._trivy_scan(Path("trivy"), "probe", tmp_path / "poetry.lock")


def test_trivy_acquisition_rejects_wrong_checksum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trivy bytes must match the committed release digest before extraction."""
    payload = b"not a Trivy archive"
    monkeypatch.setattr(
        gates, "_download", lambda _url, destination: destination.write_bytes(payload)
    )
    monkeypatch.setattr(
        gates,
        "_trivy_asset",
        lambda: ("trivy_0.74.0_Linux-64bit.tar.gz", hashlib.sha256(b"different").hexdigest()),
    )
    with pytest.raises(GateError, match="checksum mismatch"):
        gates.acquire_trivy()


@pytest.mark.parametrize(
    ("system", "machine", "archive", "digest"),
    [
        (
            "Linux",
            "x86_64",
            "trivy_0.74.0_Linux-64bit.tar.gz",
            "2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a",
        ),
        (
            "Linux",
            "aarch64",
            "trivy_0.74.0_Linux-ARM64.tar.gz",
            "b94ce1976bbf3c15b514b605ee88be7c6d94a29be2302847ff01cb794d47aad5",
        ),
        (
            "Darwin",
            "x86_64",
            "trivy_0.74.0_macOS-64bit.tar.gz",
            "472816f6888dda689d075c30254d4210b4d1035acf365aa72332f584c2f60485",
        ),
        (
            "Darwin",
            "arm64",
            "trivy_0.74.0_macOS-ARM64.tar.gz",
            "1caada5e0e2091909357c7525d3aa76f4b660b13821bc143b190c7483e31cc11",
        ),
    ],
)
def test_trivy_asset_matches_supported_host_release_manifest(
    monkeypatch: pytest.MonkeyPatch,
    system: str,
    machine: str,
    archive: str,
    digest: str,
) -> None:
    """Every documented native host selects its checksum-pinned release asset."""
    monkeypatch.setattr(gates.platform, "system", lambda: system)
    monkeypatch.setattr(gates.platform, "machine", lambda: machine)
    assert gates._trivy_asset() == (archive, digest)


def test_trivy_asset_rejects_unsupported_native_host(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An undocumented native host fails explicitly rather than skipping the gate."""
    monkeypatch.setattr(gates.platform, "system", lambda: "Windows")
    monkeypatch.setattr(gates.platform, "machine", lambda: "AMD64")
    with pytest.raises(GateError, match="unsupported Trivy host Windows/amd64"):
        gates._trivy_asset()


def test_run_command_timeout_is_fail_closed() -> None:
    """A timed-out scanner command is terminated and reported as infrastructure failure."""
    with pytest.raises(GateError, match="command timed out"):
        gates.run_command(
            [sys.executable, "-c", "import time; time.sleep(5)"],
            timeout=0.05,
        )


def test_bandit_scan_binds_categories_and_forbids_exit_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bandit invocation must include all category IDs and ignore-nosec only."""
    commands: list[list[str]] = []

    def fake_run(argv: list[str], **_kwargs: object) -> gates.Completed:
        commands.append(argv)
        if argv[1:] == ["--version"]:
            return gates.Completed(0, "bandit 1.9.4", "")
        if argv[1:] == ["--help"]:
            return gates.Completed(0, " ".join(gates.BANDIT_TESTS), "")
        return gates.Completed(0, '{"results": []}', "")

    monkeypatch.setattr(gates, "run_command", fake_run)
    monkeypatch.setattr(gates, "_source_files", lambda: [Path("source.py")])
    findings, evidence = gates._bandit_scan()
    assert findings == []
    assert set(evidence["tests"]) == {
        test_id for ids in gates.CATEGORY_TESTS.values() for test_id in ids
    }
    scan_command = commands[-1]
    assert "--ignore-nosec" in scan_command
    assert "--exit-zero" not in scan_command


def test_main_rejects_conflicting_mode_selectors() -> None:
    """Contradictory positional and option modes must fail instead of winning by order."""
    with pytest.raises(SystemExit, match="2"):
        gates.main(["static", "--mode", "dependency"])
