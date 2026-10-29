"""
Rule 19's operator-token, guard, and AllowAny mechanics (rule 46's scan).

Implementation detail of :mod:`scripts.module_conventions.rules_routes`; that
module keeps rule 37's module-name exception tables (``OPERATOR_TOKENS`` and
``TRAFFIC_FILTER_TOKENS``) and passes them into the token scan here, and it
re-exports every public name defined here, so existing import paths keep
working.
"""

from __future__ import annotations

import ast
from pathlib import Path

from scripts.module_conventions._routes_view_index import (
    _base_name,
    _defines_view_code,
    _view_class_index,
    _view_framework,
)
from scripts.module_conventions.core import (
    Corpus,
    Module,
    _docstring_nodes,
    _parse,
)

FORBIDDEN_VIEW_TOKENS = ("is_staff", "is_superuser", "IsAdminUser", "redirect_to_login")

# Rule 19's sanctioned page-guard mixins and the named public-read
# declarations: a page declares its guard with a login or role mixin, and a
# public page declares that with a mixin whose name carries the public-read
# promise (``PublicSystemOrgReadMixin`` or a ``*PublicReadMixin``).
GUARD_MIXIN_NAMES: frozenset[str] = frozenset({"LoginRequiredMixin", "OrgRoleMixin"})
PUBLIC_READ_MIXIN_NAMES: frozenset[str] = frozenset({"PublicSystemOrgReadMixin"})
PUBLIC_READ_MIXIN_SUFFIX = "PublicReadMixin"

#: Rule 19's second public-read shape: orgs' marker for a public page that
#: reads no tenant-scoped row at all.  A ``*PublicReadMixin`` must resolve to
#: one of the two declared shapes, so an empty mixin cannot pass by its name.
PUBLIC_READ_PRESENTATION_MIXIN_NAME = "PublicReadPresentationMixin"

#: Rule 19's enforcers of a ``min_org_role`` attribute: the attribute is a
#: guard only beside a base that reads it.
ROLE_ENFORCING_BASE_NAMES: frozenset[str] = frozenset({"OrgApiBaseView", "OrgRoleMixin"})


def _view_token(node: ast.AST) -> str | None:
    """Return the forbidden authorization token a view node uses, if any."""
    if isinstance(node, ast.Name) and node.id in FORBIDDEN_VIEW_TOKENS:
        return node.id
    if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_VIEW_TOKENS:
        return node.attr
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        if node.value in FORBIDDEN_VIEW_TOKENS:
            return node.value
    return None


def _is_sanctioned_guard_name(name: str) -> bool:
    """Return whether a base-class name is a sanctioned guard declaration."""
    return (
        name in GUARD_MIXIN_NAMES
        or name in PUBLIC_READ_MIXIN_NAMES
        or name.endswith(PUBLIC_READ_MIXIN_SUFFIX)
    )


def _permission_expression_name(node: ast.expr) -> str | None:
    """Return the permission name an expression contributes, call form included."""
    if isinstance(node, ast.Call):
        node = node.func
    return _base_name(node)


def _get_permissions_binding(
    node: ast.ClassDef,
    aliases: dict[str, str],
) -> tuple[bool, set[str] | None]:
    """
    Return whether a class overrides ``get_permissions()`` and what it returns.

    The second element is the returned permission names with import aliases
    resolved, or ``None`` when the override exists but returns no literal
    list/tuple the harness can read; clause A then treats the override as no
    declaration (fail closed).
    """
    override = next(
        (
            statement
            for statement in node.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
            and statement.name == "get_permissions"
        ),
        None,
    )
    if override is None:
        return False, None
    names: set[str] = set()
    recognized = False
    for child in ast.walk(override):
        if not isinstance(child, ast.Return) or child.value is None:
            continue
        if isinstance(child.value, (ast.List, ast.Tuple)):
            recognized = True
            for element in child.value.elts:
                found = _permission_expression_name(element)
                if found is not None:
                    names.add(aliases.get(found, found))
    return True, names if recognized else None


def _declares_permission_classes(node: ast.ClassDef) -> bool:
    """Return whether a class body assigns ``permission_classes``."""
    for statement in node.body:
        if isinstance(statement, ast.Assign):
            names = {target.id for target in statement.targets if isinstance(target, ast.Name)}
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            names = {statement.target.id}
        else:
            continue
        if "permission_classes" in names:
            return True
    return False


def _declares_min_org_role(node: ast.ClassDef) -> bool:
    """Return whether a class body declares a ``min_org_role`` attribute."""
    for statement in node.body:
        if isinstance(statement, ast.Assign):
            names = {target.id for target in statement.targets if isinstance(target, ast.Name)}
        elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
            names = {statement.target.id}
        else:
            continue
        if "min_org_role" in names:
            return True
    return False


def _inherits_role_enforcement(
    name: str,
    classes: dict[str, tuple[ast.ClassDef, str]],
    seen: set[str],
) -> bool:
    """Return whether a class's bases reach an enforcer of ``min_org_role``."""
    entry = classes.get(name)
    if entry is None:
        return False
    for base in entry[0].bases:
        base_id = _base_name(base)
        if base_id is None:
            continue
        if base_id in ROLE_ENFORCING_BASE_NAMES:
            return True
        if base_id in classes and base_id not in seen:
            seen.add(base_id)
            if _inherits_role_enforcement(base_id, classes, seen):
                return True
    return False


def _class_declares_guard(
    name: str,
    classes: dict[str, tuple[ast.ClassDef, str]],
    bindings: dict[str, tuple[set[str], dict[str, str]]],
    aliases_by_rel: dict[str, dict[str, str]],
    memo: dict[tuple[str, bool], bool],
    in_progress: set[str],
    allow_drf_permissions: bool,
) -> bool:
    """
    Return whether a class declares a guard itself or inherits one.

    DRF permission declarations count while ``allow_drf_permissions`` holds —
    a plain Django page enforces none of them, so they are not counted on it
    or through its ancestry; sanctioned login/role/public-read ancestry
    (wrapper mixins included) always counts.  A Django page may inherit a
    guard through another view or through a mixin, but a mixin's DRF
    permission attributes remain inert there.  Import aliases resolve in the
    declaring class's file.
    """
    key = (name, allow_drf_permissions)
    if key in memo:
        return memo[key]
    if _is_sanctioned_guard_name(name):
        memo[key] = True
        return True
    entry = classes.get(name)
    if entry is None:
        memo[key] = False
        return False
    node, rel = entry
    file_aliases = aliases_by_rel.get(rel, {})
    if allow_drf_permissions:
        has_override, returned = _get_permissions_binding(node, file_aliases)
        if has_override:
            # A get_permissions() override decides the view's permissions at
            # runtime, so it also blocks an inherited declaration; an
            # override the harness cannot classify fails closed.
            memo[key] = returned is not None
            return memo[key]
        if _declares_permission_classes(node):
            memo[key] = True
            return True
    if _declares_min_org_role(node) and _inherits_role_enforcement(name, classes, {name}):
        memo[key] = True
        return True
    if name in in_progress:
        return False
    in_progress.add(name)
    declared = False
    for base in node.bases:
        base_id = _base_name(base)
        if base_id is None:
            continue
        if _is_sanctioned_guard_name(base_id):
            declared = True
            break
        if base_id not in classes:
            continue
        base_framework = _view_framework(base_id, classes, bindings, {base_id})
        if base_framework == "drf":
            child_allows_drf = True
        elif base_framework == "django":
            child_allows_drf = False
        else:
            child_allows_drf = allow_drf_permissions
        if _class_declares_guard(
            base_id,
            classes,
            bindings,
            aliases_by_rel,
            memo,
            in_progress,
            child_allows_drf,
        ):
            declared = True
            break
    in_progress.discard(name)
    memo[key] = declared
    return declared


def _permission_classes_declaration(node: ast.ClassDef) -> ast.expr | None:
    """Return the class body's ``permission_classes`` value, if it declares one."""
    for statement in node.body:
        if isinstance(statement, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "permission_classes"
            for target in statement.targets
        ):
            return statement.value
        if (
            isinstance(statement, ast.AnnAssign)
            and isinstance(statement.target, ast.Name)
            and statement.target.id == "permission_classes"
        ):
            return statement.value
    return None


def _permission_value_names(
    value: ast.expr,
    file_aliases: dict[str, str],
    classes: dict[str, tuple[ast.ClassDef, str]],
    aliases_by_rel: dict[str, dict[str, str]],
    memo: dict[str, set[str]],
    in_progress: set[str],
) -> set[str]:
    """Resolve a ``permission_classes`` value to the permission names it declares."""
    if isinstance(value, (ast.List, ast.Tuple)):
        return {
            file_aliases.get(found, found)
            for element in value.elts
            if (found := _permission_expression_name(element)) is not None
        }
    aliased = _base_name(value)
    if aliased is not None and aliased in classes:
        return _effective_permission_names(aliased, classes, aliases_by_rel, memo, in_progress)
    return set()


def _inherited_permission_names(
    node: ast.ClassDef,
    classes: dict[str, tuple[ast.ClassDef, str]],
    aliases_by_rel: dict[str, dict[str, str]],
    memo: dict[str, set[str]],
    in_progress: set[str],
) -> set[str]:
    """Resolve the permissions a class inherits from its bases."""
    result: set[str] = set()
    for base in node.bases:
        base_id = _base_name(base)
        if base_id is not None:
            result |= _effective_permission_names(
                base_id, classes, aliases_by_rel, memo, in_progress
            )
    return result


def _effective_permission_names(
    name: str,
    classes: dict[str, tuple[ast.ClassDef, str]],
    aliases_by_rel: dict[str, dict[str, str]],
    memo: dict[str, set[str]],
    in_progress: set[str],
) -> set[str]:
    """Resolve a class's effective permissions, its file's aliases included."""
    if name in memo:
        return memo[name]
    entry = classes.get(name)
    if entry is None:
        memo[name] = set()
        return memo[name]
    if name in in_progress:
        return set()
    in_progress.add(name)
    node, rel = entry
    file_aliases = aliases_by_rel.get(rel, {})
    has_override, returned = _get_permissions_binding(node, file_aliases)
    if has_override:
        result = returned if returned is not None else set()
    else:
        declaration = _permission_classes_declaration(node)
        if declaration is not None:
            result = _permission_value_names(
                declaration, file_aliases, classes, aliases_by_rel, memo, in_progress
            )
        else:
            result = _inherited_permission_names(node, classes, aliases_by_rel, memo, in_progress)
    in_progress.discard(name)
    memo[name] = result
    return result


def _reads_user_is_authenticated(node: ast.AST) -> bool:
    """Return whether a body reads ``X.user.is_authenticated`` directly."""
    for child in ast.walk(node):
        owner = child.value if isinstance(child, ast.Attribute) else None
        if (
            isinstance(child, ast.Attribute)
            and child.attr == "is_authenticated"
            and isinstance(owner, ast.Attribute)
            and owner.attr == "user"
        ):
            return True
    return False


def _sibling_rel(node: ast.ImportFrom, module_name: str) -> str | None:
    """Resolve a same-module import to the sibling file it reads from."""
    package = f"quickscale_modules_{module_name}"
    if node.level == 1:
        return f"{node.module.replace('.', '/')}.py" if node.module else "__init__.py"
    if node.level != 0 or not node.module:
        return None
    parts = node.module.split(".")
    if parts[:1] == [package] and len(parts) > 1:
        return f"{'/'.join(parts[1:])}.py"
    if parts[:2] == ["quickscale_modules", module_name] and len(parts) > 2:
        return f"{'/'.join(parts[2:])}.py"
    return None


def _module_helper_index(
    module: Module,
) -> tuple[dict[str, set[str]], dict[str, dict[str, tuple[str, str]]]]:
    """
    Index a module's authentication-reading helpers and its sibling imports.

    Returns, per file, the names of module-level functions whose bodies read
    ``user.is_authenticated``, and the file's imports of same-module siblings
    as local name -> (target file, original name), so a view's helper call
    resolves to the helper's defining file across a rule 28 split.
    """
    readers_by_rel: dict[str, set[str]] = {}
    imports_by_rel: dict[str, dict[str, tuple[str, str]]] = {}
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        readers_by_rel[rel] = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and _reads_user_is_authenticated(node)
        }
        imports: dict[str, tuple[str, str]] = {}
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            target = _sibling_rel(node, module.name)
            if target is None:
                continue
            for alias in node.names:
                imports[alias.asname or alias.name] = (target, alias.name)
        imports_by_rel[rel] = imports
    return readers_by_rel, imports_by_rel


def _effective_methods(
    name: str,
    classes: dict[str, tuple[ast.ClassDef, str]],
) -> dict[str, tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]]:
    """Return a class's methods with their defining file, nearest definition first."""
    methods: dict[str, tuple[ast.FunctionDef | ast.AsyncFunctionDef, str]] = {}
    seen: set[str] = set()

    def walk(class_name: str) -> None:
        if class_name in seen:
            return
        seen.add(class_name)
        entry = classes.get(class_name)
        if entry is None:
            return
        node, rel = entry
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.setdefault(statement.name, (statement, rel))
        for base in node.bases:
            base_id = _base_name(base)
            if base_id is not None:
                walk(base_id)

    walk(name)
    return methods


def _allow_any_hand_check_violations(
    module_name: str,
    rel: str,
    node: ast.ClassDef,
    classes: dict[str, tuple[ast.ClassDef, str]],
    readers_by_rel: dict[str, set[str]],
    imports_by_rel: dict[str, dict[str, tuple[str, str]]],
) -> list[str]:
    """
    Return rule 19's violations for an ``AllowAny`` view that hand-checks auth.

    A public view states its public guard and must not read
    ``request.user.is_authenticated`` by hand, directly or through a helper
    its effective methods call; authentication is the guard's decision, not
    the view body's.  The scan follows the view's effective methods —
    inherited handlers and helpers resolved to their nearest definition —
    and resolves each method's helper calls through that method's defining
    file, matching Python function globals, private-sibling splits included.
    """
    violations: list[str] = []
    methods = _effective_methods(node.name, classes)
    if any(_reads_user_is_authenticated(method) for method, _ in methods.values()):
        violations.append(
            f"rule 19: {module_name}: {rel}: view class {node.name} declares AllowAny "
            "and reads request.user.is_authenticated by hand"
        )
    helper_names: set[str] = set()
    for method, method_rel in methods.values():
        imported_readers: set[str] = set()
        for local_name, (target_rel, original) in imports_by_rel.get(method_rel, {}).items():
            if original in readers_by_rel.get(target_rel, set()):
                imported_readers.add(local_name)
        local_readers = readers_by_rel.get(method_rel, set()) | imported_readers
        for child in ast.walk(method):
            if not isinstance(child, ast.Call):
                continue
            func = child.func
            if isinstance(func, ast.Name) and func.id in local_readers:
                helper_names.add(func.id)
            elif (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "self"
                and func.attr in methods
                and _reads_user_is_authenticated(methods[func.attr][0])
            ):
                helper_names.add(f"self.{func.attr}")
    for helper in sorted(helper_names):
        violations.append(
            f"rule 19: {module_name}: {rel}: view class {node.name} declares AllowAny "
            f"and calls {helper}(), which checks request.user by hand"
        )
    return violations


def _token_violations(
    corpus: Corpus,
    operator_tokens: dict[tuple[str, str], frozenset[str]],
    traffic_filter_tokens: dict[tuple[str, str], frozenset[str]],
) -> list[str]:
    """
    Return rule 19's forbidden-token violations for every module.

    The first of the rule's two ordered passes: ``is_staff``, ``is_superuser``,
    ``IsAdminUser``, and hand-written ``redirect_to_login`` — imported or
    aliased, read as an attribute, or passed as a string — appear only in the
    listed operator paths.  The tables live in
    :mod:`scripts.module_conventions.rules_routes` (rule 37's exemption) and
    are passed in here.
    """
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            if not _defines_view_code(tree):
                continue
            key = (module.name, Path(rel).name)
            allowed = operator_tokens.get(key, frozenset()) | traffic_filter_tokens.get(
                key, frozenset()
            )
            docstrings = _docstring_nodes(tree)
            for node in ast.walk(tree):
                if not isinstance(node, ast.expr):
                    continue
                token = _view_token(node)
                if token is None or token in allowed:
                    continue
                if isinstance(node, ast.Constant) and id(node) in docstrings:
                    continue
                violations.append(
                    f"rule 19: {module.name}: {rel}:{node.lineno} uses {token} outside "
                    "the listed operator paths"
                )
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    imported = [alias.name for alias in node.names]
                elif isinstance(node, ast.Import):
                    imported = [alias.name.split(".")[-1] for alias in node.names]
                else:
                    continue
                for name in imported:
                    if name in FORBIDDEN_VIEW_TOKENS and name not in allowed:
                        violations.append(
                            f"rule 19: {module.name}: {rel}:{node.lineno} imports {name} "
                            "outside the listed operator paths"
                        )
    return violations


def _inherits_public_read_shape(
    node: ast.ClassDef,
    classes: dict[str, tuple[ast.ClassDef, str]],
    seen: set[str],
) -> bool:
    """Return whether a class resolves to a sanctioned public-read shape."""
    for base in node.bases:
        base_id = _base_name(base)
        if base_id is None:
            continue
        if base_id in PUBLIC_READ_MIXIN_NAMES:
            return True
        if base_id == PUBLIC_READ_PRESENTATION_MIXIN_NAME:
            return True
        if base_id in classes and base_id not in seen:
            seen.add(base_id)
            if _inherits_public_read_shape(classes[base_id][0], classes, seen):
                return True
    return False


def _public_read_mixin_violations(
    module: Module,
    classes: dict[str, tuple[ast.ClassDef, str]],
) -> list[str]:
    """
    Return rule 19's undeclared ``*PublicReadMixin`` findings.

    A module-owned ``*PublicReadMixin`` declares one of two shapes: it
    inherits ``PublicSystemOrgReadMixin``, so the page runs under the public
    organization's context, or it inherits orgs'
    ``PublicReadPresentationMixin``, so the page reads no tenant-scoped row.
    A mixin that declares neither fails closed rather than passing by its
    name alone (enforcement gap 23).
    """
    violations: list[str] = []
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            if not node.name.endswith(PUBLIC_READ_MIXIN_SUFFIX):
                continue
            if _inherits_public_read_shape(node, classes, {node.name}):
                continue
            violations.append(
                f"rule 19: {module.name}: {rel}: public-read mixin {node.name} "
                "neither inherits PublicSystemOrgReadMixin nor declares "
                "PublicReadPresentationMixin"
            )
    return violations


def _guard_violations(module: Module) -> list[str]:
    """
    Return rule 19's guard violations for one module.

    The second of the rule's two ordered passes: every view class declares a
    guard, and an ``AllowAny`` view must not read ``request.user`` by hand.
    """
    violations: list[str] = []
    classes, view_names, bindings, aliases_by_rel = _view_class_index(module)
    readers_by_rel, imports_by_rel = _module_helper_index(module)
    guard_memo: dict[tuple[str, bool], bool] = {}
    permission_memo: dict[str, set[str]] = {}
    for rel, text in module.files.items():
        if not rel.endswith(".py") or rel.startswith("migrations/"):
            continue
        tree = _parse(text)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef) or node.name not in view_names:
                continue
            framework = _view_framework(node.name, classes, bindings, {node.name})
            if not _class_declares_guard(
                node.name,
                classes,
                bindings,
                aliases_by_rel,
                guard_memo,
                set(),
                framework == "drf",
            ):
                violations.append(
                    f"rule 19: {module.name}: {rel}: view class {node.name} "
                    "declares no authorization guard"
                )
            permission_names = _effective_permission_names(
                node.name, classes, aliases_by_rel, permission_memo, set()
            )
            if "AllowAny" in permission_names:
                violations.extend(
                    _allow_any_hand_check_violations(
                        module.name,
                        rel,
                        node,
                        classes,
                        readers_by_rel,
                        imports_by_rel,
                    )
                )
    violations.extend(_public_read_mixin_violations(module, classes))
    return violations
