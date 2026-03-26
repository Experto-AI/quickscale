"""Additional tests for ProjectGenerator covering uncovered branches."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from quickscale_core.generator import ProjectGenerator


class TestProjectGeneratorThemeValidation:
    """Tests for theme validation edge cases in __init__."""

    def test_init_raises_value_error_when_theme_dir_missing_in_custom_template_dir(
        self, tmp_path: Path
    ) -> None:
        """ValueError raised when custom template_dir has no theme subdirectory."""
        template_dir = tmp_path / "templates"
        template_dir.mkdir()
        # Do NOT create themes/showcase_html – theme name is valid but dir is missing

        with pytest.raises(ValueError, match="Theme directory not found"):
            ProjectGenerator(template_dir=template_dir, theme="showcase_html")

    def test_init_rejects_removed_htmx_theme(self, tmp_path: Path) -> None:
        """ValueError raised for removed showcase_htmx theme."""
        template_dir = tmp_path / "mytemplates"
        template_dir.mkdir()
        # Create a supported theme dir so validation fails on the theme value itself.
        (template_dir / "themes" / "showcase_html").mkdir(parents=True)

        with pytest.raises(ValueError, match="Invalid theme 'showcase_htmx'"):
            ProjectGenerator(template_dir=template_dir, theme="showcase_htmx")


class TestGetThemeTemplatePath:
    """Tests for _get_theme_template_path covering the common/ fallback branch."""

    def _make_generator_with_custom_templates(self, tmp_path: Path) -> ProjectGenerator:
        """Helper: create a minimal template dir and a generator using it."""
        template_dir = tmp_path / "templates"
        (template_dir / "themes" / "showcase_html").mkdir(parents=True)
        return ProjectGenerator(template_dir=template_dir, theme="showcase_html")

    def test_returns_theme_path_when_theme_template_exists(
        self, tmp_path: Path
    ) -> None:
        """Theme-specific template is preferred over common template."""
        template_dir = tmp_path / "templates"
        theme_dir = template_dir / "themes" / "showcase_html"
        theme_dir.mkdir(parents=True)
        # Create the theme-specific template
        (theme_dir / "mytemplate.html.j2").write_text("{{ project_name }}")

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_html")
        result = generator._get_theme_template_path("mytemplate.html.j2")

        assert result == "themes/showcase_html/mytemplate.html.j2"

    def test_returns_common_path_when_only_common_template_exists(
        self, tmp_path: Path
    ) -> None:
        """Returns common/ path when theme template is absent but common exists."""
        template_dir = tmp_path / "templates"
        theme_dir = template_dir / "themes" / "showcase_html"
        theme_dir.mkdir(parents=True)
        common_dir = template_dir / "common"
        common_dir.mkdir()
        # Only create the common template, not the theme-specific one
        (common_dir / "fallback.html.j2").write_text("fallback content")

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_html")
        result = generator._get_theme_template_path("fallback.html.j2")

        assert result == "common/fallback.html.j2"

    def test_returns_template_name_when_neither_theme_nor_common_exists(
        self, tmp_path: Path
    ) -> None:
        """Falls back to bare template name for backward compatibility."""
        template_dir = tmp_path / "templates"
        (template_dir / "themes" / "showcase_html").mkdir(parents=True)

        generator = ProjectGenerator(template_dir=template_dir, theme="showcase_html")
        result = generator._get_theme_template_path("some_root_template.j2")

        assert result == "some_root_template.j2"


class TestGenerateParentDirectoryErrors:
    """Tests for PermissionError branches in generate() parent directory handling."""

    def test_generate_raises_permission_error_when_ensure_directory_fails(
        self, tmp_path: Path
    ) -> None:
        """PermissionError raised when parent dir creation fails with OSError."""
        generator = ProjectGenerator(theme="showcase_html")
        # Use a nested path where parent doesn't exist
        output_path = tmp_path / "nonexistent_parent" / "subdir" / "myproject"

        with patch(
            "quickscale_core.generator.generator.ensure_directory",
            side_effect=OSError("disk full"),
        ):
            with pytest.raises(PermissionError, match="Cannot create parent directory"):
                generator.generate("myproject", output_path)

    def test_generate_raises_permission_error_for_unwritable_parent(
        self, tmp_path: Path
    ) -> None:
        """PermissionError raised when parent directory exists but is not writable."""
        generator = ProjectGenerator(theme="showcase_html")
        readonly_parent = tmp_path / "readonly_parent"
        readonly_parent.mkdir()
        readonly_parent.chmod(0o444)

        try:
            with pytest.raises(PermissionError):
                generator.generate("myproject", readonly_parent / "output")
        finally:
            readonly_parent.chmod(0o755)

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


class TestGeneratePoetryLock:
    """Tests for _generate_poetry_lock covering FileNotFoundError branch."""

    def test_generate_poetry_lock_handles_file_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture
    ) -> None:
        """Prints warning when poetry executable is not found; does not raise."""
        generator = ProjectGenerator(theme="showcase_html")
        project_path = tmp_path / "fakeproject"
        project_path.mkdir()

        with patch("subprocess.run", side_effect=FileNotFoundError("poetry not found")):
            # Should not raise any exception
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
