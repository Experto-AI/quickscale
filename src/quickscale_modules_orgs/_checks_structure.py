"""Removal-boundary static analysis helpers for the orgs system checks.

``checks.py`` owns the registered check entry points, the privileged-command
declaration, and the RLS boot guard; the AST helpers that follow a boundary
implementation's entry path, compare live constants, and build the discharge
messages live here (Module Conventions rule 28).  ``checks._boundary_implementations``
stays a patch seam on the facade and is passed into the wiring check below.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from collections.abc import Callable, Iterator

from django.apps import apps
from django.core.checks import Error

from quickscale_modules_orgs.removal import (
    ORGANIZATION_MODEL_LABEL,
    REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE,
    ExternalProviderField,
    OrganizationRemovalObligation,
    RemovalAction,
    RemovalBoundary,
    coordinator_discharge_actions,
    removal_boundary_implementations,
)
from quickscale_modules_orgs.tenancy import has_organization_id_field


def _constant_value(node: ast.AST) -> tuple[bool, object]:
    """Resolve *node* as a constant expression, or report it unresolved.

    Only literals, boolean negation, boolean operators, and comparisons over
    resolvable operands are folded, so a branch that is provably never taken
    (``if False``, ``if 1 == 0``, ``if not True``) is skipped.  A predicate
    beyond this fragment is treated as reachable: the walk is a best-effort
    static guard, and the coordinator's runtime ``finish`` is the backstop.
    """
    if isinstance(node, ast.Constant):
        return True, node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return _negated_constant(node.operand)
    if isinstance(node, ast.BoolOp):
        return _boolean_constant(node)
    if isinstance(node, ast.Compare):
        return _comparison_constant(node)
    return False, None


def _negated_constant(operand: ast.AST) -> tuple[bool, object]:
    """Resolve a ``not`` expression over one foldable operand."""
    resolved, value = _constant_value(operand)
    return (True, not value) if resolved else (False, None)


def _boolean_constant(node: ast.BoolOp) -> tuple[bool, object]:
    """Fold an ``and``/``or`` expression with short-circuit semantics."""
    is_and = isinstance(node.op, ast.And)
    result: object = None
    for value in node.values:
        resolved, result = _constant_value(value)
        if not resolved:
            return False, None
        if is_and and not result:
            return True, result
        if not is_and and result:
            return True, result
    return True, result


def _comparison_constant(node: ast.Compare) -> tuple[bool, object]:
    """Fold a chain of comparisons over resolvable operands."""
    resolved, left = _constant_value(node.left)
    if not resolved:
        return False, None
    for operator, comparator in zip(node.ops, node.comparators, strict=True):
        resolved, right = _constant_value(comparator)
        if not resolved:
            return False, None
        outcome = _compare_constants(operator, left, right)
        if outcome is None:
            return False, None
        if not outcome:
            return True, False
        left = right
    return True, True


def _compare_constants(operator: ast.cmpop, left: object, right: object) -> bool | None:
    """Compare two resolved constants, or report an unsupported operator."""
    try:
        if isinstance(operator, ast.Eq):
            return bool(left == right)
        if isinstance(operator, ast.NotEq):
            return bool(left != right)
        if isinstance(operator, ast.Is):
            return left is right
        if isinstance(operator, ast.IsNot):
            return left is not right
        if isinstance(operator, ast.In):
            return bool(left in right)  # type: ignore[operator]
        if isinstance(operator, ast.NotIn):
            return bool(left not in right)  # type: ignore[operator]
    except TypeError:
        return None
    return None


def _constant_falsey(node: ast.AST) -> bool:
    """Return whether *node* is a provably false constant expression."""
    resolved, value = _constant_value(node)
    return resolved and not value


def _reachable_nodes(node: ast.AST) -> Iterator[ast.AST]:
    """Yield *node* and every child an execution can reach.

    A branch guarded by a provably false constant expression is skipped, so
    coordinator calls kept behind ``if False`` or ``if 1 == 0`` do not count
    as boundary wiring.
    """
    yield node
    for child in ast.iter_child_nodes(node):
        if isinstance(child, ast.If) and _constant_falsey(child.test):
            for alternative in child.orelse:
                yield from _reachable_nodes(alternative)
            continue
        if isinstance(child, ast.While) and _constant_falsey(child.test):
            for alternative in child.orelse:
                yield from _reachable_nodes(alternative)
            continue
        yield from _reachable_nodes(child)


def _discharge_stage_names(source: str) -> set[str]:
    """Return the ``RemovalAction`` names *source* discharges through the coordinator."""
    names: set[str] = set()
    for node in _reachable_nodes(ast.parse(source)):
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        if (
            not isinstance(function, ast.Attribute)
            or function.attr != "discharge_stage"
        ):
            continue
        for argument in node.args:
            if (
                isinstance(argument, ast.Attribute)
                and isinstance(argument.value, ast.Name)
                and argument.value.id == "RemovalAction"
            ):
                names.add(argument.attr)
    return names


def _calls_coordinator_finish(source: str) -> bool:
    """Return whether *source* calls the coordinator's completeness guard."""
    return any(
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "finish"
        for node in _reachable_nodes(ast.parse(source))
    )


def _function_bodies(tree: ast.Module) -> dict[str, ast.AST]:
    """Map module-level function names and ``Class.method`` qualnames to nodes."""
    bodies: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bodies.setdefault(node.name, node)
        elif isinstance(node, ast.ClassDef):
            for child in node.body:
                if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    bodies.setdefault(f"{node.name}.{child.name}", child)
    return bodies


def _called_function_names(node: ast.AST, owner: str) -> set[str]:
    """Return the qualnames *node* calls, resolving ``self`` calls to *owner*."""
    owner_class = owner.split(".")[0] if "." in owner else ""
    names: set[str] = set()
    for child in _reachable_nodes(node):
        if not isinstance(child, ast.Call):
            continue
        function = child.func
        if isinstance(function, ast.Name):
            names.add(function.id)
        elif isinstance(function, ast.Attribute):
            if (
                owner_class
                and isinstance(function.value, ast.Name)
                and function.value.id == "self"
            ):
                names.add(f"{owner_class}.{function.attr}")
            else:
                names.add(function.attr)
    return names


def _entry_function_source(source: str, entry_name: str) -> str | None:
    """Return *entry_name*'s body and every function body it reaches.

    Wiring is asserted over the executing path only: a coordinator call kept in
    an unreachable helper does not count, so a boundary whose entry point stops
    routing a stage fails the check.
    """
    bodies = _function_bodies(ast.parse(source))
    if entry_name not in bodies:
        return None
    reachable: set[str] = set()
    pending = [entry_name]
    while pending:
        name = pending.pop()
        if name in reachable or name not in bodies:
            continue
        reachable.add(name)
        pending.extend(_called_function_names(bodies[name], name))
    return "\n".join(ast.unparse(bodies[name]) for name in sorted(reachable))


def _resolved_boundary_implementations(
    boundary_implementations: Callable[[], dict[RemovalBoundary, tuple[str, str, str]]]
    | None,
) -> Callable[[], dict[RemovalBoundary, tuple[str, str, str]]]:
    """Return the caller's declared-implementation lookup or the module default."""
    if boundary_implementations is None:
        return removal_boundary_implementations
    return boundary_implementations


def _boundary_wiring_messages(
    *,
    boundary_implementations: Callable[[], dict[RemovalBoundary, tuple[str, str, str]]]
    | None = None,
) -> list:
    """Report boundary implementations that bypass the shared coordinator.

    A boundary that stops discharging a stage, or stops calling ``finish``,
    leaves declared obligations unenforced while its declarations still look
    valid, so the check follows the implementing module's entry path and fails
    closed when a routed stage or the completeness guard is missing from it.
    The declared-implementation lookup arrives as a parameter so the caller's
    ``checks._boundary_implementations`` patch seam keeps resolving; a direct
    caller with no argument falls back to the removal-level declaration.
    """
    messages: list = []
    try:
        implementations = _resolved_boundary_implementations(boundary_implementations)()
    except (TypeError, ValueError) as exc:
        return [
            Error(
                f"Failed to read the declared removal-boundary implementations: {exc}",
                hint=(
                    "Declare each boundary implementation on its owner's AppConfig "
                    f"as a '{REMOVAL_BOUNDARY_IMPLEMENTATIONS_ATTRIBUTE}' mapping."
                ),
                id="quickscale_orgs.E002",
            )
        ]
    for boundary, implementation in implementations.items():
        app_name, module_path, entry_name = implementation
        if not apps.is_installed(app_name):
            continue
        module = importlib.import_module(module_path)
        try:
            source = inspect.getsource(module)
        except OSError as exc:
            messages.append(
                Error(
                    f"Could not read the {boundary.value!r} boundary "
                    f"implementation {module_path}: {exc}",
                    hint="Keep boundary implementations in readable source files.",
                    id="quickscale_orgs.E002",
                )
            )
            continue
        entry_source = _entry_function_source(source, entry_name)
        if entry_source is None:
            messages.append(
                Error(
                    f"The {boundary.value!r} boundary implementation "
                    f"{module_path} has no {entry_name!r} entry point to check.",
                    hint="Name the removal entry point the check follows.",
                    id="quickscale_orgs.E002",
                )
            )
            continue
        missing = sorted(
            action.value
            for action in coordinator_discharge_actions(boundary)
            if action.name not in _discharge_stage_names(entry_source)
        )
        if missing:
            messages.append(
                Error(
                    f"The {boundary.value!r} boundary implementation {module_path} "
                    "does not route these stages through the shared coordinator: "
                    f"{', '.join(missing)}.",
                    hint=(
                        "Discharge every declared stage with "
                        "RemovalCoordinator.discharge_stage on the entry path."
                    ),
                    id="quickscale_orgs.E002",
                )
            )
        if not _calls_coordinator_finish(entry_source):
            messages.append(
                Error(
                    f"The {boundary.value!r} boundary implementation {module_path} "
                    "never calls RemovalCoordinator.finish, so a stage it skips "
                    "would pass silently.",
                    hint="Call coordinator.finish() once the removal completes.",
                    id="quickscale_orgs.E002",
                )
            )
    return messages


def _route_mismatch_messages(obligation: OrganizationRemovalObligation) -> list[Error]:
    """Report boundary actions the shared coordinator has no route for."""
    messages: list[Error] = []
    for boundary in RemovalBoundary:
        action = obligation.action_for(boundary)
        if action is RemovalAction.SKIP:
            continue
        if action in coordinator_discharge_actions(boundary):
            continue
        messages.append(
            Error(
                f"Organization-removal obligation {obligation.name!r} "
                f"declares {action.value!r} for the {boundary.value!r} "
                "boundary, but that boundary has no shared-coordinator "
                "route to discharge it.",
                hint=(
                    f"Give the {boundary.value!r} boundary a coordinator "
                    f"route for {action.value!r}, or declare SKIP with a "
                    "reason when the boundary must not perform it."
                ),
                id="quickscale_orgs.E002",
            )
        )
    return messages


def _reconcile_mismatch_message(
    obligation: OrganizationRemovalObligation,
) -> Error | None:
    """Report anonymize reconciliation whose declared fields have no guard."""
    if obligation.anonymize_action is not RemovalAction.RECONCILE:
        return None
    if all(
        provider_field.boundary_guarded
        for provider_field in obligation.external_provider_fields
    ):
        return None
    return Error(
        f"Organization-removal obligation {obligation.name!r} "
        "declares 'reconcile' for the 'anonymize' boundary but "
        "declares provider fields no boundary guard reconciles.",
        hint=(
            "Declare SKIP when the boundary retains the rows, or "
            "mark the fields boundary_guarded when a boundary guard "
            "decides their liveness."
        ),
        id="quickscale_orgs.E002",
    )


def _uninspectable_refusal_field_messages(
    obligation: OrganizationRemovalObligation,
    provider_field: ExternalProviderField,
) -> list[Error]:
    """Report a declared provider field no boundary can inspect per organization."""
    try:
        model = apps.get_model(provider_field.model_label)
    except LookupError:
        return []
    if model._meta.label_lower == ORGANIZATION_MODEL_LABEL or has_organization_id_field(
        model
    ):
        return []
    return [
        Error(
            f"Organization-removal obligation {obligation.name!r} declares "
            f"provider field {provider_field.model_label}."
            f"{provider_field.field_name}, but that model is not "
            "organization-scoped, so no removal boundary can inspect it.",
            hint=(
                "Declare provider fields on models that carry an "
                "organization_id or on the organization row, or mark the field "
                "boundary_guarded when a boundary guard decides its liveness."
            ),
            id="quickscale_orgs.E002",
        )
    ]


def _obligation_mismatch_messages(
    obligation: OrganizationRemovalObligation,
) -> list[Error]:
    """Report every unsupported declaration on one obligation."""
    messages = _route_mismatch_messages(obligation)
    reconcile_message = _reconcile_mismatch_message(obligation)
    if reconcile_message is not None:
        messages.append(reconcile_message)
    messages.extend(
        message
        for provider_field in obligation.external_provider_fields
        if not provider_field.boundary_guarded
        for message in _uninspectable_refusal_field_messages(obligation, provider_field)
    )
    return messages
