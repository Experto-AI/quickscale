"""Tests for blog template inheritance and CSS loading.

These pin the shared-shell contract: the blog base template must extend the
project's ``base.html`` rather than emitting its own ``<html>`` document, so
blog pages inherit the project shell instead of duplicating it.
"""

from pathlib import Path

import quickscale_modules_blog

MODULE_PATH = Path(quickscale_modules_blog.__file__).parent
BASE_TEMPLATE = MODULE_PATH / "templates" / "quickscale_blog" / "base.html"
CHILD_DIR = MODULE_PATH / "templates" / "quickscale_blog" / "blog"


class TestBaseTemplateInheritance:
    """The blog base template composes with the project shell."""

    def test_base_template_exists(self):
        assert BASE_TEMPLATE.exists(), f"Template not found at {BASE_TEMPLATE}"

    def test_base_extends_project_base(self):
        """Base template extends base.html instead of being a standalone document."""
        content = BASE_TEMPLATE.read_text()
        assert '{% extends "base.html" %}' in content

    def test_base_is_not_a_standalone_document(self):
        """No duplicated page shell: the project base owns <html>, <body>, footer."""
        content = BASE_TEMPLATE.read_text().lower()
        for tag in ("<!doctype", "<html", "<head>", "<body>", "<footer"):
            assert tag not in content, f"{tag} must come from base.html, not blog"

    def test_base_inherits_parent_css_via_block_super(self):
        """extra_css adds to the parent block rather than replacing it."""
        content = BASE_TEMPLATE.read_text()
        assert "{% block extra_css %}" in content
        assert "{{ block.super }}" in content
        assert "quickscale_blog/css/blog.css" in content

    def test_base_has_no_inline_style_block(self):
        """Styling lives in a stylesheet, not inlined in the template."""
        content = BASE_TEMPLATE.read_text().lower()
        assert "<style" not in content

    def test_base_exposes_child_content_block(self):
        """Children fill blog_content, since content is used by the base itself."""
        content = BASE_TEMPLATE.read_text()
        assert "{% block blog_content %}" in content

    def test_base_wraps_child_block_in_content_div(self):
        """CSS scopes content rules to the wrapper, so the wrapper must exist.

        base.html's reset zeroes default margins; blog.css restores spacing
        under .blog-content. Drop the wrapper and the page loses its rhythm.
        """
        content = BASE_TEMPLATE.read_text()
        assert '<div class="blog-content">' in content

    def test_base_includes_orgs_debug_banner(self):
        """The VIEW-AS banner survives the move to the shared shell."""
        content = BASE_TEMPLATE.read_text()
        assert "quickscale_orgs/_debug_banner.html" in content


class TestChildTemplates:
    """Child templates target the module content block."""

    def test_children_use_module_content_block(self):
        for name in [
            "post_list.html",
            "post_detail.html",
            "category_list.html",
            "tag_list.html",
        ]:
            content = (CHILD_DIR / name).read_text()
            assert "{% block blog_content %}" in content, name
            assert "{% block content %}" not in content, name
