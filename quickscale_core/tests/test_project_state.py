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

from quickscale_core.config import ConfigError, ModuleConfig, ModuleInfo
from quickscale_core.schema.config_schema import ConfigValidationError
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
    StateError,
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
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
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
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
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
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
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
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
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
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
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
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
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
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
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
# ConfigError -> StateError normalization at the project-state boundary
# ---------------------------------------------------------------------------


class TestVerifyConsistencyNormalizesConfigError:
    """Phase 1: ``verify_consistency`` must surface ConfigError as StateError.

    The unified :class:`ProjectStateManager` is the boundary that CLI
    surfaces talk to. A malformed ``.quickscale/config.yml`` raises
    :class:`quickscale_core.config.ConfigError` from the low-level loader,
    and that error type must be normalized to
    :class:`quickscale_core.schema.state_schema.StateError` here so callers
    only need to handle one error class for both ``state.yml`` and
    ``config.yml``.
    """

    def _write_malformed_config(self, project_path: Path) -> Path:
        config_dir = project_path / ".quickscale"
        config_dir.mkdir()
        config_file = config_dir / "config.yml"
        # Tabs are not valid for YAML indentation.
        config_file.write_text(
            "default_remote: https://example.com/r.git\nmodules:\n\tauth:\n"
        )
        return config_file

    def test_verify_consistency_raises_state_error_for_malformed_config(
        self, tmp_path: Path
    ) -> None:
        manager = ProjectStateManager(tmp_path)
        self._write_malformed_config(tmp_path)

        with pytest.raises(StateError) as excinfo:
            manager.verify_consistency()

        # The boundary message must mention config.yml so operators can act.
        assert "config.yml" in str(excinfo.value)

    def test_verify_consistency_chains_underlying_config_error(
        self, tmp_path: Path
    ) -> None:
        """The original ConfigError must remain reachable via __cause__."""
        manager = ProjectStateManager(tmp_path)
        self._write_malformed_config(tmp_path)

        with pytest.raises(StateError) as excinfo:
            manager.verify_consistency()

        assert isinstance(excinfo.value.__cause__, ConfigError)
        # The deeper yaml.YAMLError must still be reachable from the chain.
        assert isinstance(excinfo.value.__cause__.__cause__, yaml.YAMLError)


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
                theme="showcase_react",
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


# ---------------------------------------------------------------------------
# Phase 2: Consolidated state schema
# ---------------------------------------------------------------------------


class TestModuleStateConsolidatedTracking:
    """Phase 2: ModuleState carries optional consolidated tracking fields."""

    def test_module_state_has_consolidated_tracking_false_by_default(self) -> None:
        module = ModuleState(name="auth")
        assert module.has_consolidated_tracking is False

    def test_module_state_has_consolidated_tracking_when_all_present(self) -> None:
        module = ModuleState(
            name="auth",
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_at="2025-01-01",
        )
        assert module.has_consolidated_tracking is True

    def test_module_state_partial_tracking_is_not_consolidated(self) -> None:
        module = ModuleState(name="auth", prefix="modules/auth")
        assert module.has_consolidated_tracking is False


class TestManagedFileRecord:
    """Phase 2: ManagedFileRecord is the consolidated form for state.yml."""

    def test_to_dict_round_trip(self) -> None:
        from quickscale_core.schema.state_schema import ManagedFileRecord

        record = ManagedFileRecord(
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

        rebuilt = ManagedFileRecord.from_dict(data)
        assert rebuilt.path == record.path
        assert rebuilt.hash == record.hash
        assert rebuilt.applied_at == record.applied_at

    def test_default_timestamp_is_iso(self) -> None:
        from quickscale_core.schema.state_schema import ManagedFileRecord

        record = ManagedFileRecord(path="x", hash="y")
        datetime.fromisoformat(record.applied_at)


class TestQuickScaleStateConsolidatedModules:
    """Phase 2: QuickScaleState.has_consolidated_modules property."""

    def test_empty_modules_is_consolidated(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
        )
        assert state.has_consolidated_modules is True

    def test_all_modules_consolidated(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(
                    name="auth",
                    prefix="modules/auth",
                    branch="splits/auth-module",
                    installed_at="2025-01-01",
                ),
            },
        )
        assert state.has_consolidated_modules is True

    def test_mixed_modules_not_consolidated(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(
                    name="auth",
                    prefix="modules/auth",
                    branch="splits/auth-module",
                    installed_at="2025-01-01",
                ),
                "billing": ModuleState(name="billing"),  # No tracking.
            },
        )
        assert state.has_consolidated_modules is False


class TestStateManagerConsolidatedSections:
    """Phase 2: StateManager loads/saves consolidated sections."""

    def test_save_and_load_consolidated_module_tracking(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.62.0",
                    prefix="modules/auth",
                    branch="splits/auth-module",
                    installed_at="2025-01-01",
                ),
            },
        )
        manager.save(state)
        loaded = manager.load()

        assert loaded is not None
        assert loaded.modules["auth"].prefix == "modules/auth"
        assert loaded.modules["auth"].branch == "splits/auth-module"
        assert loaded.modules["auth"].installed_at == "2025-01-01"

    def test_save_and_load_managed_files(self, tmp_path: Path) -> None:
        from quickscale_core.schema.state_schema import ManagedFileRecord

        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            managed_files={
                "myapp/settings/modules.py": ManagedFileRecord(
                    path="myapp/settings/modules.py",
                    hash="abc123",
                    applied_at="2025-01-01T10:00:00",
                ),
            },
        )
        manager.save(state)
        loaded = manager.load()

        assert loaded is not None
        assert "myapp/settings/modules.py" in loaded.managed_files
        record = loaded.managed_files["myapp/settings/modules.py"]
        assert record.hash == "abc123"
        assert record.applied_at == "2025-01-01T10:00:00"

    def test_load_legacy_state_without_consolidated_sections(
        self, tmp_path: Path
    ) -> None:
        """Legacy state.yml without consolidated sections loads fine."""
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "modules:\n"
            "  auth:\n"
            '    version: "0.62.0"\n'
        )
        loaded = manager.load()

        assert loaded is not None
        assert loaded.modules["auth"].prefix is None
        assert loaded.modules["auth"].branch is None
        assert loaded.modules["auth"].installed_at is None
        assert loaded.managed_files == {}

    def test_save_omits_none_tracking_fields(self, tmp_path: Path) -> None:
        """When tracking fields are None, they should not appear in YAML."""
        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        manager.save(state)

        raw = yaml.safe_load(manager.state_file.read_text())
        auth_data = raw["modules"]["auth"]
        assert "prefix" not in auth_data
        assert "branch" not in auth_data
        assert "installed_at" not in auth_data


class TestProjectStateManagerReadThroughImport:
    """Phase 2: ProjectStateManager read-through imports legacy files."""

    def test_load_state_imports_legacy_config_when_no_consolidated(
        self, tmp_path: Path
    ) -> None:
        """When state.yml lacks consolidated sections, import from config.yml."""
        manager = ProjectStateManager(tmp_path)

        # Write legacy state.yml without consolidated tracking.
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        manager.save_state(state)

        # Write legacy config.yml with tracking metadata.
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="0.62.0",
            installed_at="2025-01-01",
        )
        manager.save_config(config)

        # Load state — should read-through import from config.yml.
        loaded = manager.load_state()
        assert loaded is not None
        assert loaded.modules["auth"].prefix == "modules/auth"
        assert loaded.modules["auth"].branch == "splits/auth-module"
        assert loaded.modules["auth"].installed_at == "2025-01-01"

    def test_load_state_ignores_legacy_when_consolidated_present(
        self, tmp_path: Path
    ) -> None:
        """When state.yml has consolidated sections, ignore legacy files."""
        manager = ProjectStateManager(tmp_path)

        # Write consolidated state.yml.
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.62.0",
                    prefix="modules/auth",
                    branch="splits/auth-module",
                    installed_at="2025-01-01",
                ),
            },
        )
        manager.save_state(state)

        # Write a conflicting legacy config.yml.
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth-OLD",
            branch="splits/auth-module-OLD",
            installed_version="0.62.0",
            installed_at="2020-01-01",
        )
        manager.save_config(config)

        # Load state — should ignore legacy config.yml.
        loaded = manager.load_state()
        assert loaded is not None
        assert loaded.modules["auth"].prefix == "modules/auth"
        assert loaded.modules["auth"].branch == "splits/auth-module"
        assert loaded.modules["auth"].installed_at == "2025-01-01"

    def test_load_state_imports_legacy_file_hashes_when_no_consolidated(
        self, tmp_path: Path
    ) -> None:
        """When state.yml lacks managed_files, import from file_hashes.yml."""
        manager = ProjectStateManager(tmp_path)

        # Write legacy state.yml without managed_files.
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
        )
        manager.save_state(state)

        # Write legacy file_hashes.yml.
        manager.save_managed_file_hashes({"myapp/settings/modules.py": "abc123"})

        # Load state — should read-through import from file_hashes.yml.
        loaded = manager.load_state()
        assert loaded is not None
        assert "myapp/settings/modules.py" in loaded.managed_files
        assert loaded.managed_files["myapp/settings/modules.py"].hash == "abc123"

    def test_load_state_returns_none_when_no_state_file(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)
        assert manager.load_state() is None

    def test_read_through_import_creates_module_state_from_config_only(
        self, tmp_path: Path
    ) -> None:
        """If config.yml has a module not in state.yml, import it."""
        manager = ProjectStateManager(tmp_path)

        # Write state.yml with no modules.
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
        )
        manager.save_state(state)

        # Write config.yml with a module.
        config = ModuleConfig(default_remote="https://example.com/r.git")
        config.modules["auth"] = ModuleInfo(
            prefix="modules/auth",
            branch="splits/auth-module",
            installed_version="0.62.0",
            installed_at="2025-01-01",
        )
        manager.save_config(config)

        loaded = manager.load_state()
        assert loaded is not None
        assert "auth" in loaded.modules
        assert loaded.modules["auth"].prefix == "modules/auth"


# ---------------------------------------------------------------------------
# Lazy re-export coverage (config/__init__.py and schema/__init__.py)
# ---------------------------------------------------------------------------


class TestConfigLazyReExports:
    """Exercise the lazy ``__getattr__`` in ``quickscale_core.config``."""

    def test_import_project_state_manager(self) -> None:
        from quickscale_core.config import ProjectStateManager

        assert ProjectStateManager is not None

    def test_import_managed_file_hash(self) -> None:
        from quickscale_core.config import ManagedFileHash

        assert ManagedFileHash is not None

    def test_import_managed_file_record(self) -> None:
        from quickscale_core.config import ManagedFileRecord

        assert ManagedFileRecord is not None

    def test_import_version_drift_warning(self) -> None:
        from quickscale_core.config import VersionDriftWarning

        assert VersionDriftWarning is not None

    def test_import_check_version_drift(self) -> None:
        from quickscale_core.config import check_version_drift

        assert callable(check_version_drift)

    def test_import_compute_file_hashes(self) -> None:
        from quickscale_core.config import compute_file_hashes

        assert callable(compute_file_hashes)

    def test_import_default_managed_wiring_paths(self) -> None:
        from quickscale_core.config import DEFAULT_MANAGED_WIRING_PATHS

        assert isinstance(DEFAULT_MANAGED_WIRING_PATHS, (list, tuple))

    def test_import_file_hashes_filename(self) -> None:
        from quickscale_core.config import FILE_HASHES_FILENAME

        assert isinstance(FILE_HASHES_FILENAME, str)

    def test_unknown_attribute_raises(self) -> None:
        import quickscale_core.config as cfg

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = cfg.NONEXISTENT_LAZY_EXPORT


class TestSchemaLazyReExports:
    """Exercise the lazy ``__getattr__`` in ``quickscale_core.schema``."""

    def test_import_config_delta(self) -> None:
        from quickscale_core.schema import ConfigDelta

        assert ConfigDelta is not None

    def test_import_compute_delta(self) -> None:
        from quickscale_core.schema import compute_delta

        assert callable(compute_delta)

    def test_import_format_delta(self) -> None:
        from quickscale_core.schema import format_delta

        assert callable(format_delta)

    def test_import_module_state(self) -> None:
        from quickscale_core.schema import ModuleState

        assert ModuleState is not None

    def test_import_project_state(self) -> None:
        from quickscale_core.schema import ProjectState

        assert ProjectState is not None

    def test_import_quickscale_state(self) -> None:
        from quickscale_core.schema import QuickScaleState

        assert QuickScaleState is not None

    def test_import_state_error(self) -> None:
        from quickscale_core.schema import StateError

        assert issubclass(StateError, Exception)

    def test_import_state_manager(self) -> None:
        from quickscale_core.schema import StateManager

        assert StateManager is not None

    def test_import_managed_file_record(self) -> None:
        from quickscale_core.schema import ManagedFileRecord

        assert ManagedFileRecord is not None

    def test_import_project_state_manager(self) -> None:
        from quickscale_core.schema import ProjectStateManager

        assert ProjectStateManager is not None

    def test_import_managed_file_hash(self) -> None:
        from quickscale_core.schema import ManagedFileHash

        assert ManagedFileHash is not None

    def test_import_version_drift_warning(self) -> None:
        from quickscale_core.schema import VersionDriftWarning

        assert VersionDriftWarning is not None

    def test_import_check_version_drift(self) -> None:
        from quickscale_core.schema import check_version_drift

        assert callable(check_version_drift)

    def test_import_compute_file_hashes(self) -> None:
        from quickscale_core.schema import compute_file_hashes

        assert callable(compute_file_hashes)

    def test_import_default_managed_wiring_paths(self) -> None:
        from quickscale_core.schema import DEFAULT_MANAGED_WIRING_PATHS

        assert isinstance(DEFAULT_MANAGED_WIRING_PATHS, (list, tuple))

    def test_import_file_hashes_filename(self) -> None:
        from quickscale_core.schema import FILE_HASHES_FILENAME

        assert isinstance(FILE_HASHES_FILENAME, str)

    def test_unknown_attribute_raises(self) -> None:
        import quickscale_core.schema as schema

        with pytest.raises(AttributeError, match="has no attribute"):
            _ = schema.NONEXISTENT_LAZY_EXPORT


# ---------------------------------------------------------------------------
# StateManager error-path and branch coverage
# ---------------------------------------------------------------------------


class TestStateManagerErrorPaths:
    """Cover uncovered error/validation branches in StateManager.load()."""

    def test_load_non_mapping_state_file(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text("- just\n- a\n- list\n")
        with pytest.raises(StateError, match="must be a YAML mapping"):
            manager.load()

    def test_load_project_not_mapping(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text('version: "1"\nproject: "not-a-mapping"\n')
        with pytest.raises(
            StateError, match="'project' in state file must be a mapping"
        ):
            manager.load()

    def test_load_legacy_name_schema_raises(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text('version: "1"\nproject:\n  name: myapp\n')
        with pytest.raises(StateError, match="Legacy state schema detected"):
            manager.load()

    def test_load_missing_slug_raises(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\nproject:\n  package: myapp\n  theme: showcase_react\n'
        )
        with pytest.raises(StateError, match="project.slug must be a non-empty string"):
            manager.load()

    def test_load_missing_package_raises(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\nproject:\n  slug: myapp\n  theme: showcase_react\n'
        )
        with pytest.raises(
            StateError, match="project.package must be a non-empty string"
        ):
            manager.load()

    def test_load_missing_theme_raises(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\nproject:\n  slug: myapp\n  package: myapp\n'
        )
        with pytest.raises(
            StateError, match="project.theme must be a non-empty string"
        ):
            manager.load()

    def test_load_modules_not_mapping_raises(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "modules: not-a-mapping\n"
        )
        with pytest.raises(
            StateError, match="'modules' in state file must be a mapping"
        ):
            manager.load()

    def test_load_module_entry_not_mapping_raises(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "modules:\n"
            "  auth: not-a-mapping\n"
        )
        with pytest.raises(StateError, match="state must be a mapping"):
            manager.load()

    def test_load_managed_files_as_list(self, tmp_path: Path) -> None:
        """Managed files stored as a list of dicts (save format) load correctly."""
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "managed_files:\n"
            "  - path: myapp/settings.py\n"
            "    hash: abc123\n"
            "    applied_at: '2025-01-01T10:00:00'\n"
        )
        loaded = manager.load()
        assert loaded is not None
        assert "myapp/settings.py" in loaded.managed_files
        assert loaded.managed_files["myapp/settings.py"].hash == "abc123"

    def test_load_managed_files_as_dict(self, tmp_path: Path) -> None:
        """Managed files stored as a dict keyed by path also load correctly."""
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "managed_files:\n"
            "  myapp/settings.py:\n"
            "    hash: def456\n"
            "    applied_at: '2025-01-01T10:00:00'\n"
        )
        loaded = manager.load()
        assert loaded is not None
        assert "myapp/settings.py" in loaded.managed_files
        assert loaded.managed_files["myapp/settings.py"].hash == "def456"

    def test_load_managed_files_skips_invalid_list_entries(
        self, tmp_path: Path
    ) -> None:
        """Non-dict entries in the managed_files list are silently skipped."""
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "managed_files:\n"
            "  - not-a-dict\n"
            "  - path: ok.py\n"
            "    hash: abc\n"
        )
        loaded = manager.load()
        assert loaded is not None
        assert "ok.py" in loaded.managed_files

    def test_load_managed_files_skips_invalid_dict_entries(
        self, tmp_path: Path
    ) -> None:
        """Non-dict values in the managed_files dict are silently skipped."""
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "managed_files:\n"
            "  bad_entry: not-a-dict\n"
            "  ok.py:\n"
            "    hash: abc\n"
        )
        loaded = manager.load()
        assert loaded is not None
        assert "ok.py" in loaded.managed_files

    def test_load_managed_files_skips_missing_required_keys(
        self, tmp_path: Path
    ) -> None:
        """Dict entries missing required keys (path/hash) are silently skipped."""
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(
            'version: "1"\n'
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "managed_files:\n"
            "  - hash: abc\n"  # missing path
            "  - path: ok.py\n"
            "    hash: def\n"
        )
        loaded = manager.load()
        assert loaded is not None
        assert "ok.py" in loaded.managed_files

    def test_load_invalid_yaml_raises(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        manager.state_dir.mkdir(parents=True, exist_ok=True)
        manager.state_file.write_text(":\n  invalid: [yaml\n")
        with pytest.raises(StateError, match="Failed to parse state file"):
            manager.load()


class TestStateManagerUpdateAndVerify:
    """Cover StateManager.update() and verify_filesystem() branches."""

    def test_update_refreshes_last_applied(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(
                slug="myapp",
                package="myapp",
                theme="showcase_react",
                last_applied="2020-01-01T00:00:00",
            ),
        )
        manager.save(state)
        manager.update(state)

        loaded = manager.load()
        assert loaded is not None
        assert loaded.project.last_applied != "2020-01-01T00:00:00"

    def test_verify_filesystem_no_state_file(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        result = manager.verify_filesystem()
        assert result == {"orphaned_modules": [], "missing_modules": []}

    def test_verify_filesystem_detects_orphaned_modules(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
        )
        manager.save(state)

        # Create a modules directory with an orphaned module.
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "orphaned_mod").mkdir()

        result = manager.verify_filesystem()
        assert "orphaned_mod" in result["orphaned_modules"]

    def test_verify_filesystem_detects_missing_modules(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        manager.save(state)

        # No modules directory on filesystem — auth is missing.
        result = manager.verify_filesystem()
        assert "auth" in result["missing_modules"]
        assert result["orphaned_modules"] == []

    def test_verify_filesystem_clean(self, tmp_path: Path) -> None:
        manager = StateManager(tmp_path)
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        manager.save(state)

        # Create the matching module directory.
        modules_dir = tmp_path / "modules"
        modules_dir.mkdir()
        (modules_dir / "auth").mkdir()

        result = manager.verify_filesystem()
        assert result["orphaned_modules"] == []
        assert result["missing_modules"] == []


class TestQuickScaleStateConsolidatedProperties:
    """Cover has_consolidated_managed_files and has_consolidated_modules."""

    def test_has_consolidated_managed_files_always_true(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
        )
        assert state.has_consolidated_managed_files is True

    def test_has_consolidated_modules_empty_is_true(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
        )
        assert state.has_consolidated_modules is True

    def test_has_consolidated_modules_with_tracking(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(
                    name="auth",
                    version="0.62.0",
                    prefix="modules/auth",
                    branch="splits/auth",
                    installed_at="2025-01-01",
                ),
            },
        )
        assert state.has_consolidated_modules is True

    def test_has_consolidated_modules_without_tracking(self) -> None:
        state = QuickScaleState(
            version="1",
            project=ProjectState(slug="myapp", package="myapp", theme="showcase_react"),
            modules={
                "auth": ModuleState(name="auth", version="0.62.0"),
            },
        )
        assert state.has_consolidated_modules is False


# ---------------------------------------------------------------------------
# Phase 2.3b: resolve_authoritative_project_metadata
# ---------------------------------------------------------------------------


class TestResolveAuthoritativeProjectMetadata:
    """Tests for ProjectStateManager.resolve_authoritative_project_metadata."""

    def test_returns_metadata_from_consolidated_state(self, tmp_path: Path) -> None:
        """When state.yml has consolidated sections, its project is authoritative."""
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        StateManager(tmp_path).save(
            QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp", package="myapp", theme="showcase_react"
                ),
                modules={},
            )
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.resolve_authoritative_project_metadata()
        assert result == ("myapp", "myapp", "showcase_react")

    def test_falls_back_to_quickscale_yml(self, tmp_path: Path) -> None:
        """When state.yml is absent, quickscale.yml provides project metadata."""
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.resolve_authoritative_project_metadata()
        assert result == ("myproject", "myproject", "showcase_react")

    def test_returns_none_when_no_source_available(self, tmp_path: Path) -> None:
        """Returns None when neither state.yml nor quickscale.yml exists."""
        manager = ProjectStateManager(tmp_path)
        result = manager.resolve_authoritative_project_metadata()
        assert result is None

    def test_raises_when_quickscale_yml_is_invalid(self, tmp_path: Path) -> None:
        """Raises ConfigValidationError when quickscale.yml is malformed.

        SA18.6: validation errors propagate instead of returning None,
        making invalid config distinguishable from "no project here."
        """
        (tmp_path / "quickscale.yml").write_text("- invalid\n- list\n")
        manager = ProjectStateManager(tmp_path)
        with pytest.raises(ConfigValidationError, match="must be a YAML mapping"):
            manager.resolve_authoritative_project_metadata()


# ---------------------------------------------------------------------------
# Phase 2.3b: materialize_authoritative_state
# ---------------------------------------------------------------------------


class TestMaterializeAuthoritativeState:
    """Tests for ProjectStateManager.materialize_authoritative_state."""

    def test_noop_when_already_consolidated(self, tmp_path: Path) -> None:
        """Materialization is a no-op when state.yml is already consolidated."""
        StateManager(tmp_path).save(
            QuickScaleState(
                version="1",
                project=ProjectState(
                    slug="myapp", package="myapp", theme="showcase_react"
                ),
                modules={
                    "auth": ModuleState(
                        name="auth",
                        version="0.62.0",
                        prefix="modules/auth",
                        branch="splits/auth-module",
                        installed_at="2025-01-01",
                    ),
                },
            )
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()
        assert result is not None
        assert result.project.slug == "myapp"
        assert "auth" in result.modules

    def test_materializes_from_quickscale_yml_and_legacy_config(
        self, tmp_path: Path
    ) -> None:
        """Config-only project with existing state.yml gets consolidated state.

        CR-M5-P3-006: materialization requires an existing state.yml with
        authoritative timestamps.  When state.yml exists with timestamps but
        lacks consolidated module-tracking sections, materialization merges
        legacy config.yml tracking and preserves the original timestamps.
        """
        # quickscale.yml provides project metadata.
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        # Existing state.yml with authoritative timestamps but no consolidated
        # module tracking — the pre-M2 migration scenario.  The modules section
        # has entries without prefix/branch/installed_at, so consolidated
        # sections are NOT considered present.
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
        )
        # Legacy config.yml provides module tracking.
        (quickscale_dir / "config.yml").write_text(
            "default_remote: https://github.com/Experto-AI/quickscale.git\n"
            "modules:\n"
            "  auth:\n"
            "    prefix: modules/auth\n"
            "    branch: splits/auth-module\n"
            "    installed_version: '0.62.0'\n"
            "    installed_at: '2025-01-01'\n"
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        assert result is not None
        assert result.project.slug == "myproject"
        assert result.project.package == "myproject"
        assert result.project.theme == "showcase_react"
        # Timestamps preserved from raw state.yml — not fabricated.
        assert result.project.created_at == "2024-06-15T10:30:00"
        assert result.project.last_applied == "2024-12-01T14:45:00"
        assert "auth" in result.modules
        assert result.modules["auth"].version == "0.62.0"
        assert result.modules["auth"].prefix == "modules/auth"
        assert result.modules["auth"].branch == "splits/auth-module"

        # Verify it was persisted to disk.
        assert (quickscale_dir / "state.yml").exists()
        reloaded = StateManager(tmp_path).load()
        assert reloaded is not None
        assert reloaded.project.slug == "myproject"
        assert reloaded.project.created_at == "2024-06-15T10:30:00"
        assert reloaded.project.last_applied == "2024-12-01T14:45:00"
        assert "auth" in reloaded.modules

    def test_returns_none_when_no_quickscale_yml(self, tmp_path: Path) -> None:
        """Materialization fails gracefully when no quickscale.yml exists."""
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()
        assert result is None

    def test_preserves_real_project_metadata_not_synthetic(
        self, tmp_path: Path
    ) -> None:
        """Materialization uses real project metadata from authoritative sources.

        CR-M5-P3-006: when state.yml has timestamps, its project block is
        authoritative.  This test verifies that materialized state carries
        the real metadata from state.yml, not fabricated values.
        """
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        # state.yml with timestamps and project metadata.
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: real-project\n"
            "  package: real_project\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
            "modules: {}\n"
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        assert result is not None
        assert result.project.slug == "real-project"
        assert result.project.package == "real_project"
        assert result.project.theme == "showcase_react"

    def test_preserves_authoritative_timestamp_from_existing_state(
        self, tmp_path: Path
    ) -> None:
        """CR-M5-P3-006 regression: preserve created_at/last_applied from existing state.

        When state.yml exists with real timestamps but lacks consolidated
        module-tracking sections, materialization must preserve the original
        project timestamps rather than overwriting them with datetime.now().
        """
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        # state.yml with real timestamps but missing consolidated module tracking.
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
            "modules: {}\n"
        )
        # quickscale.yml provides desired state (required for materialization).
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        assert result is not None
        # Timestamps must be preserved from the existing state.yml.
        assert result.project.created_at == "2024-06-15T10:30:00"
        assert result.project.last_applied == "2024-12-01T14:45:00"

        # Verify persistence.
        reloaded = StateManager(tmp_path).load()
        assert reloaded is not None
        assert reloaded.project.created_at == "2024-06-15T10:30:00"
        assert reloaded.project.last_applied == "2024-12-01T14:45:00"

    def test_aborts_when_no_state_yml_exists(self, tmp_path: Path) -> None:
        """CR-M5-P3-006: no state.yml means no authoritative timestamps → abort.

        Materialization must never fabricate created_at/last_applied with
        datetime.now().  When state.yml does not exist, there is no
        authoritative timestamp source, so materialization returns None.
        """
        # quickscale.yml provides project metadata.
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        # No state.yml exists.
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        # Must abort — no fabricated timestamps.
        assert result is None
        # state.yml must not have been created.
        assert not (tmp_path / ".quickscale" / "state.yml").exists()

    def test_aborts_when_state_yml_lacks_timestamps(self, tmp_path: Path) -> None:
        """CR-M5-P3-006: state.yml without created_at/last_applied → abort.

        Even when state.yml exists and is parseable, if it lacks explicit
        timestamp fields, materialization must not fabricate them.
        """
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        # state.yml exists but has no created_at or last_applied.
        # No modules section either, so consolidated sections are absent
        # and materialization proceeds to the timestamp check.
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
        )
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        # Must abort — no authoritative timestamps in raw YAML.
        assert result is None

    def test_aborts_when_state_yml_has_partial_timestamps(self, tmp_path: Path) -> None:
        """CR-M5-P3-006: state.yml with only one timestamp → abort.

        Both created_at and last_applied must be present in the raw YAML.
        A partial timestamp set is not authoritative.
        """
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        # state.yml has created_at but no last_applied.
        # No modules section, so consolidated sections are absent.
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
        )
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        # Must abort — incomplete timestamps.
        assert result is None

    # ------------------------------------------------------------------
    # CR-F12.2-001: fail-open legacy import logging + shape-invalid YAML
    # ------------------------------------------------------------------

    def test_skips_malformed_legacy_config(self, tmp_path: Path) -> None:
        """Malformed legacy config.yml is skipped (fail-open) during materialization.

        CR-F12.2-001: materialize_authoritative_state logs a warning and
        continues without legacy module tracking when config.yml is
        YAML-malformed.
        """
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
        )
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        # Malformed YAML in legacy config.yml.
        (quickscale_dir / "config.yml").write_text("invalid: [unclosed bracket\n")

        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        # Must still succeed (fail-open) with no module tracking.
        assert result is not None
        assert result.project.slug == "myproject"
        assert len(result.modules) == 0

    def test_skips_shape_invalid_legacy_config(self, tmp_path: Path) -> None:
        """Shape-invalid legacy config.yml is skipped (fail-open) during materialization.

        CR-F12.2-001: YAML that parses but lacks required config structure
        now raises ConfigError (via load_config), which is caught and
        logged by materialize_authoritative_state.
        """
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
        )
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        # Valid YAML but not a valid module config: missing default_remote.
        (quickscale_dir / "config.yml").write_text("modules: {}\n")

        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        # Must still succeed (fail-open).
        assert result is not None
        assert result.project.slug == "myproject"

    def test_skips_malformed_legacy_file_hashes(self, tmp_path: Path) -> None:
        """Malformed legacy file_hashes.yml is skipped (fail-open) during materialization.

        CR-F12.2-001: materialize_authoritative_state logs a warning and
        continues without legacy file hashes when file_hashes.yml is
        malformed.
        """
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
        )
        (tmp_path / "quickscale.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myproject\n"
            "  package: myproject\n"
            "  theme: showcase_react\n"
            "modules: {}\n"
        )
        # Malformed YAML in legacy file_hashes.yml.
        (quickscale_dir / "file_hashes.yml").write_text("invalid: [unclosed bracket\n")

        manager = ProjectStateManager(tmp_path)
        result = manager.materialize_authoritative_state()

        # Must still succeed (fail-open) with no managed files.
        assert result is not None
        assert result.project.slug == "myproject"


# ---------------------------------------------------------------------------
# Phase 2.3b: _read_raw_project_timestamps
# ---------------------------------------------------------------------------


class TestReadRawProjectTimestamps:
    """Tests for ProjectStateManager._read_raw_project_timestamps.

    CR-M5-P3-006: this helper reads timestamps directly from the raw YAML
    to bypass StateManager.load() defaults that fabricate datetime.now().
    """

    def test_returns_none_when_no_state_file(self, tmp_path: Path) -> None:
        manager = ProjectStateManager(tmp_path)
        assert manager._read_raw_project_timestamps() is None

    def test_returns_none_when_state_file_is_empty(self, tmp_path: Path) -> None:
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text("")
        manager = ProjectStateManager(tmp_path)
        assert manager._read_raw_project_timestamps() is None

    def test_returns_none_when_project_section_missing(self, tmp_path: Path) -> None:
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text("version: '1'\nmodules: {}\n")
        manager = ProjectStateManager(tmp_path)
        assert manager._read_raw_project_timestamps() is None

    def test_returns_none_when_created_at_missing(self, tmp_path: Path) -> None:
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
        )
        manager = ProjectStateManager(tmp_path)
        assert manager._read_raw_project_timestamps() is None

    def test_returns_none_when_last_applied_missing(self, tmp_path: Path) -> None:
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
        )
        manager = ProjectStateManager(tmp_path)
        assert manager._read_raw_project_timestamps() is None

    def test_returns_timestamps_when_both_present(self, tmp_path: Path) -> None:
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "  created_at: '2024-06-15T10:30:00'\n"
            "  last_applied: '2024-12-01T14:45:00'\n"
        )
        manager = ProjectStateManager(tmp_path)
        result = manager._read_raw_project_timestamps()
        assert result == ("2024-06-15T10:30:00", "2024-12-01T14:45:00")

    def test_returns_none_for_malformed_yaml(self, tmp_path: Path) -> None:
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(":\n  invalid: [yaml\n")
        manager = ProjectStateManager(tmp_path)
        assert manager._read_raw_project_timestamps() is None

    def test_returns_none_when_timestamps_are_not_strings(self, tmp_path: Path) -> None:
        """Non-string timestamp values (e.g. integers) are not authoritative."""
        quickscale_dir = tmp_path / ".quickscale"
        quickscale_dir.mkdir()
        (quickscale_dir / "state.yml").write_text(
            "version: '1'\n"
            "project:\n"
            "  slug: myapp\n"
            "  package: myapp\n"
            "  theme: showcase_react\n"
            "  created_at: 12345\n"
            "  last_applied: 67890\n"
        )
        manager = ProjectStateManager(tmp_path)
        assert manager._read_raw_project_timestamps() is None
