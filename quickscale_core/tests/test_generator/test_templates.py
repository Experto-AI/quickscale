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


class TestMissingVariableErrors:
    """Verify templates handle missing variables appropriately."""

    def test_missing_project_name_renders_partial(self, jinja_env: Environment) -> None:
        """Test template renders with missing project_name using Jinja2 defaults."""
        template = jinja_env.get_template("manage.py.j2")
        output = template.render({})
        # Jinja2 default behavior renders undefined variables as empty strings
        # Production should use StrictUndefined for explicit failures
        assert ".settings" in output
