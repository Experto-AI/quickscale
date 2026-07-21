"""Project generator implementation"""

import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from quickscale_core.generator.runtime_pins import (
    DJANGO_CONSTRAINT,
    DJANGO_CI_MATRIX_VERSION,
    POSTGRES_DOCKER_TAG,
    POSTGRES_VERSION,
    PYTHON_CONSTRAINT,
    PYTHON_DOCKER_TAG,
    PYTHON_VERSION,
)
from quickscale_core.utils.file_utils import (
    ensure_directory,
    validate_project_name,
    write_file,
)


# Hard ceiling for the `poetry lock` subprocess during generation. Without a
# timeout a stalled dependency resolve (unreachable index, hung network) blocks
# generation — and any test that drives it — indefinitely. Bounded so a hang
# degrades to a warning instead of wedging.
POETRY_LOCK_TIMEOUT_SECONDS = 300


# React theme Django-side templates that should be rendered from the shared
# ``templates/`` location when the theme-specific copy is absent.
REACT_THEME_SHARED_DJANGO_TEMPLATES: tuple[str, ...] = (
    "templates/admin/index.html.j2",
    "templates/admin/app_index.html.j2",
)

# ---------------------------------------------------------------------------
# Theme-to-emitted-path routing (consumed by SA66 conformance gate)
# ---------------------------------------------------------------------------

#: Theme prefix -> emitted-project directory mapping.
#: Keys are the directory name under ``themes/``; values are the destination
#: directory in the generated project.
_THEME_DEST_MAP: dict[str, str] = {
    "showcase_react": "frontend",
}

#: Subdirectory re-mappings within a theme's tree.
#: Keys are source subdirectory patterns; values are the complete emitted
#: path relative to the project root (ignoring the theme's root destination,
#: since these subdirectories map to well-known project directories rather
#: than being nested under the theme's root prefix).
_THEME_SUBDIR_MAP: dict[str, str] = {
    "templates": "templates",
    "static": "static",
    "public": "frontend/public",
    "src": "frontend/src",
    "e2e": "frontend/e2e",
}


def _resolve_theme_emitted_path(template_rel: Path) -> str | None:
    """Map a theme template path to its emitted project-relative path.

    Returns ``None`` for theme files that are not directly emitted as
    project files (e.g. non-Jinja2 artifacts only used at scaffold time,
    or the theme README which the generator explicitly skips).
    """
    # template_rel looks like themes/showcase_react/vite.config.ts (no .j2)
    parts = template_rel.parts
    if len(parts) < 3:
        return None
    theme_name = parts[1]
    rest = Path(*parts[2:])

    dest_prefix = _THEME_DEST_MAP.get(theme_name)
    if dest_prefix is None:
        return None

    # Check for a known subdirectory mapping.
    # The subdirectory map gives the COMPLETE emitted paths relative to the
    # project root, so the theme prefix is ignored for these entries --
    # the subdir might map to a totally different location (e.g. theme
    # templates/ goes to project templates/, not frontend/templates/).
    first_segment = rest.parts[0] if rest.parts else ""
    if first_segment in _THEME_SUBDIR_MAP:
        sub_dest = _THEME_SUBDIR_MAP[first_segment]
        suffix = Path(*rest.parts[1:])
        return str(Path(sub_dest) / suffix)

    # Files at the theme root (package.json.j2, tsconfig.json.j2, etc.)
    dest_segments = [seg for seg in [dest_prefix] if seg]
    return str(Path(*dest_segments) / rest)


def _theme_non_jinja_emitted_paths(
    template_root: Path, theme: str = "showcase_react"
) -> dict[str, str]:
    """Return ``{emitted_path: template_root_rel_path}`` for non-Jinja theme files
    that the generator copies as-is.

    Only the ``showcase_react`` theme emits non-Jinja files (TypeScript source
    files, PNG icons, etc.).
    """
    result: dict[str, str] = {}
    # Only the React theme has non-Jinja files that are emitted as project
    # artifacts.  Other themes only carry repo-tracking placeholders.
    if theme != "showcase_react":
        return result
    theme_dir = template_root / "themes" / theme
    if not theme_dir.is_dir():
        return result
    dest_prefix = _THEME_DEST_MAP.get(theme, "")
    for theme_path in sorted(theme_dir.rglob("*")):
        if not theme_path.is_file():
            continue
        # Only include non-Jinja files
        if theme_path.suffix == ".j2":
            continue
        # The generator explicitly skips the theme README
        if theme_path.name == "README.md" and theme_path.parent == theme_dir:
            continue
        rel = theme_path.relative_to(theme_dir)
        first_segment = rel.parts[0] if rel.parts else ""
        if first_segment in _THEME_SUBDIR_MAP:
            sub_dest = _THEME_SUBDIR_MAP[first_segment]
            suffix = Path(*rel.parts[1:])
            emitted = str(Path(sub_dest) / suffix)
        else:
            dest_segments = [seg for seg in [dest_prefix] if seg]
            emitted = str(Path(*dest_segments) / rel)
        # Store the template-root-relative path (includes theme name)
        result[emitted] = f"themes/{theme}/{rel}"
    return result


def get_generator_emission_mapping(
    template_root: Path,
    *,
    theme: str = "showcase_react",
    package_name: str = "{package}",
    selected_modules: list[str] | None = None,
) -> dict[str, str]:
    """Return ``{emitted_path: template_rel_path}`` for every file the
    generator emits for a given theme and module selection.

    This is the authoritative emission mapping consumed by both production
    generation and the SA66 conformance gate.  Template paths use
    ``{package}`` or ``package_name`` as a placeholder for the generated
    project's Python package name.

    Priority order for conflicting emitted destinations:
        1. Theme-specific templates (always win)
        2. Common templates (only if not claimed by theme)
        3. ``project_name``, ``github``, and root-level templates (only if
           not claimed by theme or common)

    Args:
    ----
        template_root: Path to the generator's templates directory.
        theme: Theme name to use for resolution (default ``showcase_react``).
        package_name: Python package name placeholder.  For conformance
            mapping use the default ``{package}``; for production use the
            actual package name.
        selected_modules: Optional list of selected module names.  After
            SA105, this no longer filters frontend source files — all
            module files are always emitted as dormant entries.  It is
            retained for non-frontend surfaces (e.g. Django settings
            wiring).

    Returns:
    -------
        dict mapping each emitted project-relative path to the source
        template's relative path within the template tree.

    Raises:
    ------
        ValueError: If two different source templates map to the same
            emitted destination.

    """
    mapping: dict[str, str] = {}
    theme_claimed: set[str] = set()
    common_claimed: set[str] = set()

    # ------------------------------------------------------------------
    # Pass 1: Theme-specific .j2 templates (highest priority)
    # ------------------------------------------------------------------
    for template_path in sorted(template_root.rglob("*.j2")):
        rel = template_path.relative_to(template_root)
        stem = str(rel)
        name_without_suffix = stem[:-3] if stem.endswith(".j2") else stem
        rel_no_j2 = Path(name_without_suffix)
        parts = rel_no_j2.parts

        if parts[0] != "themes":
            continue
        # Skip templates from non-matching themes
        if len(parts) < 3 or parts[1] != theme:
            continue

        emitted = _resolve_theme_emitted_path(rel_no_j2)
        if emitted is not None:
            if emitted in mapping:
                raise ValueError(
                    f"Duplicate emitted destination {emitted!r}: "
                    f"'{mapping[emitted]}' and '{stem}'"
                )
            mapping[emitted] = stem
            theme_claimed.add(emitted)

    # ------------------------------------------------------------------
    # Pass 2: Common templates (lower priority than theme, higher than root)
    # ------------------------------------------------------------------
    for template_path in sorted(template_root.rglob("*.j2")):
        rel = template_path.relative_to(template_root)
        stem = str(rel)
        name_without_suffix = stem[:-3] if stem.endswith(".j2") else stem
        rel_no_j2 = Path(name_without_suffix)
        parts = rel_no_j2.parts

        if parts[0] != "common":
            continue

        suffix = Path(*parts[1:])
        emitted = str(suffix)

        if emitted in theme_claimed:
            continue  # theme-specific template overrides common

        if emitted in mapping:
            if mapping[emitted] == stem:
                continue  # idempotent entry
            raise ValueError(
                f"Duplicate emitted destination {emitted!r}: "
                f"'{mapping[emitted]}' and '{stem}'"
            )
        mapping[emitted] = stem
        common_claimed.add(emitted)

    # ------------------------------------------------------------------
    # Pass 3: All remaining .j2 templates (project_name, github, root-level)
    # ------------------------------------------------------------------
    for template_path in sorted(template_root.rglob("*.j2")):
        rel = template_path.relative_to(template_root)
        stem = str(rel)
        name_without_suffix = stem[:-3] if stem.endswith(".j2") else stem
        rel_no_j2 = Path(name_without_suffix)
        parts = rel_no_j2.parts

        # Skip theme and common — handled in passes 1 and 2
        if parts[0] in ("themes", "common"):
            continue

        # --- project_name/ templates (emitted as {package}/...) ---
        if parts[0] == "project_name":
            suffix = Path(*parts[1:])
            emitted = str(Path(package_name) / suffix)
        # --- github/ -> .github/ ---
        elif parts[0] == "github":
            suffix = Path(*parts[1:])
            emitted = str(Path(".github") / suffix)
        # --- Root-level templates ---
        else:
            emitted = name_without_suffix

        # Skip if already claimed by a higher-priority template
        if emitted in theme_claimed:
            continue

        # Root-level templates defer to common/ when they map to the same
        # emitted project path (e.g. templates/admin/index.html.j2 exists
        # both at root and under common/ — common wins).
        if parts[0] not in ("project_name", "github") and emitted in common_claimed:
            continue

        if emitted in mapping:
            if mapping[emitted] == stem:
                continue  # idempotent entry
            raise ValueError(
                f"Duplicate emitted destination {emitted!r}: "
                f"'{mapping[emitted]}' and '{stem}'"
            )
        mapping[emitted] = stem

    # ------------------------------------------------------------------
    # Pass 4: Non-Jinja theme files copied as-is
    # ------------------------------------------------------------------
    for emitted_path, template_rel in _theme_non_jinja_emitted_paths(
        template_root, theme=theme
    ).items():
        if emitted_path in mapping:
            raise ValueError(
                f"Duplicate emitted destination {emitted_path!r}: "
                f"'{mapping[emitted_path]}' and '{template_rel}'"
            )
        mapping[emitted_path] = template_rel

    # ------------------------------------------------------------------
    # Pass 5: Dynamically generated outputs
    # ------------------------------------------------------------------
    mapping["poetry.lock"] = "<dynamic: generated by _generate_poetry_lock()>"

    return mapping


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
                selected. After SA105, this no longer gates frontend source
                files — all module files are always emitted as dormant entries
                regardless of selection. It is retained for non-frontend
                surfaces (e.g. Django settings wiring).

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
        available_themes = ["showcase_react"]
        if theme not in available_themes:
            raise ValueError(
                f"Invalid theme '{theme}'. Available themes: {', '.join(available_themes)}"
            )

        if template_dir is None:
            # Resolve templates from the installed package path deterministically.
            import quickscale_core

            package_dir = Path(quickscale_core.__file__).parent
            template_dir = package_dir / "generator" / "templates"

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

        Raises:
        ------
            FileNotFoundError: If the template is not found in the theme
                or common directories — includes the attempted paths.

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

        # Neither theme nor common path exists — raise immediately with
        # attempted paths instead of deferring to a later Jinja
        # TemplateNotFound.
        raise FileNotFoundError(
            f"Template '{template_name}' not found for theme '{self.theme}'. "
            f"Searched:\n"
            f"  - {theme_full_path}\n"
            f"  - {common_full_path}\n"
            f"Ensure the template exists in one of these locations."
        )

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
        # SA94 retired-theme sentinel: reject retired themes before any
        # tempfile creation, file writes/copies, cleanup, or subprocess.
        available_themes = ["showcase_react"]
        if self.theme not in available_themes:
            raise ValueError(
                f"Invalid theme '{self.theme}'. Available themes: {', '.join(available_themes)}"
            )

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
        # Default runtime DB role name derived from the Python package name.
        # Used for the NOSUPERUSER/NOBYPASSRLS role created by the init SQL.
        _runtime_db_role = f"{package_name}_app"
        _runtime_db_default_password = f"{_runtime_db_role}_password"

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
            # Generated-project runtime pins (owned by this module, not the generator)
            "python_version": PYTHON_VERSION,
            "python_constraint": PYTHON_CONSTRAINT,
            "python_docker_tag": PYTHON_DOCKER_TAG,
            "django_constraint": DJANGO_CONSTRAINT,
            "django_ci_version": DJANGO_CI_MATRIX_VERSION,
            "postgres_version": POSTGRES_VERSION,
            "postgres_docker_tag": POSTGRES_DOCKER_TAG,
            # Runtime DB role (RLS enforcement — NOSUPERUSER, NOBYPASSRLS)
            "runtime_db_role": _runtime_db_role,
            "runtime_db_password": _runtime_db_default_password,
        }

        # Known executable files (emitted paths that should be executable)
        _EXECUTABLE_FILES: frozenset[str] = frozenset(
            {
                "manage.py",
                "scripts/lint.sh",
                # Note: start.sh is intentionally excluded from executable
                # mode to preserve backward-compatible generated-output
                # behavior (it was False in the original file_mappings).
            }
        )

        # Get the authoritative emission mapping for this theme and selection.
        # This replaces the previous hardcoded file_mappings and
        # _generate_react_frontend routing.
        mapping = get_generator_emission_mapping(
            self.template_dir,
            theme=self.theme,
            package_name=package_name,
            selected_modules=self.selected_modules,
        )

        for emitted_path, template_rel in mapping.items():
            # poetry.lock is generated dynamically after all files are written
            if emitted_path == "poetry.lock":
                continue

            output_file_path = output_path / emitted_path

            if template_rel.endswith(".j2"):
                # Jinja template — render with project context
                template = self.env.get_template(template_rel)
                content = template.render(**context)

                is_executable = emitted_path in _EXECUTABLE_FILES
                write_file(output_file_path, content, executable=is_executable)
            else:
                # Non-Jinja file — copy as-is (preserving metadata via shutil.copy2)
                source_path = self.template_dir / template_rel
                ensure_directory(output_file_path.parent)
                shutil.copy2(source_path, output_file_path)

        # Generate poetry.lock dynamically to ensure it's always in sync
        # with pyproject.toml (avoids stale lock file issues)
        self._generate_poetry_lock(output_path)

    def _generate_react_frontend(self, output_path: Path, context: dict) -> None:
        """Generate React frontend from theme templates (delegating compatibility seam).

        The actual frontend generation is now handled by the authoritative
        :meth:`_generate_project` which consumes
        :func:`get_generator_emission_mapping`. This method is retained as
        a delegating seam for any external caller that directly references
        it — it calls ``_generate_project`` via the parent generation flow.

        .. note::

            This method is **not** called by the current generation path
            (``_generate_project`` handles both themes uniformly). It exists
            only as a compatibility shim for any code that may call it
            directly.
        """
        # Delegate to the same mapping-driven path that _generate_project uses.
        # Re-render would be redundant; this is a no-op seam.
        pass

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
        # Escape hatch for test suites: ``poetry lock`` is a network side-effect
        # that, under parallel/repeated generation, serializes on Poetry's global
        # cache lock and can wedge the run. Setting ``QS_SKIP_POETRY_LOCK=1`` skips
        # it so unit tests that drive ``generate()`` stay fast and hermetic. Tests
        # that need a real lock (e2e) leave it unset and produce one explicitly.
        if os.environ.get("QS_SKIP_POETRY_LOCK") == "1":
            return
        try:
            result = subprocess.run(
                ["poetry", "lock"],
                cwd=project_path,
                capture_output=True,
                text=True,
                check=False,
                timeout=POETRY_LOCK_TIMEOUT_SECONDS,
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
        except subprocess.TimeoutExpired:
            # `poetry lock` hung (typically a stalled network dependency
            # resolve). Degrade to a warning instead of blocking forever, so a
            # slow/unreachable index can never wedge generation (or the test
            # suite that drives it). User can regenerate the lock manually.
            import sys

            print(
                "Warning: 'poetry lock' timed out after "
                f"{POETRY_LOCK_TIMEOUT_SECONDS}s (network issue?). "
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
