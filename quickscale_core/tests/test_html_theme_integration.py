from pathlib import Path

from quickscale_core.generator.generator import ProjectGenerator


class TestHtmlThemeIntegration:
    def test_html_theme_surfaces_operational_modules_without_admin_nav(
        self, tmp_path: Path
    ) -> None:
        """showcase_html should keep starter output focused on shipped dashboard surfaces."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_operational_modules"
        generator.generate("html_operational_modules", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        navigation = (
            output_path / "templates" / "components" / "navigation.html"
        ).read_text()

        assert "Open social" not in index_html
        assert "/social/embeds" not in navigation
        assert "Open notifications" in index_html
        assert "/admin/quickscale_modules_notifications/" in index_html
        assert "Open backup ops" in index_html
        assert "/admin/quickscale_modules_backups/backuppolicy/" in index_html
        assert (
            "There is no Django Admin configuration surface for storage secrets."
            in index_html
        )
        assert "Billing" not in index_html
        assert "Teams" not in index_html

        assert '<span class="nav-section-title">Social</span>' not in navigation
        assert '<span class="nav-section-title">Billing</span>' not in navigation
        assert '<span class="nav-section-title">Teams</span>' not in navigation
        assert "Notifications" not in navigation
        assert "Backups" not in navigation

    def test_html_theme_does_not_generate_public_social_templates(
        self, tmp_path: Path
    ) -> None:
        """showcase_html should not scaffold the public social pages or routes."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_social_templates"
        generator.generate("html_social_templates", output_path)

        urls_py = (output_path / "html_social_templates" / "urls.py").read_text()
        link_tree_template = output_path / "templates" / "social" / "link_tree.html"
        embeds_template = output_path / "templates" / "social" / "embeds.html"

        assert 'r"^social/?$"' not in urls_py
        assert 'r"^social/embeds/?$"' not in urls_py
        assert not link_tree_template.exists()
        assert not embeds_template.exists()

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
        assert "apt.postgresql.org.asc" in dockerfile
        assert "python:3.14-slim-bookworm" in dockerfile
        assert "gpg --dearmor" not in dockerfile
        assert "gnupg" not in dockerfile

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
