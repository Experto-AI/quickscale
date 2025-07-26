"""Sync-back command implementation for reverse development workflow."""
import os
import re
import shutil
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import logging

from .command_base import Command
from quickscale.utils.error_manager import CommandError, ValidationError
from quickscale.utils.message_manager import MessageManager


class SyncBackCommand(Command):
    """Sync changes from generated project back to QuickScale templates."""

    def __init__(self) -> None:
        """Initialize sync-back command with logger."""
        super().__init__()
        self.logger = logging.getLogger('quickscale.sync_back')

    def _get_quickscale_root(self) -> Path:
        """Get the QuickScale root directory."""
        return Path(__file__).parent.parent.parent

    def _detect_installation_mode(self) -> str:
        """Detect if QuickScale is installed in development or production mode.
        
        Returns:
            'development' for Git clone + editable install
            'production' for pip install
        """
        quickscale_root = self._get_quickscale_root()
        
        # Check for .git directory (Git clone)
        git_dir = quickscale_root / '.git'
        has_git = git_dir.exists()
        
        # Check if templates are writable (editable install)
        templates_dir = quickscale_root / 'quickscale' / 'project_templates'
        has_writable_templates = templates_dir.exists() and os.access(templates_dir, os.W_OK)
        
        if has_git and has_writable_templates:
            return 'development'
        else:
            return 'production'

    def _validate_project_path(self, project_path: str) -> Path:
        """Validate that the provided path is a valid QuickScale project.
        
        Args:
            project_path: Path to the generated project
            
        Returns:
            Validated Path object
            
        Raises:
            ValidationError: If path is invalid or not a QuickScale project
        """
        project_dir = Path(project_path).resolve()
        
        if not project_dir.exists():
            raise ValidationError(f"Project directory does not exist: {project_dir}")
        
        if not project_dir.is_dir():
            raise ValidationError(f"Path is not a directory: {project_dir}")
        
        # Check for QuickScale project indicators
        docker_compose = project_dir / 'docker-compose.yml'
        manage_py = project_dir / 'manage.py'
        
        if not docker_compose.exists() or not manage_py.exists():
            raise ValidationError(
                f"Directory does not appear to be a QuickScale project: {project_dir}\n"
                "Expected files: docker-compose.yml, manage.py"
            )
        
        return project_dir

    def _get_quickscale_templates_dir(self) -> Path:
        """Get the QuickScale templates directory."""
        quickscale_root = self._get_quickscale_root()
        return quickscale_root / 'quickscale' / 'project_templates'

    def _categorize_file(self, file_path: Path, relative_path: Path) -> str:
        """Categorize a file based on its extension and path.
        
        Args:
            file_path: Absolute path to the file
            relative_path: Relative path from project root
            
        Returns:
            Category: 'safe', 'careful', 'never'
        """
        # Never sync extensions
        never_extensions = {'.sqlite3', '.db', '.pyc', '.pyo', '.log'}
        if file_path.suffix.lower() in never_extensions:
            return 'never'
        
        # Never sync paths  
        never_paths = {'__pycache__', 'logs', '.git', '.egg-info', 'staticfiles', 'media', 'node_modules'}
        path_parts = set(relative_path.parts)
        if any(never_part in path_parts for never_part in never_paths):
            return 'never'
        
        # Never sync patterns
        if relative_path.match('*/migrations/*.py'):
            return 'never'
        
        if relative_path.name.startswith('.env'):
            return 'never'
        
        # Careful files (need variable restoration)
        careful_files = {'settings.py', 'urls.py', 'wsgi.py', 'asgi.py', 'manage.py'}
        if file_path.name in careful_files:
            return 'careful'
        
        # Safe files (direct copy)
        safe_extensions = {
            '.html', '.css', '.js', '.svg', '.png', '.jpg', '.gif', '.ico',
            '.md', '.txt', '.json', '.yaml', '.yml'
        }
        safe_paths = {'templates', 'static', 'docs'}
        
        if (file_path.suffix.lower() in safe_extensions or 
            any(safe_part in relative_path.parts for safe_part in safe_paths)):
            return 'safe'
        
        # Default to never for unknown files
        return 'never'

    def _files_are_different(self, file1_path: Path, file2_path: Path) -> bool:
        """Compare two files to determine if they are different.
        
        Args:
            file1_path: Path to first file
            file2_path: Path to second file
            
        Returns:
            True if files are different, False if they are the same
        """
        if not file1_path.exists() or not file2_path.exists():
            return True
            
        try:
            # For text files, compare content
            with open(file1_path, 'r', encoding='utf-8', errors='ignore') as f1:
                content1 = f1.read()
            with open(file2_path, 'r', encoding='utf-8', errors='ignore') as f2:
                content2 = f2.read()
            return content1 != content2
        except (UnicodeDecodeError, PermissionError):
            # For binary files or files we can't read, compare size and modification time
            stat1 = file1_path.stat()
            stat2 = file2_path.stat()
            return stat1.st_size != stat2.st_size or abs(stat1.st_mtime - stat2.st_mtime) > 1

    def _scan_project_files(self, project_dir: Path, templates_dir: Path) -> Dict[str, List[Tuple[Path, Path]]]:
        """Scan project and template files, categorizing them.
        
        Args:
            project_dir: Project directory path
            templates_dir: Templates directory path
            
        Returns:
            Dictionary with categorized file lists
        """
        result = {
            'safe': [],
            'careful': [],
            'never': [],
            'new': [],
            'deleted': []
        }
        
        # Scan project files
        project_files = set()
        for file_path in project_dir.rglob('*'):
            if file_path.is_file():
                relative_path = file_path.relative_to(project_dir)
                project_files.add(relative_path)
                
                template_path = templates_dir / relative_path
                category = self._categorize_file(file_path, relative_path)
                
                if category == 'never':
                    result['never'].append((file_path, template_path))
                elif template_path.exists():
                    # Only include files that are actually different
                    if self._files_are_different(file_path, template_path):
                        result[category].append((file_path, template_path))
                    # If files are identical, skip them silently
                else:
                    # New file
                    result['new'].append((file_path, template_path))
        
        # Scan template files for deletions
        for template_path in templates_dir.rglob('*'):
            if template_path.is_file():
                relative_path = template_path.relative_to(templates_dir)
                if relative_path not in project_files:
                    # File exists in templates but not in project
                    project_path = project_dir / relative_path
                    category = self._categorize_file(template_path, relative_path)
                    if category != 'never':
                        result['deleted'].append((project_path, template_path))
        
        return result

    def _restore_template_variables(self, content: str, file_path: Path) -> str:
        """Restore template variables in careful files.
        
        Args:
            content: File content
            file_path: Path to the file
            
        Returns:
            Content with template variables restored
        """
        # Common template variable patterns
        replacements = [
            # SECRET_KEY restoration
            (r"SECRET_KEY\s*=\s*['\"][^'\"]+['\"]", "SECRET_KEY = '$secret_key'"),
            (r'PROJECT_NAME\s*=\s*["\'][^"\']+["\']', "PROJECT_NAME = '$project_name'"),
            (r"DATABASE_URL\s*=\s*['\"][^'\"]+['\"]", "DATABASE_URL = '$database_url'"),
            # PROJECT_NAME restoration - match various patterns
            (r"PROJECT_NAME\s*=\s*['\"][^'\"]+['\"]", "PROJECT_NAME = '$project_name'"),
        ]
        
        result = content
        for pattern, replacement in replacements:
            result = re.sub(pattern, replacement, result)
        
        return result

    def _preview_changes(self, file_scan: Dict[str, List[Tuple[Path, Path]]]) -> None:
        """Display a preview of changes that would be made.
        
        Args:
            file_scan: Categorized file scan results
        """
        MessageManager.info("📋 QuickScale Sync-Back Preview")
        MessageManager.info("=" * 31)
        MessageManager.info("")
        
        # Safe files
        if file_scan['safe']:
            MessageManager.info("✅ SAFE FILES (Direct Copy):")
            for project_path, template_path in file_scan['safe']:
                relative_path = project_path.relative_to(self.project_root)
                MessageManager.info(f"  📄 {relative_path} (modified)")
        
        # New files
        if file_scan['new']:
            for project_path, template_path in file_scan['new']:
                relative_path = project_path.relative_to(self.project_root)
                MessageManager.info(f"  🆕 {relative_path} (new file)")
        
        if file_scan['safe'] or file_scan['new']:
            MessageManager.info("")
        
        # Careful files
        if file_scan['careful']:
            MessageManager.info("⚠️  CAREFUL FILES (Variable Restoration):")
            for project_path, template_path in file_scan['careful']:
                relative_path = project_path.relative_to(self.project_root)
                MessageManager.info(f"  ⚙️  {relative_path} (modified - will restore template variables)")
            MessageManager.info("")
        
        # Never sync files
        if file_scan['never']:
            MessageManager.info("🚫 NEVER SYNC (Auto-Skip by Extension/Path):")
            count = min(5, len(file_scan['never']))  # Show max 5 examples
            for i, (project_path, _) in enumerate(file_scan['never'][:count]):
                relative_path = project_path.relative_to(self.project_root)
                MessageManager.info(f"  💾 {relative_path} (auto-skipped)")
            if len(file_scan['never']) > 5:
                MessageManager.info(f"  ... and {len(file_scan['never']) - 5} more files")
            MessageManager.info("")
        
        # Deleted files
        if file_scan['deleted']:
            MessageManager.info("🗑  DELETED FILES (Removed from project):")
            for _, template_path in file_scan['deleted']:
                relative_path = template_path.relative_to(self.templates_root)
                MessageManager.info(f"  ❌ {relative_path} (will be deleted from templates)")
            MessageManager.info("")
        
        # Summary
        safe_count = len(file_scan['safe'])
        new_count = len(file_scan['new'])
        careful_count = len(file_scan['careful'])
        never_count = len(file_scan['never'])
        deleted_count = len(file_scan['deleted'])
        
        MessageManager.info("📊 SUMMARY:")
        MessageManager.info(f"  - {safe_count + new_count} safe files to copy ({new_count} new, {safe_count} modified)")
        MessageManager.info(f"  - {careful_count} careful files with variable restoration")
        MessageManager.info(f"  - {never_count} files auto-skipped by rules")
        MessageManager.info(f"  - {deleted_count} files to delete from templates")
        MessageManager.info(f"  - 0 conflicts detected")
        MessageManager.info("")
        MessageManager.info("Run with --apply to execute these changes.")

    def _apply_changes(self, file_scan: Dict[str, List[Tuple[Path, Path]]]) -> None:
        """Apply the sync-back changes.
        
        Args:
            file_scan: Categorized file scan results
        """
        MessageManager.info("💾 Applying sync-back changes...")
        
        changes_applied = 0
        
        # Process safe files (direct copy)
        for project_path, template_path in file_scan['safe'] + file_scan['new']:
            try:
                # Ensure parent directory exists
                template_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Copy file
                shutil.copy2(project_path, template_path)
                changes_applied += 1
                
                relative_path = project_path.relative_to(self.project_root)
                self.logger.debug(f"Copied safe file: {relative_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to copy {project_path}: {e}")
                MessageManager.error(f"Failed to copy {project_path.name}: {e}")
        
        # Process careful files (with variable restoration)
        for project_path, template_path in file_scan['careful']:
            try:
                # Read project file content
                content = project_path.read_text(encoding='utf-8')
                
                # Restore template variables
                restored_content = self._restore_template_variables(content, project_path)
                
                # Ensure parent directory exists
                template_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Write to template file
                template_path.write_text(restored_content, encoding='utf-8')
                changes_applied += 1
                
                relative_path = project_path.relative_to(self.project_root)
                self.logger.debug(f"Processed careful file: {relative_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to process {project_path}: {e}")
                MessageManager.error(f"Failed to process {project_path.name}: {e}")
        
        # Process deleted files
        for _, template_path in file_scan['deleted']:
            try:
                template_path.unlink()
                changes_applied += 1
                
                relative_path = template_path.relative_to(self.templates_root)
                self.logger.debug(f"Deleted template file: {relative_path}")
                
            except Exception as e:
                self.logger.error(f"Failed to delete {template_path}: {e}")
                MessageManager.error(f"Failed to delete {template_path.name}: {e}")
        
        MessageManager.success(f"✅ Successfully applied {changes_applied} changes!")

    def execute(self, project_path: str, preview: bool = False, apply: bool = False) -> None:
        """Execute the sync-back command.
        
        Args:
            project_path: Path to the generated project
            preview: Show preview of changes
            apply: Apply changes
        """
        # Detect installation mode
        installation_mode = self._detect_installation_mode()
        
        if installation_mode == 'production':
            MessageManager.error("❌ Sync-back unavailable: QuickScale installed via pip")
            MessageManager.info("")
            MessageManager.info("To use sync-back functionality:")
            MessageManager.info("1. Clone the repository: git clone https://github.com/Experto-AI/quickscale.git")
            MessageManager.info("2. Install in development mode: cd quickscale && pip install -e .")
            MessageManager.info("3. Use sync-back: quickscale sync-back ./my-project --preview")
            MessageManager.info("")
            MessageManager.info("Alternative: Fork the repository and submit a pull request with your improvements.")
            raise CommandError("Sync-back functionality requires development mode installation")
        
        # Validate arguments
        if not preview and not apply:
            raise ValidationError("Must specify either --preview or --apply")
        
        if preview and apply:
            raise ValidationError("Cannot specify both --preview and --apply")
        
        # Validate project path
        project_dir = self._validate_project_path(project_path)
        templates_dir = self._get_quickscale_templates_dir()
        
        # Store as instance variables for use in other methods
        self.project_root = project_dir
        self.templates_root = templates_dir
        
        self.logger.info(f"Scanning project: {project_dir}")
        self.logger.info(f"Templates directory: {templates_dir}")
        
        # Scan files
        file_scan = self._scan_project_files(project_dir, templates_dir)
        
        if preview:
            self._preview_changes(file_scan)
        elif apply:
            # Create backup before applying changes
            backup_msg = "Creating backup before applying changes..."
            MessageManager.info(backup_msg)
            
            # Simple backup by creating a .bak copy of critical files
            backup_count = 0
            for project_path, template_path in file_scan['safe'] + file_scan['careful']:
                if template_path.exists():
                    backup_path = template_path.with_suffix(template_path.suffix + '.bak')
                    try:
                        shutil.copy2(template_path, backup_path)
                        backup_count += 1
                    except Exception as e:
                        self.logger.warning(f"Failed to backup {template_path}: {e}")
            
            if backup_count > 0:
                MessageManager.info(f"✅ Created {backup_count} backup files")
            
            self._apply_changes(file_scan)
