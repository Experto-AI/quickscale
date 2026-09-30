"""Conformance checks for token-styled module page templates.

The module and page sets derive from discovery (decisions.md rules 8 and 37):
every module discovered under ``quickscale_modules/*/module.yml`` that ships
page templates must provide one flat
``templates/quickscale_<module>/base.html`` owning
``{% block <module>_content %}``; every page extends that base and emits no
document shell; module static files live under
``static/quickscale_<module>/{css,js,img}/``; template-tag libraries carry the
``quickscale_<module>`` stem.

Templates under ``email/`` and ``admin/`` follow the software that loads them
(rule 8 folder exceptions) and are outside the page contract.
"""

from __future__ import annotations

import ast
from ipaddress import ip_address
import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from quickscale_core.contracts.module_discovery import (
    authoritative_module_names,
    discover_shipped_module_paths,
)

ROOT = Path(__file__).resolve().parents[2]

THEME_ROOT = (
    "quickscale_core/src/quickscale_core/generator/templates/themes/showcase_react"
)
NON_PAGE_TEMPLATE_PREFIXES = ("email/", "admin/")
NON_PAGE_TEMPLATE_NAMES = ("base.html",)
SOFTWARE_OWNED_TEMPLATE_FOLDERS = ("account", "admin")

ACCEPTED_FRONTEND_ORIGINS = (
    ("https://vite.example.test", "https://vite.example.test"),
    ("https://vite.example.test/", "https://vite.example.test"),
    ("http://127.0.0.1:45173", "http://127.0.0.1:45173"),
)

REJECTED_FRONTEND_ORIGINS = (
    "https://vite.example.test?",
    "https://vite.example.test#",
    "http://127.1",
    "http://2130706433",
    "http://0x7f000001",
    "http://0x7f.0.0.1",
    "http://0177.0.0.1",
    "http://127.0.0.0x1",
    "http://localhost:0",
    "http://é.example",
    "http://exa mple.test",
)


def _module_packages() -> dict[str, Path]:
    """Map each discovered module to its source package directory (rule 37)."""
    module_paths = discover_shipped_module_paths()
    packages: dict[str, Path] = {}
    for module_name in authoritative_module_names():
        module_path = module_paths.get(module_name)
        if module_path is not None:
            packages[module_name] = (
                module_path / "src" / f"quickscale_modules_{module_name}"
            )
    return packages


PACKAGES = _module_packages()
MODULE_NAMES = tuple(PACKAGES)


def _module_template_root(module_name: str) -> Path:
    return PACKAGES[module_name] / "templates" / f"quickscale_{module_name}"


def _page_templates(module_name: str) -> list[Path]:
    root = _module_template_root(module_name)
    if not root.is_dir():
        return []
    pages: list[Path] = []
    for path in sorted(root.rglob("*.html")):
        relative = path.relative_to(root).as_posix()
        if relative in NON_PAGE_TEMPLATE_NAMES:
            continue
        if relative.startswith(NON_PAGE_TEMPLATE_PREFIXES):
            continue
        if path.name.startswith("_"):
            continue
        pages.append(path)
    return pages


def _stray_page_templates(module_name: str) -> list[Path]:
    """Return ``.html`` templates outside the module's canonical namespace.

    ``templates/account/`` (django-allauth) and ``templates/admin/`` (Django
    admin) follow the software that loads them (rule 8 folder exceptions);
    every other page template must live under
    ``templates/quickscale_<module>/``.
    """
    templates_root = PACKAGES[module_name] / "templates"
    if not templates_root.is_dir():
        return []
    namespace = f"quickscale_{module_name}"
    stray: list[Path] = []
    for path in sorted(templates_root.rglob("*.html")):
        top = path.relative_to(templates_root).parts[0]
        if top in SOFTWARE_OWNED_TEMPLATE_FOLDERS or top == namespace:
            continue
        stray.append(path)
    return stray


def _block_tag_pattern(block_name: str) -> re.Pattern[str]:
    """Match a Django ``{% block <name> %}`` tag across valid spacing."""
    return re.compile(r"{%\s*block\s+" + re.escape(block_name) + r"\s*%}")


def _module_stylesheets() -> list[Path]:
    stylesheets: list[Path] = []
    for module_name in MODULE_NAMES:
        static_root = PACKAGES[module_name] / "static"
        if static_root.is_dir():
            stylesheets.extend(
                path for path in sorted(static_root.rglob("*.css")) if path.is_file()
            )
    return stylesheets


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_pages_extend_one_flat_module_base(module_name: str) -> None:
    stray = _stray_page_templates(module_name)
    assert not stray, (
        f"page templates must live under templates/quickscale_{module_name}/: {stray}"
    )

    pages = _page_templates(module_name)
    if not pages:
        pytest.skip(f"{module_name} ships no page templates")

    base = _module_template_root(module_name) / "base.html"
    assert base.is_file(), f"{module_name} pages need {base}"

    base_content = base.read_text()
    assert '{% extends "base.html" %}' in base_content, base
    assert _block_tag_pattern("content").search(base_content), base
    assert _block_tag_pattern(f"{module_name}_content").search(base_content), base
    assert "<html" not in base_content.lower(), base

    for page in pages:
        content = page.read_text()
        assert f'{{% extends "quickscale_{module_name}/base.html" %}}' in content, page
        assert _block_tag_pattern(f"{module_name}_content").search(content), page
        assert not _block_tag_pattern("content").search(content), page
        assert "<html" not in content.lower(), page
        assert "<!doctype" not in content.lower(), page


def test_module_bases_load_stylesheets_through_the_parent_block() -> None:
    for module_name in MODULE_NAMES:
        base = _module_template_root(module_name) / "base.html"
        if not base.is_file():
            continue
        content = base.read_text()
        if "{% static '" not in content:
            continue
        assert "{% block extra_css %}" in content, base
        assert "{{ block.super }}" in content, base
        assert "<style" not in content.lower(), base


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_static_files_follow_the_quickscale_stem(module_name: str) -> None:
    static_root = PACKAGES[module_name] / "static"
    if not static_root.is_dir():
        pytest.skip(f"{module_name} ships no static files")

    files = sorted(
        path
        for path in static_root.rglob("*")
        if path.is_file() and not path.name.startswith(".")
    )
    assert files, static_root
    for path in files:
        relative = path.relative_to(static_root)
        assert relative.parts[0] == f"quickscale_{module_name}", path
        assert len(relative.parts) >= 2 and relative.parts[1] in {
            "css",
            "js",
            "img",
        }, path


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_template_static_references_resolve(module_name: str) -> None:
    template_root = _module_template_root(module_name)
    if not template_root.is_dir():
        pytest.skip(f"{module_name} ships no templates")

    references: set[str] = set()
    for path in sorted(template_root.rglob("*")):
        if not path.is_file() or path.suffix not in {".html", ".txt"}:
            continue
        references.update(re.findall(r"{%\s*static\s+'([^']+)'", path.read_text()))

    for reference in sorted(references):
        assert reference.startswith(f"quickscale_{module_name}/"), reference
        assert (PACKAGES[module_name] / "static" / reference).is_file(), reference


@pytest.mark.parametrize("module_name", MODULE_NAMES)
def test_module_template_tag_libraries_carry_the_stem(module_name: str) -> None:
    templatetags = PACKAGES[module_name] / "templatetags"
    if not templatetags.is_dir():
        pytest.skip(f"{module_name} ships no template-tag libraries")

    libraries = [
        path for path in sorted(templatetags.glob("*.py")) if path.name != "__init__.py"
    ]
    assert libraries, f"{templatetags} has no library module"
    for library in libraries:
        stem = library.stem
        assert stem == f"quickscale_{module_name}" or stem.startswith(
            f"quickscale_{module_name}_"
        ), library


@pytest.mark.parametrize(
    "stylesheet",
    _module_stylesheets(),
    ids=lambda path: path.name,
)
def test_module_stylesheets_use_shared_tokens(stylesheet: Path) -> None:
    content = stylesheet.read_text()

    assert "hsl(var(--" in content
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", content)
    assert not re.search(r"\brgba?\(", content)


def test_billing_primary_cta_foreground_wins_the_anchor_cascade() -> None:
    billing_styles = (
        PACKAGES["billing"] / "static" / "quickscale_billing" / "css" / "billing.css"
    ).read_text()
    token_source = (ROOT / THEME_ROOT / "src/index.css").read_text()

    assert ".billing-content .billing-pricing__button--primary" in billing_styles
    assert "color: hsl(var(--primary-foreground));" in billing_styles
    assert token_source.count("--primary-foreground:") >= 2


@pytest.mark.parametrize(
    ("stylesheet", "required_rules"),
    [
        (
            "quickscale_modules/blog/src/quickscale_modules_blog/static/"
            "quickscale_blog/css/blog.css",
            (".blog-markdown-content ul", "list-style: disc", "list-style: decimal"),
        ),
        (
            "quickscale_modules/listings/src/quickscale_modules_listings/static/"
            "quickscale_listings/css/listings.css",
            (
                ".listing-markdown-content ul",
                "list-style: disc",
                "list-style: decimal",
            ),
        ),
        (
            "quickscale_modules/crm/src/quickscale_modules_crm/static/"
            "quickscale_crm/css/crm.css",
            (".crm-content .api-list", "list-style: disc"),
        ),
    ],
)
def test_semantic_module_lists_restore_markers_after_tailwind_preflight(
    stylesheet: str,
    required_rules: tuple[str, ...],
) -> None:
    content = (ROOT / stylesheet).read_text()

    for required_rule in required_rules:
        assert required_rule in content


def test_affected_presentation_references_only_canonical_tokens() -> None:
    token_source = (ROOT / THEME_ROOT / "src/index.css").read_text()
    canonical_tokens = set(re.findall(r"(--[a-z0-9-]+)\s*:", token_source))

    for module_name in MODULE_NAMES:
        package = PACKAGES[module_name]
        for pattern in ("*.css", "*.html", "*.js"):
            for path in package.rglob(pattern):
                if "admin" in path.relative_to(package).parts:
                    continue
                referenced_tokens = set(
                    re.findall(r"var\((--[a-z0-9-]+)", path.read_text())
                )
                assert referenced_tokens <= canonical_tokens, (
                    f"{path} references undefined tokens: "
                    f"{sorted(referenced_tokens - canonical_tokens)}"
                )


def test_auth_script_uses_token_backed_strength_classes() -> None:
    auth_script = (
        PACKAGES["auth"] / "static" / "quickscale_auth" / "js" / "auth.js"
    ).read_text()

    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", auth_script)
    assert ".style.color" not in auth_script
    for strength in ("weak", "moderate", "strong"):
        assert f"password-strength--{strength}" in auth_script


def test_generated_shell_defines_the_module_block_contract() -> None:
    shell = (ROOT / THEME_ROOT / "templates/base.html.j2").read_text()

    for block in ("title", "extra_css", "content", "extra_js"):
        assert f"{{% block {block} %}}" in shell


def test_generated_shell_loads_the_react_token_source() -> None:
    theme = ROOT / THEME_ROOT
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
    assert "def _quickscale_validate_frontend_host_port" in local_settings
    assert (
        "QUICKSCALE_FRONTEND_HOST_PORT = _quickscale_validate_frontend_host_port("
        in local_settings
    )
    assert 'config("QUICKSCALE_FRONTEND_ORIGIN", default="")' in local_settings
    assert "def _quickscale_validate_frontend_origin" in local_settings
    assert "must be a canonical HTTP(S) origin" in local_settings
    assert 'f"http://localhost:{QUICKSCALE_FRONTEND_HOST_PORT}"' in local_settings
    assert "{% static 'frontend/assets/index.css' %}" in shell
    assert "{% static 'frontend/assets/index.css' %}" in react_host
    assert "base: '/static/frontend/'" in vite_config
    assert "port: 5173" in vite_config
    assert "strictPort: true" in vite_config
    assert "QUICKSCALE_FRONTEND_HOST_PORT" in vite_config
    assert "http://localhost:${frontendHostPort}" in vite_config
    assert "QUICKSCALE_FRONTEND_ORIGIN" in vite_config
    assert "allowedHosts: frontendAllowedHosts" in vite_config
    assert "name: 'quickscale-exact-host'" in vite_config
    assert "server.middlewares.use" in vite_config
    assert "prependListener(" in vite_config
    assert "return requestHost === frontendOrigin.host" in vite_config
    assert "'^/static(?:$|/(?!frontend(?:/|$)))':" in vite_config
    assert "'/static':" not in vite_config


def test_generated_debug_workflows_keep_vite_available(
    generated_project_path: Path,
) -> None:
    compose = (generated_project_path / "docker-compose.yml").read_text()
    readme = (generated_project_path / "README.md").read_text()

    assert "corepack pnpm run build && corepack pnpm run dev --host 0.0.0.0" in compose
    assert "--config.fetch-retries=5" in compose
    assert '"${QUICKSCALE_FRONTEND_HOST_PORT:-5173}:5173"' in compose
    assert (
        compose.count(
            "QUICKSCALE_FRONTEND_HOST_PORT=${QUICKSCALE_FRONTEND_HOST_PORT:-5173}"
        )
        == 2
    )
    assert (
        compose.count("QUICKSCALE_FRONTEND_ORIGIN=${QUICKSCALE_FRONTEND_ORIGIN:-}") == 2
    )
    assert (
        "process.env.QUICKSCALE_FRONTEND_ORIGIN||('http://localhost:'+port)" in compose
    )
    assert "headers:{Host:host}" in compose
    assert "path:'/static/frontend/src/index.css'" in compose
    assert "retries: 120" in compose
    assert "condition: service_healthy" in compose
    assert "pnpm --dir frontend build && pnpm --dir frontend dev" in readme
    assert "In a second terminal, from the project root" in readme


def test_generated_django_and_vite_origin_validators_share_a_corpus(
    generated_project_path: Path,
) -> None:
    local_settings = (
        generated_project_path / "testproject" / "settings" / "local.py"
    ).read_text()
    vite_test = (
        generated_project_path
        / "frontend"
        / "src"
        / "test"
        / "viteAssetRouting.test.ts"
    ).read_text()
    parsed_settings = ast.parse(local_settings)
    validator_nodes = [
        node
        for node in parsed_settings.body
        if isinstance(node, ast.FunctionDef)
        and node.name
        in {
            "_quickscale_canonical_frontend_hostname",
            "_quickscale_validate_frontend_host_port",
            "_quickscale_validate_frontend_origin",
        }
    ]
    namespace = {"ip_address": ip_address, "re": re, "urlsplit": urlsplit}
    exec(
        compile(
            ast.Module(body=validator_nodes, type_ignores=[]),
            "<generated-local-settings-origin-validators>",
            "exec",
        ),
        namespace,
    )
    host_port_validator = namespace["_quickscale_validate_frontend_host_port"]
    validator = namespace["_quickscale_validate_frontend_origin"]

    assert host_port_validator("1") == 1
    assert host_port_validator("5173") == 5173
    assert host_port_validator("65535") == 65535
    for configured_port in (
        "0",
        "-1",
        "+5173",
        "05173",
        "65536",
        "999999999999999999999999999999999999",
        "not-a-port",
    ):
        with pytest.raises(ValueError, match="must be between 1 and 65535"):
            host_port_validator(configured_port)
        assert repr(configured_port) in vite_test

    for configured_origin, canonical_origin in ACCEPTED_FRONTEND_ORIGINS:
        assert validator(configured_origin) == canonical_origin
        assert repr(configured_origin) in vite_test

    for configured_origin in REJECTED_FRONTEND_ORIGINS:
        with pytest.raises(ValueError, match="must be a canonical HTTP\\(S\\) origin"):
            validator(configured_origin)
        assert repr(configured_origin) in vite_test


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
