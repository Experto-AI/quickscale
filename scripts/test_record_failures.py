"""Contract tests for the failure-replay helper used by `make retry`."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
import record_failures

SCRIPT = Path(record_failures.__file__).resolve()


def _write_lastfailed(root: Path, entries: dict[str, bool]) -> Path:
    cache = root / ".pytest_cache" / "v" / "cache"
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / "lastfailed"
    target.write_text(json.dumps(entries), encoding="utf-8")
    return target


@pytest.fixture
def fake_repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Build a repo layout with the three rootdir shapes the helper knows."""
    (tmp_path / "quickscale_core" / "tests").mkdir(parents=True)
    (tmp_path / "quickscale_cli" / "tests").mkdir(parents=True)
    (tmp_path / "quickscale_modules" / "blog" / "tests").mkdir(parents=True)
    monkeypatch.setattr(record_failures, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(
        record_failures, "RECORD_PATH", tmp_path / ".quickscale" / "last-failures.json"
    )
    return tmp_path


def test_roots_cover_core_cli_and_every_module(fake_repo: Path) -> None:
    kinds = {kind: path.name for kind, path in record_failures._roots()}
    assert kinds["core"] == "quickscale_core"
    assert kinds["cli"] == "quickscale_cli"
    assert kinds["module"] == "blog"


def test_node_ids_become_a_keyword_expression(fake_repo: Path) -> None:
    """
    Reduce node ids to bare function names.

    The make targets already pass a test directory positionally, so a raw node
    id would add a second selection instead of narrowing the first.
    """
    names = record_failures._test_names(
        [
            "tests/test_a.py::TestThing::test_alpha",
            "tests/test_b.py::test_beta[case-1]",
            "tests/test_c.py::test_beta[case-2]",
        ]
    )
    assert names == ["test_alpha", "test_beta"]


def test_repro_commands_are_shaped_per_root_kind(fake_repo: Path) -> None:
    _write_lastfailed(fake_repo / "quickscale_core", {"tests/test_x.py::test_one": True})
    _write_lastfailed(
        fake_repo / "quickscale_modules" / "blog", {"tests/test_y.py::test_two": True}
    )
    record = record_failures._collect("integration")
    repros = {entry["kind"]: entry["repro"] for entry in record["entries"]}
    # A core failure maps to test-unit even though the integration stage
    # surfaced it: `make test-integration` only runs module suites.
    assert repros["core"] == "make test-unit SECTIONS=core K=test_one"
    assert repros["module"] == "make test-integration MODULE=blog K=test_two"


def test_e2e_stage_maps_core_and_cli_roots_to_the_e2e_target(fake_repo: Path) -> None:
    _write_lastfailed(fake_repo / "quickscale_cli", {"tests/test_e2e.py::test_flow": True})
    record = record_failures._collect("e2e")
    assert record["entries"][0]["repro"] == "make test-e2e K=test_flow"


def test_keyword_with_shell_metacharacters_is_quoted(fake_repo: Path) -> None:
    """The repro string is executed by `make retry`, so it must be shell-safe."""
    _write_lastfailed(fake_repo / "quickscale_core", {"tests/t.py::test_a": True})
    _write_lastfailed(fake_repo / "quickscale_cli", {"tests/t.py::test_b": True})
    for entry in record_failures._collect("unit")["entries"]:
        assert entry["repro"].count("K=") == 1
    # Multiple names collapse into one quoted -k expression.
    _write_lastfailed(
        fake_repo / "quickscale_core",
        {"tests/t.py::test_a": True, "tests/t.py::test_b": True},
    )
    core = record_failures._collect("unit")["entries"][0]
    assert core["repro"].endswith("K='test_a or test_b'")


def test_passing_entries_in_the_cache_are_ignored(fake_repo: Path) -> None:
    """Pytest stores cleared tests as falsy values; those are not failures."""
    _write_lastfailed(
        fake_repo / "quickscale_cli",
        {"tests/test_x.py::test_kept": True, "tests/test_x.py::test_cleared": False},
    )
    record = record_failures._collect("unit")
    assert record["entries"][0]["ids"] == ["tests/test_x.py::test_kept"]


def test_stale_caches_are_excluded_by_the_since_bound(fake_repo: Path) -> None:
    """
    Exclude caches this run never touched.

    Pytest keeps lastfailed until a run clears it, so an untouched cache holds
    failures from an unrelated session; replaying those is worse than nothing.
    """
    cache = _write_lastfailed(fake_repo / "quickscale_core", {"tests/t.py::test_old": True})
    import os

    os.utime(cache, (1_000_000, 1_000_000))
    assert record_failures._collect("unit", since=2_000_000)["entries"] == []
    assert record_failures._collect("unit", since=None)["entries"] != []


def test_replay_without_a_record_refuses_to_guess(fake_repo: Path, capsys) -> None:
    """No record file must not silently replay whatever the caches still hold."""
    _write_lastfailed(fake_repo / "quickscale_core", {"tests/t.py::test_ancient": True})
    exit_code = record_failures.main(["replay"])
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "No recorded failures" in output
    assert "test_ancient" not in output


def test_record_then_replay_round_trips(fake_repo: Path, capsys) -> None:
    _write_lastfailed(fake_repo / "quickscale_cli", {"tests/t.py::test_round": True})
    assert record_failures.main(["record", "--stage", "coverage"]) == 0
    capsys.readouterr()
    assert record_failures.main(["replay", "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == "make test-unit SECTIONS=cli K=test_round"


def test_replay_falls_back_to_a_stage_command_when_no_cache_exists(fake_repo: Path, capsys) -> None:
    """Stages running with -p no:cacheprovider still get a usable rerun command."""
    assert record_failures.main(["record", "--stage", "integration"]) == 0
    capsys.readouterr()
    assert record_failures.main(["replay", "--quiet"]) == 0
    assert capsys.readouterr().out.strip() == "make ci ONLY=integration"


def test_unreadable_record_reports_instead_of_crashing(fake_repo: Path, capsys) -> None:
    record_failures.RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    record_failures.RECORD_PATH.write_text("{not json", encoding="utf-8")
    assert record_failures.main(["replay"]) == 2
    assert "unreadable" in capsys.readouterr().err


def test_module_is_executable_as_a_script() -> None:
    """`make retry` shells out to this file, so the CLI entrypoint must work."""
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "replay", "--quiet"],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert result.returncode == 0
