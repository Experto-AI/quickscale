"""Utility functions for template generation to maintain DRY principles."""
import os
import re
import string
from pathlib import Path
import shutil
import logging
from typing import Dict, List, Set, Optional, Any, Callable

# Define modules that should be copied directly from the source code
# rather than using static templates
SYNCED_MODULES = {
    # Format: 'source_module_path': 'target_path_in_project'
    'utils/env_utils.py': 'core/env_utils.py',
    # Add more modules to sync as needed
}

# Modules that import synced modules and need import fixes
MODULES_WITH_IMPORTS = {
    'utils/env_utils.py': [
        ('from quickscale.utils.env_utils', 'core'),
    ],
    # Add more modules and their import patterns as needed
}

# Define file patterns that should be treated as templates
# and rendered with project-specific variables
TEMPLATE_PATTERNS = [
    # Format: (glob_pattern, replace_variables_func)
    ('**/*.py', True),  
    ('**/*.md', True),
    ('**/*.html', True),
    ('**/*.yml', True),
    ('**/*.yaml', True),
    ('**/*.json', True),
    ('**/*.txt', True),
    ('**/*.ini', True),
    ('**/*.cfg', True),
    ('**/.env*', True),
]

# Binary file extensions that should never be processed as templates
BINARY_EXTENSIONS = {
    '.pyc', '.pyo', '.so', '.dll', '.exe', '.bin', 
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.ico', 
    '.pdf', '.zip', '.tar', '.gz', '.tgz', '.rar'
}

def copy_sync_modules(
    project_dir: Path, 
    quickscale_dir: Path, 
    logger: logging.Logger
) -> None:
    """Copy modules that should be synced from source to the project.
    
    Args:
        project_dir: Path to the generated project directory
        quickscale_dir: Path to the quickscale source directory
        logger: Logger instance for logging
    """
    for source_path, target_path in SYNCED_MODULES.items():
        source_file = quickscale_dir / source_path
        target_file = project_dir / target_path
        
        if source_file.exists():
            # Ensure target directory exists
            target_file.parent.mkdir(parents=True, exist_ok=True)
            
            logger.info(f"Syncing {source_path} to {target_path}")
            shutil.copy2(source_file, target_file)
        else:
            logger.warning(f"Source file {source_file} not found for syncing")

def is_binary_file(file_path: Path) -> bool:
    """Detect if a file is binary based on extension or content.
    
    Args:
        file_path: Path to the file to check
        
    Returns:
        True if file is binary, False otherwise
    """
    # Check by extension first
    if any(file_path.name.endswith(ext) for ext in BINARY_EXTENSIONS):
        return True
    
    # Check by content using UTF-8 decoding
    chunk_size = 8192
    try:
        with open(file_path, 'rb') as file:
            chunk = file.read(chunk_size)
            return b'\0' in chunk or not chunk.decode('utf-8')
    except (UnicodeDecodeError, IOError):
        return True

def render_template(content: str, variables: Dict[str, Any]) -> str:
    """Render a template string with the given variables.
    
    Args:
        content: Template content string
        variables: Dictionary of variables to replace in the template
        
    Returns:
        Rendered template string
    """
    # Use a simple replacement approach instead of string.Template
    rendered = content
    for key, value in variables.items():
        placeholder = f"${key}"
        rendered = rendered.replace(placeholder, str(value))
    return rendered

def process_file_templates(
    project_dir: Path,
    template_variables: Dict[str, Any],
    logger: logging.Logger
) -> None:
    """Process template files in the project directory.
    
    Args:
        project_dir: Path to the project directory
        template_variables: Variables to use for template rendering
        logger: Logger instance for logging
    """
    import fnmatch
    
    # Walk through all files in the project directory
    for root, _, files in os.walk(project_dir):
        for file in files:
            file_path = Path(os.path.join(root, file))
            rel_path = file_path.relative_to(project_dir)
            
            # Skip binary files
            if is_binary_file(file_path):
                continue
                
            # Check if file matches any template pattern
            should_process = any(
                fnmatch.fnmatch(str(rel_path), pattern)
                for pattern, should_render in TEMPLATE_PATTERNS
                if should_render
            )
            
            if should_process:
                try:
                    # Read the file content
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Render the template
                    rendered_content = render_template(content, template_variables)
                    
                    # Write back the rendered content
                    if rendered_content != content:
                        logger.debug(f"Rendering template: {file_path}")
                        with open(file_path, 'w', encoding='utf-8') as f:
                            f.write(rendered_content)
                except Exception as e:
                    logger.warning(f"Failed to render template {file_path}: {str(e)}")

def fix_imports(
    project_dir: Path,
    logger: logging.Logger
) -> None:
    """Fix imports in the project to use proper relative imports.
    
    Args:
        project_dir: Path to the generated project directory
        logger: Logger instance for logging
    """
    processed_files: Set[str] = set()
    
    for source_module, import_patterns in MODULES_WITH_IMPORTS.items():
        for import_pattern, target_module in import_patterns:
            target_path = project_dir / target_module
            
            # Find all Python files in the project
            for root, _, files in os.walk(project_dir):
                for file in files:
                    if not file.endswith('.py'):
                        continue
                    
                    file_path = os.path.join(root, file)
                    
                    # Skip already processed files
                    if file_path in processed_files:
                        continue
                    
                    # Skip the synced module itself
                    target_file_path = str(project_dir / SYNCED_MODULES.get(source_module, ''))
                    if target_file_path and os.path.samefile(file_path, target_file_path):
                        continue
                    
                    try:
                        with open(file_path, 'r', encoding='utf-8') as f:
                            content = f.read()
                        
                        if import_pattern in content:
                            logger.debug(f"Fixing imports in {file_path}")
                            
                            # Calculate the relative import path
                            rel_path = os.path.relpath(
                                project_dir / target_module, 
                                os.path.dirname(file_path)
                            )
                            
                            if rel_path == '.':
                                new_import = "from .env_utils"
                            else:
                                # Convert path to import format
                                rel_import = '.'.join(rel_path.split(os.sep))
                                if rel_import.startswith('.'):
                                    new_import = f"from {rel_import}.env_utils"
                                else:
                                    new_import = f"from {rel_import}.env_utils"
                            
                            # Replace the import
                            updated_content = content.replace(import_pattern, new_import)
                            
                            # Write back the file
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write(updated_content)
                            
                            processed_files.add(file_path)
                    except Exception as e:
                        logger.warning(f"Failed to fix imports in {file_path}: {str(e)}")
                        
def remove_duplicated_templates(project_dir: Path, logger: logging.Logger) -> None:
    """Remove template files that have been replaced by synced modules.
    
    Args:
        project_dir: Path to the project directory
        logger: Logger instance for logging
    """
    # Identify duplicated templates that should be removed
    for source_path, target_path in SYNCED_MODULES.items():
        # Check if there's an original template file that should be removed
        template_path = project_dir / 'templates' / target_path
        if template_path.exists() and template_path.is_file():
            logger.info(f"Removing duplicated template: {template_path}")
            template_path.unlink()
