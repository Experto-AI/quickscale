from pathlib import Path

from quickscale_core.generator.generator import ProjectGenerator


class TestHtmlThemeIntegration:
    def test_html_theme_surfaces_operational_modules_without_admin_nav(
        self, tmp_path: Path
    ) -> None:
        """showcase_html should surface admin-backed modules on the dashboard, not in main nav."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_operational_modules"
        generator.generate("html_operational_modules", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        navigation = (
            output_path / "templates" / "components" / "navigation.html"
        ).read_text()

        assert "Open social" in index_html
        assert "/social/embeds" in navigation
        assert "Open notifications" in index_html
        assert "/admin/quickscale_modules_notifications/" in index_html
        assert "Open backup ops" in index_html
        assert "/admin/quickscale_modules_backups/backuppolicy/" in index_html
        assert (
            "There is no Django Admin configuration surface for storage secrets."
            in index_html
        )

        assert '<span class="nav-section-title">Social</span>' in navigation
        assert "Notifications" not in navigation
        assert "Backups" not in navigation

    def test_html_theme_generates_public_social_templates(self, tmp_path: Path) -> None:
        """showcase_html should generate stable public social templates."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_social_templates"
        generator.generate("html_social_templates", output_path)

        urls_py = (output_path / "html_social_templates" / "urls.py").read_text()
        link_tree_template = (
            output_path / "templates" / "social" / "link_tree.html"
        ).read_text()
        embeds_template = (
            output_path / "templates" / "social" / "embeds.html"
        ).read_text()

        assert 'r"^social/?$"' in urls_py
        assert 'r"^social/embeds/?$"' in urls_py
        assert urls_py.index('r"^social/?$"') < urls_py.index(
            're_path(r".*", custom_404_view)'
        )
        assert urls_py.index('r"^social/embeds/?$"') < urls_py.index(
            're_path(r".*", custom_404_view)'
        )
        assert 'class="qs-social-shell"' in link_tree_template
        assert 'class="qs-social-rail"' in link_tree_template
        assert "Link tree" in link_tree_template
        assert 'class="qs-social-shell"' in embeds_template
        assert 'class="qs-social-rail"' in embeds_template
        assert "Social Embeds" in embeds_template

    def test_html_theme_dockerfile_keeps_postgresql_client_for_backup_ops(
        self, tmp_path: Path
    ) -> None:
        """showcase_html should generate the same backup-capable runtime image."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_backup_runtime"
        generator.generate("html_backup_runtime", output_path)

        dockerfile = (output_path / "Dockerfile").read_text()

        assert "postgresql-client-18" in dockerfile
        assert "apt.postgresql.org" in dockerfile
        assert "python:3.14-slim-bookworm" in dockerfile

    def test_html_theme_generates_backups_admin_overrides(self, tmp_path: Path) -> None:
        """showcase_html should expose backup actions on admin index pages."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_backups_admin_overrides"
        generator.generate("html_backups_admin_overrides", output_path)

        admin_index = (output_path / "templates" / "admin" / "index.html").read_text()
        app_index = (output_path / "templates" / "admin" / "app_index.html").read_text()

        assert "Create backup now" not in admin_index
        assert "Open backup ops" in admin_index
        assert 'app.app_label == "quickscale_modules_backups"' in admin_index
        assert (
            'action="/admin/quickscale_modules_backups/backuppolicy/ops/create/"'
            in app_index
        )
        assert "Open backup ops" in app_index
        assert 'app_label == "quickscale_modules_backups"' in app_index
