"""Static analysis of donor migrations and their module-level dependencies.

Reads migration modules with Python's syntax tree and symbol tables to decide
which operations the autodetector can regenerate, which module-level bindings
a carried operation references, and whether an operation's state is mutated at
import in a way the carry cannot reproduce.
"""

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
import ast
import builtins
import symtable


_AUTODETECTOR_OPERATION_NAMES: frozenset[str] = frozenset(
    {
        "AddConstraint",
        "AddField",
        "AddIndex",
        "AlterField",
        "AlterIndexTogether",
        "AlterModelManagers",
        "AlterModelOptions",
        "AlterModelTable",
        "AlterModelTableComment",
        "AlterOrderWithRespectTo",
        "AlterUniqueTogether",
        "CreateModel",
        "DeleteModel",
        "RemoveConstraint",
        "RemoveField",
        "RemoveIndex",
        "RenameField",
        "RenameIndex",
        "RenameModel",
    }
)


def _migration_operation_name(node: ast.AST) -> str | None:
    """Return the operation name of a migration ``operations`` list element."""
    if not isinstance(node, ast.Call):
        return None
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def _migration_owned_operations(app_dir: Path) -> list[str]:
    """Return donor migration operations the autodetector cannot reproduce."""
    migrations_dir = app_dir / "migrations"
    if not migrations_dir.is_dir():
        return []
    flagged: list[str] = []
    for migration_path in sorted(migrations_dir.glob("*.py")):
        if migration_path.name == "__init__.py":
            continue
        try:
            tree = ast.parse(migration_path.read_text(), filename=str(migration_path))
        except SyntaxError as exc:
            flagged.append(f"{migration_path.name}: unparseable migration ({exc})")
            continue
        for node in ast.walk(tree):
            targets: list[ast.expr]
            if isinstance(node, ast.AnnAssign):
                targets = [node.target]
            elif isinstance(node, ast.Assign):
                targets = node.targets
            else:
                continue
            if not any(
                isinstance(target, ast.Name) and target.id == "operations"
                for target in targets
            ):
                continue
            value = node.value
            if value is None:
                flagged.append(
                    f"{migration_path.name}:{node.lineno} unresolved operations declaration"
                )
                continue
            if not isinstance(value, (ast.List, ast.Tuple)):
                flagged.append(
                    f"{migration_path.name}:{node.lineno} unresolved operations declaration"
                )
                continue
            for element in value.elts:
                operation_name = _migration_operation_name(element)
                if (
                    operation_name is not None
                    and operation_name not in _AUTODETECTOR_OPERATION_NAMES
                ):
                    flagged.append(
                        f"{migration_path.name}:{getattr(element, 'lineno', '?')} "
                        f"{operation_name}"
                    )
                elif operation_name is None:
                    flagged.append(
                        f"{migration_path.name}:{getattr(element, 'lineno', '?')} "
                        "unresolved operation"
                    )
    return flagged


@dataclass(frozen=True)
class CarriedMigration:
    """One recipient migration appending donor operations that cannot regenerate.

    ``name`` is the recipient-relative migration file name; ``content`` is a
    complete, compile-checked migration module that carries only the donor's
    non-autodetector operations plus the module-level code they reference.
    """

    donor_name: str
    name: str
    content: str
    operation_names: tuple[str, ...]


_BUILTIN_NAMES: frozenset[str] = frozenset(dir(builtins))

_SUPPORTED_MIGRATION_CLASS_ATTRIBUTES: frozenset[str] = frozenset(
    {"atomic", "dependencies", "initial", "operations"}
)

_OPERATIONS_MUTATING_METHODS: frozenset[str] = frozenset(
    {"append", "extend", "insert", "remove", "pop", "clear", "sort", "reverse"}
)

_NAMESPACE_MUTATING_METHODS: frozenset[str] = frozenset(
    {
        "add",
        "append",
        "clear",
        "discard",
        "extend",
        "insert",
        "pop",
        "remove",
        "reverse",
        "setdefault",
        "sort",
        "update",
    }
)


def _module_executed_statements(
    statements: list[ast.stmt], *, nested: bool = False
) -> Iterator[tuple[ast.stmt, bool]]:
    """Yield statements that execute at module import, with a nested flag.

    Function and class bodies are deliberately not entered: their locals are
    not module state, so only the statements run while the migration module is
    imported can mutate a required binding.  ``nested`` is True for statements
    inside control flow, where a plain-name binding is a rebinding the carry
    does not reproduce.
    """
    for node in statements:
        yield node, nested
        child_statements: list[ast.stmt] = []
        if isinstance(node, ast.If):
            child_statements = [*node.body, *node.orelse]
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            child_statements = [*node.body, *node.orelse]
        elif isinstance(node, ast.Try):
            child_statements = node.body
            for handler in node.handlers:
                child_statements = [*child_statements, *handler.body]
            child_statements = [*child_statements, *node.orelse, *node.finalbody]
        elif isinstance(node, ast.TryStar):
            child_statements = node.body
            for handler in node.handlers:
                child_statements = [*child_statements, *handler.body]
            child_statements = [*child_statements, *node.orelse, *node.finalbody]
        elif isinstance(node, (ast.With, ast.AsyncWith)):
            child_statements = node.body
        elif isinstance(node, ast.Match):
            child_statements = [
                statement for case in node.cases for statement in case.body
            ]
        if child_statements:
            yield from _module_executed_statements(child_statements, nested=True)


def _module_executed_expression_nodes(node: ast.stmt) -> Iterator[ast.AST]:
    """Yield nodes a module-executed statement evaluates, skipping scopes.

    Decorators, defaults, annotations, and base classes are evaluated at
    import like any other expression, while a nested function, class, or
    lambda body is not.
    """
    pending: list[ast.AST] = []
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        pending.extend(node.decorator_list)
        arguments = node.args
        pending.extend(arg for arg in arguments.defaults if arg is not None)
        pending.extend(arg for arg in arguments.kw_defaults if arg is not None)
        for argument in [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]:
            if argument.annotation is not None:
                pending.append(argument.annotation)
        for optional_argument in (arguments.vararg, arguments.kwarg):
            if (
                optional_argument is not None
                and optional_argument.annotation is not None
            ):
                pending.append(optional_argument.annotation)
        if node.returns is not None:
            pending.append(node.returns)
    elif isinstance(node, ast.ClassDef):
        pending.extend(node.bases)
        pending.extend(node.keywords)
        pending.extend(node.decorator_list)
    else:
        pending.extend(
            child
            for child in ast.iter_child_nodes(node)
            if not isinstance(
                child,
                (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda),
            )
        )
    while pending:
        current = pending.pop()
        yield current
        if isinstance(
            current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Lambda)
        ):
            continue
        pending.extend(ast.iter_child_nodes(current))


def _target_names(target: ast.expr) -> Iterator[str]:
    """Yield every module name a binding target binds, unpacking nested targets."""
    if isinstance(target, ast.Name):
        yield target.id
    elif isinstance(target, (ast.Tuple, ast.List)):
        for element in target.elts:
            yield from _target_names(element)
    elif isinstance(target, ast.Starred):
        yield from _target_names(target.value)
    elif isinstance(target, (ast.Subscript, ast.Attribute)):
        # An inner mutation of the object a name refers to.
        yield from _target_names(target.value)


def _statement_binding_targets(node: ast.stmt) -> list[ast.expr]:
    """Return the binding targets a module-executed statement establishes."""
    if isinstance(node, ast.Assign):
        return list(node.targets)
    if isinstance(node, ast.AugAssign):
        return [node.target]
    if isinstance(node, ast.AnnAssign):
        return [node.target]
    if isinstance(node, ast.Delete):
        return list(node.targets)
    if isinstance(node, (ast.For, ast.AsyncFor)):
        return [node.target]
    if isinstance(node, (ast.With, ast.AsyncWith)):
        return [
            item.optional_vars for item in node.items if item.optional_vars is not None
        ]
    return []


def _match_pattern_names(pattern: ast.pattern) -> Iterator[str]:
    """Yield every name a module-executed ``match`` pattern captures."""
    if isinstance(pattern, ast.MatchAs) and pattern.name:
        yield pattern.name
    elif isinstance(pattern, ast.MatchStar) and pattern.name:
        yield pattern.name
    elif isinstance(pattern, ast.MatchMapping) and pattern.rest:
        yield pattern.rest
    for child in ast.iter_child_nodes(pattern):
        if isinstance(child, ast.pattern):
            yield from _match_pattern_names(child)


def _mutation_from_binding_targets(
    node: ast.stmt, nested: bool, names: set[str]
) -> str | None:
    """Return the first binding-target mutation of *names* in a statement."""
    for target in _statement_binding_targets(node):
        bound = set(_target_names(target))
        if not bound & names:
            continue
        if (
            not nested
            and isinstance(node, (ast.Assign, ast.AnnAssign))
            and isinstance(target, ast.Name)
        ):
            continue  # the module-level declaration itself is carried
        return sorted(bound & names)[0]
    return None


def _mutation_from_control_flow(node: ast.stmt, names: set[str]) -> str | None:
    """Return a name a try handler or match pattern binds in a statement."""
    if isinstance(node, (ast.Try, ast.TryStar)):
        for handler in node.handlers:
            if handler.name in names:
                return handler.name
    if isinstance(node, ast.Match):
        for case in node.cases:
            captured = set(_match_pattern_names(case.pattern))
            if captured & names:
                return sorted(captured & names)[0]
    return None


def _mutation_from_expressions(node: ast.stmt, names: set[str]) -> str | None:
    """Return a name an evaluated expression binds or mutates in a statement."""
    for child in _module_executed_expression_nodes(node):
        if (
            isinstance(child, ast.NamedExpr)
            and isinstance(child.target, ast.Name)
            and child.target.id in names
        ):
            return child.target.id
        if (
            isinstance(child, ast.Call)
            and isinstance(child.func, ast.Attribute)
            and child.func.attr in _NAMESPACE_MUTATING_METHODS
        ):
            receiver_names = set(_target_names(child.func.value))
            if receiver_names & names:
                return sorted(receiver_names & names)[0]
    return None


def _module_level_mutation(tree: ast.Module, names: set[str]) -> str | None:
    """Return the first mutation of one of *names* that module import runs.

    A binding mutated after its declaration (``SQL.append(...)`` in a loop,
    ``MAPPING["key"] = ...``, an ``if``-nested rebinding or unpacking,
    a loop target, ``SQL += [...]``, ``del SQL[...]``) is not reproduced by
    carrying the declaration's source segment, so carrying a reference to it
    would change the operation silently.
    """
    for node, nested in _module_executed_statements(tree.body):
        mutation = _mutation_from_binding_targets(node, nested, names)
        if mutation is not None:
            return mutation
        mutation = _mutation_from_control_flow(node, names)
        if mutation is not None:
            return mutation
        mutation = _mutation_from_expressions(node, names)
        if mutation is not None:
            return mutation
    return None


def _module_level_bindings(tree: ast.Module) -> dict[str, list[ast.stmt]]:
    """Map every name bound at module level to the statements that bind it."""
    bindings: dict[str, list[ast.stmt]] = {}
    for node in tree.body:
        names: list[str] = []
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Import):
            names.extend(
                alias.asname or alias.name.split(".", maxsplit=1)[0]
                for alias in node.names
            )
        elif isinstance(node, ast.ImportFrom):
            names.extend(alias.asname or alias.name for alias in node.names)
        elif isinstance(node, ast.Assign):
            names.extend(
                target.id for target in node.targets if isinstance(target, ast.Name)
            )
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            if isinstance(node.target, ast.Name):
                names.append(node.target.id)
        for name in names:
            bindings.setdefault(name, []).append(node)
    return bindings


def _referenced_names(node: ast.AST) -> set[str]:
    """Return every name a node reads."""
    return {
        child.id
        for child in ast.walk(node)
        if isinstance(child, ast.Name) and isinstance(child.ctx, ast.Load)
    }


def _validate_operations_declaration(
    migration_class: ast.ClassDef, *, donor_name: str
) -> None:
    """Reject any dynamic construction of the operations list.

    A later ``operations.append(...)`` would otherwise escape the literal-list
    inspection and be removed with the donor history, silently dropping the
    operation it added.
    """
    for statement in migration_class.body:
        if isinstance(
            statement,
            (
                ast.If,
                ast.For,
                ast.AsyncFor,
                ast.While,
                ast.Try,
                ast.With,
                ast.AsyncWith,
            ),
        ):
            raise ValueError(
                f"{donor_name}: the Migration class contains a dynamic "
                "statement that cannot be inspected"
            )

    def _mutates_operations(target: ast.expr, *, declaration: bool) -> bool:
        if isinstance(target, ast.Name):
            # A plain name target is the single operations declaration; any
            # other plain-name binding of it (augmented or deleted) is dynamic.
            return target.id == "operations" and not declaration
        return (
            isinstance(target, (ast.Subscript, ast.Attribute))
            and isinstance(target.value, ast.Name)
            and target.value.id == "operations"
        )

    for node in ast.walk(migration_class):
        mutation = False
        if isinstance(node, ast.AugAssign):
            mutation = _mutates_operations(node.target, declaration=False)
        elif isinstance(node, ast.AnnAssign):
            mutation = _mutates_operations(node.target, declaration=True)
        elif isinstance(node, ast.Assign):
            mutation = any(
                _mutates_operations(target, declaration=True) for target in node.targets
            )
        elif isinstance(node, ast.Delete):
            mutation = any(
                _mutates_operations(target, declaration=False)
                for target in node.targets
            )
        if mutation:
            raise ValueError(f"{donor_name}: operations are built dynamically")
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "operations"
            and node.func.attr in _OPERATIONS_MUTATING_METHODS
        ):
            raise ValueError(f"{donor_name}: operations are built dynamically")


def _definition_source_segment(text: str, statement: ast.stmt) -> str | None:
    """Return a definition's source including its decorators.

    ``ast.get_source_segment`` starts a decorated function or class at the
    ``def``/``class`` line, so the decorator lines must be included explicitly
    or the carried definition would silently lose its wrapper.
    """
    decorators = getattr(statement, "decorator_list", [])
    start = statement.lineno
    if decorators:
        start = min(start, *(decorator.lineno for decorator in decorators))
    end = statement.end_lineno
    if end is None:
        return ast.get_source_segment(text, statement)
    lines = text.splitlines(keepends=True)
    return "".join(lines[start - 1 : end])


def _symtable_global_names(table: symtable.SymbolTable) -> set[str]:
    """Return the module-level names a symbol table (and its children) read."""
    names = {
        symbol.get_name()
        for symbol in table.get_symbols()
        if symbol.is_referenced() and symbol.is_global()
    }
    for child in table.get_children():
        names |= _symtable_global_names(child)
    return names


def _evaluated_definition_names(statement: ast.stmt) -> set[str]:
    """Return the names a def/class statement reads in its enclosing scope.

    Decorators, default values, annotations, and base classes are evaluated
    where the definition is created, not inside it, so they are module
    dependencies like any other reference.
    """
    nodes: list[ast.AST] = []
    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
        nodes.extend(statement.decorator_list)
        arguments = statement.args
        nodes.extend(arg for arg in arguments.defaults if arg is not None)
        nodes.extend(arg for arg in arguments.kw_defaults if arg is not None)
        for argument in [
            *arguments.posonlyargs,
            *arguments.args,
            *arguments.kwonlyargs,
        ]:
            if argument.annotation is not None:
                nodes.append(argument.annotation)
        for optional_argument in (arguments.vararg, arguments.kwarg):
            if (
                optional_argument is not None
                and optional_argument.annotation is not None
            ):
                nodes.append(optional_argument.annotation)
        if statement.returns is not None:
            nodes.append(statement.returns)
    elif isinstance(statement, ast.ClassDef):
        nodes.extend(statement.bases)
        nodes.extend(statement.keywords)
        nodes.extend(statement.decorator_list)
    names: set[str] = set()
    for node in nodes:
        names |= _referenced_names(node)
    return names


def _definition_required_names(text: str) -> dict[str, set[str]]:
    """Map each top-level def/class name to the module names it requires.

    The interpreter's own symbol tables decide scope, so function parameters,
    local assignments, comprehension targets, and class namespaces are never
    mistaken for module-level dependencies.
    """
    try:
        module_table = symtable.symtable(text, "<migration>", "exec")
        tree = ast.parse(text)
    except SyntaxError:
        return {}
    children = {child.get_name(): child for child in module_table.get_children()}
    required: dict[str, set[str]] = {}
    for statement in tree.body:
        if not isinstance(
            statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        table = children.get(statement.name)
        names = _symtable_global_names(table) if table is not None else set()
        names |= _evaluated_definition_names(statement)
        required[statement.name] = names
    return required


def _class_attribute_declaration(node: ast.ClassDef, attribute: str) -> ast.expr | None:
    """Return the class body's value for an attribute, or None when absent.

    Raises when the attribute is declared more than once or through an
    augmented assignment, because its effective value cannot be established
    statically.
    """
    value: ast.expr | None = None
    declarations = 0
    for statement in node.body:
        if isinstance(statement, ast.AugAssign):
            if (
                isinstance(statement.target, ast.Name)
                and statement.target.id == attribute
            ):
                raise ValueError(f"{attribute} is built dynamically")
            continue
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if not any(
            isinstance(target, ast.Name) and target.id == attribute
            for target in targets
        ):
            continue
        declarations += 1
        value = statement.value
    if declarations > 1:
        raise ValueError(f"{attribute} is declared more than once")
    return value


def _validate_migration_class_attributes(
    migration_class: ast.ClassDef, *, donor_name: str
) -> None:
    """Fail closed on Migration class statements the carry cannot reproduce."""
    for statement in migration_class.body:
        if isinstance(statement, ast.Expr):
            continue  # class docstring
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            raise ValueError(
                f"{donor_name}: the Migration class contains a statement that "
                "cannot be carried"
            )
        for target in (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        ):
            if not isinstance(target, ast.Name) or (
                target.id not in _SUPPORTED_MIGRATION_CLASS_ATTRIBUTES
            ):
                raise ValueError(
                    f"{donor_name}: the Migration class declares unsupported "
                    f"attribute {getattr(target, 'id', '?')!r}"
                )


def _validate_migration_dependencies(
    migration_class: ast.ClassDef, *, label: str, donor_name: str
) -> None:
    """Fail closed unless every dependency edge is a same-app literal."""
    dependencies = _class_attribute_declaration(migration_class, "dependencies")
    if dependencies is None:
        return
    if not isinstance(dependencies, (ast.List, ast.Tuple)):
        raise ValueError(f"{donor_name}: dependencies cannot be resolved statically")
    for element in dependencies.elts:
        if not (isinstance(element, (ast.Tuple, ast.List)) and len(element.elts) == 2):
            raise ValueError(
                f"{donor_name}: dependencies cannot be resolved statically"
            )
        app_label, migration_name = element.elts
        if not (
            isinstance(app_label, ast.Constant)
            and isinstance(app_label.value, str)
            and isinstance(migration_name, ast.Constant)
            and isinstance(migration_name.value, str)
        ):
            raise ValueError(
                f"{donor_name}: dependencies cannot be resolved statically"
            )
        if app_label.value != label:
            raise ValueError(
                f"{donor_name}: depends on app {app_label.value!r}; only "
                "same-app dependencies can be carried safely"
            )


def _migration_class_is_atomic(
    migration_class: ast.ClassDef, *, donor_name: str
) -> bool:
    """Return whether the Migration class declares a literal ``atomic = False``."""
    atomic = _class_attribute_declaration(migration_class, "atomic")
    if atomic is None:
        return False
    if isinstance(atomic, ast.Constant) and atomic.value is False:
        return True
    raise ValueError(f"{donor_name}: atomic cannot be resolved statically")


def _validate_migration_class(
    migration_class: ast.ClassDef, *, label: str, donor_name: str
) -> bool:
    """Validate a donor Migration class and return whether it is non-atomic."""
    _validate_migration_class_attributes(migration_class, donor_name=donor_name)
    _validate_migration_dependencies(
        migration_class, label=label, donor_name=donor_name
    )
    return _migration_class_is_atomic(migration_class, donor_name=donor_name)
