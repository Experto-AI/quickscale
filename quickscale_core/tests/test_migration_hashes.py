"""Tests for the module migration content-hash helpers."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from quickscale_core import migration_hashes
from quickscale_core.migration_hashes import (
    MigrationHashError,
    compute_migration_hashes,
    compute_module_migration_hashes,
    hash_migration_file,
    is_frozen_vintage,
    resolve_module_migrations_dir,
)


def _write_module(
    root: Path,
    name: str,
    migrations: dict[str, str] | None = None,
) -> Path:
    """Create a module directory in the shipped layout.

    ``migrations=None`` builds a service-style module with no migrations
    package; a mapping builds a model-style module with one file per entry.
    """
    module_dir = root / name
    package_dir = module_dir / "src" / f"quickscale_modules_{name}"
    package_dir.mkdir(parents=True)
    (package_dir / "__init__.py").write_text("")
    if migrations is not None:
        migrations_dir = package_dir / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "__init__.py").write_text("")
        for filename, content in migrations.items():
            (migrations_dir / filename).write_text(content)
    return module_dir


class TestComputeMigrationHashes:
    """Hashing one migrations package."""

    def test_hashes_raw_file_bytes(self, tmp_path: Path) -> None:
        module_dir = _write_module(tmp_path, "auth", {"0001_initial.py": "x = 1\n"})
        hashes = compute_module_migration_hashes(module_dir)
        expected = hashlib.sha256(b"x = 1\n").hexdigest()
        assert hashes == {"0001_initial.py": expected}

    def test_orders_migration_files_by_name(self, tmp_path: Path) -> None:
        module_dir = _write_module(
            tmp_path,
            "auth",
            {
                "0002_add_field.py": "second",
                "0001_initial.py": "first",
                "0010_late_change.py": "tenth",
            },
        )
        hashes = compute_module_migration_hashes(module_dir)
        assert list(hashes) == [
            "0001_initial.py",
            "0002_add_field.py",
            "0010_late_change.py",
        ]

    def test_ignores_non_migration_files(self, tmp_path: Path) -> None:
        module_dir = _write_module(tmp_path, "auth", {"0001_initial.py": "initial"})
        migrations_dir = module_dir / "src" / "quickscale_modules_auth" / "migrations"
        (migrations_dir / "helpers.py").write_text("not a migration")
        (migrations_dir / "notes.txt").write_text("not python")
        (migrations_dir / "__pycache__").mkdir()
        (migrations_dir / "__pycache__" / "0009_hidden.cpython-314.pyc").write_bytes(
            b"cache"
        )
        hashes = compute_module_migration_hashes(module_dir)
        assert list(hashes) == ["0001_initial.py"]

    def test_digest_covers_whole_file(self, tmp_path: Path) -> None:
        payload = ("line of migration source\n" * 4000).encode()
        assert len(payload) > 65536
        migration = tmp_path / "0001_initial.py"
        migration.write_bytes(payload)
        assert hash_migration_file(migration) == hashlib.sha256(payload).hexdigest()

    def test_tampered_content_changes_digest(self, tmp_path: Path) -> None:
        module_dir = _write_module(tmp_path, "auth", {"0001_initial.py": "original"})
        before = compute_module_migration_hashes(module_dir)
        migration = (
            module_dir
            / "src"
            / "quickscale_modules_auth"
            / "migrations"
            / "0001_initial.py"
        )
        migration.write_text("tampered")
        after = compute_module_migration_hashes(module_dir)
        assert before != after
        assert after["0001_initial.py"] == hashlib.sha256(b"tampered").hexdigest()

    def test_service_module_yields_empty_mapping(self, tmp_path: Path) -> None:
        module_dir = _write_module(tmp_path, "analytics", migrations=None)
        assert compute_module_migration_hashes(module_dir) == {}

    def test_missing_source_package_fails_closed(self, tmp_path: Path) -> None:
        module_dir = tmp_path / "auth"
        module_dir.mkdir()
        (module_dir / "module.yml").write_text("name: auth\n")
        with pytest.raises(MigrationHashError, match="no source package"):
            compute_module_migration_hashes(module_dir)

    def test_empty_migrations_package_fails_closed(self, tmp_path: Path) -> None:
        module_dir = _write_module(tmp_path, "auth", migrations={})
        with pytest.raises(MigrationHashError, match="no numbered migration files"):
            compute_module_migration_hashes(module_dir)

    def test_missing_migrations_directory_fails_closed(self, tmp_path: Path) -> None:
        with pytest.raises(MigrationHashError, match="not found"):
            compute_migration_hashes(tmp_path / "absent" / "migrations")

    def test_resolution_reports_shipped_layout(self, tmp_path: Path) -> None:
        module_dir = _write_module(tmp_path, "auth", {"0001_initial.py": "initial"})
        resolved = resolve_module_migrations_dir(module_dir)
        assert resolved == module_dir / "src" / "quickscale_modules_auth" / "migrations"
        assert resolve_module_migrations_dir(_write_module(tmp_path, "storage")) is None


class TestIsFrozenVintage:
    """Which applied vintages sit at or after the model migration freeze."""

    def test_unset_freeze_has_no_frozen_vintage(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """While SA204 (j) has not set the freeze vintage, nothing is frozen."""
        monkeypatch.setattr(migration_hashes, "MIGRATION_FREEZE_VINTAGE", None)
        assert is_frozen_vintage("0.89.0") is False
        assert is_frozen_vintage("99.0.0") is False

    def test_vintage_at_the_freeze_is_frozen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(migration_hashes, "MIGRATION_FREEZE_VINTAGE", "0.90.0")
        assert is_frozen_vintage("0.90.0") is True

    def test_vintage_after_the_freeze_is_frozen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(migration_hashes, "MIGRATION_FREEZE_VINTAGE", "0.90.0")
        assert is_frozen_vintage("0.90.1") is True
        assert is_frozen_vintage("1.0.0") is True

    def test_vintage_before_the_freeze_is_not_frozen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(migration_hashes, "MIGRATION_FREEZE_VINTAGE", "0.90.0")
        assert is_frozen_vintage("0.89.0") is False

    def test_missing_or_unparseable_vintage_is_not_frozen(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(migration_hashes, "MIGRATION_FREEZE_VINTAGE", "0.90.0")
        assert is_frozen_vintage(None) is False
        assert is_frozen_vintage("") is False
        assert is_frozen_vintage("not.a.version") is False
