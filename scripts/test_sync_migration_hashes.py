"""
Hermetic tests for the migration hash manifest generator.

The generator is exercised against a complete twelve-module fixture tree
(the authoritative inventory) installed through the module-discovery
override seam, so no test reads or writes the real checked-in manifest.

Test matrix
-----------
* ``TestWrite`` — regeneration, structure, and determinism.
* ``TestCheck`` — current, drifted, missing, malformed, and read-only behavior.
* ``TestFailClosed`` — discovery and migration-package failures exit 2.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from collections.abc import Iterator
from pathlib import Path

import pytest

import scripts.sync_migration_hashes as sync_migration_hashes
from quickscale_core.contracts import module_discovery

MODEL_MODULES: tuple[str, ...] = (
    "auth",
    "backups",
    "billing",
    "blog",
    "crm",
    "forms",
    "listings",
    "notifications",
    "orgs",
    "social",
)
SERVICE_MODULES: tuple[str, ...] = ("analytics", "storage")


def _build_modules_fixture(root: Path) -> None:
    """Create the twelve shipped modules with migration files where they ship them."""
    for name in MODEL_MODULES:
        module_dir = root / name
        package_dir = module_dir / "src" / f"quickscale_modules_{name}"
        migrations_dir = package_dir / "migrations"
        migrations_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text(f"name: {name}\n")
        (package_dir / "__init__.py").write_text("")
        (migrations_dir / "__init__.py").write_text("")
        (migrations_dir / "0001_initial.py").write_text(f"# {name} initial migration\n")
    for name in SERVICE_MODULES:
        module_dir = root / name
        package_dir = module_dir / "src" / f"quickscale_modules_{name}"
        package_dir.mkdir(parents=True)
        (module_dir / "module.yml").write_text(f"name: {name}\n")
        (package_dir / "__init__.py").write_text("")


@pytest.fixture
def manifest_path(tmp_path: Path) -> Path:
    """Return a manifest path outside the repository tree."""
    return tmp_path / "migration_hashes.json"


@pytest.fixture
def modules_fixture(tmp_path: Path) -> Iterator[Path]:
    """Install a complete twelve-module fixture as the discovery root."""
    modules_root = tmp_path / "quickscale_modules"
    modules_root.mkdir()
    _build_modules_fixture(modules_root)
    original = module_discovery.get_modules_base_path()
    module_discovery.set_modules_base_path(modules_root)
    try:
        yield modules_root
    finally:
        module_discovery.set_modules_base_path(original)


def _check(manifest_path: Path, capsys: pytest.CaptureFixture[str]) -> tuple[int, str, str]:
    """Run check mode and return ``(exit_code, stdout, stderr)``."""
    code = sync_migration_hashes.main(["--check", "--manifest", str(manifest_path)])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


class TestWrite:
    """Regeneration mode."""

    def test_write_then_check_is_current(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        assert sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)]) == 0
        capsys.readouterr()
        assert manifest_path.is_file()

        code, stdout, stderr = _check(manifest_path, capsys)
        assert code == 0
        assert "is current" in stdout
        assert stderr == ""

    def test_manifest_structure_covers_every_module(
        self,
        modules_fixture: Path,
        manifest_path: Path,
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert payload["schema_version"] == 1
        modules = payload["modules"]
        assert sorted(modules) == sorted(MODEL_MODULES + SERVICE_MODULES)
        for name in MODEL_MODULES:
            expected = hashlib.sha256(f"# {name} initial migration\n".encode()).hexdigest()
            assert modules[name] == {"0001_initial.py": expected}
        for name in SERVICE_MODULES:
            assert modules[name] == {}

    def test_rewrite_is_byte_identical(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        tmp_path: Path,
    ) -> None:
        other_path = tmp_path / "other_manifest.json"
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        sync_migration_hashes.main(["--write", "--manifest", str(other_path)])
        assert manifest_path.read_bytes() == other_path.read_bytes()

    def test_second_write_reports_already_current(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        capsys.readouterr()
        assert sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)]) == 0
        assert "already current" in capsys.readouterr().out


class TestCheck:
    """Check mode."""

    def test_source_change_reports_drift_with_diff(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        capsys.readouterr()
        migration = (
            modules_fixture
            / "auth"
            / "src"
            / "quickscale_modules_auth"
            / "migrations"
            / "0001_initial.py"
        )
        migration.write_text("# auth initial migration, edited\n")

        code, stdout, stderr = _check(manifest_path, capsys)
        assert code == 1
        assert "0001_initial.py" in stdout
        assert stderr == ""

    def test_stale_manifest_text_reports_drift(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        capsys.readouterr()
        manifest_path.write_text(manifest_path.read_text(encoding="utf-8") + "\n")

        code, stdout, _stderr = _check(manifest_path, capsys)
        assert code == 1
        assert stdout.startswith("--- ")

    def test_check_is_read_only(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        capsys.readouterr()
        original = manifest_path.read_bytes()
        migration = (
            modules_fixture
            / "blog"
            / "src"
            / "quickscale_modules_blog"
            / "migrations"
            / "0001_initial.py"
        )
        migration.write_text("# changed\n")

        assert _check(manifest_path, capsys)[0] == 1
        assert manifest_path.read_bytes() == original

    def test_missing_manifest_is_configuration_error(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        code, _stdout, stderr = _check(manifest_path, capsys)
        assert code == 2
        assert "ERROR:" in stderr

    def test_new_migration_reports_drift(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        capsys.readouterr()
        migrations_dir = modules_fixture / "auth" / "src" / "quickscale_modules_auth" / "migrations"
        (migrations_dir / "0002_add_field.py").write_text("# new migration\n")

        code, stdout, _stderr = _check(manifest_path, capsys)
        assert code == 1
        assert "0002_add_field.py" in stdout

    @pytest.mark.parametrize(
        ("label", "content"),
        [
            ("truncated JSON", '{"schema_version": 1, "modules": {'),
            (
                "duplicate key",
                '{"schema_version": 1, "schema_version": 1, "modules": {}}',
            ),
            ("wrong schema version", '{"schema_version": 2, "modules": {}}'),
            ("boolean schema version", '{"schema_version": true, "modules": {}}'),
            ("non-finite description", '{"schema_version": 1, "modules": {}, "description": NaN}'),
            (
                "infinite description",
                '{"schema_version": 1, "modules": {}, "description": Infinity}',
            ),
            ("modules not an object", '{"schema_version": 1, "modules": []}'),
            (
                "non-string digest",
                '{"schema_version": 1, "modules": {"auth": {"0001_initial.py": 1}}}',
            ),
        ],
    )
    def test_malformed_manifest_is_configuration_error(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
        label: str,
        content: str,
    ) -> None:
        manifest_path.write_text(content, encoding="utf-8")

        code, _stdout, stderr = _check(manifest_path, capsys)
        assert code == 2, label
        assert "ERROR:" in stderr


class TestFailClosed:
    """Malformed module trees exit 2 instead of hashing a partial inventory."""

    def test_missing_source_package_is_configuration_error(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        capsys.readouterr()
        shutil.rmtree(modules_fixture / "crm" / "src")

        code, _stdout, stderr = _check(manifest_path, capsys)
        assert code == 2
        assert "no source package" in stderr

    def test_empty_migrations_package_is_configuration_error(
        self,
        modules_fixture: Path,
        manifest_path: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        sync_migration_hashes.main(["--write", "--manifest", str(manifest_path)])
        capsys.readouterr()
        (
            modules_fixture
            / "listings"
            / "src"
            / "quickscale_modules_listings"
            / "migrations"
            / "0001_initial.py"
        ).unlink()

        code, _stdout, stderr = _check(manifest_path, capsys)
        assert code == 2
        assert "no numbered migration files" in stderr
