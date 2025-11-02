"""Project generator implementation"""

import os
import shutil
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from quickscale_core.utils.file_utils import (
    ensure_directory,
    validate_project_name,
    write_file,
)


class ProjectGenerator:
    """Generate Django projects from templates"""

    def __init__(self, template_dir: Path | None = None, theme: str = "showcase_html"):
        """
        Initialize generator with template directory and theme

        Args:
        ----
            template_dir: Path to template directory (auto-detected if None)
            theme: Theme name to use (default: showcase_html)

        Raises:
        ------
            ValueError: If theme is not available
            FileNotFoundError: If template directory not found

        """
        self.theme = theme

        # Validate theme
        available_themes = ["showcase_html", "showcase_htmx", "showcase_react"]
        if theme not in available_themes:
            raise ValueError(
                f"Invalid theme '{theme}'. Available themes: {', '.join(available_themes)}"
            )

        if template_dir is None:
            # Try to find templates in development environment first
            import quickscale_core

            package_dir = Path(quickscale_core.__file__).parent

            # Check if we're in development (source directory exists)
            dev_template_dir = package_dir / "generator" / "templates"
            if dev_template_dir.exists():
                template_dir = dev_template_dir
            else:
                # Fall back to package templates (should be included)
                template_dir = package_dir / "templates"

                # If package templates don't exist, try to find source templates
                # by walking up from the current file location
                if not template_dir.exists():
                    current_file = Path(__file__)
                    # Try common development layouts
                    possible_paths = [
                        current_file.parent / "templates",  # Same directory
                        current_file.parent.parent
                        / "generator"
                        / "templates",  # Parent
                        Path.cwd()
                        / "quickscale_core"
                        / "src"
                        / "quickscale_core"
                        / "generator"
                        / "templates",  # From repo root
                    ]

                    for path in possible_paths:
                        if path.exists():
                            template_dir = path
                            break

        # Validate template directory exists
        if not template_dir.exists():
            raise FileNotFoundError(f"Template directory not found: {template_dir}")

        self.template_dir = template_dir
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir), followlinks=True),
            keep_trailing_newline=True,
        )

        # Validate theme directory exists
        theme_dir = self.template_dir / "themes" / self.theme
        if not theme_dir.exists():
            raise ValueError(
                f"Theme directory not found: {theme_dir}. "
                f"Theme '{self.theme}' is not yet implemented."
            )

    def _get_theme_template_path(self, template_name: str) -> str:
        """
        Resolve template path for current theme

        Looks for template in theme-specific directory first,
        falls back to common templates.

        Args:
        ----
            template_name: Name of template file (e.g., 'base.html.j2')

        Returns:
        -------
            str: Full path to template relative to template_dir

        """
        # Check theme-specific template first
        theme_path = f"themes/{self.theme}/{template_name}"
        theme_full_path = self.template_dir / "themes" / self.theme / template_name

        if theme_full_path.exists():
            return theme_path

        # Fall back to common template
        common_path = f"common/{template_name}"
        common_full_path = self.template_dir / "common" / template_name

        if common_full_path.exists():
            return common_path

        # Fall back to root template (for backward compatibility)
        return template_name

    def generate(self, project_name: str, output_path: Path) -> None:
        """
        Generate Django project from templates

        Args:
        ----
            project_name: Name of the project (must be valid Python identifier)
            output_path: Path where project will be created

        Raises:
        ------
            ValueError: If project_name is invalid
            FileExistsError: If output_path already exists
            PermissionError: If output_path is not writable

        """
        # Validate project name
        is_valid, error_msg = validate_project_name(project_name)
        if not is_valid:
            raise ValueError(f"Invalid project name: {error_msg}")

        # Check if output path already exists
        if output_path.exists():
            raise FileExistsError(
                f"Output path already exists: {output_path}. "
                "Please choose a different name or remove the existing directory."
            )

        # Check if parent directory is writable
        parent = output_path.parent
        if not parent.exists():
            try:
                ensure_directory(parent)
            except (OSError, PermissionError) as e:
                raise PermissionError(
                    f"Cannot create parent directory {parent}: {e}"
                ) from e

        if not os.access(parent, os.W_OK):
            raise PermissionError(f"Parent directory is not writable: {parent}")

        # Generate project in temporary directory first (atomic creation)
        temp_dir = Path(tempfile.mkdtemp(prefix=f"quickscale_{project_name}_"))

        try:
            # Generate project in temp directory
            self._generate_project(project_name, temp_dir)

            # Move to final location
            shutil.move(str(temp_dir), str(output_path))

        except Exception as e:
            # Clean up temp directory on failure
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to generate project: {e}") from e

    def _generate_project(self, project_name: str, output_path: Path) -> None:
        """Generate project structure in specified directory"""
        # Context for template rendering
        context = {
            "project_name": project_name,
        }

        # Map of template files to output files
        # Format: (template_path, output_path, executable)
        file_mappings = [
            # Root level files
            ("README.md.j2", "README.md", False),
            ("manage.py.j2", "manage.py", True),
            ("pyproject.toml.j2", "pyproject.toml", False),
            ("poetry.lock.j2", "poetry.lock", False),
            (".gitignore.j2", ".gitignore", False),
            (".dockerignore.j2", ".dockerignore", False),
            (".editorconfig.j2", ".editorconfig", False),
            (".env.example.j2", ".env.example", False),
            ("Dockerfile.j2", "Dockerfile", False),
            ("docker-compose.yml.j2", "docker-compose.yml", False),
            ("railway.json.j2", "railway.json", False),
            ("start.sh.j2", "start.sh", False),
            # Project package files
            ("project_name/__init__.py.j2", f"{project_name}/__init__.py", False),
            ("project_name/urls.py.j2", f"{project_name}/urls.py", False),
            ("project_name/views.py.j2", f"{project_name}/views.py", False),
            ("project_name/wsgi.py.j2", f"{project_name}/wsgi.py", False),
            ("project_name/asgi.py.j2", f"{project_name}/asgi.py", False),
            # Settings files
            (
                "project_name/settings/__init__.py.j2",
                f"{project_name}/settings/__init__.py",
                False,
            ),
            (
                "project_name/settings/base.py.j2",
                f"{project_name}/settings/base.py",
                False,
            ),
            (
                "project_name/settings/local.py.j2",
                f"{project_name}/settings/local.py",
                False,
            ),
            (
                "project_name/settings/production.py.j2",
                f"{project_name}/settings/production.py",
                False,
            ),
            # Template files (theme-specific)
            (
                self._get_theme_template_path("templates/base.html.j2"),
                "templates/base.html",
                False,
            ),
            (
                self._get_theme_template_path("templates/index.html.j2"),
                "templates/index.html",
                False,
            ),
            (
                self._get_theme_template_path(
                    "templates/components/navigation.html.j2"
                ),
                "templates/components/navigation.html",
                False,
            ),
            # Error page templates (shared across all themes)
            ("templates/404.html.j2", "templates/404.html", False),
            ("templates/500.html.j2", "templates/500.html", False),
            # Static files (theme-specific)
            (
                self._get_theme_template_path("static/css/style.css.j2"),
                "static/css/style.css",
                False,
            ),
            (
                self._get_theme_template_path("static/images/favicon.svg.j2"),
                "static/images/favicon.svg",
                False,
            ),
            # CI/CD and quality tools
            ("github/workflows/ci.yml.j2", ".github/workflows/ci.yml", False),
            (".pre-commit-config.yaml.j2", ".pre-commit-config.yaml", False),
            # Tests
            ("tests/__init__.py.j2", "tests/__init__.py", False),
            ("tests/conftest.py.j2", "tests/conftest.py", False),
            ("tests/test_example.py.j2", "tests/test_example.py", False),
        ]

        # Render and write all files
        for template_path, output_file, executable in file_mappings:
            # Render template
            template = self.env.get_template(template_path)
            content = template.render(**context)

            # Write file
            output_file_path = output_path / output_file
            write_file(output_file_path, content, executable=executable)
