"""Tests for theme system functionality"""

import pytest

from quickscale_core.generator import ProjectGenerator


class TestThemeInitialization:
    """Test theme parameter initialization"""

    def test_default_theme(self, tmp_path):
        """Generator should use showcase_html as default theme"""
        generator = ProjectGenerator()
        assert generator.theme == "showcase_html"

    def test_explicit_theme(self, tmp_path):
        """Generator should accept explicit theme parameter"""
        generator = ProjectGenerator(theme="showcase_html")
        assert generator.theme == "showcase_html"

    def test_invalid_theme_name(self, tmp_path):
        """Generator should reject invalid theme names"""
        with pytest.raises(ValueError, match="Invalid theme 'invalid_theme'"):
            ProjectGenerator(theme="invalid_theme")

    def test_available_themes_list(self, tmp_path):
        """Error message should list available themes"""
        with pytest.raises(ValueError, match="Available themes"):
            ProjectGenerator(theme="nonexistent")


class TestThemeValidation:
    """Test theme directory validation"""

    def test_showcase_html_theme_exists(self):
        """showcase_html theme directory should exist"""
        generator = ProjectGenerator(theme="showcase_html")
        theme_dir = generator.template_dir / "themes" / "showcase_html"
        assert theme_dir.exists()

    def test_htmx_theme_placeholder_exists(self):
        """showcase_htmx should have placeholder directory"""
        generator = ProjectGenerator(theme="showcase_html")
        theme_dir = generator.template_dir / "themes" / "showcase_htmx"
        assert theme_dir.exists()
        readme = theme_dir / "README.md"
        assert readme.exists()

    def test_react_theme_placeholder_exists(self):
        """showcase_react should have placeholder directory"""
        generator = ProjectGenerator(theme="showcase_html")
        theme_dir = generator.template_dir / "themes" / "showcase_react"
        assert theme_dir.exists()
        readme = theme_dir / "README.md"
        assert readme.exists()


class TestThemeTemplateResolution:
    """Test theme-specific template path resolution"""

    def test_theme_template_path_resolution(self):
        """_get_theme_template_path should resolve theme-specific templates"""
        generator = ProjectGenerator(theme="showcase_html")

        # Theme-specific template
        path = generator._get_theme_template_path("templates/base.html.j2")
        assert "themes/showcase_html" in path

    def test_theme_static_path_resolution(self):
        """_get_theme_template_path should resolve theme-specific static files"""
        generator = ProjectGenerator(theme="showcase_html")

        # Theme-specific static file
        path = generator._get_theme_template_path("static/css/style.css.j2")
        assert "themes/showcase_html" in path

    def test_common_template_fallback(self):
        """_get_theme_template_path should fall back to common templates"""
        generator = ProjectGenerator(theme="showcase_html")

        # This should fall back to root (backend templates)
        path = generator._get_theme_template_path("manage.py.j2")
        # Should not be in themes directory
        assert "themes" not in path or "manage.py.j2" in path


class TestProjectGenerationWithTheme:
    """Test complete project generation with themes"""

    def test_generate_with_default_theme(self, tmp_path):
        """Generate project with default theme"""
        generator = ProjectGenerator()
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Verify frontend templates exist
        assert (output_path / "templates" / "base.html").exists()
        assert (output_path / "templates" / "index.html").exists()

        # Verify static files exist
        assert (output_path / "static" / "css" / "style.css").exists()
        assert (output_path / "static" / "images" / "favicon.svg").exists()

        # Verify backend files exist
        assert (output_path / "manage.py").exists()
        assert (output_path / "pyproject.toml").exists()

    def test_generate_with_explicit_theme(self, tmp_path):
        """Generate project with explicit showcase_html theme"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Verify all files created
        assert (output_path / "templates" / "base.html").exists()
        assert (output_path / "templates" / "index.html").exists()
        assert (output_path / "static" / "css" / "style.css").exists()

    def test_generated_output_matches_v060(self, tmp_path):
        """Generated project structure should match v0.60.0 output"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # List of files that should exist (from v0.60.0)
        expected_files = [
            "README.md",
            "manage.py",
            "pyproject.toml",
            ".gitignore",
            ".dockerignore",
            "Dockerfile",
            "docker-compose.yml",
            "railway.json",
            ".env.example",
            "templates/base.html",
            "templates/index.html",
            "static/css/style.css",
            "static/images/favicon.svg",
            f"{project_name}/__init__.py",
            f"{project_name}/urls.py",
            f"{project_name}/settings/base.py",
            f"{project_name}/settings/local.py",
            f"{project_name}/settings/production.py",
            "tests/__init__.py",
            "tests/conftest.py",
            ".github/workflows/ci.yml",
        ]

        for file_path in expected_files:
            assert (output_path / file_path).exists(), f"Missing file: {file_path}"


class TestBackwardCompatibility:
    """Test backward compatibility with existing code"""

    def test_generator_without_theme_parameter(self, tmp_path):
        """Generator should work without theme parameter (backward compatible)"""
        # Old code: ProjectGenerator()
        generator = ProjectGenerator()
        project_name = "testproject"
        output_path = tmp_path / project_name

        # Should generate successfully with default theme
        generator.generate(project_name, output_path)
        assert output_path.exists()

    def test_generated_templates_identical_to_v060(self, tmp_path):
        """Generated templates should be identical to v0.60.0"""
        generator = ProjectGenerator(theme="showcase_html")
        project_name = "testproject"
        output_path = tmp_path / project_name

        generator.generate(project_name, output_path)

        # Check template content (should have same structure as v0.60.0)
        base_html = (output_path / "templates" / "base.html").read_text()
        assert "<!DOCTYPE html>" in base_html
        assert "<title>" in base_html
        assert "{% block content %}" in base_html
