"""Tests for QuickScale project template rendering and validation."""

import ast
from pathlib import Path

import pytest
from jinja2 import Environment, FileSystemLoader


@pytest.fixture
def template_dir() -> Path:
    """Locate and return the templates directory path."""
    core_dir = Path(__file__).parent.parent.parent / "src" / "quickscale_core"
    templates_dir = core_dir / "generator" / "templates"
    assert templates_dir.exists(), f"Templates directory not found: {templates_dir}"
    return templates_dir


@pytest.fixture
def jinja_env(template_dir: Path) -> Environment:
    """Create a Jinja2 environment configured with template loader."""
    return Environment(loader=FileSystemLoader(str(template_dir)))


@pytest.fixture
def test_context() -> dict[str, str]:
    """Provide sample context data for template rendering tests."""
    return {
        "project_name": "testproject",
    }


class TestTemplateLoading:
    """Verify all project templates can be loaded by Jinja2."""

    def test_manage_py_loads(self, jinja_env: Environment) -> None:
        """Test manage.py template loads without errors."""
        template = jinja_env.get_template("manage.py.j2")
        assert template is not None

    def test_project_init_loads(self, jinja_env: Environment) -> None:
        """Test project __init__.py template loads without errors."""
        template = jinja_env.get_template("project_name/__init__.py.j2")
        assert template is not None

    def test_settings_init_loads(self, jinja_env: Environment) -> None:
        """Test settings __init__.py template loads without errors."""
        template = jinja_env.get_template("project_name/settings/__init__.py.j2")
        assert template is not None

    def test_settings_base_loads(self, jinja_env: Environment) -> None:
        """Test base settings template loads without errors."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        assert template is not None

    def test_settings_local_loads(self, jinja_env: Environment) -> None:
        """Test local settings template loads without errors."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        assert template is not None

    def test_settings_production_loads(self, jinja_env: Environment) -> None:
        """Test production settings template loads without errors."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        assert template is not None

    def test_urls_loads(self, jinja_env: Environment) -> None:
        """Test URL configuration template loads without errors."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        assert template is not None

    def test_wsgi_loads(self, jinja_env: Environment) -> None:
        """Test WSGI configuration template loads without errors."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        assert template is not None

    def test_asgi_loads(self, jinja_env: Environment) -> None:
        """Test ASGI configuration template loads without errors."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        assert template is not None

    def test_base_html_loads(self, jinja_env: Environment) -> None:
        """Test base HTML template loads without errors."""
        template = jinja_env.get_template("templates/base.html.j2")
        assert template is not None

    def test_index_html_loads(self, jinja_env: Environment) -> None:
        """Test index HTML template loads without errors."""
        template = jinja_env.get_template("templates/index.html.j2")
        assert template is not None

    def test_style_css_loads(self, jinja_env: Environment) -> None:
        """Test CSS stylesheet template loads without errors."""
        template = jinja_env.get_template("static/css/style.css.j2")
        assert template is not None


class TestTemplateRendering:
    """Verify templates render correctly with sample context data."""

    def test_manage_py_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test manage.py renders with project name and shebang."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "#!/usr/bin/env python" in output

    def test_settings_base_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base settings renders with project name."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_settings_local_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test local settings renders with project name."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_settings_production_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test production settings renders with project name."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_urls_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test URL configuration renders with project name."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_wsgi_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test WSGI configuration renders with project name."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_asgi_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test ASGI configuration renders with project name."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output

    def test_base_html_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test base HTML template renders with project name."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output
        assert "<!DOCTYPE html>" in output

    def test_index_html_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test index HTML template renders with project name."""
        template = jinja_env.get_template("templates/index.html.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output
        assert "Welcome to" in output

    def test_style_css_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test CSS stylesheet template renders with project name."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert output is not None
        assert "testproject" in output
        assert "body {" in output


class TestPythonSyntaxValidity:
    """Verify rendered Python templates produce syntactically valid code."""

    def test_manage_py_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered manage.py produces valid Python syntax."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_settings_base_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered base settings produces valid Python syntax."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_settings_local_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered local settings produces valid Python syntax."""
        template = jinja_env.get_template("project_name/settings/local.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_settings_production_valid_python(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test rendered production settings produces valid Python syntax."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_urls_valid_python(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test rendered URL configuration produces valid Python syntax."""
        template = jinja_env.get_template("project_name/urls.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_wsgi_valid_python(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test rendered WSGI configuration produces valid Python syntax."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        output = template.render(test_context)
        ast.parse(output)

    def test_asgi_valid_python(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test rendered ASGI configuration produces valid Python syntax."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        output = template.render(test_context)
        ast.parse(output)


class TestRequiredVariables:
    """Verify templates correctly use required context variables."""

    def test_project_name_in_manage_py(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in manage.py settings path."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render(test_context)
        assert "testproject.settings" in output

    def test_project_name_in_settings(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "testproject" in output

    def test_project_name_in_wsgi(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in WSGI settings path."""
        template = jinja_env.get_template("project_name/wsgi.py.j2")
        output = template.render(test_context)
        assert "testproject.settings" in output

    def test_project_name_in_asgi(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test project_name variable is correctly rendered in ASGI settings path."""
        template = jinja_env.get_template("project_name/asgi.py.j2")
        output = template.render(test_context)
        assert "testproject.settings" in output


class TestProductionReadyFeatures:
    """Verify production-ready security and configuration features are present."""

    def test_security_middleware_in_base(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test security middleware is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "SecurityMiddleware" in output
        assert "WhiteNoiseMiddleware" in output

    def test_logging_configured(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test logging with rotating file handler is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "LOGGING" in output
        assert "RotatingFileHandler" in output

    def test_production_security_settings(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test production security settings include SSL and cookie security."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        assert "SECURE_SSL_REDIRECT" in output
        assert "SESSION_COOKIE_SECURE" in output
        assert "CSRF_COOKIE_SECURE" in output
        assert "SECURE_HSTS_SECONDS" in output

    def test_postgresql_in_production(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test production settings configure PostgreSQL database."""
        template = jinja_env.get_template("project_name/settings/production.py.j2")
        output = template.render(test_context)
        assert "postgresql" in output

    def test_whitenoise_in_base(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test WhiteNoise static file serving is configured in base settings."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "whitenoise" in output.lower()

    def test_decouple_used(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test python-decouple is used for environment-based configuration."""
        template = jinja_env.get_template("project_name/settings/base.py.j2")
        output = template.render(test_context)
        assert "from decouple import config" in output
        assert "SECRET_KEY = config(" in output


class TestHTMLTemplateStructure:
    """Verify HTML templates contain required structural elements."""

    def test_base_html_has_doctype(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template includes DOCTYPE declaration."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert "<!DOCTYPE html>" in output

    def test_base_html_has_meta_viewport(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template includes responsive viewport meta tag."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert 'name="viewport"' in output
        assert "width=device-width" in output

    def test_base_html_has_blocks(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template includes extensible blocks."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert "{% block title %}" in output or "<title>" in output
        assert "{% block content %}" in output
        assert "{% block extra_js %}" in output
        assert "{% block extra_css %}" in output

    def test_base_html_links_to_css(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test base HTML template links to stylesheet."""
        template = jinja_env.get_template("templates/base.html.j2")
        output = template.render(test_context)
        assert "style.css" in output

    def test_index_html_extends_base(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test index HTML template extends base template."""
        # Verify template loads successfully
        jinja_env.get_template("templates/index.html.j2")
        # Read the raw template file to check extends directive
        import pathlib

        template_path = pathlib.Path(jinja_env.loader.searchpath[0]) / "templates" / "index.html.j2"
        source = template_path.read_text()
        assert "{% extends" in source or "{%raw%}{% extends" in source
        assert "base.html" in source

    def test_index_html_has_welcome_message(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test index HTML template includes welcome message."""
        template = jinja_env.get_template("templates/index.html.j2")
        output = template.render(test_context)
        assert "Welcome to testproject" in output

    def test_index_html_has_next_steps(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test index HTML template includes next steps guidance."""
        template = jinja_env.get_template("templates/index.html.j2")
        output = template.render(test_context)
        assert "Next Steps" in output
        assert "manage.py" in output


class TestCSSTemplateStructure:
    """Verify CSS templates contain required styling rules."""

    def test_css_has_body_styles(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes body element styling."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "body {" in output
        assert "font-family:" in output

    def test_css_has_responsive_design(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes responsive media queries."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "@media" in output
        assert "max-width" in output

    def test_css_has_header_styles(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes header element styling."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "header" in output

    def test_css_has_footer_styles(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test CSS template includes footer element styling."""
        template = jinja_env.get_template("static/css/style.css.j2")
        output = template.render(test_context)
        assert "footer" in output


class TestMissingVariableErrors:
    """Verify templates handle missing variables appropriately."""

    def test_missing_project_name_renders_partial(self, jinja_env: Environment) -> None:
        """Test template renders with missing project_name using Jinja2 defaults."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render({})
        # Jinja2 default behavior renders undefined variables as empty strings
        # Production should use StrictUndefined for explicit failures
        assert ".settings" in output


class TestDevOpsTemplateLoading:
    """Verify all DevOps templates can be loaded by Jinja2."""

    def test_pyproject_toml_loads(self, jinja_env: Environment) -> None:
        """Test pyproject.toml template loads without errors."""
        template = jinja_env.get_template("pyproject.toml.j2")
        assert template is not None

    def test_dockerfile_loads(self, jinja_env: Environment) -> None:
        """Test Dockerfile template loads without errors."""
        template = jinja_env.get_template("Dockerfile.j2")
        assert template is not None

    def test_docker_compose_loads(self, jinja_env: Environment) -> None:
        """Test docker-compose.yml template loads without errors."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        assert template is not None

    def test_dockerignore_loads(self, jinja_env: Environment) -> None:
        """Test .dockerignore template loads without errors."""
        template = jinja_env.get_template(".dockerignore.j2")
        assert template is not None

    def test_env_example_loads(self, jinja_env: Environment) -> None:
        """Test .env.example template loads without errors."""
        template = jinja_env.get_template(".env.example.j2")
        assert template is not None

    def test_gitignore_loads(self, jinja_env: Environment) -> None:
        """Test .gitignore template loads without errors."""
        template = jinja_env.get_template(".gitignore.j2")
        assert template is not None

    def test_editorconfig_loads(self, jinja_env: Environment) -> None:
        """Test .editorconfig template loads without errors."""
        template = jinja_env.get_template(".editorconfig.j2")
        assert template is not None


class TestDevOpsTemplateRendering:
    """Verify DevOps templates render correctly with sample context data."""

    def test_pyproject_toml_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml renders with project name."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "[tool.poetry]" in output

    def test_dockerfile_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test Dockerfile renders with project name."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "FROM python:" in output

    def test_docker_compose_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml renders with project name."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "version:" in output

    def test_dockerignore_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .dockerignore renders correctly."""
        template = jinja_env.get_template(".dockerignore.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "__pycache__" in output
        assert ".git" in output

    def test_env_example_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .env.example renders with project name."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "testproject" in output
        assert "SECRET_KEY=" in output

    def test_gitignore_renders(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .gitignore renders correctly."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "__pycache__" in output
        assert ".env" in output

    def test_editorconfig_renders(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .editorconfig renders correctly."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert output is not None
        assert len(output) > 0
        assert "root = true" in output
        assert "indent_style" in output


class TestPyprojectTomlContent:
    """Verify pyproject.toml contains required production dependencies and configuration."""

    def test_django_dependency(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test pyproject.toml includes Django dependency."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "Django" in output
        assert ">=5.0,<6.0" in output

    def test_postgresql_driver(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test pyproject.toml includes PostgreSQL driver."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "psycopg2-binary" in output

    def test_environment_config(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test pyproject.toml includes environment configuration library."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "python-decouple" in output

    def test_whitenoise_static_files(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes WhiteNoise for static files."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "whitenoise" in output

    def test_gunicorn_server(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test pyproject.toml includes Gunicorn production server."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "gunicorn" in output

    def test_dev_dependencies(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test pyproject.toml includes development dependencies."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "[tool.poetry.group.dev.dependencies]" in output
        assert "pytest" in output
        assert "pytest-django" in output
        assert "ruff" in output
        assert "mypy" in output

    def test_pytest_configuration(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test pyproject.toml includes pytest configuration."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "[tool.pytest.ini_options]" in output
        assert "DJANGO_SETTINGS_MODULE" in output

    def test_ruff_configuration(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test pyproject.toml includes ruff formatter and linter configuration."""
        template = jinja_env.get_template("pyproject.toml.j2")
        output = template.render(test_context)
        assert "[tool.ruff]" in output
        assert "select" in output
        assert "line-length" in output
        # Verify comment about ruff format replacing black
        assert "handled by ruff format" in output


class TestDockerfileContent:
    """Verify Dockerfile contains production-ready multi-stage build configuration."""

    def test_multi_stage_build(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test Dockerfile uses multi-stage build pattern."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "FROM python:3.11-slim as builder" in output
        assert "FROM python:3.11-slim" in output

    def test_non_root_user(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test Dockerfile creates and uses non-root user."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "groupadd" in output
        assert "useradd" in output
        assert "USER django" in output

    def test_poetry_installation(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test Dockerfile installs Poetry for dependency management."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "poetry" in output.lower()

    def test_optimized_layers(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test Dockerfile optimizes layer caching with dependency files first."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "COPY pyproject.toml poetry.lock" in output
        # Dependencies installed before copying application code
        lines = output.split("\n")
        poetry_install_idx = next(
            i for i, line in enumerate(lines) if "poetry install" in line.lower()
        )
        copy_app_idx = next(i for i, line in enumerate(lines) if "COPY --chown" in line)
        assert poetry_install_idx < copy_app_idx

    def test_healthcheck(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test Dockerfile includes health check."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "HEALTHCHECK" in output

    def test_gunicorn_command(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test Dockerfile runs Gunicorn production server."""
        template = jinja_env.get_template("Dockerfile.j2")
        output = template.render(test_context)
        assert "gunicorn" in output
        assert "testproject.wsgi:application" in output


class TestDockerComposeContent:
    """Verify docker-compose.yml contains complete development environment."""

    def test_postgres_service(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test docker-compose.yml includes PostgreSQL service."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "db:" in output
        assert "postgres:" in output
        assert "POSTGRES_DB" in output

    def test_web_service(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test docker-compose.yml includes web service."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "web:" in output
        assert "build:" in output

    def test_persistent_volumes(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test docker-compose.yml defines persistent volumes."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "volumes:" in output
        assert "postgres_data:" in output
        assert "static_volume:" in output
        assert "media_volume:" in output

    def test_healthchecks(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test docker-compose.yml includes healthchecks."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "healthcheck:" in output
        assert "condition: service_healthy" in output

    def test_environment_variables(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test docker-compose.yml configures environment variables."""
        template = jinja_env.get_template("docker-compose.yml.j2")
        output = template.render(test_context)
        assert "DATABASE_URL" in output
        assert "DJANGO_SETTINGS_MODULE" in output


class TestEnvExampleContent:
    """Verify .env.example contains all required environment variables."""

    def test_secret_key(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .env.example includes SECRET_KEY."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "SECRET_KEY=" in output
        assert "testproject" in output

    def test_debug_flag(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .env.example includes DEBUG flag."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "DEBUG=" in output

    def test_allowed_hosts(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .env.example includes ALLOWED_HOSTS."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "ALLOWED_HOSTS=" in output

    def test_database_url(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .env.example includes DATABASE_URL with PostgreSQL."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "DATABASE_URL=" in output
        assert "postgresql://" in output
        assert "testproject" in output

    def test_helpful_comments(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .env.example includes explanatory comments."""
        template = jinja_env.get_template(".env.example.j2")
        output = template.render(test_context)
        assert "#" in output
        assert "SECURITY WARNING" in output


class TestGitignoreContent:
    """Verify .gitignore excludes appropriate files and directories."""

    def test_python_artifacts(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .gitignore excludes Python artifacts."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert "__pycache__" in output
        assert "*.py[cod]" in output  # Matches .pyc, .pyo, .pyd

    def test_virtual_environments(
        self, jinja_env: Environment, test_context: dict[str, str]
    ) -> None:
        """Test .gitignore excludes virtual environments."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".venv" in output
        assert "venv/" in output

    def test_django_artifacts(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .gitignore excludes Django-specific files."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert "db.sqlite3" in output
        assert "/media" in output
        assert "/staticfiles" in output

    def test_environment_files(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .gitignore excludes environment variable files."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".env" in output

    def test_ide_files(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .gitignore excludes IDE-specific files."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".vscode/" in output
        assert ".idea/" in output

    def test_testing_artifacts(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .gitignore excludes testing artifacts."""
        template = jinja_env.get_template(".gitignore.j2")
        output = template.render(test_context)
        assert ".pytest_cache" in output
        assert ".coverage" in output


class TestEditorconfigContent:
    """Verify .editorconfig defines consistent editor settings."""

    def test_root_declaration(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .editorconfig declares root = true."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "root = true" in output

    def test_charset_setting(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .editorconfig sets UTF-8 charset."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "charset = utf-8" in output

    def test_line_endings(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .editorconfig sets line endings."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "end_of_line" in output

    def test_python_indent(self, jinja_env: Environment, test_context: dict[str, str]) -> None:
        """Test .editorconfig sets Python indentation to 4 spaces."""
        template = jinja_env.get_template(".editorconfig.j2")
        output = template.render(test_context)
        assert "[*.{py,pyi}]" in output or "[*.py]" in output
        assert "indent_size = 4" in output
