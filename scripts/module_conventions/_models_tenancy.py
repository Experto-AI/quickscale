"""
Rule 13's tenancy-scan mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_models`; that
module re-exports every public name defined here, so existing import paths
keep working.
"""

from __future__ import annotations

import ast
from collections.abc import Mapping

from scripts.module_conventions._misc_checks import (
    _base_origin,
    _base_origins,
    _import_bindings,
)
from scripts.module_conventions.core import (
    MODULE_ABSTRACT_BASES,
    Module,
    _call_func_name,
    _class_names,
    _meta_class,
    _model_classes,
    _parse,
)

#: Rule 13: where the tenant admin base is defined, and its name.  The marker
#: is matched by resolved import origin, so a same-named local class never
#: satisfies the clause.
ORG_ADMIN_MODULE = "quickscale_modules_orgs.admin"
TENANT_ADMIN_BASE = "TenantModelAdmin"

#: Rule 13: where Django's plain admin base and the admin site registry are
#: defined; a non-tenant model's admin subclasses the former, and a
#: registration goes through ``@admin.register`` instead of the latter's call.
DJANGO_ADMIN_MODULE = "django.contrib.admin"
ADMIN_BASE = "ModelAdmin"
DJANGO_ADMIN_SITE_MODULE = "django.contrib.admin.site"
ADMIN_REGISTER = "register"


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


#: Rule 13's base-origin table type: one class name maps to a base-origin list
#: per declaration of that name.
ClassOrigins = dict[str, list[list[tuple[str | None, str]]]]


def _package_class_origins(files: Mapping[str, str]) -> ClassOrigins:
    """Map each package class name to the origin lists of its declarations."""
    origins: ClassOrigins = {}
    for rel, text in sorted(files.items()):
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        bindings = _import_bindings(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef):
                origins.setdefault(node.name, []).append(_base_origins(node, bindings))
    return origins


def _is_package_internal(module_path: str | None, package: str) -> bool:
    """Return whether a resolved base origin stays inside the module's package."""
    if module_path is None or module_path.startswith("."):
        return True
    return module_path == package or module_path.startswith(f"{package}.")


def _reachable_base_origins(
    name: str,
    origins_by_name: ClassOrigins,
    package: str,
) -> set[tuple[str | None, str]]:
    """Return every base origin a package class reaches, transitively."""
    found: set[tuple[str | None, str]] = set()
    pending = [name]
    seen = {name}
    while pending:
        current = pending.pop()
        for origin_list in origins_by_name.get(current, []):
            for module_path, origin_name in origin_list:
                found.add((module_path, origin_name))
                if (
                    _is_package_internal(module_path, package)
                    and origin_name in origins_by_name
                    and origin_name not in seen
                ):
                    seen.add(origin_name)
                    pending.append(origin_name)
    return found


def _registered_model_names(decorator: ast.Call) -> list[str] | None:
    """Return the models a ``@admin.register`` decorator names, if it names them."""
    names: list[str] = []
    for argument in decorator.args:
        if not isinstance(argument, ast.Name):
            return None
        names.append(argument.id)
    return names or None


def _admin_site_registration_violations(
    module_name: str,
    rel: str,
    tree: ast.Module,
    bindings: Mapping[str, tuple[str, str | None, bool]],
) -> list[str]:
    """Rule 13: a registration goes through ``@admin.register``, not a call."""
    decorators = {
        id(decorator)
        for class_node in ast.walk(tree)
        if isinstance(class_node, ast.ClassDef)
        for decorator in class_node.decorator_list
    }
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node) in decorators:
            continue
        module_path, name = _base_origin(node.func, bindings)
        if module_path != DJANGO_ADMIN_SITE_MODULE or name != ADMIN_REGISTER:
            continue
        registered = node.args[0].id if node.args and isinstance(node.args[0], ast.Name) else None
        subject = f"registers {registered} through" if registered else "registers a model through"
        violations.append(
            f"rule 13: {module_name}: {rel}:{node.lineno} {subject} "
            "admin.site.register; use @admin.register"
        )
    return violations


def _decorator_registration_violations(
    module_name: str,
    rel: str,
    admin_node: ast.ClassDef,
    decorator: ast.Call,
    origins_by_name: ClassOrigins,
    package: str,
) -> list[str]:
    """Rule 13: one ``@admin.register`` decorator against its admin base."""
    location = f"rule 13: {module_name}: {rel}:{admin_node.lineno}"
    model_names = _registered_model_names(decorator)
    if model_names is None:
        return [f"{location} registers a model through a spelling the detector cannot resolve"]
    admin_origins = _reachable_base_origins(admin_node.name, origins_by_name, package)
    tenant_base = (ORG_ADMIN_MODULE, TENANT_ADMIN_BASE) in admin_origins
    model_base = (DJANGO_ADMIN_MODULE, ADMIN_BASE) in admin_origins
    violations: list[str] = []
    for model_name in model_names:
        if model_name not in origins_by_name:
            violations.append(
                f"{location} registers {model_name}, which the module's package does not define"
            )
            continue
        model_origins = _reachable_base_origins(model_name, origins_by_name, package)
        tenant = any(origin_name == "TenantModel" for _path, origin_name in model_origins)
        if tenant and not tenant_base:
            violations.append(
                f"{location} registers tenant model {model_name} with {admin_node.name}; "
                "use TenantModelAdmin"
            )
        elif not tenant and tenant_base:
            violations.append(
                f"{location} registers non-tenant model {model_name} with {admin_node.name}; "
                "use admin.ModelAdmin"
            )
        elif not tenant and not model_base:
            violations.append(
                f"{location} registers {model_name} with {admin_node.name}, which does not "
                "subclass admin.ModelAdmin"
            )
    return violations


def _admin_registration_violations(module: Module) -> list[str]:
    """
    Rule 13: tenant models register on ``TenantModelAdmin``, others on ``admin.ModelAdmin``.

    Both register with ``@admin.register``.  The registered model's tenant-ness
    comes from its transitive bases inside the module's own package; both admin
    markers are matched by resolved import origin, so an external mixin
    contributes no marker and a same-named local class never satisfies one.  A
    registered model the package does not define fails closed: the detector
    cannot decide its tenant-ness.
    """
    origins_by_name = _package_class_origins(module.files)
    package = f"quickscale_modules_{module.name}"
    violations: list[str] = []
    for rel, text in sorted(module.files.items()):
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        bindings = _import_bindings(tree)
        violations.extend(_admin_site_registration_violations(module.name, rel, tree, bindings))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                module_path, name = _base_origin(decorator.func, bindings)
                if module_path != DJANGO_ADMIN_MODULE or name != ADMIN_REGISTER:
                    continue
                violations.extend(
                    _decorator_registration_violations(
                        module.name, rel, node, decorator, origins_by_name, package
                    )
                )
    return violations
