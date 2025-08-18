"""Unit tests for sync-back command implementation."""
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import pytest

from quickscale.commands.sync_back_command import SyncBackCommand
from quickscale.utils.error_manager import error_manager


class TestSyncBackCommand:
    """Test cases for SyncBackCommand."""

    def setup_method(self):
        """Set up test fixtures."""
        self.sync_back_cmd = SyncBackCommand()
        self.temp_dir = None

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def _create_temp_project(self) -> Path:
        """Create a temporary test project directory."""
        self.temp_dir = tempfile.mkdtemp()
        project_dir = Path(self.temp_dir) / "test_project"
        project_dir.mkdir(parents=True)
        
        # Create required project files
        (project_dir / "docker-compose.yml").write_text("services:\n  web:\n    image: test")
        (project_dir / "manage.py").write_text("#!/usr/bin/env python\nimport sys")
        
        return project_dir

    def _create_temp_templates(self) -> Path:
        """Create a temporary templates directory."""
        templates_dir = Path(self.temp_dir) / "templates"
        templates_dir.mkdir(parents=True)
        return templates_dir

    def test_detect_installation_mode_development(self):
        """Test detection of development mode installation."""
        with patch('pathlib.Path.exists') as mock_exists, \
             patch('os.access') as mock_access:
            
            # Mock .git directory exists and templates are writable
            mock_exists.return_value = True
            mock_access.return_value = True
            
            mode = self.sync_back_cmd._detect_installation_mode()
            assert mode == 'development'

    def test_detect_installation_mode_production(self):
        """Test detection of production mode installation."""
        with patch('pathlib.Path.exists') as mock_exists:
            # Mock .git directory doesn't exist
            mock_exists.return_value = False
            
            mode = self.sync_back_cmd._detect_installation_mode()
            assert mode == 'production'

    def test_validate_project_path_valid(self):
        """Test validation of valid project path."""
        project_dir = self._create_temp_project()
        
        result = self.sync_back_cmd._validate_project_path(str(project_dir))
        assert result == project_dir

    def test_validate_project_path_not_exists(self):
        """Test validation of non-existent project path."""
        with pytest.raises(error_manager.ValidationError, match="Project directory does not exist"):
            self.sync_back_cmd._validate_project_path("/non/existent/path")

    def test_validate_project_path_not_quickscale_project(self):
        """Test validation of directory that's not a QuickScale project."""
        self.temp_dir = tempfile.mkdtemp()
        project_dir = Path(self.temp_dir) / "not_quickscale"
        project_dir.mkdir(parents=True)
        
        with pytest.raises(error_manager.ValidationError, match="does not appear to be a QuickScale project"):
            self.sync_back_cmd._validate_project_path(str(project_dir))

    def test_categorize_file_safe_template(self):
        """Test categorization of safe template files."""
        file_path = Path("/project/templates/home.html")
        relative_path = Path("templates/home.html")
        
        category = self.sync_back_cmd._categorize_file(file_path, relative_path)
        assert category == 'safe'

    def test_categorize_file_safe_static(self):
        """Test categorization of safe static files."""
        file_path = Path("/project/static/css/style.css")
        relative_path = Path("static/css/style.css")
        
        category = self.sync_back_cmd._categorize_file(file_path, relative_path)
        assert category == 'safe'

    def test_categorize_file_careful_settings(self):
        """Test categorization of careful settings files."""
        file_path = Path("/project/core/settings.py")
        relative_path = Path("core/settings.py")
        
        category = self.sync_back_cmd._categorize_file(file_path, relative_path)
        assert category == 'careful'

    def test_categorize_file_never_database(self):
        """Test categorization of never-sync database files."""
        file_path = Path("/project/db.sqlite3")
        relative_path = Path("db.sqlite3")
        
        category = self.sync_back_cmd._categorize_file(file_path, relative_path)
        assert category == 'never'

    def test_categorize_file_never_migrations(self):
        """Test categorization of never-sync migration files."""
        file_path = Path("/project/app/migrations/0001_initial.py")
        relative_path = Path("app/migrations/0001_initial.py")
        
        category = self.sync_back_cmd._categorize_file(file_path, relative_path)
        assert category == 'never'

    def test_categorize_file_never_cache(self):
        """Test categorization of never-sync cache files."""
        file_path = Path("/project/__pycache__/file.pyc")
        relative_path = Path("__pycache__/file.pyc")
        
        category = self.sync_back_cmd._categorize_file(file_path, relative_path)
        assert category == 'never'

    def test_categorize_file_never_env(self):
        """Test categorization of never-sync environment files."""
        file_path = Path("/project/.env")
        relative_path = Path(".env")
        
        category = self.sync_back_cmd._categorize_file(file_path, relative_path)
        assert category == 'never'

    def test_restore_template_variables_secret_key(self):
        """Test restoration of SECRET_KEY template variable."""
        content = "SECRET_KEY = 'actual-secret-key-value'"
        file_path = Path("/project/settings.py")
        
        result = self.sync_back_cmd._restore_template_variables(content, file_path)
        assert "SECRET_KEY = '$secret_key'" in result

    def test_restore_template_variables_database_url(self):
        """Test restoration of DATABASE_URL template variable."""
        content = "DATABASE_URL = 'postgres://user:pass@host:5432/db'"
        file_path = Path("/project/settings.py")
        
        result = self.sync_back_cmd._restore_template_variables(content, file_path)
        assert "DATABASE_URL = '$database_url'" in result

    def test_restore_template_variables_project_name(self):
        """Test restoration of PROJECT_NAME template variable."""
        content = "PROJECT_NAME = 'my-actual-project'"
        file_path = Path("/project/settings.py")
        
        result = self.sync_back_cmd._restore_template_variables(content, file_path)
        assert "PROJECT_NAME = '$project_name'" in result

    def test_execute_production_mode_error(self):
        """Test execution in production mode shows error."""
        with patch.object(self.sync_back_cmd, '_detect_installation_mode', return_value='production'):
            with pytest.raises(error_manager.CommandError, match="Sync-back functionality requires development mode"):
                self.sync_back_cmd.execute("./project", preview=True)

    def test_execute_no_flags_error(self):
        """Test execution without preview, apply, or interactive flags shows error."""
        with patch.object(self.sync_back_cmd, '_detect_installation_mode', return_value='development'):
            with pytest.raises(error_manager.ValidationError, match="Must specify either --preview, --apply, or --interactive"):
                self.sync_back_cmd.execute("./project")

    def test_execute_both_flags_error(self):
        """Test execution with multiple mode flags shows error."""
        with patch.object(self.sync_back_cmd, '_detect_installation_mode', return_value='development'):
            with pytest.raises(error_manager.ValidationError, match="Cannot specify multiple modes"):
                self.sync_back_cmd.execute("./project", preview=True, apply=True)

    def test_execute_interactive_success(self):
        """Test successful interactive execution."""
        project_dir = self._create_temp_project()
        templates_dir = self._create_temp_templates()
        
        with patch.object(self.sync_back_cmd, '_detect_installation_mode', return_value='development'), \
             patch.object(self.sync_back_cmd, '_get_quickscale_templates_dir', return_value=templates_dir), \
             patch.object(self.sync_back_cmd, '_interactive_changes') as mock_interactive:
            
            self.sync_back_cmd.execute(str(project_dir), interactive=True)
            mock_interactive.assert_called_once()

    def test_execute_preview_success(self):
        """Test successful preview execution."""
        project_dir = self._create_temp_project()
        templates_dir = self._create_temp_templates()
        
        # Create some test files
        (project_dir / "templates").mkdir()
        (project_dir / "templates" / "home.html").write_text("<h1>Test</h1>")
        
        with patch.object(self.sync_back_cmd, '_detect_installation_mode', return_value='development'), \
             patch.object(self.sync_back_cmd, '_get_quickscale_templates_dir', return_value=templates_dir), \
             patch.object(self.sync_back_cmd, '_preview_changes') as mock_preview:
            
            self.sync_back_cmd.execute(str(project_dir), preview=True)
            mock_preview.assert_called_once()

    def test_execute_apply_success(self):
        """Test successful apply execution."""
        project_dir = self._create_temp_project()
        templates_dir = self._create_temp_templates()
        
        # Create some test files
        (project_dir / "templates").mkdir()
        (project_dir / "templates" / "home.html").write_text("<h1>Test</h1>")
        
        with patch.object(self.sync_back_cmd, '_detect_installation_mode', return_value='development'), \
             patch.object(self.sync_back_cmd, '_get_quickscale_templates_dir', return_value=templates_dir), \
             patch.object(self.sync_back_cmd, '_apply_changes') as mock_apply:
            
            self.sync_back_cmd.execute(str(project_dir), apply=True)
            mock_apply.assert_called_once()

    def test_scan_project_files_basic(self):
        """Test basic project file scanning."""
        project_dir = self._create_temp_project()
        templates_dir = self._create_temp_templates()
        
        # Create test files in project
        (project_dir / "templates").mkdir()
        (project_dir / "templates" / "home.html").write_text("<h1>Test</h1>")
        (project_dir / "static").mkdir()
        (project_dir / "static" / "style.css").write_text("body { color: red; }")
        (project_dir / "core").mkdir()
        (project_dir / "core" / "settings.py").write_text("SECRET_KEY = 'test'")
        (project_dir / "db.sqlite3").write_text("database")
        
        # Create corresponding template files
        (templates_dir / "templates").mkdir()
        (templates_dir / "templates" / "home.html").write_text("<h1>Original</h1>")
        
        result = self.sync_back_cmd._scan_project_files(project_dir, templates_dir)
        
        # Check that files are categorized correctly
        assert len(result['safe']) == 1  # home.html exists in both
        assert len(result['new']) == 4   # style.css, settings.py, manage.py, docker-compose.yml are new
        assert len(result['never']) == 1 # db.sqlite3 is never synced
        assert len(result['deleted']) == 0

    def test_apply_changes_safe_files(self):
        """Test applying changes for safe files."""
        project_dir = self._create_temp_project()
        templates_dir = self._create_temp_templates()
        
        # Create test file in project
        (project_dir / "templates").mkdir()
        test_file = project_dir / "templates" / "home.html"
        test_file.write_text("<h1>Updated Content</h1>")
        
        # Create template directory
        (templates_dir / "templates").mkdir()
        template_file = templates_dir / "templates" / "home.html"
        
        file_scan = {
            'safe': [(test_file, template_file)],
            'careful': [],
            'never': [],
            'new': [],
            'deleted': []
        }
        
        with patch('quickscale.utils.message_manager.MessageManager.info'), \
             patch('quickscale.utils.message_manager.MessageManager.success'):
            
            # Set the required instance variables that _apply_changes expects
            self.sync_back_cmd.project_root = project_dir
            self.sync_back_cmd.templates_root = templates_dir
            
            self.sync_back_cmd._apply_changes(file_scan)
            
            # Check that file was copied
            assert template_file.exists()
            assert template_file.read_text() == "<h1>Updated Content</h1>"

    def test_files_are_different_identical_files(self):
        """Test file comparison with identical files."""
        project_dir = self._create_temp_project()
        
        # Create identical files
        file1 = project_dir / "test1.txt"
        file2 = project_dir / "test2.txt"
        content = "This is test content\nLine 2\nLine 3"
        file1.write_text(content)
        file2.write_text(content)
        
        assert not self.sync_back_cmd._files_are_different(file1, file2)

    def test_files_are_different_different_content(self):
        """Test file comparison with different content."""
        project_dir = self._create_temp_project()
        
        # Create different files
        file1 = project_dir / "test1.txt"
        file2 = project_dir / "test2.txt"
        file1.write_text("Original content")
        file2.write_text("Modified content")
        
        assert self.sync_back_cmd._files_are_different(file1, file2)

    def test_files_are_different_missing_file(self):
        """Test file comparison with missing file."""
        project_dir = self._create_temp_project()
        
        # Create one file, leave other missing
        file1 = project_dir / "test1.txt"
        file2 = project_dir / "missing.txt"
        file1.write_text("Content")
        
        assert self.sync_back_cmd._files_are_different(file1, file2)

    def test_categorize_file_never_staticfiles(self):
        """Test that staticfiles are categorized as never sync."""
        project_dir = self._create_temp_project()
        
        # Test staticfiles directory
        staticfiles_path = project_dir / "staticfiles" / "admin" / "css" / "base.css"
        staticfiles_path.parent.mkdir(parents=True)
        staticfiles_path.write_text("/* CSS content */")
        
        relative_path = staticfiles_path.relative_to(project_dir)
        category = self.sync_back_cmd._categorize_file(staticfiles_path, relative_path)
        assert category == 'never'

    def test_categorize_file_never_media(self):
        """Test that media files are categorized as never sync."""
        project_dir = self._create_temp_project()
        
        # Test media directory
        media_path = project_dir / "media" / "uploads" / "image.jpg"
        media_path.parent.mkdir(parents=True)
        media_path.write_text("fake image content")
        
        relative_path = media_path.relative_to(project_dir)
        category = self.sync_back_cmd._categorize_file(media_path, relative_path)
        assert category == 'never'

    def test_categorize_file_never_node_modules(self):
        """Test that node_modules are categorized as never sync."""
        project_dir = self._create_temp_project()
        
        # Test node_modules directory
        node_path = project_dir / "node_modules" / "package" / "index.js"
        node_path.parent.mkdir(parents=True)
        node_path.write_text("module.exports = {};")
        
        relative_path = node_path.relative_to(project_dir)
        category = self.sync_back_cmd._categorize_file(node_path, relative_path)
        assert category == 'never'

    def test_scan_project_files_only_different_files(self):
        """Test that scanning only includes files that are actually different."""
        project_dir = self._create_temp_project()
        templates_dir = self._create_temp_templates()
        
        # Create identical files (should not be included)
        (project_dir / "identical.html").write_text("<h1>Same content</h1>")
        (templates_dir / "identical.html").write_text("<h1>Same content</h1>")
        
        # Create different files (should be included)
        (project_dir / "different.html").write_text("<h1>Modified content</h1>")
        (templates_dir / "different.html").write_text("<h1>Original content</h1>")
        
        # Create new file (should be included)
        (project_dir / "new.html").write_text("<h1>New content</h1>")
        
        file_scan = self.sync_back_cmd._scan_project_files(project_dir, templates_dir)
        
        # Only different files should be included in safe category
        safe_files = [f[0].name for f in file_scan['safe']]
        assert 'different.html' in safe_files
        assert 'identical.html' not in safe_files
        
        # New files should be in new category
        new_files = [f[0].name for f in file_scan['new']]
        assert 'new.html' in new_files
