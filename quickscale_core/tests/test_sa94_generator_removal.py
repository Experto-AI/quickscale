"""SA94 Phase 3: showcase_html theme removal verification.

This test file validates:
- React generation with no modules emits correct frontend output and no HTML-only artifacts.
- React generation with social module preserves TemplateView routes for /social and /social/embeds.
- The generator no longer accepts ``showcase_html`` as a valid theme.
- ``_THEME_DEST_MAP`` no longer contains a ``showcase_html`` entry.
- Generated views.py contains no HTML-only ``social_link_tree_view`` / ``social_embeds_view``.
- Generated urls.py uses ``TemplateView`` (not function views) for social routes.
"""

from pathlib import Path

import pytest

from quickscale_core.generator.generator import ProjectGenerator, _THEME_DEST_MAP


class TestShowcaseHtmlRemoval:
    """Verify the generator has fully removed the showcase_html theme."""

    def test_showcase_html_not_in_theme_dest_map(self) -> None:
        """``_THEME_DEST_MAP`` must not contain a ``showcase_html`` entry."""
        assert "showcase_html" not in _THEME_DEST_MAP

    def test_showcase_html_rejected_by_generator(self) -> None:
        """``ProjectGenerator`` must reject ``showcase_html`` as a retired theme."""
        with pytest.raises(ValueError, match="showcase_html"):
            ProjectGenerator(theme="showcase_html")

    def test_showcase_html_theme_dir_does_not_exist(self) -> None:
        """The ``showcase_html`` theme directory must be deleted."""
        generator = ProjectGenerator(theme="showcase_react")
        theme_dir = generator.template_dir / "themes" / "showcase_html"
        assert not theme_dir.exists()


class TestReactNoModulesGeneration:
    """React theme generation with no modules selected.

    Verifies the generated project has the expected React frontend and
    no HTML-only scaffolding.
    """

    PROJECT_NAME = "react_no_modules"

    @pytest.fixture(autouse=True)
    def _generate(self, tmp_path: Path) -> None:
        generator = ProjectGenerator(theme="showcase_react", selected_modules=[])
        self._output_path = tmp_path / self.PROJECT_NAME
        generator.generate(self.PROJECT_NAME, self._output_path)

    @property
    def output_path(self) -> Path:
        return self._output_path

    # --- Frontend output exists ---
    def test_frontend_structure_exists(self) -> None:
        """React frontend directory and key files should be present."""
        assert (self.output_path / "frontend" / "package.json").exists()
        assert (self.output_path / "frontend" / "vite.config.ts").exists()
        assert (self.output_path / "frontend" / "src" / "main.tsx").exists()
        assert (self.output_path / "frontend" / "src" / "App.tsx").exists()

    def test_django_templates_exist(self) -> None:
        """Core Django templates should be present."""
        assert (self.output_path / "templates" / "index.html").exists()
        assert (self.output_path / "templates" / "base.html").exists()
        assert (self.output_path / "templates" / "404.html").exists()
        assert (self.output_path / "templates" / "500.html").exists()

    # --- HTML-root assets/components do NOT exist ---
    def test_no_components_directory_in_templates(self) -> None:
        """No ``templates/components/`` should be generated (HTML-only)."""
        assert not (self.output_path / "templates" / "components").exists()

    def test_no_root_static_assets(self) -> None:
        """No root ``static/`` directory should be generated (HTML-only)."""
        assert not (self.output_path / "static" / "css" / "style.css").exists()
        assert not (self.output_path / "static" / "images" / "favicon.svg").exists()

    # --- HTML-only views/bindings are absent ---
    def test_views_no_html_social_functions(self) -> None:
        """Generated views.py must not contain HTML-only social view functions."""
        views_py = (self.output_path / self.PROJECT_NAME / "views.py").read_text()
        assert "social_link_tree_view" not in views_py
        assert "social_embeds_view" not in views_py

    def test_urls_uses_template_view_for_social(self) -> None:
        """Generated urls.py must use ``TemplateView`` for social routes, not function views."""
        urls_py = (self.output_path / self.PROJECT_NAME / "urls.py").read_text()
        # Must use TemplateView for social routes
        assert 'TemplateView.as_view(template_name="social/link_tree.html")' in urls_py
        assert 'TemplateView.as_view(template_name="social/embeds.html")' in urls_py
        # Must NOT use function-view imports
        assert "social_link_tree_view" not in urls_py
        assert "social_embeds_view" not in urls_py

    def test_urls_has_react_shell_and_spa_catch_all(self) -> None:
        """Generated urls.py must include the React shell view and SPA catch-all."""
        urls_py = (self.output_path / self.PROJECT_NAME / "urls.py").read_text()
        assert (
            'react_shell_view = TemplateView.as_view(template_name="index.html")'
            in urls_py
        )
        assert "react_shell_urlpatterns" in urls_py
        assert "urlpatterns += react_shell_urlpatterns" in urls_py
        # SPA catch-all must be unconditional
        assert 're_path(r".*", react_shell_view)' in urls_py

    def test_full_project_structure(self) -> None:
        """Basic generated project structure should be intact."""
        assert (self.output_path / "manage.py").exists()
        assert (self.output_path / "Makefile").exists()
        assert (self.output_path / "pyproject.toml").exists()
        assert (self.output_path / "README.md").exists()


class TestReactSocialGeneration:
    """React theme generation with social module selected.

    Verifies that the social routes are correctly generated as TemplateView routes.
    """

    PROJECT_NAME = "react_with_social"

    @pytest.fixture(autouse=True)
    def _generate(self, tmp_path: Path) -> None:
        generator = ProjectGenerator(
            theme="showcase_react", selected_modules=["social"]
        )
        self._output_path = tmp_path / self.PROJECT_NAME
        generator.generate(self.PROJECT_NAME, self._output_path)

    @property
    def output_path(self) -> Path:
        return self._output_path

    def test_social_routes_preserved(self) -> None:
        """Social routes must be present and use TemplateView."""
        urls_py = (self.output_path / self.PROJECT_NAME / "urls.py").read_text()
        assert 'r"^social/?$"' in urls_py
        assert 'r"^social/embeds/?$"' in urls_py
        assert 'TemplateView.as_view(template_name="social/link_tree.html")' in urls_py
        assert 'TemplateView.as_view(template_name="social/embeds.html")' in urls_py
        # No function view imports for social
        assert "social_link_tree_view" not in urls_py
        assert "social_embeds_view" not in urls_py

    def test_social_templates_exist(self) -> None:
        """Social Django template wrappers must exist."""
        assert (self.output_path / "templates" / "social" / "link_tree.html").exists()
        assert (self.output_path / "templates" / "social" / "embeds.html").exists()

    def test_social_frontend_pages_present(self) -> None:
        """Social React pages should be present when social module is selected."""
        frontend = self.output_path / "frontend"
        assert (frontend / "src" / "pages" / "SocialLinkTreePublicPage.tsx").exists()
        assert (frontend / "src" / "pages" / "SocialEmbedsPublicPage.tsx").exists()

    def test_views_no_html_social_functions(self) -> None:
        """Generated views.py must not contain HTML-only social view functions."""
        views_py = (self.output_path / self.PROJECT_NAME / "views.py").read_text()
        assert "social_link_tree_view" not in views_py
        assert "social_embeds_view" not in views_py

    def test_no_html_components(self) -> None:
        """No HTML-only components directory should be generated."""
        assert not (self.output_path / "templates" / "components").exists()
