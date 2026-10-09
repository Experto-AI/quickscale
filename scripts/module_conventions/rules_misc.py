"""Checks/errors, email, notification person-link, and stub-exemption rules."""

from __future__ import annotations

import ast
import tomllib
from collections.abc import Mapping

from scripts.module_conventions.core import (
    Corpus,
    _call_func_name,
    _class_names,
    _parse,
    _static_truth,
)


def _calls_within(node: ast.AST) -> list[ast.Call]:
    """Return calls reachable in a node, skipping statically dead branches."""
    calls: list[ast.Call] = []
    pending = [node]
    while pending:
        current = pending.pop()
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if isinstance(current, ast.Lambda):
            # The body is deferred; only default arguments evaluate at definition.
            for default in [*current.args.defaults, *current.args.kw_defaults]:
                if default is not None:
                    pending.append(default)
            continue
        if isinstance(current, ast.If):
            truth = _static_truth(current.test)
            if truth is True:
                pending.append(current.test)
                pending.extend(current.body)
                continue
            if truth is False:
                pending.append(current.test)
                pending.extend(current.orelse)
                continue
        if isinstance(current, ast.While) and _static_truth(current.test) is False:
            pending.append(current.test)
            pending.extend(current.orelse)
            continue
        if isinstance(current, ast.IfExp):
            truth = _static_truth(current.test)
            if truth is True:
                pending.append(current.test)
                pending.append(current.body)
                continue
            if truth is False:
                pending.append(current.test)
                pending.append(current.orelse)
                continue
        if isinstance(current, ast.BoolOp):
            for operand in current.values:
                pending.append(operand)
                truth = _static_truth(operand)
                if (isinstance(current.op, ast.And) and truth is False) or (
                    isinstance(current.op, ast.Or) and truth is True
                ):
                    break
            continue
        if isinstance(current, ast.Call):
            calls.append(current)
        pending.extend(ast.iter_child_nodes(current))
    return calls


def _direct_calls(node: ast.AST) -> list[ast.Call]:
    """Return calls executed by a function body before it terminates."""
    calls: list[ast.Call] = []
    _collect_direct_calls(list(getattr(node, "body", [])), calls)
    return calls


def _statements_terminate(statements: list[ast.stmt]) -> bool:
    """Return True when every executed route through these statements ends in return/raise."""
    return _collect_direct_calls(statements, [])


def _match_exhaustive(cases: list[ast.match_case]) -> bool:
    """Return True when an unguarded catch-all case matches every value."""
    return any(
        isinstance(case.pattern, ast.MatchAs)
        and case.pattern.pattern is None
        and case.guard is None
        for case in cases
    )


def _effective_cases(cases: list[ast.match_case]) -> list[ast.match_case]:
    """Drop cases whose guard is statically false; their bodies never run."""
    return [case for case in cases if case.guard is None or _static_truth(case.guard) is not False]


def _may_fall_through(statements: list[ast.stmt]) -> bool:
    """Return True when some route through every statement completes normally."""
    for statement in statements:
        if isinstance(statement, (ast.Raise, ast.Return, ast.Break, ast.Continue)):
            return False
        if isinstance(statement, ast.If):
            truth = _static_truth(statement.test)
            if truth is True:
                if not _may_fall_through(statement.body):
                    return False
            elif truth is False:
                if not _may_fall_through(statement.orelse):
                    return False
            elif not (_may_fall_through(statement.body) or _may_fall_through(statement.orelse)):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            if not _may_fall_through(statement.body):
                return False
            continue
        if isinstance(statement, ast.While) and _static_truth(statement.test) is True:
            # An endless loop completes only through a break.
            if not _contains_jump(statement.body, ast.Break):
                return False
            continue
        if isinstance(statement, (ast.For, ast.While)):
            # A loop whose condition may be false at once runs zero times.
            continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            if not _may_fall_through(statement.finalbody):
                return False
            normal_falls = _may_fall_through(statement.body) and _may_fall_through(statement.orelse)
            handler_falls = any(_may_fall_through(handler.body) for handler in statement.handlers)
            if not (normal_falls or handler_falls):
                return False
            continue
        if isinstance(statement, ast.Match):
            cases = _effective_cases(statement.cases)
            if _match_exhaustive(cases) and not any(_may_fall_through(case.body) for case in cases):
                return False
            continue
    return True


def _contains_jump(statements: list[ast.stmt], kind: type[ast.Break]) -> bool:
    """
    Return True when a reachable break/continue targeting the analyzed loop exists.

    A jump inside a nested loop targets that loop, a jump in a statically dead
    branch never runs, and a jump after an unconditional return/raise or after
    another jump is unreachable, so none of them counts.
    """
    for statement in statements:
        if isinstance(statement, (ast.Raise, ast.Return)):
            return False
        if isinstance(statement, ast.Break):
            return kind is ast.Break
        if isinstance(statement, ast.Continue):
            return kind is ast.Continue
        if isinstance(statement, (ast.For, ast.While)):
            # A nested loop's else suite is outside it and can still jump out of
            # the loop being analyzed; the nested loop itself may terminate the
            # enclosing sequence.
            if _contains_jump(statement.orelse, kind):
                return True
            if _statements_terminate([statement]) or not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, ast.If):
            truth = _static_truth(statement.test)
            if truth is True:
                if _contains_jump(statement.body, kind):
                    return True
                if not _may_fall_through(statement.body):
                    return False
                continue
            if truth is False:
                if _contains_jump(statement.orelse, kind):
                    return True
                if not _may_fall_through(statement.orelse):
                    return False
                continue
            if _contains_jump(statement.body, kind) or _contains_jump(statement.orelse, kind):
                return True
            if not _may_fall_through(statement.body) and not _may_fall_through(statement.orelse):
                return False
            continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            if not _may_fall_through(statement.finalbody):
                # A return/raise or jump in ``finally`` overrides the pending jump.
                return _contains_jump(statement.finalbody, kind)
            if (
                _contains_jump(statement.body, kind)
                or any(_contains_jump(handler.body, kind) for handler in statement.handlers)
                or _contains_jump(statement.orelse, kind)
                or _contains_jump(statement.finalbody, kind)
            ):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            if _contains_jump(statement.body, kind):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, ast.Match):
            if any(_contains_jump(case.body, kind) for case in _effective_cases(statement.cases)):
                return True
            if not _may_fall_through([statement]):
                return False
    return False


def _contains_break(statements: list[ast.stmt]) -> bool:
    """Return True when a reachable break can leave this loop before its else suite."""
    return _contains_jump(statements, ast.Break)


def _contains_continue(statements: list[ast.stmt]) -> bool:
    """Return True when a reachable continue can restart this loop's next iteration."""
    return _contains_jump(statements, ast.Continue)


def _collect_direct_calls(statements: list[ast.stmt], calls: list[ast.Call]) -> bool:
    """Collect executed calls in order; return True when the sequence terminates."""
    for statement in statements:
        if isinstance(statement, ast.Raise):
            return True
        if isinstance(statement, ast.Return):
            if statement.value is not None:
                calls.extend(_calls_within(statement.value))
            return True
        if isinstance(statement, (ast.Break, ast.Continue)):
            # Control leaves this statement sequence: later calls are unreachable.
            return False
        if isinstance(statement, ast.If):
            test = statement.test
            calls.extend(_calls_within(test))
            truth = _static_truth(test)
            if truth is not None:
                branch = statement.body if truth else statement.orelse
                if _collect_direct_calls(branch, calls):
                    return True
                if not _may_fall_through(branch):
                    return False
            else:
                body_terminates = _collect_direct_calls(statement.body, calls)
                else_terminates = _collect_direct_calls(statement.orelse, calls)
                if body_terminates and else_terminates:
                    return True
                if not _may_fall_through([statement]):
                    return False
            continue
        if isinstance(statement, (ast.With, ast.AsyncWith)):
            for item in statement.items:
                calls.extend(_calls_within(item.context_expr))
            if _collect_direct_calls(statement.body, calls):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, (ast.For, ast.While)):
            iterable = statement.test if isinstance(statement, ast.While) else statement.iter
            calls.extend(_calls_within(iterable))
            if isinstance(statement, ast.While) and _static_truth(statement.test) is False:
                if _collect_direct_calls(statement.orelse, calls):
                    return True
                if not _may_fall_through([statement]):
                    return False
                continue
            _collect_direct_calls(statement.body, calls)
            else_terminates = _collect_direct_calls(statement.orelse, calls)
            # ``break`` leaves the loop without running ``else``, so a terminating
            # else suite does not terminate the enclosing sequence when the loop
            # body can break out.
            if else_terminates and not _contains_break(statement.body):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, ast.Match):
            calls.extend(_calls_within(statement.subject))
            for case in statement.cases:
                if case.guard is not None:
                    calls.extend(_calls_within(case.guard))
            cases = _effective_cases(statement.cases)
            case_results = [_collect_direct_calls(case.body, calls) for case in cases]
            if cases and all(case_results) and _match_exhaustive(cases):
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        if isinstance(statement, (ast.Try, ast.TryStar)):
            body_terminates = _collect_direct_calls(statement.body, calls)
            handler_results = [
                _collect_direct_calls(handler.body, calls) for handler in statement.handlers
            ]
            handlers_terminate = bool(handler_results) and all(handler_results)
            else_terminates = False
            if not body_terminates:
                else_terminates = _collect_direct_calls(statement.orelse, calls)
            final_terminates = _collect_direct_calls(statement.finalbody, calls)
            raise_path_terminates = (not statement.handlers) or handlers_terminate
            if final_terminates:
                return True
            if body_terminates and raise_path_terminates:
                return True
            if else_terminates and raise_path_terminates:
                return True
            if not _may_fall_through([statement]):
                return False
            continue
        calls.extend(_calls_within(statement))
    return False


def _ready_scope_signature_calls(tree: ast.Module) -> tuple[bool, list[str]]:
    """
    Return whether registration is reachable and the calls' execution order.

    Registration must run from the AppConfig's own ``ready()`` scope; the
    same traversal follows one level of ``self.<method>`` and module-level
    functions, expanding each helper at the position its call executes so the
    returned call names match Python's execution order.
    """
    app_config = next(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
            and any(
                base == "AppConfig" or base.endswith("AppConfig") for base in _class_names(node)
            )
        ),
        None,
    )
    if app_config is None:
        return False, []
    ready = next(
        (
            statement
            for statement in app_config.body
            if isinstance(statement, ast.FunctionDef) and statement.name == "ready"
        ),
        None,
    )
    if ready is None:
        return False, []
    methods: dict[str, ast.FunctionDef] = {
        statement.name: statement
        for statement in app_config.body
        if isinstance(statement, ast.FunctionDef)
    }
    module_functions: dict[str, ast.FunctionDef] = {
        statement.name: statement
        for statement in tree.body
        if isinstance(statement, ast.FunctionDef)
    }
    seen: set[int] = set()
    order: list[str] = []

    def expand(node: ast.FunctionDef) -> None:
        if id(node) in seen:
            return
        seen.add(id(node))
        for call in _direct_calls(node):
            if isinstance(call.func, ast.Name):
                called = call.func.id
                if called in {"register_module_checks", "register_module_settings_check"}:
                    order.append(called)
                if called in module_functions:
                    expand(module_functions[called])
            elif (
                isinstance(call.func, ast.Attribute)
                and isinstance(call.func.value, ast.Name)
                and call.func.value.id == "self"
                and call.func.attr in methods
            ):
                expand(methods[call.func.attr])

    expand(ready)
    return bool(order), order


def _registration_reachable(tree: ast.Module) -> bool:
    """Registration must run from the AppConfig's own ready() scope."""
    reachable, _order = _ready_scope_signature_calls(tree)
    return reachable


def _ready_registration_order(tree: ast.Module) -> list[str]:
    """Return the registration helper calls reachable from ready(), in order."""
    _reachable, order = _ready_scope_signature_calls(tree)
    return order


def _expected_error_base(module_name: str) -> str:
    """Return the one ``<Module>Error`` base name the module must declare."""
    return f"{module_name.capitalize()}Error"


#: Builtin exception bases a module-defined error may subclass without the
#: ``Error`` suffix; the no-exceptions clause treats them as module errors.
_BUILTIN_EXCEPTION_BASES = frozenset(
    {
        "ArithmeticError",
        "AssertionError",
        "AttributeError",
        "EOFError",
        "Exception",
        "ImportError",
        "IndexError",
        "KeyError",
        "LookupError",
        "NameError",
        "NotImplementedError",
        "OSError",
        "RuntimeError",
        "StopIteration",
        "TypeError",
        "ValueError",
    }
)


def _declares_module_error(node: ast.ClassDef) -> bool:
    """Return whether a class is a module-defined error by name or base."""
    if node.name.endswith("Error"):
        return True
    return any(
        base.endswith("Exception") or base.endswith("Error") or base in _BUILTIN_EXCEPTION_BASES
        for base in _class_names(node)
    )


def _api_exception_names(tree: ast.Module) -> set[str]:
    """
    Return the local names a module resolves to DRF's ``APIException``.

    ``APIException`` itself, the attribute form ``exceptions.APIException``
    (whose attribute name ``_class_names`` already reports), and every import
    alias are covered, so the prohibition is checked on the class's base
    regardless of how the module spells it.
    """
    names = {"APIException"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and (node.module or "").endswith("exceptions"):
            for alias in node.names:
                if alias.name == "APIException":
                    names.add(alias.asname or alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith(".APIException"):
                    names.add(alias.asname or alias.name.rsplit(".", 1)[-1])
    return names


def rule_10_checks_errors(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        apps = module.files.get("apps.py")
        if apps is not None and "checks.py" in module.files:
            tree = _parse(apps)
            if not _registration_reachable(tree):
                violations.append(
                    f"rule 10: {module.name}: checks.py exists but ready() registers nothing"
                )
            order = _ready_registration_order(tree)
            if (
                "register_module_checks" in order
                and "register_module_settings_check" in order
                and order.index("register_module_checks")
                < order.index("register_module_settings_check")
            ):
                violations.append(
                    f"rule 10: {module.name}: ready() registers module checks "
                    "before the generic settings check"
                )
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef) and node.name == "ready":
                    if any(isinstance(child, ast.Raise) for child in ast.walk(node)):
                        violations.append(
                            f"rule 10: {module.name}: ready() raises outside the shared helper"
                        )
                    for child in ast.walk(node):
                        if not isinstance(child, (ast.Try, ast.TryStar)) or not child.handlers:
                            continue
                        if any(
                            isinstance(call, ast.Call)
                            and _call_func_name(call)
                            in {
                                "register_module_checks",
                                "register_module_settings_check",
                            }
                            for call in ast.walk(child)
                        ):
                            violations.append(
                                f"rule 10: {module.name}: ready() catches a registration failure"
                            )
        # Rule 10's APIException prohibition is closed-world over every
        # module-defined class in every package file — the hierarchy derives
        # from Exception alone, whatever a class is named, wherever it sits,
        # and however deeply it is nested.
        for rel, text in sorted(module.files.items()):
            if not rel.endswith(".py"):
                continue
            file_tree = _parse(text)
            forbidden = _api_exception_names(file_tree)
            for node in ast.walk(file_tree):
                if not isinstance(node, ast.ClassDef):
                    continue
                if any(parent in forbidden for parent in _class_names(node)):
                    violations.append(
                        f"rule 10: {module.name}: {rel} defines {node.name} deriving "
                        "from APIException; the module hierarchy derives from Exception alone"
                    )
        expected_base = _expected_error_base(module.name)
        exceptions = module.files.get("exceptions.py")
        if exceptions is None:
            for rel, text in sorted(module.files.items()):
                if not rel.endswith(".py"):
                    continue
                for node in ast.walk(_parse(text)):
                    if isinstance(node, ast.ClassDef) and _declares_module_error(node):
                        violations.append(
                            f"rule 10: {module.name}: {rel} defines {node.name} but "
                            "the module ships no exceptions.py"
                        )
            continue
        classes = [node for node in _parse(exceptions).body if isinstance(node, ast.ClassDef)]
        error_classes = [node for node in classes if node.name.endswith("Error")]
        if not error_classes:
            violations.append(f"rule 10: {module.name}: exceptions.py has no {expected_base} base")
            continue
        error_names = {node.name for node in error_classes}
        if expected_base not in error_names:
            violations.append(
                f"rule 10: {module.name}: exceptions.py has no {expected_base} base; "
                "the base is named after the module as spelled"
            )
        for node in error_classes:
            parents = _class_names(node)
            if node.name == expected_base:
                if "Exception" not in parents:
                    violations.append(
                        f"rule 10: {module.name}: {expected_base} does not derive from Exception"
                    )
                continue
            if not parents:
                continue
            if all(parent == "Exception" for parent in parents):
                violations.append(
                    f"rule 10: {module.name}: {node.name} is a second error root, "
                    f"not a subclass of {expected_base}"
                )
                continue
            if not any(parent in error_names for parent in parents):
                violations.append(
                    f"rule 10: {module.name}: {node.name} does not derive from "
                    "the module error base"
                )
    return violations


def rule_20_email(corpus: Corpus) -> list[str]:
    violations: list[str] = []
    for module in corpus.modules:
        if module.name == "notifications":
            continue
        for rel, text in module.files.items():
            if not rel.endswith(".py"):
                continue
            tree = _parse(text)
            imports_mail = any(
                isinstance(node, ast.Import)
                and any(alias.name == "django.core.mail" for alias in node.names)
                or isinstance(node, ast.ImportFrom)
                and (node.module or "").startswith("django.core.mail")
                for node in ast.walk(tree)
            )
            calls_mail = any(
                isinstance(node, ast.Call)
                and _call_func_name(node)
                in {
                    "send_mail",
                    "EmailMessage",
                    "EmailMultiAlternatives",
                    "get_connection",
                }
                for node in ast.walk(tree)
            )
            if imports_mail or calls_mail:
                violations.append(f"rule 20: {module.name}: {rel} sends email directly")
        if "send_notification" in "".join(module.files.values()):
            required = module.manifest.get("required_modules")
            if not isinstance(required, list):
                required = []
            if "notifications" not in required:
                violations.append(
                    f"rule 20: {module.name}: calls send_notification "
                    "without requiring notifications"
                )
    return violations


def _mapping_key_writes(tree: ast.Module, key: str) -> list[int]:
    """Return the line numbers where *key* is written as a mapping key."""
    lines: list[int] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Dict):
            for dict_key in node.keys:
                if isinstance(dict_key, ast.Constant) and dict_key.value == key:
                    lines.append(dict_key.lineno)
        elif isinstance(node, ast.Subscript) and isinstance(node.ctx, ast.Store):
            if isinstance(node.slice, ast.Constant) and node.slice.value == key:
                lines.append(node.lineno)
        elif isinstance(node, ast.Call):
            for keyword in node.keywords:
                if keyword.arg == key:
                    lines.append(keyword.value.lineno)
    return lines


def rule_50_notification_links(corpus: Corpus) -> list[str]:
    """Rule 50: a sender declares whom a notification is about, never by key."""
    violations: list[str] = []
    for module in corpus.modules:
        for rel, text in sorted(module.files.items()):
            if not rel.endswith(".py"):
                continue
            for lineno in _mapping_key_writes(_parse(text), "actor_user_id"):
                violations.append(
                    f"rule 50: {module.name}: {rel}:{lineno} writes the reserved "
                    "notification person-link key 'actor_user_id' in module source; "
                    "pass send_notification(about_users=...) instead"
                )
    return violations


def rule_45_stub_exemptions(corpus: Corpus) -> list[str]:
    """Rule 45: third-party stub exemptions live in the root ``mypy.ini`` only."""
    violations: list[str] = []
    for module in corpus.modules:
        pyproject = module.root_files.get("pyproject.toml")
        if pyproject is None:
            continue
        try:
            data = tomllib.loads(pyproject)
        except tomllib.TOMLDecodeError:
            # Rule 18 reports the unparsable file.
            continue
        tool = data.get("tool")
        mypy = tool.get("mypy") if isinstance(tool, Mapping) else None
        if isinstance(mypy, Mapping):
            violations.append(
                f"rule 45: {module.name}: pyproject.toml declares a per-module [tool.mypy] table"
            )
    return violations
