"""Tests for auth module template rendering and CSS loading"""

import pytest
from django.urls import reverse


@pytest.mark.django_db
class TestTemplateCSSLoading:
    """Tests for CSS loading in auth templates"""

    def test_auth_base_template_has_css_block(self):
        """Test that auth base template includes CSS in extra_css block"""
        # Read the template file directly to verify structure
        from pathlib import Path
        import quickscale_modules_auth

        module_path = Path(quickscale_modules_auth.__file__).parent
        template_path = (
            module_path / "templates" / "quickscale_modules_auth" / "base.html"
        )

        assert template_path.exists(), f"Template not found at {template_path}"

        template_content = template_path.read_text()

        # Verify template extends base.html
        assert '{% extends "base.html" %}' in template_content

        # Verify CSS block exists and loads auth.css
        assert "{% block extra_css %}" in template_content
        assert "quickscale_modules_auth/css/auth.css" in template_content

        # Verify block.super is called to inherit parent CSS
        assert "{{ block.super }}" in template_content

    def test_profile_page_includes_auth_css(self, authenticated_client):
        """Test profile page includes auth module CSS"""
        response = authenticated_client.get(reverse("quickscale_auth:profile"))
        assert response.status_code == 200
        assert b"quickscale_modules_auth/css/auth.css" in response.content

    def test_profile_edit_page_includes_auth_css(self, authenticated_client):
        """Test profile edit page includes auth module CSS"""
        response = authenticated_client.get(reverse("quickscale_auth:profile-edit"))
        assert response.status_code == 200
        assert b"quickscale_modules_auth/css/auth.css" in response.content

    def test_account_delete_page_includes_auth_css(self, authenticated_client):
        """Test account delete page includes auth module CSS"""
        response = authenticated_client.get(reverse("quickscale_auth:account-delete"))
        assert response.status_code == 200
        assert b"quickscale_modules_auth/css/auth.css" in response.content

    def test_css_loading_order_in_module_templates(self, authenticated_client):
        """Test that main CSS loads before auth CSS in our module templates"""
        response = authenticated_client.get(reverse("quickscale_auth:profile"))
        assert response.status_code == 200

        content = response.content.decode("utf-8")
        main_css_pos = content.find('href="/static/css/style.css"')
        auth_css_pos = content.find("quickscale_modules_auth/css/auth.css")

        # Both should be present
        assert main_css_pos != -1, "Main CSS not found in response"
        assert auth_css_pos != -1, "Auth CSS not found in response"

        # Main CSS should come before auth CSS (due to block.super)
        assert (
            main_css_pos < auth_css_pos
        ), "CSS loading order incorrect: main CSS should load before auth CSS"


@pytest.mark.django_db
class TestNavigationStyling:
    """Tests for navigation consistency across pages"""

    def test_home_page_has_navigation(self, anonymous_client):
        """Test home page includes navigation component"""
        response = anonymous_client.get("/")
        assert response.status_code == 200
        assert b'class="site-nav"' in response.content
        assert b'class="nav-brand"' in response.content

    def test_profile_page_has_navigation(self, authenticated_client):
        """Test profile page includes navigation component (uses our custom template)"""
        response = authenticated_client.get(reverse("quickscale_auth:profile"))
        assert response.status_code == 200
        assert b'class="site-nav"' in response.content
        assert b'class="nav-brand"' in response.content

    def test_navigation_consistency_in_module_pages(self, authenticated_client):
        """Test navigation uses consistent CSS classes in our module pages"""
        # Check home page
        home_response = authenticated_client.get("/")
        assert b'class="nav-menu"' in home_response.content

        # Check profile page (our custom template)
        profile_response = authenticated_client.get(reverse("quickscale_auth:profile"))
        assert b'class="nav-menu"' in profile_response.content

        # Both should have the same navigation structure
        assert home_response.content.count(
            b'class="site-nav"'
        ) == profile_response.content.count(b'class="site-nav"')
