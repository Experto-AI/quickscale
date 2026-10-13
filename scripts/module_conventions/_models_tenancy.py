"""
Rule 13's tenancy-scan mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_models`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast

from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES,
    _call_func_name,
    _class_names,
    _meta_class,
    _model_classes,
)


def _tenant_reference_violations(module_name: str, rel: str, tree: ast.Module) -> list[str]:
    """Rule 13: only orgs calls tenancy helpers or retypes the manager."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            called = _call_func_name(node)
            if called == "tenant_org_fk":
                violations.append(f"rule 13: {module_name}: {rel} calls tenant_org_fk")
            if called == "TenantManager":
                violations.append(f"rule 13: {module_name}: {rel} constructs TenantManager")
        targets: list[ast.expr] = []
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
        for target in targets:
            if isinstance(target, ast.Name) and target.id == "base_manager_name":
                violations.append(f"rule 13: {module_name}: {rel} retypes base_manager_name")
    return violations


def _tenant_meta_violations(module_name: str, tree: ast.Module) -> list[str]:
    """Rule 13: an abstract-base model's Meta must inherit the base Meta."""
    violations: list[str] = []
    for node in _model_classes(tree):
        meta = _meta_class(node)
        if meta is not None and not meta.bases:
            if any(base in MODULE_ABSTRACT_BASES for base in _class_names(node)):
                violations.append(
                    f"rule 13: {module_name}: {node.name}.Meta does not inherit the base Meta"
                )
    return violations
