"""Integration tests for sync-back CLI command."""
import os
import tempfile
import shutil
from pathlib import Path
from unittest.mock import patch
import pytest

from quickscale.commands.command_manager import CommandManager


class TestSyncBackCLIIntegration:
    """Integration tests for sync-back CLI command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.command_manager = CommandManager()
        self.temp_dir = None

    def teardown_method(self):
        """Clean up test fixtures."""
        if self.temp_dir and Path(self.temp_dir).exists():
            shutil.rmtree(self.temp_dir)

    def _create_test_project(self) -> Path:
        """Create a test project directory with QuickScale structure."""
        self.temp_dir = tempfile.mkdtemp()
        project_dir = Path(self.temp_dir) / "test_project"
        project_dir.mkdir(parents=True)
        
        # Create required QuickScale project files
        (project_dir / "docker-compose.yml").write_text("""
services:
  web:
    build: .
    ports:
      - "8000:8000"
  db:
    image: postgres:13
""")
        (project_dir / "manage.py").write_text("""
#!/usr/bin/env python
import os
import sys

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
""")
        
        # Create template files
        templates_dir = project_dir / "templates"
        templates_dir.mkdir(parents=True)
        (templates_dir / "base.html").write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}QuickScale{% endblock %}</title>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
""")
        
        public_templates = templates_dir / "public"
        public_templates.mkdir()
        (public_templates / "home.html").write_text("""
{% extends "base.html" %}
{% block title %}Home - QuickScale{% endblock %}
{% block content %}
<h1>Welcome to QuickScale</h1>
<p>Your SaaS starter kit is ready!</p>
{% endblock %}
""")
        
        # Create static files
        static_dir = project_dir / "static"
        static_dir.mkdir(parents=True)
        css_dir = static_dir / "css"
        css_dir.mkdir()
        (css_dir / "styles.css").write_text("""
body {
    font-family: Arial, sans-serif;
    margin: 0;
    padding: 20px;
}
h1 {
    color: #333;
}
""")
        
        # Create core settings file
        core_dir = project_dir / "core"
        core_dir.mkdir()
        (core_dir / "settings.py").write_text("""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'actual-secret-key-for-test-project'
DEBUG = True
ALLOWED_HOSTS = []

PROJECT_NAME = 'test_project'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'test_project_db',
        'USER': 'testuser',
        'PASSWORD': 'testpass123',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
""")
        
        # Create URLs file
        (core_dir / "urls.py").write_text("""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('public.urls')),
]
""")
        
        # Create some files that should never be synced
        (project_dir / "db.sqlite3").write_text("test database content")
        logs_dir = project_dir / "logs"
        logs_dir.mkdir()
        (logs_dir / "django.log").write_text("test log content")
        
        cache_dir = project_dir / "__pycache__"
        cache_dir.mkdir()
        (cache_dir / "test.pyc").write_text("compiled python")
        
        # Create .env file (should not be synced)
        (project_dir / ".env").write_text("""
SECRET_KEY=actual-secret-key-for-test
DB_PASSWORD=secretpassword
""")
        
        return project_dir

    def _create_test_templates_dir(self) -> Path:
        """Create a test QuickScale templates directory."""
        templates_dir = Path(self.temp_dir) / "quickscale_templates"
        templates_dir.mkdir(parents=True)
        
        # Create some existing template files
        existing_templates = templates_dir / "templates"
        existing_templates.mkdir(parents=True)
        (existing_templates / "base.html").write_text("""
<!DOCTYPE html>
<html>
<head>
    <title>{% block title %}$project_name{% endblock %}</title>
</head>
<body>
    {% block content %}{% endblock %}
</body>
</html>
""")
        
        # Create core directory with template settings
        core_dir = templates_dir / "core"
        core_dir.mkdir()
        (core_dir / "settings.py").write_text("""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = '$secret_key'
DEBUG = True
ALLOWED_HOSTS = []

PROJECT_NAME = '$project_name'

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]
""")
        
        return templates_dir

    def test_sync_back_preview_development_mode(self):
        """Test sync-back preview in development mode."""
        project_dir = self._create_test_project()
        templates_dir = self._create_test_templates_dir()
        
        with patch('quickscale.commands.sync_back_command.SyncBackCommand._detect_installation_mode', 
                   return_value='development'), \
             patch('quickscale.commands.sync_back_command.SyncBackCommand._get_quickscale_templates_dir', 
                   return_value=templates_dir), \
             patch('quickscale.utils.message_manager.MessageManager.info') as mock_info:
            
            # Execute sync-back preview
            self.command_manager.sync_back_project(str(project_dir), preview=True)
            
            # Check that preview was displayed
            mock_info.assert_called()
            
            # Check that some expected messages were shown
            info_messages = [call.args[0] for call in mock_info.call_args_list]
            preview_message = any("QuickScale Sync-Back Preview" in msg for msg in info_messages)
            assert preview_message, "Preview header should be displayed"

    def test_sync_back_apply_development_mode(self):
        """Test sync-back apply in development mode."""
        project_dir = self._create_test_project()
        templates_dir = self._create_test_templates_dir()
        
        with patch('quickscale.commands.sync_back_command.SyncBackCommand._detect_installation_mode', 
                   return_value='development'), \
             patch('quickscale.commands.sync_back_command.SyncBackCommand._get_quickscale_templates_dir', 
                   return_value=templates_dir), \
             patch('quickscale.utils.message_manager.MessageManager.info'), \
             patch('quickscale.utils.message_manager.MessageManager.success') as mock_success:
            
            # Execute sync-back apply
            self.command_manager.sync_back_project(str(project_dir), apply=True)
            
            # Check that success message was shown
            mock_success.assert_called()
            
            # Check that files were actually copied/updated
            # Check that new template files were created
            new_home_template = templates_dir / "templates" / "public" / "home.html"
            assert new_home_template.exists(), "New template file should be created"
            
            # Check that CSS file was copied
            new_css_file = templates_dir / "static" / "css" / "styles.css"
            assert new_css_file.exists(), "New CSS file should be created"
            
            # Check that careful files had variables restored
            settings_file = templates_dir / "core" / "settings.py"
            settings_content = settings_file.read_text()
            assert "$secret_key" in settings_content, "SECRET_KEY should be restored to template variable"
            assert "$project_name" in settings_content, "PROJECT_NAME should be restored to template variable"

    def test_sync_back_production_mode_error(self):
        """Test sync-back fails gracefully in production mode."""
        project_dir = self._create_test_project()
        
        with patch('quickscale.commands.sync_back_command.SyncBackCommand._detect_installation_mode', 
                   return_value='production'), \
             patch('quickscale.utils.message_manager.MessageManager.error') as mock_error, \
             patch('quickscale.utils.message_manager.MessageManager.info') as mock_info:
            
            # Execute sync-back and expect it to fail gracefully
            with pytest.raises(Exception):  # CommandError should be raised
                self.command_manager.sync_back_project(str(project_dir), preview=True)
            
            # Check that error message was shown
            mock_error.assert_called()
            error_message = mock_error.call_args[0][0]
            assert "unavailable" in error_message, "Should show unavailable message"
            
            # Check that help instructions were shown
            mock_info.assert_called()
            info_messages = [call.args[0] for call in mock_info.call_args_list]
            git_clone_instruction = any("git clone" in msg for msg in info_messages)
            assert git_clone_instruction, "Should show git clone instructions"

    def test_sync_back_invalid_project_path(self):
        """Test sync-back with invalid project path."""
        with patch('quickscale.commands.sync_back_command.SyncBackCommand._detect_installation_mode', 
                   return_value='development'):
            
            # Execute sync-back with non-existent path
            with pytest.raises(Exception):  # ValidationError should be raised
                self.command_manager.sync_back_project("/non/existent/path", preview=True)

    def test_sync_back_file_categorization(self):
        """Test that different file types are categorized correctly."""
        project_dir = self._create_test_project()
        templates_dir = self._create_test_templates_dir()
        
        # Add more diverse files to test categorization
        (project_dir / "docs").mkdir()
        (project_dir / "docs" / "README.md").write_text("# Test Documentation")
        
        # Add migration files (should be never synced)
        app_dir = project_dir / "myapp"
        app_dir.mkdir()
        migrations_dir = app_dir / "migrations"
        migrations_dir.mkdir()
        (migrations_dir / "0001_initial.py").write_text("# Migration file")
        
        # Add WSGI file (should be careful)
        (project_dir / "core" / "wsgi.py").write_text("""
import os
from django.core.wsgi import get_wsgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
application = get_wsgi_application()
""")
        
        with patch('quickscale.commands.sync_back_command.SyncBackCommand._detect_installation_mode', 
                   return_value='development'), \
             patch('quickscale.commands.sync_back_command.SyncBackCommand._get_quickscale_templates_dir', 
                   return_value=templates_dir), \
             patch('quickscale.utils.message_manager.MessageManager.info') as mock_info:
            
            # Execute sync-back preview to see categorization
            self.command_manager.sync_back_project(str(project_dir), preview=True)
            
            # Check that different categories are mentioned in output
            info_messages = " ".join([call.args[0] for call in mock_info.call_args_list])
            
            # Should mention safe files
            assert "SAFE FILES" in info_messages, "Should categorize safe files"
            
            # Should mention careful files
            assert "CAREFUL FILES" in info_messages, "Should categorize careful files"
            
            # Should mention never sync files
            assert "NEVER SYNC" in info_messages, "Should categorize never sync files"

    def test_sync_back_backup_creation(self):
        """Test that backups are created before applying changes."""
        project_dir = self._create_test_project()
        templates_dir = self._create_test_templates_dir()
        
        with patch('quickscale.commands.sync_back_command.SyncBackCommand._detect_installation_mode', 
                   return_value='development'), \
             patch('quickscale.commands.sync_back_command.SyncBackCommand._get_quickscale_templates_dir', 
                   return_value=templates_dir), \
             patch('quickscale.utils.message_manager.MessageManager.info') as mock_info, \
             patch('quickscale.utils.message_manager.MessageManager.success'):
            
            # Execute sync-back apply
            self.command_manager.sync_back_project(str(project_dir), apply=True)
            
            # Check that backup message was shown
            info_messages = [call.args[0] for call in mock_info.call_args_list]
            backup_message = any("backup" in msg.lower() for msg in info_messages)
            assert backup_message, "Should mention backup creation"
            
            # Check that backup files were actually created
            backup_files = list(templates_dir.rglob("*.bak"))
            assert len(backup_files) > 0, "Should create backup files"

    def test_sync_back_default_project_path(self):
        """Test that sync-back works with default project path (current directory)."""
        project_dir = self._create_test_project()
        templates_dir = self._create_test_templates_dir()
        
        # Change to the project directory to test default path behavior
        original_cwd = os.getcwd()
        try:
            os.chdir(str(project_dir))
            
            with patch('quickscale.commands.sync_back_command.SyncBackCommand._detect_installation_mode', 
                       return_value='development'), \
                 patch('quickscale.commands.sync_back_command.SyncBackCommand._get_quickscale_templates_dir', 
                       return_value=templates_dir), \
                 patch('quickscale.utils.message_manager.MessageManager.info') as mock_info, \
                 patch('quickscale.utils.message_manager.MessageManager.success'):
                
                # Execute sync-back without specifying project path (should use current directory)
                # This should not raise any errors
                self.command_manager.sync_back_project(".", preview=True)
                
                # Check that preview output was generated (indicates successful execution)
                assert mock_info.call_count > 0, "Should generate preview output"
                
                # Check that some output mentions the expected files
                info_messages = [call.args[0] for call in mock_info.call_args_list]
                preview_text = " ".join(info_messages)
                assert "SAFE FILES" in preview_text, "Should show safe files in preview"
                assert "SUMMARY" in preview_text, "Should show summary in preview"
                
        finally:
            os.chdir(original_cwd)
