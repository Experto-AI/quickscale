"""Conformance checks for token-styled module page templates."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]

BASE_CONTRACTS = {
    "auth": (
        "quickscale_modules/auth/src/quickscale_modules_auth/templates/"
        "quickscale_modules_auth/base.html",
        "quickscale_modules_auth/css/auth.css",
    ),
    "billing": (
        "quickscale_modules/billing/src/quickscale_modules_billing/templates/"
        "quickscale_modules_billing/base.html",
        "quickscale_modules_billing/css/billing.css",
    ),
    "blog": (
        "quickscale_modules/blog/src/quickscale_modules_blog/templates/"
        "quickscale_modules_blog/blog/base.html",
        "quickscale_modules_blog/blog.css",
    ),
    "listings": (
        "quickscale_modules/listings/src/quickscale_modules_listings/templates/"
        "quickscale_modules_listings/listings/base.html",
        "quickscale_modules_listings/listings.css",
    ),
    "crm": (
        "quickscale_modules/crm/src/quickscale_modules_crm/templates/"
        "quickscale_modules_crm/crm/base.html",
        "quickscale_modules_crm/crm.css",
    ),
}

CHILD_CONTRACTS = {
    "quickscale_modules/auth/src/quickscale_modules_auth/templates/"
    "quickscale_modules_auth/account/*.html": "quickscale_modules_auth/base.html",
    "quickscale_modules/billing/src/quickscale_modules_billing/templates/"
    "quickscale_modules_billing/*.html": "quickscale_modules_billing/base.html",
    "quickscale_modules/billing/src/quickscale_modules_billing/templates/"
    "quickscale_modules_billing/billing/*.html": "quickscale_modules_billing/base.html",
    "quickscale_modules/blog/src/quickscale_modules_blog/templates/"
    "quickscale_modules_blog/blog/*.html": "quickscale_modules_blog/blog/base.html",
    "quickscale_modules/listings/src/quickscale_modules_listings/templates/"
    "quickscale_modules_listings/listings/*.html": (
        "quickscale_modules_listings/listings/base.html"
    ),
    "quickscale_modules/crm/src/quickscale_modules_crm/templates/"
    "quickscale_modules_crm/crm/*.html": "quickscale_modules_crm/crm/base.html",
}

MODULE_STYLESHEETS = [
    "quickscale_modules/auth/src/quickscale_modules_auth/static/"
    "quickscale_modules_auth/css/auth.css",
    "quickscale_modules/billing/src/quickscale_modules_billing/static/"
    "quickscale_modules_billing/css/billing.css",
    "quickscale_modules/blog/src/quickscale_modules_blog/static/"
    "quickscale_modules_blog/blog.css",
    "quickscale_modules/listings/src/quickscale_modules_listings/static/"
    "quickscale_modules_listings/listings.css",
    "quickscale_modules/crm/src/quickscale_modules_crm/static/"
    "quickscale_modules_crm/crm.css",
]

AFFECTED_PRESENTATION_ROOTS = [
    ROOT / "quickscale_modules" / module_name / "src"
    for module_name in ("auth", "billing", "blog", "listings", "crm")
]


@pytest.mark.parametrize(("module_name", "contract"), BASE_CONTRACTS.items())
def test_module_base_extends_project_shell_and_loads_stylesheet(
    module_name: str,
    contract: tuple[str, str],
) -> None:
    template_path, stylesheet = contract
    content = (ROOT / template_path).read_text()

    assert '{% extends "base.html" %}' in content, module_name
    assert "{% block extra_css %}" in content, module_name
    assert "{{ block.super }}" in content, module_name
    assert stylesheet in content, module_name
    assert "<style" not in content.lower(), module_name


@pytest.mark.parametrize(("pattern", "parent"), CHILD_CONTRACTS.items())
def test_every_module_page_inherits_its_styled_base(pattern: str, parent: str) -> None:
    paths = sorted(ROOT.glob(pattern))
    assert paths, pattern

    for path in paths:
        if path.name == "base.html":
            continue
        content = path.read_text()
        assert f'{{% extends "{parent}" %}}' in content, path
        assert "<style" not in content.lower(), path


@pytest.mark.parametrize("stylesheet", MODULE_STYLESHEETS)
def test_module_stylesheets_use_shared_tokens(stylesheet: str) -> None:
    content = (ROOT / stylesheet).read_text()

    assert "hsl(var(--" in content
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", content)
    assert not re.search(r"\brgba?\(", content)


def test_affected_presentation_references_only_canonical_tokens() -> None:
    token_source = (
        ROOT / "quickscale_core/src/quickscale_core/generator/templates/themes/"
        "showcase_react/src/index.css"
    ).read_text()
    canonical_tokens = set(re.findall(r"(--[a-z0-9-]+)\s*:", token_source))

    for source_root in AFFECTED_PRESENTATION_ROOTS:
        for pattern in ("*.css", "*.html", "*.js"):
            for path in source_root.rglob(pattern):
                referenced_tokens = set(
                    re.findall(r"var\((--[a-z0-9-]+)", path.read_text())
                )
                assert referenced_tokens <= canonical_tokens, (
                    f"{path} references undefined tokens: "
                    f"{sorted(referenced_tokens - canonical_tokens)}"
                )


def test_auth_script_uses_token_backed_strength_classes() -> None:
    auth_script = (
        ROOT / "quickscale_modules/auth/src/quickscale_modules_auth/static/"
        "quickscale_modules_auth/js/auth.js"
    ).read_text()

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", auth_script)
    assert ".style.color" not in auth_script
    for strength in ("weak", "moderate", "strong"):
        assert f"password-strength--{strength}" in auth_script


def test_generated_shell_loads_the_react_token_source() -> None:
    theme = ROOT / (
        "quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react"
    )
    token_source = (theme / "src/index.css").read_text()
    shell = (theme / "templates/base.html.j2").read_text()

    assert "--primary:" in token_source
    assert "--radius:" in token_source
    assert "frontend/assets/index.css" in shell
    assert "settings.QUICKSCALE_FRONTEND_ORIGIN" in shell
    assert "{% if settings.DEBUG %}" in shell
    assert "hsl(var(--foreground))" in shell
    assert 'localStorage.getItem("theme-storage")' in shell
    assert "classList.add(theme)" in shell
    assert "--primary:" not in shell


def test_generated_shell_resolves_tokens_for_development_and_production(
    generated_project_path: Path,
) -> None:
    shell = (generated_project_path / "templates" / "base.html").read_text()
    react_host = (generated_project_path / "templates" / "index.html").read_text()
    vite_config = (generated_project_path / "frontend" / "vite.config.ts").read_text()
    local_settings = (
        generated_project_path / "testproject" / "settings" / "local.py"
    ).read_text()

    assert (generated_project_path / "frontend" / "src" / "index.css").is_file()
    assert "{% if settings.DEBUG %}" in shell
    live_token_href = (
        "{{ settings.QUICKSCALE_FRONTEND_ORIGIN|default:'http://localhost:5173' }}"
        "/static/frontend/src/index.css"
    )
    assert live_token_href in shell
    assert live_token_href in react_host
    assert "{% if settings.DEBUG %}" in react_host
    frontend_port_setting = """QUICKSCALE_FRONTEND_HOST_PORT = config(
    "QUICKSCALE_FRONTEND_HOST_PORT",
    default=5173,
    cast=int,
)"""
    assert frontend_port_setting in local_settings
    assert 'config("QUICKSCALE_FRONTEND_ORIGIN", default="")' in local_settings
    assert 'f"http://localhost:{QUICKSCALE_FRONTEND_HOST_PORT}"' in local_settings
    assert "{% static 'frontend/assets/index.css' %}" in shell
    assert "{% static 'frontend/assets/index.css' %}" in react_host
    assert "base: '/static/frontend/'" in vite_config
    assert "port: 5173" in vite_config
    assert "strictPort: true" in vite_config
    assert "QUICKSCALE_FRONTEND_ORIGIN" in vite_config
    assert "allowedHosts: frontendAllowedHosts" in vite_config
    assert "'^/static(?:$|/(?!frontend(?:/|$)))':" in vite_config
    assert "'/static':" not in vite_config


def test_generated_debug_workflows_keep_vite_available(
    generated_project_path: Path,
) -> None:
    compose = (generated_project_path / "docker-compose.yml").read_text()
    readme = (generated_project_path / "README.md").read_text()

    assert "corepack pnpm run build && corepack pnpm run dev --host 0.0.0.0" in compose
    assert '"${QUICKSCALE_FRONTEND_HOST_PORT:-5173}:5173"' in compose
    assert (
        "QUICKSCALE_FRONTEND_HOST_PORT=${QUICKSCALE_FRONTEND_HOST_PORT:-5173}"
        in compose
    )
    assert (
        compose.count("QUICKSCALE_FRONTEND_ORIGIN=${QUICKSCALE_FRONTEND_ORIGIN:-}") == 2
    )
    assert "127.0.0.1:5173/static/frontend/src/index.css" in compose
    assert "retries: 120" in compose
    assert "condition: service_healthy" in compose
    assert "pnpm --dir frontend build && pnpm --dir frontend dev" in readme
    assert "In a second terminal, from the project root" in readme


def test_generated_react_hosts_do_not_override_the_shell_token_stylesheet(
    generated_project_path: Path,
) -> None:
    templates = generated_project_path / "templates"
    live_token_href = (
        "{{ settings.QUICKSCALE_FRONTEND_ORIGIN|default:'http://localhost:5173' }}"
        "/static/frontend/src/index.css"
    )

    assert live_token_href in (templates / "base.html").read_text()
    assert live_token_href in (templates / "index.html").read_text()
    for relative_path in ("social/link_tree.html", "social/embeds.html"):
        social_host = (templates / relative_path).read_text()
        assert "frontend/assets/index.css" not in social_host
