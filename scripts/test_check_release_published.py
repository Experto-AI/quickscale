"""
Tests for the published-release gate (scripts/check_release_published.py).

Regression context: QuickScale 0.87.0 shipped a CLI whose generated projects
pin ``quickscale-core>=0.87.0,<0.88.0`` while ``quickscale-core`` 0.87.0 was
never published to PyPI, so every ``quickscale apply`` embedding a
core-dependent module died at ``poetry lock`` with "which doesn't match any
versions".  This gate makes that state a hard release failure.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
_SPEC = importlib.util.spec_from_file_location(
    "check_release_published", REPO_ROOT / "scripts" / "check_release_published.py"
)
assert _SPEC is not None and _SPEC.loader is not None
check_release_published = importlib.util.module_from_spec(_SPEC)
sys.modules["check_release_published"] = check_release_published
_SPEC.loader.exec_module(check_release_published)


def _make_repo(tmp_path: Path, version: str, core_spec: str) -> Path:
    repo = tmp_path / "repo"
    (repo / "quickscale_modules" / "backups").mkdir(parents=True)
    (repo / "VERSION").write_text(f"{version}\n")
    (repo / "quickscale_modules" / "backups" / "module.yml").write_text(
        f'name: backups\nversion: "{version}"\ndependencies:\n  - quickscale-core{core_spec}\n'
    )
    return repo


@pytest.fixture
def fake_index(monkeypatch):
    """Patch the index lookup with an in-memory release table."""

    def _install(table: dict[str, list[str]]):
        def _fetch(distribution: str, index_url: str) -> list[str]:
            return list(table.get(distribution, []))

        monkeypatch.setattr(check_release_published, "fetch_released_versions", _fetch)

    return _install


class TestConstraintSatisfaction:
    """Constraint evaluation against published versions."""

    @pytest.mark.parametrize(
        "spec,versions,expected",
        [
            (">=0.87.0,<0.88.0", ["0.86.0"], False),
            (">=0.87.0,<0.88.0", ["0.86.0", "0.87.0"], True),
            (">=0.87.0,<0.88.0", ["0.88.0"], False),
            (">=0.87.0,<0.88.0", ["0.87.3"], True),
            ("", ["0.86.0"], True),
            ("", [], False),
            ("^0.87.0", ["0.87.1"], True),
        ],
    )
    def test_constraint_is_satisfied(self, spec, versions, expected):
        assert check_release_published.constraint_is_satisfied(spec, versions) is expected

    def test_unsupported_operator_raises(self):
        with pytest.raises(check_release_published.CheckError):
            check_release_published._clause_holds((0, 87, 0), "@@", "0.87.0")


class TestReleasePublishedGate:
    """End-to-end behaviour of the gate against a synthetic repository."""

    def test_fails_when_core_is_unpublished(self, tmp_path, fake_index, capsys):
        """The exact 0.87.0 regression: CLI shipped, core missing from PyPI."""
        repo = _make_repo(tmp_path, "0.87.0", ">=0.87.0,<0.88.0")
        fake_index(
            {
                "quickscale-core": ["0.86.0"],
                "quickscale-cli": ["0.86.0", "0.87.0"],
                "quickscale": ["0.86.0", "0.87.0"],
            }
        )

        status = check_release_published.run_check(repo, "https://example.invalid")

        output = capsys.readouterr().out
        assert status == 1
        assert "quickscale-core==0.87.0 is not published" in output
        assert "module 'backups' pins quickscale-core>=0.87.0,<0.88.0" in output

    def test_passes_when_every_distribution_is_published(self, tmp_path, fake_index, capsys):
        repo = _make_repo(tmp_path, "0.87.0", ">=0.87.0,<0.88.0")
        published = ["0.86.0", "0.87.0"]
        fake_index(
            {
                "quickscale-core": published,
                "quickscale-cli": published,
                "quickscale": published,
            }
        )

        status = check_release_published.run_check(repo, "https://example.invalid")

        assert status == 0
        assert "All pinned QuickScale distributions are published" in (capsys.readouterr().out)

    def test_missing_modules_directory_is_a_configuration_error(self, tmp_path, fake_index):
        repo = tmp_path / "empty"
        repo.mkdir()
        (repo / "VERSION").write_text("0.87.0\n")
        fake_index({"quickscale-core": ["0.87.0"]})

        with pytest.raises(check_release_published.CheckError):
            check_release_published.run_check(repo, "https://example.invalid")

    def test_main_reports_configuration_errors_as_exit_two(self, tmp_path):
        status = check_release_published.main(["--repo-root", str(tmp_path / "does-not-exist")])
        assert status == 2

    def test_current_repository_manifests_declare_a_core_constraint(self):
        """Guards the parser against manifest format drift."""
        constraints = check_release_published.collect_core_constraints(REPO_ROOT)
        assert "backups" in constraints
        assert constraints["backups"].startswith(">=")


class TestRetries:
    """Retry loop used while PyPI catches up after a publish."""

    def test_retries_until_the_index_catches_up(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, "0.87.0", ">=0.87.0,<0.88.0")
        attempts = {"count": 0}

        def _fetch(distribution: str, index_url: str) -> list[str]:
            attempts["count"] += 1
            if attempts["count"] <= 3:
                return ["0.86.0"]
            return ["0.86.0", "0.87.0"]

        monkeypatch.setattr(check_release_published, "fetch_released_versions", _fetch)
        monkeypatch.setattr(check_release_published.time, "sleep", lambda _: None)

        status = check_release_published.run_check_with_retries(
            repo, "https://example.invalid", retries=3, retry_delay=0.0
        )

        assert status == 0

    def test_gives_up_after_the_final_retry(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path, "0.87.0", ">=0.87.0,<0.88.0")
        monkeypatch.setattr(
            check_release_published,
            "fetch_released_versions",
            lambda distribution, index_url: ["0.86.0"],
        )
        monkeypatch.setattr(check_release_published.time, "sleep", lambda _: None)

        status = check_release_published.run_check_with_retries(
            repo, "https://example.invalid", retries=2, retry_delay=0.0
        )

        assert status == 1
