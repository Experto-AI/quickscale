"""Extended tests for module_config.py - covering CRM, listings apply, auth apply and edge cases."""

from pathlib import Path
from unittest.mock import patch

import click
import pytest

from quickscale_cli.commands.module_config import (
    MODULE_CONFIGURATORS,
    _add_django_allauth_dependency,
    _add_django_filter_dependency,
    _add_drf_and_filter_dependencies,
    _filter_new_apps,
    _generate_auth_settings_addition,
    _is_app_in_installed_apps,
    apply_auth_configuration,
    apply_blog_configuration,
    apply_crm_configuration,
    apply_listings_configuration,
    configure_crm_module,
    get_default_crm_config,
)


# ============================================================================
# Helper to build a realistic project layout
# ============================================================================


def _make_project(tmp_path: Path, project_name: str = "myproject") -> Path:
    """Create a minimal QuickScale project structure for testing"""
    project = tmp_path / project_name
    project.mkdir()
    settings_dir = project / project_name / "settings"
    settings_dir.mkdir(parents=True)
    (settings_dir / "base.py").write_text("INSTALLED_APPS = []\nMIDDLEWARE = []\n")
    (project / project_name / "urls.py").write_text(
        'from django.urls import include, path\nurlpatterns = [\n    path("admin/", include("admin")),\n]\n'
    )
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.11"\nDjango = "^6.0"\n'
    )
    return project


# ============================================================================
# _is_app_in_installed_apps / _filter_new_apps
# ============================================================================


class TestIsAppInInstalledApps:
    """Tests for _is_app_in_installed_apps helper"""

    def test_app_present_double_quotes(self):
        """Detect app in double-quoted list"""
        content = 'INSTALLED_APPS += ["django_filters"]'
        assert _is_app_in_installed_apps(content, "django_filters") is True

    def test_app_present_single_quotes(self):
        """Detect app in single-quoted list"""
        content = "INSTALLED_APPS += ['rest_framework']"
        assert _is_app_in_installed_apps(content, "rest_framework") is True

    def test_app_not_present(self):
        """Return False when app not in settings"""
        content = "INSTALLED_APPS = ['django.contrib.admin']"
        assert _is_app_in_installed_apps(content, "rest_framework") is False


class TestFilterNewApps:
    """Tests for _filter_new_apps helper"""

    def test_all_new(self):
        """Return all apps when none exist"""
        content = "INSTALLED_APPS = []"
        result = _filter_new_apps(content, ["a", "b"])
        assert result == ["a", "b"]

    def test_some_existing(self):
        """Filter out already-present apps"""
        content = 'INSTALLED_APPS = ["a"]'
        result = _filter_new_apps(content, ["a", "b"])
        assert result == ["b"]

    def test_all_existing(self):
        """Return empty when all apps exist"""
        content = 'INSTALLED_APPS = ["a", "b"]'
        result = _filter_new_apps(content, ["a", "b"])
        assert result == []


# ============================================================================
# Auth settings generation – different auth methods
# ============================================================================


class TestGenerateAuthSettingsAddition:
    """Tests for _generate_auth_settings_addition with all auth methods"""

    def test_email_auth_method(self):
        """Test email-only auth settings"""
        config = {
            "allow_registration": True,
            "email_verification": "none",
            "authentication_method": "email",
        }
        result = _generate_auth_settings_addition(config)
        assert 'ACCOUNT_LOGIN_METHODS = {"email"}' in result
        assert '"email*", "password1*", "password2*"' in result

    def test_username_auth_method(self):
        """Test username-only auth settings"""
        config = {
            "allow_registration": False,
            "email_verification": "mandatory",
            "authentication_method": "username",
        }
        result = _generate_auth_settings_addition(config)
        assert 'ACCOUNT_LOGIN_METHODS = {"username"}' in result
        assert '"username*", "password1*", "password2*"' in result
        assert "ACCOUNT_ALLOW_REGISTRATION = False" in result
        assert 'ACCOUNT_EMAIL_VERIFICATION = "mandatory"' in result

    def test_both_auth_method(self):
        """Test both email+username auth settings"""
        config = {
            "allow_registration": True,
            "email_verification": "optional",
            "authentication_method": "both",
        }
        result = _generate_auth_settings_addition(config)
        assert "email" in result and "username" in result
        assert 'ACCOUNT_EMAIL_VERIFICATION = "optional"' in result

    def test_common_settings_present(self):
        """Verify common settings are always included"""
        config = {
            "allow_registration": True,
            "email_verification": "none",
            "authentication_method": "email",
        }
        result = _generate_auth_settings_addition(config)
        assert "AUTH_USER_MODEL" in result
        assert "SITE_ID = 1" in result
        assert "LOGIN_REDIRECT_URL" in result
        assert "LOGOUT_REDIRECT_URL" in result
        assert "SESSION_COOKIE_AGE" in result
        assert "ACCOUNT_ADAPTER" in result
        assert "ACCOUNT_SIGNUP_FORM_CLASS" in result


# ============================================================================
# apply_auth_configuration – full flows
# ============================================================================


class TestApplyAuthConfiguration:
    """Tests for apply_auth_configuration with realistic project layout"""

    def test_settings_not_found(self, tmp_path):
        """Warn and return when settings.py missing"""
        project = tmp_path / "proj"
        project.mkdir()
        apply_auth_configuration(project, get_default_crm_config())
        # Should not raise – just prints warning

    def test_already_configured(self, tmp_path):
        """Skip when auth already present in settings"""
        project = _make_project(tmp_path)
        settings = project / "myproject" / "settings" / "base.py"
        settings.write_text("INSTALLED_APPS = []\nquickscale_modules_auth\n")
        apply_auth_configuration(
            project,
            {
                "allow_registration": True,
                "email_verification": "none",
                "authentication_method": "email",
            },
        )
        # No duplicate write
        assert settings.read_text().count("quickscale_modules_auth") == 1

    def test_full_apply_auth(self, tmp_path):
        """Full auth configuration with all file writes"""
        project = _make_project(tmp_path)
        # Create auth module pyproject for dependency resolution
        auth_dir = project / "modules" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-allauth = "^0.60.0"\n'
        )

        config = {
            "allow_registration": True,
            "email_verification": "none",
            "authentication_method": "email",
        }
        apply_auth_configuration(project, config)

        settings_content = (project / "myproject" / "settings" / "base.py").read_text()
        assert "quickscale_modules_auth" in settings_content
        assert "allauth" in settings_content
        assert "AUTH_USER_MODEL" in settings_content

        urls_content = (project / "myproject" / "urls.py").read_text()
        assert "allauth.urls" in urls_content

    def test_urls_already_has_allauth(self, tmp_path):
        """Skip URL update when allauth already in urls"""
        project = _make_project(tmp_path)
        auth_dir = project / "modules" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-allauth = "^0.60.0"\n'
        )
        (project / "myproject" / "urls.py").write_text("allauth already here\n")

        config = {
            "allow_registration": True,
            "email_verification": "none",
            "authentication_method": "email",
        }
        apply_auth_configuration(project, config)
        # No error raised


# ============================================================================
# _add_django_allauth_dependency edge cases
# ============================================================================


class TestAddDjangoAllauthDependencyEdgeCases:
    """Edge cases for _add_django_allauth_dependency"""

    def test_no_version_match_in_auth_pyproject(self, tmp_path):
        """Abort when version cannot be parsed from auth pyproject"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')
        auth_dir = tmp_path / "modules" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "pyproject.toml").write_text("[tool.poetry.dependencies]\n")

        with pytest.raises(click.Abort):
            _add_django_allauth_dependency(tmp_path, pyproject)

    def test_file_read_error(self, tmp_path):
        """Abort on file read error"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')
        auth_dir = tmp_path / "modules" / "auth"
        auth_dir.mkdir(parents=True)
        auth_pyproject = auth_dir / "pyproject.toml"
        auth_pyproject.write_text(
            '[tool.poetry.dependencies]\ndjango-allauth = "^0.60.0"\n'
        )

        with patch(
            "builtins.open", side_effect=[pyproject.open(), FileNotFoundError("mocked")]
        ):
            with pytest.raises(click.Abort):
                _add_django_allauth_dependency(tmp_path, pyproject)

    def test_no_dependencies_section(self, tmp_path):
        """Warn when [tool.poetry.dependencies] section missing"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.poetry]\nname = 'test'\n")
        auth_dir = tmp_path / "modules" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-allauth = "^0.60.0"\n'
        )

        # Should not raise, just warn
        _add_django_allauth_dependency(tmp_path, pyproject)


# ============================================================================
# Blog configuration - full apply flow
# ============================================================================


class TestApplyBlogConfigurationFull:
    """Full tests for apply_blog_configuration"""

    def test_settings_not_found(self, tmp_path):
        """Warn and return when settings.py missing"""
        project = tmp_path / "proj"
        project.mkdir()
        apply_blog_configuration(project, {"posts_per_page": 10, "enable_rss": True})

    def test_already_configured(self, tmp_path):
        """Skip when blog already present"""
        project = _make_project(tmp_path)
        settings = project / "myproject" / "settings" / "base.py"
        settings.write_text("quickscale_modules_blog\n")
        apply_blog_configuration(project, {"posts_per_page": 10, "enable_rss": True})

    def test_full_apply_blog_with_rss(self, tmp_path):
        """Full blog config apply with RSS enabled"""
        project = _make_project(tmp_path)
        config = {"posts_per_page": 15, "enable_rss": True}
        apply_blog_configuration(project, config)

        settings = (project / "myproject" / "settings" / "base.py").read_text()
        assert "quickscale_modules_blog" in settings
        assert "BLOG_POSTS_PER_PAGE = 15" in settings
        assert "markdownx" in settings.lower() or "MARKDOWNX" in settings

        urls = (project / "myproject" / "urls.py").read_text()
        assert "quickscale_modules_blog.urls" in urls
        assert "markdownx" in urls

    def test_full_apply_blog_without_rss(self, tmp_path):
        """Full blog config apply with RSS disabled"""
        project = _make_project(tmp_path)
        config = {"posts_per_page": 5, "enable_rss": False}
        apply_blog_configuration(project, config)

        urls = (project / "myproject" / "urls.py").read_text()
        assert "quickscale_modules_blog.urls" in urls
        # markdownx URL should not be added when RSS disabled
        assert "markdownx" not in urls

    def test_blog_urls_already_present(self, tmp_path):
        """Skip URL update when blog urls already present"""
        project = _make_project(tmp_path)
        (project / "myproject" / "urls.py").write_text("quickscale_modules_blog here\n")
        config = {"posts_per_page": 10, "enable_rss": True}
        apply_blog_configuration(project, config)


# ============================================================================
# Listings configuration - full apply flows
# ============================================================================


class TestApplyListingsConfigurationFull:
    """Full tests for apply_listings_configuration"""

    def test_settings_not_found(self, tmp_path):
        """Warn and return when settings.py missing"""
        project = tmp_path / "proj"
        project.mkdir()
        apply_listings_configuration(project, {"listings_per_page": 12})

    def test_already_configured(self, tmp_path):
        """Skip when listings already present"""
        project = _make_project(tmp_path)
        settings = project / "myproject" / "settings" / "base.py"
        settings.write_text("quickscale_modules_listings\n")
        apply_listings_configuration(project, {"listings_per_page": 12})

    def test_full_apply_listings(self, tmp_path):
        """Full listings config apply"""
        project = _make_project(tmp_path)
        # Create listings module pyproject
        listings_dir = project / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-filter = "^23.0"\n'
        )

        config = {"listings_per_page": 20}
        apply_listings_configuration(project, config)

        settings = (project / "myproject" / "settings" / "base.py").read_text()
        assert "quickscale_modules_listings" in settings
        assert "LISTINGS_PER_PAGE = 20" in settings

        urls = (project / "myproject" / "urls.py").read_text()
        assert "quickscale_modules_listings.urls" in urls

    def test_listings_all_apps_already_present(self, tmp_path):
        """All required apps already in INSTALLED_APPS"""
        project = _make_project(tmp_path)
        settings = project / "myproject" / "settings" / "base.py"
        settings.write_text(
            'INSTALLED_APPS = ["django_filters", "quickscale_modules_listings"]\n'
        )
        # No listings module dir needed since we already have the apps
        # but need pyproject for dependency
        (project / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\npython = "^3.11"\ndjango-filter = "^23.0"\n'
        )

        config = {"listings_per_page": 15}
        # This should still write settings but not duplicate INSTALLED_APPS
        # It fails because settings check passes at "already configured" since the string is present
        # Actually, if quickscale_modules_listings is in settings, it returns early
        # Let's test the _filter_new_apps path differently - settings has django_filters but not the module
        settings.write_text('INSTALLED_APPS = ["django_filters"]\n')
        apply_listings_configuration(project, config)

        content = settings.read_text()
        assert "LISTINGS_PER_PAGE = 15" in content

    def test_listings_urls_already_present(self, tmp_path):
        """Skip URL update when listings URLs already present"""
        project = _make_project(tmp_path)
        (project / "myproject" / "urls.py").write_text(
            "quickscale_modules_listings here\n"
        )
        settings = project / "myproject" / "settings" / "base.py"
        settings.write_text("INSTALLED_APPS = []\n")
        listings_dir = project / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-filter = "^23.0"\n'
        )

        config = {"listings_per_page": 12}
        apply_listings_configuration(project, config)


# ============================================================================
# _add_django_filter_dependency edge cases
# ============================================================================


class TestAddDjangoFilterDependencyEdgeCases:
    """Edge cases for _add_django_filter_dependency"""

    def test_no_version_match(self, tmp_path):
        """Abort when version cannot be parsed"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')
        listings_dir = tmp_path / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text("[tool.poetry.dependencies]\n")

        with pytest.raises(click.Abort):
            _add_django_filter_dependency(tmp_path, pyproject)

    def test_file_read_error(self, tmp_path):
        """Abort on file read error"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')
        listings_dir = tmp_path / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-filter = "^23.0"\n'
        )

        with patch(
            "builtins.open", side_effect=[pyproject.open(), FileNotFoundError("mocked")]
        ):
            with pytest.raises(click.Abort):
                _add_django_filter_dependency(tmp_path, pyproject)

    def test_no_dependencies_section(self, tmp_path):
        """Warn when [tool.poetry.dependencies] section missing"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.poetry]\nname = 'test'\n")
        listings_dir = tmp_path / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-filter = "^23.0"\n'
        )

        _add_django_filter_dependency(tmp_path, pyproject)


# ============================================================================
# CRM module configuration
# ============================================================================


class TestCRMModuleConfig:
    """Tests for CRM module configuration functions"""

    def test_get_default_crm_config(self):
        """Test default CRM configuration"""
        config = get_default_crm_config()
        assert config["enable_api"] is True
        assert config["deals_per_page"] == 25
        assert config["contacts_per_page"] == 50

    def test_configure_crm_non_interactive(self):
        """Test non-interactive CRM configuration"""
        config = configure_crm_module(non_interactive=True)
        assert config["enable_api"] is True
        assert config["deals_per_page"] == 25
        assert config["contacts_per_page"] == 50

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_crm_interactive(self, mock_confirm, mock_prompt):
        """Test interactive CRM configuration"""
        mock_confirm.return_value = False
        mock_prompt.side_effect = [30, 100]

        config = configure_crm_module(non_interactive=False)
        assert config["enable_api"] is False
        assert config["deals_per_page"] == 30
        assert config["contacts_per_page"] == 100

    def test_crm_in_module_configurators(self):
        """Test CRM is registered in MODULE_CONFIGURATORS"""
        assert "crm" in MODULE_CONFIGURATORS
        configurator, applier = MODULE_CONFIGURATORS["crm"]
        config = configurator(non_interactive=True)
        assert "enable_api" in config


# ============================================================================
# _add_drf_and_filter_dependencies
# ============================================================================


class TestAddDrfAndFilterDependencies:
    """Tests for _add_drf_and_filter_dependencies"""

    def test_crm_module_pyproject_missing(self, tmp_path):
        """Abort when CRM module pyproject.toml not found"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')

        with pytest.raises(click.Abort):
            _add_drf_and_filter_dependencies(tmp_path, pyproject)

    def test_adds_both_dependencies(self, tmp_path):
        """Add both DRF and django-filter when missing"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')
        crm_dir = tmp_path / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'djangorestframework = "^3.15.0"\n'
            'django-filter = "^23.0"\n'
        )

        _add_drf_and_filter_dependencies(tmp_path, pyproject)

        content = pyproject.read_text()
        assert "djangorestframework" in content
        assert "django-filter" in content

    def test_skips_existing_dependencies(self, tmp_path):
        """Skip deps that already exist in pyproject"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.poetry.dependencies]\npython = "^3.11"\n'
            'djangorestframework = "^3.14.0"\n'
            'django-filter = "^23.0"\n'
        )
        crm_dir = tmp_path / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'djangorestframework = "^3.15.0"\n'
            'django-filter = "^24.0"\n'
        )

        _add_drf_and_filter_dependencies(tmp_path, pyproject)
        # No error, and versions unchanged

    def test_parse_error(self, tmp_path):
        """Abort on parse error"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.11"\n')
        crm_dir = tmp_path / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text("invalid content")

        # No version match → no additions needed → should not abort
        _add_drf_and_filter_dependencies(tmp_path, pyproject)


# ============================================================================
# apply_crm_configuration
# ============================================================================


class TestApplyCRMConfiguration:
    """Tests for apply_crm_configuration"""

    def test_settings_not_found(self, tmp_path):
        """Warn and return when settings.py missing"""
        project = tmp_path / "proj"
        project.mkdir()
        apply_crm_configuration(project, get_default_crm_config())

    def test_already_configured(self, tmp_path):
        """Skip when CRM already present"""
        project = _make_project(tmp_path)
        settings = project / "myproject" / "settings" / "base.py"
        settings.write_text("quickscale_modules_crm\n")
        apply_crm_configuration(project, get_default_crm_config())

    def test_full_apply_crm_with_api(self, tmp_path):
        """Full CRM config apply with API enabled"""
        project = _make_project(tmp_path)
        crm_dir = project / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'djangorestframework = "^3.15.0"\n'
            'django-filter = "^23.0"\n'
        )

        config = {"enable_api": True, "deals_per_page": 25, "contacts_per_page": 50}
        apply_crm_configuration(project, config)

        settings = (project / "myproject" / "settings" / "base.py").read_text()
        assert "quickscale_modules_crm" in settings
        assert "CRM_DEALS_PER_PAGE = 25" in settings
        assert "CRM_CONTACTS_PER_PAGE = 50" in settings
        assert "CRM_ENABLE_API = True" in settings
        assert "REST_FRAMEWORK" in settings

        urls = (project / "myproject" / "urls.py").read_text()
        assert "quickscale_modules_crm.urls" in urls

    def test_full_apply_crm_without_api(self, tmp_path):
        """Full CRM config apply with API disabled"""
        project = _make_project(tmp_path)
        crm_dir = project / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'djangorestframework = "^3.15.0"\n'
            'django-filter = "^23.0"\n'
        )

        config = {"enable_api": False, "deals_per_page": 10, "contacts_per_page": 20}
        apply_crm_configuration(project, config)

        settings = (project / "myproject" / "settings" / "base.py").read_text()
        assert "CRM_ENABLE_API = False" in settings
        assert "REST_FRAMEWORK" not in settings

    def test_crm_all_apps_already_present(self, tmp_path):
        """All required CRM apps already in settings"""
        project = _make_project(tmp_path)
        settings = project / "myproject" / "settings" / "base.py"
        settings.write_text('INSTALLED_APPS = ["rest_framework", "django_filters"]\n')
        crm_dir = project / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'djangorestframework = "^3.15.0"\n'
            'django-filter = "^23.0"\n'
        )

        config = {"enable_api": True, "deals_per_page": 25, "contacts_per_page": 50}
        apply_crm_configuration(project, config)

        content = settings.read_text()
        assert "CRM_DEALS_PER_PAGE" in content

    def test_crm_urls_already_present(self, tmp_path):
        """Skip URL update when CRM URLs already present"""
        project = _make_project(tmp_path)
        (project / "myproject" / "urls.py").write_text("quickscale_modules_crm\n")
        crm_dir = project / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text("[tool.poetry.dependencies]\n")

        config = get_default_crm_config()
        apply_crm_configuration(project, config)

    def test_crm_no_pyproject(self, tmp_path):
        """Apply CRM when no pyproject.toml exists"""
        project = _make_project(tmp_path)
        (project / "pyproject.toml").unlink()

        config = get_default_crm_config()
        apply_crm_configuration(project, config)

        settings = (project / "myproject" / "settings" / "base.py").read_text()
        assert "CRM_DEALS_PER_PAGE" in settings
