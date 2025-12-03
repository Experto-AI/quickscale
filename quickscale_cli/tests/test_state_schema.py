"""Tests for QuickScale state schema and StateManager"""

import tempfile
from pathlib import Path

import pytest
import yaml

from quickscale_cli.schema.state_schema import (
    ModuleState,
    ProjectState,
    QuickScaleState,
    StateError,
    StateManager,
)


class TestModuleState:
    """Tests for ModuleState dataclass"""

    def test_module_state_creation(self):
        """Test creating a ModuleState"""
        module = ModuleState(
            name="auth",
            version="1.0.0",
            commit_sha="abc123",
            embedded_at="2025-01-01T00:00:00",
            options={"registration": True},
        )

        assert module.name == "auth"
        assert module.version == "1.0.0"
        assert module.commit_sha == "abc123"
        assert module.embedded_at == "2025-01-01T00:00:00"
        assert module.options == {"registration": True}

    def test_module_state_defaults(self):
        """Test ModuleState with default values"""
        module = ModuleState(name="auth")

        assert module.name == "auth"
        assert module.version is None
        assert module.commit_sha is None
        assert isinstance(module.embedded_at, str)
        assert module.options == {}


class TestProjectState:
    """Tests for ProjectState dataclass"""

    def test_project_state_creation(self):
        """Test creating a ProjectState"""
        project = ProjectState(
            name="myapp",
            theme="showcase_html",
            created_at="2025-01-01T00:00:00",
            last_applied="2025-01-02T00:00:00",
        )

        assert project.name == "myapp"
        assert project.theme == "showcase_html"
        assert project.created_at == "2025-01-01T00:00:00"
        assert project.last_applied == "2025-01-02T00:00:00"

    def test_project_state_defaults(self):
        """Test ProjectState with default timestamps"""
        project = ProjectState(name="myapp", theme="showcase_html")

        assert project.name == "myapp"
        assert project.theme == "showcase_html"
        assert isinstance(project.created_at, str)
        assert isinstance(project.last_applied, str)


class TestQuickScaleState:
    """Tests for QuickScaleState dataclass"""

    def test_quickscale_state_creation(self):
        """Test creating a complete QuickScaleState"""
        project = ProjectState(name="myapp", theme="showcase_html")
        auth_module = ModuleState(name="auth", version="1.0.0")

        state = QuickScaleState(
            version="1",
            project=project,
            modules={"auth": auth_module},
        )

        assert state.version == "1"
        assert state.project.name == "myapp"
        assert "auth" in state.modules
        assert state.modules["auth"].name == "auth"

    def test_quickscale_state_empty_modules(self):
        """Test QuickScaleState with no modules"""
        project = ProjectState(name="myapp", theme="showcase_html")
        state = QuickScaleState(version="1", project=project)

        assert state.version == "1"
        assert state.project.name == "myapp"
        assert state.modules == {}


class TestStateManager:
    """Tests for StateManager class"""

    def test_state_manager_initialization(self):
        """Test StateManager initialization"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            assert manager.project_path == project_path
            assert manager.state_dir == project_path / ".quickscale"
            assert manager.state_file == project_path / ".quickscale" / "state.yml"

    def test_load_nonexistent_state(self):
        """Test loading state when file doesn't exist"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(Path(tmpdir))
            state = manager.load()

            assert state is None

    def test_save_and_load_state(self):
        """Test saving and loading state"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            # Create state
            project = ProjectState(
                name="myapp",
                theme="showcase_html",
                created_at="2025-01-01T00:00:00",
                last_applied="2025-01-01T00:00:00",
            )
            auth_module = ModuleState(
                name="auth",
                version="1.0.0",
                commit_sha="abc123",
                embedded_at="2025-01-01T00:00:00",
                options={"registration": True},
            )
            state = QuickScaleState(
                version="1",
                project=project,
                modules={"auth": auth_module},
            )

            # Save state
            manager.save(state)

            # Verify file exists
            assert manager.state_file.exists()

            # Load state
            loaded_state = manager.load()

            assert loaded_state is not None
            assert loaded_state.version == "1"
            assert loaded_state.project.name == "myapp"
            assert loaded_state.project.theme == "showcase_html"
            assert "auth" in loaded_state.modules
            assert loaded_state.modules["auth"].name == "auth"
            assert loaded_state.modules["auth"].version == "1.0.0"
            assert loaded_state.modules["auth"].options == {"registration": True}

    def test_save_state_atomic(self):
        """Test that state saving is atomic (uses temporary file)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            project = ProjectState(name="myapp", theme="showcase_html")
            state = QuickScaleState(version="1", project=project)

            manager.save(state)

            # Verify no .tmp file left behind
            tmp_files = list(project_path.glob("**/*.tmp"))
            assert len(tmp_files) == 0

    def test_update_state(self):
        """Test updating state with new timestamp"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(Path(tmpdir))

            project = ProjectState(
                name="myapp",
                theme="showcase_html",
                created_at="2025-01-01T00:00:00",
                last_applied="2025-01-01T00:00:00",
            )
            state = QuickScaleState(version="1", project=project)

            # Save initial state
            manager.save(state)

            # Update state
            manager.update(state)

            # Load and verify last_applied was updated
            loaded_state = manager.load()
            assert loaded_state is not None
            assert loaded_state.project.last_applied != "2025-01-01T00:00:00"

    def test_load_invalid_yaml(self):
        """Test loading state with invalid YAML"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            # Create invalid YAML file
            manager.state_dir.mkdir(parents=True, exist_ok=True)
            with open(manager.state_file, "w") as f:
                f.write("invalid: [unclosed")

            with pytest.raises(StateError, match="Failed to parse state file"):
                manager.load()

    def test_load_invalid_structure(self):
        """Test loading state with invalid structure"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            # Create state file with invalid structure
            manager.state_dir.mkdir(parents=True, exist_ok=True)
            with open(manager.state_file, "w") as f:
                yaml.dump("not a dict", f)

            with pytest.raises(StateError, match="State file must be a YAML mapping"):
                manager.load()

    def test_verify_filesystem_no_state(self):
        """Test filesystem verification when no state exists"""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = StateManager(Path(tmpdir))
            drift = manager.verify_filesystem()

            assert drift["orphaned_modules"] == []
            assert drift["missing_modules"] == []

    def test_verify_filesystem_orphaned_modules(self):
        """Test detection of orphaned modules (in filesystem but not in state)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            # Create state without auth module
            project = ProjectState(name="myapp", theme="showcase_html")
            state = QuickScaleState(version="1", project=project, modules={})
            manager.save(state)

            # Create auth module in filesystem
            modules_dir = project_path / "modules" / "auth"
            modules_dir.mkdir(parents=True)

            # Verify drift
            drift = manager.verify_filesystem()
            assert "auth" in drift["orphaned_modules"]
            assert drift["missing_modules"] == []

    def test_verify_filesystem_missing_modules(self):
        """Test detection of missing modules (in state but not in filesystem)"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            # Create state with auth module
            project = ProjectState(name="myapp", theme="showcase_html")
            auth_module = ModuleState(name="auth")
            state = QuickScaleState(
                version="1", project=project, modules={"auth": auth_module}
            )
            manager.save(state)

            # Don't create auth module in filesystem

            # Verify drift
            drift = manager.verify_filesystem()
            assert drift["orphaned_modules"] == []
            assert "auth" in drift["missing_modules"]

    def test_verify_filesystem_consistent(self):
        """Test filesystem verification when state matches filesystem"""
        with tempfile.TemporaryDirectory() as tmpdir:
            project_path = Path(tmpdir)
            manager = StateManager(project_path)

            # Create state with auth module
            project = ProjectState(name="myapp", theme="showcase_html")
            auth_module = ModuleState(name="auth")
            state = QuickScaleState(
                version="1", project=project, modules={"auth": auth_module}
            )
            manager.save(state)

            # Create auth module in filesystem
            modules_dir = project_path / "modules" / "auth"
            modules_dir.mkdir(parents=True)

            # Verify no drift
            drift = manager.verify_filesystem()
            assert drift["orphaned_modules"] == []
            assert drift["missing_modules"] == []
