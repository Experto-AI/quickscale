"""Project generator implementation"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from quickscale_core.utils.file_utils import (
    ensure_directory,
    validate_project_name,
    write_file,
)


# Map of optional React theme source files to the module key that gates them.
# When ``selected_modules`` is provided and the gating module is not selected,
# the generator skips rendering the file entirely. When ``selected_modules`` is
# ``None``, the file is always rendered to preserve the default behavior.
REACT_THEME_OPTIONAL_FILES: dict[str, str] = {
    "src/pages/BlogPage.tsx": "blog",
    "src/pages/CrmPage.tsx": "crm",
    "src/pages/FormsPage.tsx": "forms",
    "src/pages/ListingsPage.tsx": "listings",
    "src/components/forms/FormRenderer.tsx": "forms",
    "src/components/forms/FormFieldRenderer.tsx": "forms",
    "src/components/forms/FormSuccess.tsx": "forms",
    "src/hooks/useFormSchema.ts": "forms",
    "src/pages/SocialLinkTreePublicPage.tsx": "social",
    "src/pages/SocialEmbedsPublicPage.tsx": "social",
}

# React theme Django-side templates that should be rendered from the shared
# ``templates/`` location when the theme-specific copy is absent.
REACT_THEME_SHARED_DJANGO_TEMPLATES: tuple[str, ...] = (
    "templates/admin/index.html.j2",
    "templates/admin/app_index.html.j2",
)


class ProjectGenerator:
    """Generate Django projects from templates"""

    def __init__(
        self,
        template_dir: Path | None = None,
        theme: str = "showcase_react",
        selected_modules: list[str] | None = None,
    ):
        """
        Initialize generator with template directory and theme

        Args:
        ----
            template_dir: Path to template directory (auto-detected if None)
            theme: Theme name to use (default: showcase_react)
            selected_modules: Optional list of module names that the user
                selected. When provided, the React theme generator uses it to
                gate optional per-module React components and TypeScript
                interface entries. When ``None`` (default), the generator
                preserves the legacy behavior of emitting every per-module
                surface.

        Raises:
        ------
            ValueError: If theme is not available
            FileNotFoundError: If template directory not found

        """
        self.theme = theme
        self.selected_modules = (
            list(selected_modules) if selected_modules is not None else None
        )

        # Validate theme
        available_themes = ["showcase_html", "showcase_react"]
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

    def generate(
        self,
        project_slug: str,
        output_path: Path,
        package_name: str | None = None,
    ) -> None:
        """
        Generate Django project from templates

        Args:
        ----
            project_slug: Filesystem/service slug for the project
            output_path: Path where project will be created
            package_name: Optional explicit Python package name. If omitted,
                defaults to project_slug with hyphens replaced by underscores.

        Raises:
        ------
            ValueError: If project_name is invalid
            FileExistsError: If output_path already exists
            PermissionError: If output_path is not writable

        """
        # Validate project name
        is_valid, error_msg = validate_project_name(project_slug)
        if not is_valid:
            raise ValueError(f"Invalid project name: {error_msg}")

        if package_name is None:
            package_name = project_slug.replace("-", "_")

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
        temp_dir = Path(tempfile.mkdtemp(prefix=f"quickscale_{project_slug}_"))

        try:
            # Generate project in temp directory
            self._generate_project(project_slug, package_name, temp_dir)

            # Move to final location
            shutil.move(str(temp_dir), str(output_path))

        except Exception as e:
            # Clean up temp directory on failure
            if temp_dir.exists():
                shutil.rmtree(temp_dir, ignore_errors=True)
            raise RuntimeError(f"Failed to generate project: {e}") from e

    def _generate_project(
        self,
        project_slug: str,
        package_name: str,
        output_path: Path,
    ) -> None:
        """Generate project structure in specified directory"""
        # Context for template rendering
        context = {
            "project_name": project_slug,
            "package_name": package_name,
            "theme": self.theme,
            "host_uid": os.getuid() if hasattr(os, "getuid") else 1000,
            "host_gid": os.getgid() if hasattr(os, "getgid") else 1000,
            "selected_modules": list(self.selected_modules)
            if self.selected_modules is not None
            else None,
        }

        # Map of template files to output files
        # Format: (template_path, output_path, executable)
        file_mappings = [
            # Root level files
            ("Makefile.j2", "Makefile", False),
            ("README.md.j2", "README.md", False),
            ("manage.py.j2", "manage.py", True),
            ("pyproject.toml.j2", "pyproject.toml", False),
            # poetry.lock is generated dynamically via `poetry lock` below
            (".gitignore.j2", ".gitignore", False),
            (".dockerignore.j2", ".dockerignore", False),
            (".editorconfig.j2", ".editorconfig", False),
            (".env.example.j2", ".env.example", False),
            (".env.j2", ".env", False),
            ("Dockerfile.j2", "Dockerfile", False),
            ("docker-compose.yml.j2", "docker-compose.yml", False),
            ("railway.json.j2", "railway.json", False),
            ("start.sh.j2", "start.sh", False),
            ("scripts/lint.sh.j2", "scripts/lint.sh", True),
            # Project package files
            ("project_name/__init__.py.j2", f"{package_name}/__init__.py", False),
            ("project_name/urls.py.j2", f"{package_name}/urls.py", False),
            (
                "project_name/urls_modules.py.j2",
                f"{package_name}/urls_modules.py",
                False,
            ),
            ("project_name/views.py.j2", f"{package_name}/views.py", False),
            ("project_name/wsgi.py.j2", f"{package_name}/wsgi.py", False),
            ("project_name/asgi.py.j2", f"{package_name}/asgi.py", False),
            (
                "project_name/context_processors.py.j2",
                f"{package_name}/context_processors.py",
                False,
            ),
            # Settings files
            (
                "project_name/settings/__init__.py.j2",
                f"{package_name}/settings/__init__.py",
                False,
            ),
            (
                "project_name/settings/base.py.j2",
                f"{package_name}/settings/base.py",
                False,
            ),
            (
                "project_name/settings/modules.py.j2",
                f"{package_name}/settings/modules.py",
                False,
            ),
            (
                "project_name/settings/local.py.j2",
                f"{package_name}/settings/local.py",
                False,
            ),
            (
                "project_name/settings/production.py.j2",
                f"{package_name}/settings/production.py",
                False,
            ),
            # Error page templates (shared across all themes)
            ("templates/404.html.j2", "templates/404.html", False),
            ("templates/500.html.j2", "templates/500.html", False),
            # CI/CD and quality tools
            ("github/workflows/ci.yml.j2", ".github/workflows/ci.yml", False),
            (".pre-commit-config.yaml.j2", ".pre-commit-config.yaml", False),
            # Tests
            ("tests/__init__.py.j2", "tests/__init__.py", False),
            ("tests/conftest.py.j2", "tests/conftest.py", False),
            ("tests/test_example.py.j2", "tests/test_example.py", False),
        ]

        # Theme-specific files: HTML uses Django templates, React uses frontend/
        if self.theme == "showcase_react":
            # React theme: copy entire frontend directory
            self._generate_react_frontend(output_path, context)
        else:
            # HTML secondary theme: use Django templates and static files
            file_mappings.extend(
                [
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
                        self._get_theme_template_path("templates/admin/index.html.j2"),
                        "templates/admin/index.html",
                        False,
                    ),
                    (
                        self._get_theme_template_path(
                            "templates/admin/app_index.html.j2"
                        ),
                        "templates/admin/app_index.html",
                        False,
                    ),
                    (
                        self._get_theme_template_path(
                            "templates/components/navigation.html.j2"
                        ),
                        "templates/components/navigation.html",
                        False,
                    ),
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
                    (
                        self._get_theme_template_path(
                            "templates/social/link_tree.html.j2"
                        ),
                        "templates/social/link_tree.html",
                        False,
                    ),
                    (
                        self._get_theme_template_path(
                            "templates/social/embeds.html.j2"
                        ),
                        "templates/social/embeds.html",
                        False,
                    ),
                ]
            )

        # Render and write all files
        for template_path, output_file, executable in file_mappings:
            # Render template
            template = self.env.get_template(template_path)
            content = template.render(**context)

            # Write file
            output_file_path = output_path / output_file
            write_file(output_file_path, content, executable=executable)

        # Generate poetry.lock dynamically to ensure it's always in sync
        # with pyproject.toml (avoids stale lock file issues)
        self._generate_poetry_lock(output_path)

    def _generate_react_frontend(self, output_path: Path, context: dict) -> None:
        """Generate React frontend from theme templates

        Copies all files from showcase_react theme, rendering .j2 templates
        with project context. Also generates the Django index.html template
        for serving the React app.

        """
        theme_dir = self.template_dir / "themes" / "showcase_react"
        frontend_output = output_path / "frontend"
        templates_output = output_path / "templates"
        ensure_directory(frontend_output)
        ensure_directory(templates_output)

        # Walk through all files in theme directory
        for root, _dirs, files in os.walk(theme_dir):
            rel_root = Path(root).relative_to(theme_dir)

            for filename in files:
                src_path = Path(root) / filename

                # Skip README.md (theme documentation, not project file)
                if filename == "README.md" and rel_root == Path("."):
                    continue

                # Handle templates directory separately - copy to project templates/
                if str(rel_root).startswith("templates"):
                    if filename.endswith(".j2"):
                        output_filename = filename[:-3]  # Remove .j2 extension
                        rel_template_path = rel_root / output_filename
                        # Convert relative path to just the filename within templates/
                        output_file_path = output_path / rel_template_path

                        # Prefer the theme-specific Django template when it
                        # exists; otherwise fall back to the shared
                        # ``templates/`` location so that admin overrides and
                        # other identical templates can live in one place.
                        template_rel_path = (
                            f"themes/showcase_react/{rel_root / filename}"
                        )
                        if not (self.template_dir / template_rel_path).exists():
                            template_rel_path = str(rel_root / filename)

                        template = self.env.get_template(template_rel_path)
                        content = template.render(**context)

                        write_file(output_file_path, content)
                    continue

                # Determine output path and whether to render as template
                if filename.endswith(".j2"):
                    # Template file: render it
                    output_filename = filename[:-3]  # Remove .j2 extension
                    rel_output_path = rel_root / output_filename

                    # Get template relative to template_dir
                    template_rel_path = f"themes/showcase_react/{rel_root / filename}"
                    template = self.env.get_template(template_rel_path)
                    content = template.render(**context)

                    # Skip optional React components when their gating module
                    # is not selected. This keeps generated apps free of dead
                    # imports and unrendered routes for unselected modules.
                    if self._should_skip_optional_react_file(rel_output_path):
                        continue

                    output_file_path = frontend_output / rel_output_path
                    write_file(output_file_path, content)
                else:
                    # Regular file: copy as-is
                    rel_output_path = rel_root / filename
                    output_file_path = frontend_output / rel_output_path

                    ensure_directory(output_file_path.parent)
                    shutil.copy2(src_path, output_file_path)

        # Render shared Django templates that are not theme-specific. The
        # React walker above only visits files inside the theme directory, so
        # we explicitly add shared Django templates (such as admin overrides)
        # here to keep both themes in sync without duplicating files.
        for shared_rel in REACT_THEME_SHARED_DJANGO_TEMPLATES:
            shared_source = self.template_dir / shared_rel
            if not shared_source.exists():
                continue

            output_rel = Path(shared_rel).with_suffix("")  # Strip .j2
            output_file_path = output_path / output_rel
            template = self.env.get_template(shared_rel)
            content = template.render(**context)
            write_file(output_file_path, content)

    def _should_skip_optional_react_file(self, rel_output_path: Path) -> bool:
        """Return True when an optional React file should be skipped.

        Optional files are mapped to the module that gates them in
        :data:`REACT_THEME_OPTIONAL_FILES`. When ``selected_modules`` is
        ``None`` (legacy default) no file is skipped. When
        ``selected_modules`` is an explicit list, the file is skipped only
        when the gating module is missing from the list.
        """
        if self.selected_modules is None:
            return False

        posix_path = rel_output_path.as_posix()
        gating_module = REACT_THEME_OPTIONAL_FILES.get(posix_path)
        if gating_module is None:
            return False

        return gating_module not in self.selected_modules

    def _generate_poetry_lock(self, project_path: Path) -> None:
        """
        Generate poetry.lock file for the project.

        Runs `poetry lock` in the project directory to create a fresh lock
        file that matches pyproject.toml. This ensures the lock file is
        always in sync with dependencies.

        Args:
        ----
            project_path: Path to the generated project directory

        Raises:
        ------
            RuntimeError: If poetry lock command fails

        """
        try:
            result = subprocess.run(
                ["poetry", "lock"],
                cwd=project_path,
                capture_output=True,
                text=True,
                check=False,
            )

            if result.returncode != 0:
                # Log warning but don't fail - user can run poetry install manually
                # This handles cases where poetry is not available or network issues
                import sys

                print(
                    f"Warning: Could not generate poetry.lock: {result.stderr}",
                    file=sys.stderr,
                )
                print(
                    "Run 'poetry install' in the project directory to generate it.",
                    file=sys.stderr,
                )
        except FileNotFoundError:
            # Poetry not installed - user will need to run poetry install
            import sys

            print(
                "Warning: Poetry not found. Run 'poetry install' in the project "
                "directory to generate poetry.lock.",
                file=sys.stderr,
            )
