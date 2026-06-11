"""Tests for the unified QuickScale project state owner.

Covers ``quickscale_core.project_state`` — the additive unified owner
for ``.quickscale/state.yml`` and ``.quickscale/config.yml`` plus
managed-file drift detection helpers introduced in Phase 3.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from pathlib import Path

import pytest
import yaml

from quickscale_core.config import ModuleConfig, ModuleInfo
from quickscale_core.project_state import (
    DEFAULT_MANAGED_WIRING_PATHS,
    FILE_HASHES_FILENAME,
    ManagedFileHash,
    ProjectStateManager,
    VersionDriftWarning,
    check_version_drift,
    compute_file_hashes,
    hash_managed_file,
)
from quickscale_core.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateManager,
)


# ---------------------------------------------------------------------------
# Re-exports stay intact
# ---------------------------------------------------------------------------


class TestProjectStateReExports:
    """The unified module must re-export existing names unchanged."""

    def test_module_config_symbols_are_reexported(self) -> None:
        from quickscale_core.project_state import (
            ModuleConfig as ProjectStateModuleConfig,
        )
        from quickscale_core.config import ModuleConfig as ConfigModuleConfig

        assert ProjectStateModuleConfig is ConfigModuleConfig

    def test_state_schema_symbols_are_reexported(self) -> None:
        from quickscale_core.project_state import StateManager as PSMStateManager
        from quickscale_core.schema.state_schema import (
            StateManager as SchemaStateManager,
        )

        assert PSMStateManager is SchemaStateManager


# ---------------------------------------------------------------------------
# ManagedFileHash dataclass
# ---------------------------------------------------------------------------


class TestManagedFileHash:
    """Tests for the ManagedFileHash dataclass."""

    def test_to_dict_round_trip(self) -> None:
        record = ManagedFileHash(
            path="myapp/settings/modules.py",
            hash="abc123",
            applied_at="2025-12-01T10:00:00",
        )

        data = record.to_dict()
        assert data == {
            "path": "myapp/settings/modules.py",
            "hash": "abc123",
            "applied_at": "2025-12-01T10:00:00",
        }

        rebuilt = ManagedFileHash.from_dict(data)
        assert rebuilt.path == record.path
        assert rebuilt.hash == record.hash
        assert rebuilt.applied_at == record.applied_at

    def test_default_timestamp_is_iso(self) -> None:
        record = ManagedFileHash(path="x", hash="y")
        # The default applied_at must be ISO-8601 (round-trippable).
        datetime.fromisoformat(record.applied_at)


# ---------------------------------------------------------------------------
# hash_managed_file / compute_file_hashes
# ---------------------------------------------------------------------------


class TestComputeFileHashes:
    """Tests for SHA-256 helpers."""

    def test_hash_managed_file_matches_hashlib(self, tmp_path: Path) -> None:
        target = tmp_path / "hello.py"
        target.write_text("hello\n")

        expected = hashlib.sha256(b"hello\n").hexdigest()
        assert hash_managed_file(target) == expected

    def test_hash_managed_file_missing_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            hash_managed_file(tmp_path / "nope.py")

    def test_compute_file_hashes_skips_missing(self, tmp_path: Path) -> None:
        (tmp_path / "exists.py").write_text("ok")

        result = compute_file_hashes(tmp_path, ["exists.py", "missing.py"])
        assert "exists.py" in result
        assert "missing.py" not in result

    def test_compute_file_hashes_normalizes_paths(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "a.py").write_text("a")
        # Use backslashes and a leading slash to verify normalization.
        result = compute_file_hashes(tmp_path, ["\\sub\\a.py", "/sub/a.py"])
        assert result == {"sub/a.py": hashlib.sha256(b"a").hexdigest()}


# ---------------------------------------------------------------------------
# check_version_drift
# ---------------------------------------------------------------------------


class TestCheckVersionDrift:
    """Tests for the cross-file version drift detector."""

    def test_returns_empty_when_state_and_config_agree(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="0.62.0",
            installed_at="2025-12-01",
        )

        assert check_version_drift(state, config) == []

    def test_returns_warning_when_versions_differ(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
                "billing": ModuleState(name="billing", version="1.0.0"),
            },
        )
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="0.63.0",  # Drift!
            installed_at="2025-12-01",
        )
        config.modules["billing"] = ModuleInfo(
            prefix="modules/billing",
            branch="splits/billing-module",
            installed_version="1.0.0",
            installed_at="2025-12-01",
        )

        warnings = check_version_drift(state, config)
        assert len(warnings) == 1
        assert isinstance(warnings[0], VersionDriftWarning)
        assert warnings[0].module == "auth"
        assert warnings[0].state_version == "0.62.0"
        assert warnings[0].config_version == "0.63.0"

    def test_ignores_modules_only_in_one_source(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "only_in_state": ModuleState(name="only_in_state"),
            },
        )
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["only_in_config"] = ModuleInfo(
            prefix="modules/only_in_config",
            branch="splits/x",
            installed_version="1.0.0",
            installed_at="2025-12-01",
        )

        assert check_version_drift(state, config) == []

    def test_returns_empty_when_state_or_config_is_none(self) -> None:
        config = ModuleConfig(default_remote="https://example.com/r.git")
        assert check_version_drift(None, config) == []

        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
        )
        assert check_version_drift(state, None) == []
        assert check_version_drift(None, None) == []


# ---------------------------------------------------------------------------
# ProjectStateManager
# ---------------------------------------------------------------------------


class TestProjectStateManager:
    """Tests for the unified project state manager."""

    def test_constructs_with_expected_paths(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)

        assert manager.project_path == tmp_path
        assert manager.state_file == tmp_path / ".quickscale" / "state.yml"
        assert manager.config_file == tmp_path / ".quickscale" / "config.yml"
        assert manager.file_hashes_file == (
            tmp_path / ".quickscale" / FILE_HASHES_FILENAME
        )

    def test_load_state_delegates_to_state_manager(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)
        assert manager.load_state() is None

        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
        )
        manager.save_state(state)
        assert manager.load_state() is not None

    def test_save_and_load_config_round_trip(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="0.62.0",
            installed_at="2025-12-01",
        )
        manager.save_config(config)

        loaded = manager.load_config()
        assert loaded.default_remote == "https://example.com/r.git"
        assert "auth" in loaded.modules
        assert loaded.modules["auth"].installed_version == "0.62.0"

    def test_load_config_returns_default_when_missing(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)
        loaded = manager.load_config()
        assert loaded.default_remote == ("https://github.com/Experto-AI/quickscale.git")
        assert loaded.modules == {}

    def test_capture_managed_file_hashes_persists(self, tmp_path: Path) -> None:
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()
        settings_dir = package_dir / "settings"
        settings_dir.mkdir()
        settings_modules = settings_dir / "modules.py"
        settings_modules.write_text("APP = []\n")
        urls_modules = package_dir / "urls_modules.py"
        urls_modules.write_text("URLS = []\n")

        manager = ProjectStateManager(tmp_path)
        records = manager.capture_managed_file_hashes(
            [
                "myapp/settings/modules.py",
                "myapp/urls_modules.py",
                "myapp/missing.py",
            ]
        )

        assert set(records) == {
            "myapp/settings/modules.py",
            "myapp/urls_modules.py",
        }
        assert records["myapp/settings/modules.py"].hash == (
            hashlib.sha256(b"APP = []\n").hexdigest()
        )

        # The ledger file should now exist.
        assert manager.file_hashes_file.exists()
        persisted = yaml.safe_load(manager.file_hashes_file.read_text())
        assert persisted["version"] == "1"
        paths = {entry["path"] for entry in persisted["files"]}
        assert paths == {
            "myapp/settings/modules.py",
            "myapp/urls_modules.py",
        }

    def test_save_managed_file_hashes_accepts_string_map(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)
        manager.save_managed_file_hashes({"a/b.py": "deadbeef" * 8})

        stored = manager.load_managed_file_hashes()
        assert "a/b.py" in stored
        assert stored["a/b.py"].hash == "deadbeef" * 8

    def test_detect_managed_file_drift_reports_modified(self, tmp_path: Path) -> None:
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()
        settings_dir = package_dir / "settings"
        settings_dir.mkdir()
        settings_modules = settings_dir / "modules.py"
        settings_modules.write_text("A = 1\n")
        urls_modules = package_dir / "urls_modules.py"
        urls_modules.write_text("URLS = []\n")

        manager = ProjectStateManager(tmp_path)
        manager.capture_managed_file_hashes(
            [
                "myapp/settings/modules.py",
                "myapp/urls_modules.py",
            ]
        )

        # No drift immediately after capture.
        assert manager.detect_managed_file_drift() == []

        # Mutate one file and re-check.
        settings_modules.write_text("A = 2\n")
        drifted = manager.detect_managed_file_drift()
        assert len(drifted) == 1
        assert drifted[0].path == "myapp/settings/modules.py"
        assert drifted[0].hash == (hashlib.sha256(b"A = 1\n").hexdigest())

    def test_detect_managed_file_drift_reports_missing(self, tmp_path: Path) -> None:
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()
        (package_dir / "settings").mkdir()
        settings_modules = package_dir / "settings" / "modules.py"
        settings_modules.write_text("A = 1\n")

        manager = ProjectStateManager(tmp_path)
        manager.capture_managed_file_hashes(["myapp/settings/modules.py"])

        # Remove the file and verify drift is reported.
        settings_modules.unlink()
        drifted = manager.detect_managed_file_drift()
        assert len(drifted) == 1
        assert drifted[0].path == "myapp/settings/modules.py"

    def test_detect_drift_filters_by_path(self, tmp_path: Path) -> None:
        package_dir = tmp_path / "myapp"
        package_dir.mkdir()
        (package_dir / "settings").mkdir()
        a = package_dir / "settings" / "modules.py"
        a.write_text("A\n")
        b = package_dir / "urls_modules.py"
        b.write_text("B\n")

        manager = ProjectStateManager(tmp_path)
        manager.capture_managed_file_hashes(
            ["myapp/settings/modules.py", "myapp/urls_modules.py"]
        )

        # Mutate both, but only ask about one.
        a.write_text("A2\n")
        b.write_text("B2\n")
        drifted = manager.detect_managed_file_drift(["myapp/settings/modules.py"])
        assert [r.path for r in drifted] == ["myapp/settings/modules.py"]

    def test_detect_drift_empty_when_no_ledger(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)
        assert manager.detect_managed_file_drift() == []

    def test_verify_consistency_reports_drift(self, tmp_path: Path) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="0.63.0",
            installed_at="2025-12-01",
        )

        manager = ProjectStateManager(tmp_path)
        manager.save_state(state)
        manager.save_config(config)

        report = manager.verify_consistency()
        assert "version_drift" in report
        assert len(report["version_drift"]) == 1
        assert report["version_drift"][0].module == "auth"

    def test_verify_consistency_empty_when_files_agree(self, tmp_path: Path) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_html"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="0.62.0",
            installed_at="2025-12-01",
        )

        manager = ProjectStateManager(tmp_path)
        manager.save_state(state)
        manager.save_config(config)

        assert manager.verify_consistency() == {"version_drift": []}

    def test_load_managed_file_hashes_returns_empty_for_missing(
        self, tmp_path: Path
    ) -> None:
        manager = ProjectStateManager(tmp_path)
        assert manager.load_managed_file_hashes() == {}


# ---------------------------------------------------------------------------
# State schema state.yml format is unchanged by Phase 3
# ---------------------------------------------------------------------------


class TestStateYmlFormatUnchanged:
    """Verify the legacy state schema is untouched by Phase 3 changes."""

    def test_legacy_state_save_unchanged(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_html",
                created_at="2025-12-01T10:00:00",
                last_applied="2025-12-01T11:00:00",
            ),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.62.0",
                    commit_sha="abc123",
                    embedded_at="2025-12-01T10:00:00",
                    options={"registration_enabled": True},
                )
            },
        )
        manager.save(state)

        raw = yaml.safe_load(manager.state_file.read_text())
        # Phase 3 must not have added any new top-level keys.
        assert set(raw) == {"version", "project", "modules"}
        # And the file_hashes key must not appear on the legacy state file.
        assert "file_hashes" not in raw
        assert "managed_file_hashes" not in raw


# ---------------------------------------------------------------------------
# Sanity check on the default managed-wiring paths
# ---------------------------------------------------------------------------


class TestDefaultManagedWiringPaths:
    """The default tracked paths are stable, repo-relative, and forward-slashed."""

    def test_default_paths_are_repo_relative(self) -> None:
        for path in DEFAULT_MANAGED_WIRING_PATHS:
            assert "\\" not in path
            assert not path.startswith("/")
            assert path.endswith(".py")
