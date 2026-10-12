"""
Rule 7's URL mounts, route names, and mount-literal mechanics.

Implementation detail of :mod:`scripts.module_conventions.rules_routes`; that
module keeps rule 37's module-name exception tables (``rule_37`` exempts only
``rules_routes.py``), orchestrates the rule's ordered finding groups, and
re-exports every name defined here, so existing import paths and test patch
targets keep working.
"""

from __future__ import annotations

import ast
import re

from scripts.module_conventions.core import (
    SNAKE_CASE,
    Corpus,
    Module,
    _call_func_name,
    _declared_url_mounts,
    _keyword,
    _literal,
    _parse,
    _string_assignments,
    _wiring_projection,
)

#: Adapter keywords and assignment targets whose values must come only from
#: the module manifest (Module Wiring Authority): the wiring fields an
#: adapter may project, never declare as Python literals.
WIRING_LITERAL_FIELDS = (
    "apps",
    "middleware",
    "url_includes",
    "pre_home_url_includes",
    "spa_routes",
)


def _declares_literal_wiring(value: ast.expr) -> bool:
    """
    Return True when a non-empty list/tuple literal hard-codes module wiring.

    The manifest is the only place that sets a module's apps, middleware, and
    URL mounts, so an adapter naming literal wiring entries violates it.  An
    *empty* literal declares nothing at all: it is how a switched-off module
    mounts none of its public URLs (rule 1), so it stays allowed and the check
    must not flag it.
    """
    return isinstance(value, (ast.List, ast.Tuple)) and bool(value.elts)


def _keyword_literal_wiring_violations(module: Module, node: ast.Call) -> list[str]:
    """Return rule 7 violations for one call's literal wiring keywords."""
    violations: list[str] = []
    for keyword in node.keywords:
        if keyword.arg in WIRING_LITERAL_FIELDS and _declares_literal_wiring(keyword.value):
            violations.append(f"rule 7: {module.name}: adapter.py declares a literal {keyword.arg}")
    if (
        isinstance(node.func, ast.Attribute)
        and node.func.attr in {"append", "insert"}
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id in WIRING_LITERAL_FIELDS
        and any(
            isinstance(argument, ast.Constant) and isinstance(argument.value, str)
            for argument in node.args
        )
    ):
        violations.append(
            f"rule 7: {module.name}: adapter.py appends a literal to {node.func.value.id}"
        )
    return violations


def _target_literal_wiring_violations(module: Module, node: ast.AST) -> list[str]:
    """Return rule 7 violations for literal wiring assigned in one adapter."""
    targets: list[ast.expr] = []
    if isinstance(node, ast.Assign) and _declares_literal_wiring(node.value):
        targets = list(node.targets)
    elif (
        isinstance(node, ast.AnnAssign)
        and node.value is not None
        and _declares_literal_wiring(node.value)
    ):
        targets = [node.target]
    return [
        f"rule 7: {module.name}: adapter.py declares a literal {target.id}"
        for target in targets
        if isinstance(target, ast.Name) and target.id in WIRING_LITERAL_FIELDS
    ]


def _adapter_literal_wiring_violations(module: Module, adapter: str) -> list[str]:
    """Return rule 7 violations for literal wiring declared in one adapter."""
    violations: list[str] = []
    for node in ast.walk(_parse(adapter)):
        if isinstance(node, ast.Call):
            violations.extend(_keyword_literal_wiring_violations(module, node))
            continue
        violations.extend(_target_literal_wiring_violations(module, node))
    return violations


def _urls_route_name_violations(module_name: str, tree: ast.Module) -> list[str]:
    """Return rule 7's route-name violations for one module's ``urls.py``."""
    violations: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = _call_func_name(node)
        if func in {"path", "re_path"}:
            name = _literal(_keyword(node, "name"))
            if isinstance(name, str):
                violations.extend(_route_name_violations(module_name, name, "path name"))
        elif func == "register" and node.args and isinstance(node.args[0], ast.Constant):
            basename = _literal(_keyword(node, "basename"))
            if isinstance(basename, str):
                violations.extend(_route_name_violations(module_name, basename, "router basename"))
            elif basename is None:
                violations.append(
                    f"rule 7: {module_name}: router.register without an explicit basename"
                )
    root_view_name = _string_assignments(tree).get("root_view_name")
    if root_view_name is not None:
        violations.extend(_route_name_violations(module_name, root_view_name, "api root"))
    return violations


def _module_url_violations(module: Module) -> list[str]:
    """Return rule 7's manifest, adapter, and route-name violations for one module."""
    violations: list[str] = []
    package = f"quickscale_modules_{module.name}"
    includes = _wiring_projection(module.manifest, "url_includes")
    own = [
        entry
        for entry in includes
        if isinstance(entry, list)
        and len(entry) == 2
        and isinstance(entry[1], str)
        and entry[1] == f"{package}.urls"
    ]
    for entry in includes:
        if not isinstance(entry, list) or len(entry) != 2:
            violations.append(f"rule 7: {module.name}: malformed url_includes entry {entry!r}")
            continue
        mount = entry[0]
        if not isinstance(mount, str) or not mount or mount.startswith("/"):
            violations.append(
                f"rule 7: {module.name}: url mount {mount!r} must be a non-empty relative path"
            )
    if "urls.py" in module.files and not own:
        violations.append(
            f"rule 7: {module.name}: manifest url_includes does not mount {package}.urls"
        )
    adapter = module.files.get("adapter.py", "")
    if adapter:
        violations.extend(_adapter_literal_wiring_violations(module, adapter))
    urls = module.files.get("urls.py")
    if urls is None:
        return violations
    violations.extend(_urls_route_name_violations(module.name, _parse(urls)))
    return violations


def _route_name_violations(module: str, name: str, where: str) -> list[str]:
    violations: list[str] = []
    skeleton = name.replace("{basename}", "x").replace("{url_name}", "x").replace("{lookup}", "x")
    if "{" in skeleton or "}" in skeleton:
        violations.append(f"rule 7: {module}: unresolved route template {name!r} in {where}")
        return violations
    if not SNAKE_CASE.match(skeleton):
        violations.append(f"rule 7: {module}: route name {name!r} in {where} is not snake_case")
    if re.search(rf"(^|_){module}(_|$)", skeleton):
        violations.append(f"rule 7: {module}: route name {name!r} in {where} repeats the module")
    return violations


def _url_prefix_collision_violations(corpus: Corpus) -> list[str]:
    """
    Rule 41 over the manifests: a URL prefix belongs to one module.

    The pre-home and post-home buckets render into one URLconf, so the owner
    registry spans both.  One module may chain several targets under one
    prefix (auth composes ``accounts/`` that way) and the identical
    ``(prefix, target)`` pair from two modules is the equal-contribution merge
    rule 30 sanctions; a second *module* claiming a prefix with a different
    target fails here and in ``apply`` itself (``collect_url_wiring``).
    """
    owners: dict[str, str] = {}
    seen_pairs: set[tuple[str, str]] = set()
    violations: list[str] = []
    for module in corpus.modules:
        for field in ("pre_home_url_includes", "url_includes"):
            for entry in _wiring_projection(module.manifest, field):
                if not (
                    isinstance(entry, (list, tuple))
                    and len(entry) == 2
                    and all(isinstance(part, str) for part in entry)
                ):
                    continue
                prefix, target = entry
                pair = (prefix, target)
                owner = owners.get(prefix)
                if owner is None:
                    owners[prefix] = module.name
                elif owner != module.name and pair not in seen_pairs:
                    violations.append(
                        f"rule 7: modules '{owner}' and '{module.name}' both mount URL "
                        f"prefix '{prefix}' with different targets"
                    )
                    continue
                seen_pairs.add(pair)
    return violations


#: Rule 41's theme-API-literal scan root and its test-file exemption: the
#: theme's own Vitest files build fetch targets by hand.
THEME_TS_ROOT = "generator/templates/themes/showcase_react/src/"
THEME_TS_TEST_MARKER = "/test/"


def _theme_api_literal_violations(corpus: Corpus) -> list[str]:
    """
    Rule 41 over the theme's TypeScript: module API bases come from the seam.

    The theme reads every module API base from ``moduleApiPaths``, so any
    quoted ``/<mount>/api`` in its TypeScript is the mount written by hand.
    The trailing lookahead only stops a longer segment (``/orgs/apiary``)
    from matching; a route-pattern or prose spelling of the mount counts just
    the same.
    """
    violations: list[str] = []
    for module in corpus.modules:
        for mount in _declared_url_mounts(module):
            if not mount:
                continue
            anchor = mount.rstrip("/")
            pattern = re.compile(rf"""["'`]/{re.escape(anchor)}/api(?![A-Za-z0-9_.-])""")
            for rel, text in corpus.core_files.items():
                if not (
                    rel.startswith(THEME_TS_ROOT)
                    and rel.endswith((".ts", ".tsx"))
                    and THEME_TS_TEST_MARKER not in rel
                ):
                    continue
                for match in pattern.finditer(text):
                    line = text.count("\n", 0, match.start()) + 1
                    violations.append(
                        f"rule 7: core {rel}:{line}: module '{module.name}' API path "
                        f"{match.group(0)[1:]!r} is written as a literal; the theme reads "
                        "moduleApiPaths from the seam"
                    )
    return violations
