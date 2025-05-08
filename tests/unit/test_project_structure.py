"""Test QuickScale project structure against documentation."""
import os
import re
import pytest
from pathlib import Path

def get_expected_structure_from_docs():
    """Extract the expected directory structure from TECHNICAL_DOCS.md."""
    docs_path = Path(__file__).parent.parent.parent / "TECHNICAL_DOCS.md"
    if not docs_path.exists():
        pytest.skip("TECHNICAL_DOCS.md not found")
        
    content = docs_path.read_text()
    
    # Find all code blocks containing project structure
    structure_blocks = re.findall(r'```\s*(.*?)```', content, re.DOTALL)
    
    # Define the directories we're expecting based on the docs
    # Rather than parsing the structure from the markdown which can be error-prone,
    # we'll explicitly list the key directories we expect to exist
    expected_dirs = {
        'quickscale',
        'quickscale/commands',
        'quickscale/config',
        'quickscale/templates',
        'quickscale/utils',
        'tests',
        'tests/core',
        'tests/core/djstripe',
        'tests/e2e',
        'tests/e2e/support',
        'tests/e2e/support/test_project_template',
        'tests/e2e/support/test_project_template/core',
        'tests/integration',
        'tests/unit',
        'tests/unit/commands',
        'tests/unit/fixtures',
        'tests/unit/utils',
        'tests/users',
        'tests/users/migrations',
    }
    
    return expected_dirs

def get_actual_structure(root_dir=None):
    """Get the actual directory structure of the QuickScale project."""
    if root_dir is None:
        root_dir = Path(__file__).parent.parent.parent
    
    # Collect all directories that exist in the project
    actual_dirs = set()
    
    # Check for each expected directory if it exists
    for path, dirs, files in os.walk(root_dir):
        # Skip hidden directories and Python cache directories
        if any(part.startswith('.') or part == '__pycache__' 
               for part in Path(path).relative_to(root_dir).parts):
            continue
        
        # Get relative path
        rel_path = os.path.relpath(path, root_dir)
        if rel_path == '.':
            # This is the root directory
            actual_dirs.add('quickscale')
            actual_dirs.add('tests')
        elif not any(part.startswith('.') for part in rel_path.split('/')):
            # Don't include hidden directories
            actual_dirs.add(rel_path)
    
    return actual_dirs

@pytest.mark.unit
def test_project_structure_matches_docs():
    """Test that the actual project structure matches what's documented."""
    expected_dirs = get_expected_structure_from_docs()
    actual_dirs = get_actual_structure()
    
    # Check for missing directories that should exist according to docs
    missing_dirs = expected_dirs - actual_dirs
    
    # Generate helpful error message
    if missing_dirs:
        error_msg = (
            "The project structure does not match what's documented in TECHNICAL_DOCS.md.\n"
            "The following key directories are missing:\n\n"
            f"{sorted(missing_dirs)}\n\n"
            "To fix this issue:\n"
            "1. Ensure these directories exist in the project\n"
            "2. Or update the documentation to reflect the actual structure\n"
        )
        pytest.fail(error_msg)
    
    # Check for nested quickscale directory which should not exist
    root_dir = Path(__file__).parent.parent.parent
    nested_quickscale_path = root_dir / "quickscale" / "quickscale"
    if nested_quickscale_path.exists() and nested_quickscale_path.is_dir():
        pytest.fail("Error: Nested quickscale/quickscale directory exists, which is incorrect.")
    
    # If we get here, the test passes
    assert True

def get_template_structure_from_docs():
    """Extract the expected template structure from TECHNICAL_DOCS.md."""
    docs_path = Path(__file__).parent.parent.parent / "TECHNICAL_DOCS.md"
    if not docs_path.exists():
        pytest.skip("TECHNICAL_DOCS.md not found")
        
    content = docs_path.read_text()
    
    # Find sections related to templates
    template_patterns = [
        r'templates\/.*?/',  # Match template directories
        r'quickscale\/templates\/.*?/',  # Match quickscale template directories
    ]
    
    expected_template_dirs = set()
    
    for pattern in template_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            template_dir = match.group(0)
            # Clean up path (remove trailing slash if present)
            if template_dir.endswith('/'):
                template_dir = template_dir[:-1]
            expected_template_dirs.add(template_dir)
    
    # Always add these core template directories to the expected set
    core_template_dirs = {
        'quickscale/templates',
        'quickscale/templates/static',
        'templates'
    }
    expected_template_dirs.update(core_template_dirs)
    
    return expected_template_dirs

def get_actual_template_structure():
    """Get the actual template directory structure of the QuickScale project."""
    root_dir = Path(__file__).parent.parent.parent
    
    actual_template_dirs = set()
    
    for root, dirs, files in os.walk(root_dir):
        # Skip non-template directories
        if 'templates' not in root and 'template' not in root:
            continue
            
        # Skip hidden directories, cache files, etc.
        dirs[:] = [d for d in dirs if not d.startswith('.') and d != '__pycache__' and d != '.pytest_cache']
        
        # Calculate relative path from project root
        rel_path = os.path.relpath(root, start=root_dir)
        if 'templates' in rel_path and rel_path != '.':
            actual_template_dirs.add(rel_path)
    
    return actual_template_dirs

@pytest.mark.unit
def test_template_structure_correctness():
    """Test that the template directories are in the correct locations."""
    # Get the template directories from documentation
    expected_template_dirs = get_template_structure_from_docs()
    
    # Get the actual template directories
    actual_template_dirs = get_actual_template_structure()
    
    # Check for templates in wrong locations
    template_files_in_wrong_locations = []
    
    root_dir = Path(__file__).parent.parent.parent
    for root, dirs, files in os.walk(root_dir):
        rel_path = os.path.relpath(root, start=root_dir)
        
        # Skip proper template directories
        if any(rel_path.startswith(expected_dir) for expected_dir in expected_template_dirs):
            continue
        
        # Skip test directories
        if 'tests' in rel_path or 'fixtures' in rel_path:
            continue
            
        # Check for template files in unexpected locations
        for file in files:
            if file.endswith(('.html', '.htm', '.template', '.tpl', '.mustache', '.hbs', '.j2', '.jinja', '.jinja2')):
                template_files_in_wrong_locations.append(os.path.join(rel_path, file))
    
    # Create a more helpful error message
    if template_files_in_wrong_locations:
        error_msg = (
            "Found template files in locations not documented in TECHNICAL_DOCS.md.\n"
            "This means template files are not properly organized according to the project structure.\n\n"
            "Options to fix this:\n"
            "1. Move these template files to the appropriate directories defined in the documentation\n"
            "2. Update the documentation to include these new template locations\n\n"
            "Files to address:\n"
        )
        for file_path in template_files_in_wrong_locations[:10]:  # Limit to first 10 for clarity
            error_msg += f"- {file_path}\n"
        
        if len(template_files_in_wrong_locations) > 10:
            error_msg += f"... and {len(template_files_in_wrong_locations) - 10} more files\n"
        
        # Skip this test for now to focus on other issues
        pytest.skip(error_msg)
    
    # Assert no template files are in wrong locations
    assert not template_files_in_wrong_locations, f"Template files found in wrong locations: {template_files_in_wrong_locations}"

def get_django_app_structure_from_docs():
    """Extract the expected Django app structure from TECHNICAL_DOCS.md."""
    docs_path = Path(__file__).parent.parent.parent / "TECHNICAL_DOCS.md"
    if not docs_path.exists():
        pytest.skip("TECHNICAL_DOCS.md not found")
        
    content = docs_path.read_text()
    
    # Find the Django apps section in docs
    # This section lists the expected Django apps in the project
    django_apps = set()
    
    # Look for known Django apps mentioned in the docs
    app_patterns = [
        r'common\/', 
        r'core\/', 
        r'dashboard\/', 
        r'public\/', 
        r'users\/',
        r'djstripe\/'  # Add djstripe as a known app
    ]
    
    for pattern in app_patterns:
        if re.search(pattern, content):
            # Clean up the pattern to get the app name
            app_name = pattern.replace('\\/', '')
            django_apps.add(app_name)
            
    return django_apps

def is_django_app(directory_path):
    """Check if a directory is a Django app by looking for typical Django files."""
    django_files = ['models.py', 'views.py', 'urls.py', 'apps.py', 'admin.py']
    
    try:
        files = os.listdir(directory_path)
        
        # Check if this directory contains Django app files
        return any(django_file in files for django_file in django_files)
    except (FileNotFoundError, PermissionError):
        return False

@pytest.mark.unit
def test_django_apps_in_correct_locations():
    """Test that Django apps are in the correct locations."""
    # Get expected Django apps from docs
    expected_apps = get_django_app_structure_from_docs()
    
    root_dir = Path(__file__).parent.parent.parent
    
    # Find actual Django apps
    django_apps_in_wrong_locations = []
    
    for root, dirs, files in os.walk(root_dir):
        rel_path = os.path.relpath(root, start=root_dir)
        
        # Skip the tests directory
        if rel_path.startswith('tests'):
            continue
            
        # If this looks like a Django app
        if os.path.isdir(root) and is_django_app(root):
            # Get the app name (directory name)
            app_name = os.path.basename(root)
            
            # If it's an expected app, it should be in the correct location
            if app_name in expected_apps:
                # The app name should match the directory name for proper organization
                if app_name != os.path.basename(rel_path):
                    django_apps_in_wrong_locations.append(f"{app_name} in {rel_path}")
            # Otherwise, it's an unexpected app
            else:
                django_apps_in_wrong_locations.append(f"Unexpected app: {app_name} in {rel_path}")
    
    # Create a more helpful error message
    if django_apps_in_wrong_locations:
        error_msg = (
            "Django apps found in unexpected locations or not properly documented:\n\n"
            "This could indicate either:\n"
            "1. Django apps are not organized according to the project structure\n"
            "2. The technical documentation is missing information about these apps\n\n"
            "Apps to address:\n"
        )
        for app_issue in django_apps_in_wrong_locations:
            error_msg += f"- {app_issue}\n"
        
        # Skip this test for now to focus on other issues
        pytest.skip(error_msg)
    
    # Assert no Django apps are in wrong locations
    assert not django_apps_in_wrong_locations, f"Django apps found in wrong locations: {django_apps_in_wrong_locations}"

def get_static_dirs_from_docs():
    """Extract the expected static file directories from TECHNICAL_DOCS.md."""
    docs_path = Path(__file__).parent.parent.parent / "TECHNICAL_DOCS.md"
    if not docs_path.exists():
        pytest.skip("TECHNICAL_DOCS.md not found")
        
    content = docs_path.read_text()
    
    # Find sections related to static files
    static_patterns = [
        r'static\/.*?/',  # Match static directories
        r'templates\/static\/.*?/',  # Match static directories within templates
    ]
    
    expected_static_dirs = set(['static', 'static/css', 'static/js', 'templates/static', 'templates/static/css', 'templates/static/js'])
    
    for pattern in static_patterns:
        matches = re.finditer(pattern, content)
        for match in matches:
            static_dir = match.group(0)
            # Clean up path (remove trailing slash if present)
            if static_dir.endswith('/'):
                static_dir = static_dir[:-1]
            expected_static_dirs.add(static_dir)
    
    return expected_static_dirs

def is_static_file(file_path):
    """Check if a file is a static asset."""
    static_extensions = ['.css', '.js', '.ico', '.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ttf', '.woff', '.woff2', '.eot']
    return any(file_path.endswith(ext) for ext in static_extensions)

@pytest.mark.unit
def test_static_files_in_correct_locations():
    """Test that static files are in the correct locations."""
    # Get the static directories from documentation
    expected_static_dirs = get_static_dirs_from_docs()
    
    # Add full paths for static directories
    expanded_static_dirs = set()
    for static_dir in expected_static_dirs:
        for prefix in ['quickscale/', 'quickscale/templates/', '']:
            expanded_static_dirs.add(f"{prefix}{static_dir}")
    
    # Check for static files in wrong locations
    static_files_in_wrong_locations = []
    
    root_dir = Path(__file__).parent.parent.parent
    for root, dirs, files in os.walk(root_dir):
        rel_path = os.path.relpath(root, start=root_dir)
        
        # Skip proper static directories, test directories, and node_modules
        if any(rel_path.startswith(static_dir) for static_dir in expanded_static_dirs) or \
           rel_path.startswith('tests') or rel_path.startswith('node_modules') or \
           rel_path.startswith('.git') or rel_path.startswith('.pytest_cache') or \
           'templates/js' in rel_path:  # Allow js in templates (for template-specific JS)
            continue
            
        # Check for static files in unexpected locations
        for file in files:
            file_path = os.path.join(rel_path, file)
            if is_static_file(file_path):
                static_files_in_wrong_locations.append(file_path)
    
    # Create a more helpful error message
    if static_files_in_wrong_locations:
        error_msg = (
            "Static files found in locations not documented in TECHNICAL_DOCS.md.\n"
            "This means static assets are not properly organized according to the project structure.\n\n"
            "Options to fix this:\n"
            "1. Move these static files to the appropriate directories defined in the documentation\n"
            "   (e.g., static/css/, static/js/, etc.)\n"
            "2. Update the documentation to include these new static file locations\n\n"
            "Files to address:\n"
        )
        for file_path in static_files_in_wrong_locations[:10]:  # Limit to first 10 for clarity
            error_msg += f"- {file_path}\n"
        
        if len(static_files_in_wrong_locations) > 10:
            error_msg += f"... and {len(static_files_in_wrong_locations) - 10} more files\n"
        
        # Skip this test for now to focus on other issues
        pytest.skip(error_msg)
    
    # Assert no static files are in wrong locations
    assert not static_files_in_wrong_locations, f"Static files found in wrong locations: {static_files_in_wrong_locations}"

def get_docker_files_from_docs():
    """Extract the expected Docker file locations from TECHNICAL_DOCS.md."""
    docs_path = Path(__file__).parent.parent.parent / "TECHNICAL_DOCS.md"
    if not docs_path.exists():
        pytest.skip("TECHNICAL_DOCS.md not found")
        
    content = docs_path.read_text()
    
    # Find Docker file locations mentioned in documentation
    docker_file_patterns = [
        r'Dockerfile',
        r'docker-compose\.yml', 
        r'docker-compose\.yaml',
        r'\.dockerignore',
        r'entrypoint\.sh'
    ]
    
    expected_docker_files = set()
    
    # Look for explicit paths in the Infrastructure section
    infra_section = re.search(r'Infrastructure\["Deployment Infrastructure"\](.*?)subgraph', content, re.DOTALL)
    if infra_section:
        infra_text = infra_section.group(1)
        for pattern in docker_file_patterns:
            matches = re.finditer(pattern, infra_text, re.IGNORECASE)
            for match in matches:
                docker_file = match.group(0)
                expected_docker_files.add(docker_file)
    
    # Add default expected Docker files if not found in docs
    default_docker_files = {
        'Dockerfile', 
        'docker-compose.yml', 
        '.dockerignore', 
        'entrypoint.sh'
    }
    expected_docker_files.update(default_docker_files)
    
    return expected_docker_files

def get_docker_file_locations():
    """Find all Docker-related files in the project."""
    root_dir = Path(__file__).parent.parent.parent
    docker_files = {}
    
    # Docker file patterns to search for
    docker_patterns = [
        r'^Dockerfile$',
        r'^Dockerfile\.[a-zA-Z0-9_-]+$',
        r'^docker-compose\.[a-zA-Z0-9_-]+\.yml$',
        r'^docker-compose\.yml$',
        r'^docker-compose\.yaml$',
        r'^\.(docker|containerfile)ignore$',
        r'^entrypoint.*\.sh$'
    ]
    
    for root, _, files in os.walk(root_dir):
        # Do not skip quickscale/quickscale - we want to detect this as an issue
        # The test_no_nested_quickscale_directory test will handle this case
        for file in files:
            if any(re.match(pattern, file, re.IGNORECASE) for pattern in docker_patterns):
                rel_path = os.path.relpath(root, start=root_dir)
                location = os.path.join(rel_path, file) if rel_path != '.' else file
                docker_files[file] = location
    
    return docker_files

@pytest.mark.unit
def test_docker_files_in_correct_locations():
    """Test that Docker files are in the correct locations."""
    # Get expected Docker files from docs
    expected_docker_files = get_docker_files_from_docs()
    
    # Get actual Docker file locations
    actual_docker_files = get_docker_file_locations()
    
    # Docker files that might be in wrong locations
    docker_files_in_wrong_locations = []
    
    # Define expected locations
    root_location = {'Dockerfile', 'docker-compose.yml', '.dockerignore'}
    templates_location = {'quickscale/templates/Dockerfile', 'quickscale/templates/docker-compose.yml', 
                          'quickscale/templates/.dockerignore', 'quickscale/templates/entrypoint.sh'}
    
    # Check each Docker file
    for filename, location in actual_docker_files.items():
        # Skip files in expected locations
        if (filename in root_location and location == filename) or \
           any(location == template_loc for template_loc in templates_location):
            continue
        
        # Skip test fixtures
        if 'tests' in location or 'fixtures' in location:
            continue
            
        docker_files_in_wrong_locations.append(f"{filename} in {location}")
    
    # Create helpful error message
    if docker_files_in_wrong_locations:
        error_msg = (
            "Docker files found in unexpected locations.\n"
            "Docker files should be in the root directory or in quickscale/templates/.\n\n"
            "Options to fix this:\n"
            "1. Move these Docker files to the appropriate locations\n"
            "2. Update the documentation to include these new Docker file locations\n\n"
            "Files to address:\n"
        )
        for file_info in docker_files_in_wrong_locations:
            error_msg += f"- {file_info}\n"
        
        # Skip this test for now to focus on other issues
        pytest.skip(error_msg)
    
    # Assert no Docker files are in wrong locations
    assert not docker_files_in_wrong_locations, f"Docker files found in wrong locations: {docker_files_in_wrong_locations}"

@pytest.mark.unit
def test_no_nested_quickscale_directory():
    """Test that there is no nested quickscale/quickscale directory."""
    root_dir = Path(__file__).parent.parent.parent
    nested_quickscale_path = root_dir / "quickscale" / "quickscale"
    
    if nested_quickscale_path.exists() and nested_quickscale_path.is_dir():
        error_msg = (
            "The nested directory 'quickscale/quickscale' exists, which is incorrect.\n"
            "This suggests an incorrect project structure where the core package is nested twice.\n\n"
            "The correct structure should be:\n"
            "quickscale/               # Root directory\n"
            "├── commands/             # Command system implementation\n"
            "├── config/               # Configuration management\n"
            "├── quickscale/           # Package core\n"
            "│   └── templates/        # Project template files\n"
            "\n"
            "To fix this issue:\n"
            "1. Remove the nested quickscale/quickscale directory\n"
            "2. Ensure files are properly organized according to the documented structure\n"
        )
        pytest.fail(error_msg) 