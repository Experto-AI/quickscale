"""Tests for ProjectGenerator class"""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from quickscale_core.generator import (
    ProjectGenerator,
    get_generator_emission_mapping,
)


class TestProjectGeneratorInit:
    """Tests for ProjectGenerator initialization"""

    def test_init_with_default_template_dir(self) -> None:
        """Should initialize with default template directory"""
        generator = ProjectGenerator(theme="showcase_react")

        assert generator.template_dir.exists()
        assert generator.template_dir.name == "templates"
        assert generator.env is not None

    def test_init_with_custom_template_dir(self, tmp_path: Path) -> None:
        """Should initialize with custom template directory"""
        custom_dir = tmp_path / "custom_templates"
        custom_dir.mkdir()

        # Create required themes directory structure
        themes_dir = custom_dir / "themes" / "showcase_react"
        themes_dir.mkdir(parents=True)

        generator = ProjectGenerator(template_dir=custom_dir, theme="showcase_react")

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
        generator = ProjectGenerator(theme="showcase_react")

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("123invalid", tmp_path / "output")

    def test_generate_with_keyword_name(self, tmp_path: Path) -> None:
        """Should raise ValueError for Python keyword"""
        generator = ProjectGenerator(theme="showcase_react")

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("class", tmp_path / "output")

    def test_generate_with_reserved_name(self, tmp_path: Path) -> None:
        """Should raise ValueError for reserved name"""
        generator = ProjectGenerator(theme="showcase_react")

        with pytest.raises(ValueError, match="Invalid project name"):
            generator.generate("test", tmp_path / "output")


class TestProjectGeneratorPathChecks:
    """Tests for output path validation"""

    def test_generate_to_existing_path(self, tmp_path: Path) -> None:
        """Should raise FileExistsError if output path exists"""
        generator = ProjectGenerator(theme="showcase_react")
        existing_dir = tmp_path / "existing"
        existing_dir.mkdir()

        with pytest.raises(FileExistsError, match="Output path already exists"):
            generator.generate("myproject", existing_dir)

    def test_generate_to_unwritable_parent(self, tmp_path: Path) -> None:
        """Should raise PermissionError for unwritable parent directory"""
        generator = ProjectGenerator(theme="showcase_react")

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
        generator = ProjectGenerator(theme="showcase_react")
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
            ("showcase_react", "testproject_react"),
        ],
    )
    def test_generate_emits_root_makefile_for_supported_themes(
        self, tmp_path: Path, theme: str, project_name: str
    ) -> None:
        """React theme should always emit the generated root Makefile."""
        generator = ProjectGenerator(theme=theme)
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        makefile = output_path / "Makefile"
        assert makefile.exists()
        assert ".DEFAULT_GOAL := help" in makefile.read_text()

    def test_generate_creates_project_structure(self, tmp_path: Path) -> None:
        """Should create complete project structure"""
        generator = ProjectGenerator(theme="showcase_react")
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

        # Check templates exist (React theme emits templates/ not static/)
        assert (output_path / "templates" / "index.html").exists()
        assert (output_path / "templates" / "base.html").exists()
        # React theme does not emit root static/css/
        assert (output_path / "frontend" / "package.json").exists()

    def test_manage_py_is_executable(self, tmp_path: Path) -> None:
        """Should make manage.py executable"""
        generator = ProjectGenerator(theme="showcase_react")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        manage_py = output_path / "manage.py"
        assert os.access(manage_py, os.X_OK)

    def test_generated_files_contain_project_name(self, tmp_path: Path) -> None:
        """Generated files should contain the project name"""
        generator = ProjectGenerator(theme="showcase_react")
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
        generator = ProjectGenerator(theme="showcase_react")
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
        generator = ProjectGenerator(theme="showcase_react")
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


class TestGeneratedProjectSa63RegenerationEvidence:
    """Fresh regeneration evidence tests for SA63 launcher-contract behavior.

    CR-SA63-002/003 regression: verify that a fresh ``quickscale plan/apply``
    (simulated via ``ProjectGenerator``) emits the correct env pairs and
    bridge code in the generated project's ``start.sh``, ``production.py``,
    and ``local.py``.
    """

    def test_emitted_start_sh_has_createcachetable_env_pair(
        self, generated_project_path: Path
    ) -> None:
        """The emitted start.sh must have QUICKSCALE_PRIVILEGED_COMMAND=createcachetable
        on createcachetable (SA68 Phase 1)."""
        start_sh = generated_project_path / "start.sh"
        assert start_sh.exists(), "Generated start.sh not found"

        content = start_sh.read_text()

        createcachetable_line = next(
            line
            for line in content.splitlines()
            if "python manage.py createcachetable" in line
        )
        assert (
            "QUICKSCALE_PRIVILEGED_COMMAND=createcachetable" in createcachetable_line
        ), (
            "start.sh createcachetable must carry QUICKSCALE_PRIVILEGED_COMMAND=createcachetable"
        )
        assert 'RUNTIME_DATABASE_URL=""' in createcachetable_line, (
            "start.sh createcachetable must clear RUNTIME_DATABASE_URL"
        )

    def test_emitted_production_py_has_explicit_command_contract(
        self, generated_project_path: Path
    ) -> None:
        """The emitted production.py must import os and contain the SA68 Phase 1
        command-mode env vars."""
        production_py = (
            generated_project_path / "testproject" / "settings" / "production.py"
        )
        assert production_py.exists(), "Generated production.py not found"

        content = production_py.read_text()

        # Must import os
        assert "import os" in content, "production.py must import os for env-var checks"

        # Must reference the privileged command env var
        assert "QUICKSCALE_PRIVILEGED_COMMAND" in content, (
            "production.py must reference QUICKSCALE_PRIVILEGED_COMMAND"
        )

        # Must reference the non-DB command env var
        assert "QUICKSCALE_NON_DB_COMMAND" in content, (
            "production.py must reference QUICKSCALE_NON_DB_COMMAND"
        )

        # Must still contain the ALLOW_BYPASSRLS bridge as dev/test opt-out
        assert "QUICKSCALE_ALLOW_BYPASSRLS" in content, (
            "production.py must still reference QUICKSCALE_ALLOW_BYPASSRLS"
        )

        # Must NOT contain argv sniffing
        assert "sys.argv" not in content, (
            "production.py must not inspect sys.argv after SA68 Phase 1"
        )

    def test_emitted_local_py_has_no_argv_inspection(
        self, generated_project_path: Path
    ) -> None:
        """The emitted local.py must not use argv sniffing (SA63)."""
        local_py = generated_project_path / "testproject" / "settings" / "local.py"
        assert local_py.exists(), "Generated local.py not found"

        content = local_py.read_text()

        assert "import sys" not in content, "local.py should not import sys after SA63"
        assert "sys.argv" not in content, (
            "local.py should not inspect sys.argv after SA63"
        )

    def test_emitted_production_py_has_dummy_url_fallback(
        self, generated_project_path: Path
    ) -> None:
        """The emitted production.py must contain the dummy URL fallback
        for non-DB commands (SA68 Phase 3 regression)."""
        production_py = (
            generated_project_path / "testproject" / "settings" / "production.py"
        )
        assert production_py.exists(), "Generated production.py not found"

        content = production_py.read_text()

        # Must have the dummy URL fallback for when DATABASE_URL is unset
        # during a non-DB command (collectstatic/compilemessages)
        assert "postgresql://dummy:dummy@localhost:5432/dummy" in content, (
            "Generated production.py must contain the dummy URL fallback "
            "for non-DB commands without DATABASE_URL"
        )
        # The non-DB command frozenset must be present
        assert "_KNOWN_NON_DB_COMMANDS" in content, (
            "Generated production.py must define _KNOWN_NON_DB_COMMANDS"
        )
        assert "compilemessages" in content, (
            "Generated production.py must include compilemessages "
            "in known non-DB commands"
        )

    def test_emitted_production_py_valid_python(
        self, generated_project_path: Path
    ) -> None:
        """The emitted production.py must be syntactically valid Python."""
        production_py = (
            generated_project_path / "testproject" / "settings" / "production.py"
        )
        assert production_py.exists()
        compile(production_py.read_text(), str(production_py), "exec")


class TestProjectGeneratorAtomicCreation:
    """Tests for atomic project creation (rollback on failure)"""

    def test_rollback_on_template_error(self, tmp_path: Path) -> None:
        """Should clean up temp directory if template rendering fails"""
        # Create generator with nonexistent template
        generator = ProjectGenerator(theme="showcase_react")

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
        generator = ProjectGenerator(theme="showcase_react")

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
            ProjectGenerator(template_dir=template_dir, theme="showcase_react")

    def test_init_rejects_removed_htmx_theme(self, tmp_path: Path) -> None:
        """ValueError raised for removed showcase_htmx theme."""
        template_dir = tmp_path / "mytemplates"
        template_dir.mkdir()
        (template_dir / "themes" / "showcase_react").mkdir(parents=True)

        with pytest.raises(ValueError, match="Invalid theme 'showcase_htmx'"):
            ProjectGenerator(template_dir=template_dir, theme="showcase_htmx")

    def test_returns_theme_path_when_theme_template_exists(
        self, tmp_path: Path
    ) -> None:
        """Theme-specific template is preferred over common template."""
        template_dir = tmp_path / "templates"
        theme_dir = template_dir / "themes" / "showcase_react"
        theme_dir.mkdir(parents=True)
        (theme_dir / "mytemplate.html.j2").write_text("{{ project_name }}")

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_react")

        assert (
            generator._get_theme_template_path("mytemplate.html.j2")
            == "themes/showcase_react/mytemplate.html.j2"
        )

    def test_returns_common_path_when_only_common_template_exists(
        self, tmp_path: Path
    ) -> None:
        """Returns common/ path when theme template is absent but common exists."""
        template_dir = tmp_path / "templates"
        theme_dir = template_dir / "themes" / "showcase_react"
        theme_dir.mkdir(parents=True)
        common_dir = template_dir / "common"
        common_dir.mkdir()
        (common_dir / "fallback.html.j2").write_text("fallback content")

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_react")

        assert (
            generator._get_theme_template_path("fallback.html.j2")
            == "common/fallback.html.j2"
        )

    def test_raises_file_not_found_when_neither_theme_nor_common_exists(
        self, tmp_path: Path
    ) -> None:
        """Raises FileNotFoundError with attempted paths when template is missing."""
        template_dir = tmp_path / "templates"
        (template_dir / "themes" / "showcase_react").mkdir(parents=True)

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_react")

        with pytest.raises(
            FileNotFoundError,
            match="Template 'some_root_template.j2' not found for theme 'showcase_react'",
        ):
            generator._get_theme_template_path("some_root_template.j2")


class TestProjectGeneratorErrorPaths:
    """Tests for generate() and poetry lock error handling."""

    def test_generate_raises_permission_error_when_ensure_directory_fails(
        self, tmp_path: Path
    ) -> None:
        """PermissionError raised when parent dir creation fails with OSError."""
        generator = ProjectGenerator(theme="showcase_react")
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
        generator = ProjectGenerator(theme="showcase_react")
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
        generator = ProjectGenerator(theme="showcase_react")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        with patch("subprocess.run", side_effect=FileNotFoundError("poetry not found")):
            generator._generate_poetry_lock(project_path)

        captured = capsys.readouterr()
        assert "Poetry not found" in captured.err or "poetry" in captured.err.lower()

    def test_generate_poetry_lock_handles_timeout(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """A hung `poetry lock` times out and degrades to a warning; never blocks."""
        generator = ProjectGenerator(theme="showcase_react")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd=["poetry", "lock"], timeout=300),
        ):
            generator._generate_poetry_lock(project_path)

        captured = capsys.readouterr()
        assert "timed out" in captured.err.lower()

    def test_generate_poetry_lock_passes_timeout(self, tmp_path: Path) -> None:
        """The `poetry lock` subprocess must be bounded by a timeout."""
        generator = ProjectGenerator(theme="showcase_react")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result) as mock_run:
            generator._generate_poetry_lock(project_path)

        assert mock_run.call_args.kwargs.get("timeout") is not None

    def test_generate_poetry_lock_handles_nonzero_return_code(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Prints warning when poetry lock returns non-zero exit code; does not raise."""
        generator = ProjectGenerator(theme="showcase_react")
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
        generator = ProjectGenerator(theme="showcase_react")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = ""

        with patch("subprocess.run", return_value=mock_result):
            generator._generate_poetry_lock(project_path)

        captured = capsys.readouterr()
        assert captured.err == ""


class TestSa90MappingDrivenGeneration:
    """SA90: mapping-driven generation correctness.

    Verifies that ``get_generator_emission_mapping`` is the authoritative
    single source of truth and that production generation consumes it
    faithfully.
    """

    # Known executable files at emitted-project paths.
    # Note: start.sh is intentionally NOT included to preserve backward
    # compat (original file_mappings had start.sh executable=False).
    _EXECUTABLE_EMITTED = frozenset({"manage.py", "scripts/lint.sh"})

    @staticmethod
    def _get_template_dir() -> Path:
        """Resolve the live template directory from a temporary generator."""
        import quickscale_core

        return Path(quickscale_core.__file__).parent / "generator" / "templates"

    # ------------------------------------------------------------------
    # Mapping correctness
    # ------------------------------------------------------------------

    def test_mapping_contains_poetry_lock(self) -> None:
        """The mapping should always include a poetry.lock entry."""
        mapping = get_generator_emission_mapping(
            self._get_template_dir(), theme="showcase_react"
        )
        assert "poetry.lock" in mapping
        assert "dynamic" in mapping["poetry.lock"]

    def test_mapping_no_duplicate_destinations(self) -> None:
        """The mapping must never contain duplicate emitted paths."""
        mapping = get_generator_emission_mapping(
            self._get_template_dir(), theme="showcase_react"
        )
        assert len(mapping) == len(set(mapping.keys())), (
            "Duplicate destinations in mapping for showcase_react"
        )

    def test_mapping_react_has_frontend_files(self) -> None:
        """React theme mapping must include frontend/ files."""
        react_map = get_generator_emission_mapping(
            self._get_template_dir(), theme="showcase_react"
        )
        assert any(k.startswith("frontend/") for k in react_map), (
            "React theme should include frontend/ files"
        )
        assert not any(k.startswith("static/") for k in react_map), (
            "React theme should not include static/ files"
        )
        assert not any("templates/components/" in k for k in react_map), (
            "React theme should not include templates/components/"
        )

    def test_mapping_shared_django_templates_present(self) -> None:
        """React theme must map shared Django templates (admin overrides)."""
        mapping = get_generator_emission_mapping(
            self._get_template_dir(), theme="showcase_react"
        )
        assert "templates/admin/index.html" in mapping, (
            "admin/index.html missing from showcase_react mapping"
        )
        assert "templates/admin/app_index.html" in mapping, (
            "admin/app_index.html missing from showcase_react mapping"
        )

    # ------------------------------------------------------------------
    # Post-SA105: selected_modules no longer filters frontend/src files;
    # all optional source files are always present as dormant entries.
    # selected_modules parameter is retained for non-frontend surfaces.
    # ------------------------------------------------------------------

    def test_selected_modules_does_not_filter_frontend_source(self) -> None:
        """After SA105, selected_modules no longer removes frontend/src files."""
        mapping = get_generator_emission_mapping(
            self._get_template_dir(),
            theme="showcase_react",
            selected_modules=[],
        )
        # All optional files are always present (dormant)
        assert "frontend/src/pages/BlogPage.tsx" in mapping
        assert "frontend/src/pages/CrmPage.tsx" in mapping
        assert "frontend/src/pages/FormsPage.tsx" in mapping
        assert "frontend/src/pages/ListingsPage.tsx" in mapping
        assert "frontend/src/pages/SocialLinkTreePublicPage.tsx" in mapping
        assert "frontend/src/pages/SocialEmbedsPublicPage.tsx" in mapping
        assert "frontend/src/components/forms/FormRenderer.tsx" in mapping
        assert "frontend/src/components/forms/FormFieldRenderer.tsx" in mapping
        assert "frontend/src/components/forms/FormSuccess.tsx" in mapping
        assert "frontend/src/hooks/useFormSchema.ts" in mapping

    # ------------------------------------------------------------------
    # Generated-tree completeness: every mapped file exists on disk
    # ------------------------------------------------------------------

    def test_generated_tree_matches_mapping_react(self, tmp_path: Path) -> None:
        """Generated React project must contain every file in the mapping."""
        template_dir = self._get_template_dir()
        project_name = "validname"
        mapping = get_generator_emission_mapping(
            template_dir,
            theme="showcase_react",
            package_name=project_name,
        )
        gen = ProjectGenerator(template_dir=template_dir, theme="showcase_react")
        output = tmp_path / "test_react_map"
        gen.generate(project_name, output)

        missing = [
            ep for ep in mapping if ep != "poetry.lock" and not (output / ep).exists()
        ]
        assert not missing, (
            f"React generated project missing {len(missing)} file(s): {missing[:10]}"
        )

    def test_generated_tree_matches_mapping_react_with_selection(
        self, tmp_path: Path
    ) -> None:
        """Generated React project with selected modules must match mapping."""
        template_dir = self._get_template_dir()
        project_name = "validname"
        selected = ["blog", "forms", "social"]
        mapping = get_generator_emission_mapping(
            template_dir,
            theme="showcase_react",
            package_name=project_name,
            selected_modules=selected,
        )
        gen = ProjectGenerator(
            template_dir=template_dir,
            theme="showcase_react",
            selected_modules=selected,
        )
        output = tmp_path / "test_react_sel_map"
        gen.generate(project_name, output)

        missing = [
            ep for ep in mapping if ep != "poetry.lock" and not (output / ep).exists()
        ]
        assert not missing, (
            f"React+selection generated project missing {len(missing)} "
            f"file(s): {missing[:10]}"
        )

    # ------------------------------------------------------------------
    # Executable modes
    # ------------------------------------------------------------------

    def test_executable_files_have_correct_mode(self, tmp_path: Path) -> None:
        """manage.py and scripts/lint.sh must be executable.

        Note: start.sh is intentionally NOT executable — see
        ``_EXECUTABLE_EMITTED`` exclusion comment above.  This test
        reflects the actual production mode, not an aspirational
        docstring.
        """
        template_dir = self._get_template_dir()
        gen = ProjectGenerator(template_dir=template_dir, theme="showcase_react")
        output = tmp_path / "test_exec"
        gen.generate("validname", output)

        for emitted in self._EXECUTABLE_EMITTED:
            fpath = output / emitted
            assert fpath.exists(), f"{emitted} should exist"
            assert os.access(fpath, os.X_OK), f"{emitted} should be executable"

    def test_non_executable_files_not_executable(self, tmp_path: Path) -> None:
        """Non-executable mapped files must NOT have exec mode."""
        template_dir = self._get_template_dir()
        gen = ProjectGenerator(template_dir=template_dir, theme="showcase_react")
        output = tmp_path / "test_noexec"
        gen.generate("validname", output)

        non_exec_samples = (
            "Makefile",
            "pyproject.toml",
            "README.md",
        )
        for emitted in non_exec_samples:
            candidate = output / emitted
            if candidate.exists():
                assert not os.access(candidate, os.X_OK), (
                    f"{candidate} should NOT be executable"
                )
        # Also check a package file inside the project directory
        pkg_init = output / "validname" / "__init__.py"
        if pkg_init.exists():
            assert not os.access(pkg_init, os.X_OK), (
                f"{pkg_init} should NOT be executable"
            )

    # ------------------------------------------------------------------
    # Non-Jinja byte-preserving copy
    # ------------------------------------------------------------------

    def test_non_jinja_file_bytes_preserved(self, tmp_path: Path) -> None:
        """Non-Jinja theme files must be byte-identical (shutil.copy2)."""
        template_dir = self._get_template_dir()
        # Pick a representative non-Jinja source
        non_jinja_rel = "themes/showcase_react/src/lib/utils.ts"
        source_path = template_dir / non_jinja_rel
        assert source_path.exists(), f"Non-Jinja source not found: {source_path}"
        original = source_path.read_bytes()

        gen = ProjectGenerator(template_dir=template_dir, theme="showcase_react")
        output = tmp_path / "test_bytes"
        gen.generate("validname", output)

        emitted_path = output / "frontend" / "src" / "lib" / "utils.ts"
        assert emitted_path.exists(), "Emitted non-Jinja file not found"
        assert emitted_path.read_bytes() == original, (
            "Non-Jinja file must be byte-identical after generation"
        )

    def test_non_jinja_theme_root_index_html_routed_correctly(
        self, tmp_path: Path
    ) -> None:
        """frontend/index.html must be on the verbatim-copy path (SA104-CR-001 regression).

        The theme-root ``index.html`` only contains literal ``{{ project_name }}``
        text — no actual Jinja template logic. After removing the ``.j2`` suffix
        (and its ``{% raw %}`` wrapper), the file must be sourced from a non-.j2
        path so the generator routes it through the verbatim ``shutil.copy2`` path
        rather than Jinja rendering.

        This test provides the narrow durable regression guard that was missing
        when the file was accidentally left as a Jinja template.
        """
        template_dir = self._get_template_dir()
        mapping = get_generator_emission_mapping(template_dir, theme="showcase_react")

        # The mapping entry's source must not be a .j2 template
        src = mapping.get("frontend/index.html")
        assert src is not None, "frontend/index.html must be in the emission mapping"
        assert not src.endswith(".j2"), (
            f"frontend/index.html source {src!r} must not be a Jinja template"
        )

        # Verify the source file is read from the theme root
        source_path = template_dir / src
        assert source_path.exists(), (
            f"frontend/index.html source not found: {source_path}"
        )
        assert source_path.suffix == ".html", (
            f"Source file must be .html, got {source_path.suffix}"
        )

        # Confirm byte-identical output through a full generation
        gen = ProjectGenerator(template_dir=template_dir, theme="showcase_react")
        output = tmp_path / "test_cr001"
        gen.generate("validname", output)

        emitted = output / "frontend" / "index.html"
        assert emitted.exists(), "Emitted frontend/index.html not found"

        original = source_path.read_bytes()
        assert emitted.read_bytes() == original, (
            "frontend/index.html must be byte-identical after generation "
            "(verbatim copy, not Jinja render)"
        )

    # ------------------------------------------------------------------
    # Union mapping for SA66 (no duplicates, covers all themes)
    # ------------------------------------------------------------------

    def test_react_mapping_has_expected_files(self) -> None:
        """React theme mapping must contain expected files."""
        react_map = get_generator_emission_mapping(
            self._get_template_dir(), theme="showcase_react"
        )

        # React-specific files
        assert "frontend/src/App.tsx" in react_map
        assert "frontend/src/main.tsx" in react_map
        assert "frontend/package.json" in react_map

        # Shared files should be present
        assert "Makefile" in react_map


class TestSa90ExactManifestParity:
    """SA90 durable exact-manifest parity: every generated file's path, SHA-256
    content hash, and executable mode is pinned against a checked-in fixture.

    The fixture (``sa90_emission_manifests.json``) is built independently from
    current template generation, **not** derived from
    ``get_generator_emission_mapping`` or production output at test runtime.
    This means an omitted mapping entry will cause a test failure (the
    generated tree will contain a file the fixture does not expect, or the
    fixture expects a file the tree is missing), which the mapping-consumption
    tests cannot catch because they derive their expected set from the same
    mapping.

    ``poetry.lock`` is excluded from the fixture because it is a dynamically
    generated artifact whose content varies per environment.  All other emitted
    files are pinned.
    """

    _FIXTURE_PATH = (
        Path(__file__).parents[1] / "fixtures" / "sa90_emission_manifests.json"
    )

    _VARIANTS: dict[str, dict] = {
        "react_default": {
            "theme": "showcase_react",
            "selected_modules": None,
            "project_name": "testproject",
        },
        "react_empty": {
            "theme": "showcase_react",
            "selected_modules": [],
            "project_name": "testproject",
        },
        "react_selected": {
            "theme": "showcase_react",
            "selected_modules": ["blog", "forms", "social"],
            "project_name": "testproject",
        },
    }

    # Files that are inherently non-deterministic and excluded from
    # exact manifest comparison.
    _DYNAMIC_PATHS = frozenset({"poetry.lock"})

    _EXCLUDED_PREFIXES = (".venv/",)

    # ------------------------------------------------------------------
    # Fixture validation
    # ------------------------------------------------------------------

    def test_fixture_is_valid_json(self) -> None:
        """The checked-in fixture must be parseable JSON."""
        assert self._FIXTURE_PATH.exists(), f"Fixture not found at {self._FIXTURE_PATH}"
        data = json.loads(self._FIXTURE_PATH.read_text())
        assert "_provenance" in data, "Fixture must include _provenance section"
        for var_key in self._VARIANTS:
            assert var_key in data, f"Fixture missing variant {var_key!r}"

    def test_fixture_provenance_matches_variants(self) -> None:
        """The fixture's _provenance.variants must match this test's variant table."""
        data = json.loads(self._FIXTURE_PATH.read_text())
        prov = data.get("_provenance", {}).get("variants", {})
        for var_key, cfg in self._VARIANTS.items():
            pv = prov.get(var_key, {})
            assert pv.get("theme") == cfg["theme"], (
                f"Provenance theme mismatch for {var_key}"
            )
            assert pv.get("selected_modules") == cfg["selected_modules"], (
                f"Provenance selected_modules mismatch for {var_key}"
            )

    # ------------------------------------------------------------------
    # Manifest parity per variant
    # ------------------------------------------------------------------

    @pytest.mark.parametrize("variant", list(_VARIANTS.keys()))
    def test_generated_tree_matches_manifest(
        self, tmp_path: Path, variant: str
    ) -> None:
        """For each variant, every emitted file (except poetry.lock) must
        match the checked-in manifest's path, SHA-256 hash, and mode."""
        cfg = self._VARIANTS[variant]
        fixture = json.loads(self._FIXTURE_PATH.read_text())
        expected = fixture.get(variant, {})
        assert expected, f"No manifest data for variant {variant!r}"

        generator = ProjectGenerator(
            theme=cfg["theme"],
            selected_modules=cfg.get("selected_modules"),
        )
        output = tmp_path / variant
        generator.generate(cfg["project_name"], output)

        actual: dict[str, dict] = {}
        for fpath in sorted(output.rglob("*")):
            if not fpath.is_file():
                continue
            rel = str(fpath.relative_to(output))
            if rel in self._DYNAMIC_PATHS:
                continue
            if rel.startswith(self._EXCLUDED_PREFIXES):
                continue
            content = fpath.read_bytes()
            actual[rel] = {
                "mode": oct(os.stat(fpath).st_mode)[-3:],
                "sha256": hashlib.sha256(content).hexdigest(),
            }

        # Also exclude .venv/ entries from expected set
        expected = {
            k: v
            for k, v in expected.items()
            if not k.startswith(self._EXCLUDED_PREFIXES)
        }
        missing = set(expected.keys()) - set(actual.keys())
        extra = set(actual.keys()) - set(expected.keys())
        mismatch: list[str] = []

        for path, exp_entry in expected.items():
            if path not in actual:
                continue
            act = actual[path]
            if act["mode"] != exp_entry["mode"]:
                mismatch.append(
                    f"{path}: mode expected {exp_entry['mode']}, got {act['mode']}"
                )
            if act["sha256"] != exp_entry["sha256"]:
                mismatch.append(
                    f"{path}: sha256 expected {exp_entry['sha256']}, got {act['sha256']}"
                )

        # Build a single assertion message with all discrepancies
        errors: list[str] = []
        if missing:
            errors.append(
                f"Files in fixture but absent from generated tree ({len(missing)}):\n  "
                + "\n  ".join(sorted(missing)[:20])
            )
        if extra:
            errors.append(
                f"Files in generated tree but absent from fixture ({len(extra)}):\n  "
                + "\n  ".join(sorted(extra)[:20])
            )
        if mismatch:
            errors.append(
                f"Content/mode mismatches ({len(mismatch)}):\n  "
                + "\n  ".join(mismatch[:20])
            )

        assert not errors, (
            f"Variant {variant!r} manifest parity failure:\n" + "\n".join(errors)
        )

    # ------------------------------------------------------------------
    # Stability check: current run against itself
    # ------------------------------------------------------------------

    def test_zero_delta_regeneration_stable(self) -> None:
        """Generating the same variant twice must produce identical trees
        (no non-determinism beyond poetry.lock and .venv)."""
        import tempfile

        cfg = self._VARIANTS["react_default"]
        generator = ProjectGenerator(theme=cfg["theme"])

        def _capture(out_dir: Path) -> dict[str, str]:
            generator.generate(cfg["project_name"], out_dir)
            result: dict[str, str] = {}
            for fpath in sorted(out_dir.rglob("*")):
                if not fpath.is_file():
                    continue
                rel = str(fpath.relative_to(out_dir))
                if rel in self._DYNAMIC_PATHS:
                    continue
                if rel.startswith(self._EXCLUDED_PREFIXES):
                    continue
                result[rel] = hashlib.sha256(fpath.read_bytes()).hexdigest()
            return result

        base = Path(tempfile.mkdtemp())
        try:
            tree1 = _capture(base / "run1")
            tree2 = _capture(base / "run2")
            assert tree1 == tree2, (
                "Two successive generations of react_default produced different trees"
            )
        finally:
            import shutil

            shutil.rmtree(base, ignore_errors=True)
