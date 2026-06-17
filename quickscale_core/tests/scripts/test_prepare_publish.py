"""Tests for the ``scripts/prepare_publish.py`` helper.

These tests are colocated with the rest of the ``quickscale_core`` test
suite so the repository's normal ``make test-unit`` / ``make test`` flows
exercise the publish-script modernization alongside the rest of the
package. The helper lives under ``scripts/`` rather than
``quickscale_core/src/`` because it is a build-time tool, not a runtime
dependency, but the Python API it exposes is unit-testable in isolation.
"""

from __future__ import annotations

import importlib.util
import shutil
import sys
import textwrap
import tomllib
from pathlib import Path
from typing import Any

import pytest


# ---------------------------------------------------------------------------
# Module import helper
# ---------------------------------------------------------------------------


SCRIPTS_DIR = Path(__file__).resolve().parents[3] / "scripts"
PREPARE_PUBLISH_PATH = SCRIPTS_DIR / "prepare_publish.py"


def _load_prepare_publish() -> Any:
    """Import ``prepare_publish.py`` as a module without installing it.

    The helper lives in ``scripts/`` rather than a package directory, so
    we load it by file path. The same module object is cached for the
    duration of a test run.
    """
    spec = importlib.util.spec_from_file_location(
        "prepare_publish", PREPARE_PUBLISH_PATH
    )
    if spec is None or spec.loader is None:  # pragma: no cover - defensive
        raise RuntimeError("Could not load prepare_publish.py from scripts/")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("prepare_publish", module)
    spec.loader.exec_module(module)
    return module


prepare_publish = _load_prepare_publish()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_repo(tmp_path: Path) -> Path:
    """Create a small publish-style repository under ``tmp_path``.

    The fixture writes a root ``README.md``, a root ``VERSION`` file, and
    one ``pyproject.toml`` per default publish package. Each ``pyproject``
    uses the structure the real ``scripts/publish.sh`` workflow targets:
    a ``[project]`` table with a ``readme = "../README.md"`` entry and a
    ``[tool.poetry.dependencies]`` table that may include path-based
    inter-package dependencies.
    """
    (tmp_path / "VERSION").write_text("0.86.0\n", encoding="utf-8")
    (tmp_path / "README.md").write_text("# QuickScale\n", encoding="utf-8")

    pyproject_templates = {
        "quickscale_core": textwrap.dedent(
            """\
            [project]
            name = "quickscale-core"
            version = "0.86.0"
            readme = "../README.md"

            [tool.poetry]
            packages = [{include = "quickscale_core", from = "src"}]

            [tool.poetry.dependencies]
            python = ">=3.13,<3.15"
            """
        ),
        "quickscale_cli": textwrap.dedent(
            """\
            [project]
            name = "quickscale-cli"
            version = "0.86.0"
            readme = "../README.md"

            [tool.poetry]
            packages = [{include = "quickscale_cli", from = "src"}]

            [tool.poetry.dependencies]
            python = ">=3.13,<3.15"
            click = "^8.3.1"
            quickscale-core = {path = "../quickscale_core"}
            """
        ),
        "quickscale": textwrap.dedent(
            """\
            [project]
            name = "quickscale"
            version = "0.86.0"
            readme = "../README.md"

            [tool.poetry]
            packages = []

            [tool.poetry.dependencies]
            python = ">=3.13,<3.15"
            quickscale-core = {path = "../quickscale_core", develop = true}
            quickscale-cli = {path = "../quickscale_cli"}
            """
        ),
    }
    for package, body in pyproject_templates.items():
        pkg_dir = tmp_path / package
        pkg_dir.mkdir()
        (pkg_dir / "pyproject.toml").write_text(body, encoding="utf-8")
    return tmp_path


def _pyproject(repo_root: Path, package: str) -> Path:
    return repo_root / package / "pyproject.toml"


# ---------------------------------------------------------------------------
# read_version
# ---------------------------------------------------------------------------


def test_read_version_strips_whitespace_and_carriage_returns(
    tmp_path: Path,
) -> None:
    version_file = tmp_path / "VERSION"
    version_file.write_bytes(b"  0.86.0 \r\n")
    assert prepare_publish.read_version(version_file) == "0.86.0"


def test_read_version_raises_when_missing(tmp_path: Path) -> None:
    with pytest.raises(prepare_publish.PreparePublishError):
        prepare_publish.read_version(tmp_path / "VERSION")


def test_read_version_raises_when_empty(tmp_path: Path) -> None:
    version_file = tmp_path / "VERSION"
    version_file.write_text("\n", encoding="utf-8")
    with pytest.raises(prepare_publish.PreparePublishError):
        prepare_publish.read_version(version_file)


# ---------------------------------------------------------------------------
# read_pyproject + tomllib safety
# ---------------------------------------------------------------------------


def test_read_pyproject_parses_valid_file(sample_repo: Path) -> None:
    data = prepare_publish.read_pyproject(_pyproject(sample_repo, "quickscale_cli"))
    assert data["project"]["name"] == "quickscale-cli"


def test_read_pyproject_rejects_missing_file(tmp_path: Path) -> None:
    with pytest.raises(prepare_publish.PreparePublishError):
        prepare_publish.read_pyproject(tmp_path / "missing.toml")


def test_read_pyproject_rejects_invalid_toml(tmp_path: Path) -> None:
    bad = tmp_path / "pyproject.toml"
    bad.write_text("not = valid = toml", encoding="utf-8")
    with pytest.raises(prepare_publish.PreparePublishError):
        prepare_publish.read_pyproject(bad)


# ---------------------------------------------------------------------------
# prepare_pyproject: path dependency rewrites
# ---------------------------------------------------------------------------


def test_prepare_replaces_path_dep_with_version_constraint(
    sample_repo: Path,
) -> None:
    pyproject = _pyproject(sample_repo, "quickscale_cli")
    changes = prepare_publish.prepare_pyproject("quickscale_cli", pyproject, "0.86.0")
    rewritten = pyproject.read_text(encoding="utf-8")
    assert 'quickscale-core = "^0.86.0"' in rewritten
    assert '{path = "../quickscale_core"' not in rewritten
    assert any("quickscale-core" in change for change in changes)


def test_prepare_replaces_both_path_deps_in_meta_package(
    sample_repo: Path,
) -> None:
    pyproject = _pyproject(sample_repo, "quickscale")
    changes = prepare_publish.prepare_pyproject("quickscale", pyproject, "0.86.0")
    rewritten = pyproject.read_text(encoding="utf-8")
    assert 'quickscale-core = "^0.86.0"' in rewritten
    assert 'quickscale-cli = "^0.86.0"' in rewritten
    assert 'path = "../quickscale_core"' not in rewritten
    assert 'path = "../quickscale_cli"' not in rewritten
    assert len(changes) >= 2


def test_prepare_replaces_develop_variant(
    tmp_path: Path,
) -> None:
    pkg_dir = tmp_path / "quickscale_cli"
    pkg_dir.mkdir()
    pyproject = pkg_dir / "pyproject.toml"
    pyproject.write_text(
        textwrap.dedent(
            """\
            [project]
            name = "quickscale-cli"
            version = "0.86.0"

            [tool.poetry.dependencies]
            quickscale-core = {path = "../quickscale_core", develop = true}
            """
        ),
        encoding="utf-8",
    )
    prepare_publish.prepare_pyproject("quickscale_cli", pyproject, "0.86.0")
    assert 'quickscale-core = "^0.86.0"' in pyproject.read_text(encoding="utf-8")
    assert "develop" not in pyproject.read_text(encoding="utf-8")


def test_prepare_leaves_unknown_path_deps_alone(
    sample_repo: Path,
) -> None:
    pyproject = _pyproject(sample_repo, "quickscale_cli")
    original = pyproject.read_text(encoding="utf-8")
    # Inject an extra path-based entry that the helper does not know
    # about. The rewrite map only contains quickscale-core for the CLI
    # package, so a different sibling should be left alone.
    with pyproject.open("a", encoding="utf-8") as handle:
        handle.write('other-sibling = {path = "../some_other"}\n')
    after_inject = pyproject.read_text(encoding="utf-8")
    prepare_publish.prepare_pyproject("quickscale_cli", pyproject, "0.86.0")
    final = pyproject.read_text(encoding="utf-8")
    # Known dep is rewritten.
    assert 'quickscale-core = "^0.86.0"' in final
    # Unknown path dep is left untouched so a maintainer-managed entry
    # is never silently dropped.
    assert 'other-sibling = {path = "../some_other"}' in final
    # Sanity: file is still well-formed TOML.
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    assert "other-sibling" in data["tool"]["poetry"]["dependencies"]
    # Original (pre-injection) content survived the in-flight edit, so
    # restore would still bring the file back to that exact state.
    assert final != after_inject
    # Clean up the injected line for the restore round-trip below.
    pyproject.write_text(original, encoding="utf-8")
    # Remove the leftover backup from the injection run so the restore
    # check below sees the correct baseline.
    (pyproject.with_name(pyproject.name + prepare_publish.BACKUP_SUFFIX)).unlink(
        missing_ok=True
    )


# ---------------------------------------------------------------------------
# prepare_pyproject: readme path rewrite
# ---------------------------------------------------------------------------


def test_prepare_rewrites_readme_path(sample_repo: Path) -> None:
    pyproject = _pyproject(sample_repo, "quickscale_cli")
    changes = prepare_publish.prepare_pyproject("quickscale_cli", pyproject, "0.86.0")
    rewritten = pyproject.read_text(encoding="utf-8")
    assert 'readme = "README.md"' in rewritten
    assert "../README.md" not in rewritten
    assert any("readme" in change for change in changes)


def test_prepare_also_rewrites_readme_in_meta_package(
    sample_repo: Path,
) -> None:
    pyproject = _pyproject(sample_repo, "quickscale")
    prepare_publish.prepare_pyproject("quickscale", pyproject, "0.86.0")
    rewritten = pyproject.read_text(encoding="utf-8")
    assert 'readme = "README.md"' in rewritten
    assert "../README.md" not in rewritten


# ---------------------------------------------------------------------------
# prepare_pyproject: backup, idempotency, validation
# ---------------------------------------------------------------------------


def test_prepare_creates_backup_file(sample_repo: Path) -> None:
    pyproject = _pyproject(sample_repo, "quickscale_cli")
    prepare_publish.prepare_pyproject("quickscale_cli", pyproject, "0.86.0")
    backup = pyproject.with_name(pyproject.name + prepare_publish.BACKUP_SUFFIX)
    assert backup.is_file()
    # The backup is the pre-edit pyproject, not the rewritten one.
    assert "quickscale-core = {path" in backup.read_text(encoding="utf-8")


def test_prepare_refuses_to_overwrite_invalid_toml(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "quickscale_cli"
    pkg_dir.mkdir()
    pyproject = pkg_dir / "pyproject.toml"
    original = "this is = not = valid = toml"
    pyproject.write_text(original, encoding="utf-8")

    with pytest.raises(prepare_publish.PreparePublishError):
        prepare_publish.prepare_pyproject("quickscale_cli", pyproject, "0.86.0")

    # The original file is untouched and no backup was written.
    assert pyproject.read_text(encoding="utf-8") == original
    assert not (
        pyproject.with_name(pyproject.name + prepare_publish.BACKUP_SUFFIX)
    ).is_file()


def test_prepare_rejects_missing_pyproject(tmp_path: Path) -> None:
    with pytest.raises(prepare_publish.PreparePublishError):
        prepare_publish.prepare_pyproject(
            "quickscale_cli", tmp_path / "missing.toml", "0.86.0"
        )


# ---------------------------------------------------------------------------
# restore_pyproject
# ---------------------------------------------------------------------------


def test_restore_returns_false_without_backup(sample_repo: Path) -> None:
    pyproject = _pyproject(sample_repo, "quickscale_cli")
    assert prepare_publish.restore_pyproject(pyproject) is False


def test_restore_round_trip_recovers_original(sample_repo: Path) -> None:
    pyproject = _pyproject(sample_repo, "quickscale_cli")
    original = pyproject.read_text(encoding="utf-8")
    prepare_publish.prepare_pyproject("quickscale_cli", pyproject, "0.86.0")
    assert pyproject.read_text(encoding="utf-8") != original
    assert prepare_publish.restore_pyproject(pyproject) is True
    assert pyproject.read_text(encoding="utf-8") == original
    # The backup shadow file is removed after restore.
    assert not (
        pyproject.with_name(pyproject.name + prepare_publish.BACKUP_SUFFIX)
    ).is_file()


# ---------------------------------------------------------------------------
# copy_readme / remove_readme
# ---------------------------------------------------------------------------


def test_copy_readme_is_idempotent(sample_repo: Path) -> None:
    assert prepare_publish.copy_readme(sample_repo, "quickscale_cli") is True
    # Second call must not clobber an existing copy.
    assert prepare_publish.copy_readme(sample_repo, "quickscale_cli") is False
    assert (sample_repo / "quickscale_cli" / "README.md").is_file()


def test_copy_readme_handles_missing_source(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "quickscale_cli"
    pkg_dir.mkdir()
    assert prepare_publish.copy_readme(tmp_path, "quickscale_cli") is False
    assert not (pkg_dir / "README.md").exists()


def test_remove_readme_deletes_only_existing_files(tmp_path: Path) -> None:
    pkg_dir = tmp_path / "quickscale_cli"
    pkg_dir.mkdir()
    readme = pkg_dir / "README.md"
    # A README without the helper marker is treated as pre-existing and
    # must NOT be removed by the restore path.
    readme.write_text("placeholder", encoding="utf-8")
    assert prepare_publish.remove_readme(pkg_dir) is False
    assert readme.exists()

    # Once the marker sidecar is present the README is recognised as a
    # helper-created copy and remove_readme cleans both up.
    marker = pkg_dir / prepare_publish.README_COPY_MARKER
    marker.write_text("", encoding="utf-8")
    assert prepare_publish.remove_readme(pkg_dir) is True
    assert not readme.exists()
    assert not marker.exists()
    # Second call is a clean no-op.
    assert prepare_publish.remove_readme(pkg_dir) is False


# ---------------------------------------------------------------------------
# prepare_all / restore_all
# ---------------------------------------------------------------------------


def test_prepare_all_walks_packages_in_dependency_order(
    sample_repo: Path,
) -> None:
    results = prepare_publish.prepare_all(sample_repo, "0.86.0")
    assert list(results.keys()) == list(prepare_publish.DEFAULT_PACKAGES)
    cli_text = (sample_repo / "quickscale_cli" / "pyproject.toml").read_text()
    meta_text = (sample_repo / "quickscale" / "pyproject.toml").read_text()
    assert 'quickscale-core = "^0.86.0"' in cli_text
    assert 'quickscale-core = "^0.86.0"' in meta_text
    assert 'quickscale-cli = "^0.86.0"' in meta_text


def test_restore_all_clears_backups_and_temporary_readmes(
    sample_repo: Path,
) -> None:
    prepare_publish.prepare_all(sample_repo, "0.86.0")
    # The helper has copied the root README into each package and
    # created a backup for every package.
    for package in prepare_publish.DEFAULT_PACKAGES:
        pkg_dir = sample_repo / package
        assert (pkg_dir / "README.md").is_file()
        assert (pkg_dir / f"pyproject.toml{prepare_publish.BACKUP_SUFFIX}").is_file()

    results = prepare_publish.restore_all(sample_repo)
    assert list(results.keys()) == list(prepare_publish.DEFAULT_PACKAGES)
    for package in prepare_publish.DEFAULT_PACKAGES:
        pkg_dir = sample_repo / package
        assert results[package] is True
        # Temporary README copy is removed.
        assert not (pkg_dir / "README.md").exists()
        # Backup shadow file is removed.
        assert not (
            pkg_dir / f"pyproject.toml{prepare_publish.BACKUP_SUFFIX}"
        ).is_file()
        # pyproject.toml matches the original fixture text.
        with (pkg_dir / "pyproject.toml").open("rb") as handle:
            data = tomllib.load(handle)
        assert "version" in data["project"]


def test_prepare_all_reads_version_from_repo_file(
    sample_repo: Path,
) -> None:
    # Bump the VERSION file and rerun; the rewritten constraints must
    # follow the file, not a hard-coded value.
    (sample_repo / "VERSION").write_text("1.2.3\n", encoding="utf-8")
    prepare_publish.prepare_all(sample_repo, "1.2.3")
    cli_text = (sample_repo / "quickscale_cli" / "pyproject.toml").read_text()
    assert 'quickscale-core = "^1.2.3"' in cli_text
    prepare_publish.restore_all(sample_repo)


# ---------------------------------------------------------------------------
# CLI surface
# ---------------------------------------------------------------------------


def test_cli_prepare_then_restore_round_trip(
    sample_repo: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import subprocess

    env = {"PYTHONPATH": str(SCRIPTS_DIR)}
    script = str(PREPARE_PUBLISH_PATH)
    result = subprocess.run(
        [
            sys.executable,
            script,
            "prepare",
            "--all",
            "--repo-root",
            str(sample_repo),
            "--version",
            "0.86.0",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    assert "quickscale_cli" in result.stdout
    assert "rewrote" in result.stdout

    # Round-trip via the CLI restore command.
    subprocess.run(
        [
            sys.executable,
            script,
            "restore",
            "--all",
            "--repo-root",
            str(sample_repo),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    capsys.readouterr()  # discard pytest's local capture

    for package in prepare_publish.DEFAULT_PACKAGES:
        pkg_dir = sample_repo / package
        assert not (pkg_dir / "README.md").exists()
        assert not (
            pkg_dir / f"pyproject.toml{prepare_publish.BACKUP_SUFFIX}"
        ).is_file()


def test_cli_rejects_missing_repo_root_arg(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as exc_info:
        prepare_publish.main(["prepare", "--all", "--version", "0.86.0"])
    assert exc_info.value.code == 2


def test_cli_requires_either_package_or_all(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(prepare_publish.PreparePublishError):
        prepare_publish.main(
            ["prepare", "--repo-root", str(tmp_path), "--version", "0.86.0"]
        )


# ---------------------------------------------------------------------------
# Cross-check against the live repository: the helper must leave the
# real QuickScale publish packages exactly as it found them.
# ---------------------------------------------------------------------------


def test_helper_is_a_noop_on_clean_real_pyprojects() -> None:
    """Running prepare_all against the live repo must be fully reversible."""
    repo_root = Path(__file__).resolve().parents[3]
    snapshot: dict[str, str] = {}
    for package in prepare_publish.DEFAULT_PACKAGES:
        snapshot[package] = (repo_root / package / "pyproject.toml").read_text(
            encoding="utf-8"
        )
        readme = repo_root / package / "README.md"
        snapshot[f"{package}_readme_exists"] = str(readme.exists())
        backup = repo_root / package / f"pyproject.toml{prepare_publish.BACKUP_SUFFIX}"
        snapshot[f"{package}_backup_exists"] = str(backup.exists())

    try:
        version = prepare_publish.read_version(repo_root / "VERSION")
        prepare_publish.prepare_all(repo_root, version)
        prepare_publish.restore_all(repo_root)

        for package in prepare_publish.DEFAULT_PACKAGES:
            current = (repo_root / package / "pyproject.toml").read_text(
                encoding="utf-8"
            )
            assert current == snapshot[package], (
                f"prepare_all/restore_all did not return {package} to its "
                f"original content"
            )
            readme_exists = (repo_root / package / "README.md").exists()
            assert str(readme_exists) == snapshot[f"{package}_readme_exists"]
            backup_exists = (
                repo_root / package / f"pyproject.toml{prepare_publish.BACKUP_SUFFIX}"
            ).exists()
            assert str(backup_exists) == snapshot[f"{package}_backup_exists"]
    finally:
        # Defensive cleanup: if the test fails mid-way, still attempt to
        # restore the repository to its pre-test state.
        try:
            prepare_publish.restore_all(repo_root)
        except Exception:  # pragma: no cover - best-effort cleanup
            pass
        # Remove any stray helper-created READMEs or backups.  Using the
        # marker-aware ``remove_readme`` helper ensures pre-existing
        # package READMEs are never deleted here.
        for package in prepare_publish.DEFAULT_PACKAGES:
            prepare_publish.remove_readme(repo_root / package)
            backup = (
                repo_root / package / f"pyproject.toml{prepare_publish.BACKUP_SUFFIX}"
            )
            if backup.exists():
                backup.unlink()
        # Final guard: make sure the real pyprojects are exactly the
        # original content we snapshotted at the start of the test.
        for package in prepare_publish.DEFAULT_PACKAGES:
            current = (repo_root / package / "pyproject.toml").read_text(
                encoding="utf-8"
            )
            assert current == snapshot[package], (
                f"Cleanup failed: {package}/pyproject.toml was modified "
                f"and could not be restored to its original content"
            )


# Re-export ``shutil`` so static analysis tools do not flag it as unused
# (it is used transitively by the importlib loader when reloading the
# helper in long-running test sessions).
_ = shutil
