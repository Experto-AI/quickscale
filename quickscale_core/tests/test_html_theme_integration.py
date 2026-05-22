import types
from pathlib import Path

from django.template import Context, Engine

from quickscale_core.generator.generator import ProjectGenerator


BILLING_GUARD = "{% if 'quickscale_modules_billing' in settings.INSTALLED_APPS %}"
STORAGE_GUARD = "{% if 'quickscale_modules_storage' in settings.INSTALLED_APPS %}"
SOCIAL_GUARD = "{% if 'quickscale_modules_social' in settings.INSTALLED_APPS %}"
AUTH_GUARD = "{% if user.is_authenticated %}"
ELSE_GUARD = "{% else %}"
ENDIF_GUARD = "{% endif %}"


def _slice_between(rendered_template: str, start_marker: str, end_marker: str) -> str:
    _, remainder = rendered_template.split(start_marker, 1)
    scoped_block, _ = remainder.split(end_marker, 1)
    return scoped_block


def _billing_block(rendered_template: str) -> str:
    return _slice_between(rendered_template, BILLING_GUARD, STORAGE_GUARD)


def _billing_navigation_block(rendered_template: str) -> str:
    return _slice_between(rendered_template, BILLING_GUARD, SOCIAL_GUARD)


def _split_auth_branches(scoped_block: str) -> tuple[str, str, str]:
    prefix, auth_remainder = scoped_block.split(AUTH_GUARD, 1)
    authenticated_branch, remaining = auth_remainder.split(ELSE_GUARD, 1)
    unauthenticated_branch, _ = remaining.split(ENDIF_GUARD, 1)
    return prefix, authenticated_branch, unauthenticated_branch


def _render_navigation(
    templates_dir: Path,
    *,
    project_name: str,
    installed_apps: list[str],
    link_tree_enabled: bool,
    embeds_enabled: bool,
) -> str:
    engine = Engine(dirs=[str(templates_dir)])
    return engine.get_template("components/navigation.html").render(
        Context(
            {
                "project_name": project_name,
                "settings": types.SimpleNamespace(
                    INSTALLED_APPS=installed_apps,
                    QUICKSCALE_SOCIAL_LINK_TREE_ENABLED=link_tree_enabled,
                    QUICKSCALE_SOCIAL_EMBEDS_ENABLED=embeds_enabled,
                ),
                "user": types.SimpleNamespace(
                    is_authenticated=False,
                    is_staff=False,
                ),
            }
        )
    )


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

        assert "quickscale_modules_social" in index_html
        assert "/social/embeds" in navigation
        assert "Open notifications" in index_html
        assert "/admin/quickscale_modules_notifications/" in index_html
        assert "Open backup ops" in index_html
        assert "/admin/quickscale_modules_backups/backuppolicy/" in index_html
        assert "{% if user.is_staff %}" in index_html
        assert "The CRM dashboard is limited to staff users." in index_html
        assert "Sign in with a staff account to open the CRM dashboard." in index_html
        assert (
            "There is no Django Admin configuration surface for storage secrets."
            in index_html
        )
        assert "Billing" in index_html
        assert "/billing/pricing/" in index_html
        assert "{{ modules.billing.url }}" in index_html
        assert "Teams" not in index_html

        assert 'class="qs-topbar"' in navigation
        assert 'class="qs-topbar-brand"' in navigation
        assert "Showcase HTML starter" in navigation
        assert ">App</a>" in navigation
        assert ">Organizations</a>" in navigation
        assert "/billing/pricing/" in navigation
        assert "{{ modules.billing.url }}" in navigation
        assert "{% url 'account_login' %}" in navigation
        assert "{% url 'account_signup' %}" in navigation
        assert "{% url 'account_logout' %}" in navigation
        assert "{% if user.is_staff %}" in navigation
        assert ">CRM</a>" in navigation
        assert 'class="qs-topbar-status"' in navigation
        assert ">Docs</a>" in navigation
        assert "Notifications" not in navigation
        assert "Backups" not in navigation

    def test_html_theme_billing_card_and_auth_aware_links(self, tmp_path: Path) -> None:
        """showcase_html should surface billing through module-owned Django pages."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_billing_card"
        generator.generate("html_billing_card", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        billing_block = _billing_block(index_html)
        billing_actions = _slice_between(
            billing_block,
            '<div class="module-card-actions">',
            "</div>",
        )
        actions_prefix, authenticated_actions, unauthenticated_actions = (
            _split_auth_branches(billing_actions)
        )

        assert BILLING_GUARD in index_html
        assert "<h3>Billing</h3>" in billing_block
        assert '<span class="module-badge">Active</span>' in billing_block
        assert (
            "<p>Stripe-backed pricing and customer billing pages owned by the billing "
            "module.</p>" in billing_block
        )
        assert (
            '<p class="module-note">QuickScale keeps billing on module-owned Django '
            "pages rather than generating a starter-owned frontend billing app.</p>"
            in billing_block
        )
        assert billing_actions.count(AUTH_GUARD) == 1
        assert billing_actions.count(ELSE_GUARD) == 1
        assert "/billing/" not in actions_prefix
        assert (
            '<a class="module-link" href="{{ modules.billing.url }}">Open billing</a>'
            in authenticated_actions
        )
        assert "/billing/pricing/" not in authenticated_actions
        assert "/billing/dashboard/" not in authenticated_actions
        assert (
            '<a class="module-link" href="/billing/pricing/">View pricing</a>'
            in unauthenticated_actions
        )
        assert "/billing/dashboard/" not in unauthenticated_actions

    def test_html_theme_billing_navigation_section(self, tmp_path: Path) -> None:
        """showcase_html navigation should keep billing auth-aware and teams-free."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_billing_navigation"
        generator.generate("html_billing_navigation", output_path)

        navigation = (
            output_path / "templates" / "components" / "navigation.html"
        ).read_text()
        billing_block = _billing_navigation_block(navigation)
        billing_prefix, authenticated_items, unauthenticated_items = (
            _split_auth_branches(billing_block)
        )

        assert BILLING_GUARD in navigation
        assert billing_block.count(AUTH_GUARD) == 1
        assert billing_block.count(ELSE_GUARD) == 1
        assert "/billing/dashboard/" not in billing_prefix
        assert (
            '<a href="{{ modules.billing.url }}" class="qs-topbar-link">Billing</a>'
            in authenticated_items
        )
        assert "/billing/pricing/" not in authenticated_items
        assert "/billing/dashboard/" not in authenticated_items
        assert (
            '<a href="/billing/pricing/" class="qs-topbar-link">Pricing</a>'
            in unauthenticated_items
        )
        assert "/billing/dashboard/" not in unauthenticated_items
        assert '<span class="nav-section-title">Teams</span>' not in navigation

    def test_html_theme_billing_installed_apps_guard(self, tmp_path: Path) -> None:
        """showcase_html billing links should stay inside the billing app guard."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_billing_guard"
        generator.generate("html_billing_guard", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        navigation = (
            output_path / "templates" / "components" / "navigation.html"
        ).read_text()

        assert index_html.count(BILLING_GUARD) == 1
        index_prefix, index_remainder = index_html.split(BILLING_GUARD, 1)
        index_billing_block, index_suffix = index_remainder.split(STORAGE_GUARD, 1)
        assert "/billing/" not in index_prefix
        assert "/billing/" not in index_suffix
        assert index_billing_block.count("/billing/pricing/") == 1
        assert index_billing_block.count("{{ modules.billing.url }}") == 1
        assert "/billing/dashboard/" not in index_billing_block
        assert index_billing_block.rstrip().endswith("{% endif %}")

        assert navigation.count(BILLING_GUARD) == 1
        nav_prefix, nav_remainder = navigation.split(BILLING_GUARD, 1)
        nav_billing_block, nav_suffix = nav_remainder.split(SOCIAL_GUARD, 1)
        assert "/billing/" not in nav_prefix
        assert "/billing/" not in nav_suffix
        assert nav_billing_block.count("/billing/pricing/") == 1
        assert nav_billing_block.count("{{ modules.billing.url }}") == 1
        assert "/billing/dashboard/" not in nav_billing_block
        assert nav_billing_block.count(AUTH_GUARD) == 1
        assert nav_billing_block.rstrip().endswith("{% endif %}")

    def test_html_theme_billing_no_teams_entry(self, tmp_path: Path) -> None:
        """showcase_html should not surface teams before that module ships."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_billing_no_teams"
        generator.generate("html_billing_no_teams", output_path)

        index_html = (output_path / "templates" / "index.html").read_text()
        navigation = (
            output_path / "templates" / "components" / "navigation.html"
        ).read_text()

        for generated_file in (index_html, navigation):
            assert "Teams" not in generated_file
            assert "quickscale_modules_teams" not in generated_file

    def test_html_theme_generates_public_social_templates_and_routes(
        self, tmp_path: Path
    ) -> None:
        """showcase_html should scaffold server-rendered public social pages and routes."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_social_templates"
        generator.generate("html_social_templates", output_path)

        urls_py = (output_path / "html_social_templates" / "urls.py").read_text()
        link_tree_template = output_path / "templates" / "social" / "link_tree.html"
        embeds_template = output_path / "templates" / "social" / "embeds.html"

        assert 'r"^social/?$"' in urls_py
        assert 'r"^social/embeds/?$"' in urls_py
        assert link_tree_template.exists()
        assert embeds_template.exists()
        assert "social_link_tree_view" in urls_py
        assert "social_embeds_view" in urls_py

    def test_html_theme_navigation_renders_both_public_social_links_by_default(
        self, tmp_path: Path
    ) -> None:
        """showcase_html should render both public social links when both flags are enabled."""
        generator = ProjectGenerator(theme="showcase_html")
        output_path = tmp_path / "html_social_navigation"
        generator.generate("html_social_navigation", output_path)

        rendered_navigation = _render_navigation(
            output_path / "templates",
            project_name=output_path.name,
            installed_apps=["quickscale_modules_social"],
            link_tree_enabled=True,
            embeds_enabled=True,
        )
        social_link = '<a href="/social/" class="qs-topbar-link">Social</a>'
        embeds_link = '<a href="/social/embeds/" class="qs-topbar-link">Embeds</a>'

        assert (
            "{% if settings.QUICKSCALE_SOCIAL_LINK_TREE_ENABLED %}"
            not in rendered_navigation
        )
        assert (
            "{% if settings.QUICKSCALE_SOCIAL_EMBEDS_ENABLED %}"
            not in rendered_navigation
        )
        assert rendered_navigation.count(social_link) == 1
        assert rendered_navigation.count(embeds_link) == 1
        assert rendered_navigation.index(social_link) < rendered_navigation.index(
            embeds_link
        )

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
        assert "python:3.13-slim-bookworm" in dockerfile
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
