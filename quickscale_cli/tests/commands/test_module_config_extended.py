"""Extended tests for `module_config.py`.

Covers CRM, listings apply, auth apply, and edge cases.
"""

from pathlib import Path
from unittest.mock import patch

import click
import pytest

from quickscale_cli.backups_contract import (
    DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
    DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
)
from quickscale_cli.commands.module_config import (
    MODULE_CONFIGURATORS,
    _add_django_allauth_dependency,
    _add_django_filter_dependency,
    _add_drf_and_filter_dependencies,
    _add_storage_dependencies,
    _filter_new_apps,
    _generate_auth_settings_addition,
    _is_app_in_installed_apps,
    apply_analytics_configuration,
    apply_auth_configuration,
    apply_backups_configuration,
    apply_blog_configuration,
    apply_crm_configuration,
    apply_forms_configuration,
    apply_listings_configuration,
    apply_notifications_configuration,
    apply_social_configuration,
    apply_storage_configuration,
    configure_analytics_module,
    configure_backups_module,
    configure_forms_module,
    configure_storage_module,
    configure_crm_module,
    configure_notifications_module,
    configure_social_module,
    get_default_analytics_config,
    get_default_backups_config,
    get_default_crm_config,
    get_default_forms_config,
    get_default_notifications_config,
    get_default_social_config,
    get_default_storage_config,
    format_auth_migration_remediation,
    validate_backups_module_options,
)
from quickscale_cli.commands.module_wiring_specs import build_module_wiring_specs
from quickscale_cli.social_contract import (
    SOCIAL_EMBEDS_PATH,
    SOCIAL_INTEGRATION_BASE_PATH,
    SOCIAL_INTEGRATION_EMBEDS_PATH,
    SOCIAL_LINK_TREE_PATH,
)
from quickscale_cli.utils.module_dependency_sync import sync_project_module_dependencies
from quickscale_cli.utils.module_dependency_sync import (
    DependencySyncError,
    ProjectDependencySyncResult,
    _extract_dependency_name,
    _extract_version_tuple,
    _load_poetry_dependencies,
    _load_project_name,
    _load_toml_file,
    _prefer_dependency_value,
    _render_toml_literal,
    resolve_embedded_module_install_path,
)
from quickscale_core.module_wiring import collect_wiring


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
        "from django.urls import include, path\n"
        "urlpatterns = [\n"
        '    path("admin/", include("admin")),\n'
        "]\n"
    )
    (project / "pyproject.toml").write_text(
        '[tool.poetry.dependencies]\npython = "^3.14"\nDjango = "^6.0"\n'
    )
    (project / "quickscale.yml").write_text(
        f'version: "1"\n'
        f"project:\n"
        f"  slug: {project_name}\n"
        f"  package: {project_name}\n"
        f"  theme: showcase_html\n"
        f"docker:\n"
        f"  start: false\n"
    )
    return project


def _write_module_package(
    project: Path,
    module_name: str,
    *,
    manifest_content: str,
    pyproject_content: str,
) -> None:
    """Create a minimal embedded module package for dependency-sync tests."""
    module_dir = project / "modules" / module_name
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "module.yml").write_text(manifest_content)
    (module_dir / "pyproject.toml").write_text(pyproject_content)


class TestSharedModuleDependencySync:
    """Tests for the shared CLI dependency-sync helper."""

    def test_sync_adds_module_path_and_manifest_backed_dependency(self, tmp_path):
        project = _make_project(tmp_path)
        _write_module_package(
            project,
            "auth",
            manifest_content=(
                "name: auth\n"
                'version: "0.83.0"\n'
                "dependencies:\n"
                "  - django-allauth>=0.63.0\n"
            ),
            pyproject_content=(
                "[project]\n"
                'name = "quickscale-module-auth"\n\n'
                "[tool.poetry.dependencies]\n"
                'python = "^3.14"\n'
                'django-allauth = ">=65.14.1,<66.0.0"\n'
            ),
        )

        result = sync_project_module_dependencies(project, {"auth": {}})

        pyproject_content = (project / "pyproject.toml").read_text()
        assert result.added_package_dependencies == ["django-allauth"]
        assert result.added_path_dependencies == ["quickscale-module-auth"]
        assert 'django-allauth = ">=65.14.1,<66.0.0"' in pyproject_content
        assert (
            'quickscale-module-auth = {path = "./modules/auth", develop = true}'
            in pyproject_content
        )

    def test_sync_is_add_only_for_existing_project_dependency(self, tmp_path):
        project = _make_project(tmp_path)
        (project / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'python = "^3.14"\n'
            'Django = "^6.0"\n'
            'django-filter = "^99.0"\n'
        )
        _write_module_package(
            project,
            "listings",
            manifest_content=(
                "name: listings\n"
                'version: "0.83.0"\n'
                "dependencies:\n"
                "  - django-filter>=25.0\n"
            ),
            pyproject_content=(
                "[project]\n"
                'name = "quickscale-module-listings"\n\n'
                "[tool.poetry.dependencies]\n"
                'python = "^3.14"\n'
                'django-filter = "^25.2"\n'
            ),
        )

        result = sync_project_module_dependencies(project, {"listings": {}})

        pyproject_content = (project / "pyproject.toml").read_text()
        assert result.added_package_dependencies == []
        assert result.added_path_dependencies == ["quickscale-module-listings"]
        assert 'django-filter = "^99.0"' in pyproject_content
        assert (
            'quickscale-module-listings = {path = "./modules/listings", develop = true}'
            in pyproject_content
        )

    def test_storage_local_sync_skips_cloud_packages(self, tmp_path):
        project = _make_project(tmp_path)
        _write_module_package(
            project,
            "storage",
            manifest_content=(
                "name: storage\n"
                'version: "0.83.0"\n'
                "dependencies:\n"
                "  - django-storages>=1.14.4\n"
                "  - boto3>=1.35.0\n"
            ),
            pyproject_content=(
                "[project]\n"
                'name = "quickscale-module-storage"\n\n'
                "[tool.poetry.dependencies]\n"
                'python = "^3.14"\n'
                'django-storages = "^1.14.4"\n'
                'boto3 = "^1.35.0"\n'
            ),
        )

        result = sync_project_module_dependencies(
            project,
            {"storage": {"backend": "local"}},
        )

        pyproject_content = (project / "pyproject.toml").read_text()
        assert result.added_package_dependencies == []
        assert result.added_path_dependencies == ["quickscale-module-storage"]
        assert "django-storages" not in pyproject_content
        assert "boto3" not in pyproject_content
        assert (
            'quickscale-module-storage = {path = "./modules/storage", develop = true}'
            in pyproject_content
        )

    def test_storage_cloud_sync_adds_cloud_packages(self, tmp_path):
        project = _make_project(tmp_path)
        _write_module_package(
            project,
            "storage",
            manifest_content=(
                "name: storage\n"
                'version: "0.83.0"\n'
                "dependencies:\n"
                "  - django-storages>=1.14.4\n"
                "  - boto3>=1.35.0\n"
            ),
            pyproject_content=(
                "[project]\n"
                'name = "quickscale-module-storage"\n\n'
                "[tool.poetry.dependencies]\n"
                'python = "^3.14"\n'
                'django-storages = "^1.14.4"\n'
                'boto3 = "^1.35.0"\n'
            ),
        )

        result = sync_project_module_dependencies(
            project,
            {"storage": {"backend": "s3"}},
        )

        pyproject_content = (project / "pyproject.toml").read_text()
        assert result.added_package_dependencies == ["boto3", "django-storages"]
        assert result.added_path_dependencies == ["quickscale-module-storage"]
        assert 'django-storages = "^1.14.4"' in pyproject_content
        assert 'boto3 = "^1.35.0"' in pyproject_content
        assert (
            'quickscale-module-storage = {path = "./modules/storage", develop = true, extras = ["cloud"]}'
            in pyproject_content
        )


class TestSharedModuleDependencySyncHelpers:
    """Focused coverage for pure dependency-sync helper branches."""

    def test_project_dependency_sync_result_changed_property(self):
        assert ProjectDependencySyncResult().changed is False
        assert (
            ProjectDependencySyncResult(
                added_path_dependencies=["quickscale-module-auth"]
            ).changed
            is True
        )
        assert (
            ProjectDependencySyncResult(
                added_package_dependencies=["django-allauth"]
            ).changed
            is True
        )

    def test_resolve_embedded_module_install_path_returns_none_when_module_missing(
        self,
        tmp_path,
    ):
        assert resolve_embedded_module_install_path(tmp_path, "auth") is None

    def test_load_toml_file_raises_for_invalid_toml(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("[tool.poetry\n")

        with pytest.raises(DependencySyncError, match="Invalid TOML"):
            _load_toml_file(pyproject)

    def test_module_metadata_helpers_raise_meaningful_errors(self, tmp_path):
        pyproject = tmp_path / "pyproject.toml"

        with pytest.raises(DependencySyncError, match=r"valid \[project\] table"):
            _load_project_name(pyproject, {"project": []}, "auth")

        with pytest.raises(
            DependencySyncError,
            match=r"missing \[project\]\.name",
        ):
            _load_project_name(pyproject, {"project": {}}, "auth")

        with pytest.raises(
            DependencySyncError,
            match=r"Unable to locate \[tool\.poetry\.dependencies\]",
        ):
            _load_poetry_dependencies(pyproject, {"tool": []})

        with pytest.raises(
            DependencySyncError,
            match=r"Unable to locate \[tool\.poetry\.dependencies\]",
        ):
            _load_poetry_dependencies(pyproject, {"tool": {"poetry": []}})

        with pytest.raises(
            DependencySyncError,
            match="must be a mapping",
        ):
            _load_poetry_dependencies(
                pyproject, {"tool": {"poetry": {"dependencies": []}}}
            )

        with pytest.raises(
            DependencySyncError, match="Unable to parse dependency name"
        ):
            _extract_dependency_name("!!!", "auth")

    def test_version_preference_and_toml_literal_helpers_cover_edge_cases(self):
        assert _extract_version_tuple("git+https://example.com/pkg") is None
        assert _prefer_dependency_value("^1.2.0", "^1.3.0") == "^1.3.0"
        assert _prefer_dependency_value("^1.3.0", "^1.2.0") == "^1.3.0"
        assert _prefer_dependency_value({"path": "./modules/auth"}, "^1.3.0") == {
            "path": "./modules/auth"
        }
        assert _render_toml_literal(True) == "true"
        assert _render_toml_literal(3) == "3"
        assert _render_toml_literal(1.5) == "1.5"
        assert _render_toml_literal(["auth", 2]) == '["auth", 2]'
        assert (
            _render_toml_literal({"path": "./modules/auth", "develop": True})
            == '{path = "./modules/auth", develop = true}'
        )

        with pytest.raises(
            DependencySyncError, match="Unsupported TOML dependency value"
        ):
            _render_toml_literal(object())


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
        """Managed wiring remains idempotent when auth reapplied."""
        project = _make_project(tmp_path)
        auth_dir = project / "modules" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-allauth = "^0.60.0"\n'
        )
        config = {
            "registration_enabled": True,
            "email_verification": "none",
            "authentication_method": "email",
        }
        apply_auth_configuration(project, config)
        apply_auth_configuration(project, config)

        managed_settings = (
            project / "myproject" / "settings" / "modules.py"
        ).read_text()
        assert managed_settings.count("'quickscale_modules_auth'") == 1

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
            "registration_enabled": True,
            "email_verification": "none",
            "authentication_method": "email",
        }
        apply_auth_configuration(project, config)

        settings_content = (
            project / "myproject" / "settings" / "modules.py"
        ).read_text()
        assert "quickscale_modules_auth" in settings_content
        assert "allauth" in settings_content
        assert "AUTH_USER_MODEL" in settings_content

        urls_content = (project / "myproject" / "urls_modules.py").read_text()
        assert "allauth.urls" in urls_content
        assert "quickscale_modules_auth.urls" in urls_content

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
            "registration_enabled": True,
            "email_verification": "none",
            "authentication_method": "email",
        }
        apply_auth_configuration(project, config)
        managed_urls = (project / "myproject" / "urls_modules.py").read_text()
        assert "quickscale_modules_auth.urls" in managed_urls


# ============================================================================
# _add_django_allauth_dependency edge cases
# ============================================================================


class TestAddDjangoAllauthDependencyEdgeCases:
    """Edge cases for _add_django_allauth_dependency"""

    def test_no_version_match_in_auth_pyproject(self, tmp_path):
        """Abort when version cannot be parsed from auth pyproject"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')
        auth_dir = tmp_path / "modules" / "auth"
        auth_dir.mkdir(parents=True)
        (auth_dir / "pyproject.toml").write_text("[tool.poetry.dependencies]\n")

        with pytest.raises(click.Abort):
            _add_django_allauth_dependency(tmp_path, pyproject)

    def test_file_read_error(self, tmp_path):
        """Abort on file read error"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')
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
        """Managed wiring remains idempotent when blog reapplied."""
        project = _make_project(tmp_path)
        config = {"posts_per_page": 10, "enable_rss": True}
        apply_blog_configuration(project, config)
        apply_blog_configuration(project, config)
        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert settings.count("quickscale_modules_blog") == 1

    def test_full_apply_blog_with_rss(self, tmp_path):
        """Full blog config apply with RSS enabled"""
        project = _make_project(tmp_path)
        config = {"posts_per_page": 15, "enable_rss": True}
        apply_blog_configuration(project, config)

        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert "quickscale_modules_blog" in settings
        assert "'BLOG_POSTS_PER_PAGE': 15" in settings
        assert "markdownx" in settings.lower() or "MARKDOWNX" in settings

        urls = (project / "myproject" / "urls_modules.py").read_text()
        assert "quickscale_modules_blog.urls" in urls
        assert "markdownx.urls" in urls

    def test_full_apply_blog_without_rss(self, tmp_path):
        """Full blog config apply with RSS disabled"""
        project = _make_project(tmp_path)
        config = {"posts_per_page": 5, "enable_rss": False}
        apply_blog_configuration(project, config)

        urls = (project / "myproject" / "urls_modules.py").read_text()
        assert "quickscale_modules_blog.urls" in urls
        assert "markdownx.urls" in urls

    def test_blog_urls_already_present(self, tmp_path):
        """Skip URL update when blog urls already present"""
        project = _make_project(tmp_path)
        (project / "myproject" / "urls.py").write_text("quickscale_modules_blog here\n")
        config = {"posts_per_page": 10, "enable_rss": True}
        apply_blog_configuration(project, config)
        managed_urls = (project / "myproject" / "urls_modules.py").read_text()
        assert "quickscale_modules_blog.urls" in managed_urls


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
        """Managed wiring remains idempotent when listings reapplied."""
        project = _make_project(tmp_path)
        listings_dir = project / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-filter = "^23.0"\n'
        )
        config = {"listings_per_page": 12}
        apply_listings_configuration(project, config)
        apply_listings_configuration(project, config)
        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert settings.count("quickscale_modules_listings") == 1

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

        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert "quickscale_modules_listings" in settings
        assert "'LISTINGS_PER_PAGE': 20" in settings

        urls = (project / "myproject" / "urls_modules.py").read_text()
        assert "quickscale_modules_listings.urls" in urls
        assert "markdownx.urls" in urls

    def test_full_apply_listings_leaves_pyproject_dependency_sync_to_cli_helper(
        self,
        tmp_path,
    ):
        """Listings wiring should no longer mutate pyproject.toml directly."""
        project = _make_project(tmp_path)
        listings_dir = project / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'django-filter = "^23.0"\n'
            'django-markdownx = "^4.0"\n'
        )

        apply_listings_configuration(project, {"listings_per_page": 20})

        pyproject_content = (project / "pyproject.toml").read_text()
        assert "django-filter" not in pyproject_content
        assert "django-markdownx" not in pyproject_content

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
            '[tool.poetry.dependencies]\npython = "^3.14"\ndjango-filter = "^23.0"\n'
        )

        config = {"listings_per_page": 15}
        settings.write_text('INSTALLED_APPS = ["django_filters"]\n')
        listings_dir = project / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text(
            '[tool.poetry.dependencies]\ndjango-filter = "^23.0"\n'
        )
        apply_listings_configuration(project, config)

        content = (project / "myproject" / "settings" / "modules.py").read_text()
        assert "'LISTINGS_PER_PAGE': 15" in content

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
        managed_urls = (project / "myproject" / "urls_modules.py").read_text()
        assert "quickscale_modules_listings.urls" in managed_urls
        assert "markdownx.urls" in managed_urls


# ============================================================================
# _add_django_filter_dependency edge cases
# ============================================================================


class TestAddDjangoFilterDependencyEdgeCases:
    """Edge cases for _add_django_filter_dependency"""

    def test_no_version_match(self, tmp_path):
        """Abort when version cannot be parsed"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')
        listings_dir = tmp_path / "modules" / "listings"
        listings_dir.mkdir(parents=True)
        (listings_dir / "pyproject.toml").write_text("[tool.poetry.dependencies]\n")

        with pytest.raises(click.Abort):
            _add_django_filter_dependency(tmp_path, pyproject)

    def test_file_read_error(self, tmp_path):
        """Abort on file read error"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')
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


class TestModuleWiringSpecs:
    """Regression tests for module wiring spec collisions"""

    def test_analytics_wiring_emits_flat_settings(self):
        """Analytics wiring should emit flat settings plus the analytics app."""
        specs = build_module_wiring_specs(
            {
                "analytics": {
                    "posthog_api_key_env_var": "OPS_POSTHOG_API_KEY",
                    "posthog_host_env_var": "OPS_POSTHOG_HOST",
                    "posthog_host": "https://eu.i.posthog.com",
                    "exclude_staff": True,
                    "anonymous_by_default": False,
                }
            }
        )

        apps, _, settings, _ = collect_wiring(specs)

        assert "quickscale_modules_analytics" in apps
        assert settings["QUICKSCALE_ANALYTICS_ENABLED"] is True
        assert settings["QUICKSCALE_ANALYTICS_PROVIDER"] == "posthog"
        assert (
            settings["QUICKSCALE_ANALYTICS_POSTHOG_API_KEY_ENV_VAR"]
            == "OPS_POSTHOG_API_KEY"
        )
        assert (
            settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST_ENV_VAR"] == "OPS_POSTHOG_HOST"
        )
        assert (
            settings["QUICKSCALE_ANALYTICS_POSTHOG_HOST"] == "https://eu.i.posthog.com"
        )
        assert settings["QUICKSCALE_ANALYTICS_EXCLUDE_STAFF"] is True
        assert settings["QUICKSCALE_ANALYTICS_ANONYMOUS_BY_DEFAULT"] is False

    def test_analytics_wiring_disabled_omits_managed_settings(self):
        """Disabled analytics should not contribute apps or managed settings."""
        specs = build_module_wiring_specs({"analytics": {"enabled": False}})

        apps, _, settings, _ = collect_wiring(specs)

        assert "quickscale_modules_analytics" not in apps
        assert "QUICKSCALE_ANALYTICS_ENABLED" not in settings

    def test_blog_and_listings_markdownx_media_path_uses_blog_value(self):
        """`MARKDOWNX_MEDIA_PATH` should remain stable with blog and listings."""
        specs = build_module_wiring_specs(
            {
                "blog": {"posts_per_page": 10, "enable_rss": True},
                "listings": {"listings_per_page": 12},
            }
        )
        _, _, settings, _ = collect_wiring(specs)

        assert settings["MARKDOWNX_MEDIA_PATH"] == "blog/markdownx/"

    def test_listings_wiring_includes_markdownx_urls(self):
        """Listings wiring should include markdownx URLs for admin uploads"""
        specs = build_module_wiring_specs({"listings": {"listings_per_page": 12}})

        assert specs["listings"].url_includes == (
            ("listings/", "quickscale_modules_listings.urls"),
            ("markdownx/", "markdownx.urls"),
        )

    def test_blog_wiring_without_rss_still_includes_markdownx_urls(self):
        """Blog wiring should keep markdownx URLs even when RSS is disabled."""
        specs = build_module_wiring_specs(
            {"blog": {"posts_per_page": 10, "enable_rss": False}}
        )

        _, _, settings, urls = collect_wiring(specs)

        assert settings["BLOG_ENABLE_RSS"] is False
        assert ("blog/", "quickscale_modules_blog.urls") in urls
        assert ("markdownx/", "markdownx.urls") in urls

    def test_storage_wiring_local_keeps_filesystem_defaults(self):
        """Storage wiring should not force STORAGES override for local backend."""
        specs = build_module_wiring_specs(
            {
                "storage": {
                    "backend": "local",
                    "media_url": "/media/",
                    "public_base_url": "",
                    "private_media_enabled": False,
                }
            }
        )

        _, _, settings, _ = collect_wiring(specs)

        assert settings["QUICKSCALE_STORAGE_BACKEND"] == "local"
        assert settings["MEDIA_URL"] == "/media/"
        assert "STORAGES" not in settings

    def test_storage_wiring_s3_sets_s3_backend(self):
        """Storage wiring should configure S3-compatible backend in cloud mode."""
        specs = build_module_wiring_specs(
            {
                "storage": {
                    "backend": "s3",
                    "media_url": "/media/",
                    "public_base_url": "",
                    "bucket_name": "assets",
                    "endpoint_url": "",
                    "region_name": "us-east-1",
                    "access_key_id": "key",
                    "secret_access_key": "secret",
                    "default_acl": "",
                    "querystring_auth": False,
                    "private_media_enabled": False,
                }
            }
        )

        _, _, settings, _ = collect_wiring(specs)

        assert settings["QUICKSCALE_STORAGE_BACKEND"] == "s3"
        assert (
            settings["STORAGES"]["default"]["BACKEND"]
            == "storages.backends.s3.S3Storage"
        )
        assert (
            settings["STORAGES"]["staticfiles"]["BACKEND"]
            == "whitenoise.storage.CompressedManifestStaticFilesStorage"
        )
        assert settings["QUICKSCALE_STORAGE_PUBLIC_BASE_URL"] == ""
        assert settings["AWS_STORAGE_BUCKET_NAME"] == "assets"
        assert settings["AWS_QUERYSTRING_AUTH"] is False

    def test_storage_wiring_invalid_backend_and_media_url_are_normalized(self):
        """Storage wiring should normalize invalid backends and relative URLs."""
        specs = build_module_wiring_specs(
            {
                "storage": {
                    "backend": "invalid",
                    "media_url": "media",
                    "public_base_url": "",
                    "private_media_enabled": True,
                }
            }
        )

        _, _, settings, _ = collect_wiring(specs)

        assert settings["QUICKSCALE_STORAGE_BACKEND"] == "local"
        assert settings["MEDIA_URL"] == "/media/"
        assert settings["QUICKSCALE_STORAGE_PRIVATE_MEDIA_ENABLED"] is True

    def test_storage_wiring_r2_sets_optional_provider_settings(self):
        """Storage wiring should emit optional provider fields for R2 mode."""
        specs = build_module_wiring_specs(
            {
                "storage": {
                    "backend": "r2",
                    "media_url": "https://cdn.example.com/",
                    "public_base_url": "https://cdn.example.com",
                    "bucket_name": "assets",
                    "endpoint_url": "https://account.r2.cloudflarestorage.com",
                    "region_name": "auto",
                    "access_key_id": "key-id",
                    "secret_access_key": "secret-key",
                    "default_acl": "public-read",
                    "querystring_auth": True,
                    "private_media_enabled": False,
                }
            }
        )

        _, _, settings, _ = collect_wiring(specs)

        assert settings["QUICKSCALE_STORAGE_BACKEND"] == "r2"
        assert settings["MEDIA_URL"] == "https://cdn.example.com/"
        assert (
            settings["QUICKSCALE_STORAGE_PUBLIC_BASE_URL"] == "https://cdn.example.com"
        )
        assert (
            settings["AWS_S3_ENDPOINT_URL"]
            == "https://account.r2.cloudflarestorage.com"
        )
        assert settings["AWS_S3_REGION_NAME"] == "auto"
        assert settings["AWS_ACCESS_KEY_ID"] == "key-id"
        assert settings["AWS_SECRET_ACCESS_KEY"] == "secret-key"
        assert settings["AWS_DEFAULT_ACL"] == "public-read"
        assert settings["AWS_QUERYSTRING_AUTH"] is True

    def test_auth_wiring_supports_legacy_allow_registration_and_username_mode(self):
        """Auth wiring should keep legacy config compatibility paths covered."""
        specs = build_module_wiring_specs(
            {
                "auth": {
                    "allow_registration": False,
                    "authentication_method": "username",
                    "email_verification": "mandatory",
                }
            }
        )

        _, _, settings, urls = collect_wiring(specs)

        assert settings["ACCOUNT_ALLOW_REGISTRATION"] is False
        assert settings["ACCOUNT_LOGIN_METHODS"] == {"username"}
        assert settings["ACCOUNT_SIGNUP_FIELDS"] == [
            "username*",
            "password1*",
            "password2*",
        ]
        assert ("accounts/", "allauth.urls") in urls

    def test_auth_wiring_supports_both_authentication_mode(self):
        """Auth wiring should generate combined login/signup fields for both mode."""
        specs = build_module_wiring_specs(
            {
                "auth": {
                    "registration_enabled": True,
                    "authentication_method": "both",
                    "email_verification": "optional",
                }
            }
        )

        _, _, settings, _ = collect_wiring(specs)

        assert settings["ACCOUNT_LOGIN_METHODS"] == {"email", "username"}
        assert settings["ACCOUNT_SIGNUP_FIELDS"] == [
            "email*",
            "username*",
            "password1*",
            "password2*",
        ]

    def test_forms_wiring_without_submissions_api_omits_rest_framework(self):
        """Forms wiring should avoid REST_FRAMEWORK when submissions API is disabled."""
        specs = build_module_wiring_specs(
            {
                "forms": {
                    "forms_per_page": 15,
                    "spam_protection_enabled": False,
                    "rate_limit": "10/minute",
                    "data_retention_days": 14,
                    "submissions_api_enabled": False,
                }
            }
        )

        _, _, settings, _ = collect_wiring(specs)

        assert settings["FORMS_PER_PAGE"] == 15
        assert settings["FORMS_SPAM_PROTECTION"] is False
        assert settings["FORMS_RATE_LIMIT"] == "10/minute"
        assert settings["FORMS_DATA_RETENTION_DAYS"] == 14
        assert settings["FORMS_SUBMISSIONS_API"] is False
        assert "REST_FRAMEWORK" not in settings

    def test_crm_and_forms_wiring_do_not_collide_on_rest_framework(self):
        """CRM and forms wiring should keep distinct module-owned settings."""
        specs = build_module_wiring_specs(
            {
                "crm": {
                    "enable_api": True,
                    "deals_per_page": 10,
                    "contacts_per_page": 20,
                },
                "forms": {
                    "forms_per_page": 15,
                    "spam_protection_enabled": True,
                    "rate_limit": "10/minute",
                    "data_retention_days": 14,
                    "submissions_api_enabled": True,
                },
            }
        )

        apps, _, settings, urls = collect_wiring(specs)

        assert "rest_framework" in apps
        assert "django_filters" in apps
        assert settings["CRM_ENABLE_API"] is True
        assert settings["CRM_DEALS_PER_PAGE"] == 10
        assert settings["CRM_CONTACTS_PER_PAGE"] == 20
        assert settings["FORMS_PER_PAGE"] == 15
        assert settings["FORMS_SUBMISSIONS_API"] is True
        assert "REST_FRAMEWORK" not in settings
        assert ("crm/", "quickscale_modules_crm.urls") in urls
        assert ("", "quickscale_modules_forms.urls") in urls

    def test_build_module_wiring_specs_skips_unknown_modules(self):
        """Unknown modules should be ignored by the wiring builder registry."""
        specs = build_module_wiring_specs(
            {"unknown": {}, "storage": {"backend": "local"}}
        )

        assert "unknown" not in specs
        assert "storage" in specs

    def test_social_wiring_creates_managed_backend_transport(self):
        """Social wiring should emit fixed-route settings and managed transport files."""
        specs = build_module_wiring_specs(
            {
                "social": {
                    "layout_variant": "GRID",
                    "provider_allowlist": ["Twitter", "YouTube"],
                    "cache_ttl_seconds": 600,
                    "links_per_page": 18,
                    "embeds_per_page": 9,
                }
            },
            project_package="myproject",
        )

        _, _, settings, urls = collect_wiring(specs)
        social_spec = specs["social"]
        managed_social_views = social_spec.managed_files[
            "quickscale_managed/social_views.py"
        ]

        assert settings["QUICKSCALE_SOCIAL_LINK_TREE_PATH"] == SOCIAL_LINK_TREE_PATH
        assert settings["QUICKSCALE_SOCIAL_EMBEDS_PATH"] == SOCIAL_EMBEDS_PATH
        assert (
            settings["QUICKSCALE_SOCIAL_INTEGRATION_BASE_PATH"]
            == SOCIAL_INTEGRATION_BASE_PATH
        )
        assert (
            settings["QUICKSCALE_SOCIAL_INTEGRATION_EMBEDS_PATH"]
            == SOCIAL_INTEGRATION_EMBEDS_PATH
        )
        assert settings["QUICKSCALE_SOCIAL_PROVIDER_ALLOWLIST"] == ["x", "youtube"]
        assert settings["QUICKSCALE_SOCIAL_EMBED_PROVIDER_ALLOWLIST"] == ["youtube"]
        assert urls == [
            ("_quickscale/social/", "myproject.quickscale_managed.social_urls")
        ]
        assert "quickscale_managed/__init__.py" in social_spec.managed_files
        assert "quickscale_managed/social_urls.py" in social_spec.managed_files
        assert "quickscale_managed/social_views.py" in social_spec.managed_files
        assert "quickscale_modules_social.services" in managed_social_views
        assert "build_social_link_tree_payload" in managed_social_views
        assert "build_social_embeds_payload" in managed_social_views
        assert "PAYLOAD_STATUS_HTTP" in managed_social_views
        assert "_error_payload" in managed_social_views

    def test_social_wiring_requires_project_package(self):
        """Social managed transport wiring should require the generated package name."""
        with pytest.raises(ValueError, match="project_package is required"):
            build_module_wiring_specs({"social": {}})


class TestFormsModuleConfig:
    """Tests for the forms module configurator and applier helpers."""

    def test_format_auth_migration_remediation_falls_back_to_slug(self, tmp_path):
        project = tmp_path / "demo-project"
        project.mkdir()

        with (
            patch(
                "quickscale_cli.commands.module_config.resolve_project_identity",
                side_effect=RuntimeError("boom"),
            ),
            patch(
                "quickscale_cli.commands.module_config.derive_package_from_slug",
                return_value="demo_project",
            ),
        ):
            remediation = format_auth_migration_remediation(project)

        assert f"cd {project.resolve()}" in remediation
        assert "demo_project_fresh" in remediation
        assert "docker compose down -v" in remediation

    def test_configure_forms_non_interactive_uses_defaults(self, capsys):
        config = configure_forms_module(non_interactive=True)

        output = capsys.readouterr().out

        assert config == get_default_forms_config()
        assert "Using default forms module configuration" in output
        assert "Forms per page: 25" in output

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_forms_interactive(self, mock_confirm, mock_prompt):
        mock_confirm.side_effect = [False, False]
        mock_prompt.side_effect = [40, "10/minute", 30]

        config = configure_forms_module(non_interactive=False)

        assert config == {
            "forms_per_page": 40,
            "spam_protection_enabled": False,
            "rate_limit": "10/minute",
            "data_retention_days": 30,
            "submissions_api_enabled": False,
        }

    @patch("quickscale_cli.commands.module_config._regenerate_wiring_for_module")
    def test_apply_forms_configuration_regenerates_wiring(
        self,
        mock_regenerate,
        tmp_path,
        capsys,
    ):
        project = _make_project(tmp_path)
        config = {
            "forms_per_page": 40,
            "spam_protection_enabled": False,
            "rate_limit": "10/minute",
            "data_retention_days": 30,
            "submissions_api_enabled": False,
        }

        apply_forms_configuration(project, config)

        output = capsys.readouterr().out

        mock_regenerate.assert_called_once_with(project, "forms", config)
        assert "Forms per page: 40" in output
        assert "Spam protection: Disabled" in output
        assert "Submissions API: Disabled" in output


class TestStorageModuleConfig:
    """Tests for storage module configurator registration and defaults."""

    def test_storage_default_config_keys_match_manifest_contract_intent(self):
        config = get_default_storage_config()
        assert config["backend"] == "local"
        assert config["media_url"] == "/media/"
        assert "custom_domain" not in config
        assert config["querystring_auth"] is False

    def test_storage_in_module_configurators(self):
        assert "storage" in MODULE_CONFIGURATORS
        config = configure_storage_module(non_interactive=True)
        assert config["backend"] == "local"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_storage_interactive_local(self, mock_confirm, mock_prompt):
        """Interactive local storage configuration should skip cloud-only prompts."""
        mock_confirm.return_value = False
        mock_prompt.side_effect = ["local", "media", "https://cdn.example.com/media"]

        config = configure_storage_module(non_interactive=False)

        assert config["backend"] == "local"
        assert config["media_url"] == "media"
        assert config["public_base_url"] == "https://cdn.example.com/media"
        assert config["bucket_name"] == ""

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_storage_interactive_cloud(self, mock_confirm, mock_prompt):
        """Interactive cloud storage configuration should collect provider settings."""
        mock_confirm.return_value = True
        mock_prompt.side_effect = [
            "r2",
            "/media/",
            "https://cdn.example.com/media",
            "assets",
            "https://account.r2.cloudflarestorage.com",
            "auto",
            "key-id",
            "secret-key",
            "public-read",
        ]

        config = configure_storage_module(non_interactive=False)

        assert config["backend"] == "r2"
        assert config["bucket_name"] == "assets"
        assert config["endpoint_url"] == "https://account.r2.cloudflarestorage.com"
        assert config["region_name"] == "auto"
        assert config["access_key_id"] == "key-id"
        assert config["secret_access_key"] == "secret-key"
        assert config["default_acl"] == "public-read"
        assert config["querystring_auth"] is True

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_storage_interactive_reuses_existing_values(
        self,
        mock_confirm,
        mock_prompt,
    ):
        """Interactive storage configuration should surface existing values as defaults."""
        mock_confirm.return_value = False
        mock_prompt.side_effect = [
            "s3",
            "/media/",
            "https://cdn.example.com/media",
            "assets",
            "",
            "eu-west-1",
            "key-id",
            "secret-key",
            "",
        ]

        config = configure_storage_module(
            non_interactive=False,
            existing_config={
                "backend": "s3",
                "media_url": "/media/",
                "public_base_url": "https://cdn.example.com/media",
                "bucket_name": "assets",
                "region_name": "eu-west-1",
                "access_key_id": "key-id",
                "secret_access_key": "secret-key",
            },
        )

        assert config["backend"] == "s3"
        assert config["public_base_url"] == "https://cdn.example.com/media"
        assert config["bucket_name"] == "assets"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_storage_switching_to_local_clears_cloud_values(
        self,
        mock_confirm,
        mock_prompt,
    ):
        """Switching storage to local should clear stale cloud-only settings."""
        mock_confirm.return_value = False
        mock_prompt.side_effect = ["local", "/media/", ""]

        config = configure_storage_module(
            non_interactive=False,
            existing_config={
                "backend": "s3",
                "media_url": "/media/",
                "public_base_url": "https://cdn.example.com/media",
                "bucket_name": "assets",
                "endpoint_url": "https://account.r2.cloudflarestorage.com",
                "region_name": "auto",
                "access_key_id": "key-id",
                "secret_access_key": "secret-key",
                "default_acl": "public-read",
                "querystring_auth": True,
            },
        )

        assert config["backend"] == "local"
        assert config["bucket_name"] == ""
        assert config["endpoint_url"] == ""
        assert config["region_name"] == ""
        assert config["access_key_id"] == ""
        assert config["secret_access_key"] == ""
        assert config["default_acl"] == ""
        assert config["querystring_auth"] is False

    def test_add_storage_dependencies_aborts_when_module_pyproject_missing(
        self, tmp_path
    ):
        """Abort if the embedded storage module `pyproject.toml` is missing."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')

        with pytest.raises(click.Abort):
            _add_storage_dependencies(tmp_path, pyproject)

    def test_add_storage_dependencies_adds_missing_packages(self, tmp_path):
        """Add `django-storages` and `boto3` when they are absent."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text(
            '[tool.poetry.dependencies]\npython = "^3.14"\nDjango = "^6.0"\n'
        )
        storage_dir = tmp_path / "modules" / "storage"
        storage_dir.mkdir(parents=True)
        (storage_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'django-storages = "^1.14.4"\n'
            'boto3 = "^1.35.0"\n'
        )

        _add_storage_dependencies(tmp_path, pyproject)

        content = pyproject.read_text()
        assert 'django-storages = "^1.14.4"' in content
        assert 'boto3 = "^1.35.0"' in content

    def test_add_storage_dependencies_skips_when_present(self, tmp_path):
        """Be a no-op when both storage dependency packages already exist."""
        pyproject = tmp_path / "pyproject.toml"
        original = (
            '[tool.poetry.dependencies]\npython = "^3.14"\n'
            'django-storages = "^1.14.4"\n'
            'boto3 = "^1.35.0"\n'
        )
        pyproject.write_text(original)

        _add_storage_dependencies(tmp_path, pyproject)

        assert pyproject.read_text() == original

    def test_add_storage_dependencies_handles_missing_dependencies_section(
        self, tmp_path
    ):
        """Return cleanly without a Poetry dependency section."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.group.dev.dependencies]\npytest = "^9.0"\n')
        storage_dir = tmp_path / "modules" / "storage"
        storage_dir.mkdir(parents=True)
        (storage_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'django-storages = "^1.14.4"\n'
            'boto3 = "^1.35.0"\n'
        )

        _add_storage_dependencies(tmp_path, pyproject)

        assert "django-storages" not in pyproject.read_text()

    @patch("quickscale_cli.commands.module_config._regenerate_wiring_for_module")
    def test_apply_storage_configuration_cloud_only_regenerates_wiring(
        self,
        mock_regenerate,
        tmp_path,
    ):
        """Cloud storage apply should leave dependency sync to the shared CLI helper."""
        project = _make_project(tmp_path)

        apply_storage_configuration(
            project,
            {
                "backend": "s3",
                "bucket_name": "assets",
            },
        )

        mock_regenerate.assert_called_once_with(
            project,
            "storage",
            get_default_storage_config()
            | {
                "backend": "s3",
                "bucket_name": "assets",
            },
        )

    @patch("quickscale_cli.commands.module_config._regenerate_wiring_for_module")
    def test_apply_storage_configuration_local_skips_dependency_install(
        self,
        mock_regenerate,
        tmp_path,
    ):
        """Applying local storage config should only regenerate wiring."""
        project = _make_project(tmp_path)

        apply_storage_configuration(project, {"backend": "local"})

        mock_regenerate.assert_called_once_with(
            project,
            "storage",
            get_default_storage_config() | {"backend": "local"},
        )


class TestAnalyticsModuleConfig:
    """Tests for analytics module configurator registration and wiring."""

    def test_analytics_default_config_keys_match_manifest_contract_intent(self):
        config = get_default_analytics_config()

        assert config["enabled"] is True
        assert config["provider"] == "posthog"
        assert config["posthog_api_key_env_var"] == "POSTHOG_API_KEY"
        assert config["posthog_host_env_var"] == "POSTHOG_HOST"
        assert config["posthog_host"] == "https://us.i.posthog.com"
        assert config["exclude_debug"] is True
        assert config["exclude_staff"] is False
        assert config["anonymous_by_default"] is True

    def test_analytics_in_module_configurators(self):
        assert "analytics" in MODULE_CONFIGURATORS

        config = configure_analytics_module(non_interactive=True)

        assert config["enabled"] is True
        assert config["provider"] == "posthog"
        assert config["anonymous_by_default"] is True

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_analytics_interactive(self, mock_confirm, mock_prompt):
        """Interactive analytics configuration should normalize custom values."""
        mock_confirm.side_effect = [True, False, True, False]
        mock_prompt.side_effect = [
            "OPS_POSTHOG_API_KEY",
            "OPS_POSTHOG_HOST",
            "eu.i.posthog.com/",
        ]

        config = configure_analytics_module(non_interactive=False)

        assert config["enabled"] is True
        assert config["provider"] == "posthog"
        assert config["posthog_api_key_env_var"] == "OPS_POSTHOG_API_KEY"
        assert config["posthog_host_env_var"] == "OPS_POSTHOG_HOST"
        assert config["posthog_host"] == "https://eu.i.posthog.com"
        assert config["exclude_debug"] is False
        assert config["exclude_staff"] is True
        assert config["anonymous_by_default"] is False

    @patch("quickscale_cli.commands.module_config._regenerate_wiring_for_module")
    def test_apply_analytics_configuration_regenerates_managed_wiring(
        self,
        mock_regenerate,
        tmp_path,
    ):
        project = _make_project(tmp_path)

        apply_analytics_configuration(
            project,
            {
                "posthog_api_key_env_var": "OPS_POSTHOG_API_KEY",
                "posthog_host": "eu.i.posthog.com/",
                "exclude_staff": True,
            },
        )

        mock_regenerate.assert_called_once_with(
            project,
            "analytics",
            get_default_analytics_config()
            | {
                "posthog_api_key_env_var": "OPS_POSTHOG_API_KEY",
                "posthog_host": "https://eu.i.posthog.com",
                "exclude_staff": True,
            },
        )


# ============================================================================
# Backups module configuration
# ============================================================================


class TestBackupsModuleConfig:
    """Tests for backups module configurator registration and validation."""

    def test_backups_default_config_keys_match_manifest_contract_intent(self):
        config = get_default_backups_config()
        assert config["retention_days"] == 14
        assert config["naming_prefix"] == "db"
        assert config["target_mode"] == "local"
        assert config["remote_access_key_id_env_var"] == ""
        assert config["remote_secret_access_key_env_var"] == ""
        assert config["automation_enabled"] is False

    def test_backups_in_module_configurators(self):
        assert "backups" in MODULE_CONFIGURATORS
        config = configure_backups_module(non_interactive=True)
        assert config["target_mode"] == "local"

    def test_validate_backups_module_options_local_defaults_are_valid(self):
        assert validate_backups_module_options(get_default_backups_config()) == []

    def test_validate_backups_module_options_empty_mapping_uses_defaults(self):
        assert validate_backups_module_options({}) == []

    def test_validate_backups_module_options_require_remote_fields(self):
        issues = validate_backups_module_options(
            get_default_backups_config() | {"target_mode": "private_remote"}
        )

        assert any("remote_bucket_name" in issue for issue in issues)
        assert any("remote_access_key_id_env_var" in issue for issue in issues)
        assert any("remote_secret_access_key_env_var" in issue for issue in issues)

    def test_validate_backups_module_options_reject_invalid_env_var_names(self):
        issues = validate_backups_module_options(
            get_default_backups_config()
            | {
                "target_mode": "private_remote",
                "remote_bucket_name": "private-bucket",
                "remote_region_name": "auto",
                "remote_access_key_id_env_var": "ops-backups-access-key-id",
                "remote_secret_access_key_env_var": "ops-backups-secret-access-key",
            }
        )

        assert any(
            (
                "remote_access_key_id_env_var must be an environment variable name"
                in issue
            )
            for issue in issues
        )
        assert any(
            (
                "remote_secret_access_key_env_var must be an environment variable name"
                in issue
            )
            for issue in issues
        )

    def test_validate_backups_module_options_reject_literal_aws_access_key_id(self):
        issues = validate_backups_module_options(
            get_default_backups_config()
            | {
                "target_mode": "private_remote",
                "remote_bucket_name": "private-bucket",
                "remote_region_name": "auto",
                "remote_access_key_id_env_var": "AKIAIOSFODNN7EXAMPLE",
                "remote_secret_access_key_env_var": "OPS_BACKUPS_SECRET_ACCESS_KEY",
            }
        )

        assert any("not a literal AWS access key id" in issue for issue in issues)

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_backups_interactive_local(self, mock_confirm, mock_prompt):
        mock_confirm.return_value = False
        mock_prompt.side_effect = [
            "local",
            30,
            "ops",
            ".private/backups",
        ]

        config = configure_backups_module(non_interactive=False)

        assert config["target_mode"] == "local"
        assert config["retention_days"] == 30
        assert config["naming_prefix"] == "ops"
        assert config["local_directory"] == ".private/backups"

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_backups_interactive_private_remote(
        self,
        mock_confirm,
        mock_prompt,
    ):
        mock_confirm.return_value = True
        mock_prompt.side_effect = [
            "private_remote",
            14,
            "db",
            ".quickscale/backups",
            "0 3 * * *",
            "private-bucket",
            "ops/backups",
            "https://account.r2.example.com",
            "auto",
            "OPS_BACKUPS_ACCESS_KEY_ID",
            "OPS_BACKUPS_SECRET_ACCESS_KEY",
        ]

        config = configure_backups_module(non_interactive=False)

        assert config["target_mode"] == "private_remote"
        assert config["remote_bucket_name"] == "private-bucket"
        assert config["remote_prefix"] == "ops/backups"
        assert config["remote_access_key_id_env_var"] == "OPS_BACKUPS_ACCESS_KEY_ID"
        assert (
            config["remote_secret_access_key_env_var"]
            == "OPS_BACKUPS_SECRET_ACCESS_KEY"
        )
        assert config["automation_enabled"] is True
        assert config["schedule"] == "0 3 * * *"

    @patch("quickscale_cli.commands.module_config._regenerate_wiring_for_module")
    def test_apply_backups_configuration_regenerates_managed_wiring(
        self,
        mock_regenerate,
        tmp_path,
    ):
        project = _make_project(tmp_path)

        apply_backups_configuration(
            project,
            {
                "retention_days": 30,
                "naming_prefix": "ops",
                "target_mode": "local",
                "local_directory": ".private/backups",
                "automation_enabled": True,
                "schedule": "0 4 * * *",
            },
        )

        mock_regenerate.assert_called_once_with(
            project,
            "backups",
            get_default_backups_config()
            | {
                "retention_days": 30,
                "naming_prefix": "ops",
                "target_mode": "local",
                "local_directory": ".private/backups",
                "automation_enabled": True,
                "schedule": "0 4 * * *",
            },
        )

    def test_backups_wiring_sets_private_settings_without_public_urls(self):
        specs = build_module_wiring_specs(
            {
                "backups": {
                    "retention_days": 14,
                    "naming_prefix": "db",
                    "target_mode": "private_remote",
                    "local_directory": ".quickscale/backups",
                    "remote_bucket_name": "private-bucket",
                    "remote_prefix": "ops/backups",
                    "remote_endpoint_url": "https://account.r2.example.com",
                    "remote_region_name": "auto",
                    "remote_access_key_id_env_var": DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR,
                    "remote_secret_access_key_env_var": DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR,
                    "automation_enabled": True,
                    "schedule": "0 2 * * *",
                }
            }
        )

        _, _, settings, _ = collect_wiring(specs)

        assert settings["QUICKSCALE_BACKUPS_TARGET_MODE"] == "private_remote"
        assert settings["QUICKSCALE_BACKUPS_REMOTE_BUCKET_NAME"] == "private-bucket"
        assert (
            settings["QUICKSCALE_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR"]
            == DEFAULT_BACKUPS_REMOTE_ACCESS_KEY_ID_ENV_VAR
        )
        assert (
            settings["QUICKSCALE_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR"]
            == DEFAULT_BACKUPS_REMOTE_SECRET_ACCESS_KEY_ENV_VAR
        )
        assert "QUICKSCALE_STORAGE_PUBLIC_BASE_URL" not in settings
        assert "MEDIA_URL" not in settings


class TestNotificationsModuleConfig:
    """Tests for notifications module configurator registration and wiring."""

    def test_notifications_default_config_keys_match_manifest_contract_intent(self):
        config = get_default_notifications_config()

        assert config["enabled"] is True
        assert config["sender_name"] == "QuickScale"
        assert config["sender_email"] == "noreply@example.com"
        assert config["resend_domain"] == ""
        assert config["resend_api_key_env_var"] == "RESEND_API_KEY"

    def test_notifications_in_module_configurators(self):
        assert "notifications" in MODULE_CONFIGURATORS

        config = configure_notifications_module(non_interactive=True)

        assert config["enabled"] is True
        assert config["default_tags"] == ["quickscale", "transactional"]

    @patch("quickscale_cli.commands.module_config._regenerate_wiring_for_module")
    def test_apply_notifications_configuration_regenerates_managed_wiring(
        self,
        mock_regenerate,
        tmp_path,
    ):
        project = _make_project(tmp_path)

        apply_notifications_configuration(
            project,
            {
                "enabled": True,
                "sender_name": "Ops",
                "sender_email": "ops@example.com",
                "reply_to_email": "support@example.com",
                "resend_domain": "mg.example.com",
                "resend_api_key_env_var": "OPS_RESEND_API_KEY",
                "webhook_secret_env_var": "OPS_NOTIFICATIONS_WEBHOOK_SECRET",
                "default_tags": ["quickscale", "ops"],
                "allowed_tags": ["quickscale", "ops", "transactional"],
                "webhook_ttl_seconds": 600,
            },
        )

        mock_regenerate.assert_called_once_with(
            project,
            "notifications",
            get_default_notifications_config()
            | {
                "enabled": True,
                "sender_name": "Ops",
                "sender_email": "ops@example.com",
                "reply_to_email": "support@example.com",
                "resend_domain": "mg.example.com",
                "resend_api_key_env_var": "OPS_RESEND_API_KEY",
                "webhook_secret_env_var": "OPS_NOTIFICATIONS_WEBHOOK_SECRET",
                "default_tags": ["quickscale", "ops"],
                "allowed_tags": ["quickscale", "ops", "transactional"],
                "webhook_ttl_seconds": 600,
            },
        )

    def test_notifications_wiring_stays_console_safe_by_default(self):
        specs = build_module_wiring_specs(
            {
                "notifications": {
                    "enabled": True,
                    "sender_name": "QuickScale",
                    "sender_email": "noreply@example.com",
                    "reply_to_email": "",
                    "resend_domain": "",
                    "resend_api_key_env_var": "RESEND_API_KEY",
                    "webhook_secret_env_var": "",
                    "default_tags": ["quickscale", "transactional"],
                    "allowed_tags": ["quickscale", "transactional", "ops"],
                    "webhook_ttl_seconds": 300,
                }
            }
        )

        _, _, settings, urls = collect_wiring(specs)

        assert (
            settings["EMAIL_BACKEND"]
            == "django.core.mail.backends.console.EmailBackend"
        )
        assert settings["DEFAULT_FROM_EMAIL"] == "noreply@example.com"
        assert "QUICKSCALE_NOTIFICATIONS_ENABLED" in settings
        assert ("", "quickscale_modules_notifications.urls") in urls

    def test_notifications_wiring_live_delivery_owns_email_backend(self):
        specs = build_module_wiring_specs(
            {
                "notifications": {
                    "enabled": True,
                    "sender_name": "Ops",
                    "sender_email": "ops@example.com",
                    "reply_to_email": "support@example.com",
                    "resend_domain": "mg.example.com",
                    "resend_api_key_env_var": "OPS_RESEND_API_KEY",
                    "webhook_secret_env_var": "OPS_NOTIFICATIONS_WEBHOOK_SECRET",
                    "default_tags": ["quickscale", "ops"],
                    "allowed_tags": ["quickscale", "ops", "transactional"],
                    "webhook_ttl_seconds": 600,
                }
            }
        )

        apps, _, settings, _ = collect_wiring(specs)

        assert "anymail" in apps
        assert settings["EMAIL_BACKEND"] == "anymail.backends.resend.EmailBackend"
        assert settings["QUICKSCALE_NOTIFICATIONS_RESEND_DOMAIN"] == "mg.example.com"
        assert (
            settings["QUICKSCALE_NOTIFICATIONS_RESEND_API_KEY_ENV_VAR"]
            == "OPS_RESEND_API_KEY"
        )

    def test_notifications_wiring_disabled_leaves_email_backend_unmanaged(self):
        specs = build_module_wiring_specs(
            {
                "notifications": {
                    "enabled": False,
                    "sender_name": "Ops",
                    "sender_email": "ops@example.com",
                }
            }
        )

        apps, _, settings, _ = collect_wiring(specs)

        assert "quickscale_modules_notifications" in apps
        assert "EMAIL_BACKEND" not in settings


class TestSocialModuleConfig:
    """Tests for social module configurator registration and wiring."""

    def test_social_default_config_keys_match_manifest_contract_intent(self):
        config = get_default_social_config()

        assert config["link_tree_enabled"] is True
        assert config["layout_variant"] == "list"
        assert config["embeds_enabled"] is True
        assert config["provider_allowlist"] == [
            "facebook",
            "instagram",
            "linkedin",
            "tiktok",
            "x",
            "youtube",
        ]

    def test_social_in_module_configurators(self):
        assert "social" in MODULE_CONFIGURATORS

        config = configure_social_module(non_interactive=True)

        assert config["link_tree_enabled"] is True
        assert config["embeds_enabled"] is True

    @patch("quickscale_cli.commands.module_config.click.prompt")
    @patch("quickscale_cli.commands.module_config.click.confirm")
    def test_configure_social_interactive_normalizes_provider_aliases(
        self,
        mock_confirm,
        mock_prompt,
    ):
        mock_confirm.side_effect = [True, True]
        mock_prompt.side_effect = ["cards", "Twitter, YouTube", 600, 18, 9]

        config = configure_social_module(non_interactive=False)

        assert config["layout_variant"] == "cards"
        assert config["provider_allowlist"] == ["x", "youtube"]
        assert config["cache_ttl_seconds"] == 600

    def test_apply_social_configuration_creates_managed_transport_files(
        self,
        tmp_path,
        capsys,
    ):
        project = _make_project(tmp_path)

        apply_social_configuration(
            project,
            {
                "layout_variant": "grid",
                "provider_allowlist": ["Twitter", "YouTube"],
                "cache_ttl_seconds": 600,
                "links_per_page": 18,
                "embeds_per_page": 9,
            },
        )

        managed_settings = (
            project / "myproject" / "settings" / "modules.py"
        ).read_text()
        managed_urls = (project / "myproject" / "urls_modules.py").read_text()
        managed_init = (
            project / "myproject" / "quickscale_managed" / "__init__.py"
        ).read_text()
        managed_social_urls = (
            project / "myproject" / "quickscale_managed" / "social_urls.py"
        ).read_text()
        managed_social_views = (
            project / "myproject" / "quickscale_managed" / "social_views.py"
        ).read_text()
        output = capsys.readouterr().out

        assert "quickscale_modules_social" not in managed_settings
        assert "QUICKSCALE_SOCIAL_LINK_TREE_PATH" in managed_settings
        assert "QUICKSCALE_SOCIAL_INTEGRATION_BASE_PATH" in managed_settings
        assert "myproject.quickscale_managed.social_urls" in managed_urls
        assert "QuickScale managed integration package" in managed_init
        assert 'path("embeds/", social_embeds_payload' in managed_social_urls
        assert "integration_base_path" in managed_social_views
        assert "quickscale_modules_social.services" in managed_social_views
        assert "build_social_link_tree_payload" in managed_social_views
        assert "build_social_embeds_payload" in managed_social_views
        assert "PAYLOAD_STATUS_HTTP" in managed_social_views
        assert "_error_payload" in managed_social_views
        assert "JsonResponse" in managed_social_views
        assert "fresh showcase_react keeps /social and /social/embeds" in output
        assert (
            "showcase_html and existing generated projects require manual theme adoption"
            in output
        )


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
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')

        with pytest.raises(click.Abort):
            _add_drf_and_filter_dependencies(tmp_path, pyproject)

    def test_adds_both_dependencies(self, tmp_path):
        """Add both DRF and django-filter when missing"""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')
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
            '[tool.poetry.dependencies]\npython = "^3.14"\n'
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
        pyproject.write_text('[tool.poetry.dependencies]\npython = "^3.14"\n')
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
        """Managed wiring remains idempotent when CRM reapplied."""
        project = _make_project(tmp_path)
        crm_dir = project / "modules" / "crm"
        crm_dir.mkdir(parents=True)
        (crm_dir / "pyproject.toml").write_text(
            "[tool.poetry.dependencies]\n"
            'djangorestframework = "^3.15.0"\n'
            'django-filter = "^23.0"\n'
        )
        config = get_default_crm_config()
        apply_crm_configuration(project, config)
        apply_crm_configuration(project, config)
        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert settings.count("quickscale_modules_crm") == 1

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

        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert "quickscale_modules_crm" in settings
        assert "'CRM_DEALS_PER_PAGE': 25" in settings
        assert "'CRM_CONTACTS_PER_PAGE': 50" in settings
        assert "'CRM_ENABLE_API': True" in settings
        assert "REST_FRAMEWORK" not in settings

        urls = (project / "myproject" / "urls_modules.py").read_text()
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

        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert "'CRM_ENABLE_API': False" in settings
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

        content = (project / "myproject" / "settings" / "modules.py").read_text()
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
        managed_urls = (project / "myproject" / "urls_modules.py").read_text()
        assert "quickscale_modules_crm.urls" in managed_urls

    def test_crm_no_pyproject(self, tmp_path):
        """Apply CRM when no pyproject.toml exists"""
        project = _make_project(tmp_path)
        (project / "pyproject.toml").unlink()

        config = get_default_crm_config()
        apply_crm_configuration(project, config)

        settings = (project / "myproject" / "settings" / "modules.py").read_text()
        assert "CRM_DEALS_PER_PAGE" in settings
