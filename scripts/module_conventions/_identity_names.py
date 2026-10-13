"""
Rule 2's module identity names: apps, URLs, templates, commands, db_table.

Implementation detail of :mod:`scripts.module_conventions.rules_identity`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.module_conventions.core import (
    ALLOWED_TEMPLATE_DIRS,
    Corpus,
    Module,
    _parse,
    _string_assignments,
)


def _apps_identity_violations(module: Module, stem: str, package: str) -> list[str]:
    """Return rule 2's violations for the module's ``apps.py`` name and label."""
    apps = module.files.get("apps.py")
    if apps is None:
        return [f"rule 2: {module.name}: missing apps.py"]
    violations: list[str] = []
    assignments = _string_assignments(_parse(apps))
    if assignments.get("name") != package:
        violations.append(
            f"rule 2: {module.name}: apps.py name is "
            f"{assignments.get('name')!r}, expected {package!r}"
        )
    if assignments.get("label") != stem:
        violations.append(
            f"rule 2: {module.name}: apps.py label is "
            f"{assignments.get('label')!r}, expected {stem!r}"
        )
    return violations


def _urls_app_name_violations(module: Module, stem: str) -> list[str]:
    """Return rule 2's violation for the module's ``urls.py`` ``app_name``."""
    urls = module.files.get("urls.py")
    if urls is None:
        return []
    app_name = _string_assignments(_parse(urls)).get("app_name")
    if app_name != stem:
        return [f"rule 2: {module.name}: urls.py app_name is {app_name!r}, expected {stem!r}"]
    return []


def _template_directory_violations(module: Module, stem: str) -> list[str]:
    """Return rule 2's violations for template directories outside the stem."""
    violations: list[str] = []
    for rel in module.files:
        parts = rel.split("/")
        if parts[0] != "templates":
            continue
        if len(parts) < 2:
            continue
        if parts[1] not in (stem, *ALLOWED_TEMPLATE_DIRS):
            violations.append(f"rule 2: {module.name}: template directory {parts[1]!r} in {rel}")
    return violations


def _command_name_violations(module: Module, stem: str) -> list[str]:
    """Return rule 2's violations for management commands missing the stem."""
    violations: list[str] = []
    for rel in module.files:
        if not rel.startswith("management/commands/"):
            continue
        command = Path(rel).stem
        if command == "__init__":
            continue
        if not command.startswith(f"{stem}_"):
            violations.append(
                f"rule 2: {module.name}: command {command!r} lacks the {stem}_ prefix"
            )
    return violations


def _db_table_violations(module: Module) -> list[str]:
    """Return rule 2's violations for a class body that sets ``db_table``."""
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py"):
            continue
        for node in ast.walk(_parse(text)):
            if not isinstance(node, ast.ClassDef):
                continue
            for stmt in node.body:
                target_names: list[str] = []
                if isinstance(stmt, ast.Assign):
                    target_names = [
                        target.id for target in stmt.targets if isinstance(target, ast.Name)
                    ]
                elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                    target_names = [stmt.target.id]
                if "db_table" in target_names:
                    violations.append(f"rule 2: {module.name}: {rel} sets db_table on {node.name}")
    return violations


def rule_2_identity_names(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        stem = f"quickscale_{module.name}"
        package = f"quickscale_modules_{module.name}"
        violations.extend(_apps_identity_violations(module, stem, package))
        violations.extend(_urls_app_name_violations(module, stem))
        violations.extend(_template_directory_violations(module, stem))
        violations.extend(_command_name_violations(module, stem))
        violations.extend(_db_table_violations(module))
    return violations
