"""
Rule 8's template, static-file, and template-tag mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_routes`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from scripts.module_conventions.core import (
    ALLOWED_TEMPLATE_DIRS,
    Corpus,
    Module,
    _literal,
    _parse,
)


def _is_admin_model_override(value: str) -> bool:
    """Return whether a template path is Django's ``admin/<label>/<model>/``."""
    parts = value.split("/")
    return len(parts) >= 4 and parts[0] == "admin" and all(parts[1:4]) and value.endswith(".html")


def _module_page_files(module: Module, stem: str) -> list[str]:
    """Return the module's module-owned template pages."""
    pages: list[str] = []
    for rel in module.files:
        if not rel.startswith("templates/") or not rel.endswith(".html"):
            continue
        if Path(rel).name.startswith("_"):
            continue
        parts = rel.split("/")[1:-1]
        if any(part in ALLOWED_TEMPLATE_DIRS for part in parts):
            continue
        if "email" in parts:
            continue
        if parts and parts[0] != stem:
            continue
        pages.append(rel)
    return pages


def _page_file_violations(module: Module, stem: str, base_rel: str, pages: list[str]) -> list[str]:
    """Return rule 8's per-page shape violations."""
    violations: list[str] = []
    for rel in pages:
        text = module.files[rel]
        parts = rel.split("/")[1:-1]
        if len(parts) > 1:
            violations.append(f"rule 8: {module.name}: {rel} is not flat under templates/{stem}/")
        if re.search(r"<html\b", text, re.IGNORECASE):
            violations.append(f"rule 8: {module.name}: {rel} emits <html>")
        if rel == base_rel:
            continue
        if not re.search(rf'\{{%\s*extends\s+["\']{re.escape(stem)}/base\.html["\']', text):
            violations.append(f"rule 8: {module.name}: {rel} does not extend {stem}/base.html")
        if not re.search(rf"\{{%\s*block\s+{re.escape(module.name)}_content\s*%\}}", text):
            violations.append(f"rule 8: {module.name}: {rel} fills no {module.name}_content block")
    return violations


def _page_violations(module: Module, stem: str, base_rel: str, pages: list[str]) -> list[str]:
    """Return rule 8's base-template and page-shape violations."""
    if not pages:
        return []
    violations: list[str] = []
    if base_rel not in module.files:
        violations.append(f"rule 8: {module.name}: missing module base {base_rel}")
    else:
        if not re.search(r'\{%\s*extends\s+["\']base\.html["\']', module.files[base_rel]):
            violations.append(f"rule 8: {module.name}: {base_rel} does not extend base.html")
        content_block = re.search(
            rf"\{{%\s*block\s+{re.escape(module.name)}_content\s*%\}}",
            module.files[base_rel],
        )
        if content_block is None:
            violations.append(
                f"rule 8: {module.name}: {base_rel} owns no {module.name}_content block"
            )
    violations.extend(_page_file_violations(module, stem, base_rel, pages))
    return violations


def _static_path_violations(module: Module, stem: str) -> list[str]:
    """Return rule 8's static-path violations."""
    violations: list[str] = []
    for rel in module.files:
        if not rel.startswith("static/"):
            continue
        parts = rel.split("/")
        if parts[1] != stem:
            violations.append(f"rule 8: {module.name}: static path {rel} lacks the {stem} root")
            continue
        if len(parts) >= 4 and parts[2] not in {"css", "js", "img"}:
            violations.append(f"rule 8: {module.name}: static path {rel} is outside css/js/img")
    return violations


def _template_tag_library_violations(module: Module, stem: str) -> list[str]:
    """Return rule 8's template-tag-library stem violations."""
    violations: list[str] = []
    for rel in module.files:
        if not rel.startswith("templatetags/") or not rel.endswith(".py"):
            continue
        library = Path(rel).stem
        if library in {"__init__"} or library.startswith("_"):
            continue
        if library != stem and not library.startswith(f"{stem}_"):
            violations.append(
                f"rule 8: {module.name}: template tag library {library!r} lacks the {stem} stem"
            )
    return violations


def _admin_override_violations(module: Module) -> list[str]:
    """Return rule 8's admin-template-override violations."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        for node in ast.walk(_parse(text)):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if not isinstance(target, ast.Name) or target.id not in {
                    "change_list_template",
                    "change_form_template",
                }:
                    continue
                value = _literal(node.value)
                if isinstance(value, str) and not _is_admin_model_override(value):
                    violations.append(
                        f"rule 8: {module.name}: {rel} admin override {value!r} is not "
                        "under admin/<label>/<model>/"
                    )
    return violations


def rule_8_templates(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        base_rel = f"templates/{stem}/base.html"
        pages = _module_page_files(module, stem)
        violations.extend(_page_violations(module, stem, base_rel, pages))
        violations.extend(_static_path_violations(module, stem))
        violations.extend(_template_tag_library_violations(module, stem))
        violations.extend(_admin_override_violations(module))
    return violations
