"""Tests for ProjectGenerator class"""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.generator import ProjectGenerator


class TestProjectGeneratorInit:
    """Tests for ProjectGenerator initialization"""

    def test_init_with_default_template_dir(self) -> None:
        """Should initialize with default template directory"""
        generator = ProjectGenerator(theme="showcase_html")

        assert generator.template_dir.exists()
        assert generator.template_dir.name == "templates"
        assert generator.env is not None

    def test_init_with_custom_template_dir(self, tmp_path: Path) -> None:
        """Should initialize with custom template directory"""
        custom_dir = tmp_path / "custom_templates"
        custom_dir.mkdir()

        # Create required themes directory structure
        themes_dir = custom_dir / "themes" / "showcase_html"
        themes_dir.mkdir(parents=True)

        generator = ProjectGenerator(template_dir=custom_dir, theme="showcase_html")

        assert generator.template_dir == custom_dir

    def test_init_with_nonexistent_dir(self, tmp_path: Path) -> None:
        """Should raise FileNotFoundError for nonexistent directory"""
        nonexistent = tmp_path / "nonexistent"

        with pytest.raises(FileNotFoundError, match="Template directory not found"):
            ProjectGenerator(template_dir=nonexistent)


class TestProjectGeneratorValidation:
    """Tests for project name validation in generator"""

    def test_generate_with_invalid_name(self, tmp_path: Path) -> None:
        """Should raise ValueError for invalid project name"""
        generator = ProjectGenerator(theme="showcase_html")

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("123invalid", tmp_path / "output")

    def test_generate_with_keyword_name(self, tmp_path: Path) -> None:
        """Should raise ValueError for Python keyword"""
        generator = ProjectGenerator(theme="showcase_html")

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("class", tmp_path / "output")

    def test_generate_with_reserved_name(self, tmp_path: Path) -> None:
        """Should raise ValueError for reserved name"""
        generator = ProjectGenerator(theme="showcase_html")

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("test", tmp_path / "output")


class TestProjectGeneratorPathChecks:
    """Tests for output path validation"""

    def test_generate_to_existing_path(self, tmp_path: Path) -> None:
        """Should raise FileExistsError if output path exists"""
        generator = ProjectGenerator(theme="showcase_html")
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        with pytest.raises(FileExistsError, match="Output path already exists"):
            generator.generate("myproject", existing_dir)

    def test_generate_to_unwritable_parent(self, tmp_path: Path) -> None:
        """Should raise PermissionError for unwritable parent directory"""
        generator = ProjectGenerator(theme="showcase_html")

        # Create a directory and make it read-only
        readonly_dir = tmp_path / "readonly"
        readonly_dir.mkdir()
        readonly_dir.chmod(0o444)

        try:
            with pytest.raises(PermissionError):
                generator.generate("myproject", readonly_dir / "output")
        finally:
            # Restore permissions for cleanup
            readonly_dir.chmod(0o755)

    def test_generate_creates_parent_directory(self, tmp_path: Path) -> None:
        """Should create parent directory if it does not exist"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "myproject"

        # Create a nested path where intermediate directories don't exist
        output_path = tmp_path / "level1" / "level2" / project_name

        # Parent directories should not exist yet
        assert not (tmp_path / "level1").exists()

        # Generate project - should create parent directories
        generator.generate(project_name, output_path)

        # Verify project was created
        assert output_path.exists()
        assert (output_path / "manage.py").exists()
        assert (tmp_path / "level1").exists()
        assert (tmp_path / "level1" / "level2").exists()


class TestProjectGeneratorGeneration:
    """Tests for successful project generation"""

    @pytest.mark.parametrize(
        ("theme", "project_name"),
        [
            ("showcase_html", "testproject_html"),
            ("showcase_react", "testproject_react"),
        ],
    )
    def test_generate_emits_root_makefile_for_supported_themes(
        self, tmp_path: Path, theme: str, project_name: str
    ) -> None:
        """Supported themes should always emit the generated root Makefile."""
        generator = ProjectGenerator(theme=theme)
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        makefile = output_path / "Makefile"
        assert makefile.exists()
        assert ".DEFAULT_GOAL := help" in makefile.read_text()

    def test_generate_creates_project_structure(self, tmp_path: Path) -> None:
        """Should create complete project structure"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check root files exist
        assert (output_path / "manage.py").exists()
        assert (output_path / "pyproject.toml").exists()
        if not (output_path / "poetry.lock").exists():
            pytest.skip("poetry.lock generation skipped (network unavailable)")
        assert (output_path / ".gitignore").exists()
        assert (output_path / "Dockerfile").exists()
        assert (output_path / "docker-compose.yml").exists()

        # Check project package exists
        assert (output_path / project_name / "__init__.py").exists()
        assert (output_path / project_name / "urls.py").exists()
        assert (output_path / project_name / "wsgi.py").exists()
        assert (output_path / project_name / "asgi.py").exists()

        # Check settings package exists
        assert (output_path / project_name / "settings" / "__init__.py").exists()
        assert (output_path / project_name / "settings" / "base.py").exists()
        assert (output_path / project_name / "settings" / "local.py").exists()
        assert (output_path / project_name / "settings" / "production.py").exists()

        # Check templates and static files
        assert (output_path / "templates" / "index.html").exists()
        assert (output_path / "static" / "css" / "style.css").exists()

    def test_manage_py_is_executable(self, tmp_path: Path) -> None:
        """Should make manage.py executable"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        manage_py = output_path / "manage.py"
        assert os.access(manage_py, os.X_OK)

    def test_generated_files_contain_project_name(self, tmp_path: Path) -> None:
        """Generated files should contain the project name"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "myapp"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check that project name appears in key files
        pyproject_content = (output_path / "pyproject.toml").read_text()
        assert f'name = "{project_name}"' in pyproject_content

        urls_content = (output_path / project_name / "urls.py").read_text()
        assert project_name in urls_content

    def test_generated_urls_modules_exports_placeholder_buckets(
        self, tmp_path: Path
    ) -> None:
        """Generated urls_modules.py should expose raw placeholder buckets."""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "myapp"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        urls_modules_content = (
            output_path / project_name / "urls_modules.py"
        ).read_text()

        assert (
            "PRE_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []"
            in urls_modules_content
        )
        assert (
            "POST_HOME_MODULE_URLPATTERNS: list[ManagedURLPattern] = []"
            in urls_modules_content
        )
        assert "MODULE_URLPATTERNS: list[ManagedURLPattern] = (" in urls_modules_content
        assert (
            "PRE_HOME_MODULE_URLPATTERNS + POST_HOME_MODULE_URLPATTERNS"
            in urls_modules_content
        )

    def test_generated_python_files_are_valid(self, tmp_path: Path) -> None:
        """Generated Python files should be syntactically valid"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "validproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Try to compile Python files
        python_files = [
            output_path / "manage.py",
            output_path / project_name / "__init__.py",
            output_path / project_name / "urls.py",
            output_path / project_name / "urls_modules.py",
            output_path / project_name / "wsgi.py",
            output_path / project_name / "asgi.py",
            output_path / project_name / "settings" / "base.py",
            output_path / project_name / "settings" / "local.py",
            output_path / project_name / "settings" / "production.py",
        ]

        for py_file in python_files:
            # This will raise SyntaxError if file is invalid
            compile(py_file.read_text(), str(py_file), "exec")


class TestGeneratedProjectSettingsProxyMath:
    """Validate emitted settings files after full project generation.

    SA36 regression: the inline proxy-math comment in the generated
    ``base.py`` must match the actual ``-TRUSTED_PROXY_COUNT`` indexing
    used by ``get_client_ip()``. This test verifies the fix survives
    a full project generation (regeneration-path validation).
    """

    def test_generated_base_settings_proxy_math_comment_corrected(
        self, generated_project_path: Path
    ) -> None:
        """The emitted base.py must contain the corrected proxy-math comment."""
        base_py = generated_project_path / "testproject" / "settings" / "base.py"
        assert base_py.exists(), "Generated base.py not found"

        content = base_py.read_text()

        # Must contain the corrected formula (Nth from the right)
        assert "-TRUSTED_PROXY_COUNT" in content, (
            "Generated base.py should reference -TRUSTED_PROXY_COUNT (not the old +1 formula)"
        )
        # Must NOT contain the stale +1 formula
        assert "-(TRUSTED_PROXY_COUNT + 1)" not in content, (
            "Generated base.py must not contain the old stale +1 proxy-math formula"
        )

    def test_generated_base_settings_valid_python(
        self, generated_project_path: Path
    ) -> None:
        """The emitted base.py must be syntactically valid Python."""
        base_py = generated_project_path / "testproject" / "settings" / "base.py"
        assert base_py.exists()
        compile(base_py.read_text(), str(base_py), "exec")

    def test_generated_settings_package_all_valid_python(
        self, generated_project_path: Path
    ) -> None:
        """All emitted settings files must be syntactically valid."""
        settings_dir = generated_project_path / "testproject" / "settings"
        for py_file in sorted(settings_dir.glob("*.py")):
            compile(py_file.read_text(), str(py_file), "exec")


class TestProjectGeneratorAtomicCreation:
    """Tests for atomic project creation (rollback on failure)"""

    def test_rollback_on_template_error(self, tmp_path: Path) -> None:
        """Should clean up temp directory if template rendering fails"""
        # Create generator with nonexistent template
        generator = ProjectGenerator(theme="showcase_html")

        # Monkey-patch to force an error during generation
        original_method = generator._generate_project

        def failing_generate(*args: object, **kwargs: object) -> None:
            raise RuntimeError("Simulated template error")

        generator._generate_project = failing_generate  # type: ignore[method-assign]

        output_path = tmp_path / "failproject"

        with pytest.raises(RuntimeError, match="Failed to generate project"):
            generator.generate("validname", output_path)

        # Output path should not exist (rollback)
        assert not output_path.exists()

        # Restore original method
        generator._generate_project = original_method  # type: ignore[method-assign]


class TestProjectGeneratorMultipleProjects:
    """Tests for generating multiple projects"""

    def test_generate_multiple_projects(self, tmp_path: Path) -> None:
        """Should be able to generate multiple projects"""
        generator = ProjectGenerator(theme="showcase_html")

        projects = ["project1", "project2", "project3"]

        for project_name in projects:
            output_path = tmp_path / project_name
            generator.generate(project_name, output_path)

            assert output_path.exists()
            assert (output_path / "manage.py").exists()
            assert (output_path / project_name / "settings" / "base.py").exists()


class TestProjectGeneratorThemeValidation:
    """Tests for theme validation and template path edge cases."""

    def test_init_raises_value_error_when_theme_dir_missing_in_custom_template_dir(
        self, tmp_path: Path
    ) -> None:
        """ValueError raised when custom template_dir has no theme subdirectory."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()

        with pytest.raises(ValueError, match="Theme directory not found"):
            ProjectGenerator(template_dir=template_dir, theme="showcase_html")

    def test_init_rejects_removed_htmx_theme(self, tmp_path: Path) -> None:
        """ValueError raised for removed showcase_htmx theme."""
        template_dir = tmp_path / "mytemplates"
        template_dir.mkdir()
        (template_dir / "themes" / "showcase_html").mkdir(parents=True)

        with pytest.raises(ValueError, match="Invalid theme 'showcase_htmx'"):
            ProjectGenerator(template_dir=template_dir, theme="showcase_htmx")

    def test_returns_theme_path_when_theme_template_exists(
        self, tmp_path: Path
    ) -> None:
        """Theme-specific template is preferred over common template."""
        template_dir = tmp_path / "templates"
        theme_dir = template_dir / "themes" / "showcase_html"
        theme_dir.mkdir(parents=True)
        (theme_dir / "mytemplate.html.j2").write_text("{{ project_name }}")

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_html")

        assert (
            generator._get_theme_template_path("mytemplate.html.j2")
            == "themes/showcase_html/mytemplate.html.j2"
        )

    def test_returns_common_path_when_only_common_template_exists(
        self, tmp_path: Path
    ) -> None:
        """Returns common/ path when theme template is absent but common exists."""
        template_dir = tmp_path / "templates"
        theme_dir = template_dir / "themes" / "showcase_html"
        theme_dir.mkdir(parents=True)
        common_dir = template_dir / "common"
        common_dir.mkdir()
        (common_dir / "fallback.html.j2").write_text("fallback content")

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_html")

        assert (
            generator._get_theme_template_path("fallback.html.j2")
            == "common/fallback.html.j2"
        )

    def test_raises_file_not_found_when_neither_theme_nor_common_exists(
        self, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError with attempted paths when template is missing."""
        template_dir = tmp_path / "templates"
        (template_dir / "themes" / "showcase_html").mkdir(parents=True)

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_html")

        with pytest.raises(
            FileNotFoundError,
            match="Template 'some_root_template.j2' not found for theme 'showcase_html'",
        ):
            generator._get_theme_template_path("some_root_template.j2")


class TestProjectGeneratorErrorPaths:
    """Tests for generate() and poetry lock error handling."""

    def test_generate_raises_permission_error_when_ensure_directory_fails(
        self, tmp_path: Path
    ) -> None:
        """PermissionError raised when parent dir creation fails with OSError."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "nonexistent_parent" / "subdir" / "myproject"

        with patch(
            "quickscale_core.generator.generator.ensure_directory",
            side_effect=OSError("disk full"),
        ):
            with pytest.raises(PermissionError, match="Cannot create parent directory"):
                generator.generate("myproject", output_path)

    def test_generate_raises_permission_error_when_access_denied(
        self, tmp_path: Path
    ) -> None:
        """PermissionError raised via os.access check returning False."""
        generator = ProjectGenerator(theme="showcase_html")
        parent_dir = tmp_path / "existing_parent"
        parent_dir.mkdir()
        output_path = parent_dir / "myproject"

        with patch("os.access", return_value=False):
            with pytest.raises(PermissionError, match="not writable"):
                generator.generate("myproject", output_path)

    def test_generate_poetry_lock_handles_file_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Prints warning when poetry executable is not found; does not raise."""
        generator = ProjectGenerator(theme="showcase_html")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        with patch("subprocess.run", side_effect=FileNotFoundError("poetry not found")):
            generator._generate_poetry_lock(project_path)

        captured = capsys.readouterr()
        assert "Poetry not found" in captured.err or "poetry" in captured.err.lower()

    def test_generate_poetry_lock_handles_nonzero_return_code(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Prints warning when poetry lock returns non-zero exit code; does not raise."""
        generator = ProjectGenerator(theme="showcase_html")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "some error output"

        with patch("subprocess.run", return_value=mock_result):
            generator._generate_poetry_lock(project_path)

        captured = capsys.readouterr()
        assert "poetry.lock" in captured.err or "poetry" in captured.err.lower()

    def test_generate_poetry_lock_succeeds_silently(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """No output when poetry lock runs successfully."""
        generator = ProjectGenerator(theme="showcase_html")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            generator._generate_poetry_lock(project_path)

        captured = capsys.readouterr()
        assert captured.err == ""
